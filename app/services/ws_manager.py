from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Dict, Set

from fastapi import WebSocket


@dataclass
class Client:
    user_id: int
    ws: WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._clients_by_user: Dict[int, Set[WebSocket]] = {}
        self._last_pong: Dict[WebSocket, float] = {}
        self._msg_counter_minute: Dict[WebSocket, tuple[int, float]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients_by_user.setdefault(user_id, set()).add(websocket)
        now = monotonic()
        self._last_pong[websocket] = now
        self._msg_counter_minute[websocket] = (0, now)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        conns = self._clients_by_user.get(user_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._clients_by_user.pop(user_id, None)
        self._last_pong.pop(websocket, None)
        self._msg_counter_minute.pop(websocket, None)

    async def send_to_user(self, user_id: int, message: dict) -> None:
        for ws in list(self._clients_by_user.get(user_id, set())):
            await ws.send_json(message)

    async def broadcast(self, message: dict) -> None:
        for conns in list(self._clients_by_user.values()):
            for ws in list(conns):
                await ws.send_json(message)

    def touch_pong(self, ws: WebSocket) -> None:
        self._last_pong[ws] = monotonic()

    def is_timed_out(self, ws: WebSocket, timeout_seconds: int) -> bool:
        last = self._last_pong.get(ws, 0.0)
        return (monotonic() - last) > timeout_seconds

    def check_rate_limit(self, ws: WebSocket, max_per_minute: int) -> bool:
        count, start = self._msg_counter_minute.get(ws, (0, monotonic()))
        now = monotonic()
        if now - start >= 60:
            self._msg_counter_minute[ws] = (1, now)
            return True
        if count + 1 > max_per_minute:
            return False
        self._msg_counter_minute[ws] = (count + 1, start)
        return True


manager = ConnectionManager()


