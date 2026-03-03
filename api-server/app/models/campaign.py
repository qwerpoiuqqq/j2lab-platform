"""Campaign model - Table 11: campaigns.

Campaign entity with full lifecycle tracking.
Source: reference/quantum-campaign/backend/app/models/campaign.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.campaign_keyword_pool import CampaignKeywordPool


class CampaignStatus(str, Enum):
    """Campaign lifecycle status."""

    PENDING = "pending"
    QUEUED = "queued"
    REGISTERING = "registering"
    ACTIVE = "active"
    DAILY_EXHAUSTED = "daily_exhausted"
    CAMPAIGN_EXHAUSTED = "campaign_exhausted"
    PAUSED = "paused"
    DEACTIVATED = "deactivated"
    PENDING_EXTEND = "pending_extend"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class Campaign(Base):
    """Campaign entity with superap registration tracking."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    campaign_code: Mapped[Optional[str]] = mapped_column(String(20))
    superap_account_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("superap_accounts.id"),
    )
    order_item_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("order_items.id", ondelete="SET NULL"),
    )
    place_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("places.id"),
    )
    extraction_job_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("extraction_jobs.id", ondelete="SET NULL"),
    )

    # === Campaign Basic Info ===
    agency_name: Mapped[Optional[str]] = mapped_column(String(100))
    place_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default=""
    )
    place_url: Mapped[str] = mapped_column(Text, nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # === Duration/Limits ===
    registered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    total_limit: Mapped[Optional[int]] = mapped_column(Integer)
    current_conversions: Mapped[int] = mapped_column(Integer, default=0)

    # === Module Results ===
    landmark_name: Mapped[Optional[str]] = mapped_column(String(200))
    step_count: Mapped[Optional[int]] = mapped_column(Integer)
    module_context: Mapped[Optional[Any]] = mapped_column(JSON)

    # === Keywords ===
    original_keywords: Mapped[Optional[str]] = mapped_column(Text)

    # === Status ===
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CampaignStatus.PENDING.value,
    )
    registration_step: Mapped[Optional[str]] = mapped_column(String(30))
    registration_message: Mapped[Optional[str]] = mapped_column(Text)

    # === Extension ===
    extend_target_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    extension_history: Mapped[Optional[Any]] = mapped_column(JSON)

    # === Keyword Rotation ===
    last_keyword_change: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # === Network + Company + Handler ===
    network_preset_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("network_presets.id"),
    )
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("companies.id"),
    )
    managed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
    )

    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    # Relationships
    keyword_pool: Mapped[List["CampaignKeywordPool"]] = relationship(
        "CampaignKeywordPool",
        back_populates="campaign",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_campaigns_status", "status"),
        Index("idx_campaigns_place_id", "place_id"),
        Index("idx_campaigns_superap_account_id", "superap_account_id"),
        Index("idx_campaigns_order_item_id", "order_item_id"),
        Index("idx_campaigns_end_date", "end_date"),
        Index("idx_campaigns_company_id", "company_id"),
        Index("idx_campaigns_network_preset_id", "network_preset_id"),
        Index("idx_campaigns_managed_by", "managed_by"),
    )
