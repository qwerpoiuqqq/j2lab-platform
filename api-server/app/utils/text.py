"""Shared text utilities."""

from __future__ import annotations

import re


def slugify(name: str, fallback: str = "item") -> str:
    """Generate a URL-safe slug from a name string.

    Replaces whitespace with underscores, strips special characters,
    truncates to 50 chars, and lowercases.
    """
    code = re.sub(r"\s+", "_", name.strip())
    code = re.sub(r"[^a-zA-Z0-9가-힣_]", "", code)
    return code[:50].lower() or fallback
