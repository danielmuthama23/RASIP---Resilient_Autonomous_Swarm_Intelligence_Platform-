import json
import os
import tempfile

from scripts import generate_synthetic_swarm_telemetry as gen


def test_generator_writes_expected_lines():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    try:
        # produce 2 drones, 1 second at 1 Hz -> 2 lines
        gen.generate(num=2, duration=1.0, hz=1.0, start_ts=1650000000.0, out_file=path)
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "droneId" in obj
            assert "ts" in obj
            assert isinstance(obj["battery"], (int, float))
            assert 0.0 <= obj["battery"] <= 100.0
            assert "pos" in obj and all(k in obj["pos"] for k in ("x","y","z"))
    finally:
        os.remove(path)
