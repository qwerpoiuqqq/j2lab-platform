"""Place model - Table 6: places (Naver Place data).

Source: reference/keyword-extract/src/models.py (PlaceData, RegionInfo)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.keyword import Keyword


class Place(Base):
    """Naver Place entity with full scraped data."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=False,  # Naver-assigned ID
    )

    # === Basic Info ===
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    place_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="place"
    )
    category: Mapped[Optional[str]] = mapped_column(String(500))
    main_category: Mapped[Optional[str]] = mapped_column(String(100))

    # === Address (RegionInfo) ===
    city: Mapped[Optional[str]] = mapped_column(String(50))
    si: Mapped[Optional[str]] = mapped_column(String(50))
    gu: Mapped[Optional[str]] = mapped_column(String(50))
    dong: Mapped[Optional[str]] = mapped_column(String(50))
    major_area: Mapped[Optional[str]] = mapped_column(String(50))
    road_address: Mapped[Optional[str]] = mapped_column(String(500))
    jibun_address: Mapped[Optional[str]] = mapped_column(String(500))
    stations: Mapped[Optional[Any]] = mapped_column(JSON, default=[])

    # === Contact ===
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    virtual_phone: Mapped[Optional[str]] = mapped_column(String(20))

    # === Business Info ===
    business_hours: Mapped[Optional[str]] = mapped_column(Text)
    introduction: Mapped[Optional[str]] = mapped_column(Text)
    naver_url: Mapped[Optional[str]] = mapped_column(String(500))

    # === Review/Keyword Data (PlaceData 1:1 mapping) ===
    keywords: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    conveniences: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    micro_reviews: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    review_menu_keywords: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    review_theme_keywords: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    voted_keywords: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    payment_info: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    seat_items: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    specialties: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    menus: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    medical_subjects: Mapped[Optional[Any]] = mapped_column(JSON, default=[])
    discovered_regions: Mapped[Optional[Any]] = mapped_column(JSON, default=[])

    # === Booking ===
    has_booking: Mapped[bool] = mapped_column(Boolean, default=False)
    booking_type: Mapped[Optional[str]] = mapped_column(String(20))
    booking_hub_id: Mapped[Optional[str]] = mapped_column(String(100))
    booking_url: Mapped[Optional[str]] = mapped_column(Text)

    # === Meta ===
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    # Relationships
    extracted_keywords: Mapped[List["Keyword"]] = relationship(
        "Keyword",
        back_populates="place",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_places_place_type", "place_type"),
        Index("idx_places_gu", "gu"),
        Index("idx_places_major_area", "major_area"),
    )
