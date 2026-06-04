**Overview**

This document explains how synthetic telemetry data is generated, how the project processes it, and how to run the generator.

**Data format produced**

Each line is a JSON object (JSONL) with fields compatible with `fabric/sample_swarm_telemetry.jsonl`:
- `droneId` — e.g. `DR-01`
- `ts` — timestamp (epoch float)
- `battery` — percent (0..100)
- `signal` — 0..1
- `aiConf` — 0..1
- `pos` — `{x,y,z}` (meters/local)
- `formation` — string label
- `alert` — boolean

The generator lives at `scripts/generate_synthetic_swarm_telemetry.py`.

**How the project's processing pipeline consumes telemetry**

High-level steps the backend performs (map these to code in `backend/` and `fabric/`):
- Ingest: read JSONL (file or websocket) and parse frames.
- Validate: ensure required fields exist and types are correct.
- Map / Normalize: convert `pos` → `x,y,altitude` and scale values if needed (e.g., `signal` 0..1 → 0..100 for components expecting percent). Example mapping:
  - `droneId` → `id`
  - `pos.x,pos.y,pos.z` → `x,y,altitude`
  - `aiConf` → `ai_conf`
  - `battery` (0..100) → `battery`
- Feature extraction: compute velocity (delta position / dt), pairwise distances, formation one-hot, low-battery flags.
- Fusion & smoothing: feed observations into `backend/sensor_fusion.py` (or `edge/fusion/kalman_filter.py`) to fuse IMU/GPS/SLAM simulated values.
- Broadcast & storage: broadcast via WebSocket (`backend/websocket_server.py`) and optionally persist to
  - a time-series DB or
  - JSONL files under `fabric/` or
  - vector-store used by RAG (`backend/rag/vector_store.py` / `fabric/retriever.py`)

**Why synthetic data is useful here**
- Test real-time ingestion, broadcast, and analytics without hardware.
- Train or validate ML models (`ai-models/`) with labeled scenarios (alerts, formation changes).

**How to run the generator**

Generate 5 drones for 60 seconds at 1 Hz and write to a file:

```bash
python scripts/generate_synthetic_swarm_telemetry.py --num 5 --duration 60 --hz 1 --out fabric/generated_swarm_telemetry.jsonl
```

Stream to stdout (useful for piping into consumers):

```bash
python scripts/generate_synthetic_swarm_telemetry.py --num 3 --duration 30 --hz 2
```

Example: feed generated file into an ingestion consumer (pseudo-command):

```bash
# (Pseudo) consumer that reads JSONL and forwards to backend websocket
cat fabric/generated_swarm_telemetry.jsonl | python path/to/your_consumer.py
```

**Mapping notes for this repo**
- `fabric/sample_swarm_telemetry.jsonl` shows the preferred JSONL shape — the generator follows that.
- `backend/telemetry.py` uses fused `pos` → `x,y,altitude` and includes extra fields (`lat`,`lon`,`history`). A small adapter can convert `pos` ➜ `x,y,altitude` and append lat/lon.

**Next steps / integration ideas**
- Add a small adapter script `scripts/replay_to_ws.py` that reads JSONL and posts frames to the project's WebSocket broadcast to test the full stack.
- Add labeled scenarios (e.g., repeated low-battery alerts) for training `ai-models/retraining.py`.
