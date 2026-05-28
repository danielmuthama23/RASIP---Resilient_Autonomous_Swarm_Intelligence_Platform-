from __future__ import annotations
import os, json, base64, hashlib
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2   import PBKDF2HMAC
from cryptography.hazmat.primitives               import hashes
from cryptography.hazmat.backends                import default_backend

KEY_SIZE   = 32    # 256-bit AES key
NONCE_SIZE = 12    # 96-bit nonce (GCM standard)
TAG_SIZE   = 16    # 128-bit authentication tag
KDF_ITER   = 100_000  # PBKDF2 iterations

class AESCipherGCM:
    """
    AES-256-GCM authenticated encryption.
    Improvements over CBC variant used in backend/security/:
      • GCM provides built-in integrity (no separate HMAC)
      • 96-bit random nonce per message (NIST recommended)
      • Additional data (AAD) support for context binding
      • PBKDF2-HMAC-SHA256 key derivation from passphrase
    """

    def __init__(self, key: bytes | None = None):
        if key is None:
            env = os.getenv("RASIP_AES_KEY", "")
            key = bytes.fromhex(env) if env else os.urandom(KEY_SIZE)
        if len(key) != KEY_SIZE:
            raise ValueError(f"Key must be {KEY_SIZE} bytes")
        self._aesgcm = AESGCM(key)
        self._key    = key

    # ── Encrypt ───────────────────────────────────────────
    def encrypt(self, payload: Any,
               aad: bytes | None = None) -> str:
        """
        Serialise payload, encrypt with GCM.
        Returns base64(nonce + ciphertext_with_tag).
        aad = Additional Authenticated Data (not encrypted,
              but integrity-protected — e.g. drone_id).
        """
        plaintext = json.dumps(payload).encode()
        nonce     = os.urandom(NONCE_SIZE)
        ct        = self._aesgcm.encrypt(nonce, plaintext, aad)
        return base64.b64encode(nonce + ct).decode()

    # ── Decrypt ───────────────────────────────────────────
    def decrypt(self, token: str,
               aad: bytes | None = None) -> Any:
        """
        Decode token, split nonce, decrypt + verify tag.
        Raises InvalidTag on tampering or wrong key.
        """
        raw       = base64.b64decode(token)
        nonce     = raw[:NONCE_SIZE]
        ct        = raw[NONCE_SIZE:]
        plaintext = self._aesgcm.decrypt(nonce, ct, aad)
        return json.loads(plaintext)

    # ── PBKDF2 key derivation from passphrase ─────────────
    @classmethod
    def from_passphrase(cls, passphrase: str,
                        salt: bytes | None = None) -> AESCipherGCM:
        """
        Derive a 256-bit key from a human-readable passphrase
        using PBKDF2-HMAC-SHA256. salt should be stored
        alongside the ciphertext for decryption.
        """
        salt = salt or os.urandom(16)
        kdf  = PBKDF2HMAC(
            algorithm  = hashes.SHA256(),
            length     = KEY_SIZE,
            salt       = salt,
            iterations = KDF_ITER,
            backend    = default_backend(),
        )
        key = kdf.derive(passphrase.encode())
        return cls(key)

    # ── Utilities ─────────────────────────────────────────
    @staticmethod
    def generate_key() -> str:
        """Generate a new random 256-bit key as hex."""
        return os.urandom(KEY_SIZE).hex()

    def key_hex(self) -> str:
        return self._key.hex()

    def rotate_key(self) -> str:
        """Generate and apply a fresh key; return hex for storage."""
        new_key     = os.urandom(KEY_SIZE)
        self._aesgcm = AESGCM(new_key)
        self._key    = new_key
        return new_key.hex()
