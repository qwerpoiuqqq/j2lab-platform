"""AES symmetric encryption/decryption utility (Fernet).

Uses the same SECRET_KEY as api-server to decrypt superap account passwords.
Ported from reference/quantum-campaign/backend/app/utils/encryption.py.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _derive_key(secret: str) -> bytes:
    """Derive a Fernet-compatible 32-byte key from SECRET_KEY (PBKDF2-SHA256)."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        b"quantum-campaign-salt",
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(dk)


def _get_fernet() -> Fernet:
    """Return a Fernet instance."""
    key = _derive_key(settings.SECRET_KEY)
    return Fernet(key)


def encrypt_password(plain_text: str) -> str:
    """Encrypt password. Returns Fernet token string."""
    f = _get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_text: str) -> str:
    """Decrypt password. Fernet token -> plain text string.

    Returns plaintext as-is if it is not a valid Fernet token (legacy compat).
    """
    if not encrypted_text:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        # Legacy plaintext password compatibility
        return encrypted_text
