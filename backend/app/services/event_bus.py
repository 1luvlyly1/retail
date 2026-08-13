"""
Redis Pub/Sub bridge.

Vấn đề: Celery worker và FastAPI chạy trong 2 process/container riêng biệt,
không share memory. ConnectionManager (giữ WebSocket connections) chỉ sống
trong process FastAPI — Celery worker không thể gọi trực tiếp vào đó.

Giải pháp: Celery worker PUBLISH message lên Redis channel.
FastAPI process chạy 1 background task SUBSCRIBE channel đó,
nhận message rồi forward qua WebSocket connections thật của nó.
"""
from __future__ import annotations

import json

import redis.asyncio as aioredis

from app.core.config import settings

CHANNEL_PREFIX = "sitevisit:visit:"


def _redis_url() -> str:
    return settings.REDIS_URL


async def publish_visit_event(visit_id: str, data: dict) -> None:
    """Gọi từ Celery worker (qua run_async) để gửi event tới FastAPI process."""
    client = aioredis.from_url(_redis_url())
    try:
        await client.publish(f"{CHANNEL_PREFIX}{visit_id}", json.dumps(data))
    finally:
        await client.close()


def publish_visit_event_sync(visit_id: str, data: dict) -> None:
    """Phiên bản sync — dùng trực tiếp trong Celery task (không cần asyncio)."""
    import redis as sync_redis

    client = sync_redis.from_url(_redis_url())
    try:
        client.publish(f"{CHANNEL_PREFIX}{visit_id}", json.dumps(data))
    finally:
        client.close()
