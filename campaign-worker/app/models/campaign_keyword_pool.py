"""Campaign keyword pool model - maps to campaign_keyword_pool table.

This model mirrors the table created by api-server's migrations.
campaign-worker manages keyword rotation through this table.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class CampaignKeywordPool(Base):
    """Campaign keyword pool model for keyword rotation."""

    __tablename__ = "campaign_keyword_pool"

    id = Column(BigInteger, primary_key=True)
    campaign_id = Column(BigInteger, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(255), nullable=False)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True))
    round_number = Column(Integer, default=1)

    # Relationships
    campaign = relationship("Campaign", back_populates="keywords")

    __table_args__ = (
        UniqueConstraint("campaign_id", "keyword", name="uq_campaign_keyword"),
    )

    def __repr__(self) -> str:
        return (
            f"<CampaignKeywordPool(id={self.id}, keyword='{self.keyword}', "
            f"is_used={self.is_used})>"
        )
