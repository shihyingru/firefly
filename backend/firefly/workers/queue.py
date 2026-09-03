"""RQ 任務佇列 / RQ job queue. 指紋、聚類、起草皆非同步(文件 03)。"""
from __future__ import annotations

import os

from rq import Queue

from ..services.redis_client import get_sync_redis

QUEUE_NAME = "firefly"


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_sync_redis())


async def dispatch_process_url(normalized_url: str) -> None:
    """排程 Stage 0 任務。FIREFLY_INLINE_JOBS=1 時在同一事件迴圈內直接執行(測試/單機示範)。
    Dispatch the Stage 0 job. With FIREFLY_INLINE_JOBS=1 it runs inline on the same loop (tests/demo)."""
    if os.environ.get("FIREFLY_INLINE_JOBS") == "1":
        from ..pipeline.jobs import _process_url

        await _process_url(normalized_url)
        return
    get_queue().enqueue("firefly.pipeline.jobs.process_url", normalized_url, job_timeout=300)
