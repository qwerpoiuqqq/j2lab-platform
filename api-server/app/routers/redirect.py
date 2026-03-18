"""스마트 트래픽/저장하기 리다이렉트 라우터.

공개 엔드포인트 — 인증 불필요.
GET /r/{slug} → 302 리다이렉트 (2단계 가중치 분배).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.campaign import Campaign
from app.services.redirect_service import build_redirect_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["redirect"])


@router.get("/r/{slug}")
async def redirect_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """스마트 트래픽/저장하기 리다이렉트."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.landing_slug == slug,
            Campaign.status.in_(["active", "daily_exhausted", "pending_keyword_change"]),
        )
    )
    campaign = result.scalars().first()

    if not campaign:
        return JSONResponse(status_code=404, content={"detail": "Campaign not found"})

    config = campaign.redirect_config or {}
    if not config:
        return JSONResponse(status_code=404, content={"detail": "No redirect config"})

    redirect_url, channel = build_redirect_url(config)

    logger.info(
        f"[Redirect] slug={slug} campaign={campaign.id} "
        f"place={campaign.place_name} channel={channel}"
    )

    return RedirectResponse(url=redirect_url, status_code=302)
