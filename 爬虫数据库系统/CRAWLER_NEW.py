import os
import re
import json
import time
import socket
import base64
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

# 搜狐图片 AES 解密（data-src 加密场景）
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    _SOHU_AES_KEY = b"www.sohu.com6666"
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

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
    strategy_type: str = Field(default="professional", description="策略类型: baby(宝宝策略) / professional(专业模式)")
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

        # 6) 原始 HTML 兜底：某些网站（如百度百家号）将发布时间嵌在 JS 变量中，
        #    soup.get_text() 不包含 script 内容，需搜索原始 HTML
        if html:
            # 限定搜索带时间的完整日期格式，避免误匹配纯日期
            full_datetime_patterns = [
                r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})[ T](\d{1,2}:\d{2}:\d{2})",
                r"(20\d{2})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2}:\d{2})",
            ]
            for pattern in full_datetime_patterns:
                m = re.search(pattern, html)
                if m:
                    year, month, day, t = m.group(1), m.group(2), m.group(3), m.group(4)
                    candidate = f"{year}-{month.zfill(2)}-{day.zfill(2)} {t}"
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

            # ===== 爬取前 DNS 连通性预检查 =====
            # 提前发现 DNS 故障，避免任务"成功完成"但 0 条数据的误导
            check_url = (rule.start_urls[0] if rule.start_urls else strategy.target_url).strip()
            check_domain = urlparse(check_url).netloc
            if check_domain:
                try:
                    socket.gethostbyname(check_domain)
                except Exception as dns_err:
                    dns_msg = (
                        f"DNS解析失败，无法解析域名 '{check_domain}': {dns_err}。"
                        f"请检查系统DNS配置（/etc/resolv.conf）是否指向可用的DNS服务器。"
                    )
                    task.error_message = dns_msg
                    task.Status = "failed"
                    task.end_time = datetime.now()
                    db.commit()
                    logger.error(f"任务因DNS预检查失败: task_id={task_id}, domain={check_domain}, err={dns_err}")
                    return

            visited = set()
            queue = [(u, 0) for u in rule.start_urls]
            failed_count = 0
            last_error_msg = None

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
                    text_body = self._extract_text(soup, rule, html)
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
                    # 先提交 Content，确保即使后续图片提取失败，文本数据也不会丢失
                    db.commit()

                    # 图片提取单独 try-except，避免图片处理失败导致 Content 丢失
                    image_count = 0
                    if rule.download_images:
                        try:
                            image_count = self._extract_and_save_images(
                                db=db,
                                soup=soup,
                                base_url=url,
                                webpage_id=page.id,
                                rule=rule,
                                headers=rule.headers,
                                timeout=rule.timeout,
                                html=html,
                            )
                        except Exception as img_err:
                            logger.warning(f"图片提取失败（不影响文本）: task_id={task_id}, url={url}, err={img_err}")

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
                    failed_count += 1
                    last_error_msg = str(e)
                    logger.warning(f"页面抓取失败: task_id={task_id}, url={url}, err={e}")
                    db.commit()

            # 循环结束，更新任务状态
            # 如果所有页面都失败了，标记任务为 failed 并记录错误摘要
            if (task.item_count or 0) == 0 and failed_count > 0:
                task.error_message = (
                    f"全部 {failed_count} 个页面抓取失败。最后错误: {last_error_msg}"
                )
                final_status = "failed"
                logger.warning(f"任务所有页面失败: task_id={task_id}, failed_count={failed_count}")
            else:
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
        """
        多级回退提取标题：
        1. 优先使用策略配置的 title_selector
        2. 回退到 h1 标签
        3. 回退到 meta[property=og:title]
        4. 回退到 <title> 标签
        """
        # 1. 优先使用策略配置的选择器
        node = soup.select_one(rule.title_selector)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text

        # 2. 回退到 h1 标签
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(" ", strip=True)
            if text:
                return text

        # 3. 回退到 og:title meta 标签
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # 4. 回退到 <title> 标签
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            # 清理常见的站点后缀，如 "xxx_新浪新闻"、"xxx-百度百家号"
            for sep in ["_", "-", "|"]:
                if sep in text:
                    parts = text.split(sep)
                    # 取最长的部分作为标题（通常是正文标题，不是站点名）
                    text = max(parts, key=len).strip()
            if text:
                return text

        return ""

    def _extract_text(self, soup: BeautifulSoup, rule: CrawlRule, html: str = "") -> str:
        # 1. 优先尝试从 <script> 中的 JS 变量提取真实正文（央视等 JS 渲染页面）
        #    当页面用 JS 动态填充正文时，body_selector 抓到的常是空 div 或 "正在加载" 占位符
        if html:
            js_html = self._extract_js_rendered_html(html)
            if js_html:
                try:
                    sub_soup = BeautifulSoup(js_html, "lxml")
                    self._clean_boilerplate(sub_soup)
                    js_text = self._filter_nav_lines(sub_soup.get_text("\n", strip=True))
                    if js_text and len(js_text) >= 20:
                        return js_text
                except Exception:
                    pass

        # 2. 回退到 CSS 选择器
        node = soup.select_one(rule.body_selector)
        if not node:
            node = soup.body
        if not node:
            return ""
        # 清除导航栏、页眉页脚、脚本样式等无关元素后再提取文本
        self._clean_boilerplate(node)
        raw_text = node.get_text("\n", strip=True)
        return self._filter_nav_lines(raw_text)

    def _clean_boilerplate(self, node) -> None:
        """
        就地清除节点中的导航、页眉页脚、脚本样式等与正文无关的元素。
        在 get_text 前调用，避免抓到大量菜单/导航文本（如新浪新闻的频道列表）。
        """
        if node is None:
            return
        # 1. 删除标签级别明确的非正文元素
        for tag_name in ('script', 'style', 'noscript', 'nav', 'header', 'footer',
                         'aside', 'form', 'iframe', 'svg', 'button'):
            for t in node.find_all(tag_name):
                t.decompose()

        # 2. 删除 class/id 命中导航/菜单/页眉页脚等模式的元素
        #    使用正则匹配常见命名，覆盖 nav/menu/header/footer/sidebar/breadcrumb/share/comment 等
        pattern = re.compile(
            r'nav|menu|header|footer|sidebar|breadcrumb|topbar|top-bar|bottombar|bottom-bar|'
            r'share|comment|recommend|related|toolbar|banner|advert|promo|popup|modal|'
            r'login|register|copyright|backtotop|site-link|channel',
            re.IGNORECASE
        )
        # 关键修复：遍历时需检查元素是否已被分解（父元素被删除后子元素会失效）
        # 否则 elem.get('class') 会抛出 AttributeError: 'NoneType' object has no attribute 'get'
        for elem in list(node.find_all(True)):
            # 已被 decompose 的元素 parent 为 None，跳过
            if elem.parent is None:
                continue
            try:
                cls = elem.get('class') or []
                cls_str = ' '.join(cls) if isinstance(cls, list) else str(cls)
                elem_id = elem.get('id') or ''
                if pattern.search(cls_str) or pattern.search(elem_id):
                    elem.decompose()
            except Exception:
                continue

    def _filter_nav_lines(self, text: str) -> str:
        """
        过滤文本中的导航菜单行和无关短文本。
        依据：正文段落通常较长且以句末标点结尾；导航项通常是 2-4 字的短词（如"新闻""体育"）。
        """
        if not text:
            return text
        # 句末标点（中英文），有这些标点的行即使是短句也保留（如"好。""来源：新华社。"）
        sentence_end = re.compile(r'[。！？!?.…]$')
        # 纯符号行（如 ">" "×" "·" "|" "-"）
        symbol_only = re.compile(r'^[\s\-\—\|\>\×\·\+\*\#\·\·]+$')
        # 常见品牌/导航前缀（如"新浪新闻""新浪体育"等纯导航文本）
        nav_prefixes = ('新浪首页', '新浪新闻', '新浪体育', '新浪财经', '新浪娱乐', '新浪科技',
                        '新浪博客', '新浪图片', '新浪视频', '新浪游戏', '新浪邮箱', '新浪微博',
                        '移动客户端', '注册', '登录', '热搜')

        kept = []
        for raw_line in text.split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            # 保留以句末标点结尾的行（正文特征）
            if sentence_end.search(line):
                kept.append(line)
                continue
            # 过滤纯符号行
            if symbol_only.match(line):
                continue
            # 过滤常见导航前缀行
            if any(line.startswith(p) for p in nav_prefixes) and len(line) <= 12:
                continue
            # 过滤超短行（<=4 字符，且非句末），如"新闻""体育""财经"等导航菜单项
            if len(line) <= 4:
                continue
            kept.append(line)
        return '\n'.join(kept)

    def _extract_js_rendered_html(self, html: str) -> Optional[str]:
        """
        检测 JavaScript 渲染型页面（如央视新闻），从 <script> 标签中
        形如 `var contentdate = '<p>...</p>'` 的变量里提取真正的正文 HTML 字符串。
        返回 HTML 字符串，如未找到返回 None。

        央视新闻页的 #text_area 在初始 HTML 中是空的，正文 HTML 实际
        藏在 script 变量 contentdate 中，由 JS 在前端运行时填充。
        """
        if not html:
            return None

        # 常见的 JS 变量名（央视新闻使用 contentdate）
        var_names = [
            "contentdate",
            "content_data",
            "article_content",
            "article_data",
            "contentHtml",
            "articleHtml",
            "pageContent",
            "contenttext",
            "detail_content",
            "htmlContent",
            "body_content",
        ]

        for name in var_names:
            # 匹配 var name = '...' 或 var name = "..."
            # 用 [\s\S] 允许跨行匹配；非贪婪避免吃掉过多内容
            pattern = re.compile(
                r"var\s+" + re.escape(name) + r"\s*=\s*(['\"])([\s\S]*?)\1\s*[;<\n]",
                re.MULTILINE,
            )
            m = pattern.search(html)
            if not m:
                continue
            raw = m.group(2)
            # 必须像 HTML 内容（含 p/img/br/div 等标签）
            if "<p" not in raw and "<img" not in raw and "<br" not in raw and "<div" not in raw:
                continue
            try:
                sub_soup = BeautifulSoup(raw, "lxml")
                text = sub_soup.get_text(" ", strip=True)
                if not text or len(text) < 20:
                    continue
                return raw
            except Exception:
                continue

        return None

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
            html: str = "",
    ) -> int:
        """
        只抓正文区域中更像“内容配图”的图片：
        1. 优先限制在正文/图片容器内
        2. 过滤广告、logo、icon、小图标、分享图等噪声图片
        3. 支持 src / data-src / data-original / srcset
        4. 按最小宽高、最小面积、最大宽高比过滤
        5. 优先解析页面 script 中的 imgsList（搜狐等懒加载加密站点）
        6. JS 渲染型页面（如央视）：从 script 变量 contentdate 中提取 <img>
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
                # 搜狐加密 data-src：非 URL 形态，尝试 AES 解密还原真实图片地址
                if not re.match(r"^https?://|^//", img_url):
                    decrypted = self._decrypt_sohu_image_url(img_url)
                    if decrypted:
                        img_url = decrypted
                    else:
                        continue
                if self._is_noise_image(img, img_url, rule):
                    continue
                desc = img.get("alt", "") or ""
                if _save_one(img_url, desc):
                    count += 1

        # ===== 兜底路径 2：JS 渲染型页面（央视新闻等）=====
        # 当 <img> 解析没抓到图片时，尝试从 script 变量 contentdate 中提取 <img>
        # 这种页面正文 HTML 藏在 JS 变量里，soup.select("img") 拿不到
        if count == 0 and html:
            js_html = self._extract_js_rendered_html(html)
            if js_html:
                try:
                    js_soup = BeautifulSoup(js_html, "lxml")
                    for img in js_soup.select("img"):
                        img_url = self._get_best_image_url(img, base_url)
                        if not img_url:
                            continue
                        if not re.match(r"^https?://|^//", img_url):
                            continue
                        if self._is_noise_image(img, img_url, rule):
                            continue
                        desc = img.get("alt", "") or ""
                        if _save_one(img_url, desc):
                            count += 1
                except Exception:
                    pass

        return count

    def _decrypt_sohu_image_url(self, raw: str) -> str:
        """
        解密搜狐文章 <img data-src> 中的加密字符串。
        搜狐使用 AES-128-ECB（PKCS7 填充）加密图片 URL，密钥为 'www.sohu.com6666'。
        解密后得到真实图片地址（如 http://img.mp.sohu.com/.../*.jpg）。
        """
        if not _HAS_CRYPTO or not raw:
            return ""
        raw = raw.strip()
        # 加密串特征：Base64 字符集，长度>=32，不以 http 开头
        if len(raw) < 32 or raw.startswith(("http://", "https://", "//", "data:")):
            return ""
        try:
            cipher = AES.new(_SOHU_AES_KEY, AES.MODE_ECB)
            decrypted = unpad(cipher.decrypt(base64.b64decode(raw)), AES.block_size)
            url = decrypted.decode("utf-8")
            # 校验解密结果是否为合法 URL
            if url.startswith(("http://", "https://", "//")):
                if url.startswith("//"):
                    url = "https:" + url
                return url
            return ""
        except Exception:
            return ""

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

# 挂载静态文件服务，让前端可以通过 HTTP 访问本地下载的图片
from fastapi.staticfiles import StaticFiles
_IMAGES_DIR = os.path.abspath("./images")
if os.path.isdir(_IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=_IMAGES_DIR), name="images")

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
