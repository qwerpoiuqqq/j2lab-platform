"""KeywordRankHistory model - Table 8: keyword_rank_history.

Historical rank tracking for keywords.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.keyword import Keyword


class KeywordRankHistory(Base):
    """Daily rank record for a keyword."""

    __tablename__ = "keyword_rank_history"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    keyword_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank_position: Mapped[Optional[int]] = mapped_column(Integer)
    map_type: Mapped[Optional[str]] = mapped_column(String(10))
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    keyword_ref: Mapped["Keyword"] = relationship(
        "Keyword",
        back_populates="rank_history",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "keyword_id", "recorded_date", name="uq_rank_history_keyword_date"
        ),
        Index("idx_rank_history_keyword_id", "keyword_id"),
        Index("idx_rank_history_recorded_date", "recorded_date"),
    )
