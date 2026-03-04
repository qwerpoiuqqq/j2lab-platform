"""Campaign model - maps to campaigns table.

This model mirrors the table created by api-server's migrations.
campaign-worker reads and updates campaign status, keywords, etc.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Campaign(Base):
    """Campaign model."""

    __tablename__ = "campaigns"

    id = Column(BigInteger, primary_key=True)
    campaign_code = Column(String(20))
    superap_account_id = Column(Integer, ForeignKey("superap_accounts.id"))
    order_item_id = Column(BigInteger)
    place_id = Column(BigInteger)
    extraction_job_id = Column(BigInteger)

    # Basic info
    agency_name = Column(String(100))
    place_name = Column(String(200), nullable=False, default="")
    place_url = Column(Text, nullable=False)
    campaign_type = Column(String(50), nullable=False)

    # Period/limits
    registered_at = Column(DateTime(timezone=True))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    daily_limit = Column(Integer, nullable=False)
    total_limit = Column(Integer)
    current_conversions = Column(Integer, default=0)

    # Module results
    landmark_name = Column(String(200))
    step_count = Column(Integer)
    module_context = Column(JSONB)

    # Keywords
    original_keywords = Column(Text)

    # Status
    status = Column(String(20), nullable=False, default="pending")
    registration_step = Column(String(30))
    registration_message = Column(Text)

    # Extension
    extend_target_id = Column(BigInteger)
    extension_history = Column(JSONB)

    # Conversion threshold
    conversion_threshold_handled = Column(Boolean, default=False, server_default="false")

    # Keyword rotation
    last_keyword_change = Column(DateTime(timezone=True))

    # Network + Company + Handler
    network_preset_id = Column(Integer)
    company_id = Column(Integer)
    managed_by = Column(Uuid)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(DateTime(timezone=True))

    # Relationships
    superap_account = relationship("SuperapAccount", back_populates="campaigns", foreign_keys=[superap_account_id])
    keywords = relationship(
        "CampaignKeywordPool",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Campaign(id={self.id}, place_name='{self.place_name}', "
            f"status='{self.status}')>"
        )
