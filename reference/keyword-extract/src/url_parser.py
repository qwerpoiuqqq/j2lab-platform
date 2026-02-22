"""
네이버 플레이스 URL 파서

URL에서 업종 타입과 MID(플레이스 고유 ID)를 추출합니다.
"""

import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class PlaceType(Enum):
    """플레이스 업종 타입"""
    RESTAURANT = "restaurant"  # 맛집/음식점
    HOSPITAL = "hospital"      # 병의원
    HAIRSHOP = "hairshop"      # 미용실
    NAILSHOP = "nailshop"      # 네일샵
    PLACE = "place"            # 일반 업종
    UNKNOWN = "unknown"        # 알 수 없음


@dataclass
class ParsedURL:
    """파싱된 URL 정보"""
    original_url: str
    place_type: PlaceType
    mid: str
    is_valid: bool
    error_message: Optional[str] = None


def parse_place_url(url: str) -> ParsedURL:
    """
    네이버 플레이스 URL을 파싱하여 업종과 MID를 추출합니다.
    
    지원 URL 형식:
    - https://m.place.naver.com/restaurant/12345678
    - https://m.place.naver.com/hospital/12345678/home
    - https://m.place.naver.com/place/12345678/information
    - https://place.naver.com/restaurant/12345678
    - https://naver.me/xxxxx (단축 URL - 미지원, 확장 필요)
    
    Args:
        url: 네이버 플레이스 URL
        
    Returns:
        ParsedURL: 파싱 결과
    """
    # URL 정규화
    url = url.strip()
    
    # 패턴: place.naver.com/{업종}/{MID}
    pattern = r'(?:https?://)?(?:m\.)?place\.naver\.com/(\w+)/(\d+)'
    match = re.search(pattern, url)
    
    if not match:
        return ParsedURL(
            original_url=url,
            place_type=PlaceType.UNKNOWN,
            mid="",
            is_valid=False,
            error_message="지원되지 않는 URL 형식입니다."
        )
    
    place_type_str = match.group(1).lower()
    mid = match.group(2)
    
    # 업종 타입 매핑
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
        is_valid=True
    )


def get_place_type_korean(place_type: PlaceType) -> str:
    """업종 타입의 한글명 반환"""
    names = {
        PlaceType.RESTAURANT: "맛집/음식점",
        PlaceType.HOSPITAL: "병의원",
        PlaceType.HAIRSHOP: "미용실",
        PlaceType.NAILSHOP: "네일샵",
        PlaceType.PLACE: "일반 업종",
        PlaceType.UNKNOWN: "알 수 없음",
    }
    return names.get(place_type, "알 수 없음")


# 테스트
if __name__ == "__main__":
    test_urls = [
        "https://m.place.naver.com/restaurant/1082820234",
        "https://m.place.naver.com/hospital/1984640040/home",
        "https://m.place.naver.com/hairshop/1210917989/information",
        "https://place.naver.com/place/1573829847",
        "https://m.place.naver.com/nailshop/123456789",
        "https://invalid-url.com/test",
    ]
    
    print("=" * 60)
    print("네이버 플레이스 URL 파서 테스트")
    print("=" * 60)
    
    for url in test_urls:
        result = parse_place_url(url)
        print(f"\nURL: {url}")
        print(f"  유효: {result.is_valid}")
        if result.is_valid:
            print(f"  업종: {get_place_type_korean(result.place_type)}")
            print(f"  MID: {result.mid}")
        else:
            print(f"  에러: {result.error_message}")
