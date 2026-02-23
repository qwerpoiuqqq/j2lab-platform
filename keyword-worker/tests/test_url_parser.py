"""Tests for URL parser utility."""

import pytest

from app.utils.url_parser import PlaceType, parse_place_url


class TestParseURL:
    """Test URL parsing for various Naver Place URL formats."""

    def test_restaurant_url(self):
        result = parse_place_url("https://m.place.naver.com/restaurant/1082820234")
        assert result.is_valid is True
        assert result.place_type == PlaceType.RESTAURANT
        assert result.mid == "1082820234"

    def test_restaurant_url_with_path(self):
        result = parse_place_url(
            "https://m.place.naver.com/restaurant/1082820234/home"
        )
        assert result.is_valid is True
        assert result.place_type == PlaceType.RESTAURANT
        assert result.mid == "1082820234"

    def test_hospital_url(self):
        result = parse_place_url(
            "https://m.place.naver.com/hospital/1984640040/home"
        )
        assert result.is_valid is True
        assert result.place_type == PlaceType.HOSPITAL
        assert result.mid == "1984640040"

    def test_hairshop_url(self):
        result = parse_place_url(
            "https://m.place.naver.com/hairshop/1210917989/information"
        )
        assert result.is_valid is True
        assert result.place_type == PlaceType.HAIRSHOP
        assert result.mid == "1210917989"

    def test_place_url(self):
        result = parse_place_url("https://place.naver.com/place/1573829847")
        assert result.is_valid is True
        assert result.place_type == PlaceType.PLACE
        assert result.mid == "1573829847"

    def test_map_url(self):
        result = parse_place_url(
            "https://map.naver.com/p/entry/place/1234567890"
        )
        assert result.is_valid is True
        assert result.place_type == PlaceType.PLACE
        assert result.mid == "1234567890"

    def test_desktop_url(self):
        """Desktop URL without 'm.' prefix."""
        result = parse_place_url(
            "https://place.naver.com/restaurant/1082820234"
        )
        assert result.is_valid is True
        assert result.place_type == PlaceType.RESTAURANT
        assert result.mid == "1082820234"

    def test_invalid_url(self):
        result = parse_place_url("https://invalid-url.com/test")
        assert result.is_valid is False
        assert result.place_type == PlaceType.UNKNOWN
        assert result.mid == ""

    def test_empty_url(self):
        result = parse_place_url("")
        assert result.is_valid is False

    def test_url_with_whitespace(self):
        result = parse_place_url(
            "  https://m.place.naver.com/restaurant/1082820234  "
        )
        assert result.is_valid is True
        assert result.mid == "1082820234"

    def test_nailshop_url(self):
        result = parse_place_url(
            "https://m.place.naver.com/nailshop/123456789"
        )
        assert result.is_valid is True
        assert result.place_type == PlaceType.NAILSHOP
        assert result.mid == "123456789"
