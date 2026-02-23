"""ExtractionJob model - mirrors api-server's extraction_jobs table.

Keyword extraction job tracking.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExtractionJobStatus(str, Enum):
    """Extraction job status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExtractionJob(Base):
    """Keyword extraction job with progress tracking."""

    __tablename__ = "extraction_jobs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    order_item_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("order_items.id", ondelete="SET NULL"),
    )
    place_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("places.id", ondelete="SET NULL"),
    )
    naver_url: Mapped[str] = mapped_column(Text, nullable=False)

    # === Job Parameters ===
    target_count: Mapped[int] = mapped_column(Integer, default=100)
    max_rank: Mapped[int] = mapped_column(Integer, default=50)
    min_rank: Mapped[int] = mapped_column(Integer, default=1)
    name_keyword_ratio: Mapped[float] = mapped_column(Float, default=0.30)

    # === Results ===
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ExtractionJobStatus.QUEUED.value,
    )
    place_name: Mapped[Optional[str]] = mapped_column(String(200))
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[Optional[Any]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # === Worker Info ===
    proxy_slot: Mapped[Optional[int]] = mapped_column(Integer)
    worker_id: Mapped[Optional[str]] = mapped_column(String(50))

    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    __table_args__ = (
        Index("idx_extraction_jobs_status", "status"),
        Index("idx_extraction_jobs_place_id", "place_id"),
        Index("idx_extraction_jobs_order_item_id", "order_item_id"),
        {"extend_existing": True},
    )
