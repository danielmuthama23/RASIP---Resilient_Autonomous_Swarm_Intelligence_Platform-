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
