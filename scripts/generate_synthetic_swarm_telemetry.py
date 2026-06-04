"""Synthetic swarm telemetry generator.

Produces JSON Lines compatible with `fabric/sample_swarm_telemetry.jsonl`.

Usage examples:
  python scripts/generate_synthetic_swarm_telemetry.py --num 5 --duration 60 --hz 1 --out fabric/generated_swarm_telemetry.jsonl
  python scripts/generate_synthetic_swarm_telemetry.py --num 3 --duration 10 --hz 2

Fields per line:
  - droneId: DR-XX
  - ts: Unix epoch (float)
  - battery: percentage
  - signal: 0-1
  - aiConf: 0-1
  - pos: {x,y,z}
  - formation: string
  - alert: bool
"""

import argparse
import json
import math
import random
import time
from typing import Dict, Tuple


FORMATIONS = ["V-WING", "LINE", "CIRCLE", "COLUMN"]


def synth_pos(base: Tuple[float, float, float], t: float, idx: int) -> Dict[str, float]:
    # small coordinated motion: rotate around base point
    angle = (t * 0.2 + idx * 0.5) % (2 * math.pi)
    radius = 2.0 + (idx % 3) * 0.5
    x = base[0] + math.cos(angle) * radius + random.uniform(-0.2, 0.2)
    y = base[1] + math.sin(angle) * radius + random.uniform(-0.2, 0.2)
    z = base[2] + math.sin(t * 0.05 + idx) * 1.0 + random.uniform(-0.1, 0.1)
    return {"x": round(x, 3), "y": round(y, 3), "z": round(z, 3)}


def synth_battery(start: float, elapsed: float, idx: int) -> float:
    # battery drains slowly, with occasional jumps
    drain = elapsed * (0.01 + (idx % 4) * 0.002)
    noise = random.gauss(0, 0.5)
    val = max(0.0, start - drain + noise)
    return round(val, 2)


def synth_signal(elapsed: float) -> float:
    # 0..1 signal with slight variation
    base = 0.9 - min(0.5, elapsed * 0.0005)
    return round(max(0.2, min(1.0, base + random.gauss(0, 0.03))), 2)


def synth_ai_conf() -> float:
    return round(max(0.0, min(1.0, random.gauss(0.85, 0.08))), 2)


def should_alert(elapsed: float, idx: int) -> bool:
    # random alerts more likely as battery gets low or AI conf drops
    if random.random() < 0.005:
        return True
    return False


def generate(num: int, duration: float, hz: float, start_ts: float, out_file=None):
    step = 1.0 / hz
    steps = int(duration * hz)
    # initialize base positions and battery
    bases = [
        (random.uniform(10, 20) + i * 0.5, random.uniform(-6, 0) - i * 0.3, random.uniform(148, 154))
        for i in range(num)
    ]
    batteries = [random.uniform(85, 100) for _ in range(num)]

    f = open(out_file, "w") if out_file else None
    try:
        for s in range(steps):
            t = start_ts + s * step
            elapsed = s * step
            for i in range(num):
                rec = {
                    "droneId": f"DR-{i+1:02d}",
                    "ts": float(t),
                    "battery": synth_battery(batteries[i], elapsed, i),
                    "signal": synth_signal(elapsed),
                    "aiConf": synth_ai_conf(),
                    "pos": synth_pos(bases[i], elapsed, i),
                    "formation": random.choice(FORMATIONS),
                    "alert": should_alert(elapsed, i),
                }
                line = json.dumps(rec)
                if f:
                    f.write(line + "\n")
                else:
                    print(line)
            # sleep to keep realtime if writing to stdout
            if not f:
                time.sleep(step)
    finally:
        if f:
            f.close()


def main():
    p = argparse.ArgumentParser(description="Generate synthetic swarm telemetry JSONL")
    p.add_argument("--num", type=int, default=5, help="number of drones")
    p.add_argument("--duration", type=float, default=30.0, help="duration seconds")
    p.add_argument("--hz", type=float, default=1.0, help="samples per second per drone")
    p.add_argument("--out", type=str, default=None, help="output file (JSONL). If omitted, prints to stdout")
    p.add_argument("--start-ts", type=float, default=None, help="start timestamp (epoch). Defaults to now")
    args = p.parse_args()

    start_ts = args.start_ts if args.start_ts is not None else time.time()
    generate(args.num, args.duration, args.hz, start_ts, out_file=args.out)


if __name__ == '__main__':
    main()
