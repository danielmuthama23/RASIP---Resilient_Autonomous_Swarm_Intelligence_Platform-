import numpy as np
from typing import Dict, List

# Altitude layer shared by all formations
ALT = 55.0
SPACING = 25.0  # metres between slots

class FormationControl:
    """Return a list of 3-D target positions (slots) for each drone."""

    # ── Dispatcher ───────────────────────────────────────
    def slots(self, formation: str, n: int) -> List[np.ndarray]:
        _map: Dict[str, any] = {
            "V-WING":  self._v_wing,
            "CIRCLE":  self._circle,
            "GRID":    self._grid,
            "DIAMOND": self._diamond,
            "SEARCH":  self._search,
        }
        fn = _map.get(formation, self._v_wing)
        return fn(n)

    # ── V-wing ────────────────────────────────────────────
    def _v_wing(self, n: int) -> List[np.ndarray]:
        slots = []
        half  = n // 2
        for i in range(n):
            side   = 1 if i < half else -1
            offset = (i % half + 1) * SPACING
            slots.append(np.array([
                -offset,            # X: trailing behind leader
                side * offset,      # Y: spread left / right
                ALT,
            ]))
        return slots

    # ── Circle ────────────────────────────────────────────
    def _circle(self, n: int) -> List[np.ndarray]:
        r = SPACING * n / (np.pi * 2)
        return [
            np.array([
                r * np.cos(2 * np.pi * i / n),
                r * np.sin(2 * np.pi * i / n),
                ALT,
            ])
            for i in range(n)
        ]

    # ── Grid ─────────────────────────────────────────────
    def _grid(self, n: int) -> List[np.ndarray]:
        cols = int(np.ceil(np.sqrt(n)))
        return [
            np.array([
                (i % cols - cols / 2) * SPACING,
                (i // cols - cols / 2) * SPACING,
                ALT,
            ])
            for i in range(n)
        ]

    # ── Diamond ──────────────────────────────────────────
    def _diamond(self, n: int) -> List[np.ndarray]:
        # Nested diamond rings: 1 leader + rings of 4, 8, 12 …
        slots = [np.zeros(3)]  # leader at origin
        ring, step = 1, 0
        while len(slots) < n:
            per_ring = ring * 4
            for j in range(per_ring):
                angle = 2 * np.pi * j / per_ring
                slots.append(np.array([
                    ring * SPACING * np.cos(angle),
                    ring * SPACING * np.sin(angle),
                    ALT + step * 5,  # stagger altitude per ring
                ]))
                if len(slots) == n: break
            ring += 1; step += 1
        return slots[:n]

    # ── Search (expanding sweep lanes) ───────────────────
    def _search(self, n: int) -> List[np.ndarray]:
        # Parallel lanes spaced by SPACING, drones along each lane
        lanes  = max(2, n // 4)
        per    = int(np.ceil(n / lanes))
        slots  = []
        for lane in range(lanes):
            y = (lane - lanes / 2) * SPACING * 2
            for j in range(per):
                if len(slots) == n: break
                slots.append(np.array([
                    (j - per / 2) * SPACING,
                    y,
                    ALT,
                ]))
        return slots[:n]
