from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.auth import router as auth_router
from app.api.simulations import router as sim_router
from app.ws.handler import ws_handler

app = FastAPI(title="Market Replay Backtester", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sim_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket):
    await ws_handler(websocket)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
