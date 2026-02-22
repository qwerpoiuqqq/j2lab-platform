from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


class Campaign(Base):
    """캠페인 모델."""

    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    campaign_code = Column(String(20))  # superap 캠페인 번호
    account_id = Column(Integer, ForeignKey("accounts.id"))
    agency_name = Column(String(100))
    place_name = Column(String(200), nullable=False, default="")
    place_url = Column(Text, nullable=False)
    place_id = Column(String(50), index=True)  # 플레이스 ID (URL에서 추출)
    campaign_type = Column(String(50), nullable=False)  # '트래픽' or '저장하기'

    registered_at = Column(DateTime)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    daily_limit = Column(Integer, nullable=False)
    total_limit = Column(Integer)
    current_conversions = Column(Integer, default=0)

    landmark_name = Column(String(200))  # 선택된 명소
    step_count = Column(Integer)  # 걸음수 (정답)

    original_keywords = Column(Text)  # 원본 키워드 풀

    status = Column(String(20), default='pending')
    registration_step = Column(String(30), nullable=True)  # queued|logging_in|running_modules|filling_form|submitting|extracting_code|completed|failed
    registration_message = Column(Text, nullable=True)  # 진행 상태 메시지
    extend_target_id = Column(Integer, nullable=True)  # 연장 대상 캠페인 DB ID (pending_extend 시 사용)
    extension_history = Column(Text, nullable=True)  # JSON 배열: [{"round":1,"start_date":"...","end_date":"...","daily_limit":50,"extended_at":"..."}]
    last_keyword_change = Column(DateTime)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    account = relationship("Account", back_populates="campaigns")
    keywords = relationship("KeywordPool", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Campaign(id={self.id}, place_name='{self.place_name}', status='{self.status}')>"
