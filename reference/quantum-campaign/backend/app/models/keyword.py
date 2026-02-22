from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


class KeywordPool(Base):
    """캠페인별 키워드 풀 모델."""

    __tablename__ = "keyword_pool"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    keyword = Column(String(255), nullable=False)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime)

    # Relationships
    campaign = relationship("Campaign", back_populates="keywords")

    __table_args__ = (
        UniqueConstraint('campaign_id', 'keyword', name='uq_campaign_keyword'),
    )

    def __repr__(self):
        return f"<KeywordPool(id={self.id}, keyword='{self.keyword}', is_used={self.is_used})>"
