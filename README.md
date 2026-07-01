# SpideX 爬虫数据库管理系统

> 复旦大学 数据库及其实现课程 小组项目

基于 **Vue 3 + FastAPI + MySQL** 的网络爬虫与数据管理平台，支持策略化爬取、文本/图片数据管理、内容检索与可视化仪表盘。

---

## 目录

- [系统架构](#系统架构)
- [环境要求](#环境要求)
- [安装部署](#安装部署)
  - [1. 克隆项目](#1-克隆项目)
  - [2. 安装 MySQL 并创建数据库](#2-安装-mysql-并创建数据库)
  - [3. 安装 Python 依赖](#3-安装-python-依赖)
  - [4. 安装前端依赖](#4-安装前端依赖)
- [配置说明](#配置说明)
- [启动服务](#启动服务)
- [使用说明](#使用说明)
  - [登录系统](#登录系统)
  - [创建爬虫策略](#创建爬虫策略)
  - [启动与控制爬虫](#启动与控制爬虫)
  - [数据管理](#数据管理)
  - [内容检索](#内容检索)
- [功能验证与测试](#功能验证与测试)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   浏览器 (Vue 3 SPA)                │
│              localhost:3002 (Vite Dev Server)        │
└──────────────┬──────────────────┬───────────────────┘
               │ /api/*           │ /data-api/*
               ▼                  ▼
┌──────────────────────┐  ┌───────────────────────────┐
│  爬虫后端服务        │  │  数据查询代理服务          │
│  CRAWLER_NEW.py      │  │  data_proxy.py            │
│  localhost:8000      │  │  localhost:8004            │
│  策略/爬取/任务管理  │  │  数据查询/删除/导出        │
└──────────┬───────────┘  └──────────┬────────────────┘
           │                         │
           ▼                         ▼
┌─────────────────────────────────────────────────────┐
│                  MySQL 数据库                        │
│               crawler_db (端口 3306)                 │
│   admin / crawler_strategy / task_record / website   │
│   webpage / content / image / datasource             │
└─────────────────────────────────────────────────────┘
```

系统由三个服务组成：

| 服务 | 端口 | 说明 |
|------|------|------|
| **前端** (Vite Dev Server) | 3002 | Vue 3 SPA，提供用户界面 |
| **爬虫后端** (CRAWLER_NEW.py) | 8000 | FastAPI 服务，负责策略管理、爬虫执行、任务控制 |
| **数据代理** (data_proxy.py) | 8004 | FastAPI 服务，负责数据查询、删除、导出、图片代理 |

前端通过 Vite 的代理配置将 `/api/*` 转发至后端服务、`/data-api/*` 转发至数据代理服务。

---

## 环境要求

| 组件 | 最低版本 |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |
| MySQL | 8.0+ |
| Git | 2.30+ |

**操作系统**：Linux (推荐 Ubuntu 22.04+) / macOS / Windows (WSL2)

---

## 安装部署

### 1. 克隆项目

```bash
git clone https://github.com/xiaoberber8-ai/database-project-for-web-crawler.git
cd database-project-for-web-crawler
```

### 2. 安装 MySQL 并创建数据库

```bash
# Ubuntu 安装 MySQL
sudo apt update
sudo apt install mysql-server

# 启动 MySQL 服务
sudo systemctl start mysql
sudo systemctl enable mysql

# 登录 MySQL 创建数据库和用户
sudo mysql -u root -p
```

在 MySQL 中执行：

```sql
CREATE DATABASE crawler_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 如需创建专用用户（可选）
CREATE USER 'crawler'@'%' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON crawler_db.* TO 'crawler'@'%';
FLUSH PRIVILEGES;
```

> **说明**：系统首次启动时，SQLAlchemy 会根据 ORM 模型自动创建所有数据表（`admin`、`crawler_strategy`、`task_record`、`website`、`webpage`、`content`、`image`、`datasource`、`system_setting`），无需手动建表。

### 3. 安装 Python 依赖

```bash
pip install fastapi uvicorn sqlalchemy pymysql requests beautifulsoup4 lxml pillow pydantic pycryptodome
```

各依赖用途说明：

| 依赖包 | 用途 |
|--------|------|
| `fastapi` + `uvicorn` | 后端 Web 框架与 ASGI 服务器 |
| `sqlalchemy` + `pymysql` | ORM 与 MySQL 驱动 |
| `requests` | HTTP 请求（爬取网页） |
| `beautifulsoup4` + `lxml` | HTML 解析与数据提取 |
| `pillow` | 图片尺寸检测与过滤 |
| `pydantic` | 请求/响应数据校验 |
| `pycryptodome` | 搜狐图片 AES 解密（可选） |

### 4. 安装前端依赖

```bash
cd crawler-frontend
npm install
cd ..
```

---

## 配置说明

### 数据库连接配置

数据库连接通过环境变量配置，也可直接修改代码中的默认值。

**方式一：环境变量（推荐）**

```bash
export DATABASE_URL="mysql+pymysql://root:your_password@127.0.0.1:3306/crawler_db?charset=utf8mb4"
export DB_HOST="127.0.0.1"
export DB_PORT="3306"
export DB_USER="root"
export DB_PASSWORD="your_password"
export DB_NAME="crawler_db"
```

**方式二：修改代码默认值**

- 爬虫后端：编辑 `爬虫数据库系统/CRAWLER_NEW.py` 第 57-60 行的 `DATABASE_URL` 默认值
- 数据代理：编辑 `crawler-frontend/data_proxy.py` 第 22-28 行的 `DB_CONFIG` 默认值

### 端口配置

| 服务 | 默认端口 | 环境变量 |
|------|---------|---------|
| 爬虫后端 | 8000 | 修改 `CRAWLER_NEW.py` 中的 `uvicorn.run` port 参数 |
| 数据代理 | 8004 | `DATA_PROXY_PORT` |
| 前端开发服务器 | 3002 | 修改 `crawler-frontend/vite.config.js` 中的 `server.port` |

> **注意**：如果修改了后端端口，需要同步更新 `vite.config.js` 中的代理 `target` 地址。

---

## 启动服务

需要按顺序启动三个服务（分别在三个终端中运行）：

### 终端 1：启动爬虫后端服务

```bash
cd 爬虫数据库系统
python CRAWLER_NEW.py
```

启动成功后会看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### 终端 2：启动数据代理服务

```bash
cd crawler-frontend
python data_proxy.py
```

启动成功后会看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8004 (Press CTRL+C to quit)
```

### 终端 3：启动前端开发服务器

```bash
cd crawler-frontend
npm run dev
```

启动成功后会看到：

```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:3002/
```

### 验证服务状态

在浏览器中访问以下地址确认各服务正常运行：

| 地址 | 预期结果 |
|------|---------|
| http://localhost:8000/ | 返回 `{"message":"Crawler API is running"}` |
| http://localhost:8004/webpages | 返回 JSON 数组（可能为空 `[]`） |
| http://localhost:3002/ | 显示 SpideX 登录页面 |

---

## 使用说明

### 登录系统

1. 打开浏览器访问 http://localhost:3002/
2. 在登录页面输入任意用户名和密码（非空即可）即可登录
3. 登录后自动跳转至仪表盘页面

### 创建爬虫策略

系统提供两种策略模式：

#### 宝宝策略（快速爬取）

适合快速抓取单个页面，只需输入名称和目标 URL：

1. 点击「新建策略」→ 选择「宝宝策略」
2. 填写策略名称和目标网址（如 `https://news.sina.com.cn`）
3. 点击「创建并爬取」立即开始

> 宝宝策略使用默认参数：爬取深度=1，不下载图片，仅抓取文本内容。

#### 专业模式（完整配置）

适合需要精细控制的高级用户：

1. 点击「新建策略」→ 选择「专业模式」
2. 配置各项参数：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 策略名称 | 自定义策略标识 | - |
| 目标URL | 爬取起始地址 | - |
| 爬取深度 | BFS 最大深度（1-5） | 1 |
| 允许域名 | 限制爬取范围（留空则不限） | 空 |
| 标题选择器 | CSS 选择器，如 `h1`、`.title` | `title` |
| 正文选择器 | CSS 选择器，如 `.article`、`body` | `body` |
| 下载图片 | 是否下载页面图片 | 是 |
| 只抓正文图片 | 过滤正文区域外的图片 | 是 |
| 重复数据处理 | `skip`（跳过）/ `overwrite`（覆盖） | skip |
| 超时时间 | 单页请求超时（秒） | 15 |
| 请求频率 | 每秒请求数 | 1.0 |

3. 点击「创建」保存策略

### 启动与控制爬虫

1. 在策略列表上方的「爬虫控制」栏，从下拉菜单选择一个策略
2. 点击「启动」按钮开始爬取
3. 爬取过程中可使用控制按钮：

| 按钮 | 功能 |
|------|------|
| 启动 | 选中策略开始爬取 |
| 暂停 | 暂停当前爬取任务 |
| 恢复 | 恢复已暂停的任务 |
| 停止 | 终止当前爬取任务 |
| 刷新状态 | 更新爬虫运行状态 |

4. 在「任务记录」表中可查看每次爬取的 ID、状态、条目数、时间等信息

### 数据管理

通过左侧导航栏的「数据管理」进入：

#### 文本数据

- 支持按**任务 ID**、**策略 ID** 筛选内容
- 支持单条删除、批量勾选删除
- 支持导出为 CSV 文件
- 显示标题、正文摘要、爬取时间、发布者等信息

#### 图片数据

- 支持按**任务 ID**、**策略 ID** 筛选图片
- 缩略图显示（通过本地图片代理加载）
- 点击预览大图
- 支持单条删除、批量删除

### 内容检索

通过左侧导航栏的「内容检索」进入：

- 支持按**关键词**全文搜索（标题 + 正文）
- 支持按**策略 ID** 过滤
- 显示匹配内容的标题、正文片段、发布时间

---

## 功能验证与测试

部署完成后，按以下步骤验证核心功能：

### 测试 1：系统启动与登录

```bash
# 1. 确认三个服务均正常启动
curl http://localhost:8000/             # 预期: {"message":"Crawler API is running"}
curl http://localhost:8004/webpages     # 预期: []（空数组）
curl http://localhost:3002/             # 预期: HTML 页面

# 2. 浏览器访问 http://localhost:3002/ 登录
```

**预期结果**：登录页正常显示，输入任意用户名密码后跳转至仪表盘。

### 测试 2：创建宝宝策略并爬取

1. 点击「新建策略」→ 选择「宝宝策略」
2. 输入名称 `测试爬取`，目标 URL `https://news.sina.com.cn`
3. 点击「创建并爬取」

**预期结果**：
- 策略列表出现新策略
- 爬虫状态变为「运行中」
- 等待片刻后任务完成，任务记录显示抓取条目数 > 0

### 测试 3：专业模式策略爬取

1. 新建专业模式策略，配置如下：
   - 名称：`新浪新闻深度爬取`
   - 目标URL：`https://news.sina.com.cn`
   - 爬取深度：2
   - 标题选择器：`h1`
   - 正文选择器：`.article`
   - 下载图片：开启
   - 重复数据处理：跳过
2. 选中该策略，点击「启动」

**预期结果**：爬虫执行 BFS 爬取，在任务记录中可见抓取条目数逐渐增长。

### 测试 4：数据查看与管理

1. 进入「数据管理」→「文本数据」
2. 确认有数据记录，查看标题、正文、爬取时间
3. 测试按任务 ID / 策略 ID 筛选
4. 勾选多条记录，点击批量删除
5. 切换至「图片数据」标签
6. 确认缩略图正常加载，点击可预览大图

**预期结果**：数据列表正常展示，筛选/删除/导出功能正常。

### 测试 5：内容检索

1. 进入「内容检索」页面
2. 在搜索框输入关键词（如「新闻」）
3. 可选：输入策略 ID 过滤
4. 点击搜索

**预期结果**：返回匹配的内容列表，显示标题和正文高亮片段。

### 测试 6：仪表盘

1. 进入「仪表盘」页面

**预期结果**：显示策略总数、任务总数、已爬取网页数、文本内容数、图片数等统计信息及最近任务状态。

### 测试 7：API 接口验证

```bash
# 获取策略列表
curl http://localhost:8000/strategies

# 获取爬虫状态
curl http://localhost:8000/crawl/status

# 获取任务列表
curl http://localhost:8000/tasks

# 查询文本内容（通过数据代理）
curl http://localhost:8004/contents

# 查询图片数据
curl http://localhost:8004/images
```

**预期结果**：各接口返回正确的 JSON 数据。

---

## 项目结构

```
database-project-for-web-crawler/
├── README.md                          # 项目说明文档
├── .gitignore                         # Git 忽略配置
├── 代码文档.md                         # 代码架构与接口文档
├── 用户操作手册.md                     # 详细用户操作手册
│
├── 爬虫数据库系统/                      # 后端服务目录
│   ├── CRAWLER_NEW.py                  # 爬虫核心服务（FastAPI，端口 8000）
│   ├── Crawler System Usage Guide.docx # 英文使用指南
│   └── images/                         # 爬取的图片存储目录（gitignore 排除）
│
└── crawler-frontend/                   # 前端项目目录
    ├── index.html                      # HTML 入口
    ├── package.json                    # Node.js 依赖配置
    ├── package-lock.json               # 依赖锁定文件
    ├── vite.config.js                  # Vite 构建配置（含代理规则）
    ├── data_proxy.py                   # 数据查询代理服务（FastAPI，端口 8004）
    ├── src/
    │   ├── main.js                     # Vue 应用入口
    │   ├── App.vue                     # 根组件
    │   ├── api/
    │   │   └── index.js                # API 请求封装（axios）
    │   ├── router/
    │   │   └── index.js                # 路由配置（含登录守卫）
    │   ├── assets/
    │   │   └── spidex-logo.png         # 系统 Logo
    │   ├── components/
    │   │   └── SpiderAnimation.vue     # 爬虫动画组件
    │   └── views/
    │       ├── Login.vue               # 登录页
    │       ├── Layout.vue              # 布局框架（侧边栏+顶栏）
    │       ├── Dashboard.vue           # 仪表盘
    │       ├── Crawler.vue             # 爬虫策略管理
    │       ├── Data.vue                # 数据管理（文本+图片）
    │       └── Search.vue              # 内容检索
    └── node_modules/                   # 前端依赖（gitignore 排除）
```

---

## 常见问题

### Q1：启动后端报错 `Can't connect to MySQL server`

**原因**：MySQL 服务未启动或连接配置错误。

**解决**：
```bash
# 检查 MySQL 是否运行
sudo systemctl status mysql

# 如未运行，启动 MySQL
sudo systemctl start mysql

# 检查连接参数（用户名、密码、主机、端口）是否正确
# 可通过 mysql 命令行手动测试连接
mysql -u root -p -h 127.0.0.1 -P 3306 crawler_db
```

### Q2：前端页面打开空白或 API 请求 404

**原因**：后端服务未启动，或 Vite 代理配置与后端端口不匹配。

**解决**：
1. 确认 `CRAWLER_NEW.py`（端口 8000）和 `data_proxy.py`（端口 8004）均已启动
2. 检查 `crawler-frontend/vite.config.js` 中的 `proxy.target` 是否指向正确端口
3. 重启前端开发服务器 `npm run dev`

### Q3：爬虫启动后抓取条目为 0

**可能原因与解决**：

| 原因 | 解决方法 |
|------|---------|
| DNS 无法解析域名 | 检查 `/etc/resolv.conf`，确保有可用 DNS（如 `8.8.8.8`） |
| 目标网站拒绝访问 | 更换 `User-Agent` 或降低请求频率 |
| 网络不通 | `ping` 目标网站确认网络可达 |
| 选择器匹配不到内容 | 调整标题/正文选择器，或使用默认的 `title`/`body` |

### Q4：图片缩略图无法显示

**原因**：外链图片 URL 存在防盗链或 token 过期。

**解决**：系统已内置本地图片代理（`/image_file/{id}` 接口），需确保：
1. `data_proxy.py` 正在运行
2. 图片已被下载到 `爬虫数据库系统/images/` 目录
3. 策略中开启了「下载图片」选项

### Q5：`pip install pycryptodome` 安装失败

**说明**：`pycryptodome` 仅用于搜狐图片的 AES 解密，非必需依赖。安装失败不影响其他功能，可跳过安装。

### Q6：如何清空数据重新开始

```sql
-- 登录 MySQL 后执行（谨慎操作！会删除所有数据）
USE crawler_db;
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE image;
TRUNCATE TABLE content;
TRUNCATE TABLE webpage;
TRUNCATE TABLE task_record;
TRUNCATE TABLE datasource;
TRUNCATE TABLE website;
TRUNCATE TABLE crawler_strategy;
TRUNCATE TABLE admin;
SET FOREIGN_KEY_CHECKS = 1;
```

同时删除本地图片文件：
```bash
rm -rf 爬虫数据库系统/images/*
```
