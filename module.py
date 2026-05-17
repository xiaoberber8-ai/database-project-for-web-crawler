# 在你的 Ubuntu/WSL 终端中安装 FastAPI 和本地运行服务器 uvicorn：
pip install fastapi uvicorn

# 新建main.py，假设爬虫文件是crawler.py
# 内容如下

from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

# 假设你上面的爬虫代码保存在了 crawler_models.py 中
# 我们直接引入配置好的 SessionLocal 和 数据库表模型
from crawler import SessionLocal, Content, WebPage, TaskRecord, CrawlerStrategy

app = FastAPI(title="网络数据爬取管理系统 API")

# 依赖项：每次请求获取一个数据库会话，用完自动关闭
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 一、 工作台 (Dashboard) 模块接口
# ==========================================
@app.get("/api/dashboard/stats", summary="获取大屏概览统计")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # 1. 总抓取文章量
    total_content = db.query(Content).count()
    
    # 2. 今日新增网页数 (注意大小写，匹配你的 ORM 定义)
    today = date.today()
    today_new = db.query(WebPage).filter(
        func.date(WebPage.fetch_time) == today
    ).count()
    
    # 3. 活跃任务数 (匹配你设定的 Status 字段)
    active_tasks = db.query(TaskRecord).filter(
        TaskRecord.Status == "running"
    ).count()
    
    return {
        "total_content": total_content,
        "today_new": today_new,
        "active_tasks": active_tasks
    }

# ==========================================
# 二、 数据中心模块接口
# ==========================================
@app.get("/api/content/list", summary="获取清洗后的文章列表")
def get_content_list(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    # 多表联查：查询 Content 并带出关联的 WebPage 的 url
    results = db.query(Content, WebPage.url, WebPage.fetch_time)\
        .join(WebPage, Content.webpage_id == WebPage.id)\
        .order_by(WebPage.fetch_time.desc())\
        .offset(skip).limit(limit).all()
    
    # 将结果格式化为前端好用的 JSON
    data = []
    for content, url, fetch_time in results:
        data.append({
            "id": content.id,
            "title": content.Title,  # 你的模型里是 Title 大写
            "text_preview": content.text_body[:100] + "..." if content.text_body else "",
            "source_url": url,
            "fetch_time": fetch_time
        })
    return {"total": len(data), "data": data}

# ==========================================
# 三、 高级检索模块接口
# ==========================================
@app.get("/api/search", summary="综合搜索引擎")
def search_content(keyword: str = Query(..., description="搜索关键字"), db: Session = Depends(get_db)):
    # 在标题或正文中模糊查找
    search_rule = f"%{keyword}%"
    results = db.query(Content, WebPage.url)\
        .join(WebPage, Content.webpage_id == WebPage.id)\
        .filter(
            (Content.Title.ilike(search_rule)) | (Content.text_body.ilike(search_rule))
        )\
        .limit(100).all()
        
    data = [{"title": c.Title, "url": u} for c, u in results]
    return {"keyword": keyword, "matches": len(data), "results": data}

# ==========================================
# 四、 爬虫任务管理接口
# ==========================================
@app.post("/api/strategy/{strategy_id}/run", summary="手动触发一个爬虫策略")
def run_strategy(strategy_id: int):
    # 这里可以调用你爬虫代码里的 CrawlerExecutor().crawl_strategy(strategy_id)
    # 实际开发中，建议用 Celery 或后台任务来跑，防止阻塞接口
    return {"message": f"策略 {strategy_id} 已下发执行队列"}




# 编好后，在终端运行
uvicorn main:app --reload
# 启动成功后，打开浏览器，访问 http://127.0.0.1:8000/docs
# 前端根据此来编写代码，对接数据
