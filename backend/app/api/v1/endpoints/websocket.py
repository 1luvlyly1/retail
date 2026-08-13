from __future__ import annotations

import asyncio
import json
from typing import Dict, Set

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.services.event_bus import CHANNEL_PREFIX

logger = structlog.get_logger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, visit_id: str):
        await websocket.accept()
        self._rooms.setdefault(visit_id, set()).add(websocket)
        logger.info("WS connected", visit_id=visit_id)

    def disconnect(self, websocket: WebSocket, visit_id: str):
        if visit_id in self._rooms:
            self._rooms[visit_id].discard(websocket)
            if not self._rooms[visit_id]:
                del self._rooms[visit_id]

    async def broadcast_to_visit(self, visit_id: str, data: dict):
        dead = set()
        for ws in self._rooms.get(visit_id, set()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._rooms.get(visit_id, set()).discard(ws)

    async def send_to_socket(self, websocket: WebSocket, data: dict):
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    def get_connection_count(self, visit_id: str) -> int:
        return len(self._rooms.get(visit_id, set()))


manager = ConnectionManager()

# visit_id -> asyncio Task chạy subscriber riêng cho visit đó
_subscriber_tasks: Dict[str, asyncio.Task] = {}


async def _subscribe_and_forward(visit_id: str):
    """
    Lắng nghe Redis channel của visit này, forward mọi message
    tới các WebSocket connections thật đang mở trong process này.
    Chạy cho tới khi process restart hoặc exception (không dừng khi hết client
    để tránh miss event trong cửa sổ reconnect).
    """
    client = aioredis.from_url(settings.REDIS_URL)
    pubsub = client.pubsub()
    channel = f"{CHANNEL_PREFIX}{visit_id}"
    await pubsub.subscribe(channel)
    logger.info("Subscribed to visit channel", visit_id=visit_id)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            # Không break khi count == 0: nếu break thì subscriber chết, WebSocket
            # reconnect sẽ tạo subscriber mới nhưng có cửa sổ chưa subscribe → mất event.
            # broadcast_to_visit xử lý gracefully khi không có connection (noop).
            try:
                data = json.loads(message["data"])
                await manager.broadcast_to_visit(visit_id, data)
            except (json.JSONDecodeError, TypeError):
                pass
    finally:
        await pubsub.unsubscribe(channel)
        await client.close()
        _subscriber_tasks.pop(visit_id, None)
        logger.info("Unsubscribed from visit channel", visit_id=visit_id)


def _ensure_subscriber(visit_id: str):
    """Khởi tạo subscriber task cho visit này nếu chưa có."""
    existing = _subscriber_tasks.get(visit_id)
    if existing is None or existing.done():
        _subscriber_tasks[visit_id] = asyncio.create_task(_subscribe_and_forward(visit_id))


@router.websocket("/visits/{visit_id}")
async def visit_websocket(websocket: WebSocket, visit_id: str):
    await manager.connect(websocket, visit_id)
    _ensure_subscriber(visit_id)
    await manager.send_to_socket(websocket, {
        "type": "connected",
        "visit_id": visit_id,
        "message": "Đang theo dõi cập nhật realtime...",
    })
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if json.loads(data).get("type") == "ping":
                    await manager.send_to_socket(websocket, {"type": "pong"})
            except asyncio.TimeoutError:
                await manager.send_to_socket(websocket, {"type": "heartbeat"})
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, visit_id)
