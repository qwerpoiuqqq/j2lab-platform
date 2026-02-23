"""Keyword generation engine for Naver Place keywords.

Generates keyword combinations from place data:
- Region variations (city, gu, dong, station + suffixes)
- Business type keywords (restaurant, hospital, general)
- Name-based keywords (business name morphemes)
- Modifier keywords (review themes mapped to search terms)

Ported from: reference/keyword-extract/src/smart_worker.py (Phase 2 logic)
"""

from __future__ import annotations

import logging
import re
from itertools import combinations
from typing import Dict, List, Optional, Set

from app.services.place_scraper import PlaceData, RegionInfo

logger = logging.getLogger(__name__)


# ==================== Constants ====================

THEME_MAPPING: Dict[str, List[str]] = {
    "전망": ["뷰맛집", "오션뷰", "전망좋은", "경치좋은"],
    "분위기": ["분위기좋은", "인테리어", "감성", "사진찍기좋은"],
    "가격": ["가성비", "저렴한", "착한가격"],
    "목적": ["데이트", "모임", "회식", "가족모임", "혼밥"],
    "주차": ["주차", "주차편한", "주차가능", "주차장"],
    "사진": ["사진맛집", "인생샷", "포토존"],
    "친절": ["친절한"],
    "특별한": ["이색", "특별한메뉴"],
    "단체": ["단체석", "넓은"],
    "혼밥": ["혼밥", "혼술"],
    "청결": ["깨끗한", "청결한"],
}

RESTAURANT_CATEGORIES: Set[str] = {
    "음식", "요리", "식당", "카페", "주점", "호프", "맛집",
    "한식", "양식", "일식", "중식", "분식", "뷔페", "레스토랑",
    "고기", "구이", "회", "돈가스", "파스타", "피자", "버거",
    "갈비", "곱창", "국밥", "면", "제과", "베이커리", "디저트",
    "치킨", "족발", "보쌈", "찜", "탕", "전골", "냉면", "칼국수",
    "커피", "브런치", "펍", "바", "이자카야", "선술집",
}

HOSPITAL_CATEGORIES: Set[str] = {
    "병원", "의원", "치과", "한의원", "클리닉", "피부과",
    "정형외과", "신경외과", "내과", "외과", "안과", "이비인후과",
    "재활의학과", "산부인과", "비뇨기과", "성형외과", "마취통증의학과",
    "소아과", "정신과", "신경과", "흉부외과", "심장내과",
    "동물병원", "수의과", "펫클리닉",
}

BUSINESS_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "restaurant": ["맛집", "음식점", "식당"],
    "hospital": ["병원", "의원", "병의원"],
    "general": ["전문점", "매장"],
}

MANDATORY_MODIFIERS: List[str] = ["지도", "추천"]

STANDALONE_BLOCKED: Set[str] = {
    "24시", "아트", "샵", "전문", "추천", "잘하는", "유명한",
    "근처", "주변", "부근", "가까운",
}

LOCATION_SUFFIXES: List[str] = ["근처", "주변", "부근", "가까운"]

DUPLICATE_DONG_NAMES: Set[str] = {
    "역삼동", "역삼", "신사동", "신사", "삼성동", "삼성", "대치동", "대치",
    "청담동", "청담", "논현동", "논현", "서초동", "서초", "방배동", "방배",
    "잠실동", "잠실", "송파동", "송파", "강동", "강서동", "강서",
    "명동", "본동", "신동", "구동", "상동", "하동",
    "내동", "외동", "대동", "소동", "장동", "단동",
    "남동", "북동", "동동", "서동",
    "해운대", "서면", "남포동", "남포", "동래동", "동래",
    "연산동", "연산", "부전동", "부전",
    "동구", "서구", "남구", "북구", "중구",
    "유성동", "유성", "둔산동", "둔산", "월평동", "월평",
    "중앙동", "중앙", "신정동", "신정", "목동",
    "구월동", "구월", "간석동", "간석", "만수동", "만수",
    "송도동", "송도", "부평동", "부평",
    "일산동", "일산", "분당동", "분당", "판교동", "판교",
    "동탄동", "동탄", "광교동", "광교",
}


# ==================== Business Type Detection ====================

def detect_business_type(category: str) -> str:
    """Detect business type from category string.

    Returns: 'restaurant', 'hospital', or 'general'
    """
    if not category:
        return "general"
    for kw in RESTAURANT_CATEGORIES:
        if kw in category:
            return "restaurant"
    for kw in HOSPITAL_CATEGORIES:
        if kw in category:
            return "hospital"
    return "general"


# ==================== Region Keyword Generation ====================

def generate_region_keywords(region: RegionInfo) -> List[str]:
    """Generate region keyword variations from RegionInfo.

    Creates combinations of:
    - Individual regions (city, gu, dong, station)
    - Paired regions (city + dong, gu + station, etc.)
    - Location suffixes (nearby, around, etc.)

    Returns deduplicated list of region variations.
    """
    result: List[str] = []
    core_regions: List[str] = []
    dong_regions: List[str] = []
    station_list: List[str] = []
    road_list: List[str] = []

    # Collect region components
    if region.si:
        result.append(region.si)
        core_regions.append(region.si)
    if region.si_without_suffix and region.si_without_suffix not in result:
        result.append(region.si_without_suffix)
        core_regions.append(region.si_without_suffix)
    if region.major_area and region.major_area not in result:
        result.append(region.major_area)
        core_regions.append(region.major_area)
    if region.gu:
        result.append(region.gu)
        core_regions.append(region.gu)
    if region.gu_without_suffix and region.gu_without_suffix not in result:
        result.append(region.gu_without_suffix)
        core_regions.append(region.gu_without_suffix)

    # Dong handling - check for duplicates
    if region.dong:
        if region.dong not in DUPLICATE_DONG_NAMES:
            result.append(region.dong)
        dong_regions.append(region.dong)
    if region.dong_without_suffix and region.dong_without_suffix not in dong_regions:
        if region.dong_without_suffix not in DUPLICATE_DONG_NAMES:
            result.append(region.dong_without_suffix)
        dong_regions.append(region.dong_without_suffix)

    # Stations
    for station in region.stations:
        if station:
            station_list.append(station)
            if station not in result:
                result.append(station)
            base = station.replace("역", "")
            if len(base) >= 2 and base not in result:
                result.append(base)
                core_regions.append(base)

    # Road
    if region.road:
        road_list.append(region.road)

    # 2-combination: dong + core region (dong is not standalone if duplicate)
    combo_regions: List[str] = []
    for dong in dong_regions:
        for parent in core_regions[:6]:
            combo = f"{parent} {dong}"
            if combo not in result:
                result.append(combo)
                combo_regions.append(combo)

    # Core region pairs
    for i, r1 in enumerate(core_regions[:6]):
        for j, r2 in enumerate(core_regions[:6]):
            if i != j and r1 != r2:
                combo = f"{r1} {r2}"
                if combo not in result:
                    result.append(combo)
                    combo_regions.append(combo)

    # Road combinations
    for road in road_list:
        for reg in core_regions[:4]:
            road_combo = f"{reg} {road}"
            if road_combo not in result:
                result.append(road_combo)

    # Location suffix combinations
    for reg in core_regions[:6]:
        for suffix in LOCATION_SUFFIXES:
            s = f"{reg} {suffix}"
            if s not in result:
                result.append(s)

    for station in station_list:
        for suffix in LOCATION_SUFFIXES:
            s1 = f"{station} {suffix}"
            if s1 not in result:
                result.append(s1)
            if station.endswith("역"):
                s2 = f"{station}{suffix}"
                if s2 not in result:
                    result.append(s2)

    for combo in combo_regions[:8]:
        for suffix in LOCATION_SUFFIXES:
            s = f"{combo} {suffix}"
            if s not in result:
                result.append(s)

    # Province-level prefix (city field = province abbreviation)
    if region.city:
        province = region.city
        for r in core_regions[:4]:
            if province != r and province not in r:
                pcombo = f"{province} {r}"
                if pcombo not in result:
                    result.append(pcombo)

    # Deduplicate keeping order
    seen: Set[str] = set()
    deduped: List[str] = []
    for v in result:
        v = v.strip()
        if v and len(v) >= 2 and v not in seen:
            seen.add(v)
            deduped.append(v)
    return deduped


# ==================== Name Morpheme Parsing ====================

def parse_business_name(name: str) -> List[str]:
    """Parse business name into morpheme parts.

    Example: "세라믹치과의원" -> ["세라믹", "치과", "의원", "세라믹치과", "치과의원", ...]
    """
    result: Set[str] = set()

    # Split by spaces
    space_parts = [p.strip() for p in name.split() if len(p.strip()) >= 2]
    result.update(space_parts)

    # Contiguous combinations without spaces
    if len(space_parts) >= 2:
        for i in range(len(space_parts)):
            for j in range(i + 1, len(space_parts) + 1):
                combo = "".join(space_parts[i:j])
                if len(combo) >= 2:
                    result.add(combo)

    # Strip common suffixes
    suffixes_to_strip = [
        "의원", "병원", "치과", "한의원", "클리닉", "센터", "샵",
        "아트", "네일", "점", "지점", "본점", "분점", "매장", "호점",
    ]
    name_no_space = name.replace(" ", "")
    for suffix in suffixes_to_strip:
        if name_no_space.endswith(suffix) and len(name_no_space) > len(suffix):
            base = name_no_space[: -len(suffix)]
            if len(base) >= 2:
                result.add(base)

    return list(result)


# ==================== Keyword Pool Generation ====================

def generate_keyword_pool(
    place_data: PlaceData,
    target_count: int = 200,
    name_keyword_ratio: float = 0.30,
) -> List[Dict]:
    """Generate a keyword pool from place data.

    Produces keyword combinations in hierarchical layers:
    R1: region + business_type_keyword (highest priority)
    R2: region + name_keyword (for name-based ranking)
    R3: region + category keyword
    R4: region + menu/service keyword
    R5: region + modifier keyword
    R6-R10: multi-word combinations

    Args:
        place_data: Scraped place data.
        target_count: Target number of keywords (default 200).
        name_keyword_ratio: Ratio of name-based keywords (default 30%).

    Returns:
        List of keyword dicts: [{"keyword": "...", "source": "...", "priority": N}]
    """
    business_type = detect_business_type(place_data.category)
    regions = generate_region_keywords(place_data.region)
    name_parts = parse_business_name(place_data.name)
    biz_keywords = BUSINESS_TYPE_KEYWORDS.get(business_type, ["전문점"])

    # Collect base keywords (menus, categories, subjects)
    base_keywords: List[str] = []

    # From place keywords
    for kw in place_data.keywords:
        if kw and len(kw) >= 2 and kw not in STANDALONE_BLOCKED:
            base_keywords.append(kw)

    # From category (split by comma)
    if place_data.category:
        for cat in place_data.category.split(","):
            cat = cat.strip()
            if cat and len(cat) >= 2 and cat not in base_keywords:
                base_keywords.append(cat)

    # From menus (restaurant only)
    if business_type == "restaurant":
        for menu in place_data.menus[:15]:
            if menu and len(menu) >= 2 and menu not in base_keywords:
                base_keywords.append(menu)

    # From medical subjects (hospital only)
    if business_type == "hospital":
        for subj in place_data.medical_subjects:
            if subj and len(subj) >= 2 and subj not in base_keywords:
                base_keywords.append(subj)

    # Modifiers from review themes
    modifiers: List[str] = list(MANDATORY_MODIFIERS)
    if business_type == "restaurant":
        for rk in place_data.review_theme_keywords:
            mapped = THEME_MAPPING.get(rk.label, [])
            for m in mapped[:2]:
                if m not in modifiers:
                    modifiers.append(m)

    # Build keyword pool
    pool: List[Dict] = []
    seen: Set[str] = set()

    def _add(keyword: str, source: str, priority: int):
        kw = keyword.strip()
        if kw and len(kw) >= 2 and kw not in seen:
            seen.add(kw)
            pool.append({"keyword": kw, "source": source, "priority": priority})

    # --- R1: region + business type keyword (highest priority) ---
    for region in regions[:20]:
        for biz_kw in biz_keywords:
            _add(f"{region} {biz_kw}", "R1-region-biz", 1)

    # --- R2: region + name keyword ---
    name_target = int(target_count * name_keyword_ratio)
    for region in regions[:15]:
        for name_part in name_parts[:5]:
            _add(f"{region} {name_part}", "R2-region-name", 2)
            if len(pool) >= name_target + len(regions) * len(biz_keywords):
                break

    # --- R3: region + category ---
    for region in regions[:15]:
        for cat in base_keywords[:5]:
            _add(f"{region} {cat}", "R3-region-category", 3)

    # --- R4: region + menu/service ---
    for region in regions[:12]:
        for kw in base_keywords[5:15]:
            _add(f"{region} {kw}", "R4-region-menu", 4)

    # --- R5: region + modifier ---
    for region in regions[:10]:
        for mod in modifiers[:6]:
            _add(f"{region} {mod}", "R5-region-modifier", 5)

    # --- R6: region + biz_keyword + modifier ---
    for region in regions[:8]:
        for biz_kw in biz_keywords:
            for mod in modifiers[:4]:
                _add(f"{region} {biz_kw} {mod}", "R6-region-biz-mod", 6)

    # --- R7: region + name + biz_keyword ---
    for region in regions[:8]:
        for name_part in name_parts[:3]:
            for biz_kw in biz_keywords[:2]:
                _add(f"{region} {name_part} {biz_kw}", "R7-region-name-biz", 7)

    # --- R8: name alone (PLT candidates) ---
    for name_part in name_parts:
        _add(name_part, "R8-name-only", 8)

    # --- R9: category + modifier ---
    for cat in base_keywords[:8]:
        for mod in modifiers[:4]:
            _add(f"{cat} {mod}", "R9-category-mod", 9)

    # --- R10: region + menu + modifier ---
    for region in regions[:6]:
        for menu in base_keywords[:6]:
            for mod in modifiers[:3]:
                _add(f"{region} {menu} {mod}", "R10-region-menu-mod", 10)

    logger.info(
        "Generated keyword pool: %d keywords (target: %d)",
        len(pool),
        target_count,
    )

    # Sort by priority and trim to target
    pool.sort(key=lambda x: x["priority"])
    if len(pool) > target_count * 3:
        pool = pool[: target_count * 3]

    return pool
