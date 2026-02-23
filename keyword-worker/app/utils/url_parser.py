"""Naver Place URL parser.

Extracts place type and MID (place unique ID) from Naver Place URLs.
Ported from: reference/keyword-extract/src/url_parser.py
"""

import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class PlaceType(Enum):
    """Naver Place business type."""

    RESTAURANT = "restaurant"
    HOSPITAL = "hospital"
    HAIRSHOP = "hairshop"
    NAILSHOP = "nailshop"
    PLACE = "place"
    UNKNOWN = "unknown"


@dataclass
class ParsedURL:
    """Parsed URL information."""

    original_url: str
    place_type: PlaceType
    mid: str
    is_valid: bool
    error_message: Optional[str] = None


def parse_place_url(url: str) -> ParsedURL:
    """Parse a Naver Place URL to extract business type and MID.

    Supported URL formats:
    - https://m.place.naver.com/restaurant/12345678
    - https://m.place.naver.com/hospital/12345678/home
    - https://m.place.naver.com/place/12345678/information
    - https://place.naver.com/restaurant/12345678
    - https://map.naver.com/p/entry/place/12345678

    Args:
        url: Naver Place URL.

    Returns:
        ParsedURL with parsed components.
    """
    url = url.strip()

    # Pattern 1: place.naver.com/{type}/{MID}
    pattern1 = r"(?:https?://)?(?:m\.)?place\.naver\.com/(\w+)/(\d+)"
    match = re.search(pattern1, url)

    if not match:
        # Pattern 2: map.naver.com/p/entry/place/{MID}
        pattern2 = r"(?:https?://)?map\.naver\.com/p/entry/place/(\d+)"
        match2 = re.search(pattern2, url)
        if match2:
            return ParsedURL(
                original_url=url,
                place_type=PlaceType.PLACE,
                mid=match2.group(1),
                is_valid=True,
            )

        return ParsedURL(
            original_url=url,
            place_type=PlaceType.UNKNOWN,
            mid="",
            is_valid=False,
            error_message="Unsupported URL format.",
        )

    place_type_str = match.group(1).lower()
    mid = match.group(2)

    type_mapping = {
        "restaurant": PlaceType.RESTAURANT,
        "hospital": PlaceType.HOSPITAL,
        "hairshop": PlaceType.HAIRSHOP,
        "nailshop": PlaceType.NAILSHOP,
        "place": PlaceType.PLACE,
    }

    place_type = type_mapping.get(place_type_str, PlaceType.UNKNOWN)

    return ParsedURL(
        original_url=url,
        place_type=place_type,
        mid=mid,
        is_valid=True,
    )


def get_place_type_korean(place_type: PlaceType) -> str:
    """Return Korean name for the place type."""
    names = {
        PlaceType.RESTAURANT: "restaurant",
        PlaceType.HOSPITAL: "hospital",
        PlaceType.HAIRSHOP: "hairshop",
        PlaceType.NAILSHOP: "nailshop",
        PlaceType.PLACE: "place",
        PlaceType.UNKNOWN: "unknown",
    }
    return names.get(place_type, "unknown")
