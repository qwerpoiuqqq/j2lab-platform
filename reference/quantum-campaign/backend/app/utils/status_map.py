"""캠페인 상태 한글↔영문 매핑.

superap.io에서 반환하는 한글 상태를 DB 내부 영문 코드로 통일하고,
프론트엔드 표시용 한글 라벨로 변환하는 유틸리티.
"""

# superap.io 한글 → DB 내부 영문 코드
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

# DB 내부 영문 코드 → 프론트 표시용 한글 라벨
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
    """superap.io 한글 상태 또는 레거시 값을 내부 영문 코드로 정규화.

    이미 영문 코드인 경우 그대로 반환합니다.
    매핑에 없는 값은 원본을 그대로 반환합니다.
    """
    if not status:
        return "pending"
    # 한글 → 영문 매핑에 있으면 변환
    if status in SUPERAP_TO_INTERNAL:
        return SUPERAP_TO_INTERNAL[status]
    # 이미 영문 코드이면 그대로
    if status in INTERNAL_TO_KOREAN:
        return status
    # 매핑에 없는 값은 그대로 반환
    return status


def to_display_label(status: str) -> str:
    """내부 영문 코드를 프론트 표시용 한글 라벨로 변환.

    매핑에 없는 값은 원본을 그대로 반환합니다.
    """
    if not status:
        return "대기중"
    return INTERNAL_TO_KOREAN.get(status, status)
