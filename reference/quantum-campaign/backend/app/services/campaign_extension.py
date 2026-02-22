"""캠페인 연장 세팅 서비스.

Phase 3 - Task 3.4: 같은 업체의 진행 중인 캠페인이 있고,
총 타수 조건 충족 시 연장 세팅 처리.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.services.superap import SuperapController, SuperapCampaignError


@dataclass
class ExtensionInfo:
    """연장 가능 여부 확인 결과."""

    is_eligible: bool
    existing_campaign_code: Optional[str] = None
    existing_campaign_id: Optional[int] = None
    existing_total_count: Optional[int] = None
    reason: str = ""


@dataclass
class ExtensionResult:
    """연장 실행 결과."""

    success: bool
    campaign_id: Optional[int] = None
    new_total_count: Optional[int] = None
    new_end_date: Optional[date] = None
    added_keywords_count: int = 0
    error_message: Optional[str] = None


def extract_place_id(url: str) -> Optional[str]:
    """플레이스 URL에서 업체 ID를 추출합니다.

    지원 URL 형식:
    - https://m.place.naver.com/restaurant/1724563569
    - https://m.place.naver.com/restaurant/1724563569/home
    - https://place.naver.com/restaurant/1724563569
    - https://map.naver.com/v5/entry/place/1724563569

    Args:
        url: 네이버 플레이스 URL

    Returns:
        숫자로 이루어진 플레이스 ID 또는 None
    """
    if not url:
        return None

    # URL에서 마지막 숫자 시퀀스 추출 (경로 기반)
    # 패턴: /place/숫자 또는 /restaurant/숫자 또는 /cafe/숫자 등
    match = re.search(r'/(?:place|restaurant|cafe|hospital|beauty|accommodation|shopping)/(\d+)', url)
    if match:
        return match.group(1)

    # 대체: URL 경로에서 긴 숫자 시퀀스 추출
    parsed = urlparse(url)
    path_match = re.search(r'/(\d{5,})', parsed.path)
    if path_match:
        return path_match.group(1)

    return None


def check_extension_eligible(
    place_id: str,
    new_total_count: int,
    db: Session,
    new_start_date: Optional[date] = None,
    account_id: Optional[int] = None,
) -> ExtensionInfo:
    """연장 가능 여부를 확인합니다.

    조건:
    1. 같은 place_id + 같은 계정의 캠페인이 있음
    2. 기존 캠페인 마감일이 새 시작일 기준 5일 이내
    3. 기존 캠페인이 활성 상태

    Args:
        place_id: 플레이스 ID
        new_total_count: 새로 추가할 총 타수
        db: DB 세션
        new_start_date: 새 캠페인 시작일
        account_id: 계정 DB ID (다른 계정이면 연장 불가)

    Returns:
        ExtensionInfo: 연장 가능 여부 및 기존 캠페인 정보
    """
    from datetime import timedelta

    if not place_id:
        return ExtensionInfo(
            is_eligible=False,
            reason="플레이스 ID가 없습니다",
        )

    if not new_start_date:
        return ExtensionInfo(
            is_eligible=False,
            reason="시작일 정보가 없습니다",
        )

    # 같은 place_id + 같은 계정 캠페인 중 마감일이 새 시작일 5일 이내인 것 조회
    # (한글 레거시 상태 포함)
    active_statuses = [
        "active", "집행중",
        "daily_exhausted", "일일소진",
        "campaign_exhausted", "전체소진", "캠페인소진",
    ]
    query = db.query(Campaign).filter(
        Campaign.place_id == place_id,
        Campaign.status.in_(active_statuses),
        Campaign.end_date >= new_start_date - timedelta(days=5),
        Campaign.end_date <= new_start_date,
    )
    if account_id is not None:
        query = query.filter(Campaign.account_id == account_id)
    existing_campaign = query.order_by(Campaign.end_date.desc()).first()

    if not existing_campaign:
        return ExtensionInfo(
            is_eligible=False,
            reason="연장 대상 캠페인이 없습니다 (마감일 5일 이내 캠페인 없음)",
        )

    gap_days = (new_start_date - existing_campaign.end_date).days
    return ExtensionInfo(
        is_eligible=True,
        existing_campaign_code=existing_campaign.campaign_code,
        existing_campaign_id=existing_campaign.id,
        existing_total_count=existing_campaign.total_limit or 0,
        reason=f"연장 가능: 기존 마감일({existing_campaign.end_date}) → 새 시작일({new_start_date}), 간격 {gap_days}일",
    )


async def extend_campaign(
    superap_controller: SuperapController,
    db: Session,
    account_id: str,
    existing_campaign_id: int,
    new_total_count: int,
    new_end_date: date,
    new_keywords: List[str],
) -> ExtensionResult:
    """기존 캠페인을 연장합니다.

    처리:
    1. superap.io에서 캠페인 수정 (총 타수, 만료일)
    2. 키워드 풀에 새 키워드 추가
    3. DB 업데이트

    Args:
        superap_controller: SuperapController 인스턴스
        db: DB 세션
        account_id: superap 계정 식별자
        existing_campaign_id: 기존 캠페인 DB ID
        new_total_count: 추가할 총 타수
        new_end_date: 새 만료일
        new_keywords: 추가할 키워드 목록

    Returns:
        ExtensionResult: 연장 실행 결과
    """
    result = ExtensionResult(success=False)

    try:
        # 1. 기존 캠페인 조회
        campaign = db.query(Campaign).filter(Campaign.id == existing_campaign_id).first()
        if not campaign:
            result.error_message = f"캠페인을 찾을 수 없습니다: ID {existing_campaign_id}"
            return result

        if not campaign.campaign_code:
            result.error_message = "캠페인 코드가 없습니다"
            return result

        # 2. 새 총 타수 계산
        existing_total = campaign.total_limit or 0
        updated_total = existing_total + new_total_count

        # 3. superap.io에서 캠페인 수정
        edit_success = await superap_controller.edit_campaign(
            account_id=account_id,
            campaign_code=campaign.campaign_code,
            new_total_limit=updated_total,
            new_end_date=new_end_date,
        )

        if not edit_success:
            result.error_message = "superap.io 캠페인 수정 실패"
            return result

        # 4. DB 업데이트 - 캠페인 정보
        campaign.total_limit = updated_total
        campaign.end_date = new_end_date
        campaign.updated_at = datetime.now(timezone.utc)

        # 5. 키워드 풀에 새 키워드 추가 (중복 제외)
        existing_keywords = {kw.keyword for kw in campaign.keywords}
        added_count = 0

        for keyword in new_keywords:
            keyword = keyword.strip()
            if keyword and keyword not in existing_keywords:
                kw = KeywordPool(
                    campaign_id=campaign.id,
                    keyword=keyword,
                    is_used=False,
                )
                db.add(kw)
                existing_keywords.add(keyword)
                added_count += 1

        # 6. original_keywords 업데이트
        if campaign.original_keywords and new_keywords:
            all_keywords = campaign.original_keywords + ", " + ", ".join(new_keywords)
            campaign.original_keywords = all_keywords
        elif new_keywords:
            campaign.original_keywords = ", ".join(new_keywords)

        db.commit()
        db.refresh(campaign)

        result.success = True
        result.campaign_id = campaign.id
        result.new_total_count = updated_total
        result.new_end_date = new_end_date
        result.added_keywords_count = added_count
        return result

    except SuperapCampaignError as e:
        db.rollback()
        result.error_message = f"Superap 오류: {str(e)}"
        return result
    except Exception as e:
        db.rollback()
        result.error_message = f"예기치 않은 오류: {str(e)}"
        return result
