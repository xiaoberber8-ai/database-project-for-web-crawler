#这是第一版爬虫，有点小问题我尽快修改。
#使用步骤如下：
#1.将数据库配置里数据库地址修改一下，代码里现在是我的本地数据库，如果换成你的本地数据库就只要将Shenle123456换成你的mysql密码。确保mysql里有名为crawler_db的数据库
#2.在440行~最后，这段代码能创建一个策略，你可以在这里修改爬取深度、爬取目标网页等等
#3.运行后程序会自动从目标网页爬数据并自动存进数据库对应表格中
import os
import re
import json
import time
import hashlib
import threading
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship


# 数据库配置

DATABASE_URL = (
    "mysql+pymysql://root:Shenle123456@127.0.0.1:3306/crawler_db?charset=utf8mb4"
)
# 连接数据库，记得修改数据库地址。格式为mysql+pymysql://用户名：用户密码@服务器地址/数据库名称？字符集

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()



# 在数据库中生成表，以便自动填数据

class Website(Base):
    __tablename__ = "website"
    id = Column(Integer, primary_key=True)
    domain = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    company_info = Column(Text)
    contact_info = Column(Text)


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


class DataSource(Base):
    __tablename__ = "datasource"
    id = Column(Integer, primary_key=True)
    publisher_name = Column(String(255))
    origin_url = Column(Text)


class Content(Base):
    __tablename__ = "content"
    id = Column(Integer, primary_key=True)
    webpage_id = Column(Integer, ForeignKey("webpage.id"), nullable=False, index=True)
    datasource_id = Column(Integer, ForeignKey("datasource.id"))
    Title = Column(String(500))
    text_body = Column(Text)
    publish_time = Column(DateTime)
    keywords = Column(Text)


class Image(Base):
    __tablename__ = "image"
    id = Column(Integer, primary_key=True)
    webpage_id = Column(Integer, ForeignKey("webpage.id"), nullable=False, index=True)
    image_url = Column(Text, nullable=False)
    local_path = Column(Text)
    description = Column(Text)


class Admin(Base):
    __tablename__ = "admin"
    id = Column(Integer, primary_key=True)
    Username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)


class CrawlerStrategy(Base):
    __tablename__ = "crawler_strategy"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    target_url = Column(Text, nullable=False)
    rules_json = Column(Text, nullable=False)
    Status = Column(String(50), default="enabled")
    Frequency = Column(String(50), default="manual")
    creator_id = Column(Integer, ForeignKey("admin.id"))


class TaskRecord(Base):
    __tablename__ = "task_record"
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey("crawler_strategy.id"), nullable=False, index=True)
    start_time = Column(DateTime)
    Status = Column(String(50), default="pending")
    end_time = Column(DateTime)
    item_count = Column(Integer, default=0)
    error_message = Column(Text)


Base.metadata.create_all(engine)



# 策略结构

@dataclass
class CrawlRule:
    depth: int = 1
    allowed_domains: list = None
    start_urls: list = None
    title_selector: str = "title"
    body_selector: str = "body"
    image_selector: str = "img"
    link_selector: str = "a[href]"
    download_images: bool = True
    image_dir: str = "./images"
    headers: dict = None
    timeout: int = 15
    rate_limit: float = 1.0  # 每个请求间隔，单位秒



# 工具函数

def normalize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href.strip())

def md5_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def safe_filename(url: str) -> str:
    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}"
    raw = re.sub(r"[^\w\-\.]+", "_", raw)
    return raw[:180] if raw else hashlib.md5(url.encode("utf-8")).hexdigest()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)



# 爬虫执行器

class CrawlerExecutor:
    def __init__(self):
        self.session = requests.Session()
        self.pause_event = threading.Event()   # set = 允许执行，clear = 暂停
        self.stop_event = threading.Event()    # set = 强制终止
        self.pause_event.set()

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.pause_event.set()

    def stop(self):
        self.stop_event.set()
        self.pause_event.set()  # 防止暂停状态下无法退出

    def _wait_if_paused(self):
        while not self.pause_event.is_set():
            if self.stop_event.is_set():
                return False
            time.sleep(0.2)
        return not self.stop_event.is_set()

    def crawl_strategy(self, strategy_id: int):
        db = SessionLocal()
        task = TaskRecord(
            strategy_id=strategy_id,
            start_time=datetime.now(),
            Status="running",
            item_count=0
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        try:
            strategy = db.get(CrawlerStrategy, strategy_id)
            domain = urlparse(strategy.target_url).netloc

            website = db.query(Website).filter_by(domain=domain).first()

            if not website:
                website = Website(
                    domain=domain,
                    name=domain
                )
                db.add(website)
                db.commit()
                db.refresh(website)

            website_id = website.id
            if not strategy:
                raise ValueError(f"strategy_id={strategy_id} 不存在")

            rules = json.loads(strategy.rules_json)
            rule = CrawlRule(
                depth=rules.get("depth", 1),
                allowed_domains=rules.get("allowed_domains", []),
                start_urls=rules.get("start_urls", [strategy.target_url]),
                title_selector=rules.get("text_rules", {}).get("title_selector", "title"),
                body_selector=rules.get("text_rules", {}).get("body_selector", "body"),
                image_selector=rules.get("image_rules", {}).get("image_selector", "img"),
                download_images=rules.get("image_rules", {}).get("download_images", True),
                image_dir=rules.get("image_rules", {}).get("image_dir", "./images"),
                headers=rules.get("headers", {"User-Agent": "Mozilla/5.0"}),
                timeout=rules.get("timeout", 15),
                rate_limit=rules.get("rate_limit", 1.0),
            )

            ensure_dir(rule.image_dir)

            visited = set()
            queue = []
            for u in rule.start_urls:
                queue.append((u, 0))

            while queue and not self.stop_event.is_set():
                if not self._wait_if_paused():
                    break

                url, depth = queue.pop(0)
                url = url.strip()
                url_hash = md5_text(url)

                if url_hash in visited:
                    continue
                visited.add(url_hash)

                if rule.allowed_domains:
                    domain = urlparse(url).netloc
                    if not any(domain.endswith(d) for d in rule.allowed_domains):
                        continue

                page = self._save_webpage_record(db, website_id, task.id, url, url_hash)

                try:
                    resp = self.session.get(url, headers=rule.headers, timeout=rule.timeout)
                    page.fetch_time = datetime.now()
                    page.http_status = resp.status_code

                    content_type = resp.headers.get("Content-Type", "")
                    if "text/html" not in content_type:
                        page.process_status = "skipped_non_html"
                        db.commit()
                        continue

                    resp.encoding = resp.apparent_encoding or resp.encoding
                    html = resp.text
                    soup = BeautifulSoup(html, "lxml")

                    title = self._extract_title(soup, rule)
                    text_body = self._extract_text(soup, rule)
                    keywords = self._extract_keywords(soup)

                    # 数据源
                    datasource = self._get_or_create_datasource(db, url)

                    # 内容入库
                    content = Content(
                        webpage_id=page.id,
                        datasource_id=datasource.id,
                        Title=title,
                        text_body=text_body,
                        publish_time=None,
                        keywords=keywords
                    )
                    db.add(content)

                    # 图片抓取
                    image_count = 0
                    if rule.download_images:
                        image_count = self._extract_and_save_images(
                            db=db,
                            soup=soup,
                            base_url=url,
                            webpage_id=page.id,
                            image_dir=rule.image_dir,
                            headers=rule.headers,
                            timeout=rule.timeout
                        )

                    # 子链接入队
                    if depth < rule.depth:
                        for link in self._extract_links(soup, url):
                            link_hash = md5_text(link)
                            if link_hash not in visited:
                                queue.append((link, depth + 1))

                    page.process_status = "parsed"
                    page.page_type = "mixed" if image_count > 0 else "text"
                    task.item_count = (task.item_count or 0) + 1

                    db.commit()
                    time.sleep(rule.rate_limit)

                except Exception as e:
                    page.process_status = "failed"
                    page.error_message = str(e)
                    db.commit()

            task.Status = "completed" if not self.stop_event.is_set() else "cancelled"
            task.end_time = datetime.now()
            db.commit()

        except Exception as e:
            task.Status = "failed"
            task.end_time = datetime.now()
            task.error_message = str(e)
            db.commit()
            raise
        finally:
            db.close()

    def _save_webpage_record(self, db, website_id, task_id, url, url_hash):
        page = WebPage(
            website_id=website_id,
            task_id=task_id,
            url=url,
            url_hash=url_hash,
            fetch_time=None,
            http_status=None,
            process_status="fetching",
            page_type="unknown"
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        return page

    def _get_or_create_datasource(self, db, origin_url: str):
        parsed = urlparse(origin_url)
        publisher_name = parsed.netloc

        ds = db.query(DataSource).filter(DataSource.origin_url == origin_url).first()
        if ds:
            return ds

        ds = DataSource(
            publisher_name=publisher_name,
            origin_url=origin_url
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
        return ds

    def _extract_title(self, soup: BeautifulSoup, rule: CrawlRule) -> str:
        node = soup.select_one(rule.title_selector)
        return node.get_text(" ", strip=True) if node else ""

    def _extract_text(self, soup: BeautifulSoup, rule: CrawlRule) -> str:
        node = soup.select_one(rule.body_selector)
        if not node:
            node = soup.body
        if not node:
            return ""
        return node.get_text("\n", strip=True)

    def _extract_keywords(self, soup: BeautifulSoup) -> str:
        meta = soup.select_one('meta[name="keywords"]')
        if meta and meta.get("content"):
            return meta["content"]
        return ""

    def _extract_links(self, soup: BeautifulSoup, base_url: str):
        links = set()
        for a in soup.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
            full = normalize_url(base_url, href)
            if full.startswith("http://") or full.startswith("https://"):
                links.add(full)
        return list(links)

    def _extract_and_save_images(self, db, soup, base_url, webpage_id, image_dir, headers, timeout):
        count = 0
        for img in soup.select("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue

            img_url = normalize_url(base_url, src)
            desc = img.get("alt", "")

            local_path = ""
            try:
                r = self.session.get(img_url, headers=headers, timeout=timeout, stream=True)
                if r.status_code == 200:
                    ext = os.path.splitext(urlparse(img_url).path)[1]
                    if not ext or len(ext) > 5:
                        ext = ".jpg"
                    filename = safe_filename(img_url) + ext
                    local_path = os.path.join(image_dir, filename)

                    with open(local_path, "wb") as f:
                        for chunk in r.iter_content(8192):
                            if chunk:
                                f.write(chunk)

            except Exception:
                pass

            image_record = Image(
                webpage_id=webpage_id,
                image_url=img_url,
                local_path=local_path,
                description=desc
            )
            db.add(image_record)
            count += 1

        return count



# 以下是创建策略并执行爬虫的演示

if __name__ == "__main__":
    db = SessionLocal()

    # 先建一个策略
    strategy = db.query(CrawlerStrategy).filter_by(name="example_strategy").first()
    if  strategy:       #原代码是：如果没有策略，用以下默认策略_____IF NOT strategy： //这里改成通过修改以下代码中的域名手动更新策略并存入数据库
        #显然在数据库里没有strategy时会报错，留待以后修改
        rules = {
            "depth": 1,
            "allowed_domains": ["news.sina.com.cn"],    //修改下面3行的网址能爬不同网站
            "start_urls": ["http://news.sina.com.cn"],
            "text_rules": {
                "title_selector": "h1",
                "body_selector": "body"
            },
            "image_rules": {
                "image_selector": "img",
                "download_images": True,
                "image_dir": "./downloaded_images"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0"
            },
            "timeout": 10,
            "rate_limit": 1
        }

        strategy = CrawlerStrategy(
            name="example_strategy",
            target_url="http://news.sina.com.cn",
            rules_json=json.dumps(rules, ensure_ascii=False),
            Status="enabled",
            Frequency="manual",
            creator_id=None
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)

    # 保存ID
    strategy_id = strategy.id

    db.close()

    crawler = CrawlerExecutor()

    # 开始爬取
    crawler.crawl_strategy(strategy_id=strategy_id)