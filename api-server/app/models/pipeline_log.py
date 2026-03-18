"""PipelineLog model - Table 16: pipeline_logs.

Audit trail for pipeline stage transitions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.pipeline_state import PipelineState


class PipelineLog(Base):
    """Log entry for a pipeline stage transition."""

    __tablename__ = "pipeline_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    pipeline_state_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("pipeline_states.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_stage: Mapped[Optional[str]] = mapped_column(String(30))
    to_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_type: Mapped[Optional[str]] = mapped_column(String(50))
    message: Mapped[Optional[str]] = mapped_column(Text)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    actor_name: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    pipeline_state: Mapped["PipelineState"] = relationship(
        "PipelineState",
        back_populates="logs",
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_pipeline_logs_state_id", "pipeline_state_id"),
    )
