"""Replay JSONL telemetry into backend via POST /ingest.

Reads a JSONL file (or stdin) and posts frames in realtime according to their timestamps
or in fixed-rate batches. Useful to exercise the backend `FabricStream` and WebSocket
broadcast during development.

Usage:
  python scripts/replay_to_ws.py --file fabric/generated_swarm_telemetry.jsonl --url http://localhost:8000/ingest --realtime

Dependencies: `requests` (pip install requests)
"""

import argparse
import json
import sys
import time
from typing import List

import requests


def read_lines(path: str):
    if path == "-":
        for l in sys.stdin:
            yield l
    else:
        with open(path, "r", encoding="utf-8") as f:
            for l in f:
                yield l


def batch_and_post(frames: List[dict], url: str):
    if not frames:
        return
    payload = {"drones": frames}
    try:
        r = requests.post(url, json=payload, timeout=5.0)
        r.raise_for_status()
    except Exception as e:
        print("POST failed:", e)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", default="-", help="JSONL file path or - for stdin")
    p.add_argument("--url", default="http://localhost:8000/ingest", help="backend ingest URL")
    p.add_argument("--realtime", action="store_true", help="preserve original timestamps (sleep between frames)")
    p.add_argument("--batch-secs", type=float, default=1.0, help="batch interval when not using realtime")
    args = p.parse_args()

    buf = []
    last_ts = None
    for line in read_lines(args.file):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            print("invalid json line, skipping")
            continue

        ts = rec.get("ts") or time.time()
        if args.realtime and last_ts is not None:
            # sleep relative to previous frame timestamp
            delta = max(0.0, ts - last_ts)
            time.sleep(delta)

        buf.append(rec)

        # if not realtime, flush periodically
        if not args.realtime and len(buf) > 0:
            # simple time-based flush
            batch_and_post(buf, args.url)
            buf = []

        if args.realtime:
            batch_and_post([rec], args.url)
            last_ts = ts

    # flush remaining
    if buf:
        batch_and_post(buf, args.url)


if __name__ == '__main__':
    main()
