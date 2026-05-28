from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing  import Set
import asyncio, json

router   = APIRouter()
_clients: Set[WebSocket] = set()
_lock    = asyncio.Lock()

# ── Broadcast to every connected client ───────────────────
async def broadcast(payload: dict) -> None:
    """Send JSON payload to all live WebSocket clients."""
    dead = set()
    msg  = json.dumps(payload)
    async with _lock:
        for ws in _clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)   # mark for removal
        _clients -= dead

# ── Main WebSocket endpoint ───────────────────────────────
@router.websocket("/telemetry")
async def telemetry_ws(ws: WebSocket):
    await ws.accept()
    async with _lock:
        _clients.add(ws)
    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "pong":
                continue   # keepalive response — discard

            if msg_type == "command":
                # Route ATC command to swarm boids engine
                await ws.app.state.boids.handle_command(msg)

            if msg_type == "rag_query":
                # Forward natural-language query to knowledge base
                result = await ws.app.state.knowledge.query(
                    msg.get("q", "")
                )
                await ws.send_json({"type": "rag_result", **result})

    except WebSocketDisconnect:
        async with _lock:
            _clients.discard(ws)

# ── 30-second ping heartbeat loop ─────────────────────────
async def ping_loop() -> None:
    while True:
        await asyncio.sleep(30)
        await broadcast({"type": "ping"})
