# =========================
# 数据库模型 (完整关联版)
# =========================

class Admin(Base):
    __tablename__ = "admin"
    id = Column(Integer, primary_key=True)
    Username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # 关联：管理员创建的策略
    strategies = relationship("CrawlerStrategy", back_populates="creator")


class CrawlerStrategy(Base):
    __tablename__ = "crawler_strategy"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    target_url = Column(Text, nullable=False)
    rules_json = Column(Text, nullable=False)
    Status = Column(String(50), default="enabled")
    Frequency = Column(String(50), default="manual")
    creator_id = Column(Integer, ForeignKey("admin.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联：双向绑定创建者与任务记录
    creator = relationship("Admin", back_populates="strategies", lazy="joined")
    tasks = relationship("TaskRecord", back_populates="strategy")


class TaskRecord(Base):
    __tablename__ = "task_record"
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey("crawler_strategy.id"), nullable=False, index=True)
    start_time = Column(DateTime)
    Status = Column(String(50), default="pending")
    end_time = Column(DateTime)
    item_count = Column(Integer, default=0)
    error_message = Column(Text)

    # 关联：所属策略，以及该任务下抓取到的所有网页
    strategy = relationship("CrawlerStrategy", back_populates="tasks", lazy="joined")
    webpages = relationship("WebPage", back_populates="task")


class Website(Base):
    __tablename__ = "website"
    id = Column(Integer, primary_key=True)
    domain = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    company_info = Column(Text)
    contact_info = Column(Text)

    # 关联：该网站下包含的所有网页 records
    webpages = relationship("WebPage", back_populates="website")


class WebPage(Base):
    __tablename__ = "webpage"
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("website.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("task_record.id"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, index=True)
    fetch_time = Column(DateTime)
    http_status = Column(Integer)
    process_status = Column(String(50), default="pending")
    page_type = Column(String(50), default="unknown")
    error_message = Column(Text)

    __table_args__ = (
        UniqueConstraint("website_id", "url_hash", name="uq_webpage_website_urlhash"),
    )

    # 核心枢纽关联：向上连网站和任务，向下连内容和图片
    website = relationship("Website", back_populates="webpages")
    task = relationship("TaskRecord", back_populates="webpages")
    contents = relationship("Content", back_populates="webpage")
    images = relationship("Image", back_populates="webpage")


class DataSource(Base):
    __tablename__ = "datasource"
    id = Column(Integer, primary_key=True)
    publisher_name = Column(String(255))
    origin_url = Column(Text)

    # 关联：发布在这个平台上的所有内容记录
    contents = relationship("Content", back_populates="datasource")


class Content(Base):
    __tablename__ = "content"
    id = Column(Integer, primary_key=True)
    webpage_id = Column(Integer, ForeignKey("webpage.id"), nullable=False, index=True)
    datasource_id = Column(Integer, ForeignKey("datasource.id"))
    Title = Column(String(500))
    text_body = Column(Text)
    publish_time = Column(DateTime)
    keywords = Column(Text)

    # 关联：所属的网页主体，以及对应的数据源
    webpage = relationship("WebPage", back_populates="contents")
    datasource = relationship("DataSource", back_populates="contents")


class Image(Base):
    __tablename__ = "image"
    id = Column(Integer, primary_key=True)
    webpage_id = Column(Integer, ForeignKey("webpage.id"), nullable=False, index=True)
    image_url = Column(Text, nullable=False)
    local_path = Column(Text)
    description = Column(Text)

    # 关联：图片所在的网页
    webpage = relationship("WebPage", back_populates="images")


Base.metadata.create_all(engine)


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
