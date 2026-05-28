from __future__ import annotations
import os, json, base64
from typing import Any

from cryptography.hazmat.primitives.ciphers import (
    Cipher, algorithms, modes
)
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends   import default_backend

KEY_SIZE = 32   # 256-bit AES key
IV_SIZE  = 16   # 128-bit IV (AES block size)

class AESCipher:
    """
    AES-256-CBC with PKCS7 padding.
    A fresh random IV is generated for every encrypt call
    and prepended to the ciphertext so decrypt can recover it.
    """

    def __init__(self, key: bytes | None = None):
        if key is None:
            env = os.getenv("RASIP_AES_KEY", "")
            key = bytes.fromhex(env) if env else os.urandom(KEY_SIZE)
        if len(key) != KEY_SIZE:
            raise ValueError(f"AES key must be {KEY_SIZE} bytes")
        self._key = key

    # ── Encrypt ───────────────────────────────────────────
    def encrypt(self, payload: Any) -> str:
        """
        Serialize payload to JSON, pad, encrypt with a fresh IV.
        Returns base64(IV + ciphertext).
        """
        plaintext = json.dumps(payload).encode()

        # PKCS7 pad to AES block boundary
        padder    = padding.PKCS7(128).padder()
        padded    = padder.update(plaintext) + padder.finalize()

        iv = os.urandom(IV_SIZE)
        cipher = Cipher(
            algorithms.AES(self._key),
            modes.CBC(iv),
            backend=default_backend(),
        )
        enc        = cipher.encryptor()
        ciphertext = enc.update(padded) + enc.finalize()

        return base64.b64encode(iv + ciphertext).decode()

    # ── Decrypt ───────────────────────────────────────────
    def decrypt(self, token: str) -> Any:
        """
        Decode base64, split IV from ciphertext, decrypt,
        unpad, deserialise JSON and return the original payload.
        """
        raw        = base64.b64decode(token)
        iv         = raw[:IV_SIZE]
        ciphertext = raw[IV_SIZE:]

        cipher = Cipher(
            algorithms.AES(self._key),
            modes.CBC(iv),
            backend=default_backend(),
        )
        dec     = cipher.decryptor()
        padded  = dec.update(ciphertext) + dec.finalize()

        # Remove PKCS7 padding
        unpadder  = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

        return json.loads(plaintext)

    # ── Key utilities ─────────────────────────────────────
    @staticmethod
    def generate_key() -> str:
        """Generate a new random 256-bit key as hex string."""
        return os.urandom(KEY_SIZE).hex()

    def key_hex(self) -> str:
        """Return current key as hex (for .env export)."""
        return self._key.hex()
