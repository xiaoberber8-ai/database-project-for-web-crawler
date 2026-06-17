"""
数据查询代理服务 - 为前端提供 webpages/contents/images/websites 查询接口
不修改后端 CRAWLER_NEW.py，独立运行在 8002 端口
"""
import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pymysql

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "172.31.224.1"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "zhouwanyi1222"),
    "database": os.environ.get("DB_NAME", "crawler_db"),
    "charset": "utf8mb4"
}

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
    return query_all("SELECT * FROM content ORDER BY id DESC")


@app.get("/images")
def list_images():
    return query_all("SELECT * FROM image ORDER BY id DESC")


@app.get("/websites")
def list_websites():
    return query_all("SELECT * FROM website ORDER BY id DESC")


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
        from fastapi import HTTPException
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
        from fastapi import HTTPException
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
                from fastapi import HTTPException
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
                from fastapi import HTTPException
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
    except Exception as e:
        conn.rollback()
        if isinstance(e, HTTPException):
            raise e
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("DATA_PROXY_PORT", 8004))
    uvicorn.run("data_proxy:app", host="0.0.0.0", port=port, reload=False)
