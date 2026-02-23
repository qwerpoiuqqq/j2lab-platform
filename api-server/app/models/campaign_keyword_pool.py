"""CampaignKeywordPool model - Table 12: campaign_keyword_pool.

Keywords assigned to campaigns for rotation.
Source: reference/quantum-campaign/backend/app/models/keyword.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.campaign import Campaign


class CampaignKeywordPool(Base):
    """Keyword in a campaign's rotation pool."""

    __tablename__ = "campaign_keyword_pool"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    campaign_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    round_number: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        "Campaign",
        back_populates="keyword_pool",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "keyword", name="uq_campaign_kw_pool_campaign_keyword"
        ),
        Index("idx_campaign_kw_pool_campaign_id", "campaign_id"),
        Index("idx_campaign_kw_pool_is_used", "is_used"),
    )
