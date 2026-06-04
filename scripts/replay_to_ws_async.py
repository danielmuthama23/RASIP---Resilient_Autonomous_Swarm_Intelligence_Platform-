"""Async replay JSONL telemetry into backend via POST /ingest using httpx.

Reads a JSONL file (or stdin) and posts frames in realtime according to their timestamps
or in fixed-rate batches. Uses `httpx` for async HTTP to improve throughput.

Usage:
  python scripts/replay_to_ws_async.py --file fabric/generated_swarm_telemetry.jsonl --url http://localhost:8000/ingest --realtime

Dependencies: `httpx` (pip install httpx)
"""

import argparse
import asyncio
import json
import sys
import time
from typing import List

import httpx


async def read_lines(path: str):
    if path == "-":
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        while True:
            line = await reader.readline()
            if not line:
                break
            yield line.decode()
    else:
        # synchronous file read, but it's fine for initial load
        with open(path, "r", encoding="utf-8") as f:
            for l in f:
                yield l


async def post_batch(client: httpx.AsyncClient, frames: List[dict], url: str):
    if not frames:
        return
    payload = {"drones": frames}
    try:
        r = await client.post(url, json=payload, timeout=10.0)
        r.raise_for_status()
    except Exception as e:
        print("POST failed:", e)


async def replay(path: str, url: str, realtime: bool, batch_secs: float):
    async with httpx.AsyncClient() as client:
        buf: List[dict] = []
        last_ts = None
        last_flush = time.monotonic()

        async for line in read_lines(path):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                print("invalid json line, skipping")
                continue

            ts = rec.get("ts") or time.time()
            if realtime and last_ts is not None:
                delta = max(0.0, ts - last_ts)
                await asyncio.sleep(delta)

            if realtime:
                await post_batch(client, [rec], url)
                last_ts = ts
                continue

            # batching mode: accumulate and flush periodically
            buf.append(rec)
            now = time.monotonic()
            if now - last_flush >= batch_secs:
                await post_batch(client, buf, url)
                buf = []
                last_flush = now

        # final flush
        if buf:
            await post_batch(client, buf, url)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", default="-", help="JSONL file path or - for stdin")
    p.add_argument("--url", default="http://localhost:8000/ingest", help="backend ingest URL")
    p.add_argument("--realtime", action="store_true", help="preserve original timestamps (sleep between frames)")
    p.add_argument("--batch-secs", type=float, default=1.0, help="batch interval when not using realtime")
    args = p.parse_args()

    asyncio.run(replay(args.file, args.url, args.realtime, args.batch_secs))


if __name__ == '__main__':
    main()
