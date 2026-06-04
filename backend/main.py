from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from .websocket_server          import router as ws_router
from .telemetry                 import TelemetryGenerator
from .mcp_context               import MCPContextEngine
from .swarm.boids_engine        import BoidsEngine
from .rag.retriever             import RAGRetriever
from .rag.mission_knowledge     import MissionKnowledge
from .security.hedera_identity  import HederaIdentity
from .fabric.fabric_stream      import FabricStream
from .fabric.analytics          import SwarmAnalytics
from .fabric.retraining_pipeline import RetrainingPipeline


def map_incoming_drones(drones_raw):
    """Normalize incoming drone frames to backend internal shape.

    Returns list of dicts with keys: id, x, y, altitude, battery, signal, ai_conf, alert
    Values for battery/signal/ai_conf are scaled to 0..100 if provided in 0..1.
    """
    mapped = []
    for d in drones_raw:
        mapped.append({
            "id": d.get("droneId") or d.get("id"),
            "x": d.get("pos", {}).get("x", 0),
            "y": d.get("pos", {}).get("y", 0),
            "altitude": d.get("pos", {}).get("z", d.get("altitude", 0)),
            "battery": d.get("battery", d.get("bat", 0)),
            "signal": d.get("signal", d.get("sig", 0)),
            "ai_conf": d.get("aiConf", d.get("ai_conf", 0)),
            "alert": d.get("alert", False),
        })

    # Drop invalid frames without id
    mapped = [m for m in mapped if m.get("id")]

    # Normalize metrics: if values are in 0..1 range, scale to 0..100 for frontend
    for m in mapped:
        if isinstance(m.get("signal"), (int, float)) and 0.0 <= m["signal"] <= 1.0:
            m["signal"] = m["signal"] * 100.0
        if isinstance(m.get("ai_conf"), (int, float)) and 0.0 <= m["ai_conf"] <= 1.0:
            m["ai_conf"] = m["ai_conf"] * 100.0
        if isinstance(m.get("battery"), (int, float)) and 0.0 <= m["battery"] <= 1.0:
            m["battery"] = m["battery"] * 100.0

    return mapped

# ── Lifespan: wire up and start all background services ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Instantiate core services
    mcp        = MCPContextEngine()
    boids      = BoidsEngine(n_drones=20, mcp=mcp)
    telegen    = TelemetryGenerator(boids=boids, mcp=mcp)
    fabric     = FabricStream()
    analytics  = SwarmAnalytics()
    retrain    = RetrainingPipeline()
    knowledge  = MissionKnowledge()

    # Attach to app state for route access
    app.state.mcp       = mcp
    app.state.boids     = boids
    app.state.telegen   = telegen
    app.state.fabric    = fabric
    app.state.analytics = analytics
    app.state.retrain   = retrain
    app.state.knowledge = knowledge

    # Seed RAG doctrine knowledge base
    await knowledge.seed()

    # Launch background async loops
    tasks = [
        asyncio.create_task(boids.run()),
        asyncio.create_task(telegen.run()),
        asyncio.create_task(fabric.run()),
    ]
    yield

    # Graceful shutdown
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

# ── App init ──────────────────────────────────────────────
app = FastAPI(
    title    = "RASIP Backend",
    version  = "1.0.0",
    lifespan = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(ws_router)

# ── REST endpoints ────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/mcp-state")
async def mcp_state(request: Request):
    return request.app.state.mcp.snapshot()

@app.get("/hashes")
async def get_hashes():
    return HederaIdentity.ledger()

@app.post("/verify")
async def verify(body: dict):
    return HederaIdentity.verify(body["droneId"], body["payload"])

@app.get("/analytics")
async def analytics(request: Request):
    return {
        "stream":    request.app.state.fabric.summary(),
        "anomalies": request.app.state.analytics.recent_anomalies(),
        "fleet":     request.app.state.analytics.fleet_summary(),
    }

@app.get("/rag/query")
async def rag_query(q: str, request: Request):
    return await request.app.state.knowledge.query(q)

@app.get("/retrain/jobs")
async def retrain_jobs(request: Request):
    return request.app.state.retrain.job_history()

@app.get("/mesh/topology")
async def mesh_topology(request: Request):
    return request.app.state.mcp.snapshot()


@app.post("/ingest")
async def ingest_telemetry(body: dict, request: Request):
    """Accept an array of telemetry frames (JSONL-style) and inject into Fabric and MCP.

    Expected body example:
      {"drones": [ {"droneId":..., "ts":..., "battery":..., "signal":..., "aiConf":..., "pos":{x,y,z}, "formation":..., "alert":...}, ... ] }
    """
    drones = body.get("drones") or body.get("frames") or []
    if not isinstance(drones, list):
        return {"status": "error", "reason": "drones must be a list"}

    # Map and normalize incoming fields using helper
    mapped = map_incoming_drones(drones)
    request.app.state.fabric.ingest(mapped)
    request.app.state.mcp.update(mapped)
    try:
        # Broadcast same payload shape as TelemetryGenerator
        from .websocket_server import broadcast
        await broadcast({"type": "telemetry", "drones": mapped})
    except Exception:
        pass

    return {"status": "ok", "ingested": len(mapped)}
