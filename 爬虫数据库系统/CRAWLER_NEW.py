import os
import re
import json
import time
import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
import hmac

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from io import BytesIO
from PIL import Image as PILImage

# =========================
# 日志配置
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
)
logger = logging.getLogger("crawler")

# =========================
# 配置
# =========================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:zhouwanyi1222@172.31.224.1:3306/crawler_db?charset=utf8mb4",
)

ENGINE_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"
engine = create_engine(DATABASE_URL, echo=ENGINE_ECHO, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


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
    text_body = Column(LONGTEXT)
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


class SystemSetting(Base):
    __tablename__ = "system_setting"
    id = Column(Integer, primary_key=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=False)
    description = Column(String(255))

Base.metadata.create_all(engine)


# =========================
# Pydantic 请求/响应模型
# =========================

class TextRules(BaseModel):
    title_selector: str = "title"
    body_selector: str = "body"
    company_selector: Optional[str] = None
    contact_selector: Optional[str] = None
    # 👇 新增：发布者/数据源选择器
    source_selector: Optional[str] = Field(default=None, description="发布者CSS选择器，如 '.author' 或 '#source'")

class ImageRules(BaseModel):     #这是修改部分，有关图片过滤器
    # 图片选择器
    image_selector: str = "img"

    # 是否下载图片
    download_images: bool = True

    # 图片保存目录
    image_dir: str = "./images"

    # 图片容器选择器：为空则回退正文区域
    image_container_selector: Optional[str] = None

    # 最小宽度，小于该宽度的图片忽略
    min_width: int = 150

    # 最小高度，小于该高度的图片忽略
    min_height: int = 150

    # 最小图片面积（可选）
    min_area: int = 30000

    # 最大宽高比，过滤超长广告图
    max_ratio: float = 5.0

    # 过滤广告/图标关键词
    exclude_keywords: list[str] = [
        "ad",
        "ads",
        "advert",
        "banner",
        "logo",
        "icon",
        "sprite",
        "avatar",
        "share",
        "wechat",
        "wx",
        "tracking",
        "pixel",
        "recommend"
    ]

    # 是否只抓正文区域图片
    only_article_images: bool = True


class StrategyRules(BaseModel):
    depth: int = 1
    allowed_domains: List[str] = Field(default_factory=list)
    start_urls: List[str] = Field(default_factory=list)
    text_rules: TextRules = Field(default_factory=TextRules)
    image_rules: ImageRules = Field(default_factory=ImageRules)
    headers: Dict[str, Any] = Field(default_factory=lambda: dict(DEFAULT_HEADERS))
    timeout: int = 15
    rate_limit: float = 1.0
# 新增字段：控制重复数据的处理方式，默认跳过
    duplicate_action: str = Field(default="skip", description="遇到重复数据时: skip(跳过) 或 overwrite(覆盖)")


class StrategyCreate(BaseModel):
    name: str
    target_url: str
    rules: StrategyRules
    Status: str = "enabled"
    Frequency: str = "manual"
    creator_id: Optional[int] = None


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    target_url: Optional[str] = None
    rules: Optional[StrategyRules] = None
    Status: Optional[str] = None
    Frequency: Optional[str] = None
    creator_id: Optional[int] = None


class StrategyOut(BaseModel):
    id: int
    name: str
    target_url: str
    rules: StrategyRules
    Status: str
    Frequency: str
    creator_id: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class CrawlStartRequest(BaseModel):
    strategy_id: int


class TaskOut(BaseModel):
    id: int
    strategy_id: int
    start_time: Optional[datetime]
    Status: str
    end_time: Optional[datetime]
    item_count: Optional[int]
    error_message: Optional[str]

    model_config = ConfigDict(from_attributes=True)


# =========================
# 工具函数
# =========================

def get_db() -> Session:
    return SessionLocal()


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


def strategy_to_out(strategy: CrawlerStrategy) -> StrategyOut:
    return StrategyOut(
        id=strategy.id,
        name=strategy.name,
        target_url=strategy.target_url,
        rules=StrategyRules.model_validate(json.loads(strategy.rules_json)),
        Status=strategy.Status,
        Frequency=strategy.Frequency,
        creator_id=strategy.creator_id,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
    )


def parse_strategy_rules(strategy: CrawlerStrategy) -> StrategyRules:
    return StrategyRules.model_validate(json.loads(strategy.rules_json))



# 实际开发中可将其移至环境变量，这里作为学术项目演示使用静态盐
SECRET_SALT = b"crawler_project_secure_salt_2026"

def hash_password(password: str) -> str:
    """使用 SHA256 对密码进行加盐哈希"""
    return hmac.new(SECRET_SALT, password.encode('utf-8'), hashlib.sha256).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    return hmac.compare_digest(hash_password(plain_password), hashed_password)

# 简易的内存 Token 校验器（用于演示，后续可升级为标准的 JWT 库）
def generate_simple_token(username: str) -> str:
    timestamp = str(int(time.time()))
    payload = f"{username}:{timestamp}"
    signature = hmac.new(SECRET_SALT, payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"
# =========================
# 策略服务
# =========================

class StrategyService:
    @staticmethod
    def create_strategy(db: Session, payload: StrategyCreate) -> CrawlerStrategy:
        strategy = CrawlerStrategy(
            name=payload.name,
            target_url=payload.target_url,
            rules_json=payload.rules.model_dump_json(ensure_ascii=False),
            Status=payload.Status,
            Frequency=payload.Frequency,
            creator_id=payload.creator_id,
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        return strategy

    @staticmethod
    def list_strategies(db: Session) -> List[CrawlerStrategy]:
        return db.query(CrawlerStrategy).order_by(CrawlerStrategy.id.desc()).all()

    @staticmethod
    def get_strategy(db: Session, strategy_id: int) -> CrawlerStrategy:
        strategy = db.get(CrawlerStrategy, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"strategy_id={strategy_id} 不存在")
        return strategy

    @staticmethod
    def update_strategy(db: Session, strategy_id: int, payload: StrategyUpdate) -> CrawlerStrategy:
        strategy = StrategyService.get_strategy(db, strategy_id)
        data = payload.model_dump(exclude_unset=True)

        if "rules" in data and data["rules"] is not None:
            rules_dict = data.pop("rules")
            # model_dump 返回的是 dict，需要用 json.dumps 而非 model_dump_json
            if isinstance(rules_dict, dict):
                data["rules_json"] = json.dumps(rules_dict, ensure_ascii=False)
            else:
                data["rules_json"] = rules_dict.model_dump_json(ensure_ascii=False)

        if "name" in data and data["name"] is not None:
            strategy.name = data["name"]
        if "target_url" in data and data["target_url"] is not None:
            strategy.target_url = data["target_url"]
        if "rules_json" in data:
            strategy.rules_json = data["rules_json"]
        if "Status" in data and data["Status"] is not None:
            strategy.Status = data["Status"]
        if "Frequency" in data and data["Frequency"] is not None:
            strategy.Frequency = data["Frequency"]
        if "creator_id" in data:
            strategy.creator_id = data["creator_id"]

        db.commit()
        db.refresh(strategy)
        return strategy

    @staticmethod
    def delete_strategy(db: Session, strategy_id: int):
        strategy = StrategyService.get_strategy(db, strategy_id)
        db.delete(strategy)
        db.commit()


# =========================
# 爬虫执行器
# =========================

@dataclass
class CrawlRule:
    depth: int

    allowed_domains: List[str]
    start_urls: List[str]

    title_selector: str
    body_selector: str

    company_selector: str
    contact_selector: str
    source_selector: str

    image_selector: str
    download_images: bool
    image_dir: str

    image_container_selector: Optional[str]

    min_width: int
    min_height: int
    min_area: int
    max_ratio: float

    exclude_keywords: List[str]

    headers: Dict[str, Any]

    timeout: int
    rate_limit: float

    duplicate_action: str

    # 链接提取规则
    link_selector: str = "a[href]"


class CrawlerExecutor:
    import json
    import re
    from datetime import datetime
    from typing import Optional
    def _parse_datetime_string(self, text: str) -> Optional[datetime]:
        """
        尽量把各种常见日期字符串转成 datetime。
        支持：
        - 2026-05-25 12:30:00
        - 2026-05-25T12:30:00
        - 2026/05/25 12:30
        - 2026年05月25日 12:30
        """
        if not text:
            return None

        text = text.strip()
        text = text.replace("年", "-").replace("月", "-").replace("日", " ")
        text = text.replace("／", "/")
        text = re.sub(r"\s+", " ", text)

        # 去掉常见时区尾巴，先保证能解析出基础时间
        candidates = [
            text,
            text.replace("Z", ""),
            text.split("+")[0].strip(),
        ]

        fmts = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
            "%Y.%m.%d %H:%M:%S",
            "%Y.%m.%d %H:%M",
            "%Y.%m.%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
        ]

        for cand in candidates:
            # 先试 ISO
            try:
                return datetime.fromisoformat(cand)
            except Exception:
                pass

            # 再试常见格式
            for fmt in fmts:
                try:
                    return datetime.strptime(cand, fmt)
                except Exception:
                    pass

        return None

    def _extract_datetime_from_obj(self, obj) -> Optional[datetime]:
        """
        递归扫描 JSON-LD 结构，寻找 datePublished / dateCreated / dateModified 等字段。
        """
        if isinstance(obj, dict):
            for key in ("datePublished", "dateCreated", "uploadDate", "dateModified", "publishedAt"):
                value = obj.get(key)
                if isinstance(value, str):
                    dt = self._parse_datetime_string(value)
                    if dt:
                        return dt

            for value in obj.values():
                dt = self._extract_datetime_from_obj(value)
                if dt:
                    return dt

        elif isinstance(obj, list):
            for item in obj:
                dt = self._extract_datetime_from_obj(item)
                if dt:
                    return dt

        return None

    def _extract_publish_time(self, soup: BeautifulSoup, html: str) -> Optional[datetime]:
        """
        多策略提取发布时间：
        1. meta 标签
        2. time 标签
        3. JSON-LD
        4. class/id 中含 time/date/publish 的节点
        5. 正则兜底
        """

        # 1) 常见 meta 标签
        meta_keys = [
            ("property", "article:published_time"),
            ("property", "og:release_date"),
            ("property", "article:modified_time"),
            ("name", "publishdate"),
            ("name", "pubdate"),
            ("name", "date"),
            ("name", "dc.date"),
            ("name", "dc.date.issued"),
            ("name", "sailthru.date"),
        ]
        for attr_name, attr_value in meta_keys:
            meta = soup.find("meta", attrs={attr_name: attr_value})
            if meta and meta.get("content"):
                dt = self._parse_datetime_string(meta["content"])
                if dt:
                    return dt

        # 2) time 标签
        time_tag = soup.find("time")
        if time_tag:
            for attr in ("datetime", "content"):
                if time_tag.get(attr):
                    dt = self._parse_datetime_string(time_tag.get(attr))
                    if dt:
                        return dt
            dt = self._parse_datetime_string(time_tag.get_text(" ", strip=True))
            if dt:
                return dt

        # 3) JSON-LD
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text(strip=True)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                dt = self._extract_datetime_from_obj(data)
                if dt:
                    return dt
            except Exception:
                continue

        # 4) class/id 里带时间信息的节点
        selectors = [
            "[class*='time']",
            "[class*='date']",
            "[class*='publish']",
            "[id*='time']",
            "[id*='date']",
            "[id*='publish']",
            ".time",
            ".date",
            ".pub-time",
            ".pubdate",
            ".publish-time",
            ".publish-date",
            ".article-time",
            ".article-date",
        ]
        for sel in selectors:
            for node in soup.select(sel):
                text = node.get_text(" ", strip=True)
                dt = self._parse_datetime_string(text)
                if dt:
                    return dt

        # 5) 正文文本兜底：提取一个像日期的片段
        text = soup.get_text(" ", strip=True)

        patterns = [
            r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T](\d{1,2}:\d{2}(?::\d{2})?))?",
            r"(20\d{2})年(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}:\d{2}(?::\d{2})?))?",
        ]

        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                if "年" in pattern:
                    year, month, day, t = m.group(1), m.group(2), m.group(3), m.group(4)
                    candidate = f"{year}-{month}-{day}"
                    if t:
                        candidate += f" {t}"
                else:
                    year, month, day, t = m.group(1), m.group(2), m.group(3), m.group(4)
                    candidate = f"{year}-{month}-{day}"
                    if t:
                        candidate += f" {t}"

                dt = self._parse_datetime_string(candidate)
                if dt:
                    return dt

        return None

    def __init__(self):
        self.session = requests.Session()
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.pause_event.set()

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.pause_event.set()

    def stop(self):
        self.stop_event.set()
        self.pause_event.set()

    def _wait_if_paused(self) -> bool:
        while not self.pause_event.is_set():
            if self.stop_event.is_set():
                return False
            time.sleep(0.2)
        return not self.stop_event.is_set()

    def crawl_strategy(self, strategy_id: int):
        db = get_db()
        task = TaskRecord(
            strategy_id=strategy_id,
            start_time=datetime.now(),
            Status="running",
            item_count=0,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
        logger.info(f"任务开始: task_id={task_id}, strategy_id={strategy_id}")

        try:
            strategy = db.get(CrawlerStrategy, strategy_id)
            if not strategy:
                raise HTTPException(status_code=404, detail=f"strategy_id={strategy_id} 不存在")

            if strategy.Status != "enabled":
                raise HTTPException(status_code=400, detail="该策略当前不是 enabled 状态")

            rules = parse_strategy_rules(strategy)
            start_urls = rules.start_urls or [strategy.target_url]
            allowed_domains = rules.allowed_domains or []

            domain = urlparse(strategy.target_url).netloc
            website = db.query(Website).filter_by(domain=domain).first()
            if not website:
                website = Website(domain=domain, name=domain)
                db.add(website)
                db.commit()
                db.refresh(website)

            rule = CrawlRule(
                depth=rules.depth,

                allowed_domains=allowed_domains,
                start_urls=start_urls,

                # 文本提取规则
                title_selector=rules.text_rules.title_selector,
                body_selector=rules.text_rules.body_selector,

                # 图片规则
                image_selector=rules.image_rules.image_selector,
                download_images=rules.image_rules.download_images,
                image_dir=rules.image_rules.image_dir,

                # 图片正文区域
                image_container_selector=rules.image_rules.image_container_selector,

                # 图片过滤参数
                min_width=rules.image_rules.min_width,
                min_height=rules.image_rules.min_height,
                min_area=rules.image_rules.min_area,
                max_ratio=rules.image_rules.max_ratio,
                exclude_keywords=rules.image_rules.exclude_keywords,

                # 请求参数
                headers=rules.headers or dict(DEFAULT_HEADERS),
                timeout=rules.timeout,
                rate_limit=rules.rate_limit,

                # 去重策略
                duplicate_action=rules.duplicate_action,

                # 网站信息提取规则
                company_selector=rules.text_rules.company_selector,
                contact_selector=rules.text_rules.contact_selector,
                source_selector=rules.text_rules.source_selector,
            )

            ensure_dir(rule.image_dir)

            visited = set()
            queue = [(u, 0) for u in rule.start_urls]

            while queue and not self.stop_event.is_set():
                if not self._wait_if_paused():
                    break

                url, depth = queue.pop(0)
                url = url.strip()
                if not url:
                    continue

                url_hash = md5_text(url)
                if url_hash in visited:
                    continue
                visited.add(url_hash)

                if rule.allowed_domains:
                    current_domain = urlparse(url).netloc
                    if not any(current_domain.endswith(d) for d in rule.allowed_domains):
                        continue

                page, should_fetch = self._save_webpage_record(db, website.id, task.id, url, url_hash, rule.duplicate_action)
                
                if not should_fetch:
                    # 触发跳过规则：不发请求，直接处理队列里的下一个 URL
                    continue

                # 如果是覆盖模式，为了防止后续插入 Content 时触发 UniqueConstraint 报错，先清空旧关联数据
                if rule.duplicate_action == "overwrite":
                    db.query(Content).filter(Content.webpage_id == page.id).delete()
                    db.query(Image).filter(Image.webpage_id == page.id).delete()
                    db.commit()

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
                    publish_time = self._extract_publish_time(soup, html)
                    # 新增核心：提取公司和联系方式，并动态补全 Website 表中的空白元数据
                    company_info = self._extract_company(soup, rule)
                    contact_info = self._extract_contact(soup, rule)
                    if company_info and not website.company_info:
                        website.company_info = company_info
                    if contact_info and not website.contact_info:
                        website.contact_info = contact_info
                    # 每次抽取到新内容时如果发现网站元数据为空，就会自动帮其在数据库中补全
                    
                    datasource = self._get_or_create_datasource(db, url, soup, rule)

                    content = Content(
                        webpage_id=page.id,
                        datasource_id=datasource.id,
                        Title=title,
                        text_body=text_body,
                        publish_time=publish_time,
                        keywords=keywords
                    )
                    db.add(content)

                    image_count = 0
                    if rule.download_images:
                        image_count = self._extract_and_save_images(
                            db=db,
                            soup=soup,
                            base_url=url,
                            webpage_id=page.id,
                            rule=rule,
                            headers=rule.headers,
                            timeout=rule.timeout,
                        )

                    if depth + 1 < rule.depth:
                        for link in self._extract_links(soup, url, rule.link_selector):
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

            # 循环结束，更新任务状态
            final_status = "completed" if not self.stop_event.is_set() else "cancelled"
            logger.info(
                f"任务循环结束: task_id={task_id}, 即将设置状态={final_status}, "
                f"item_count={task.item_count}, stop_event={self.stop_event.is_set()}"
            )
            task.Status = final_status
            task.end_time = datetime.now()
            try:
                db.commit()
                logger.info(f"任务状态已持久化(成功路径): task_id={task_id}, status={final_status}")
            except Exception as commit_err:
                logger.error(f"成功路径 commit 失败: task_id={task_id}, err={commit_err}")
                try:
                    db.rollback()
                except Exception:
                    pass
                # 用全新会话重试
                self._force_update_task_status(task_id, "failed", f"成功路径commit失败: {commit_err}")
                raise

        except Exception as e:
            logger.error(f"任务异常: task_id={task_id}, err={repr(e)}", exc_info=True)
            try:
                task.Status = "failed"
                task.end_time = datetime.now()
                task.error_message = str(e)
                db.commit()
                logger.info(f"任务状态已持久化(异常路径): task_id={task_id}, status=failed")
            except Exception as commit_err:
                logger.error(f"异常路径 commit 也失败: task_id={task_id}, err={commit_err}")
                try:
                    db.rollback()
                except Exception:
                    pass
                # 用全新会话强制更新
                self._force_update_task_status(task_id, "failed", f"异常路径commit失败: {repr(e)}")
            raise
        finally:
            # 安全网：如果任务仍是 running，用全新会话强制标记为 failed
            # 这覆盖了所有未捕获的退出路径（如线程被杀、commit 双重失败等）
            try:
                db.close()
            except Exception:
                pass
            self._ensure_task_finalized(task_id)

    def _force_update_task_status(self, task_id: int, status: str, error_msg: str = ""):
        """用全新会话强制更新任务状态（用于主会话损坏时的兜底）"""
        fresh_db = get_db()
        try:
            t = fresh_db.get(TaskRecord, task_id)
            if t:
                t.Status = status
                t.end_time = datetime.now()
                if error_msg:
                    t.error_message = error_msg
                fresh_db.commit()
                logger.info(f"强制更新任务状态: task_id={task_id}, status={status}")
        except Exception as e:
            logger.error(f"强制更新任务状态失败: task_id={task_id}, err={repr(e)}", exc_info=True)
        finally:
            try:
                fresh_db.close()
            except Exception:
                pass

    def _ensure_task_finalized(self, task_id: int):
        """安全网：确保任务不再是 running 状态"""
        fresh_db = get_db()
        try:
            t = fresh_db.get(TaskRecord, task_id)
            if t and t.Status == "running":
                t.Status = "failed"
                t.end_time = datetime.now()
                if not t.error_message:
                    t.error_message = "任务异常终止（线程退出但状态未更新）"
                fresh_db.commit()
                logger.warning(
                    f"安全网触发: task_id={task_id} 仍为 running，已强制标记为 failed"
                )
        except Exception as e:
            logger.error(f"安全网更新失败: task_id={task_id}, err={repr(e)}", exc_info=True)
        finally:
            try:
                fresh_db.close()
            except Exception:
                pass

    def _save_webpage_record(self, db: Session, website_id: int, task_id: int, url: str, url_hash: str, duplicate_action: str) -> tuple[WebPage, bool]:
            # 1. 先查询数据库中是否已有该网页
            existing_page = db.query(WebPage).filter(
                WebPage.website_id == website_id,
                WebPage.url_hash == url_hash
            ).first()

            if existing_page:
                if duplicate_action == "skip":
                    # 策略为跳过：直接返回已存在的页面对象，并告诉外层不需要再次抓取 (False)
                    return existing_page, False
                
                # 策略为覆盖 (overwrite)：更新所属任务并重置状态，告诉外层需要抓取 (True)
                existing_page.task_id = task_id
                existing_page.process_status = "fetching"
                db.commit()
                db.refresh(existing_page)
                return existing_page, True

            # 2. 如果不存在，正常创建新记录并告诉外层需要抓取 (True)
            page = WebPage(
                website_id=website_id,
                task_id=task_id,
                url=url,
                url_hash=url_hash,
                fetch_time=None,
                http_status=None,
                process_status="fetching",
                page_type="unknown",
            )
            db.add(page)
            db.commit()
            db.refresh(page)
            return page, True

    def _get_or_create_datasource(self, db: Session, origin_url: str, soup: BeautifulSoup, rule: CrawlRule) -> DataSource:
            publisher_name = None
            
            # 1. 优先尝试通过 CSS 选择器精准提取真实发布来源
            if rule.source_selector:
                node = soup.select_one(rule.source_selector)
                if node:
                    # 清洗掉常见的“来源：”等前缀字样
                    raw_text = node.get_text(" ", strip=True)
                    publisher_name = re.sub(r"^(来源|作者|发布者)[:：\s]*", "", raw_text).strip()
            
            # 2. 如果没提取到，使用域名作为兜底
            if not publisher_name:
                parsed = urlparse(origin_url)
                publisher_name = parsed.netloc

            # 3. 查库或新建
            ds = db.query(DataSource).filter(DataSource.publisher_name == publisher_name).first()
            if ds:
                # 如果原始链接为空，可以顺便补充一下
                if not ds.origin_url:
                    ds.origin_url = origin_url
                    db.commit()
                return ds

            ds = DataSource(publisher_name=publisher_name, origin_url=origin_url)
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

    def _extract_company(self, soup: BeautifulSoup, rule: CrawlRule) -> Optional[str]:
        if not rule.company_selector:
            return None
        node = soup.select_one(rule.company_selector)
        return node.get_text(" ", strip=True) if node else None

    def _extract_contact(self, soup: BeautifulSoup, rule: CrawlRule) -> Optional[str]:
        if not rule.contact_selector:
            return None
        node = soup.select_one(rule.contact_selector)
        return node.get_text(" ", strip=True) if node else None

    def _extract_links(self, soup: BeautifulSoup, base_url: str, selector: str):
        links = set()
        for a in soup.select(selector):
            href = a.get("href")
            if not href:
                continue
            full = normalize_url(base_url, href)
            if full.startswith("http://") or full.startswith("https://"):
                links.add(full)
        return list(links)

    def _extract_and_save_images(
            self,
            db: Session,
            soup: BeautifulSoup,
            base_url: str,
            webpage_id: int,
            rule: CrawlRule,
            headers: Dict[str, Any],
            timeout: int,
    ) -> int:
        """
        只抓正文区域中更像“内容配图”的图片：
        1. 优先限制在正文/图片容器内
        2. 过滤广告、logo、icon、小图标、分享图等噪声图片
        3. 支持 src / data-src / data-original / srcset
        4. 按最小宽高、最小面积、最大宽高比过滤
        5. 优先解析页面 script 中的 imgsList（搜狐等懒加载加密站点）
        """
        count = 0

        min_width = getattr(rule, "min_width", 150)
        min_height = getattr(rule, "min_height", 150)
        min_area = getattr(rule, "min_area", 30000)
        max_ratio = getattr(rule, "max_ratio", 5.0)

        def _save_one(img_url: str, desc: str, known_w: int = 0, known_h: int = 0) -> bool:
            """下载并保存单张图片，返回是否成功。"""
            try:
                r = self.session.get(img_url, headers=headers, timeout=timeout, stream=True)
                if r.status_code != 200:
                    return False

                content_type = r.headers.get("Content-Type", "").lower()
                if not any(x in content_type for x in ("image/", "application/octet-stream")):
                    return False

                # 若已知宽高（来自 imgsList），直接用；否则用 PIL 识别
                width, height = known_w, known_h
                if not width or not height:
                    try:
                        pil_img = PILImage.open(BytesIO(r.content))
                        width, height = pil_img.size
                    except Exception:
                        return False

                if width < min_width or height < min_height:
                    return False
                if width * height < min_area:
                    return False
                ratio = max(width / max(height, 1), height / max(width, 1))
                if ratio > max_ratio:
                    return False

                ext = os.path.splitext(urlparse(img_url).path)[1]
                if not ext or len(ext) > 5:
                    ext = ".jpg"

                filename = safe_filename(img_url) + ext
                local_path = os.path.join(rule.image_dir, filename)

                with open(local_path, "wb") as f:
                    f.write(r.content)

                db.add(Image(
                    webpage_id=webpage_id,
                    image_url=img_url,
                    local_path=local_path,
                    description=desc,
                ))
                return True
            except Exception:
                return False

        # ===== 优先路径：从 script 中提取 imgsList（搜狐等懒加载加密页面）=====
        imgslist_items = self._extract_imgslist_from_scripts(soup, base_url)
        for it in imgslist_items:
            img_url = it.get("url", "")
            if not img_url:
                continue
            # imgsList 中的URL已是真实地址，无需走 _is_noise_image（避免误杀）
            # 但仍需通过尺寸过滤（_save_one 内部处理）
            if _save_one(img_url, it.get("description", ""), it.get("width", 0), it.get("height", 0)):
                count += 1

        # ===== 兜底路径：解析 <img> 标签（适用于常规站点）=====
        # 如果 imgsList 已经抓到图片，可跳过 <img> 解析避免重复；
        # 但为兼容混合场景，这里仅在 imgsList 为空时走兜底
        if count == 0:
            container = None
            if getattr(rule, "image_container_selector", None):
                container = soup.select_one(rule.image_container_selector)
            if not container:
                container = soup.select_one(rule.body_selector) if rule.body_selector else None
            if not container:
                container = soup.body or soup

            image_candidates = container.select(rule.image_selector or "img")
            for img in image_candidates:
                img_url = self._get_best_image_url(img, base_url)
                if not img_url:
                    continue
                # 跳过搜狐加密的 data-src（非URL形态）
                if not re.match(r"^https?://|^//", img_url):
                    continue
                if self._is_noise_image(img, img_url, rule):
                    continue
                desc = img.get("alt", "") or ""
                if _save_one(img_url, desc):
                    count += 1

        return count

    def _extract_imgslist_from_scripts(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """
        从页面 <script> 中提取 imgsList 数据（搜狐等站点使用）。
        搜狐文章页 <img> 的 data-src 是加密字符串，真实图片URL藏在
        JavaScript 变量 imgsList 中，格式如：
            imgsList: [
                {"url": "//q7.itc.cn/q_70/.../xxx.jpeg", "width": "2656", "height": "580"},
                ...
            ]
        返回标准化后的图片信息列表，每项包含 url/description/width/height。
        """
        results: List[Dict[str, Any]] = []
        pattern = re.compile(r"imgsList\s*:\s*(\[.*?\])\s*,", re.DOTALL)

        for script in soup.find_all("script"):
            text = script.string or script.get_text() or ""
            if "imgsList" not in text:
                continue
            match = pattern.search(text)
            if not match:
                continue
            raw = match.group(1)
            # 搜狐的 JSON 末尾常有尾随逗号，标准 json 解析会失败，需清理
            cleaned = re.sub(r",\s*([\]}])", r"\1", raw)
            try:
                items = json.loads(cleaned)
            except Exception:
                continue
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                url = it.get("url") or it.get("src") or ""
                if not url:
                    continue
                # 协议相对URL（//xxx）补全为 https:
                if url.startswith("//"):
                    url = "https:" + url
                else:
                    url = urljoin(base_url, url.strip())
                try:
                    width = int(it.get("width", 0) or 0)
                except Exception:
                    width = 0
                try:
                    height = int(it.get("height", 0) or 0)
                except Exception:
                    height = 0
                results.append({
                    "url": url,
                    "description": it.get("alt") or it.get("description") or "",
                    "width": width,
                    "height": height,
                })
            # 找到第一个有效 imgsList 即可
            if results:
                break
        return results

    def _get_best_image_url(self, img, base_url: str) -> str:
        """
        从 img 标签中优先提取更像原图的地址：
        data-original > data-src > src > srcset
        """
        for attr in ("data-original", "data-src", "src"):
            src = img.get(attr)
            if src:
                return normalize_url(base_url, src)

        srcset = img.get("srcset")
        if srcset:
            parts = [p.strip() for p in srcset.split(",") if p.strip()]
            if parts:
                last = parts[-1].split()[0]
                return normalize_url(base_url, last)

        return ""

    def _is_noise_image(self, img, img_url: str, rule: CrawlRule) -> bool:
        """
        过滤广告图、logo、icon、小图标、分享图等与正文关系较小的内容。
        """
        default_keywords = [
            "ad", "ads", "advert", "advertisement",
            "logo", "icon", "sprite", "banner",
            "avatar", "share", "wechat", "wx",
            "tracking", "pixel", "related", "recommend",
            "sponsor", "promo", "button", "footer", "header"
        ]

        exclude_keywords = getattr(rule, "exclude_keywords", None) or default_keywords

        fields = [
            str(img.get("alt", "")),
            " ".join(img.get("class", [])) if img.get("class") else "",
            str(img.get("id", "")),
            str(img.get("title", "")),
            img_url or ""
        ]
        text = " ".join(fields).lower()

        if any(k.lower() in text for k in exclude_keywords):
            return True

        if any(x in img_url.lower() for x in ("pixel", "track", "counter")):
            return True

        return False

# =========================
# FastAPI
# =========================

app = FastAPI(title="Crawler DB System", version="1.0.0")
crawler = CrawlerExecutor()
crawl_thread: Optional[threading.Thread] = None


@app.on_event("startup")
def cleanup_orphaned_tasks():
    """启动时清理上次未正常结束的任务（进程被杀导致状态残留为 running）"""
    db = get_db()
    try:
        orphaned = db.query(TaskRecord).filter(TaskRecord.Status == "running").all()
        for task in orphaned:
            task.Status = "interrupted"
            task.end_time = datetime.now()
            if not task.error_message:
                task.error_message = "服务重启，任务被中断"
        db.commit()
        if orphaned:
            print(f"[startup] 清理了 {len(orphaned)} 个孤儿任务")
    finally:
        db.close()


@app.get("/")
def root():
    return {"msg": "Crawler DB API is running"}


# -------- 策略管理 API --------

@app.post("/strategies", response_model=StrategyOut)
def create_strategy(payload: StrategyCreate):
    db = get_db()
    try:
        strategy = StrategyService.create_strategy(db, payload)
        return strategy_to_out(strategy)
    finally:
        db.close()


@app.get("/strategies", response_model=List[StrategyOut])
def list_strategies():
    db = get_db()
    try:
        strategies = StrategyService.list_strategies(db)
        return [strategy_to_out(s) for s in strategies]
    finally:
        db.close()


@app.get("/strategies/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int):
    db = get_db()
    try:
        strategy = StrategyService.get_strategy(db, strategy_id)
        return strategy_to_out(strategy)
    finally:
        db.close()


@app.put("/strategies/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, payload: StrategyUpdate):
    db = get_db()
    try:
        strategy = StrategyService.update_strategy(db, strategy_id, payload)
        return strategy_to_out(strategy)
    finally:
        db.close()


@app.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: int):
    db = get_db()
    try:
        StrategyService.delete_strategy(db, strategy_id)
        return {"msg": "strategy deleted", "strategy_id": strategy_id}
    finally:
        db.close()


# -------- 爬虫控制 API --------

@app.post("/crawl/start")
def start_crawl(payload: CrawlStartRequest):
    global crawl_thread

    if crawl_thread and crawl_thread.is_alive():
        raise HTTPException(status_code=400, detail="爬虫线程仍在运行，请先停止或等待当前任务完成")

    crawler.stop_event.clear()
    crawler.resume()

    def _thread_excepthook(args):
        logger.error(
            f"爬虫线程未捕获异常: thread={args.thread.name}, exc={repr(args.exc_value)}",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    crawl_thread = threading.Thread(
        target=crawler.crawl_strategy,
        kwargs={"strategy_id": payload.strategy_id},
        daemon=True,
        name=f"crawl-strategy-{payload.strategy_id}",
    )
    crawl_thread.excepthook = _thread_excepthook
    crawl_thread.start()
    logger.info(f"已启动爬虫线程: strategy_id={payload.strategy_id}, thread={crawl_thread.name}")

    return {"msg": "crawler started", "strategy_id": payload.strategy_id}


@app.post("/crawl/pause")
def pause_crawl():
    crawler.pause()
    return {"msg": "paused"}


@app.post("/crawl/resume")
def resume_crawl():
    crawler.resume()
    return {"msg": "resumed"}


@app.post("/crawl/stop")
def stop_crawl():
    crawler.stop()
    return {"msg": "stopped"}


@app.get("/crawl/status")
def crawl_status():
    alive = bool(crawl_thread and crawl_thread.is_alive())
    return {
        "thread_alive": alive,
        "paused": not crawler.pause_event.is_set(),
        "stopped": crawler.stop_event.is_set(),
    }


# -------- 任务查询 API --------

@app.get("/tasks", response_model=List[TaskOut])
def list_tasks(strategy_id: Optional[int] = Query(default=None)):
    db = get_db()
    try:
        q = db.query(TaskRecord).order_by(TaskRecord.id.desc())
        if strategy_id is not None:
            q = q.filter(TaskRecord.strategy_id == strategy_id)
        return q.all()
    finally:
        db.close()


@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int):
    db = get_db()
    try:
        task = db.get(TaskRecord, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"task_id={task_id} 不存在")
        return task
    finally:
        db.close()


# =========================
# 演示入口：可选
# =========================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "CRAWLER_NEW:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
