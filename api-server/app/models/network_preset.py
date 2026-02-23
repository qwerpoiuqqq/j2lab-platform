"""NetworkPreset model - Table 19: network_presets.

Network presets define account groups + media targeting for reward dedup.
Separate axis from campaign templates (which define form content).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.superap_account import SuperapAccount


class NetworkPreset(Base):
    """Network preset: account group + media targeting combination."""

    __tablename__ = "network_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False,
    )
    campaign_type: Mapped[str] = mapped_column(String(20), nullable=False)
    tier_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    media_config: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=False, default={}
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    # Relationships
    accounts: Mapped[List["SuperapAccount"]] = relationship(
        "SuperapAccount",
        back_populates="network_preset",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "campaign_type",
            "tier_order",
            name="uq_network_presets_company_type_tier",
        ),
        Index("idx_network_presets_company_id", "company_id"),
    )
