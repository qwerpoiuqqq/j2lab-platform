"""PipelineState model - Table 15: pipeline_states.

Per-order-item pipeline stage tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.pipeline_log import PipelineLog


class PipelineStage(str, Enum):
    """Pipeline stage values."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    PAYMENT_CONFIRMED = "payment_confirmed"
    EXTRACTION_QUEUED = "extraction_queued"
    EXTRACTION_RUNNING = "extraction_running"
    EXTRACTION_DONE = "extraction_done"
    ACCOUNT_ASSIGNED = "account_assigned"
    ASSIGNMENT_CONFIRMED = "assignment_confirmed"
    CAMPAIGN_REGISTERING = "campaign_registering"
    CAMPAIGN_ACTIVE = "campaign_active"
    MANAGEMENT = "management"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Valid stage transitions
VALID_PIPELINE_TRANSITIONS = {
    PipelineStage.DRAFT: [PipelineStage.SUBMITTED, PipelineStage.CANCELLED],
    PipelineStage.SUBMITTED: [
        PipelineStage.PAYMENT_CONFIRMED,
        PipelineStage.CANCELLED,
    ],
    PipelineStage.PAYMENT_CONFIRMED: [
        PipelineStage.EXTRACTION_QUEUED,
        PipelineStage.CANCELLED,
    ],
    PipelineStage.EXTRACTION_QUEUED: [
        PipelineStage.EXTRACTION_RUNNING,
        PipelineStage.FAILED,
        PipelineStage.CANCELLED,
    ],
    PipelineStage.EXTRACTION_RUNNING: [
        PipelineStage.EXTRACTION_DONE,
        PipelineStage.FAILED,
    ],
    PipelineStage.EXTRACTION_DONE: [
        PipelineStage.ACCOUNT_ASSIGNED,
        PipelineStage.FAILED,
    ],
    PipelineStage.ACCOUNT_ASSIGNED: [
        PipelineStage.ASSIGNMENT_CONFIRMED,
    ],
    PipelineStage.ASSIGNMENT_CONFIRMED: [
        PipelineStage.CAMPAIGN_REGISTERING,
    ],
    PipelineStage.CAMPAIGN_REGISTERING: [
        PipelineStage.CAMPAIGN_ACTIVE,
        PipelineStage.FAILED,
    ],
    PipelineStage.CAMPAIGN_ACTIVE: [
        PipelineStage.MANAGEMENT,
        PipelineStage.COMPLETED,
    ],
    PipelineStage.MANAGEMENT: [PipelineStage.COMPLETED],
    PipelineStage.COMPLETED: [],
    PipelineStage.FAILED: [
        # Retry: can go back to earlier stages
        PipelineStage.EXTRACTION_QUEUED,
        PipelineStage.CAMPAIGN_REGISTERING,
    ],
    PipelineStage.CANCELLED: [],
}


class PipelineState(Base):
    """Pipeline state for an order item (1:1 with order_items)."""

    __tablename__ = "pipeline_states"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    current_stage: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=PipelineStage.DRAFT.value,
    )
    previous_stage: Mapped[Optional[str]] = mapped_column(String(30))
    extraction_job_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("extraction_jobs.id"),
    )
    campaign_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("campaigns.id"),
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[Any]] = mapped_column("metadata", JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    logs: Mapped[List["PipelineLog"]] = relationship(
        "PipelineLog",
        back_populates="pipeline_state",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("order_item_id", name="uq_pipeline_states_order_item_id"),
        Index("idx_pipeline_order_item_id", "order_item_id"),
        Index("idx_pipeline_current_stage", "current_stage"),
    )
