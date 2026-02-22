"""계정 관리 CRUD API 라우터."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.campaign import Campaign
from app.utils.encryption import encrypt_password


router = APIRouter(prefix="/accounts", tags=["accounts"])


# ============================================================
# Pydantic 스키마
# ============================================================

class AccountListItem(BaseModel):
    """계정 목록 항목."""

    id: int
    user_id: str
    agency_name: Optional[str] = None
    is_active: bool
    campaign_count: int = 0
    created_at: Optional[datetime] = None


class AccountListResponse(BaseModel):
    """계정 목록 응답."""

    accounts: List[AccountListItem]
    total: int


class AccountCreate(BaseModel):
    """계정 생성 요청."""

    user_id: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    agency_name: Optional[str] = Field(None, max_length=100)


class AccountUpdate(BaseModel):
    """계정 수정 요청."""

    user_id: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=1)
    agency_name: Optional[str] = None
    is_active: Optional[bool] = None


class AccountDetailResponse(BaseModel):
    """계정 상세 응답 (비밀번호 미포함)."""

    id: int
    user_id: str
    agency_name: Optional[str] = None
    is_active: bool
    campaign_count: int = 0
    created_at: Optional[datetime] = None


class AccountDeleteResponse(BaseModel):
    """계정 삭제 응답."""

    success: bool
    message: str
    deleted_type: str  # "hard" or "soft"


# ============================================================
# 헬퍼 함수
# ============================================================

def _get_campaign_counts(db: Session) -> dict:
    """계정별 캠페인 수 일괄 조회."""
    return dict(
        db.query(Campaign.account_id, func.count(Campaign.id))
        .group_by(Campaign.account_id)
        .all()
    )


# ============================================================
# API 엔드포인트
# ============================================================

@router.get("", response_model=AccountListResponse)
async def list_accounts(
    is_active: Optional[bool] = Query(None, description="활성 상태 필터"),
    db: Session = Depends(get_db),
):
    """계정 목록 조회."""
    query = db.query(Account)
    if is_active is not None:
        query = query.filter(Account.is_active == is_active)

    accounts = query.order_by(Account.id).all()
    counts = _get_campaign_counts(db)

    items = [
        AccountListItem(
            id=a.id,
            user_id=a.user_id,
            agency_name=a.agency_name,
            is_active=a.is_active if a.is_active is not None else True,
            campaign_count=counts.get(a.id, 0),
            created_at=a.created_at,
        )
        for a in accounts
    ]
    return AccountListResponse(accounts=items, total=len(items))


@router.post("", response_model=AccountDetailResponse, status_code=201)
async def create_account(
    data: AccountCreate,
    db: Session = Depends(get_db),
):
    """계정 생성."""
    existing = db.query(Account).filter(Account.user_id == data.user_id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"'{data.user_id}' 아이디의 계정이 이미 존재합니다",
        )

    account = Account(
        user_id=data.user_id,
        password_encrypted=encrypt_password(data.password),
        agency_name=data.agency_name,
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return AccountDetailResponse(
        id=account.id,
        user_id=account.user_id,
        agency_name=account.agency_name,
        is_active=account.is_active,
        campaign_count=0,
        created_at=account.created_at,
    )


@router.put("/{account_id}", response_model=AccountDetailResponse)
async def update_account(
    account_id: int,
    data: AccountUpdate,
    db: Session = Depends(get_db),
):
    """계정 수정."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다")

    # user_id 변경 시 중복 체크
    if data.user_id is not None and data.user_id != account.user_id:
        existing = db.query(Account).filter(
            Account.user_id == data.user_id,
            Account.id != account_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"'{data.user_id}' 아이디의 계정이 이미 존재합니다",
            )
        account.user_id = data.user_id

    if data.password is not None:
        account.password_encrypted = encrypt_password(data.password)

    if data.agency_name is not None:
        account.agency_name = data.agency_name

    if data.is_active is not None:
        account.is_active = data.is_active

    db.commit()
    db.refresh(account)

    campaign_count = (
        db.query(func.count(Campaign.id))
        .filter(Campaign.account_id == account_id)
        .scalar()
        or 0
    )

    return AccountDetailResponse(
        id=account.id,
        user_id=account.user_id,
        agency_name=account.agency_name,
        is_active=account.is_active,
        campaign_count=campaign_count,
        created_at=account.created_at,
    )


@router.delete("/{account_id}", response_model=AccountDeleteResponse)
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
):
    """계정 삭제.

    - 연결된 캠페인이 없으면: 하드 삭제
    - 연결된 캠페인이 있으면: 소프트 삭제 (is_active=False)
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다")

    campaign_count = (
        db.query(func.count(Campaign.id))
        .filter(Campaign.account_id == account_id)
        .scalar()
        or 0
    )

    if campaign_count == 0:
        db.delete(account)
        db.commit()
        return AccountDeleteResponse(
            success=True,
            message=f"계정 '{account.user_id}'이(가) 삭제되었습니다",
            deleted_type="hard",
        )
    else:
        account.is_active = False
        db.commit()
        return AccountDeleteResponse(
            success=True,
            message=f"계정 '{account.user_id}'에 연결된 캠페인 {campaign_count}개가 있어 비활성화되었습니다",
            deleted_type="soft",
        )
