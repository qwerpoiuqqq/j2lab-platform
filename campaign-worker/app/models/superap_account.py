"""Superap account model - maps to superap_accounts table.

This model mirrors the table created by api-server's migrations.
campaign-worker reads from this table to get login credentials.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class SuperapAccount(Base):
    """superap.io account model."""

    __tablename__ = "superap_accounts"

    id = Column(Integer, primary_key=True)
    user_id_superap = Column(String(100), unique=True, nullable=False)
    password_encrypted = Column(Text, nullable=False)

    company_id = Column(Integer)
    network_preset_id = Column(Integer)
    unit_cost_traffic = Column(Integer, nullable=False, default=21)
    unit_cost_save = Column(Integer, nullable=False, default=31)
    assignment_order = Column(Integer, nullable=False, default=0)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)

    # Relationships
    campaigns = relationship(
        "Campaign",
        back_populates="superap_account",
        foreign_keys="Campaign.superap_account_id",
    )

    def __repr__(self) -> str:
        return f"<SuperapAccount(id={self.id}, user_id='{self.user_id_superap}')>"
