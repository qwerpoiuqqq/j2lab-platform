from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.types import JSON

from app.database import Base


class CampaignTemplate(Base):
    """캠페인 타입별 템플릿 모델."""

    __tablename__ = "campaign_templates"

    id = Column(Integer, primary_key=True)
    type_name = Column(String(50), unique=True, nullable=False)  # '트래픽', '저장하기'
    description_template = Column(Text, nullable=False)  # 참여 방법 설명
    hint_text = Column(Text, nullable=False)  # 정답 맞추기 힌트
    campaign_type_selection = Column(String(100))  # '플레이스 퀴즈' 등
    links = Column(JSON, nullable=False)  # ["링크1", "링크2", "링크3"]
    hashtag = Column(String(100))  # '#cpc_detail_place'
    image_url_200x600 = Column(Text)
    image_url_720x780 = Column(Text)
    # 텍스트 기반 전환 인식 기준 (걸음수 대신 텍스트 사용 시)
    conversion_text_template = Column(Text, default=None)  # "&명소명& ㄱㄱ" 등
    # 걸음수 모듈 출발지 (비어있으면 명소명을 출발지로 사용)
    steps_start = Column(Text, default=None)
    # Phase 3.2 추가 필드
    modules = Column(JSON, default=list)  # ["landmark", "steps"] 사용할 모듈 ID 목록
    is_active = Column(Boolean, default=True)  # 활성화 여부
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<CampaignTemplate(id={self.id}, type_name='{self.type_name}')>"
