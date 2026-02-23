"""SuperapAccount model - Table 10: superap_accounts.

Superap.io accounts with AES-encrypted passwords.
Source: reference/quantum-campaign/backend/app/models/account.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.network_preset import NetworkPreset


class SuperapAccount(Base):
    """Superap.io login account with encrypted password."""

    __tablename__ = "superap_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id_superap: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    agency_name: Mapped[Optional[str]] = mapped_column(String(100))

    # Multi-tenant
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("companies.id"),
    )

    # Network preset link
    network_preset_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("network_presets.id"),
    )

    unit_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=21)
    assignment_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    network_preset: Mapped[Optional["NetworkPreset"]] = relationship(
        "NetworkPreset",
        back_populates="accounts",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_superap_accounts_company_id", "company_id"),
        Index("idx_superap_accounts_network_preset_id", "network_preset_id"),
    )
