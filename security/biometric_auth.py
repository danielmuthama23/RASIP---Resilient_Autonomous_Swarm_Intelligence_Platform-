from __future__ import annotations
import hashlib, hmac, os, time, uuid
import numpy as np
from dataclasses import dataclass, field
from typing      import Dict, List, Optional

SECRET       = os.getenv("RASIP_HMAC_SECRET",
                         "change-me-in-production").encode()
EMBED_DIM    = 512    # FaceNet embedding dimension
MATCH_THRESH = 0.75  # cosine similarity threshold for match
LIVENESS_THRESH = 0.80  # liveness score to pass anti-spoofing
SESSION_TTL  = 3600  # session token lifetime (seconds)

@dataclass
class OperatorProfile:
    operator_id:  str
    name:         str
    embedding:    np.ndarray   # 512-d FaceNet embedding
    role:         str = "operator"   # operator | commander | admin
    enrolled_at:  float = field(default_factory=time.time)

@dataclass
class AuthSession:
    session_id:   str
    operator_id:  str
    token:        str
    issued_at:    float
    expires_at:   float
    liveness_ok:  bool
    similarity:   float

class BiometricAuth:
    """
    Operator biometric authentication for RASIP command access.
    Pipeline:
      1. Liveness detection — reject spoofing (printed photo, screen)
      2. FaceNet embedding — 512-d L2-normalised face vector
      3. Cosine similarity — match against enrolled profile
      4. HMAC-SHA256 session token — signed with server secret
    """

    def __init__(self):
        self._profiles: Dict[str, OperatorProfile] = {}
        self._sessions: Dict[str, AuthSession]     = {}

    # ── Enrolment ─────────────────────────────────────────
    def enrol(self, operator_id: str, name: str,
             face_image: np.ndarray,
             role: str = "operator") -> OperatorProfile:
        """Compute FaceNet embedding and store operator profile."""
        embedding = self._embed(face_image)
        profile   = OperatorProfile(
            operator_id = operator_id,
            name        = name,
            embedding   = embedding,
            role        = role,
        )
        self._profiles[operator_id] = profile
        return profile

    # ── Authentication ────────────────────────────────────
    def authenticate(self, face_image: np.ndarray,
                    liveness_score: float) -> Optional[AuthSession]:
        """
        Full auth pipeline: liveness → embedding → match → token.
        Returns AuthSession on success, None on failure.
        """
        # Step 1: anti-spoofing liveness check
        if liveness_score < LIVENESS_THRESH:
            return None

        # Step 2: compute face embedding
        embedding = self._embed(face_image)

        # Step 3: find best matching enrolled profile
        best_profile, best_sim = self._find_match(embedding)
        if best_profile is None:
            return None

        # Step 4: issue HMAC-signed session token
        session = self._issue_token(best_profile, best_sim, liveness_score)
        return session

    # ── FaceNet embedding (mocked) ────────────────────────
    def _embed(self, image: np.ndarray) -> np.ndarray:
        """Compute L2-normalised 512-d FaceNet embedding."""
        try:
            # Real: from facenet_pytorch import InceptionResnetV1
            # model = InceptionResnetV1(pretrained="vggface2").eval()
            # return model(preprocess(image)).detach().numpy()[0]
            vec = np.random.randn(EMBED_DIM).astype(np.float32)
        except Exception:
            vec = np.random.randn(EMBED_DIM).astype(np.float32)
        return vec / (np.linalg.norm(vec) + 1e-8)   # L2 normalise

    # ── Cosine similarity matching ────────────────────────
    def _find_match(self, embedding: np.ndarray
                  ) -> tuple[Optional[OperatorProfile], float]:
        best_sim     = 0.0
        best_profile = None
        for profile in self._profiles.values():
            sim = float(np.dot(embedding, profile.embedding))
            if sim > best_sim:
                best_sim, best_profile = sim, profile
        if best_sim < MATCH_THRESH:
            return None, best_sim
        return best_profile, best_sim

    # ── HMAC-signed session token ─────────────────────────
    def _issue_token(self, profile: OperatorProfile,
                   similarity: float,
                   liveness: float) -> AuthSession:
        now        = time.time()
        session_id = str(uuid.uuid4())
        payload    = f"{session_id}:{profile.operator_id}:{int(now)}"
        token      = hmac.new(SECRET,
                           payload.encode(),
                           hashlib.sha256).hexdigest()
        session = AuthSession(
            session_id  = session_id,
            operator_id = profile.operator_id,
            token       = token,
            issued_at   = now,
            expires_at  = now + SESSION_TTL,
            liveness_ok = liveness >= LIVENESS_THRESH,
            similarity  = similarity,
        )
        self._sessions[session_id] = session
        return session

    # ── Token validation ──────────────────────────────────
    def validate_token(self, session_id: str, token: str) -> bool:
        """Constant-time token validation; checks expiry."""
        sess = self._sessions.get(session_id)
        if not sess: return False
        if time.time() > sess.expires_at: return False
        return hmac.compare_digest(sess.token, token)

    # ── Session management ────────────────────────────────
    def revoke_session(self, session_id: str) -> bool:
        return bool(self._sessions.pop(session_id, None))

    def active_sessions(self) -> List[Dict]:
        now = time.time()
        return [
            {"sessionId": s.session_id,
             "operatorId": s.operator_id,
             "expiresIn": round(s.expires_at - now),
             "similarity": round(s.similarity, 3)}
            for s in self._sessions.values()
            if s.expires_at > now
        ]
