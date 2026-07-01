"""
数据查询代理服务 - 为前端提供 webpages/contents/images/websites 查询接口
不修改后端 CRAWLER_NEW.py，独立运行在 8002 端口

提供功能：
- /webpages、/contents、/images、/websites 数据查询接口
- /tasks/{task_id} 任务级联删除
- /strategy/{strategy_id}/cascade 策略级联删除
- /strategies/{strategy_id} 策略更新
"""
import os
import json
import logging
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import pymysql

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("data_proxy")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "172.31.224.1"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "zhouwanyi1222"),
    "database": os.environ.get("DB_NAME", "crawler_db"),
    "charset": "utf8mb4"
}

# 爬虫系统目录（CRAWLER_NEW.py 运行目录，图片保存在其下的 images/）
# data_proxy.py 在 crawler-frontend/ 下，上级目录的"爬虫数据库系统"即为爬虫工作目录
CRAWLER_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "爬虫数据库系统")

app = FastAPI(title="Crawler Data Query Proxy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def query_all(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            # 将 datetime 等类型转为字符串
            result = []
            for row in rows:
                new_row = {}
                for k, v in row.items():
                    if hasattr(v, 'isoformat'):
                        new_row[k] = v.isoformat()
                    elif isinstance(v, bytes):
                        new_row[k] = v.decode('utf-8', errors='replace')
                    else:
                        new_row[k] = v
                result.append(new_row)
            return result
    finally:
        conn.close()


@app.get("/webpages")
def list_webpages():
    return query_all("SELECT * FROM webpage ORDER BY id DESC")


@app.get("/contents")
def list_contents():
    # 关联 webpage（取 fetch_time 爬取时间、task_id）、task_record（取 strategy_id）、datasource（取 publisher_name 发布者）
    return query_all("""
        SELECT c.*,
               w.fetch_time   AS crawl_time,
               w.task_id      AS task_id,
               t.strategy_id  AS strategy_id,
               ds.publisher_name AS Publisher,
               ds.origin_url  AS datasource_url
        FROM content c
        LEFT JOIN webpage w     ON c.webpage_id = w.id
        LEFT JOIN task_record t ON w.task_id = t.id
        LEFT JOIN datasource ds ON c.datasource_id = ds.id
        ORDER BY c.id DESC
    """)


@app.get("/images")
def list_images():
    # 关联 webpage（取 task_id）、task_record（取 strategy_id），便于前端按任务/策略筛选
    return query_all("""
        SELECT i.*,
               w.task_id      AS task_id,
               t.strategy_id  AS strategy_id
        FROM image i
        LEFT JOIN webpage w     ON i.webpage_id = w.id
        LEFT JOIN task_record t ON w.task_id = t.id
        ORDER BY i.id DESC
    """)


@app.get("/image_file/{image_id}")
def get_image_file(image_id: int):
    """
    根据图片ID读取本地已下载的图片文件并返回。
    解决外链图片URL带token时效性/防盗链导致浏览器无法直接加载的问题。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT local_path FROM image WHERE id = %s", (image_id,))
            row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="图片记录不存在")

    local_path = row.get("local_path", "")
    if not local_path:
        raise HTTPException(status_code=404, detail="该图片无本地路径")

    # local_path 形如 "./images/xxx.jpg"，是相对于 CRAWLER_NEW.py 运行目录的路径
    # 映射为绝对路径
    if local_path.startswith("./"):
        abs_path = os.path.join(CRAWLER_BASE_DIR, local_path[2:])
    elif local_path.startswith("/"):
        abs_path = local_path
    else:
        abs_path = os.path.join(CRAWLER_BASE_DIR, local_path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="本地图片文件不存在")

    # 根据文件扩展名确定 Content-Type
    ext = os.path.splitext(abs_path)[1].lower()
    content_type_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".webp": "image/webp", ".bmp": "image/bmp",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")

    with open(abs_path, "rb") as f:
        content = f.read()
    return Response(content=content, media_type=content_type)


@app.get("/websites")
def list_websites():
    return query_all("SELECT * FROM website ORDER BY id DESC")


# ==================== 内容与图片的删除接口 ====================

@app.delete("/contents/{content_id}")
def delete_content(content_id: int):
    """删除单条文本内容"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM content WHERE id = %s", (content_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"内容不存在: {content_id}")
            return {"msg": "content deleted", "content_id": content_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/contents/batch-delete")
def batch_delete_contents(payload: dict):
    """批量删除文本内容"""
    ids = payload.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="ids 不能为空")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(ids))
            cursor.execute(f"DELETE FROM content WHERE id IN ({placeholders})", ids)
            deleted = cursor.rowcount
            conn.commit()
            return {"msg": "batch delete done", "deleted_count": deleted}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.delete("/images/{image_id}")
def delete_image(image_id: int):
    """删除单条图片记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM image WHERE id = %s", (image_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"图片不存在: {image_id}")
            return {"msg": "image deleted", "image_id": image_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/images/batch-delete")
def batch_delete_images(payload: dict):
    """批量删除图片记录"""
    ids = payload.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="ids 不能为空")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(ids))
            cursor.execute(f"DELETE FROM image WHERE id IN ({placeholders})", ids)
            deleted = cursor.rowcount
            conn.commit()
            return {"msg": "batch delete done", "deleted_count": deleted}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    """级联删除任务及其关联的 webpage/content/image 数据"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取该任务关联的 webpage id
            cursor.execute("SELECT id FROM webpage WHERE task_id = %s", (task_id,))
            webpage_ids = [row["id"] for row in cursor.fetchall()]

            if webpage_ids:
                placeholders = ",".join(["%s"] * len(webpage_ids))
                # 删除关联的 image
                cursor.execute(f"DELETE FROM image WHERE webpage_id IN ({placeholders})", webpage_ids)
                # 删除关联的 content
                cursor.execute(f"DELETE FROM content WHERE webpage_id IN ({placeholders})", webpage_ids)
                # 删除关联的 webpage
                cursor.execute("DELETE FROM webpage WHERE task_id = %s", (task_id,))

            # 删除任务记录
            cursor.execute("DELETE FROM task_record WHERE id = %s", (task_id,))
            conn.commit()
            return {"msg": "task and related data deleted", "task_id": task_id, "deleted_webpages": len(webpage_ids)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.delete("/strategy/{strategy_id}/cascade")
def delete_strategy_cascade(strategy_id: int):
    """级联删除策略及其所有关联数据（任务、网页、内容、图片）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 获取该策略下所有任务
            cursor.execute("SELECT id FROM task_record WHERE strategy_id = %s", (strategy_id,))
            task_ids = [row["id"] for row in cursor.fetchall()]

            for tid in task_ids:
                cursor.execute("SELECT id FROM webpage WHERE task_id = %s", (tid,))
                webpage_ids = [row["id"] for row in cursor.fetchall()]
                if webpage_ids:
                    placeholders = ",".join(["%s"] * len(webpage_ids))
                    cursor.execute(f"DELETE FROM image WHERE webpage_id IN ({placeholders})", webpage_ids)
                    cursor.execute(f"DELETE FROM content WHERE webpage_id IN ({placeholders})", webpage_ids)
                cursor.execute("DELETE FROM webpage WHERE task_id = %s", (tid,))

            cursor.execute("DELETE FROM task_record WHERE strategy_id = %s", (strategy_id,))
            cursor.execute("DELETE FROM crawler_strategy WHERE id = %s", (strategy_id,))
            conn.commit()
            return {"msg": "strategy and all related data deleted", "strategy_id": strategy_id, "deleted_tasks": len(task_ids)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: int, payload: dict):
    """更新策略 - 绕过后端 model_dump_json bug，直接操作数据库"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 检查策略是否存在
            cursor.execute("SELECT id FROM crawler_strategy WHERE id = %s", (strategy_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Strategy not found")

            updates = []
            params = []

            if "name" in payload and payload["name"] is not None:
                updates.append("name = %s")
                params.append(payload["name"])

            if "target_url" in payload and payload["target_url"] is not None:
                updates.append("target_url = %s")
                params.append(payload["target_url"])

            if "rules" in payload and payload["rules"] is not None:
                updates.append("rules_json = %s")
                params.append(json.dumps(payload["rules"], ensure_ascii=False))

            if "Status" in payload and payload["Status"] is not None:
                updates.append("`Status` = %s")
                params.append(payload["Status"])

            if "Frequency" in payload and payload["Frequency"] is not None:
                updates.append("`Frequency` = %s")
                params.append(payload["Frequency"])

            if "creator_id" in payload and payload["creator_id"] is not None:
                updates.append("creator_id = %s")
                params.append(payload["creator_id"])

            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            updates.append("updated_at = NOW()")
            params.append(strategy_id)

            sql = f"UPDATE crawler_strategy SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(sql, params)
            conn.commit()

            # 返回更新后的策略
            cursor.execute("SELECT * FROM crawler_strategy WHERE id = %s", (strategy_id,))
            row = cursor.fetchone()
            result = {}
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    result[k] = v.isoformat()
                elif isinstance(v, bytes):
                    result[k] = v.decode('utf-8', errors='replace')
                else:
                    result[k] = v
            # 解析 rules_json
            if 'rules_json' in result and result['rules_json']:
                result['rules'] = json.loads(result['rules_json'])
            return result
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("DATA_PROXY_PORT", 8004))
    uvicorn.run("data_proxy:app", host="0.0.0.0", port=port, reload=False)
