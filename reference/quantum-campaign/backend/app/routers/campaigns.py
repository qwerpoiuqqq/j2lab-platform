"""캠페인 관리 API 라우터.

Phase 3 - Task 3.6: 수기 캠페인 추가
Phase 3 - Task 3.8: 키워드 추가 및 잔량 확인
Phase 3 - Task 3.9: 캠페인 목록/상세 조회 API
"""

import json
import logging
import math
from datetime import date, datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.services.campaign_extension import extract_place_id
from app.services.keyword_rotation import check_keyword_shortage
from app.utils.encryption import decrypt_password

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def _to_kst(dt: datetime | None) -> datetime | None:
    """UTC datetime을 KST로 변환. naive datetime은 UTC로 간주."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)


router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ============================================================
# Pydantic 스키마
# ============================================================

class ExtensionHistoryItem(BaseModel):
    """연장 이력 항목."""
    round: int
    start_date: str
    end_date: str
    daily_limit: int
    total_limit_added: int = 0
    keywords_added: int = 0
    extended_at: str


class CampaignListItem(BaseModel):
    """캠페인 목록 항목."""

    id: int
    campaign_code: Optional[str] = None
    account_id: Optional[int] = None
    agency_name: Optional[str] = None
    place_name: str
    campaign_type: str
    status: str
    current_conversions: int = 0
    total_limit: Optional[int] = None
    daily_limit: int
    start_date: date
    end_date: date
    days_running: int
    keyword_status: str  # 'normal' | 'warning' | 'critical'
    keyword_remaining: int = 0
    keyword_total: int = 0
    last_keyword_change: Optional[datetime] = None
    registration_step: Optional[str] = None
    registration_message: Optional[str] = None
    extension_history: Optional[List[ExtensionHistoryItem]] = None


class CampaignListResponse(BaseModel):
    """캠페인 목록 응답."""

    campaigns: List[CampaignListItem]
    total: int
    page: int
    pages: int


class KeywordInfo(BaseModel):
    """키워드 풀 항목."""

    id: int
    keyword: str
    is_used: bool
    used_at: Optional[datetime] = None


class CampaignDetailResponse(BaseModel):
    """캠페인 상세 응답."""

    id: int
    campaign_code: Optional[str] = None
    account_id: Optional[int] = None
    agency_name: Optional[str] = None
    place_name: str
    place_url: str
    place_id: Optional[str] = None
    campaign_type: str
    status: str
    start_date: date
    end_date: date
    daily_limit: int
    total_limit: Optional[int] = None
    current_conversions: int = 0
    landmark_name: Optional[str] = None
    step_count: Optional[int] = None
    days_running: int
    keyword_status: str
    keyword_remaining: int
    keyword_total: int
    keyword_used: int
    last_keyword_change: Optional[datetime] = None
    keywords: List[KeywordInfo] = []
    registered_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    extension_history: Optional[List[ExtensionHistoryItem]] = None


class ManualCampaignInput(BaseModel):
    """수기 캠페인 추가 입력."""

    campaign_code: str
    account_id: int
    agency_name: Optional[str] = None
    place_name: str = ""  # 비어있으면 등록 후 URL에서 자동 추출
    place_url: str
    campaign_type: str
    start_date: date
    end_date: date
    daily_limit: int
    keywords: str  # 쉼표 구분

    @field_validator("campaign_type")
    @classmethod
    def validate_campaign_type(cls, v):
        if not v or not v.strip():
            raise ValueError("캠페인 이름이 비어있습니다")
        return v.strip()

    @field_validator("campaign_code")
    @classmethod
    def validate_campaign_code(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("campaign_code는 필수입니다")
        return v

    @field_validator("place_name")
    @classmethod
    def validate_place_name(cls, v):
        return v.strip() if v else ""

    @field_validator("place_url")
    @classmethod
    def validate_place_url(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("place_url은 필수입니다")
        return v

    @field_validator("daily_limit")
    @classmethod
    def validate_daily_limit(cls, v):
        if v <= 0:
            raise ValueError("daily_limit은 1 이상이어야 합니다")
        return v

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("keywords는 필수입니다")
        return v


class ManualCampaignResponse(BaseModel):
    """수기 캠페인 추가 응답."""

    success: bool
    message: str
    campaign_id: Optional[int] = None
    campaign_code: Optional[str] = None
    place_id: Optional[str] = None
    keyword_count: int = 0


class VerifyCampaignResponse(BaseModel):
    """캠페인 존재 확인 응답."""

    campaign_code: str
    exists_in_db: bool
    db_campaign_id: Optional[int] = None
    db_status: Optional[str] = None
    message: str


class AddKeywordsInput(BaseModel):
    """키워드 추가 입력."""

    keywords: str  # 쉼표 구분

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("keywords는 필수입니다")
        return v


class AddKeywordsResponse(BaseModel):
    """키워드 추가 응답."""

    success: bool
    message: str
    added_count: int = 0
    duplicates: List[str] = []
    total_keywords: int = 0
    unused_keywords: int = 0


class KeywordStatusResponse(BaseModel):
    """키워드 잔량 상태 응답."""

    campaign_id: int
    remaining_keywords: int
    remaining_days: int
    status: str  # 'normal' | 'warning' | 'critical'
    message: str


class CampaignSettingsInput(BaseModel):
    """캠페인 설정 수정 입력."""

    campaign_code: Optional[str] = None
    place_name: Optional[str] = None
    agency_name: Optional[str] = None
    daily_limit: Optional[int] = None
    total_limit: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    keywords: Optional[str] = None  # 콤마 구분 키워드 (superap.io 동기화 포함)
    sync_superap: bool = True  # superap.io에 동기화 여부

    @field_validator("daily_limit")
    @classmethod
    def validate_daily_limit(cls, v):
        if v is not None and v <= 0:
            raise ValueError("daily_limit은 1 이상이어야 합니다")
        return v

    @field_validator("total_limit")
    @classmethod
    def validate_total_limit(cls, v):
        if v is not None and v <= 0:
            raise ValueError("total_limit은 1 이상이어야 합니다")
        return v


class CampaignSettingsResponse(BaseModel):
    """캠페인 설정 수정 응답."""

    success: bool
    message: str
    campaign_id: int
    superap_synced: bool = False  # superap.io 동기화 성공 여부


class RegistrationProgressItem(BaseModel):
    """등록 진행 상태 항목."""

    campaign_id: int
    place_name: str
    status: str
    registration_step: Optional[str] = None
    registration_message: Optional[str] = None
    campaign_code: Optional[str] = None


class RegistrationProgressResponse(BaseModel):
    """등록 진행 상태 응답."""

    campaigns: List[RegistrationProgressItem]
    all_completed: bool


# ============================================================
# 헬퍼 함수
# ============================================================

def _compute_keyword_status(unused_count: int, end_date: date, today: date) -> str:
    """키워드 상태 계산."""
    if end_date < today:
        return "normal"
    remaining_days = (end_date - today).days + 1
    if unused_count < remaining_days:
        return "critical"
    if unused_count < remaining_days * 1.5:
        return "warning"
    return "normal"


# ============================================================
# API 엔드포인트
# ============================================================

@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    account_id: Optional[int] = Query(None, description="계정 ID 필터"),
    agency_name: Optional[str] = Query(None, description="대행사명 필터"),
    status: Optional[str] = Query(None, description="상태 필터"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(50, ge=1, le=100, description="페이지당 항목 수"),
    db: Session = Depends(get_db),
):
    """캠페인 목록 조회.

    필터: account_id, agency_name, status
    페이지네이션: page, limit
    """
    query = db.query(Campaign).filter(
        Campaign.status != "pending_extend",
    )

    if account_id is not None:
        query = query.filter(Campaign.account_id == account_id)
    if agency_name:
        query = query.filter(Campaign.agency_name == agency_name)
    if status:
        query = query.filter(Campaign.status == status)

    total = query.count()
    pages = math.ceil(total / limit) if total > 0 else 1

    campaigns = (
        query.order_by(Campaign.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    # 배치 쿼리: 키워드 수
    campaign_ids = [c.id for c in campaigns]
    unused_counts: dict = {}
    total_counts: dict = {}
    if campaign_ids:
        rows = (
            db.query(KeywordPool.campaign_id, func.count(KeywordPool.id))
            .filter(
                KeywordPool.campaign_id.in_(campaign_ids),
                KeywordPool.is_used == False,
            )
            .group_by(KeywordPool.campaign_id)
            .all()
        )
        unused_counts = dict(rows)

        total_rows = (
            db.query(KeywordPool.campaign_id, func.count(KeywordPool.id))
            .filter(KeywordPool.campaign_id.in_(campaign_ids))
            .group_by(KeywordPool.campaign_id)
            .all()
        )
        total_counts = dict(total_rows)

    today = date.today()
    items = []
    for c in campaigns:
        # days_running 계산
        if c.start_date and c.start_date <= today:
            days_running = (today - c.start_date).days + 1
        else:
            days_running = 0

        # keyword_status 계산
        unused = unused_counts.get(c.id, 0)
        total_kw = total_counts.get(c.id, 0)
        kw_status = _compute_keyword_status(unused, c.end_date, today)

        # extension_history 파싱
        ext_history = None
        if c.extension_history:
            try:
                ext_history = json.loads(c.extension_history)
            except (json.JSONDecodeError, TypeError):
                ext_history = None

        items.append(CampaignListItem(
            id=c.id,
            campaign_code=c.campaign_code,
            account_id=c.account_id,
            agency_name=c.agency_name,
            place_name=c.place_name,
            campaign_type=c.campaign_type,
            status=c.status or "pending",
            current_conversions=c.current_conversions or 0,
            total_limit=c.total_limit,
            daily_limit=c.daily_limit,
            start_date=c.start_date,
            end_date=c.end_date,
            days_running=days_running,
            keyword_status=kw_status,
            keyword_remaining=unused,
            keyword_total=total_kw,
            last_keyword_change=_to_kst(c.last_keyword_change),
            registration_step=c.registration_step,
            registration_message=c.registration_message,
            extension_history=ext_history,
        ))

    return CampaignListResponse(
        campaigns=items,
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/registration/progress", response_model=RegistrationProgressResponse)
async def get_registration_progress(
    campaign_ids: str = Query(..., description="쉼표 구분 캠페인 ID 목록"),
    db: Session = Depends(get_db),
):
    """캠페인 등록 진행 상태 조회 (경량 폴링용)."""
    ids = [int(x.strip()) for x in campaign_ids.split(",") if x.strip().isdigit()]

    if not ids:
        return RegistrationProgressResponse(campaigns=[], all_completed=True)

    campaigns = (
        db.query(Campaign)
        .filter(Campaign.id.in_(ids))
        .all()
    )

    items = [
        RegistrationProgressItem(
            campaign_id=c.id,
            place_name=c.place_name,
            status=c.status or "pending",
            registration_step=c.registration_step,
            registration_message=c.registration_message,
            campaign_code=c.campaign_code,
        )
        for c in campaigns
    ]

    all_done = all(
        item.registration_step in ("completed", "failed", None)
        for item in items
    )

    return RegistrationProgressResponse(
        campaigns=items,
        all_completed=all_done,
    )


@router.post("/manual", response_model=ManualCampaignResponse)
async def add_manual_campaign(
    data: ManualCampaignInput,
    db: Session = Depends(get_db),
):
    """수기 캠페인 추가.

    이미 superap.io에서 수동으로 세팅한 캠페인을
    자동 키워드 변경 대상에 포함시키기 위해 DB에 등록합니다.

    처리:
    1. 입력 검증 (계정 존재, 중복 확인)
    2. place_id 자동 추출
    3. Campaign 테이블 저장 (status='active')
    4. KeywordPool 테이블에 키워드 저장
    """
    # 1. 계정 존재 확인
    account = db.query(Account).filter(
        Account.id == data.account_id,
        Account.is_active == True,
    ).first()

    if not account:
        raise HTTPException(
            status_code=404,
            detail=f"활성 계정을 찾을 수 없습니다: ID {data.account_id}",
        )

    # 2. 캠페인 코드 중복 확인
    existing = db.query(Campaign).filter(
        Campaign.campaign_code == data.campaign_code,
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"이미 등록된 캠페인 코드입니다: {data.campaign_code}",
        )

    # 3. 날짜 검증
    if data.end_date < data.start_date:
        raise HTTPException(
            status_code=400,
            detail="종료일은 시작일 이후여야 합니다",
        )

    # 4. place_id 추출
    place_id = extract_place_id(data.place_url)

    # 4-1. 상호명이 비어있으면 place_url에서 자동 추출
    place_name = data.place_name
    if not place_name:
        try:
            from app.services.naver_map import NaverMapScraper
            async with NaverMapScraper(headless=True) as scraper:
                place_info = await scraper.get_place_info(data.place_url)
                if place_info.name:
                    place_name = place_info.name
        except Exception:
            pass  # 추출 실패 시 빈 문자열 유지

    # 5. total_limit 계산
    days = (data.end_date - data.start_date).days + 1
    total_limit = data.daily_limit * days

    # 6. 키워드 파싱
    raw_keywords = [kw.strip() for kw in data.keywords.split(",") if kw.strip()]

    if not raw_keywords:
        raise HTTPException(
            status_code=400,
            detail="유효한 키워드가 없습니다",
        )

    try:
        # 7. Campaign 생성
        campaign = Campaign(
            campaign_code=data.campaign_code,
            account_id=data.account_id,
            agency_name=data.agency_name or account.agency_name,
            place_name=place_name,
            place_url=data.place_url,
            place_id=place_id,
            campaign_type=data.campaign_type,
            start_date=data.start_date,
            end_date=data.end_date,
            daily_limit=data.daily_limit,
            total_limit=total_limit,
            original_keywords=data.keywords,
            status="active",
            registered_at=datetime.now(timezone.utc),
        )
        db.add(campaign)
        db.flush()  # ID 할당을 위해 flush

        # 8. KeywordPool에 키워드 저장
        seen = set()
        added_count = 0
        for keyword in raw_keywords:
            if keyword not in seen:
                kw = KeywordPool(
                    campaign_id=campaign.id,
                    keyword=keyword,
                    is_used=False,
                )
                db.add(kw)
                seen.add(keyword)
                added_count += 1

        db.commit()
        db.refresh(campaign)

        return ManualCampaignResponse(
            success=True,
            message=f"캠페인이 성공적으로 추가되었습니다 (키워드 {added_count}개)",
            campaign_id=campaign.id,
            campaign_code=campaign.campaign_code,
            place_id=place_id,
            keyword_count=added_count,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"캠페인 저장 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/manual/verify/{campaign_code}", response_model=VerifyCampaignResponse)
async def verify_campaign(
    campaign_code: str,
    account_id: Optional[int] = Query(None, description="계정 ID (선택)"),
    db: Session = Depends(get_db),
):
    """캠페인 코드의 DB 등록 여부 확인.

    superap.io에서 해당 캠페인이 이미 시스템에 등록되어 있는지 확인합니다.
    중복 등록 방지를 위한 사전 확인용입니다.
    """
    # DB에서 캠페인 코드 조회
    query = db.query(Campaign).filter(Campaign.campaign_code == campaign_code)

    if account_id is not None:
        query = query.filter(Campaign.account_id == account_id)

    existing = query.first()

    if existing:
        return VerifyCampaignResponse(
            campaign_code=campaign_code,
            exists_in_db=True,
            db_campaign_id=existing.id,
            db_status=existing.status,
            message=f"이미 등록된 캠페인입니다 (상태: {existing.status})",
        )

    return VerifyCampaignResponse(
        campaign_code=campaign_code,
        exists_in_db=False,
        message="등록되지 않은 캠페인 코드입니다. 수기 추가가 가능합니다.",
    )


@router.post("/{campaign_id}/keywords", response_model=AddKeywordsResponse)
async def add_keywords(
    campaign_id: int,
    data: AddKeywordsInput,
    db: Session = Depends(get_db),
):
    """캠페인에 키워드 추가.

    기존 키워드 풀과 중복 체크 후 새 키워드만 추가합니다.
    추가된 키워드는 is_used=False로 설정됩니다.
    """
    # 캠페인 존재 확인
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"캠페인 ID {campaign_id}를 찾을 수 없습니다",
        )

    # 새 키워드 파싱 (쉼표 구분)
    new_keywords = [kw.strip() for kw in data.keywords.split(",") if kw.strip()]
    if not new_keywords:
        raise HTTPException(
            status_code=400,
            detail="유효한 키워드가 없습니다",
        )

    # 기존 키워드 조회 (띄어쓰기 단위로 비교)
    existing_kw_records = db.query(KeywordPool).filter(
        KeywordPool.campaign_id == campaign_id,
    ).all()
    existing_set = {kw.keyword for kw in existing_kw_records}

    # 중복 체크 및 추가
    duplicates = []
    added_count = 0
    for keyword in new_keywords:
        if keyword in existing_set:
            duplicates.append(keyword)
        else:
            kw_record = KeywordPool(
                campaign_id=campaign_id,
                keyword=keyword,
                is_used=False,
            )
            db.add(kw_record)
            existing_set.add(keyword)
            added_count += 1

    if added_count > 0:
        db.commit()

    # 총 키워드 수 및 미사용 키워드 수
    total_keywords = db.query(KeywordPool).filter(
        KeywordPool.campaign_id == campaign_id,
    ).count()
    unused_keywords = db.query(KeywordPool).filter(
        KeywordPool.campaign_id == campaign_id,
        KeywordPool.is_used == False,
    ).count()

    return AddKeywordsResponse(
        success=True,
        message=f"키워드 {added_count}개 추가 완료"
        + (f" (중복 {len(duplicates)}개 제외)" if duplicates else ""),
        added_count=added_count,
        duplicates=duplicates,
        total_keywords=total_keywords,
        unused_keywords=unused_keywords,
    )


@router.get("/{campaign_id}/keywords/status", response_model=KeywordStatusResponse)
async def get_keyword_status(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    """캠페인 키워드 잔량 상태 조회.

    남은 일수 대비 키워드 부족 여부를 확인합니다.
    - critical: 남은 키워드 < 남은 일수
    - warning: 남은 키워드 < 남은 일수 * 1.5
    - normal: 그 외
    """
    # 캠페인 존재 확인
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"캠페인 ID {campaign_id}를 찾을 수 없습니다",
        )

    result = check_keyword_shortage(campaign_id, db)

    return KeywordStatusResponse(
        campaign_id=campaign_id,
        remaining_keywords=result["remaining_keywords"],
        remaining_days=result["remaining_days"],
        status=result["status"],
        message=result["message"],
    )


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign_detail(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    """캠페인 상세 조회.

    캠페인 정보 + 키워드 풀 정보를 반환합니다.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"캠페인 ID {campaign_id}를 찾을 수 없습니다",
        )

    # 키워드 풀 조회
    keywords = (
        db.query(KeywordPool)
        .filter(KeywordPool.campaign_id == campaign_id)
        .order_by(KeywordPool.id)
        .all()
    )
    total_kw = len(keywords)
    used_kw = sum(1 for k in keywords if k.is_used)
    unused_kw = total_kw - used_kw

    today = date.today()
    if campaign.start_date and campaign.start_date <= today:
        days_running = (today - campaign.start_date).days + 1
    else:
        days_running = 0

    kw_status = _compute_keyword_status(unused_kw, campaign.end_date, today)

    keyword_items = [
        KeywordInfo(
            id=k.id,
            keyword=k.keyword,
            is_used=k.is_used,
            used_at=k.used_at,
        )
        for k in keywords
    ]

    # extension_history 파싱
    ext_history = None
    if campaign.extension_history:
        try:
            ext_history = json.loads(campaign.extension_history)
        except (json.JSONDecodeError, TypeError):
            ext_history = None

    return CampaignDetailResponse(
        id=campaign.id,
        campaign_code=campaign.campaign_code,
        account_id=campaign.account_id,
        agency_name=campaign.agency_name,
        place_name=campaign.place_name,
        place_url=campaign.place_url,
        place_id=campaign.place_id,
        campaign_type=campaign.campaign_type,
        status=campaign.status or "pending",
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        daily_limit=campaign.daily_limit,
        total_limit=campaign.total_limit,
        current_conversions=campaign.current_conversions or 0,
        landmark_name=campaign.landmark_name,
        step_count=campaign.step_count,
        days_running=days_running,
        keyword_status=kw_status,
        keyword_remaining=unused_kw,
        keyword_total=total_kw,
        keyword_used=used_kw,
        last_keyword_change=_to_kst(campaign.last_keyword_change),
        keywords=keyword_items,
        registered_at=_to_kst(campaign.registered_at),
        created_at=_to_kst(campaign.created_at),
        extension_history=ext_history,
    )


@router.put("/{campaign_id}/settings", response_model=CampaignSettingsResponse)
async def update_campaign_settings(
    campaign_id: int,
    data: CampaignSettingsInput,
    db: Session = Depends(get_db),
):
    """캠페인 설정 수정 + superap.io 동기화.

    daily_limit, total_limit, end_date, keywords 변경 시
    superap.io에도 자동으로 반영합니다.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"캠페인 ID {campaign_id}를 찾을 수 없습니다",
        )

    # DB 업데이트
    if data.campaign_code is not None:
        campaign.campaign_code = data.campaign_code
    if data.place_name is not None:
        campaign.place_name = data.place_name
    if data.agency_name is not None:
        campaign.agency_name = data.agency_name if data.agency_name else None
    if data.daily_limit is not None:
        campaign.daily_limit = data.daily_limit
    if data.total_limit is not None:
        campaign.total_limit = data.total_limit
    if data.end_date is not None:
        campaign.end_date = data.end_date
    if data.start_date is not None:
        campaign.start_date = data.start_date

    # 키워드 처리
    if data.keywords is not None:
        new_keywords = [kw.strip() for kw in data.keywords.split(",") if kw.strip()]
        if new_keywords:
            existing_kws = {
                kw.keyword
                for kw in db.query(KeywordPool).filter(
                    KeywordPool.campaign_id == campaign.id,
                ).all()
            }
            added = 0
            for keyword in new_keywords:
                if keyword not in existing_kws:
                    db.add(KeywordPool(
                        campaign_id=campaign.id,
                        keyword=keyword,
                        is_used=False,
                    ))
                    existing_kws.add(keyword)
                    added += 1
            campaign.original_keywords = ",".join(existing_kws)

    # 날짜 검증
    if campaign.end_date < campaign.start_date:
        raise HTTPException(
            status_code=400,
            detail="종료일은 시작일 이후여야 합니다",
        )

    # superap.io 동기화: sync_superap이면 현재 DB 값 전체를 항상 전송
    # (DB는 맞지만 superap.io가 틀린 상태일 수 있으므로)
    superap_synced = False
    superap_message = ""
    superap_changes: dict = {}

    if campaign.campaign_code and data.sync_superap:
        if campaign.daily_limit:
            superap_changes["new_daily_limit"] = campaign.daily_limit
        if campaign.total_limit is not None:
            superap_changes["new_total_limit"] = campaign.total_limit
        if campaign.end_date:
            superap_changes["new_end_date"] = campaign.end_date

        # 키워드: 255자 제한 내에서
        all_kws = {
            kw.keyword
            for kw in db.query(KeywordPool).filter(
                KeywordPool.campaign_id == campaign.id,
            ).all()
        }
        if all_kws:
            import random
            kw_list = list(all_kws)
            random.shuffle(kw_list)
            result_kws = []
            current_length = 0
            for kw in kw_list:
                sep = "," if result_kws else ""
                new_len = current_length + len(sep) + len(kw)
                if new_len <= 255:
                    result_kws.append(kw)
                    current_length = new_len
                else:
                    break
            superap_changes["new_keywords"] = ",".join(result_kws)

    if superap_changes and campaign.campaign_code and data.sync_superap:
        account = None
        if campaign.account_id:
            account = db.query(Account).filter(
                Account.id == campaign.account_id,
                Account.is_active == True,
            ).first()

        if not account:
            superap_message = " (superap.io 동기화 실패: 계정 없음)"
        else:
            from app.services.superap import SuperapController
            controller = None
            try:
                controller = SuperapController(headless=True)
                await controller.initialize()

                password = decrypt_password(account.password_encrypted)
                account_key = str(account.id)
                login_ok = await controller.login(
                    account_key, account.user_id, password,
                )
                if not login_ok:
                    superap_message = " (superap.io 동기화 실패: 로그인 실패)"
                else:
                    edit_ok = await controller.edit_campaign(
                        account_id=account_key,
                        campaign_code=campaign.campaign_code,
                        **superap_changes,
                    )
                    if edit_ok:
                        superap_synced = True
                        superap_message = " + superap.io 반영 완료"
                        logger.info(
                            f"[캠페인수정] 캠페인 {campaign.campaign_code} "
                            f"superap.io 동기화 성공: {superap_changes}"
                        )
                    else:
                        superap_message = " (superap.io 동기화 실패: 수정 실패)"
                        logger.warning(
                            f"[캠페인수정] 캠페인 {campaign.campaign_code} "
                            f"superap.io 동기화 실패"
                        )
            except Exception as e:
                superap_message = f" (superap.io 동기화 오류: {str(e)})"
                logger.error(f"[캠페인수정] superap.io 동기화 오류: {e}")
            finally:
                if controller:
                    try:
                        await controller.close()
                    except Exception:
                        pass

    try:
        db.commit()
        return CampaignSettingsResponse(
            success=True,
            message=f"캠페인 설정이 수정되었습니다{superap_message}",
            campaign_id=campaign.id,
            superap_synced=superap_synced,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"설정 수정 중 오류가 발생했습니다: {str(e)}",
        )


@router.post("/{campaign_id}/sync", response_model=CampaignSettingsResponse)
async def sync_campaign_to_superap(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    """현재 DB 값 기준으로 superap.io에 강제 동기화.

    수정 버튼과 별개로, 현재 DB에 저장된 일타수/총타수/종료일/키워드를
    superap.io에 강제로 반영합니다.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"캠페인 ID {campaign_id}를 찾을 수 없습니다")

    if not campaign.campaign_code:
        raise HTTPException(status_code=400, detail="캠페인 코드가 없어 동기화할 수 없습니다")

    account = None
    if campaign.account_id:
        account = db.query(Account).filter(
            Account.id == campaign.account_id,
            Account.is_active == True,
        ).first()

    if not account:
        raise HTTPException(status_code=400, detail="연결된 활성 계정이 없습니다")

    from app.services.superap import SuperapController
    controller = None
    try:
        controller = SuperapController(headless=True)
        await controller.initialize()

        password = decrypt_password(account.password_encrypted)
        account_key = str(account.id)
        login_ok = await controller.login(account_key, account.user_id, password)
        if not login_ok:
            return CampaignSettingsResponse(
                success=False,
                message="superap.io 로그인 실패",
                campaign_id=campaign.id,
                superap_synced=False,
            )

        # 현재 DB 값으로 동기화
        superap_args: dict = {}
        if campaign.daily_limit:
            superap_args["new_daily_limit"] = campaign.daily_limit
        if campaign.total_limit is not None:
            superap_args["new_total_limit"] = campaign.total_limit
        if campaign.end_date:
            superap_args["new_end_date"] = campaign.end_date

        # 키워드: 현재 사용 중이지 않은 키워드 포함
        kw_list = [
            kw.keyword
            for kw in db.query(KeywordPool).filter(
                KeywordPool.campaign_id == campaign.id,
            ).all()
        ]
        if kw_list:
            import random
            random.shuffle(kw_list)
            result_kws = []
            current_length = 0
            for kw in kw_list:
                sep = "," if result_kws else ""
                new_len = current_length + len(sep) + len(kw)
                if new_len <= 255:
                    result_kws.append(kw)
                    current_length = new_len
                else:
                    break
            superap_args["new_keywords"] = ",".join(result_kws)

        if not superap_args:
            return CampaignSettingsResponse(
                success=False,
                message="동기화할 데이터가 없습니다",
                campaign_id=campaign.id,
                superap_synced=False,
            )

        edit_ok = await controller.edit_campaign(
            account_id=account_key,
            campaign_code=campaign.campaign_code,
            **superap_args,
        )

        if edit_ok:
            logger.info(
                f"[동기화] 캠페인 {campaign.campaign_code} superap.io 동기화 성공: {superap_args}"
            )
            return CampaignSettingsResponse(
                success=True,
                message="superap.io 동기화 완료",
                campaign_id=campaign.id,
                superap_synced=True,
            )
        else:
            return CampaignSettingsResponse(
                success=False,
                message="superap.io 수정 실패 (폼 제출 오류)",
                campaign_id=campaign.id,
                superap_synced=False,
            )
    except Exception as e:
        logger.error(f"[동기화] 캠페인 {campaign.campaign_code} 오류: {e}")
        return CampaignSettingsResponse(
            success=False,
            message=f"동기화 중 오류: {str(e)}",
            campaign_id=campaign.id,
            superap_synced=False,
        )
    finally:
        if controller:
            try:
                await controller.close()
            except Exception:
                pass


class CampaignDeleteResponse(BaseModel):
    """캠페인 삭제 응답."""

    success: bool
    message: str


class BatchDeleteRequest(BaseModel):
    """일괄 삭제 요청."""

    campaign_ids: List[int]


class BatchDeleteResponse(BaseModel):
    """일괄 삭제 응답."""

    success: bool
    deleted_count: int
    message: str


class BatchActivateResponse(BaseModel):
    """일괄 활성화 응답."""

    success: bool
    activated_count: int
    message: str


@router.delete("/{campaign_id}", response_model=CampaignDeleteResponse)
async def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    """캠페인 삭제.

    캠페인과 연관된 KeywordPool 데이터를 함께 삭제합니다.
    """
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=f"캠페인 ID {campaign_id}를 찾을 수 없습니다",
        )

    try:
        # KeywordPool 삭제
        db.query(KeywordPool).filter(
            KeywordPool.campaign_id == campaign_id
        ).delete()

        # Campaign 삭제
        db.delete(campaign)
        db.commit()

        return CampaignDeleteResponse(
            success=True,
            message=f"캠페인 '{campaign.place_name}'이(가) 삭제되었습니다",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"캠페인 삭제 중 오류가 발생했습니다: {str(e)}",
        )


@router.post("/batch/delete", response_model=BatchDeleteResponse)
async def batch_delete_campaigns(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
):
    """캠페인 일괄 삭제."""
    if not request.campaign_ids:
        raise HTTPException(
            status_code=400,
            detail="삭제할 캠페인 ID가 없습니다",
        )

    try:
        # KeywordPool 일괄 삭제
        db.query(KeywordPool).filter(
            KeywordPool.campaign_id.in_(request.campaign_ids)
        ).delete(synchronize_session="fetch")

        # Campaign 일괄 삭제
        deleted = db.query(Campaign).filter(
            Campaign.id.in_(request.campaign_ids)
        ).delete(synchronize_session="fetch")

        db.commit()

        return BatchDeleteResponse(
            success=True,
            deleted_count=deleted,
            message=f"{deleted}개 캠페인이 삭제되었습니다",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"캠페인 삭제 중 오류가 발생했습니다: {str(e)}",
        )


@router.post("/batch/activate", response_model=BatchActivateResponse)
async def batch_activate_pending(
    db: Session = Depends(get_db),
):
    """pending 상태 캠페인 일괄 활성화."""
    pending = db.query(Campaign).filter(
        Campaign.status == "pending",
    ).all()

    count = 0
    now = datetime.now(timezone.utc)
    for c in pending:
        c.status = "active"
        if not c.registered_at:
            c.registered_at = now
        count += 1

    db.commit()

    return BatchActivateResponse(
        success=True,
        activated_count=count,
        message=f"{count}개 캠페인이 활성화되었습니다" if count > 0 else "활성화할 대기 캠페인이 없습니다",
    )


class RetryRegistrationRequest(BaseModel):
    """재시도 요청."""

    campaign_ids: List[int]


class RetryRegistrationResponse(BaseModel):
    """재시도 응답."""

    success: bool
    message: str
    retried_count: int
    skipped: List[str] = []


@router.post("/registration/retry", response_model=RetryRegistrationResponse)
async def retry_registration(
    request: RetryRegistrationRequest,
    db: Session = Depends(get_db),
):
    """실패한 캠페인의 자동 등록을 재시도합니다.

    pending/failed 상태인 캠페인을 다시 queued 상태로 되돌리고
    자동 등록 백그라운드 태스크를 트리거합니다.
    """
    if not request.campaign_ids:
        raise HTTPException(
            status_code=400,
            detail="재시도할 캠페인 ID가 없습니다",
        )

    campaigns = (
        db.query(Campaign)
        .filter(Campaign.id.in_(request.campaign_ids))
        .all()
    )

    retried_ids = []
    skipped = []

    for c in campaigns:
        # pending/failed 또는 registration_step이 failed인 캠페인만 재시도
        if c.status == "pending" and c.registration_step == "failed":
            c.registration_step = "queued"
            c.registration_message = "재시도 대기 중..."
            c.updated_at = datetime.now(timezone.utc)
            retried_ids.append(c.id)
        elif c.status == "active":
            skipped.append(f"ID {c.id} ({c.place_name}): 이미 활성 상태")
        else:
            skipped.append(
                f"ID {c.id} ({c.place_name}): "
                f"재시도 불가 (status={c.status}, step={c.registration_step})"
            )

    if retried_ids:
        db.commit()

        from app.services.auto_registration import trigger_auto_registration
        trigger_auto_registration(retried_ids)

    return RetryRegistrationResponse(
        success=len(retried_ids) > 0,
        message=(
            f"{len(retried_ids)}개 캠페인 재시도를 시작합니다"
            if retried_ids
            else "재시도할 캠페인이 없습니다"
        ),
        retried_count=len(retried_ids),
        skipped=skipped,
    )
