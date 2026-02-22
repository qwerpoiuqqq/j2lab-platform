"""
데이터 모델 정의
네이버 플레이스에서 수집한 정보를 담는 구조체들
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class RegionInfo:
    """주소에서 추출한 지역 정보"""
    city: str = ""          # 시/도 (서울, 경기 등)
    si: str = ""            # 시 (고양시, 수원시 등 - 경기도 내)
    gu: str = ""            # 구 (강남구, 일산동구 등)
    dong: str = ""          # 동 (역삼동, 장항동 등)
    road: str = ""          # 도로명 (테헤란로, 중앙로 등)

    # 변형 키워드 생성용
    si_without_suffix: str = ""   # 고양 (시 제거)
    gu_without_suffix: str = ""   # 강남 (구 제거)
    dong_without_suffix: str = "" # 역삼 (동 제거)
    major_area: str = ""          # 주요 지역명 (일산 - 일산동구/일산서구에서 추출)

    # 지하철역 정보
    stations: List[str] = field(default_factory=list)  # 근처 역들 (정발산역, 마두역 등)

    # 지역 접미 수식어
    LOCATION_SUFFIXES = ["근처", "주변", "부근", "가까운"]

    @property
    def station(self) -> str:
        """하위 호환성: 첫 번째 역 반환"""
        return self.stations[0] if self.stations else ""

    @station.setter
    def station(self, value: str):
        """하위 호환성: 역 설정"""
        if value:
            if not self.stations:
                self.stations = [value]
            elif value not in self.stations:
                self.stations.insert(0, value)

    # 전국에 중복으로 존재하는 동 이름 (단독 사용 시 검색 결과 부정확)
    # 이 목록에 없는 동은 유일한 것으로 간주하여 단독 사용 허용
    DUPLICATE_DONG_NAMES = {
        # 서울/경기 중복
        "역삼동", "역삼", "신사동", "신사", "삼성동", "삼성", "대치동", "대치",
        "청담동", "청담", "논현동", "논현", "서초동", "서초", "방배동", "방배",
        "잠실동", "잠실", "송파동", "송파", "강동", "강서동", "강서",
        "고덕동", "고덕",  # 서울 강동구, 평택시 등
        "길동", "암사동", "암사", "천호동", "천호", "둔촌동", "둔촌",
        "영등포동", "영등포", "여의도동", "여의도", "마포동", "마포",
        "용산동", "용산", "성북동", "성북", "동대문", "서대문",
        "중앙동", "중앙", "신정동", "신정", "신월동", "신월",
        "목동", "등촌동", "등촌", "화곡동", "화곡", "개봉동", "개봉",
        "구로동", "구로", "금천동", "금천", "관악동", "관악",
        "동작동", "동작", "사당동", "사당", "노원동", "노원",
        "도봉동", "도봉", "수유동", "수유", "쌍문동", "쌍문",
        "창동", "월계동", "월계", "공릉동", "공릉", "하계동", "하계",
        "중계동", "중계", "상계동", "상계", "태릉", "석계동", "석계",
        "신림동", "신림", "봉천동", "봉천", "낙성대동", "낙성대",
        "신대방동", "신대방", "흑석동", "흑석",
        # 전국 공통 중복 (OO동 형태)
        "신흥동", "신흥", "행정동", "행정", "행복동", "행복",
        "남산동", "남산", "북산동", "북산", "동산동", "동산", "서산동", "서산",
        "명동", "본동", "신동", "구동", "상동", "하동",
        "내동", "외동", "대동", "소동", "장동", "단동",
        "남동", "북동", "동동", "서동",
        "성내동", "성내", "성외동", "성외", "성남동", "성남",
        "신창동", "신창", "구창동", "구창",
        "도화동", "도화", "산곡동", "산곡", "부평동", "부평",
        "인천동", "수원동", "수원", "안양동", "안양",
        "부천동", "부천", "광명동", "광명", "시흥동", "시흥",
        "평촌동", "평촌", "범계동", "범계", "안산동", "안산",
        "일산동", "일산", "분당동", "분당", "판교동", "판교",
        "동탄동", "동탄", "광교동", "광교", "영통동", "영통",
        "매탄동", "매탄", "권선동", "권선", "장안동", "장안",
        "송내동", "송내", "중동", "상동", "소사동", "소사",
        "오정동", "오정", "원미동", "원미",
        # 광역시 중복
        "해운대", "서면", "남포동", "남포", "동래동", "동래",
        "연산동", "연산", "부전동", "부전", "범일동", "범일",
        "대연동", "대연", "용호동", "용호", "광안동", "광안",
        "수영동", "수영", "민락동", "민락", "센텀",
        "동구", "서구", "남구", "북구", "중구",
        "유성동", "유성", "둔산동", "둔산", "월평동", "월평",
        "봉명동", "봉명", "탄방동", "탄방", "관저동", "관저",
        "충무동", "충무", "동명동", "동명", "서명동", "서명",
        "북성동", "북성", "남성동", "남성",
        # 인천 중복
        "구월동", "구월", "간석동", "간석", "만수동", "만수",
        "논현동", "논현", "연수동", "연수", "송도동", "송도",
    }

    def get_keyword_variations(self) -> List[str]:
        """
        지역 키워드 변형 조합 생성 - 모든 가능한 조합

        레벨별 분류:
        - L0: 시/도 (경기, 서울 등) - 단독 사용 X, 조합에서만
        - L1: 시 (평택시, 평택, 고양시, 고양 등) - 단독 사용 O
        - L2: 구 (일산동구, 일산동 등) - 단독 사용 O
        - L3: 동 (고덕동, 고덕 등) - 중복 동은 조합에서만
        - L4: 역 (정발산역, 정발산 등) - 단독 사용 O
        - L5: 도로명 (중앙로 등) - 단독 사용 X

        조합 규칙:
        1. 모든 레벨 조합: L0+L1, L0+L2, L0+L3, L1+L2, L1+L3, L2+L3, L0+L1+L3 등
        2. 모든 조합 + 수식어: 근처, 주변, 부근, 가까운
        3. 중복 동은 단독 사용 X, 상위 레벨과 조합에서만 사용
        """
        variations = []
        all_combos = []  # 2개 조합 저장 (수식어 붙일 용도)

        # === 레벨별 지역 수집 ===
        province_list = []      # L0: 시/도 (경기) - 단독 X
        city_list = []          # L1: 시 (평택시, 평택)
        gu_list = []            # L2: 구 (일산동구, 일산동)
        dong_list = []          # L3: 동 (고덕동, 고덕) - 모든 동
        unique_dong_list = []   # L3-유일: 단독 사용 가능
        duplicate_dong_list = [] # L3-중복: 조합에서만
        station_list = []       # L4: 역 (정발산역, 정발산)

        # 시/도 (경기, 서울 등) - 단독 사용 X
        if self.city:
            province_list.append(self.city)

        # 시 (평택시, 평택 등) - 단독 사용 OK
        if self.si:
            city_list.append(self.si)
        if self.si_without_suffix and self.si_without_suffix not in city_list:
            city_list.append(self.si_without_suffix)

        # 주요 지역명 (일산 - 일산동구에서 추출) - 단독 사용 OK
        if self.major_area and self.major_area not in city_list:
            city_list.append(self.major_area)

        # 구 (일산동구, 일산동 등) - 단독 사용 OK
        if self.gu:
            gu_list.append(self.gu)
        if self.gu_without_suffix and len(self.gu_without_suffix) >= 2 and self.gu_without_suffix not in gu_list:
            gu_list.append(self.gu_without_suffix)

        # 동 (고덕동, 고덕 등) - 중복 판별
        if self.dong:
            dong_list.append(self.dong)
            if self.dong in self.DUPLICATE_DONG_NAMES:
                duplicate_dong_list.append(self.dong)
            else:
                unique_dong_list.append(self.dong)
        if self.dong_without_suffix and self.dong_without_suffix not in dong_list:
            dong_list.append(self.dong_without_suffix)
            if self.dong_without_suffix in self.DUPLICATE_DONG_NAMES:
                if self.dong_without_suffix not in duplicate_dong_list:
                    duplicate_dong_list.append(self.dong_without_suffix)
            else:
                if self.dong_without_suffix not in unique_dong_list:
                    unique_dong_list.append(self.dong_without_suffix)

        # 역 (정발산역, 정발산 등) - 단독 사용 OK
        for station in self.stations:
            if station:
                station_list.append(station)
                station_name = station.replace("역", "")
                if station_name and len(station_name) >= 2 and station_name not in station_list:
                    station_list.append(station_name)

        # === 1단계: 단독 사용 가능한 지역 추가 ===
        # 시/도는 단독 사용 X
        for city in city_list:
            if city not in variations:
                variations.append(city)
        for gu in gu_list:
            if gu not in variations:
                variations.append(gu)
        for dong in unique_dong_list:  # 유일한 동만
            if dong not in variations:
                variations.append(dong)
        for station in station_list:
            if station not in variations:
                variations.append(station)

        # === 2단계: 2개 조합 ===
        # 시/도 + 시 (경기 평택, 경기 평택시)
        for prov in province_list:
            for city in city_list:
                if prov != city:
                    combo = f"{prov} {city}"
                    if combo not in variations:
                        variations.append(combo)
                        all_combos.append(combo)

        # 시/도 + 구 (경기 일산동구)
        for prov in province_list:
            for gu in gu_list:
                combo = f"{prov} {gu}"
                if combo not in variations:
                    variations.append(combo)
                    all_combos.append(combo)

        # 시/도 + 동 (경기 고덕동) - 모든 동
        for prov in province_list:
            for dong in dong_list:
                combo = f"{prov} {dong}"
                if combo not in variations:
                    variations.append(combo)
                    all_combos.append(combo)

        # 시 + 구 (고양 일산동구)
        for city in city_list:
            for gu in gu_list:
                if city != gu and city not in gu:
                    combo = f"{city} {gu}"
                    if combo not in variations:
                        variations.append(combo)
                        all_combos.append(combo)

        # 시 + 동 (평택 고덕, 평택시 고덕동) - 모든 동
        for city in city_list:
            for dong in dong_list:
                if city != dong:
                    combo = f"{city} {dong}"
                    if combo not in variations:
                        variations.append(combo)
                        all_combos.append(combo)

        # 구 + 동 (일산 장항)
        for gu in gu_list:
            for dong in dong_list:
                if gu != dong and dong not in gu:
                    combo = f"{gu} {dong}"
                    if combo not in variations:
                        variations.append(combo)
                        all_combos.append(combo)

        # 시 + 역 (고양 정발산역)
        for city in city_list:
            for station in station_list:
                combo = f"{city} {station}"
                if combo not in variations:
                    variations.append(combo)
                    all_combos.append(combo)

        # 구 + 역 (일산 정발산역)
        for gu in gu_list:
            for station in station_list:
                combo = f"{gu} {station}"
                if combo not in variations:
                    variations.append(combo)
                    all_combos.append(combo)

        # 시/도 + 역 (경기 정발산역)
        for prov in province_list:
            for station in station_list:
                combo = f"{prov} {station}"
                if combo not in variations:
                    variations.append(combo)
                    all_combos.append(combo)

        # === 3단계: 도로명 조합 ===
        if self.road:
            # 도로명 단독 (월미문화로)
            if self.road not in variations:
                variations.append(self.road)
            # 시/도 + 도로명 (인천 월미문화로)
            for prov in province_list:
                road_combo = f"{prov} {self.road}"
                if road_combo not in variations:
                    variations.append(road_combo)
                    all_combos.append(road_combo)
            for city in city_list[:4]:
                road_combo = f"{city} {self.road}"
                if road_combo not in variations:
                    variations.append(road_combo)
                    all_combos.append(road_combo)
            for gu in gu_list[:2]:
                road_combo = f"{gu} {self.road}"
                if road_combo not in variations:
                    variations.append(road_combo)
                    all_combos.append(road_combo)

        # === 4단계: 3개 조합 (주요 조합만) ===
        # 시/도 + 시 + 동 (경기 평택 고덕)
        for prov in province_list[:1]:
            for city in city_list[:2]:
                for dong in dong_list[:2]:
                    if prov != city and city != dong:
                        combo = f"{prov} {city} {dong}"
                        if combo not in variations:
                            variations.append(combo)
                            all_combos.append(combo)

        # === 5단계: 수식어 조합 ===
        # 단독 지역 + 수식어
        for city in city_list:
            for suffix in self.LOCATION_SUFFIXES:
                suffix_combo = f"{city} {suffix}"
                if suffix_combo not in variations:
                    variations.append(suffix_combo)

        for gu in gu_list:
            for suffix in self.LOCATION_SUFFIXES:
                suffix_combo = f"{gu} {suffix}"
                if suffix_combo not in variations:
                    variations.append(suffix_combo)

        for dong in unique_dong_list:  # 유일한 동만
            for suffix in self.LOCATION_SUFFIXES:
                suffix_combo = f"{dong} {suffix}"
                if suffix_combo not in variations:
                    variations.append(suffix_combo)

        for station in station_list:
            for suffix in self.LOCATION_SUFFIXES:
                suffix_combo = f"{station} {suffix}"
                if suffix_combo not in variations:
                    variations.append(suffix_combo)
                # 붙여쓰기 (정발산역근처)
                if station.endswith("역"):
                    attached = f"{station}{suffix}"
                    if attached not in variations:
                        variations.append(attached)

        # 2개 조합 + 수식어 (상위 30개)
        for combo in all_combos[:30]:
            for suffix in self.LOCATION_SUFFIXES:
                suffix_combo = f"{combo} {suffix}"
                if suffix_combo not in variations:
                    variations.append(suffix_combo)

        # 중복 제거 및 필터링
        seen = set()
        result = []
        for v in variations:
            v = v.strip()
            if v and len(v) >= 2 and v not in seen:
                seen.add(v)
                result.append(v)

        return result


@dataclass
class ReviewKeyword:
    """리뷰 탭에서 추출한 키워드 (메뉴/특징)"""
    label: str          # 키워드 이름 (예: "파스타", "분위기")
    count: int = 0      # 언급 횟수


@dataclass
class PlaceData:
    """플레이스 전체 정보"""
    # 기본 정보
    id: str = ""
    name: str = ""
    category: str = ""
    
    # 주소
    road_address: str = ""    # 도로명 주소
    jibun_address: str = ""   # 지번 주소
    region: RegionInfo = field(default_factory=RegionInfo)
    
    # 연락처
    phone: str = ""
    virtual_phone: str = ""
    
    # 키워드 및 태그
    keywords: List[str] = field(default_factory=list)       # 대표 키워드
    conveniences: List[str] = field(default_factory=list)   # 편의시설
    micro_reviews: List[str] = field(default_factory=list)  # 마이크로 리뷰 태그
    
    # 리뷰 탭 키워드 (핵심!)
    review_menu_keywords: List[ReviewKeyword] = field(default_factory=list)   # 파스타, 스테이크 등
    review_theme_keywords: List[ReviewKeyword] = field(default_factory=list)  # 맛, 분위기, 가성비 등
    voted_keywords: List[ReviewKeyword] = field(default_factory=list)         # 넓어요, 편해요 (투표)
    
    # 추가 상세 정보
    payment_info: List[str] = field(default_factory=list)  # 제로페이, 네이버페이
    seat_items: List[str] = field(default_factory=list)    # 단체석, 연인석
    
    # 업종별 특화 정보
    specialties: List[str] = field(default_factory=list)    # 진료과목, 스타일 등
    menus: List[str] = field(default_factory=list)          # 메뉴 (메뉴 탭 데이터)
    
    # 병의원 전용 정보
    medical_subjects: List[str] = field(default_factory=list) # 진료과목 (피부과, 성형외과 등)
    introduction: str = "" # 소개글 (주요 시술/특장점 추출용)

    # 예약 정보 (2026-01-15 추가)
    has_booking: bool = False  # 예약 기능 여부
    booking_type: Optional[str] = None  # "realtime" (네이버예약) 또는 "url" (외부예약)
    booking_hub_id: Optional[str] = None  # 네이버예약 허브 ID
    booking_url: Optional[str] = None  # 외부 예약 URL

    # 메타 정보
    url: str = ""
    
    # 2026-01-05 추가: 대표 키워드에서 발견된 지역명 (예: 사계해변, 산방산)
    def __post_init__(self):
        # field(default_factory=set)이 dataclass에서 동작하려면 
        # 이렇게 초기화하거나 field import가 필요. 위에 field가 import 되어있으므로
        # 필드 선언에서 바로 해도 됨.
        pass

    discovered_regions: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환 (JSON 저장용)"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "road_address": self.road_address,
            "jibun_address": self.jibun_address,
            "region": {
                "city": self.region.city,
                "si": self.region.si,
                "gu": self.region.gu,
                "dong": self.region.dong,
                "road": self.region.road,
                "major_area": self.region.major_area,
                "stations": self.region.stations,
                "keyword_variations": self.region.get_keyword_variations()
            },
            "phone": self.phone,
            "keywords": self.keywords,
            "conveniences": self.conveniences,
            "review_menu_keywords": [{"label": k.label, "count": k.count} for k in self.review_menu_keywords],
            "review_theme_keywords": [{"label": k.label, "count": k.count} for k in self.review_theme_keywords],
            "voted_keywords": [{"label": k.label, "count": k.count} for k in self.voted_keywords],
            "payment_info": self.payment_info,
            "seat_items": self.seat_items,
            "specialties": self.specialties,
            "medical_subjects": self.medical_subjects,
            "introduction": self.introduction,
            "url": self.url,
            "discovered_regions": list(self.discovered_regions),
            "has_booking": self.has_booking,
            "booking_type": self.booking_type,
            "booking_hub_id": self.booking_hub_id,
            "booking_url": self.booking_url,
        }
