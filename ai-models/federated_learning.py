from __future__ import annotations
import asyncio, copy, time
import numpy as np
from dataclasses import dataclass, field
from typing      import Any, Dict, List, Optional

# Federated hyperparameters
MIN_CLIENTS    = 5     # minimum drones needed per round
LOCAL_EPOCHS   = 3     # local training epochs per drone
LEARNING_RATE  = 1e-3
ROUND_TIMEOUT  = 60.0 # seconds to wait for client updates

@dataclass
class ClientUpdate:
    drone_id:    str
    weight_delta: Dict[str, np.ndarray]  # layer_name → Δweights
    n_samples:   int                     # local dataset size
    train_loss:  float
    round_id:    int
    submitted_at: float = field(default_factory=time.time)

@dataclass
class FedRound:
    round_id:  int
    global_weights: Dict[str, np.ndarray]
    updates:   List[ClientUpdate] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    aggregated: bool  = False

class FederatedServer:
    """
    Federated Learning coordinator (runs on backend).
    Implements FedAvg: weighted average of client Δweights
    proportional to each client's local dataset size.
    Raw data never leaves the drone — only weight deltas.
    """

    def __init__(self, global_weights: Dict[str, np.ndarray]):
        self._weights  = copy.deepcopy(global_weights)
        self._rounds:  List[FedRound] = []
        self._current: Optional[FedRound] = None
        self._round_id = 0

    # ── Start a new federation round ──────────────────────
    async def start_round(self) -> FedRound:
        """Broadcast current global weights; open update window."""
        self._round_id += 1
        self._current = FedRound(
            round_id       = self._round_id,
            global_weights = copy.deepcopy(self._weights),
        )
        self._rounds.append(self._current)
        return self._current

    # ── Accept update from a client drone ─────────────────
    def submit_update(self, update: ClientUpdate) -> bool:
        """Return False if round already aggregated or wrong round."""
        if not self._current: return False
        if update.round_id != self._current.round_id: return False
        if self._current.aggregated: return False
        self._current.updates.append(update)
        return True

    # ── FedAvg aggregation ────────────────────────────────
    async def aggregate(self) -> Optional[Dict[str, np.ndarray]]:
        """
        Wait until MIN_CLIENTS updates received or ROUND_TIMEOUT.
        Then apply weighted FedAvg to global weights.
        """
        deadline = time.monotonic() + ROUND_TIMEOUT
        while (len(self._current.updates) < MIN_CLIENTS
               and time.monotonic() < deadline):
            await asyncio.sleep(1.0)

        updates = self._current.updates
        if not updates:
            return None

        # Total samples across all participating drones
        total = sum(u.n_samples for u in updates)

        for layer in self._weights:
            # Weighted average of deltas, applied to global weights
            agg_delta = sum(
                (u.n_samples / total) * u.weight_delta.get(layer, 0)
                for u in updates
            )
            self._weights[layer] = self._weights[layer] + agg_delta

        self._current.aggregated = True
        return copy.deepcopy(self._weights)

    # ── Client-side: local training ───────────────────────
    def local_train(
        self,
        drone_id:   str,
        weights:    Dict[str, np.ndarray],
        local_data: List[Dict],
        round_id:   int,
    ) -> ClientUpdate:
        """
        Simulate LOCAL_EPOCHS of SGD on the drone's private data.
        Returns only the weight delta — raw data stays on device.
        """
        local_w = copy.deepcopy(weights)
        loss    = 0.0

        for _ in range(LOCAL_EPOCHS):
            for layer in local_w:
                # Simulate gradient step with Gaussian noise
                grad = np.random.randn(*local_w[layer].shape) * 0.01
                local_w[layer] -= LEARNING_RATE * grad
            loss += np.random.uniform(0.05, 0.3)

        delta = {k: local_w[k] - weights[k] for k in weights}
        return ClientUpdate(
            drone_id     = drone_id,
            weight_delta = delta,
            n_samples    = len(local_data),
            train_loss   = loss / LOCAL_EPOCHS,
            round_id     = round_id,
        )

    # ── Introspection ─────────────────────────────────────
    def round_history(self) -> List[Dict]:
        return [
            {"round_id": r.round_id,
             "n_clients": len(r.updates),
             "aggregated": r.aggregated,
             "started_at": r.started_at}
            for r in self._rounds
        ]
