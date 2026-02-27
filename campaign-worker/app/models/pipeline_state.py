"""PipelineState model - maps to pipeline_states table.

This model mirrors the table created by api-server's migrations.
campaign-worker uses this for the campaign expiry auto-complete job.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class PipelineStage:
    """Pipeline stage constants (subset used by campaign-worker)."""

    CAMPAIGN_ACTIVE = "campaign_active"
    MANAGEMENT = "management"
    COMPLETED = "completed"


class PipelineState(Base):
    """Pipeline state for an order item."""

    __tablename__ = "pipeline_states"

    id = Column(BigInteger, primary_key=True)
    order_item_id = Column(BigInteger, nullable=False)
    campaign_id = Column(BigInteger)
    current_stage = Column(String(30), nullable=False, default="draft")
    previous_stage = Column(String(30))

    def __repr__(self) -> str:
        return f"<PipelineState(id={self.id}, stage='{self.current_stage}')>"
