"""CampaignTemplate model - Table 13: campaign_templates.

Form content templates for superap.io campaign registration.
Source: reference/quantum-campaign/backend/app/models/template.py

Separate from network_presets:
- Templates = "what to fill" (description, hint, images, modules)
- Networks  = "which account + media" to use
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CampaignTemplate(Base):
    """Campaign registration form template."""

    __tablename__ = "campaign_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    type_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description_template: Mapped[str] = mapped_column(Text, nullable=False)
    hint_text: Mapped[str] = mapped_column(Text, nullable=False)
    campaign_type_selection: Mapped[Optional[str]] = mapped_column(String(100))
    links: Mapped[Optional[Any]] = mapped_column(JSON, nullable=False, default=[])
    hashtag: Mapped[Optional[str]] = mapped_column(String(100))
    image_url_200x600: Mapped[Optional[str]] = mapped_column(Text)
    image_url_720x780: Mapped[Optional[str]] = mapped_column(Text)
    conversion_text_template: Mapped[Optional[str]] = mapped_column(Text)
    steps_start: Mapped[Optional[str]] = mapped_column(Text)
    modules: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )
