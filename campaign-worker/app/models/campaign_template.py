"""Campaign template model - maps to campaign_templates table.

This model mirrors the table created by api-server's migrations.
campaign-worker reads templates to fill superap.io campaign forms.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class CampaignTemplate(Base):
    """Campaign type template model."""

    __tablename__ = "campaign_templates"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    type_name = Column(String(50), unique=True, nullable=False)
    description_template = Column(Text, nullable=False)
    hint_text = Column(Text, nullable=False)
    campaign_type_selection = Column(String(100))
    links = Column(JSONB, nullable=False, default=list)
    hashtag = Column(String(100))
    image_url_200x600 = Column(Text)
    image_url_720x780 = Column(Text)
    conversion_text_template = Column(Text)
    steps_start = Column(Text)
    modules = Column(JSONB, default=list)
    default_redirect_config = Column(JSONB)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return (
            f"<CampaignTemplate(id={self.id}, code='{self.code}', "
            f"type_name='{self.type_name}')>"
        )
