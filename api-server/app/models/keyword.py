"""Keyword model - Table 7: keywords (extracted keywords).

Extracted keywords with ranking data for each place.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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
    from app.models.keyword_rank_history import KeywordRankHistory
    from app.models.place import Place


class Keyword(Base):
    """Extracted keyword with current rank for a place."""

    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    place_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    keyword_type: Mapped[Optional[str]] = mapped_column(String(20))
    search_query: Mapped[Optional[str]] = mapped_column(String(300))
    current_rank: Mapped[Optional[int]] = mapped_column(Integer)
    current_map_type: Mapped[Optional[str]] = mapped_column(String(10))
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    place: Mapped["Place"] = relationship(
        "Place",
        back_populates="extracted_keywords",
        lazy="noload",
    )
    rank_history: Mapped[List["KeywordRankHistory"]] = relationship(
        "KeywordRankHistory",
        back_populates="keyword_ref",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("place_id", "keyword", name="uq_keywords_place_keyword"),
        Index("idx_keywords_place_id", "place_id"),
        Index("idx_keywords_current_rank", "current_rank"),
        Index("idx_keywords_keyword_type", "keyword_type"),
    )
