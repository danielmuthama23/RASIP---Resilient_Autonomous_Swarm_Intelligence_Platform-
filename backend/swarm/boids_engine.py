import asyncio
import numpy as np
from dataclasses import dataclass, field
from typing      import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..mcp_context import MCPContextEngine

from .formation_control  import FormationControl
from .collision_avoidance import CollisionAvoidance
from .swarm_consensus     import SwarmConsensus

TICK_HZ      = 30    # simulation ticks per second
WORLD_SIZE   = 500   # bounding box (–250 … +250 m)

# ── Boid weights ─────────────────────────────────────────
W_SEP  = 1.5   # separation  — avoid crowding neighbours
W_ALI  = 1.0   # alignment   — steer toward avg heading
W_COH  = 1.0   # cohesion    — steer toward avg position
W_FORM = 2.0   # formation   — pull toward assigned slot

SEP_RADIUS = 20   # m — start separating if closer than this
VIEW_RADIUS = 80  # m — perception range
MAX_SPEED   = 15  # m/s

@dataclass
class Boid:
    id:       str
    pos:      np.ndarray = field(default_factory=lambda: np.zeros(3))
    vel:      np.ndarray = field(default_factory=lambda: np.zeros(3))
    battery:  float = 100.0
    signal:   float = 100.0
    ai_conf:  float = 0.9
    alert:    bool  = False
    history:  list  = field(default_factory=list)
    slam_x:   float = 0.0
    slam_y:   float = 0.0
    slam_z:   float = 50.0

    # convenience aliases used by navigator / sensor_fusion
    @property
    def x(self): return float(self.pos[0])
    @property
    def y(self): return float(self.pos[1])
    @property
    def altitude(self): return float(self.pos[2])
    @property
    def heading(self):
        return float(np.arctan2(self.vel[1], self.vel[0]))

class BoidsEngine:
    def __init__(self, n_drones: int, mcp: 'MCPContextEngine'):
        self.mcp       = mcp
        self.formation = FormationControl()
        self.avoidance = CollisionAvoidance()
        self.consensus = SwarmConsensus(mcp)
        self.drones: List[Boid] = [
            Boid(
                id  = f"DR-{i+1:02d}",
                pos = np.array([
                    np.random.uniform(-100, 100),
                    np.random.uniform(-100, 100),
                    np.random.uniform( 40,  80),
                ]),
                vel = np.random.randn(3) * 2,
            )
            for i in range(n_drones)
        ]

    # ── Main tick loop ───────────────────────────────────
    async def run(self):
        dt = 1 / TICK_HZ
        while True:
            self._tick(dt)
            await asyncio.sleep(dt)

    def _tick(self, dt: float):
        positions = np.array([b.pos for b in self.drones])
        velocities = np.array([b.vel for b in self.drones])
        formation_type = self.mcp._mission.get("formation", "V-WING")
        slots = self.formation.slots(formation_type, len(self.drones))

        for i, boid in enumerate(self.drones):
            acc = self._accelerate(i, boid, positions, velocities, slots)
            boid.vel = np.clip(boid.vel + acc * dt, -MAX_SPEED, MAX_SPEED)
            boid.pos = boid.pos + boid.vel * dt

            # Wrap at world boundary
            boid.pos = ((boid.pos + WORLD_SIZE/2) % WORLD_SIZE) - WORLD_SIZE/2
            boid.pos[2] = np.clip(boid.pos[2], 10, 120)  # altitude bounds

    def _accelerate(self, i, boid, positions, velocities, slots) -> np.ndarray:
        sep  = self._separation(i, boid, positions)
        ali  = self._alignment (i, boid, positions, velocities)
        coh  = self._cohesion  (i, boid, positions)
        form = self._formation_pull(boid, slots[i])
        avoid = self.avoidance.steer(boid)

        return (W_SEP*sep + W_ALI*ali + W_COH*coh
                + W_FORM*form + avoid)

    # ── Reynolds rules ───────────────────────────────────
    def _neighbours(self, i, positions):
        diffs = positions - positions[i]
        dists = np.linalg.norm(diffs, axis=1)
        return np.where((dists > 0) & (dists < VIEW_RADIUS))[0]

    def _separation(self, i, boid, positions):
        close = [j for j in self._neighbours(i, positions)
                 if np.linalg.norm(positions[j] - boid.pos) < SEP_RADIUS]
        if not close: return np.zeros(3)
        steer = -np.mean(positions[close] - boid.pos, axis=0)
        return steer / (np.linalg.norm(steer) + 1e-8)

    def _alignment(self, i, boid, positions, velocities):
        nbrs = self._neighbours(i, positions)
        if not nbrs.size: return np.zeros(3)
        avg = np.mean(velocities[nbrs], axis=0)
        return avg / (np.linalg.norm(avg) + 1e-8)

    def _cohesion(self, i, boid, positions):
        nbrs = self._neighbours(i, positions)
        if not nbrs.size: return np.zeros(3)
        centre = np.mean(positions[nbrs], axis=0)
        delta  = centre - boid.pos
        return delta / (np.linalg.norm(delta) + 1e-8)

    def _formation_pull(self, boid, slot):
        delta = slot - boid.pos
        return delta / (np.linalg.norm(delta) + 1e-8)

    # ── ATC command handler (called from WebSocket) ───────
    async def handle_command(self, msg: dict):
        cmd = msg.get("cmd", "").upper()
        if cmd in ("V-WING","CIRCLE","GRID","DIAMOND","SEARCH"):
            self.mcp._mission["formation"] = cmd
            await self.consensus.propose("formation", cmd)
