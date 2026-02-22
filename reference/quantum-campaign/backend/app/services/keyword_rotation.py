"""키워드 자동 변경 및 관리 로직.

일일소진 또는 23:50 시점에 자동으로 키워드를 변경하는 서비스.
키워드 잔량 확인 및 경고 기능 포함.
"""

import logging
import random
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.models.account import Account
from app.utils.status_map import normalize_status

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


async def rotate_keywords(
    campaign_id: int,
    db: Session,
    superap_controller,
    trigger_type: str = "daily_exhausted",
) -> dict:
    """캠페인 키워드 변경.

    1. 해당 캠페인의 미사용 키워드 조회
    2. 255자 이내로 랜덤 조합
    3. superap.io에서 캠페인 수정 (키워드 필드만)
    4. KeywordPool 업데이트 (is_used = True)
    5. Campaign 업데이트 (last_keyword_change)

    Args:
        campaign_id: 캠페인 DB ID
        db: 데이터베이스 세션
        superap_controller: SuperapController 인스턴스 (로그인 상태)
        trigger_type: "daily_exhausted" 또는 "time_2350"

    Returns:
        dict: success, message, keywords_used, keywords_str, remaining
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return {"success": False, "message": f"캠페인 ID {campaign_id}를 찾을 수 없습니다"}

    if not campaign.campaign_code:
        return {"success": False, "message": "캠페인 코드가 없습니다"}

    # 만료일 지난 캠페인은 키워드 변경 안 함 (KST 기준)
    today_kst = datetime.now(KST).date()
    if campaign.end_date and campaign.end_date < today_kst:
        return {"success": False, "message": "만료된 캠페인은 키워드를 변경하지 않습니다"}

    # 미사용 키워드 조회
    unused_keywords = db.query(KeywordPool).filter(
        KeywordPool.campaign_id == campaign_id,
        KeywordPool.is_used == False,
    ).all()

    recycled = False
    if not unused_keywords:
        # 전체 키워드 풀 확인 (재활용 가능 여부)
        total_pool = db.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign_id,
        ).count()

        if total_pool == 0:
            return {"success": False, "message": "키워드 풀이 비어있습니다", "remaining": 0}

        # 모든 키워드 사용 상태 리셋 (used_at ASC 순으로 재활용)
        logger.info(
            f"캠페인 {campaign.campaign_code}: 미사용 키워드 0개, "
            f"전체 {total_pool}개 키워드 재활용 시작"
        )
        all_keywords = db.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign_id,
        ).all()
        for kw in all_keywords:
            kw.is_used = False
            kw.used_at = None
        db.flush()
        recycled = True

        # 리셋 후 다시 미사용 키워드 조회
        unused_keywords = db.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign_id,
            KeywordPool.is_used == False,
        ).all()

        if not unused_keywords:
            return {"success": False, "message": "키워드 재활용 후에도 사용 가능한 키워드가 없습니다", "remaining": 0}

    # 255자 이내로 랜덤 조합
    random.shuffle(unused_keywords)
    selected_keywords = []
    current_length = 0

    for kw_pool in unused_keywords:
        keyword = kw_pool.keyword.strip()
        if not keyword:
            continue
        separator_len = 1 if selected_keywords else 0  # 쉼표
        new_length = current_length + separator_len + len(keyword)
        if new_length <= 255:
            selected_keywords.append(kw_pool)
            current_length = new_length
        # 255자 초과해도 다음 키워드가 더 짧을 수 있으므로 계속 시도
        # (단, 이미 충분히 선택했으면 중단)

    if not selected_keywords:
        return {"success": False, "message": "선택할 수 있는 키워드가 없습니다"}

    # 키워드 문자열 생성 (쉼표 구분, 공백 없음)
    keywords_str = ",".join([kw.keyword.strip() for kw in selected_keywords])

    # 계정 조회
    account = db.query(Account).filter(Account.id == campaign.account_id).first()
    if not account:
        return {"success": False, "message": "계정을 찾을 수 없습니다"}

    account_key = str(account.id)

    # superap.io에서 캠페인 키워드 수정
    try:
        edit_success = await superap_controller.edit_campaign_keywords(
            account_id=account_key,
            campaign_code=campaign.campaign_code,
            new_keywords=keywords_str,
        )
    except Exception as e:
        logger.error(f"캠페인 {campaign.campaign_code} superap 키워드 수정 실패: {e}")
        return {"success": False, "message": f"superap 수정 실패: {str(e)}"}

    if not edit_success:
        return {"success": False, "message": "superap 키워드 수정 실패"}

    # KeywordPool 업데이트 (사용 처리)
    now = datetime.now(timezone.utc)
    for kw_pool in selected_keywords:
        kw_pool.is_used = True
        kw_pool.used_at = now

    # Campaign last_keyword_change 업데이트 (항상 UTC로 저장)
    if trigger_type == "time_2350":
        # 23:50 조건: KST 23:50:00을 UTC로 변환하여 저장 (날짜 밀림 방지)
        today_kst = datetime.now(KST)
        fixed_time = today_kst.replace(hour=23, minute=50, second=0, microsecond=0)
        campaign.last_keyword_change = fixed_time.astimezone(timezone.utc)
    else:
        campaign.last_keyword_change = now

    db.commit()

    # 남은 키워드 수 조회
    remaining = db.query(KeywordPool).filter(
        KeywordPool.campaign_id == campaign_id,
        KeywordPool.is_used == False,
    ).count()

    recycle_msg = " (재활용)" if recycled else ""
    logger.info(
        f"캠페인 {campaign.campaign_code} 키워드 변경 완료{recycle_msg}: "
        f"{len(selected_keywords)}개 사용, {remaining}개 남음 (trigger: {trigger_type})"
    )

    return {
        "success": True,
        "message": f"키워드 {len(selected_keywords)}개 변경 완료{recycle_msg}",
        "keywords_used": len(selected_keywords),
        "keywords_str": keywords_str,
        "remaining": remaining,
        "recycled": recycled,
    }


async def sync_campaign_status(
    campaign_id: int,
    db: Session,
    superap_controller,
) -> dict:
    """superap.io에서 캠페인 상태 조회 및 DB 업데이트.

    Args:
        campaign_id: 캠페인 DB ID
        db: 데이터베이스 세션
        superap_controller: SuperapController 인스턴스 (로그인 상태)

    Returns:
        dict: success, status, previous_status
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return {"success": False, "message": f"캠페인 ID {campaign_id}를 찾을 수 없습니다"}

    if not campaign.campaign_code:
        return {"success": False, "message": "캠페인 코드가 없습니다"}

    account = db.query(Account).filter(Account.id == campaign.account_id).first()
    if not account:
        return {"success": False, "message": "계정을 찾을 수 없습니다"}

    account_key = str(account.id)

    try:
        status = await superap_controller.get_campaign_status(
            account_id=account_key,
            campaign_code=campaign.campaign_code,
        )
    except Exception as e:
        logger.error(f"캠페인 {campaign.campaign_code} 상태 조회 실패: {e}")
        return {"success": False, "message": f"상태 조회 실패: {str(e)}"}

    if status is None:
        return {"success": False, "message": "상태를 확인할 수 없습니다"}

    previous_status = campaign.status
    normalized = normalize_status(status)
    campaign.status = normalized
    db.commit()

    logger.info(
        f"캠페인 {campaign.campaign_code} 상태 동기화: {previous_status} → {normalized} (원본: {status})"
    )

    return {
        "success": True,
        "status": normalized,
        "previous_status": previous_status,
    }


async def sync_all_campaign_statuses(
    db: Session,
    superap_controller,
    account_id: int,
) -> dict:
    """특정 계정의 모든 캠페인 상태 + 전환수를 동기화.

    각 캠페인에 대해 get_campaign_status_with_conversions()를 호출하여
    상태와 전환수를 함께 가져옵니다.

    Args:
        db: 데이터베이스 세션
        superap_controller: SuperapController 인스턴스 (로그인 상태)
        account_id: 계정 DB ID

    Returns:
        dict: success, synced_count, statuses
    """
    account_key = str(account_id)

    # 이 계정의 캠페인 코드 목록 조회 (검색 대상)
    campaigns = db.query(Campaign).filter(
        Campaign.account_id == account_id,
        Campaign.campaign_code.isnot(None),
    ).all()

    campaign_codes = list(set(c.campaign_code for c in campaigns if c.campaign_code))

    # 상태 + 전환수 조회 (개별 검색)
    campaign_info: dict = {}  # {campaign_code: {"status": str, "current_count": int, "total_count": int}}
    for code in campaign_codes:
        try:
            info = await superap_controller.get_campaign_status_with_conversions(
                account_key, code,
            )
            if info:
                campaign_info[code] = info
                logger.info(f"캠페인 {code} 상태+전환: {info}")
            else:
                logger.warning(f"캠페인 {code} 상태+전환 확인 불가")
        except Exception as e:
            logger.warning(f"캠페인 {code} 상태+전환 조회 오류: {e}")

    if not campaign_info:
        return {"success": True, "synced_count": 0, "statuses": {}}

    # DB 업데이트 (한글→영문 정규화 + 전환수)
    synced_count = 0
    statuses: dict = {}
    for campaign in campaigns:
        if campaign.campaign_code in campaign_info:
            info = campaign_info[campaign.campaign_code]
            raw_status = info.get("status", "")
            new_status = normalize_status(raw_status) if raw_status else campaign.status
            statuses[campaign.campaign_code] = new_status

            changed = False
            if raw_status and campaign.status != new_status:
                logger.info(
                    f"캠페인 {campaign.campaign_code} 상태: {campaign.status} → {new_status} (원본: {raw_status})"
                )
                campaign.status = new_status
                changed = True

            # 전환수 업데이트
            current_count = info.get("current_count", 0)
            if current_count is not None and campaign.current_conversions != current_count:
                logger.info(
                    f"캠페인 {campaign.campaign_code} 전환수: {campaign.current_conversions} → {current_count}"
                )
                campaign.current_conversions = current_count
                changed = True

            if changed:
                synced_count += 1

    if synced_count > 0:
        db.commit()

    return {
        "success": True,
        "synced_count": synced_count,
        "statuses": statuses,
    }


def should_rotate_at_2350(campaign: Campaign) -> bool:
    """23:50 조건에서 이 캠페인을 변경해야 하는지 확인.

    오늘 23:50:00 KST 이후로 이미 변경된 경우 건너뛰기.

    Args:
        campaign: 캠페인 모델 인스턴스

    Returns:
        True이면 변경 필요
    """
    if campaign.last_keyword_change is None:
        return True

    today_kst = datetime.now(KST)
    threshold = today_kst.replace(hour=23, minute=50, second=0, microsecond=0)

    last_change = campaign.last_keyword_change
    # timezone-naive datetime을 UTC로 간주 (DB에 UTC로 저장됨)
    if last_change.tzinfo is None:
        last_change = last_change.replace(tzinfo=timezone.utc)

    return last_change < threshold


def check_keyword_shortage(campaign_id: int, db: Session) -> dict:
    """남은 일수 대비 키워드 부족 여부 체크.

    Args:
        campaign_id: 캠페인 DB ID
        db: 데이터베이스 세션

    Returns:
        dict:
            - remaining_keywords: int (미사용 키워드 수)
            - remaining_days: int (남은 일수)
            - status: 'normal' | 'warning' | 'critical'
            - message: str
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return {
            "remaining_keywords": 0,
            "remaining_days": 0,
            "status": "critical",
            "message": f"캠페인 ID {campaign_id}를 찾을 수 없습니다",
        }

    # 미사용 키워드 수
    remaining_keywords = db.query(KeywordPool).filter(
        KeywordPool.campaign_id == campaign_id,
        KeywordPool.is_used == False,
    ).count()

    # 전체 키워드 수 (재활용 판단용)
    total_keywords = db.query(KeywordPool).filter(
        KeywordPool.campaign_id == campaign_id,
    ).count()

    # 남은 일수 계산 (오늘 포함, KST 기준)
    today = datetime.now(KST).date()
    if not campaign.end_date or campaign.end_date < today:
        remaining_days = 0
    else:
        remaining_days = (campaign.end_date - today).days + 1

    # 상태 판별
    if remaining_days == 0:
        status = "normal"
        message = "캠페인이 종료되었습니다"
    elif remaining_keywords == 0 and total_keywords > 0:
        # 미사용 0이지만 전체 풀은 있음 → 재활용 예정
        status = "warning"
        message = f"키워드 재활용 예정: 전체 {total_keywords}개 (다음 변경 시 리셋)"
    elif remaining_keywords < remaining_days:
        status = "critical"
        message = f"키워드 부족: {remaining_keywords}개 남음 / {remaining_days}일 남음"
    elif remaining_keywords < remaining_days * 1.5:
        status = "warning"
        message = f"키워드 주의: {remaining_keywords}개 남음 / {remaining_days}일 남음"
    else:
        status = "normal"
        message = f"키워드 충분: {remaining_keywords}개 남음 / {remaining_days}일 남음"

    return {
        "remaining_keywords": remaining_keywords,
        "remaining_days": remaining_days,
        "status": status,
        "message": message,
    }
