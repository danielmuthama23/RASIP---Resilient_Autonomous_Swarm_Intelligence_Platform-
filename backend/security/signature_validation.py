from __future__ import annotations
import uuid, time, hmac, hashlib, os
from threading  import Lock
from typing     import Dict, Optional
from dataclasses import dataclass

SECRET = os.getenv("RASIP_HMAC_SECRET", "dev-secret-change-me").encode()
TOKEN_TTL = 3600  # seconds — tokens expire after 1 h

@dataclass
class DroneCredential:
    drone_id:   str
    token:      str       # UUID4 token issued at registration
    issued_at:  float
    expires_at: float
    revoked:    bool = False

class SignatureValidator:
    """
    UUID credential registry + HMAC-SHA256 signature checker.
    Each drone registers once; every subsequent command must
    carry its token and a valid HMAC signature of the payload.
    """

    def __init__(self):
        self._registry: Dict[str, DroneCredential] = {}
        self._lock = Lock()

    # ── Registration ──────────────────────────────────────
    def register(self, drone_id: str) -> DroneCredential:
        """Issue a fresh UUID token for a drone."""
        now = time.time()
        cred = DroneCredential(
            drone_id   = drone_id,
            token      = str(uuid.uuid4()),
            issued_at  = now,
            expires_at = now + TOKEN_TTL,
        )
        with self._lock:
            self._registry[drone_id] = cred
        return cred

    # ── Token validation ──────────────────────────────────
    def validate_token(self, drone_id: str, token: str) -> bool:
        """Check token exists, matches, and has not expired or been revoked."""
        with self._lock:
            cred = self._registry.get(drone_id)
        if cred is None:
            return False
        if cred.revoked:
            return False
        if time.time() > cred.expires_at:
            return False
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(cred.token, token)

    # ── HMAC payload signature ────────────────────────────
    def sign_payload(self, payload: str) -> str:
        """Return HMAC-SHA256 hex digest of a payload string."""
        return hmac.new(
            SECRET,
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify_signature(self, payload: str, signature: str) -> bool:
        """Constant-time HMAC verification of an inbound command."""
        expected = self.sign_payload(payload)
        return hmac.compare_digest(expected, signature)

    # ── Revocation ────────────────────────────────────────
    def revoke(self, drone_id: str) -> bool:
        """Mark a drone's credential as revoked (e.g. captured / lost)."""
        with self._lock:
            cred = self._registry.get(drone_id)
            if not cred: return False
            cred.revoked = True
        return True

    def renew(self, drone_id: str) -> Optional[DroneCredential]  :
        """Re-issue a fresh token for a drone (e.g. after re-pairing)."""
        with self._lock:
            if drone_id not in self._registry: return None
        return self.register(drone_id)

    # ── Registry introspection ────────────────────────────
    def list_drones(self) -> Dict[str, Dict]:
        """Return summary of all registered drones."""
        with self._lock:
            return {
                did: {
                    "token_prefix": c.token[:8] + "…",
                    "expires_at":   c.expires_at,
                    "revoked":      c.revoked,
                }
                for did, c in self._registry.items()
            }
