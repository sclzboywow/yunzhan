import asyncio
import json
import uuid
from typing import Optional

import httpx
import websockets


USERNAME = f"user_{uuid.uuid4().hex[:8]}"
PASSWORD = "Admin1234"


async def get_token() -> Optional[str]:
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as client:
        # Try register (ignore if exists)
        try:
            await client.post("/auth/register", json={"username": USERNAME, "password": PASSWORD})
        except Exception:
            pass
        # Login
        resp = await client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
        resp.raise_for_status()
        return resp.json().get("access_token")


async def main() -> None:
    token = await get_token()
    if not token:
        raise SystemExit("no token")
    url = f"ws://127.0.0.1:8000/ws?token={token}"
    async with websockets.connect(url) as ws:
        msg1 = await ws.recv()
        print("recv1:", msg1)
        await ws.send(json.dumps({"type": "ping"}))
        msg2 = await ws.recv()
        print("recv2:", msg2)


if __name__ == "__main__":
    asyncio.run(main())


