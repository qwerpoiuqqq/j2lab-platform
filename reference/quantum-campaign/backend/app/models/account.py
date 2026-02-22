from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Account(Base):
    """superap.io 계정 관리 모델."""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False)  # superap 로그인 ID
    password_encrypted = Column(Text)  # AES 암호화
    agency_name = Column(String(100))  # 대행사명
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    campaigns = relationship("Campaign", back_populates="account")

    def __repr__(self):
        return f"<Account(id={self.id}, user_id='{self.user_id}')>"
