import asyncio, json, sys
import websockets

TOKEN = sys.argv[1]
URL = fws://127.0.0.1:8000/ws?token={TOKEN}

async def main():
    async with websockets.connect(URL) as ws:
        # recv welcome
        msg = await ws.recv()
        print('recv1:', msg)
        await ws.send(json.dumps({type:ping}))
        msg2 = await ws.recv()
        print('recv2:', msg2)

asyncio.run(main())
