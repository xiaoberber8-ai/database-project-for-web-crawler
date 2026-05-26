import io
import csv
import re
import os
from datetime import date
from fastapi import Depends, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

# 1. 核心：直接从队友的新文件中导入 app 实例和数据库模型！
# 这样不仅避免了冲突，还能完美继承队友写好的所有高级接口。
from CRAWLER_NEW import app, get_db, Content, WebPage, TaskRecord, Image

# 2. 挂载图片目录
os.makedirs("./images", exist_ok=True)
app.mount("/images", StaticFiles(directory="./images"), name="images")

# ==========================================
# 补充模块一：Dashboard 大屏统计
# ==========================================
@app.get("/api/dashboard/stats", tags=["前端展示"], summary="获取大屏概览统计")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_content = db.query(Content).count()
    today_new = db.query(WebPage).filter(func.date(WebPage.fetch_time) == date.today()).count()
    active_tasks = db.query(TaskRecord).filter(TaskRecord.Status == "running").count()
    
    return {
        "total_content": total_content,
        "today_new": today_new,
        "active_tasks": active_tasks
    }

# ==========================================
# 补充模块二：高级检索与高亮
# ==========================================
@app.get("/api/search", tags=["前端展示"], summary="高级检索 (支持高亮和分页)")
def advanced_search(
    keyword: str = Query(None, description="搜索关键词"),
    skip: int = Query(0, description="分页起始点"),
    limit: int = Query(20, description="每页数量"),
    db: Session = Depends(get_db)
):
    query = db.query(Content).join(Content.webpage)
    
    if keyword:
        search_rule = f"%{keyword}%"
        query = query.filter(or_(Content.Title.ilike(search_rule), Content.text_body.ilike(search_rule)))
        
    total = query.count()
    results = query.order_by(WebPage.fetch_time.desc()).offset(skip).limit(limit).all()
    
    data = []
    for content in results:
        title = content.Title or ""
        body_preview = (content.text_body or "")[:150] + "..."
        
        if keyword:
            pattern = re.compile(f"({re.escape(keyword)})", re.IGNORECASE)
            title = pattern.sub(r"<mark>\1</mark>", title)
            body_preview = pattern.sub(r"<mark>\1</mark>", body_preview)
            
        data.append({
            "id": content.id,
            "title_highlight": title,
            "preview_highlight": body_preview,
            "source_url": content.webpage.url if content.webpage else None,
            "fetch_time": content.webpage.fetch_time if content.webpage else None
        })
        
    return {"total": total, "data": data}

# ==========================================
# 补充模块三：文章详情与图片预览
# ==========================================
@app.get("/api/content/{content_id}", tags=["前端展示"], summary="获取文章详情及关联图片")
def get_content_detail(content_id: int, db: Session = Depends(get_db)):
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="文章不存在")
        
    image_list = []
    if content.webpage and content.webpage.images:
        image_list = [
            {"url": f"/images/{os.path.basename(img.local_path)}", "desc": img.description} 
            for img in content.webpage.images if img.local_path
        ]

    return {
        "id": content.id,
        "title": content.Title,
        "body": content.text_body,
        "source_url": content.webpage.url if content.webpage else None,
        "images": image_list
    }

# ==========================================
# 补充模块四：数据导出
# ==========================================
@app.get("/api/export/csv", tags=["前端展示"], summary="导出为 CSV 文件")
def export_csv(db: Session = Depends(get_db)):
    contents = db.query(Content).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "标题", "正文摘要", "抓取时间"])
    
    for content in contents:
        fetch_time = content.webpage.fetch_time if content.webpage else None
        time_str = fetch_time.strftime("%Y-%m-%d %H:%M:%S") if fetch_time else ""
        writer.writerow([content.id, content.Title, (content.text_body or "")[:100] + "...", time_str])
        
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=crawled_data.csv"})
