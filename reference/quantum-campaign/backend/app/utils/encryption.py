"""AES 대칭키 암호화/복호화 유틸리티 (Fernet)."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _derive_key(secret: str) -> bytes:
    """SECRET_KEY에서 Fernet 호환 32바이트 키 파생 (PBKDF2-SHA256)."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        b"quantum-campaign-salt",
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(dk)


def _get_fernet() -> Fernet:
    """Fernet 인스턴스 반환."""
    key = _derive_key(settings.SECRET_KEY)
    return Fernet(key)


def encrypt_password(plain_text: str) -> str:
    """비밀번호 암호화. 반환값은 Fernet 토큰 문자열."""
    f = _get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_text: str) -> str:
    """비밀번호 복호화. Fernet 토큰 → 평문 문자열.

    암호화되지 않은 평문(레거시)인 경우 그대로 반환.
    """
    if not encrypted_text:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        # 레거시 평문 비밀번호 호환
        return encrypted_text
