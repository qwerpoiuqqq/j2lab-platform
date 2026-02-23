"""Campaign status Korean <-> English mapping.

Normalizes Korean status strings from superap.io into internal English codes,
and provides display labels for the frontend.
Ported from reference/quantum-campaign/backend/app/utils/status_map.py.
"""

from __future__ import annotations

# superap.io Korean -> internal English code
SUPERAP_TO_INTERNAL: dict[str, str] = {
    "진행중": "active",
    "집행중": "active",
    "일일소진": "daily_exhausted",
    "캠페인소진": "campaign_exhausted",
    "전체소진": "campaign_exhausted",
    "중단": "deactivated",
    "일시정지": "paused",
    "대기중": "pending",
    "종료": "completed",
}

# Internal English code -> frontend display label
INTERNAL_TO_KOREAN: dict[str, str] = {
    "active": "진행중",
    "daily_exhausted": "일일소진",
    "campaign_exhausted": "전체소진",
    "deactivated": "중단",
    "paused": "일시정지",
    "pending": "대기중",
    "pending_extend": "연장 대기",
    "completed": "종료",
}


def normalize_status(status: str) -> str:
    """Normalize superap.io Korean status or legacy value to internal English code.

    Already-English codes are returned as-is.
    Unknown values are returned as-is.
    """
    if not status:
        return "pending"
    if status in SUPERAP_TO_INTERNAL:
        return SUPERAP_TO_INTERNAL[status]
    if status in INTERNAL_TO_KOREAN:
        return status
    return status


def to_display_label(status: str) -> str:
    """Convert internal English code to Korean display label.

    Unknown values are returned as-is.
    """
    if not status:
        return "대기중"
    return INTERNAL_TO_KOREAN.get(status, status)
