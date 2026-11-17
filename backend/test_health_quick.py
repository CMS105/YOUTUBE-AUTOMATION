import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from httpx import AsyncClient, ASGITransport
from app.main import app

async def main():
    print("STARTING TEST...", flush=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        print("CLIENT READY, SENDING GET /api/v1/health...", flush=True)
        r = await c.get("/api/v1/health")
        print("GOT RESPONSE:", r.status_code, r.text, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
