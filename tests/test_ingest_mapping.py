from backend.main import map_incoming_drones


def test_map_incoming_scaling():
    raw = [
        {"droneId": "DR-01", "pos": {"x": 1, "y": 2, "z": 3}, "battery": 0.5, "signal": 0.8, "aiConf": 0.9, "alert": False},
        {"droneId": "DR-02", "pos": {"x": 4, "y": 5, "z": 6}, "battery": 75, "signal": 85, "aiConf": 95, "alert": True},
    ]
    mapped = map_incoming_drones(raw)
    assert len(mapped) == 2
    m1, m2 = mapped
    assert m1["battery"] == 50.0
    assert m1["signal"] == 80.0
    assert m1["ai_conf"] == 90.0
    assert m2["battery"] == 75
    assert m2["signal"] == 85
    assert m2["ai_conf"] == 95
