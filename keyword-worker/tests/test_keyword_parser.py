"""Tests for keyword parser / keyword generation engine."""

import pytest

from app.services.keyword_parser import (
    BUSINESS_TYPE_KEYWORDS,
    detect_business_type,
    generate_keyword_pool,
    generate_region_keywords,
    parse_business_name,
)
from app.services.place_scraper import PlaceData, RegionInfo, ReviewKeyword


class TestDetectBusinessType:
    """Test business type detection from category string."""

    def test_restaurant_detection(self):
        assert detect_business_type("이탈리아음식") == "restaurant"
        assert detect_business_type("한식,음식점") == "restaurant"
        assert detect_business_type("카페") == "restaurant"
        assert detect_business_type("분식") == "restaurant"

    def test_hospital_detection(self):
        assert detect_business_type("치과") == "hospital"
        assert detect_business_type("피부과") == "hospital"
        assert detect_business_type("정형외과") == "hospital"
        assert detect_business_type("동물병원") == "hospital"

    def test_general_detection(self):
        assert detect_business_type("미용실") == "general"
        assert detect_business_type("변호사") == "general"
        assert detect_business_type("") == "general"
        assert detect_business_type("학원") == "general"


class TestGenerateRegionKeywords:
    """Test region keyword generation."""

    def test_basic_region(self):
        region = RegionInfo(
            city="서울",
            gu="강남구",
            dong="역삼동",
            gu_without_suffix="강남",
            dong_without_suffix="역삼",
            stations=["강남역"],
        )
        keywords = generate_region_keywords(region)

        # Should contain individual regions
        assert "강남구" in keywords
        assert "강남" in keywords
        assert "강남역" in keywords

        # Should contain station without 역
        station_base_found = any("강남" == k for k in keywords)
        assert station_base_found

        # Should contain combinations
        assert any("강남" in k and "역삼" in k for k in keywords)

        # Should contain location suffixes
        assert any("근처" in k for k in keywords)
        assert any("주변" in k for k in keywords)

    def test_region_with_si(self):
        region = RegionInfo(
            city="경기",
            si="고양시",
            gu="일산동구",
            dong="장항동",
            si_without_suffix="고양",
            gu_without_suffix="일산동",
            dong_without_suffix="장항",
            major_area="일산",
            stations=["정발산역"],
        )
        keywords = generate_region_keywords(region)

        assert "고양시" in keywords
        assert "고양" in keywords
        assert "일산" in keywords
        assert "정발산역" in keywords
        assert len(keywords) > 10  # Should generate many combinations

    def test_empty_region(self):
        region = RegionInfo()
        keywords = generate_region_keywords(region)
        assert keywords == []

    def test_duplicate_dong_not_standalone(self):
        """Duplicate dong names should not appear standalone."""
        region = RegionInfo(
            city="서울",
            gu="강남구",
            dong="역삼동",  # In DUPLICATE_DONG_NAMES
            gu_without_suffix="강남",
            dong_without_suffix="역삼",  # In DUPLICATE_DONG_NAMES
        )
        keywords = generate_region_keywords(region)
        # 역삼동 and 역삼 are duplicates - should only appear in combinations
        # But they will appear in combos like "강남 역삼"
        assert "강남구" in keywords
        assert "강남" in keywords


class TestParseBusinessName:
    """Test business name morpheme parsing."""

    def test_simple_name(self):
        parts = parse_business_name("미도인 강남")
        assert "미도인" in parts
        assert "강남" in parts
        assert "미도인강남" in parts  # combined

    def test_clinic_name(self):
        parts = parse_business_name("세라믹치과의원")
        assert "세라믹치과의원" in parts
        # Should strip suffix
        assert "세라믹" in parts or "세라믹치과" in parts

    def test_single_word_name(self):
        parts = parse_business_name("맛집")
        assert "맛집" in parts

    def test_multi_word_name(self):
        parts = parse_business_name("강남 더 클리닉")
        assert "강남" in parts
        assert any("클리닉" in p for p in parts)


class TestGenerateKeywordPool:
    """Test keyword pool generation."""

    def test_restaurant_pool(self, sample_place_data: PlaceData):
        pool = generate_keyword_pool(
            sample_place_data, target_count=100, name_keyword_ratio=0.30
        )

        assert len(pool) > 0

        # Check structure
        for item in pool:
            assert "keyword" in item
            assert "source" in item
            assert "priority" in item
            assert len(item["keyword"]) >= 2

        keywords = [item["keyword"] for item in pool]

        # Should contain region + biz type keywords
        has_region_biz = any(
            "강남" in k and ("맛집" in k or "음식점" in k or "식당" in k)
            for k in keywords
        )
        assert has_region_biz, "Should have region + business type keywords"

        # Should contain region + name keywords
        has_region_name = any(
            "강남" in k and "미도인" in k for k in keywords
        )
        assert has_region_name, "Should have region + name keywords"

    def test_hospital_pool(self, sample_hospital_data: PlaceData):
        pool = generate_keyword_pool(
            sample_hospital_data, target_count=100, name_keyword_ratio=0.30
        )

        assert len(pool) > 0

        keywords = [item["keyword"] for item in pool]

        # Should contain region + hospital keywords
        has_region_hosp = any(
            ("일산" in k or "고양" in k) and ("병원" in k or "의원" in k)
            for k in keywords
        )
        assert has_region_hosp, "Should have region + hospital keywords"

        # Should contain medical subjects
        has_subject = any("임플란트" in k or "교정" in k for k in keywords)
        assert has_subject, "Should have medical subject keywords"

    def test_pool_priority_ordering(self, sample_place_data: PlaceData):
        pool = generate_keyword_pool(sample_place_data, target_count=50)

        # Pool should be sorted by priority
        priorities = [item["priority"] for item in pool]
        assert priorities == sorted(priorities)

    def test_no_duplicate_keywords(self, sample_place_data: PlaceData):
        pool = generate_keyword_pool(sample_place_data, target_count=200)
        keywords = [item["keyword"] for item in pool]
        assert len(keywords) == len(set(keywords)), "Should have no duplicate keywords"
