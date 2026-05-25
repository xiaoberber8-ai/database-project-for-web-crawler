# 在你的 Ubuntu/WSL 终端中安装 FastAPI 和本地运行服务器 uvicorn：
pip install fastapi uvicorn


from fastapi import FastAPI, Depends, Query, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel
from datetime import date
import io
import csv
import re
import os

# 1. 核心：直接从你现有的代码库中导入所有东西！
from Crawl_module import SessionLocal, Content, WebPage, TaskRecord, CrawlerStrategy, Image, CrawlerExecutor

app = FastAPI(title="网络数据爬取管理系统 API (集成测试版)")

# 2. 实例化全局爬虫执行器
global_crawler = CrawlerExecutor()

# 如果 images 文件夹不存在，帮忙建一个，防止挂载静态资源时报错
os.makedirs("./images", exist_ok=True)
app.mount("/images", StaticFiles(directory="./images"), name="images")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 模块一：爬虫真实控制 API
# ==========================================
@app.post("/api/strategy/{strategy_id}/run", summary="真实启动爬虫 (后台运行)")
def run_strategy(strategy_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    strategy = db.query(CrawlerStrategy).filter(CrawlerStrategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    global_crawler.stop_event.clear()
    global_crawler.pause_event.set()
    # 将爬虫任务推入后台，立刻返回成功响应给前端
    background_tasks.add_task(global_crawler.crawl_strategy, strategy_id)
    return {"message": f"策略 {strategy_id} 已在后台开始执行，请查看终端运行日志"}

@app.post("/api/crawler/pause", summary="暂停爬虫")
def pause_crawler(db: Session = Depends(get_db)):
    global_crawler.pause()
    db.query(TaskRecord).filter(TaskRecord.Status == "running").update({"Status": "paused"})
    db.commit()
    return {"message": "爬虫已暂停，数据库状态已同步更新"}

@app.post("/api/crawler/resume", summary="恢复爬虫")
def resume_crawler(db: Session = Depends(get_db)):
    global_crawler.resume()
    db.query(TaskRecord).filter(TaskRecord.Status == "paused").update({"Status": "running"})
    db.commit()
    return {"message": "爬虫已恢复运行，数据库状态已同步更新"}

@app.post("/api/crawler/stop", summary="强制停止爬虫")
def stop_crawler():
    global_crawler.stop()
    return {"message": "发送停止指令成功，爬虫将在当前请求完成后退出"}

# ==========================================
# 模块二：Dashboard 大屏统计
# ==========================================
@app.get("/api/dashboard/stats", summary="获取大屏概览统计")
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
# 模块三：高级检索与高亮 (已优化为 ORM Relationship)
# ==========================================
@app.get("/api/search", summary="高级检索 (支持高亮和分页)")
def advanced_search(
    keyword: str = Query(None, description="搜索关键词"),
    skip: int = Query(0, description="分页起始点"),
    limit: int = Query(20, description="每页数量"),
    db: Session = Depends(get_db)
):
    # 只需要查 Content 表即可，利用 relationship 隐式关联 WebPage 用于排序
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
        
        # 关键词高亮包裹
        if keyword:
            pattern = re.compile(f"({re.escape(keyword)})", re.IGNORECASE)
            title = pattern.sub(r"<mark>\1</mark>", title)
            body_preview = pattern.sub(r"<mark>\1</mark>", body_preview)
            
        data.append({
            "id": content.id,
            "title_highlight": title,
            "preview_highlight": body_preview,
            # 直接调用 relationship 属性！告别元组拆包
            "source_url": content.webpage.url if content.webpage else None,
            "fetch_time": content.webpage.fetch_time if content.webpage else None
        })
        
    return {"total": total, "data": data}

# ==========================================
# 模块四：文章详情与图片预览 (已优化为极简 ORM 调用)
# ==========================================
@app.get("/api/content/{content_id}", summary="获取文章详情及关联图片")
def get_content_detail(content_id: int, db: Session = Depends(get_db)):
    # 仅需查一次 Content！
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="文章不存在")
        
    image_list = []
    # 爽点：直接通过 content.webpage.images 访问，不用再去手动查数据库了！
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
# 模块五：数据导出 (已优化)
# ==========================================
@app.get("/api/export/csv", summary="导出为 CSV 文件")
def export_csv(db: Session = Depends(get_db)):
    # 直接全量获取 Content
    contents = db.query(Content).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "标题", "正文摘要", "抓取时间"])
    
    for content in contents:
        # 直接使用 relationship 提取抓取时间
        fetch_time = content.webpage.fetch_time if content.webpage else None
        time_str = fetch_time.strftime("%Y-%m-%d %H:%M:%S") if fetch_time else ""
        writer.writerow([content.id, content.Title, (content.text_body or "")[:100] + "...", time_str])
        
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=crawled_data.csv"})

# ==========================================
# 模块六：策略管理 API (CRUD)
# ==========================================
class StrategyCreate(BaseModel):
    name: str
    target_url: str
    rules_json: str

@app.post("/api/strategy", summary="新建爬虫策略")
def create_strategy(data: StrategyCreate, db: Session = Depends(get_db)):
    new_strategy = CrawlerStrategy(
        name=data.name,
        target_url=data.target_url,
        rules_json=data.rules_json,
        Status="enabled",
        Frequency="manual"
    )
    db.add(new_strategy)
    db.commit()
    db.refresh(new_strategy)
    
    return {
        "message": "策略创建成功", 
        "id": new_strategy.id,
        "name": new_strategy.name
    }

@app.get("/api/strategy", summary="获取所有策略列表")
def get_strategies(db: Session = Depends(get_db)):
    strategies = db.query(CrawlerStrategy).order_by(CrawlerStrategy.id.desc()).all()
    return strategies

# 编好后，在终端运行
uvicorn main:app --reload
# 启动成功后，打开浏览器，访问 http://127.0.0.1:8000/docs
# 前端根据此来编写代码，对接数据
