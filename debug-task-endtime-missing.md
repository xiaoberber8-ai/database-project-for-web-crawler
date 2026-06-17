# Debug: task-endtime-missing

## Bug Description
- Task ID 13, strategy ID 6 完成后没有 end_time
- 之前已修复过类似问题（启动时清理孤儿任务），但新运行的任务仍然没有结束时间

## Status: [RESOLVED]

## Evidence
- `GET /crawl/status`: `{"thread_alive":false,"paused":false,"stopped":false}`
- `GET /tasks/13`: `{"id":13,"Status":"running","end_time":null,"item_count":2,"error_message":null}`
- 线程已死 (`thread_alive: false`)，stop_event 未设置 (`stopped: false`)
- 任务成功处理了 2 个条目 (`item_count: 2`)，说明爬虫循环正常运行过

## Root Cause
**H1 + H2 组合（commit 双重失败）**

在 `crawl_strategy` 函数中：
1. 成功路径 `task.Status = "completed"; db.commit()` 如果失败（会话损坏），抛出异常
2. 异常被外层 `except` 捕获，但 `except` 块中的 `db.commit()` 使用**同一个损坏的会话**，也会失败
3. 两次 commit 都失败 → 内存中的状态变更（Status/end_time/error_message）全部丢失
4. 任务永远停留在 `running` 状态，`end_time` 为 `null`

原来的 `finally` 块只做 `db.close()`，没有任何状态兜底逻辑。

## Fix
在 [CRAWLER_NEW.py](file:///home/xiaoberber/web_crawler/database-project-for-web-crawler/爬虫数据库系统/CRAWLER_NEW.py) 中做了以下修改：

### 1. 添加 logging 模块
- 配置 `logging.basicConfig`，记录线程名和时间戳
- 在任务开始、循环结束、commit 成功/失败、异常等关键节点记录日志

### 2. commit 失败处理（成功路径）
```python
try:
    db.commit()
except Exception as commit_err:
    db.rollback()
    self._force_update_task_status(task_id, "failed", f"成功路径commit失败: {commit_err}")
    raise
```

### 3. commit 失败处理（异常路径）
```python
except Exception as commit_err:
    db.rollback()
    self._force_update_task_status(task_id, "failed", f"异常路径commit失败: {repr(e)}")
```

### 4. finally 安全网（核心修复）
```python
finally:
    db.close()
    self._ensure_task_finalized(task_id)
```
`_ensure_task_finalized` 使用**全新会话**检查任务是否仍为 `running`，如果是则强制标记为 `failed`。这覆盖了所有未捕获的退出路径。

### 5. 线程异常钩子
```python
crawl_thread.excepthook = _thread_excepthook
```
捕获线程中未处理的异常并记录日志。

### 6. 手动修复任务13
已将 task 13 的状态从 `running` 改为 `failed`，补充了 `end_time` 和 `error_message`。

## Verification
- 任务13 已修复：`Status=failed, end_time=2026-06-17T19:39:30`
- 代码语法检查通过
- **需要重启后端服务使代码修改生效**
