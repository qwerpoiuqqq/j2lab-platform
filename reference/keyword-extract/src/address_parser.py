"""
주소 정규화 모듈
도로명/지번 주소에서 시, 구, 동, 역명을 추출

예시:
- "경기 고양시 일산동구 장항동 864" →
  city=경기, si=고양시, gu=일산동구, dong=장항동, major_area=일산
"""
import re
from typing import Optional, List
from .models import RegionInfo


class AddressParser:
    """한국 주소를 파싱하여 지역 정보를 추출"""

    # 정규표현식 패턴
    CITY_PATTERN = re.compile(r'^(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)')

    # 시 추출 (도 단위 내의 시: 고양시, 수원시 등)
    # 약칭(경북, 경남, 전북, 전남, 충북, 충남)도 포함
    SI_PATTERN = re.compile(r'(?:경기도?|강원도?|충[남북]도?|전[남북]도?|경[남북]도?|충청[남북]?도?|전라[남북]?도?|경상[남북]?도?|제주도?)\s+([가-힣]{1,5}시)\s')

    # 군 추출 (도 단위 내의 군: 청도군, 영덕군, 울릉군 등)
    # 약칭(경북, 경남, 전북, 전남, 충북, 충남)도 포함
    GUN_PATTERN = re.compile(r'(?:경기도?|강원도?|충[남북]도?|전[남북]도?|경[남북]도?|충청[남북]?도?|전라[남북]?도?|경상[남북]?도?|제주도?)\s+([가-힣]{1,5}군)\s')

    # 구/군 추출 - 시 다음에 오는 구/군 (일산동구, 일산서구, 중구, 강남구 등)
    GU_PATTERN = re.compile(r'(?:시)\s+([가-힣]{1,6}[구군])\s')

    # 특별/광역시 내 구 추출 (서울 강남구, 부산 해운대구 등)
    METRO_GU_PATTERN = re.compile(r'(?:서울|부산|대구|인천|광주|대전|울산)\s+([가-힣]{1,4}[구군])\s')

    # 동/읍/면 추출
    DONG_PATTERN = re.compile(r'([가-힣]+[동읍면])\s+\d')  # "장항동 864" 형태

    # 도로명 추출 (OO로, OO길)
    ROAD_PATTERN = re.compile(r'([가-힣]+[로길])\d*번?길?\s')

    # 역 이름 추출 패턴들
    STATION_PATTERNS = [
        re.compile(r'([가-힣]+역)\s*\d*번?\s*출구'),  # "정발산역 1번 출구"
        re.compile(r'([가-힣]+역)\s*,'),  # "정발산역 ,"
        re.compile(r'([가-힣]+역)\s+'),  # "정발산역 "
    ]

    # 주요 지역명 추출 (일산동구 → 일산, 분당구 → 분당)
    # NOTE: 중구/남구/동구/북구/서구는 여러 도시에 존재하므로 제외
    #       (city 기반 동적 매핑은 _get_major_area()에서 처리)
    MAJOR_AREA_MAP = {
        # 경기도
        "일산동구": "일산", "일산서구": "일산",
        "분당구": "분당", "수정구": "성남", "중원구": "성남",
        "영통구": "수원", "장안구": "수원", "권선구": "수원", "팔달구": "수원",
        "덕양구": "고양",
        "상록구": "안산", "단원구": "안산",
        "처인구": "용인", "기흥구": "용인", "수지구": "용인",
        "중앙구": "안양", "만안구": "안양",
        "원미구": "부천", "소사구": "부천", "오정구": "부천",
        # 서울
        "강남구": "강남", "강서구": "강서", "강북구": "강북", "강동구": "강동",
        "서초구": "서초", "송파구": "송파", "마포구": "마포", "영등포구": "영등포",
        "종로구": "종로", "용산구": "용산", "성동구": "성동",
        "광진구": "광진", "동대문구": "동대문", "중랑구": "중랑",
        "성북구": "성북", "도봉구": "도봉", "노원구": "노원",
        "은평구": "은평", "서대문구": "서대문",
        "양천구": "양천", "구로구": "구로", "금천구": "금천",
        "관악구": "관악", "동작구": "동작",
        # 부산
        "해운대구": "해운대", "수영구": "수영",
        # 인천
        "남동구": "남동", "부평구": "부평", "계양구": "계양",
        "미추홀구": "미추홀", "연수구": "연수",
        # 대구
        "수성구": "수성", "달서구": "달서",
    }

    # 광역시별 공통 구(중구/남구/동구/북구/서구) → city 기반 매핑
    METRO_GENERIC_GU_MAP = {
        "서울": {"중구": "", "동구": "", "서구": ""},
        "부산": {"중구": "", "남구": "", "동구": "", "북구": "", "서구": ""},
        "대구": {"중구": "", "남구": "", "동구": "", "북구": "", "서구": ""},
        "인천": {"중구": "", "동구": "", "남구": "", "부평구": "부평"},
        "광주": {"중구": "", "남구": "", "동구": "", "북구": "", "서구": ""},
        "대전": {"중구": "", "동구": "", "서구": ""},
        "울산": {"중구": "", "남구": "", "동구": "", "북구": ""},
    }

    def parse(self, address: str, road_info: Optional[str] = None) -> RegionInfo:
        """
        주소 문자열을 파싱하여 RegionInfo 반환

        Args:
            address: 도로명 또는 지번 주소
            road_info: 길찾기/교통 정보 문자열 (역 정보 추출용)
        """
        region = RegionInfo()

        if not address:
            return region

        # 시/도 추출
        city_match = self.CITY_PATTERN.search(address)
        if city_match:
            region.city = city_match.group(1)

        # 시 추출 (경기도 등 도 단위 내의 시)
        si_match = self.SI_PATTERN.search(address)
        if si_match:
            region.si = si_match.group(1)
            region.si_without_suffix = re.sub(r'시$', '', region.si)

        # 군 추출 (도 단위 내의 군: 청도군, 영덕군 등)
        # 군 단위 주소는 시가 없으므로 군을 gu 필드에 저장
        if not region.si:
            gun_match = self.GUN_PATTERN.search(address)
            if gun_match:
                region.gu = gun_match.group(1)
                region.gu_without_suffix = re.sub(r'군$', '', region.gu)

        # 구/군 추출 (시 다음에 오는 구)
        if not region.gu:
            gu_match = self.GU_PATTERN.search(address)
            if gu_match:
                region.gu = gu_match.group(1)
            else:
                # 특별/광역시 내 구 추출
                metro_gu_match = self.METRO_GU_PATTERN.search(address)
                if metro_gu_match:
                    region.gu = metro_gu_match.group(1)

        if region.gu:
            # 구 접미사 제거 버전
            region.gu_without_suffix = re.sub(r'[구군]$', '', region.gu)
            # 주요 지역명 추출 (일산동구 → 일산)
            region.major_area = self.MAJOR_AREA_MAP.get(region.gu, "")
            # 공통 구(중구/남구 등)는 MAJOR_AREA_MAP에 없으므로
            # city 기반으로 major_area 미설정 (gu 자체가 키워드로 사용됨)

        # 동/읍/면 추출
        dong_match = self.DONG_PATTERN.search(address)
        if dong_match:
            region.dong = dong_match.group(1)
            region.dong_without_suffix = re.sub(r'[동읍면]$', '', region.dong)

        # 도로명 추출 (OO로)
        road_match = self.ROAD_PATTERN.search(address)
        if road_match:
            region.road = road_match.group(1)

        # 역 이름 추출 (road_info에서)
        if road_info:
            stations = self._extract_stations(road_info)
            region.stations = stations

        return region

    def _extract_stations(self, text: str) -> List[str]:
        """텍스트에서 지하철역 이름 추출"""
        stations = []
        if not text:
            return stations

        for pattern in self.STATION_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                if match and match not in stations:
                    # "역" 없으면 추가
                    station = match if match.endswith("역") else f"{match}역"
                    if station not in stations:
                        stations.append(station)

        return stations

    def parse_from_apollo_data(self, place_data: dict) -> RegionInfo:
        """
        Apollo State 데이터에서 직접 RegionInfo 생성

        Args:
            place_data: PlaceDetailBase 객체의 딕셔너리
        """
        # 지번 주소가 더 정확한 동 정보를 가짐
        jibun = place_data.get('address', '')
        road_addr = place_data.get('roadAddress', '')
        road_info = place_data.get('road', '')  # 길찾기 정보 (역 정보 포함)

        # 우선 지번에서 파싱
        region = self.parse(jibun, road_info)

        # 도로명 주소에서 추가 정보 파싱
        road_region = self.parse(road_addr)

        # 지번에서 못 찾은 정보는 도로명에서 보완
        if not region.si:
            region.si = road_region.si
            region.si_without_suffix = road_region.si_without_suffix

        if not region.gu:
            region.gu = road_region.gu
            region.gu_without_suffix = road_region.gu_without_suffix
            region.major_area = road_region.major_area

        # 도로명(OO로)은 도로명 주소에서 추출
        if road_region.road:
            region.road = road_region.road

        return region
