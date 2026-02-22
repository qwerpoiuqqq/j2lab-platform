"""
Smart Keyword Worker v2
최적화된 키워드 생성 및 순위 체크 로직

[핵심 아키텍처]
- Phase 0: 데이터 추출 + 상호명 파싱
- Phase 1: 대표 샘플 검증 (메뉴당 1회만 검사)
- Phase 2: 계층적 키워드 풀 생성 (크롤링 없음)
- Phase 3: 비율 조정 (신/구지도 + 지도 키워드)
- Phase 4: 최종 순위 크롤링 (목표 개수만)
"""
import copy
import os
import re
import random
import asyncio
import threading
from itertools import combinations
from typing import List, Set, Dict, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from .place_scraper import PlaceScraper, PlaceData
from .keyword_generator import KeywordGenerator
from .rank_checker import RankChecker, RankResult
from .gemini_client import get_gemini_client

# API 모드 (속도 10배 향상) - aiohttp 필요
try:
    from .rank_checker_api import RankCheckerAPI, check_ranks_api
    HAS_API_MODE = True
except ImportError:
    HAS_API_MODE = False
    print("[SmartWorker] API 모드 사용 불가 (aiohttp 미설치). pip install aiohttp")

# GraphQL 모드 (가장 안정적이고 빠름)
try:
    from .rank_checker_graphql import RankCheckerGraphQL, ProxyConfig, check_ranks_graphql, CITY_COORDINATES
    HAS_GRAPHQL_MODE = True
except ImportError:
    HAS_GRAPHQL_MODE = False
    # Fallback: rank_checker에서 ProxyConfig import
    from .rank_checker import ProxyConfig
    print("[SmartWorker] GraphQL 모드 사용 불가")


class SmartWorker(QThread):
    """
    최적화된 키워드 작업 워커
    
    [주요 개선점]
    - 대표 1개 검증 → 전체 확정 (크롤링 85% 감소)
    - 계층적 키워드 조합 (L1~L4)
    - 실시간 [현재/목표] 카운트
    - 조기 중단 지원
    """
    
    # 시그널 정의
    progress = pyqtSignal(str)  # 상태 메시지
    sub_progress = pyqtSignal(int, int, str)  # 진행률 (현재, 전체, 메시지)
    error = pyqtSignal(str)  # 에러 메시지
    finished = pyqtSignal(list)  # 최종 결과 (RankResult 리스트)
    preview_ready = pyqtSignal(list, int)  # 미리보기 준비 (키워드 리스트, 생성 개수)
    phase1_data_ready = pyqtSignal(dict)  # Phase 1 완료 후 편집용 데이터 (지역, 키워드, 상호명, 수식어)
    
    # ==================== 상수 정의 ====================
    # 리뷰 테마 -> 검색 필터/수식어 매핑 테이블 (1:N)
    # 브라우저 분석 기반: 실제 플레이스 필터와 연동되는 키워드로 변환
    THEME_MAPPING = {
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
        "청결": ["깨끗한", "청결한"]
    }
    
    # 검색에 부적합하여 제외할 관리용 테마 (매핑되지 않은 나머지)
    NON_SEARCHABLE_THEMES = {
        "청결도", "음식량", "위치", "대기시간", "방역", 
        "배달", "예약", "화장실", "반려동물", "서비스", "만족도", "시설", "규모", "편의"
    }

    # 지역 추론 차단 목록 (시간, 단위 등 지역으로 오인될 수 있는 단어)
    REGION_INFERENCE_BLOCKLIST = {
        "심야", "새벽", "주간", "야간", "24시", "연중무휴", "매일", "주말", "평일",
        "1층", "2층", "지하", "루프탑", "테라스",
        "추천", "유명", "인기", "최고", "전문", "원조",
        # ~면으로 끝나지만 지역 아닌 음식
        "냉면", "비빔냉면", "물냉면", "평양냉면", "함흥냉면", "밀면", "막국수면", "쫄면",
        "라면", "짜장면", "짬뽕면", "우동면", "소바면", "국수면", "칼국수면", "수제비면",
        "볶음면", "비빔면", "잔치국수면", "메밀면"
    }

    # 단독 사용 불가 키워드 (다른 키워드와 조합해야만 사용 가능)
    STANDALONE_BLOCKED = {
        "24시", "아트", "샵", "전문", "추천", "잘하는", "유명한",
        "근처", "주변", "부근", "가까운"
    }

    # 지역 접미 수식어 (역/동 뒤에 붙는 수식어) - "앞" 제거
    LOCATION_SUFFIXES = ["근처", "주변", "부근", "가까운"]

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

    # ==================== 업종 판별 상수 ====================
    # 맛집 관련 카테고리 키워드
    RESTAURANT_CATEGORIES = {
        "음식", "요리", "식당", "카페", "주점", "호프", "맛집",
        "한식", "양식", "일식", "중식", "분식", "뷔페", "레스토랑",
        "고기", "구이", "회", "돈가스", "파스타", "피자", "버거",
        "갈비", "곱창", "국밥", "면", "제과", "베이커리", "디저트",
        "치킨", "족발", "보쌈", "찜", "탕", "전골", "냉면", "칼국수",
        "커피", "브런치", "펍", "바", "이자카야", "선술집"
    }

    # 병의원 관련 카테고리 키워드
    HOSPITAL_CATEGORIES = {
        "병원", "의원", "치과", "한의원", "클리닉", "피부과",
        "정형외과", "신경외과", "내과", "외과", "안과", "이비인후과",
        "재활의학과", "산부인과", "비뇨기과", "성형외과", "마취통증의학과",
        "소아과", "정신과", "신경과", "흉부외과", "심장내과",
        "동물병원", "수의과", "펫클리닉"
    }

    # 업종별 대표 키워드 (하드코딩 기본값, GUI에서 덮어쓰기 가능)
    BUSINESS_TYPE_KEYWORDS = {
        "restaurant": ["맛집", "음식점", "식당"],
        "hospital":   ["병원", "의원", "병의원"],
        "general":    ["전문점", "매장"],
    }

    # 필수 수식어 (모든 업종, 하드코딩)
    MANDATORY_MODIFIERS = ["지도", "추천"]

    # 상호명 1위 조합 비율 기본값 (맛집 한정, 목표 개수 대비 %)
    NAME_RANK1_COMBO_RATIO_DEFAULT = 0.40  # 기본 40%
    
    def __init__(self, url: str, target_count: int, max_rank: int = 50,
                 min_rank: int = 1,  # 최소 순위 (이 순위 이상만 포함)
                 proxies: List[Dict] = None,
                 new_map_ratio: int = 70,
                 use_api_mode: bool = True,  # True: API 직접 호출 (빠름), False: 브라우저 (안정)
                 use_own_ip: bool = True,  # True: 내 IP 포함, False: 프록시만 사용
                 user_slot: int = 0,  # 사용자 슬롯 (0=전체, 1~10=분할)
                 total_instances: int = 1,  # 총 실행 인스턴스 수 (프록시 분배용)
                 modifiers: Dict = None,  # 사용자 정의 수식어
                 # 사용자 편집 데이터 (GUI에서 추출 후 편집된 값)
                 user_regions: List[str] = None,
                 user_keywords: List[str] = None,
                 user_name_parts: List[str] = None,
                 user_modifiers: List[str] = None,
                 user_region_keyword_combos: List[str] = None,  # 지역+키워드 조합
                 place_data=None,  # 이미 추출된 PlaceData
                 booking_keyword_ratio: float = 0.1,  # 실시간 예약 키워드 비율 (기본 10%)
                 basic_only: bool = False,  # True: 기본 조합만 (R1-R2), False: 전체 조합 (R1-R13)
                 name_rank1_combo_ratio: float = 0.40):  # 상호명 1위 조합 비율 (맛집 한정, 목표 개수 대비)
        super().__init__()
        self.url = url
        self.target_count = target_count
        self.max_rank = max_rank
        self.min_rank = min_rank  # 최소 순위
        self.proxies = proxies or []
        self.new_map_ratio = new_map_ratio  # 신지도 비율 (%)
        self.use_api_mode = use_api_mode and HAS_API_MODE  # API 모드 사용 여부
        self.use_own_ip = use_own_ip  # 내 IP 사용 여부
        self.user_slot = user_slot  # 사용자 슬롯 (0=전체, 1~10=분할)
        self.total_instances = total_instances  # 총 실행 인스턴스 수
        self.modifiers = modifiers or {}  # 사용자 정의 수식어
        self.booking_keyword_ratio = booking_keyword_ratio  # 실시간 예약 키워드 비율
        self.basic_only = basic_only  # True: 기본 조합만 (R1-R4), False: 전체 조합 (R1-R14)
        self.name_rank1_combo_ratio = name_rank1_combo_ratio  # 상호명 1위 조합 비율
        self.is_running = True

        # 클래스 변수를 인스턴스로 복사 (멀티 JobWorker 간 오염 방지)
        self._instance_biz_keywords = copy.deepcopy(self.BUSINESS_TYPE_KEYWORDS)

        # 사용자 편집 데이터 저장 (None = 자동 생성, [] = 사용자가 비움)
        self.user_regions = user_regions  # None이면 자동, []이면 지역 없음
        self.user_keywords = user_keywords or []
        self.user_name_parts = user_name_parts or []
        self.user_modifiers_list = user_modifiers or []
        self.user_region_keyword_combos = user_region_keyword_combos or []  # 지역+키워드 조합
        self._user_regions_set = user_regions is not None  # 사용자가 지역을 설정했는지 여부
        self.provided_place_data = place_data  # 이미 추출된 데이터

        # 내부 상태
        self.scraper = None
        self.generator = KeywordGenerator()
        self.rank_checker = None
        self.gemini_client = get_gemini_client()  # AI 기반 키워드 분석
        self._ai_classification = None  # AI 기반 키워드 분류 결과 (ComprehensiveParseResult)

        # 사용자 수식어 적용
        if self.modifiers:
            self._apply_user_modifiers()
        
        self.all_results: List[RankResult] = []
        self.verified_keywords: Set[str] = set()
        
        # Phase 1 검증 결과
        self.validated_keywords: List[str] = []
        self.validated_map_types: Dict[str, str] = {}  # 키워드 -> 지도형태
        
        # 키워드 풀
        self.keyword_pool: List[Dict] = []
        
        # Phase 1 후 사용자 확인 대기 (편집 후 진행)
        self.user_confirmed = False
        self._confirm_event = threading.Event()
        # provided_place_data가 있으면 이미 추출 완료 → 바로 진행
        if self.provided_place_data:
            self.user_confirmed = True
            self._confirm_event.set()

    def _apply_user_modifiers(self):
        """사용자 정의 수식어 적용 (업종 대표 키워드 + GUI 수식어)"""
        if not self.modifiers:
            return

        print(f"[SmartWorker] 사용자 수식어 적용: {list(self.modifiers.keys())}")

        # 업종별 대표 키워드 덮어쓰기 (인스턴스 변수에만 적용 → 클래스 변수 오염 방지)
        if "맛집" in self.modifiers and self.modifiers["맛집"]:
            self._instance_biz_keywords["restaurant"] = self.modifiers["맛집"]
            print(f"  - 맛집 대표키워드: {self.modifiers['맛집']}")

        if "병원" in self.modifiers and self.modifiers["병원"]:
            self._instance_biz_keywords["hospital"] = self.modifiers["병원"]
            print(f"  - 병원 대표키워드: {self.modifiers['병원']}")

        # GUI 수식어는 별도 저장 (하드코딩 MANDATORY_MODIFIERS와 분리)
        self._gui_modifiers = []
        if "추천" in self.modifiers:
            self._gui_modifiers.extend(self.modifiers["추천"])
            print(f"  - 추천 수식어: {self.modifiers['추천']}")
        if "특징" in self.modifiers:
            self._gui_modifiers.extend(self.modifiers["특징"])
            print(f"  - 특징 수식어: {self.modifiers['특징']}")

        # 하드코딩 수식어와 중복 제거
        self._gui_modifiers = [m for m in self._gui_modifiers
                               if m not in self.MANDATORY_MODIFIERS]
        print(f"  - GUI 수식어 (중복 제거 후): {self._gui_modifiers}")

    def _detect_business_type(self, category: str) -> str:
        """
        카테고리에서 업종 유형 판별

        Args:
            category: 플레이스 카테고리 (예: "이탈리아음식", "피부과", "변호사")

        Returns:
            "restaurant" | "hospital" | "general"
        """
        if not category:
            return "general"

        # 맛집 판별
        for kw in self.RESTAURANT_CATEGORIES:
            if kw in category:
                return "restaurant"

        # 병의원 판별
        for kw in self.HOSPITAL_CATEGORIES:
            if kw in category:
                return "hospital"

        return "general"

    def stop(self):
        """작업 중단"""
        self.is_running = False
        if self.rank_checker:
            self.rank_checker.stop()
        # 미리보기 대기 중이면 해제
        self._confirm_event.set()
    
    def confirm_and_proceed(self, edited_data: dict = None):
        """사용자가 편집 확인 후 진행 승인

        Args:
            edited_data: 사용자가 편집한 데이터 (regions, keywords, name_parts, modifiers)
        """
        if edited_data:
            self.user_regions = edited_data.get("regions", [])
            self._user_regions_set = True  # 사용자가 편집함
            self.user_keywords = edited_data.get("keywords", [])
            self.user_name_parts = edited_data.get("name_parts", [])
            self.user_modifiers_list = edited_data.get("modifiers", [])
        self.user_confirmed = True
        self._confirm_event.set()

    def _prepare_phase1_data(self, place_data: PlaceData) -> dict:
        """Phase 1 완료 후 GUI에 전달할 데이터 준비 (형태소 분석 적용)"""
        # 1. 기본 지역 정보 수집 (새 필드 포함)
        base_regions = []

        # 시 (고양시, 고양)
        if place_data.region.si:
            base_regions.append(place_data.region.si)
        if place_data.region.si_without_suffix:
            base_regions.append(place_data.region.si_without_suffix)

        # 주요 지역명 (일산 from 일산동구)
        if place_data.region.major_area:
            base_regions.append(place_data.region.major_area)

        # 구 (일산동구, 일산동)
        if place_data.region.gu:
            base_regions.append(place_data.region.gu)
        if place_data.region.gu_without_suffix:
            base_regions.append(place_data.region.gu_without_suffix)

        # 동 (장항동, 장항)
        if place_data.region.dong:
            base_regions.append(place_data.region.dong)
        if place_data.region.dong_without_suffix:
            base_regions.append(place_data.region.dong_without_suffix)

        # 역
        if place_data.region.station:
            base_regions.append(place_data.region.station)
        # 다중 역 지원
        for station in place_data.region.stations:
            if station and station not in base_regions:
                base_regions.append(station)

        # 도로명
        if place_data.region.road:
            base_regions.append(place_data.region.road)

        # 발견된 지역 추가
        if hasattr(place_data, 'discovered_regions'):
            base_regions.extend(list(place_data.discovered_regions))

        # 중복 제거
        base_regions = list(dict.fromkeys([r for r in base_regions if r]))

        # 2. 지역 조합 자동 생성 (시+동, 역+근처 등)
        regions = self._generate_region_combinations(base_regions)
        print(f"[SmartWorker] 지역 조합 생성: {len(base_regions)}개 → {len(regions)}개")

        # 3. 키워드 수집 (대표키워드, 메뉴, 리뷰키워드)
        keywords = []
        keywords.extend(place_data.keywords)
        keywords.extend(place_data.menus[:10])
        for rk in place_data.review_menu_keywords[:10]:
            if rk.label not in keywords:
                keywords.append(rk.label)
        # 병원: 진료과목
        keywords.extend(place_data.medical_subjects)

        # 4. 단독 사용 불가 키워드 필터링
        keywords = self._filter_standalone_keywords(keywords)

        # 5. 상호명 형태소 분석 (분리 + 조합)
        name_parts = self._parse_business_name_morphemes(place_data.name)
        print(f"[SmartWorker] 상호명 형태소 분석: '{place_data.name}' → {name_parts}")

        # 6. 수식어 (리뷰 테마에서 추출)
        modifiers = []
        for rk in place_data.review_theme_keywords:
            modifiers.append(rk.label)

        return {
            "place_data": place_data,
            "name": place_data.name,
            "category": place_data.category,
            "regions": regions,
            "keywords": list(dict.fromkeys(keywords)),
            "name_parts": name_parts,
            "modifiers": modifiers,
        }

    def _apply_user_edited_data(self, place_data: PlaceData):
        """사용자가 편집한 데이터를 PlaceData에 적용"""
        if self.user_keywords:
            place_data.keywords = self.user_keywords
            print(f"[SmartWorker] 사용자 키워드 적용: {len(self.user_keywords)}개")
        if self.user_name_parts:
            place_data.name_parts = self.user_name_parts
            print(f"[SmartWorker] 사용자 상호명 적용: {self.user_name_parts}")

    def _generate_region_combinations(self, regions: List[str]) -> List[str]:
        """
        지역 조합 자동 생성
        1단계: 개별 지역 (고양, 일산, 정발산역 등) - 동 단위는 단독 사용 금지
        2단계: 지역끼리 2개 조합 (고양 일산, 일산 장항, 정발산 장항 등)
        3단계: 도로명 조합 (일산 중앙로 등)
        4단계: 수식어 조합 (고양 근처, 일산 장항 주변 등)

        ※ 동 단위(역삼동, 장항동 등)는 여러 지역에 동일 이름이 있어
           단독으로 검색 시 순위가 부정확할 수 있으므로 조합으로만 사용
        """
        result = set()

        # === 1단계: 개별 지역 및 분류 ===
        core_regions = []  # 핵심 지역 - 단독 사용 가능 (시, 구, 역)
        dong_regions = []  # 동 단위 - 조합에서만 사용
        station_list = []  # 역 목록
        road_list = []     # 도로명 목록

        for r in regions:
            r_stripped = r.strip()
            if not r_stripped:
                continue

            # 분류
            if r_stripped.endswith("역"):
                station_list.append(r_stripped)
                result.add(r_stripped)  # 역은 단독 사용 OK
                # 역 이름만 추출 (정발산역 → 정발산)
                base = r_stripped[:-1]
                if len(base) >= 2 and base not in core_regions:
                    core_regions.append(base)
                    result.add(base)
            elif r_stripped.endswith("로") or r_stripped.endswith("길"):
                road_list.append(r_stripped)
                # 도로명은 단독 사용 X (조합에서만)
            elif r_stripped.endswith("동"):
                # 동 단위 판별: 중복 동 이름은 조합에서만, 유일한 동은 단독 사용 OK
                base = r_stripped[:-1]
                if r_stripped in self.DUPLICATE_DONG_NAMES or base in self.DUPLICATE_DONG_NAMES:
                    # 중복 동 이름 → 조합에서만 사용
                    dong_regions.append(r_stripped)
                    if len(base) >= 2 and base not in dong_regions:
                        dong_regions.append(base)
                else:
                    # 유일한 동 이름 → 단독 사용 가능
                    result.add(r_stripped)
                    if len(base) >= 2 and base not in core_regions:
                        core_regions.append(base)
                        result.add(base)
            elif r_stripped.endswith("시") or r_stripped.endswith("구"):
                # 시/구는 단독 사용 OK
                result.add(r_stripped)
                base = r_stripped[:-1]
                if len(base) >= 2 and base not in core_regions:
                    core_regions.append(base)
                    result.add(base)
            else:
                # 접미사 없는 지역 (고양, 일산 등) - 단독 사용 OK
                if len(r_stripped) >= 2:
                    result.add(r_stripped)
                    if r_stripped not in core_regions:
                        core_regions.append(r_stripped)

        # === 2단계: 지역끼리 2개 조합 ===
        combo_regions = []

        # 동 단위는 반드시 상위 지역과 조합 (예: "고양 장항", "일산 장항")
        for dong in dong_regions:
            for parent in core_regions[:6]:  # 상위 지역 6개와 조합
                combo = f"{parent} {dong}"
                if combo not in result:
                    result.add(combo)
                    combo_regions.append(combo)

        # 상위 지역끼리 조합 (시/구/역)
        for i, r1 in enumerate(core_regions[:6]):
            for j, r2 in enumerate(core_regions[:6]):
                if i != j and r1 != r2:
                    combo = f"{r1} {r2}"
                    if combo not in result:
                        result.add(combo)
                        combo_regions.append(combo)

        # === 3단계: 도로명 조합 (도로명은 단독 사용 X) ===
        for road in road_list:
            for region in core_regions[:4]:  # 핵심 지역 4개와만 조합
                road_combo = f"{region} {road}"
                if road_combo not in result:
                    result.add(road_combo)

        # === 4단계: 수식어 조합 ===
        # 개별 지역 + 수식어
        for region in core_regions[:6]:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{region} {suffix}")

        # 역 + 수식어 (붙여쓰기 포함)
        for station in station_list:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{station} {suffix}")
                result.add(f"{station}{suffix}")  # 정발산역근처

        # 조합 지역 + 수식어 (고양 일산 근처, 일산 장항 주변 등)
        for combo in combo_regions[:8]:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{combo} {suffix}")

        return list(result)

    def _parse_business_name_morphemes(self, name: str) -> List[str]:
        """
        상호명 형태소 분석 및 조합 생성
        예: "세라믹치과의원" → ["세라믹", "치과", "의원", "세라믹치과", "치과의원", "세라믹치과의원"]
        예: "강남 더 클리닉" → ["강남", "더", "클리닉", "강남클리닉", "더클리닉"]
        """
        result = set()

        # 1. 띄어쓰기로 분리
        space_parts = [p.strip() for p in name.split() if len(p.strip()) >= 2]
        result.update(space_parts)

        # 2. 띄어쓰기 없는 연속 조합
        if len(space_parts) >= 2:
            for i in range(len(space_parts)):
                for j in range(i + 1, len(space_parts) + 1):
                    combo = "".join(space_parts[i:j])
                    if len(combo) >= 2:
                        result.add(combo)

        # 3. AI 기반 형태소 분해 (Gemini 활용)
        try:
            if self.gemini_client.is_available():
                ai_keywords = self.gemini_client.parse_name(name, "")
                if ai_keywords:
                    for token in ai_keywords:
                        if len(token) >= 2:
                            result.add(token)
        except Exception:
            pass

        # 4. 일반적인 접미사 제거 버전
        suffixes_to_strip = ["의원", "병원", "치과", "한의원", "클리닉", "센터", "샵", "아트", "네일",
                              "점", "지점", "본점", "분점", "매장", "호점"]
        name_no_space = name.replace(" ", "")
        for suffix in suffixes_to_strip:
            if name_no_space.endswith(suffix) and len(name_no_space) > len(suffix):
                base = name_no_space[:-len(suffix)]
                if len(base) >= 2:
                    result.add(base)

        return list(result)

    def _filter_standalone_keywords(self, keywords: List[str]) -> List[str]:
        """
        단독 사용 불가 키워드 필터링
        "24시", "아트" 등 단독으로 검색하면 안 되는 키워드 제거
        """
        filtered = []
        for kw in keywords:
            kw_stripped = kw.strip()
            # 단독 사용 불가 목록에 있고, 다른 단어와 조합되지 않은 경우 제외
            if kw_stripped in self.STANDALONE_BLOCKED:
                continue
            # 공백으로 분리했을 때 마지막 단어만 단독불가인 경우도 체크
            parts = kw_stripped.split()
            if len(parts) >= 2:
                # 조합된 키워드는 OK
                filtered.append(kw_stripped)
            elif kw_stripped not in self.STANDALONE_BLOCKED:
                # 단독 키워드인데 차단 목록에 없으면 OK
                filtered.append(kw_stripped)
        return filtered

    def run(self):
        asyncio.run(self._run_async())
        
    async def _run_async(self):
        try:
            # Phase 0: 데이터 추출
            place_data = await self._phase_0_extract_data()
            if not place_data:
                return
            if not self.is_running:
                self._finish_early("Phase 0에서 중단됨")
                return

            # AI 기반 키워드 분류 (Phase 0 이후, Phase 1 이전)
            self._classify_with_ai(place_data)

            # Phase 1: 키워드 검증 (API 모드로 빠르게)
            await self._phase_1_validate_samples(place_data)
            if not self.is_running:
                self._finish_early("Phase 1에서 중단됨")
                return

            # Phase 1 완료 후 사용자 편집 대기 (이미 추출된 데이터가 없을 때만)
            if not self.user_confirmed:
                # 추출된 데이터를 GUI에 전달
                extracted_data = self._prepare_phase1_data(place_data)
                self.phase1_data_ready.emit(extracted_data)
                self.progress.emit("추출 완료 - 정보를 확인/수정 후 [계속] 버튼을 클릭하세요")

                # 사용자 확인 대기
                self._confirm_event.wait()

                if not self.is_running:
                    self._finish_early("사용자가 중단함")
                    return

                # 사용자가 편집한 데이터 적용
                self._apply_user_edited_data(place_data)
                self.progress.emit("사용자 편집 데이터 적용 완료 → Phase 2 시작")

            # Phase 2: 계층적 키워드 풀 생성
            self._phase_2_generate_pool(place_data)
            if not self.is_running:
                self._finish_early("Phase 2에서 중단됨")
                return

            # Phase 3: 비율 조정
            self._phase_3_adjust_ratio(place_data)
            if not self.is_running:
                self._finish_early("Phase 3에서 중단됨")
                return

            # 미리보기 시그널 (UI 업데이트용, 대기 없음)
            preview_keywords = [item["keyword"] for item in self.keyword_pool]
            self.preview_ready.emit(preview_keywords, len(self.keyword_pool))
            self.progress.emit(f"📋 {len(preview_keywords)}개 키워드 생성 → 바로 순위 체크 시작")

            # Phase 4: 최종 순위 크롤링 (목표까지 무한 루프)
            await self._phase_4_final_ranking(place_data)

            # 중단되었든 완료되었든 결과 반환
            if self.is_running:
                self._finish()
            else:
                self._finish_early("사용자가 중단함")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

    # ==================== Phase 0: 데이터 추출 ====================
    async def _phase_0_extract_data(self) -> PlaceData:
        """Phase 0: 플레이스 데이터 추출 + 상호명 파싱

        사용자가 이미 추출한 데이터가 있으면 재사용
        """
        # 이미 추출된 데이터가 있으면 사용
        if self.provided_place_data:
            place_data = self.provided_place_data
            self.progress.emit(f"✅ {place_data.name} (기존 데이터 사용)")

            # 사용자가 편집한 데이터로 덮어쓰기
            if self.user_keywords:
                place_data.keywords = self.user_keywords
                self.progress.emit(f"   사용자 키워드: {len(self.user_keywords)}개")
            if self.user_name_parts:
                place_data.name_parts = self.user_name_parts
                self.progress.emit(f"   사용자 상호명: {self.user_name_parts}")

            return place_data

        # 새로 추출
        self.progress.emit("Phase 0: 플레이스 데이터 분석 중...")

        self.scraper = PlaceScraper()
        async with self.scraper:
            place_data = await self.scraper.get_place_data_by_url(self.url)
            if not place_data:
                raise Exception("플레이스 데이터를 가져올 수 없습니다.")

        self.progress.emit(f"✅ {place_data.name} ({place_data.category})")

        # 상호명 띄어쓰기 파싱
        name_parts = self._parse_business_name(place_data.name)
        if name_parts:
            self.progress.emit(f"   상호명 파싱: {name_parts}")

        # 카테고리 수집 (나중에 매핑용)
        self._save_category(place_data.category)

        # PlaceData에 파싱된 상호명 추가
        if not hasattr(place_data, 'name_parts'):
            place_data.name_parts = name_parts

        return place_data
    
    def _parse_business_name(self, name: str) -> List[str]:
        """상호명을 띄어쓰기로 파싱하여 2글자 이상만 반환"""
        parts = name.split()
        return [p for p in parts if len(p) >= 2]
    
    def _save_category(self, category: str):
        """카테고리를 파일에 저장 (나중에 매핑 테이블 구축용)"""
        try:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(data_dir, exist_ok=True)
            categories_file = os.path.join(data_dir, "collected_categories.txt")
            
            existing = set()
            if os.path.exists(categories_file):
                with open(categories_file, "r", encoding="utf-8") as f:
                    existing = set(f.read().splitlines())
            
            if category and category not in existing:
                with open(categories_file, "a", encoding="utf-8") as f:
                    f.write(category + "\n")
                print(f"[SmartWorker] 새 카테고리 저장: {category}")
        except Exception as e:
            print(f"[SmartWorker] 카테고리 저장 실패: {e}")

    # ==================== AI 기반 키워드 분류 ====================
    def _classify_with_ai(self, place_data: PlaceData):
        """Gemini API로 키워드를 지역/메뉴/수식어 등으로 분류 (1회 호출)

        결과를 self._ai_classification에 캐싱.
        실패 시 None 유지 → 기존 규칙 기반 로직으로 폴백.
        """
        if not self.gemini_client or not self.gemini_client.is_available():
            print("[SmartWorker] AI 분류 스킵: Gemini API 사용 불가")
            return

        try:
            self.progress.emit("AI 키워드 분류 중...")

            result = self.gemini_client.comprehensive_parse(
                name=place_data.name,
                category=place_data.category,
                address=getattr(place_data, 'address', '') or '',
                keywords=place_data.keywords[:15] if place_data.keywords else None,
                menus=place_data.menus[:15] if place_data.menus else None
            )

            if result.success:
                self._ai_classification = result
                ai_regions = result.get_all_regions()
                self.progress.emit(
                    f"   AI 분류 완료: 지역 {len(ai_regions)}개, "
                    f"업종 {len(result.business_types)}개, "
                    f"서비스 {len(result.services)}개, "
                    f"수식어 {len(result.modifiers)}개, "
                    f"테마 {len(result.themes)}개"
                )
                if ai_regions:
                    self.progress.emit(f"   AI 지역: {ai_regions}")
                if result.business_types:
                    self.progress.emit(f"   AI 업종: {result.business_types}")
                if result.services:
                    self.progress.emit(f"   AI 서비스: {result.services}")
            else:
                print(f"[SmartWorker] AI 분류 실패: {result.error_message}")
                self.progress.emit(f"   AI 분류 실패 → 규칙 기반 폴백")

        except Exception as e:
            print(f"[SmartWorker] AI 분류 예외: {e}")
            self.progress.emit(f"   AI 분류 예외 → 규칙 기반 폴백")

    # ==================== Phase 1: 지역 키워드 분석 (공통) ====================
    def _extract_regions_from_keywords(self, place_data: PlaceData):
        """대표 키워드에서 지역성 키워드 추출 (패턴 기반)"""
        extracted_regions = set()

        # 알려진 지역명 세트
        known_regions = {
            # 광역시도
            "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
            "경기", "강원", "충북", "충남", "경북", "경남", "전북", "전남", "제주",
            # 주요 시
            "수원", "용인", "고양", "창원", "천안", "청주", "전주", "성남", "화성",
            "안산", "남양주", "안양", "평택", "시흥", "김해", "부천", "하남", "파주",
            "의정부", "광명", "춘천", "원주", "김포", "청도",
            # 주요 구/지역
            "강남", "서초", "송파", "강동", "관악", "성동", "마포", "영등포",
            "구로", "강서", "용산", "종로", "중구", "동작", "양천", "은평",
            "서대문", "광진", "중랑", "성북", "도봉", "노원", "금천", "동대문",
            "해운대", "수영", "남동", "부평", "계양", "수성", "달서",
            # 신도시/지역 약칭
            "홍대", "잠실", "신촌", "이태원", "명동", "을지로", "성수",
            "건대", "왕십리", "합정", "망원", "연남", "상수", "판교", "분당",
            "수지", "동탄", "광교", "위례", "마곡", "청라", "송도", "검단",
            "미사", "일산", "한재"
        }

        for keyword in place_data.keywords:
            # 1. 키워드 자체가 지역명인지 확인
            if keyword in known_regions:
                extracted_regions.add(keyword)
                continue

            # 2. 지역 접미사 패턴 확인
            region_suffixes = ["역", "동", "구", "시", "군", "읍", "면"]
            for suffix in region_suffixes:
                if keyword.endswith(suffix) and len(keyword) > len(suffix) + 1:
                    # 차단 목록 확인
                    if keyword not in self.REGION_INFERENCE_BLOCKLIST:
                        extracted_regions.add(keyword)
                    break

            # 3. 키워드 내에 알려진 지역명 포함 확인
            for region in known_regions:
                if region in keyword and len(region) >= 2:
                    extracted_regions.add(region)

        place_data.discovered_regions.update(extracted_regions)
        if place_data.discovered_regions:
            print(f"[SmartWorker] 발견된 지역 키워드: {place_data.discovered_regions}")

    # ==================== Phase 1: 키워드 검증 (API 모드 지원) ====================
    async def _phase_1_validate_samples(self, place: PlaceData):
        """Phase 1: 각 키워드 검증 (API 모드로 10배 빠름, 배치 처리)"""
        print("[Phase1] 시작")

        # 업종 판별 (nxPlaces API는 모든 업종 지원)
        business_type = self._detect_business_type(place.category)
        # 모든 업종 GraphQL 사용 가능 (nxPlaces API)
        use_html_mode = False  # GraphQL이 모든 업종 지원

        if self.use_api_mode and HAS_GRAPHQL_MODE:
            mode_name = f"GraphQL ({business_type})"
        elif HAS_API_MODE:
            mode_name = f"HTML ({business_type})"
            use_html_mode = True
        else:
            mode_name = "브라우저"
        self.progress.emit(f"Phase 1: 키워드 검증 중... [{mode_name} 모드]")

        # 0. 지역 키워드 추출 (규칙 기반)
        self._extract_regions_from_keywords(place)

        # 0-1. AI 분류 지역 추가 (규칙 기반 보완)
        if self._ai_classification:
            ai_regions = self._ai_classification.get_all_regions()
            if ai_regions:
                place.discovered_regions.update(ai_regions)
                print(f"[Phase1] AI 지역 추가: {ai_regions}")
        print("[Phase1] 지역 추출 완료")

        # 메인 지역 결정 (큰 단위: 구/시)
        regions = place.region.get_keyword_variations()
        main_region = regions[0] if regions else place.region.gu

        # 폴백 지역 결정 (작은 단위: 동/역)
        fallback_region = None
        if place.region.dong:
            fallback_region = place.region.dong
        elif place.region.station:
            fallback_region = place.region.station
        elif len(regions) > 1:
            fallback_region = regions[1]

        if not main_region:
            self.progress.emit("⚠️ 지역 정보 없음")
            return

        # 업종 판별 (이미 위에서 수행)
        self.progress.emit(f"   업종: {business_type}")

        # 검증할 키워드 수집
        base_keywords_set: set = set()

        # 1. 상호명 파싱 (모든 업종 공통)
        name_parts = getattr(place, 'name_parts', self._parse_business_name(place.name))
        base_keywords_set.update(name_parts)
        if name_parts:
            self.progress.emit(f"   📛 상호명 파싱: {list(name_parts)[:5]}")

        # 2. 카테고리 (모든 업종 공통, 쉼표로 분리)
        if place.category:
            for cat in place.category.split(','):
                cat = cat.strip()
                if cat:
                    base_keywords_set.add(cat)
            self.progress.emit(f"   📂 카테고리: {place.category}")

        # 3. keywordList에서 - 모든 업종 공통
        if place.keywords:
            for compound_kw in place.keywords:
                # 원본 키워드 추가
                base_keywords_set.add(compound_kw)
                self.progress.emit(f"   📋 키워드: '{compound_kw}'")

        # 4. 메뉴 (맛집만 해당)
        if business_type == "restaurant" and place.menus:
            base_keywords_set.update(place.menus)
            self.progress.emit(f"   메뉴 키워드: {len(place.menus)}개")

        # 5. 병원 전용: 진료과목
        if business_type == "hospital" and place.medical_subjects:
            base_keywords_set.update(place.medical_subjects)
            self.progress.emit(f"   진료과목: {place.medical_subjects}")

        # 6. 리뷰 테마 키워드 (맛집만 - 분위기, 가성비 등)
        if business_type == "restaurant" and place.review_theme_keywords:
            theme_labels = [t.label for t in place.review_theme_keywords if t.label]
            # 테마 -> 검색 키워드 매핑 적용
            for theme in theme_labels:
                mapped = self.THEME_MAPPING.get(theme, [])
                if mapped:
                    base_keywords_set.update(mapped[:2])  # 상위 2개만
            self.progress.emit(f"   리뷰 테마: {len(theme_labels)}개")

        # 2글자 이상만 필터링 (지역명 제외)
        base_keywords = list(k for k in base_keywords_set
                           if k and len(k) >= 2 and k not in place.discovered_regions)

        self.progress.emit(f"   테스트 대상: {len(base_keywords)}개 키워드")
        self.progress.emit(f"   메인 지역: {main_region} / 폴백 지역: {fallback_region or '없음'}")

        # 프록시 설정
        proxy_configs = self._get_proxy_configs()
        place_id = self._get_place_id_from_url(self.url)

        print(f"[Phase1] base_keywords={len(base_keywords)}개, main_region={main_region}, place_id={place_id}")
        print(f"[Phase1] use_api_mode={self.use_api_mode}, HAS_GRAPHQL_MODE={HAS_GRAPHQL_MODE}")

        # 모드 선택: 모든 업종 GraphQL 지원 (nxPlaces API)
        if self.use_api_mode and HAS_GRAPHQL_MODE:
            print("[Phase1] GraphQL 모드 시작")
            await self._phase_1_graphql_batch(base_keywords, main_region, fallback_region, place_id, proxy_configs)
            print("[Phase1] GraphQL 모드 완료")
        elif self.use_api_mode and HAS_API_MODE:
            print("[Phase1] API 모드 시작")
            await self._phase_1_api_batch(base_keywords, main_region, fallback_region, place_id, proxy_configs)
        else:
            print("[Phase1] 브라우저 모드 시작")
            await self._phase_1_browser_sequential(base_keywords, main_region, fallback_region, place_id, proxy_configs)

        self.progress.emit(f"Phase 1 완료: {len(self.validated_keywords)}/{len(base_keywords)}개 키워드 확정")

    async def _phase_1_graphql_batch(self, base_keywords: List[str], main_region: str,
                                      fallback_region: str, place_id: str, proxy_configs: List[ProxyConfig]):
        """Phase 1 - GraphQL 배치 처리 (가장 빠르고 안정적)"""
        print(f"[GraphQL Batch] 시작: main_region={main_region}, keywords={len(base_keywords)}개")

        from .rank_checker_graphql import RankCheckerGraphQL
        print("[GraphQL Batch] import 성공")

        # 지역에서 좌표 추출 (긴 지역명 우선 매칭)
        coords = None
        matched_region = None

        # 긴 지역명부터 매칭 시도 (정확도 향상)
        sorted_regions = sorted(CITY_COORDINATES.keys(), key=len, reverse=True)
        for region in sorted_regions:
            if region in main_region:
                coords = CITY_COORDINATES[region]
                matched_region = region
                print(f"[GraphQL Batch] 좌표 매칭: {region} -> {coords}")
                self.progress.emit(f"   📍 좌표 감지: {region}")
                break

        if not coords:
            print(f"[GraphQL Batch] 좌표 없음 (main_region={main_region}), 기본값 서울 사용")
            coords = CITY_COORDINATES.get("서울")
            matched_region = "서울"

        # 1차: 메인 지역 + 키워드 (배치)
        test_keywords_main = [f"{main_region} {kw}" for kw in base_keywords]
        kw_map_main = {f"{main_region} {kw}": kw for kw in base_keywords}

        self.progress.emit(f"   🚀 GraphQL 1차 배치: {len(test_keywords_main)}개 키워드")
        print(f"[GraphQL Batch] 테스트 키워드: {test_keywords_main[:3]}...")

        try:
            async with RankCheckerGraphQL(
                proxies=proxy_configs if proxy_configs else None,
                default_coords=coords,
                use_own_ip=self.use_own_ip,
                user_slot=self.user_slot,
                total_instances=self.total_instances
            ) as checker:
                print(f"[GraphQL Batch] RankCheckerGraphQL 세션 시작 (내 IP 사용: {self.use_own_ip}, 슬롯: {self.user_slot}, 인스턴스: {self.total_instances})")

                def progress_cb(current, total, msg):
                    self.sub_progress.emit(current, total, msg)
                checker.set_progress_callback(progress_cb)

                # 1차 배치 실행
                print("[GraphQL Batch] check_keywords 호출 시작")
                results_main = await checker.check_keywords(
                    keywords=test_keywords_main,
                    target_place_id=place_id,
                    max_rank=self.max_rank,
                    coords=coords
                )
                print(f"[GraphQL Batch] check_keywords 완료: {len(results_main)}개 결과")

                # 1차 결과 처리
                failed_keywords = []
                for result in results_main:
                    original_kw = kw_map_main.get(result.keyword)
                    if not original_kw:
                        continue

                    # 디버그: 결과 상태 출력
                    print(f"[Phase1 DEBUG] {result.keyword}: status={result.status}, rank={result.rank}, error={result.error_message}")

                    if result.status == "error":
                        self.progress.emit(f"   ⚠️ {original_kw} 에러: {result.error_message}")
                        failed_keywords.append(original_kw)
                    elif result.rank and self.min_rank <= result.rank <= self.max_rank:
                        self.validated_keywords.append(original_kw)
                        self.validated_map_types[original_kw] = result.map_type
                        self.progress.emit(f"   ✅ {original_kw} 확정 (GraphQL, {result.rank}위)")
                        converted = RankResult(
                            keyword=result.keyword, rank=result.rank,
                            map_type=result.map_type, status=result.status
                        )
                        self.all_results.append(converted)
                    else:
                        self.progress.emit(f"   ❌ {original_kw} 순위권 외 ({result.status})")
                        failed_keywords.append(original_kw)

                # 2차: 폴백 지역 (실패한 키워드만)
                if fallback_region and fallback_region != main_region and failed_keywords:
                    # 폴백 지역 좌표
                    fallback_coords = None
                    for region, coord in CITY_COORDINATES.items():
                        if region in fallback_region:
                            fallback_coords = coord
                            break

                    test_keywords_fallback = [f"{fallback_region} {kw}" for kw in failed_keywords]
                    kw_map_fallback = {f"{fallback_region} {kw}": kw for kw in failed_keywords}

                    self.progress.emit(f"   🔄 GraphQL 2차 폴백: {len(test_keywords_fallback)}개 키워드")

                    results_fallback = await checker.check_keywords(
                        keywords=test_keywords_fallback,
                        target_place_id=place_id,
                        max_rank=self.max_rank,
                        coords=fallback_coords
                    )

                    for result in results_fallback:
                        original_kw = kw_map_fallback.get(result.keyword)
                        if not original_kw:
                            continue

                        if result.rank and self.min_rank <= result.rank <= self.max_rank:
                            self.validated_keywords.append(original_kw)
                            self.validated_map_types[original_kw] = result.map_type
                            self.progress.emit(f"   ✅ {original_kw} 폴백 확정 (GraphQL, {result.rank}위)")
                            converted = RankResult(
                                keyword=result.keyword, rank=result.rank,
                                map_type=result.map_type, status=result.status
                            )
                            self.all_results.append(converted)
                        else:
                            self.progress.emit(f"   ❌ {original_kw} 제외")

        except Exception as e:
            print(f"[GraphQL Batch] ERROR: {type(e).__name__}: {e}")
            self.progress.emit(f"   ⚠️ GraphQL 에러: {e}")
            import traceback
            traceback.print_exc()

    async def _phase_1_api_batch(self, base_keywords: List[str], main_region: str,
                                  fallback_region: str, place_id: str, proxy_configs: List[ProxyConfig],
                                  use_html_only: bool = False):
        """Phase 1 - API 배치 처리 (10배 빠름)

        Args:
            use_html_only: True면 HTML 스크래핑만 사용 (병원 검색용)
        """
        from .rank_checker_api import RankCheckerAPI

        # 1차: 메인 지역 + 키워드 (배치)
        test_keywords_main = [f"{main_region} {kw}" for kw in base_keywords]
        kw_map_main = {f"{main_region} {kw}": kw for kw in base_keywords}  # 역매핑

        mode_desc = "HTML" if use_html_only else "API"
        self.progress.emit(f"   1차 배치 ({mode_desc}): {len(test_keywords_main)}개 키워드")

        # use_html_only=True면 use_api_mode=False (순수 HTML 파싱)
        async with RankCheckerAPI(proxies=proxy_configs if proxy_configs else None, use_api_mode=not use_html_only) as checker:
            # 진행률 콜백
            def progress_cb(current, total, msg):
                self.sub_progress.emit(current, total, msg)
            checker.set_progress_callback(progress_cb)

            # 1차 배치 실행
            results_main = await checker.check_keywords(
                keywords=test_keywords_main,
                target_place_id=place_id,
                max_rank=self.max_rank
            )

            # 1차 결과 처리
            failed_keywords = []
            for result in results_main:
                original_kw = kw_map_main.get(result.keyword)
                if not original_kw:
                    continue

                if result.rank and self.min_rank <= result.rank <= self.max_rank:
                    self.validated_keywords.append(original_kw)
                    self.validated_map_types[original_kw] = result.map_type
                    self.progress.emit(f"   ✅ {original_kw} 확정 ({result.map_type}, {result.rank}위)")
                    # RankResult 변환 후 저장
                    converted = RankResult(
                        keyword=result.keyword, rank=result.rank,
                        map_type=result.map_type, status=result.status
                    )
                    self.all_results.append(converted)
                else:
                    failed_keywords.append(original_kw)

            # 2차: 폴백 지역 (실패한 키워드만)
            if fallback_region and fallback_region != main_region and failed_keywords:
                test_keywords_fallback = [f"{fallback_region} {kw}" for kw in failed_keywords]
                kw_map_fallback = {f"{fallback_region} {kw}": kw for kw in failed_keywords}

                self.progress.emit(f"   🔄 2차 폴백: {len(test_keywords_fallback)}개 키워드")

                results_fallback = await checker.check_keywords(
                    keywords=test_keywords_fallback,
                    target_place_id=place_id,
                    max_rank=self.max_rank
                )

                for result in results_fallback:
                    original_kw = kw_map_fallback.get(result.keyword)
                    if not original_kw:
                        continue

                    if result.rank and self.min_rank <= result.rank <= self.max_rank:
                        self.validated_keywords.append(original_kw)
                        self.validated_map_types[original_kw] = result.map_type
                        self.progress.emit(f"   ✅ {original_kw} 폴백 확정 ({result.map_type}, {result.rank}위)")
                        converted = RankResult(
                            keyword=result.keyword, rank=result.rank,
                            map_type=result.map_type, status=result.status
                        )
                        self.all_results.append(converted)
                    else:
                        self.progress.emit(f"   ❌ {original_kw} 제외")

    async def _phase_1_browser_sequential(self, base_keywords: List[str], main_region: str,
                                           fallback_region: str, place_id: str, proxy_configs: List[ProxyConfig]):
        """Phase 1 - 브라우저 순차 처리 (안정적이지만 느림)"""
        async with RankChecker(proxies=proxy_configs if proxy_configs else None, headless=True) as checker:
            self.rank_checker = checker

            total_keywords = len(base_keywords)
            for i, kw in enumerate(base_keywords):
                if not self.is_running:
                    return

                self.sub_progress.emit(i + 1, total_keywords, f"검사 중: {kw}")

                # 1차 시도: 메인 지역 + 키워드
                test_keyword = f"{main_region} {kw}"
                results = await checker.check_keywords(
                    keywords=[test_keyword],
                    target_place_id=place_id,
                    max_rank=self.max_rank
                )

                if results and results[0].rank and self.min_rank <= results[0].rank <= self.max_rank:
                    self.validated_keywords.append(kw)
                    self.validated_map_types[kw] = results[0].map_type
                    self.progress.emit(f"   ✅ {kw} 확정 ({results[0].map_type}, {results[0].rank}위)")
                    self.all_results.extend(results)
                    continue

                # 2차 시도: 폴백 지역
                if fallback_region and fallback_region != main_region:
                    test_keyword_fallback = f"{fallback_region} {kw}"
                    results_fallback = await checker.check_keywords(
                        keywords=[test_keyword_fallback],
                        target_place_id=place_id,
                        max_rank=self.max_rank
                    )

                    if results_fallback and results_fallback[0].rank and self.min_rank <= results_fallback[0].rank <= self.max_rank:
                        self.validated_keywords.append(kw)
                        self.validated_map_types[kw] = results_fallback[0].map_type
                        self.progress.emit(f"   ✅ {kw} 폴백 확정 ({results_fallback[0].map_type}, {results_fallback[0].rank}위)")
                        self.all_results.extend(results_fallback)
                        continue

                self.progress.emit(f"   ❌ {kw} 제외")

    # ==================== Phase 2: 계층적 키워드 풀 생성 ====================
    def _phase_2_generate_pool(self, place: PlaceData):
        """Phase 2: 계층적 키워드 조합 생성 (R1~R14)

        [핵심 원칙] 기본 → 수식어 → 키워드 → 수식어 → 확장 → 수식어 (각 단계 직후 수식어)

        === 단일 키워드 사이클 ===
        R1: 지역 + 업종대표키워드
        R2: 지역 + 업종대표 + 수식어
        R3: 지역 + 키워드
        R4: 지역 + 키워드 + 수식어
        R5: 지역 + 근처/가까운 + 업종대표키워드
        R6: 지역 + 근처/가까운 + 키워드
        R7: 가까운 + 수식어
        R8: 지역1 + 지역2 + 업종대표키워드
        R9: 지역1 + 지역2 + 키워드
        === 복수 키워드 조합 (사이클 후) ===
        R10: 지역 + 키워드 + 업종대표키워드
        R11: 지역 + 키워드1 + 키워드2
        === 특수 라운드 ===
        R12: 상호명
        R13: 3개 키워드 조합
        R14: 순서 변형
        """
        self.progress.emit("Phase 2: 키워드 풀 생성 중...")

        # ========== 지역 수집 (사용자 데이터 우선) ==========
        if self._user_regions_set:
            # 사용자가 지역을 명시적으로 설정함 (비어있어도 사용자 선택 존중)
            regions = [r.strip() for r in (self.user_regions or []) if r.strip()]
            if not regions:
                self.progress.emit("   📍 사용자가 모든 지역 해제 → 지역 없이 진행")
            else:
                self.progress.emit(f"   📍 사용자 지역: {len(regions)}개")
        else:
            # 자동 추출 + 지역 조합 생성
            base_regions = []

            # 주소 기반 지역
            addr_regions = place.region.get_keyword_variations()
            if addr_regions:
                base_regions.extend(addr_regions)

            # 구/동/역/도로명 변형
            if place.region.gu:
                base_regions.append(place.region.gu)
            if place.region.gu_without_suffix:
                base_regions.append(place.region.gu_without_suffix)
            if place.region.dong:
                base_regions.append(place.region.dong)
            if place.region.dong_without_suffix:
                base_regions.append(place.region.dong_without_suffix)
            if place.region.road:
                base_regions.append(place.region.road)
            if place.region.station:
                base_regions.append(place.region.station)

            # 발견된 지역 (키워드 기반)
            if place.discovered_regions:
                base_regions.extend(list(place.discovered_regions))

            # 지역 조합 자동 생성 (시+동, 역+근처 등)
            regions = self._generate_region_combinations(base_regions)
            if not regions:
                regions = [place.region.gu] if place.region.gu else [""]

            self.progress.emit(f"   📍 지역 조합: {len(base_regions)}개 → {len(regions)}개")

        # ========== 업종 판별 + 대표 키워드/수식어 준비 ==========
        business_type = self._detect_business_type(place.category)
        biz_keywords = list(self._instance_biz_keywords.get(business_type,
                            self._instance_biz_keywords["general"]))

        # 수식어 풀 (하드코딩 + GUI, 배타적 사용 — 한 키워드에 1개 수식어만)
        if self.user_modifiers_list:
            # 사용자가 Phase 1 편집 화면에서 수식어를 직접 편집한 경우
            user_mods = [m.strip() for m in self.user_modifiers_list if m.strip()]
            # 필수 수식어(지도, 추천)는 항상 포함, 사용자 수식어를 추가
            all_modifiers = list(self.MANDATORY_MODIFIERS)
            for m in user_mods:
                if m not in all_modifiers:
                    all_modifiers.append(m)
            self.progress.emit(f"   사용자 수식어 사용: {user_mods}")
        else:
            all_modifiers = list(self.MANDATORY_MODIFIERS)  # ["지도", "추천"]
            gui_mods = getattr(self, '_gui_modifiers', [])
            gui_mods_unique = [m for m in gui_mods if m not in all_modifiers]
            all_modifiers.extend(gui_mods_unique)

        # AI 수식어/테마 추가
        if self._ai_classification:
            for m in self._ai_classification.modifiers:
                if m not in all_modifiers:
                    all_modifiers.append(m)
            for t in self._ai_classification.themes:
                if t not in all_modifiers:
                    all_modifiers.append(t)

        self.progress.emit(f"   업종: {business_type} → 대표키워드: {biz_keywords}")
        self.progress.emit(f"   수식어: {all_modifiers} (필수: {self.MANDATORY_MODIFIERS})")

        # AI 분류 시 지역 세트 (priority_keywords 필터용)
        ai_region_set = set()
        if self._ai_classification:
            ai_region_set = set(self._ai_classification.get_all_regions())

        # ========== 키워드 소스 수집 ==========
        priority_keywords = []  # 메인 키워드 (업종+메뉴+대표)
        name_keywords = []      # 상호명 (최후순위)

        # 사용자가 키워드를 편집했으면 그것만 사용 (카테고리/메뉴 무시)
        if self.user_keywords:
            priority_keywords = [kw.strip() for kw in self.user_keywords if kw.strip()]
            self.progress.emit(f"   📋 사용자 키워드만 사용: {len(priority_keywords)}개")
        else:
            if self._ai_classification:
                # AI 분류 모드: 업종/서비스/연관 키워드 사용 (지역 완전 분리)
                for kw in self._ai_classification.business_types:
                    if kw and kw not in priority_keywords:
                        priority_keywords.append(kw)
                for kw in self._ai_classification.services:
                    if kw and kw not in priority_keywords:
                        priority_keywords.append(kw)
                for kw in self._ai_classification.related_keywords:
                    if kw and kw not in priority_keywords:
                        priority_keywords.append(kw)

                # 기존 소스에서 보충 (AI가 놓친 것 대비)
                # 카테고리
                if place.category:
                    for cat in place.category.split(','):
                        cat = cat.strip()
                        if cat and cat not in priority_keywords and cat not in ai_region_set:
                            priority_keywords.append(cat)
                # 메뉴
                if business_type == "restaurant" and place.menus:
                    for menu in place.menus[:20]:
                        if menu and menu not in priority_keywords and menu not in ai_region_set:
                            priority_keywords.append(menu)
                # 대표 키워드 (지역 제외)
                if place.keywords:
                    for kw in place.keywords[:15]:
                        if kw and kw not in priority_keywords and kw not in ai_region_set:
                            priority_keywords.append(kw)

                self.progress.emit(f"   AI 분류 기반 키워드 수집: {len(priority_keywords)}개")
            else:
                # 기존 규칙 기반 모드
                # 1. 업종 카테고리
                if place.category:
                    for cat in place.category.split(','):
                        cat = cat.strip()
                        if cat and cat not in priority_keywords:
                            priority_keywords.append(cat)

                # 2. 메뉴 (음식점)
                if business_type == "restaurant" and place.menus:
                    for menu in place.menus[:20]:
                        if menu and menu not in priority_keywords:
                            priority_keywords.append(menu)

                # 3. 대표 키워드
                if place.keywords:
                    for kw in place.keywords[:15]:
                        if kw and kw not in priority_keywords:
                            priority_keywords.append(kw)

        # Phase 1 검증 키워드 추가 (우선순위 높음)
        # 단, 사용자가 키워드를 편집한 경우 사용자 선택에 포함된 것만 추가
        if self.validated_keywords:
            user_selected_set = set(self.user_keywords) if self.user_keywords else None
            for vk in list(self.validated_keywords):
                # 사용자 편집 모드일 때는 사용자가 선택한 키워드만 추가
                if user_selected_set is not None and vk not in user_selected_set:
                    continue
                if vk and vk not in priority_keywords:
                    priority_keywords.insert(0, vk)

        # 최종 필터: priority_keywords에서 AI 지역명 제거
        if ai_region_set:
            priority_keywords = [kw for kw in priority_keywords if kw not in ai_region_set]

        # 5. 상호명 (최후순위) - 사용자 편집 데이터 또는 형태소 분석 결과
        if self.user_name_parts:
            # 사용자가 편집한 상호명 사용
            name_parts = self.user_name_parts
        else:
            # 항상 morpheme 분석 실행 (단순 split보다 정교한 결과)
            morpheme_parts = self._parse_business_name_morphemes(place.name)
            simple_parts = getattr(place, 'name_parts', []) or []
            seen = set()
            name_parts = []
            for p in morpheme_parts + simple_parts:
                if p and p not in seen:
                    seen.add(p)
                    name_parts.append(p)

        for part in name_parts:
            if part and part not in name_keywords and part not in priority_keywords:
                name_keywords.append(part)

        # AI 상호명 토큰 추가
        if self._ai_classification and self._ai_classification.name_tokens:
            for token in self._ai_classification.name_tokens:
                if token and token not in name_keywords and token not in priority_keywords:
                    name_keywords.append(token)

        self.progress.emit(f"   📋 메인 키워드: {len(priority_keywords)}개, 상호명: {name_keywords}")

        # ========== 키워드 생성 (R1~R14) ==========
        generated = set()

        def add(kw: str, level: int, source: str = None) -> bool:
            if kw and kw not in generated and kw not in self.verified_keywords:
                generated.add(kw)
                item = {"keyword": kw, "map_type": "unknown", "level": level}
                if source:
                    item["source"] = source
                self.keyword_pool.append(item)
                return True
            return False

        # ===== 대각선 균형 배치 (R1~R18) =====
        # 지역 확장: 단일(0) → 근처(1) → 지역2개(2) → 지역2개+근처(3)
        # 키워드 확장: 단독(0) → +수식어(1) → 2개조합(2) → 2개+수식어(3)
        # 대각선 레벨 = 지역복잡도 + 키워드복잡도 (낮을수록 우선)

        # === 대각선 레벨 0: 기본 ===

        # R1(L0): 지역 + 업종대표키워드
        # 예: "강남 맛집", "강남 음식점", "강남 식당"
        self.progress.emit("   R1: 지역 + 업종대표키워드")
        for region in regions:
            for bk in biz_keywords:
                add(f"{region} {bk}", 0)
        self.progress.emit(f"   R1: {len(self.keyword_pool)}개")

        # R2(L1): 지역 + 키워드
        # 예: "강남 삼겹살", "강남 목살"
        self.progress.emit("   R2: 지역 + 키워드")
        for region in regions:
            for kw in priority_keywords:
                add(f"{region} {kw}", 1)
        self.progress.emit(f"   R2: {len(self.keyword_pool)}개")

        # 사용자 편집 지역+키워드 조합 (Phase 1에서 편집된 경우)
        if self.user_region_keyword_combos:
            for combo in self.user_region_keyword_combos:
                add(combo, 1)

        # === 대각선 레벨 1: 기본 확장 ===

        # R3(L2): 지역 + 업종대표 + 수식어
        # 예: "강남 맛집 지도", "강남 음식점 추천"
        self.progress.emit("   R3: 지역 + 업종대표 + 수식어")
        for region in regions:
            for bk in biz_keywords:
                for mod in all_modifiers:
                    add(f"{region} {bk} {mod}", 2)
        self.progress.emit(f"   R3: {len(self.keyword_pool)}개")

        # R4(L3): 지역 + 키워드 + 수식어
        # 예: "강남 삼겹살 지도", "강남 목살 추천"
        self.progress.emit("   R4: 지역 + 키워드 + 수식어")
        for region in regions:
            for kw in priority_keywords:
                for mod in all_modifiers:
                    add(f"{region} {kw} {mod}", 3)
        self.progress.emit(f"   R4: {len(self.keyword_pool)}개")

        # basic_only 모드: R1-R4만 생성하고 조기 종료
        if self.basic_only:
            self.keyword_pool.sort(key=lambda x: x["level"])
            self.progress.emit(f"Phase 2 완료 (기본 조합): {len(self.keyword_pool)}개 생성")
            lvl_counts = {}
            for k in self.keyword_pool:
                lvl = k["level"]
                lvl_counts[lvl] = lvl_counts.get(lvl, 0) + 1
            for lvl, cnt in sorted(lvl_counts.items()):
                self.progress.emit(f"   Level {lvl}: {cnt}개")
            return

        # R5(L4): 지역 + 근처/가까운 + 업종대표키워드
        # 예: "강남 근처 맛집", "강남 주변 음식점"
        self.progress.emit("   R5: 지역 + 근처 + 업종대표키워드")
        for region in regions:
            for loc_suffix in self.LOCATION_SUFFIXES:
                for bk in biz_keywords:
                    add(f"{region} {loc_suffix} {bk}", 4)
        self.progress.emit(f"   R5: {len(self.keyword_pool)}개")

        # R6(L5): 지역 + 근처/가까운 + 키워드
        # 예: "강남 근처 삼겹살", "강남 가까운 목살"
        self.progress.emit("   R6: 지역 + 근처 + 키워드")
        for region in regions:
            for loc_suffix in self.LOCATION_SUFFIXES:
                for kw in priority_keywords:
                    add(f"{region} {loc_suffix} {kw}", 5)
        self.progress.emit(f"   R6: {len(self.keyword_pool)}개")

        # === 대각선 레벨 2: 중간 확장 ===

        # R7(L6): 지역 + 키워드 + 업종대표키워드
        # 예: "강남 삼겹살 맛집", "강남 목살 음식점"
        self.progress.emit("   R7: 지역 + 키워드 + 업종대표키워드")
        for region in regions:
            for kw in priority_keywords:
                for bk in biz_keywords:
                    add(f"{region} {kw} {bk}", 6)
        self.progress.emit(f"   R7: {len(self.keyword_pool)}개")

        # R8(L7): 지역 + 키워드1 + 키워드2
        # 예: "강남 삼겹살 소주", "강남 삼겹살 목살"
        self.progress.emit("   R8: 지역 + 키워드1 + 키워드2")
        for region in regions:
            for kw1, kw2 in combinations(priority_keywords[:15], 2):
                add(f"{region} {kw1} {kw2}", 7)
        self.progress.emit(f"   R8: {len(self.keyword_pool)}개")

        # R9(L8): 지역 + 근처 + 업종대표 + 수식어
        # 예: "강남 근처 맛집 지도", "강남 주변 맛집 추천"
        self.progress.emit("   R9: 지역 + 근처 + 업종대표 + 수식어")
        for region in regions:
            for loc_suffix in self.LOCATION_SUFFIXES[:2]:  # "근처","주변"만 (폭발 방지)
                for bk in biz_keywords[:2]:
                    for mod in all_modifiers:
                        add(f"{region} {loc_suffix} {bk} {mod}", 8)
        self.progress.emit(f"   R9: {len(self.keyword_pool)}개")

        # R10(L9): 지역 + 근처 + 키워드 + 수식어
        # 예: "강남 근처 삼겹살 추천", "강남 주변 목살 지도"
        self.progress.emit("   R10: 지역 + 근처 + 키워드 + 수식어")
        for region in regions:
            for loc_suffix in self.LOCATION_SUFFIXES[:2]:
                for kw in priority_keywords[:8]:
                    for mod in all_modifiers:
                        add(f"{region} {loc_suffix} {kw} {mod}", 9)
        self.progress.emit(f"   R10: {len(self.keyword_pool)}개")

        # R11(L10): 지역1 + 지역2 + 업종대표키워드 (지역 2개 조합)
        # 예: "강남 역삼 맛집", "공덕 마포 음식점"
        self.progress.emit("   R11: 지역2개 + 업종대표키워드")
        for r1, r2 in combinations(regions[:8], 2):
            for bk in biz_keywords:
                add(f"{r1} {r2} {bk}", 10)
        self.progress.emit(f"   R11: {len(self.keyword_pool)}개")

        # R12(L11): 지역1 + 지역2 + 키워드
        # 예: "강남 역삼 삼겹살", "공덕 마포 고기집"
        self.progress.emit("   R12: 지역2개 + 키워드")
        for r1, r2 in combinations(regions[:8], 2):
            for kw in priority_keywords[:10]:
                add(f"{r1} {r2} {kw}", 11)
        self.progress.emit(f"   R12: {len(self.keyword_pool)}개")

        # === 상호명 (별도) ===

        # R13(L12): 상호명 (source="name" 태그)
        # 예: "강남 OO숯불구이", "OO숯불구이 강남", "강남 맛집 OO숯불구이"
        # R-POST용: full keyword → bare name 매핑 저장
        self._name_kw_to_bare = {}  # {"강남 OO숯불구이": "OO숯불구이", ...}
        if name_keywords:
            self.progress.emit(f"   R13: 상호명 ({name_keywords})")

            # R13-0: 상호명 원본 그대로 추가 (예: "갓잇 상암점")
            original_name = place.name.strip()
            if original_name and len(original_name) >= 2:
                add(original_name, 12, source="name")
                self._name_kw_to_bare[original_name] = original_name

            # R13-1: name_kw 간 조합 (예: "갓잇"+"상암점" → "갓잇 상암점", "상암점 갓잇")
            if len(name_keywords) >= 2:
                for i, nk1 in enumerate(name_keywords):
                    for j, nk2 in enumerate(name_keywords):
                        if i != j:
                            combo = f"{nk1} {nk2}"
                            add(combo, 12, source="name")
                            self._name_kw_to_bare[combo] = nk1

            # R13-2: 지역 × 상호명 토큰 조합
            for region in regions:
                for name_kw in name_keywords:
                    kw1 = f"{region} {name_kw}"
                    kw2 = f"{name_kw} {region}"
                    add(kw1, 12, source="name")
                    add(kw2, 12, source="name")
                    self._name_kw_to_bare[kw1] = name_kw
                    self._name_kw_to_bare[kw2] = name_kw
                    for bk in biz_keywords[:1]:  # 대표 1개만
                        kw3 = f"{region} {bk} {name_kw}"
                        add(kw3, 12, source="name")
                        self._name_kw_to_bare[kw3] = name_kw
            self.progress.emit(f"   R13: {len(self.keyword_pool)}개")

        # === 대각선 레벨 3: 추가 확장 ===

        # R14(L13): 지역2개 + 업종대표 + 수식어 (NEW)
        # 예: "강남 역삼 맛집 추천", "공덕 마포 음식점 지도"
        self.progress.emit("   R14: 지역2개 + 업종대표 + 수식어")
        for r1, r2 in combinations(regions[:8], 2):
            for bk in biz_keywords[:2]:
                for mod in all_modifiers:
                    add(f"{r1} {r2} {bk} {mod}", 13)
        self.progress.emit(f"   R14: {len(self.keyword_pool)}개")

        # R15(L14): 지역2개 + 키워드 + 수식어 (NEW)
        # 예: "강남 역삼 삼겹살 추천", "공덕 마포 고기집 지도"
        self.progress.emit("   R15: 지역2개 + 키워드 + 수식어")
        for r1, r2 in combinations(regions[:8], 2):
            for kw in priority_keywords[:8]:
                for mod in all_modifiers:
                    add(f"{r1} {r2} {kw} {mod}", 14)
        self.progress.emit(f"   R15: {len(self.keyword_pool)}개")

        # R16(L15): 지역2개 + 근처 + 업종대표 (NEW)
        # 예: "강남 역삼 근처 맛집", "공덕 마포 주변 음식점"
        self.progress.emit("   R16: 지역2개 + 근처 + 업종대표")
        for r1, r2 in combinations(regions[:6], 2):
            for loc_suffix in self.LOCATION_SUFFIXES[:2]:
                for bk in biz_keywords[:2]:
                    add(f"{r1} {r2} {loc_suffix} {bk}", 15)
        self.progress.emit(f"   R16: {len(self.keyword_pool)}개")

        # === 고급 조합 + 특수 ===

        # R17(L16): 3개 키워드 조합
        # 예: "강남 삼겹살 목살 소주"
        self.progress.emit("   R17: 3개 키워드 조합")
        for region in regions:
            for combo in combinations(priority_keywords[:10], 3):
                add(f"{region} {' '.join(combo)}", 16)
        self.progress.emit(f"   R17: {len(self.keyword_pool)}개")

        # R18(L17): 순서 변형
        # 예: "삼겹살 강남", "맛집 강남 삼겹살"
        self.progress.emit("   R18: 순서 변형")
        for region in regions:
            for kw in priority_keywords:
                add(f"{kw} {region}", 17)
            for kw in priority_keywords[:8]:
                for bk in biz_keywords[:1]:
                    add(f"{bk} {region} {kw}", 17)
        self.progress.emit(f"   R18: {len(self.keyword_pool)}개")

        # Phase 4 스킵 로직용 지역 세트 저장
        self._phase2_region_set = set(regions)

        # Level 기준 정렬 (낮은 레벨 = 우선순위 높음)
        self.keyword_pool.sort(key=lambda x: x["level"])

        # 참고: 실시간 예약 키워드 REPLACE는 Phase 4 완료 후 GUI에서 적용
        # (Phase 2 시점에서는 map_type이 "unknown"이므로 신지도 판별 불가)

        self.progress.emit(f"Phase 2 완료: {len(self.keyword_pool)}개 생성")
        lvl_counts = {}
        for k in self.keyword_pool:
            lvl_counts[k["level"]] = lvl_counts.get(k["level"], 0) + 1
        self.progress.emit(f"   레벨별: {lvl_counts}")
    
    def _add_to_pool(self, keyword: str, map_type: str, level: int):
        """키워드 풀에 추가 (중복 체크)"""
        if keyword not in self.verified_keywords:
            self.keyword_pool.append({
                "keyword": keyword,
                "map_type": map_type,
                "level": level
            })

    def _add_rank1_name_combos(self, rank1_name_keywords: List[str],
                                regions: List[str], business_type: str) -> List[Dict]:
        """Phase 4에서 상호명 단독 1위 확인 후 → 업종대표키워드와 추가 조합 (R-POST)

        restaurant 한정: "OO숯불구이" 1위 → "OO숯불구이 맛집/음식점/식당" 추가

        Args:
            rank1_name_keywords: 단독 검색 시 1위인 상호명 키워드 리스트
            regions: 지역 리스트
            business_type: 업종 타입

        Returns:
            새로 생성된 키워드 아이템 리스트
        """
        if business_type != "restaurant":
            return []

        biz_keywords = self._instance_biz_keywords.get(business_type, [])
        new_keywords = []
        for name_kw in rank1_name_keywords:
            for bk in biz_keywords:
                new_keywords.append({
                    "keyword": f"{name_kw} {bk}",
                    "map_type": "unknown", "level": 1,
                    "source": "name_combo"
                })
            for region in regions[:5]:  # 상위 지역 5개만
                for bk in biz_keywords:
                    new_keywords.append({
                        "keyword": f"{region} {name_kw} {bk}",
                        "map_type": "unknown", "level": 3,
                        "source": "name_combo"
                    })
        return new_keywords

    def _apply_booking_replacement(self, place: PlaceData, business_type: str):
        """
        실시간 예약 키워드 REPLACE 적용

        - restaurant 업종만 적용
        - place.has_booking이 True인 경우만 적용
        - 신지도 리스트 형태의 키워드만 대상
        - 총 개수 유지 (ADD 아닌 REPLACE)
        - booking_keyword_ratio에 따라 비율 적용
        """
        # 조건 체크: restaurant + has_booking
        if business_type != "restaurant":
            self.progress.emit("   ⊘ 실시간 예약: restaurant 업종 아님 (SKIP)")
            return

        if not hasattr(place, 'has_booking') or not place.has_booking:
            self.progress.emit("   ⊘ 실시간 예약: 예약 기능 없음 (SKIP)")
            return

        total_keywords = len(self.keyword_pool)
        if total_keywords == 0:
            return

        # 적용할 키워드 수 계산 (비율 기반)
        booking_count = max(1, int(total_keywords * self.booking_keyword_ratio))

        # 신지도 리스트 키워드만 필터링 (교체 대상)
        # 신지도(map_type == "신지도")이면서 "예약"이 포함되지 않은 키워드
        eligible_indices = []
        for idx, item in enumerate(self.keyword_pool):
            kw = item.get("keyword", "")
            map_type = item.get("map_type", "")

            # 신지도 타입이고, "예약"이 아직 없는 키워드만 대상
            if map_type == "신지도" and "예약" not in kw:
                eligible_indices.append(idx)

        if not eligible_indices:
            self.progress.emit("   ⊘ 실시간 예약: 교체 가능한 신지도 키워드 없음 (SKIP)")
            return

        # 교체할 개수 결정 (eligible 중에서)
        replace_count = min(booking_count, len(eligible_indices))

        # 교체 실행 (앞에서부터 replace_count 개)
        replaced_keywords = []
        for i in range(replace_count):
            idx = eligible_indices[i]
            original_kw = self.keyword_pool[idx]["keyword"]
            booking_kw = f"{original_kw} 실시간 예약"

            # REPLACE: 기존 키워드를 실시간 예약 버전으로 교체
            self.keyword_pool[idx] = {
                "keyword": booking_kw,
                "map_type": "예약",  # 타입을 예약으로 변경
                "level": self.keyword_pool[idx]["level"]  # 레벨 유지
            }
            replaced_keywords.append(f"{original_kw} → {booking_kw}")

        self.progress.emit(f"   ✅ 실시간 예약: {replace_count}개 키워드 교체 (총 {total_keywords}개 유지)")
        if replaced_keywords[:3]:  # 처음 3개만 로그
            for rk in replaced_keywords[:3]:
                self.progress.emit(f"      → {rk}")
            if len(replaced_keywords) > 3:
                self.progress.emit(f"      → ... 외 {len(replaced_keywords) - 3}개")

    # ==================== Phase 3: 비율 조정 ====================
    def _phase_3_adjust_ratio(self, place: PlaceData):
        """Phase 3: 신/구지도 비율 조정 (지도 키워드 추가)"""
        self.progress.emit("Phase 3: 지도 비율 조정 중...")
        
        # 현재 비율 계산
        new_map_count = sum(1 for k in self.keyword_pool if k["map_type"] == "신지도")
        old_map_count = sum(1 for k in self.keyword_pool if k["map_type"] == "구지도")
        total = len(self.keyword_pool)
        
        if total == 0:
            return
        
        # 목표 구지도 비율
        old_map_ratio = 100 - self.new_map_ratio
        target_old = int(self.target_count * old_map_ratio / 100)
        
        # 현재 구지도 예상치
        current_old_ratio = old_map_count / total if total > 0 else 0
        expected_old = int(self.target_count * current_old_ratio)
        
        # 부족분
        deficit = target_old - expected_old
        
        if deficit > 0:
            # 부족분 전체를 "지도" 키워드로 채움 (우선순위 낮게 뒤에 추가)
            jido_count = deficit

            self.progress.emit(f"   📊 구지도 부족 → '지도' 키워드 {jido_count}개 추가 (후순위)")

            regions = place.region.get_keyword_variations()
            if not regions:
                regions = [place.region.gu] if place.region.gu else []

            # 사용자가 키워드를 편집한 경우 사용자 선택만 사용
            keywords_for_jido = self.validated_keywords
            if self.user_keywords:
                keywords_for_jido = [kw for kw in self.validated_keywords if kw in self.user_keywords]
            
            added = 0
            for region in regions:
                for kw in keywords_for_jido:
                    if added >= jido_count:
                        break
                    new_keyword = f"{region} {kw} 지도"
                    if new_keyword not in self.verified_keywords:
                        self.keyword_pool.append({  # 후순위로 뒤에 추가
                            "keyword": new_keyword,
                            "map_type": "구지도",
                            "level": 10  # 낮은 우선순위
                        })
                        added += 1
                if added >= jido_count:
                    break
        
        self.progress.emit(f"Phase 3 완료: 최종 {len(self.keyword_pool)}개 키워드")

    # ==================== Phase 4: 최종 순위 크롤링 ====================
    async def _phase_4_final_ranking(self, place: PlaceData):
        """Phase 4: 목표 개수만 실제 순위 크롤링 + 실시간 UI"""
        place_id = self._get_place_id_from_url(self.url)
        proxy_configs = self._get_proxy_configs()

        # 업종 판별 (nxPlaces API는 모든 업종 지원)
        business_type = self._detect_business_type(place.category)

        # 모드 선택: 모든 업종 GraphQL 지원 (nxPlaces API)
        if self.use_api_mode and HAS_GRAPHQL_MODE:
            mode_name = "GraphQL"
            self.progress.emit(f"Phase 4: 순위 크롤링 시작... [{mode_name} 모드]")
            await self._phase_4_graphql_mode(place_id, proxy_configs, place)
        elif self.use_api_mode and HAS_API_MODE:
            mode_name = "API"
            self.progress.emit(f"Phase 4: 순위 크롤링 시작... [{mode_name} 모드]")
            await self._phase_4_api_mode(place_id, proxy_configs)
        else:
            mode_name = "브라우저"
            self.progress.emit(f"Phase 4: 순위 크롤링 시작... [{mode_name} 모드]")
            await self._phase_4_browser_mode(place_id, proxy_configs)

    async def _phase_4_graphql_mode(self, place_id: str, proxy_configs: List[ProxyConfig], place: PlaceData):
        """Phase 4 - GraphQL API 모드 (가장 빠르고 안정적)
        R-POST: 상호명 1위 키워드 → 업종대표키워드 추가 조합 (restaurant 한정)
        """
        from .rank_checker_graphql import RankCheckerGraphQL, RankResult as GqlRankResult

        found_count = self._get_valid_count()
        business_type = self._detect_business_type(place.category)

        # 좌표 추출 (주소에서 지역 감지)
        coords = None
        address = place.jibun_address or place.road_address
        if address:
            for region, coord in CITY_COORDINATES.items():
                if region in address:
                    coords = coord
                    self.progress.emit(f"   📍 지역 감지: {region}")
                    break

        # R-POST 준비: 상호명 키워드 셋 (source="name")
        name_keyword_set = {item["keyword"] for item in self.keyword_pool
                            if item.get("source") == "name"}
        max_name_combos = int(self.target_count * self.name_rank1_combo_ratio)
        name_combo_count = 0

        # 지역 목록 (R-POST 조합용)
        regions_for_combo = place.region.get_keyword_variations() if place.region else []
        if not regions_for_combo:
            regions_for_combo = [place.region.gu] if place.region and place.region.gu else []

        # 검증할 키워드 분리: 메인 vs 상호명 (상호명은 target 달성 무관 항상 체크)
        main_keywords_to_check = []
        name_keywords_to_check = []
        for item in self.keyword_pool:
            kw = item["keyword"]
            if kw not in self.verified_keywords:
                if item.get("source") == "name":
                    name_keywords_to_check.append(kw)
                else:
                    main_keywords_to_check.append(kw)
                self.verified_keywords.add(kw)

        self.progress.emit(f"   GraphQL 모드: 메인 {len(main_keywords_to_check)}개 + 상호명 {len(name_keywords_to_check)}개")
        if name_keyword_set and business_type == "restaurant":
            self.progress.emit(f"   R-POST 대기: 상호명 {len(name_keyword_set)}개 (최대 {max_name_combos}개 조합)")

        batch_size = 50  # GraphQL 고속 배치 (워커 수 증가에 맞춤)

        # === 업종대표 실패 지역 스킵 준비 ===
        # "지역(들)+맛집" 먼저 체크 → 미노출이면 나머지 업종대표(음식점/식당) 조합 전부 스킵
        biz_keywords = list(self._instance_biz_keywords.get(
            business_type, self._instance_biz_keywords["general"]))
        first_biz = biz_keywords[0] if biz_keywords else ""
        ok_first_biz_set = set()       # 노출 성공 키워드 (예: "부천 중동 맛집")
        failed_first_biz_set = set()   # 미노출 키워드 (예: "신중 맛집")
        failed_biz_regions = set()     # 단일 지역 실패 단어 (fallback용)
        total_skipped = 0

        # "지역(들)+대표업종(맛집)" 선행 체크용 분리
        # 조건: first_biz로 끝나고, 앞 단어가 모두 region인 키워드 (R1+R11)
        region_set = getattr(self, '_phase2_region_set', set())
        primary_biz_kws = []
        remaining_main_kws = []
        if first_biz and region_set:
            for kw in main_keywords_to_check:
                if kw.endswith(f" {first_biz}"):
                    prefix = kw[:-len(f" {first_biz}")].strip()
                    prefix_parts = prefix.split()
                    if prefix_parts and all(p in region_set for p in prefix_parts):
                        primary_biz_kws.append(kw)
                        continue
                remaining_main_kws.append(kw)
        else:
            remaining_main_kws = list(main_keywords_to_check)

        if primary_biz_kws:
            self.progress.emit(
                f"   선행 체크: '{first_biz}' {len(primary_biz_kws)}개 → 미노출 지역 업종대표 조합 스킵")

        async with RankCheckerGraphQL(
            proxies=proxy_configs if proxy_configs else None,
            default_coords=coords,
            use_own_ip=self.use_own_ip,
            user_slot=self.user_slot,
            total_instances=self.total_instances
        ) as checker:

            # === Phase 4A-1: 선행 배치 — "지역+대표업종" 먼저 체크 ===
            if primary_biz_kws and self.is_running and found_count < self.target_count:
                pb_start = 0
                while pb_start < len(primary_biz_kws) and self.is_running and found_count < self.target_count:
                    pb_batch = primary_biz_kws[pb_start:pb_start + batch_size]

                    def primary_progress_cb(current, total, msg):
                        self.sub_progress.emit(found_count + current, self.target_count, msg)
                    checker.set_progress_callback(primary_progress_cb)

                    results = await checker.check_keywords(
                        keywords=pb_batch,
                        target_place_id=place_id,
                        max_rank=self.max_rank,
                        coords=coords
                    )

                    for result in results:
                        converted = RankResult(
                            keyword=result.keyword,
                            rank=result.rank,
                            map_type=result.map_type,
                            status=result.status,
                            error_message=result.error_message
                        )
                        kw_item = next((item for item in self.keyword_pool
                                        if item["keyword"] == result.keyword), None)
                        if kw_item and kw_item.get("source"):
                            converted.source = kw_item["source"]
                        self.all_results.append(converted)

                        if result.rank and self.min_rank <= result.rank <= self.max_rank:
                            found_count += 1
                            ok_first_biz_set.add(result.keyword)
                        elif result.status != "error":
                            # 정상 응답이지만 미노출 → 스킵 세트에 등록
                            failed_first_biz_set.add(result.keyword)
                            prefix = result.keyword[:-len(f" {first_biz}")].strip()
                            prefix_parts = prefix.split()
                            # 단일 지역 실패만 fallback set에 추가 (지역쌍은 전체 키워드 매칭만)
                            if len(prefix_parts) == 1:
                                failed_biz_regions.add(prefix_parts[0])
                            self.progress.emit(
                                f"   ⛔ '{result.keyword}' 미노출 → 업종대표 조합 스킵")

                    pb_start += len(pb_batch)

                skip_info = []
                if failed_biz_regions:
                    skip_info.append(f"단일지역: {failed_biz_regions}")
                if failed_first_biz_set:
                    skip_info.append(f"지역쌍: {len(failed_first_biz_set) - len(failed_biz_regions)}개")
                self.progress.emit(
                    f"   선행 완료: {len(primary_biz_kws)}개 체크, {found_count}개 발견, "
                    f"OK {len(ok_first_biz_set)}개, 스킵 대상: {', '.join(skip_info) if skip_info else '없음'}")

            # === Phase 4A-2: 나머지 메인 키워드 (실패 지역 스킵 적용) ===
            keywords_to_check = remaining_main_kws
            batch_start = 0
            while batch_start < len(keywords_to_check):
                if not self.is_running:
                    break

                if found_count >= self.target_count:
                    self.progress.emit(f"목표 달성! {found_count}개 완료")
                    break

                # 배치 구성 (실패 지역 + 업종대표 키워드 조합 스킵)
                batch = []
                scan_pos = batch_start
                while scan_pos < len(keywords_to_check) and len(batch) < batch_size:
                    kw = keywords_to_check[scan_pos]
                    scan_pos += 1

                    if failed_first_biz_set or failed_biz_regions:
                        parts = kw.split()
                        # biz_keyword 포함 여부 + 위치 찾기
                        biz_hit = None
                        biz_pos = -1
                        for bk in biz_keywords:
                            if bk in parts:
                                biz_pos = parts.index(bk)
                                biz_hit = bk
                                break

                        if biz_hit:
                            # "맛집 버전" 구성 → ok/failed 세트에서 판정
                            prefix = " ".join(parts[:biz_pos])
                            test_kw = f"{prefix} {first_biz}" if prefix else first_biz

                            if test_kw in ok_first_biz_set:
                                pass  # 통과
                            elif test_kw in failed_first_biz_set:
                                total_skipped += 1
                                if total_skipped <= 10:
                                    self.progress.emit(f"   ⏭ 스킵: {kw}")
                                elif total_skipped == 11:
                                    self.progress.emit(f"   ⏭ ... (이후 스킵 로그 생략)")
                                continue
                            else:
                                # fallback: prefix 단어 중 실패 단일 지역이 있으면 스킵
                                if any(p in failed_biz_regions for p in parts[:biz_pos]):
                                    total_skipped += 1
                                    if total_skipped <= 10:
                                        self.progress.emit(f"   ⏭ 스킵: {kw}")
                                    elif total_skipped == 11:
                                        self.progress.emit(f"   ⏭ ... (이후 스킵 로그 생략)")
                                    continue

                    batch.append(kw)
                batch_start = scan_pos

                if not batch:
                    continue

                def progress_cb(current, total, msg):
                    self.sub_progress.emit(found_count + current, self.target_count, msg)

                checker.set_progress_callback(progress_cb)

                results = await checker.check_keywords(
                    keywords=batch,
                    target_place_id=place_id,
                    max_rank=self.max_rank,
                    coords=coords
                )

                for result in results:
                    converted = RankResult(
                        keyword=result.keyword,
                        rank=result.rank,
                        map_type=result.map_type,
                        status=result.status,
                        error_message=result.error_message
                    )
                    kw_item = next((item for item in self.keyword_pool
                                    if item["keyword"] == result.keyword), None)
                    if kw_item and kw_item.get("source"):
                        converted.source = kw_item["source"]
                    self.all_results.append(converted)

                    if result.rank and self.min_rank <= result.rank <= self.max_rank:
                        found_count += 1

                processed = min(scan_pos, len(keywords_to_check))
                skip_msg = f", {total_skipped}개 스킵" if total_skipped > 0 else ""
                self.progress.emit(
                    f"   메인 진행: {processed}/{len(keywords_to_check)} ({found_count}개 발견{skip_msg})")

            # === Phase 4B: 상호명 키워드 (목표 달성 시 즉시 종료) ===
            if name_keywords_to_check and self.is_running:
                # 원본 상호명 개수 기록 (R-POST 추가분 제외 범위)
                original_name_count = len(name_keywords_to_check)
                target_reached_logged = False
                self.progress.emit(f"   상호명 체크: {original_name_count}개")
                batch_start = 0
                while batch_start < len(name_keywords_to_check):
                    if not self.is_running:
                        break

                    # 목표 달성 시 즉시 종료
                    if found_count >= self.target_count:
                        if not target_reached_logged:
                            self.progress.emit(f"   목표 달성 ({found_count}개) → 상호명 체크 종료")
                        break

                    batch = name_keywords_to_check[batch_start:batch_start + batch_size]

                    def name_progress_cb(current, total, msg):
                        self.sub_progress.emit(found_count + current, self.target_count, msg)

                    checker.set_progress_callback(name_progress_cb)

                    results = await checker.check_keywords(
                        keywords=batch,
                        target_place_id=place_id,
                        max_rank=self.max_rank,
                        coords=coords
                    )

                    for result in results:
                        converted = RankResult(
                            keyword=result.keyword,
                            rank=result.rank,
                            map_type=result.map_type,
                            status=result.status,
                            error_message=result.error_message
                        )
                        kw_item = next((item for item in self.keyword_pool
                                        if item["keyword"] == result.keyword), None)
                        if kw_item and kw_item.get("source"):
                            converted.source = kw_item["source"]
                        self.all_results.append(converted)

                        if result.rank and self.min_rank <= result.rank <= self.max_rank:
                            found_count += 1
                            if found_count >= self.target_count and not target_reached_logged:
                                self.progress.emit(f"   목표 달성! {found_count}개 완료")
                                target_reached_logged = True

                        # R-POST: 상호명 1위 → 업종대표키워드 추가 조합 (restaurant 한정)
                        # 목표 달성 전에만 R-POST 추가 (달성 후에는 불필요한 확장 방지)
                        if (result.rank == 1 and result.keyword in name_keyword_set
                                and business_type == "restaurant"
                                and name_combo_count < max_name_combos
                                and found_count < self.target_count):
                            bare_name = getattr(self, '_name_kw_to_bare', {}).get(
                                result.keyword, result.keyword)
                            new_combos = self._add_rank1_name_combos(
                                [bare_name], regions_for_combo, business_type)
                            added_count = 0
                            for combo in new_combos:
                                if combo["keyword"] not in self.verified_keywords:
                                    name_keywords_to_check.append(combo["keyword"])
                                    self.verified_keywords.add(combo["keyword"])
                                    self.keyword_pool.append(combo)
                                    name_combo_count += 1
                                    added_count += 1
                                if name_combo_count >= max_name_combos:
                                    break
                            if added_count > 0:
                                self.progress.emit(
                                    f"   R-POST: '{result.keyword}' 1위 → {added_count}개 조합 추가 "
                                    f"({name_combo_count}/{max_name_combos})")

                    processed = min(batch_start + len(batch), len(name_keywords_to_check))
                    self.progress.emit(f"   상호명 진행: {processed}/{len(name_keywords_to_check)} ({found_count}개 발견)")
                    batch_start += len(batch)

    async def _phase_4_api_mode(self, place_id: str, proxy_configs: List[ProxyConfig], use_html_only: bool = False):
        """Phase 4 - API 직접 호출 모드 (빠름)

        Args:
            use_html_only: True면 HTML 스크래핑만 사용 (병원 검색용)
        """
        from .rank_checker_api import RankCheckerAPI, RankResult as ApiRankResult

        found_count = self._get_valid_count()

        # 검증할 키워드 목록 준비 (중복 제외)
        keywords_to_check = []
        for item in self.keyword_pool:
            kw = item["keyword"]
            if kw not in self.verified_keywords:
                keywords_to_check.append(kw)
                self.verified_keywords.add(kw)

        mode_desc = "HTML 스크래핑" if use_html_only else "API"
        self.progress.emit(f"   {mode_desc} 모드: {len(keywords_to_check)}개 키워드 배치 처리")

        # 배치 크기 (한번에 처리할 키워드 수)
        batch_size = 20

        # use_html_only=True면 use_api_mode=False (순수 HTML 파싱)
        async with RankCheckerAPI(proxies=proxy_configs if proxy_configs else None, use_api_mode=not use_html_only) as checker:
            for batch_start in range(0, len(keywords_to_check), batch_size):
                if not self.is_running:
                    break

                if found_count >= self.target_count:
                    self.progress.emit(f"🎉 목표 달성! {found_count}개 완료")
                    break

                batch = keywords_to_check[batch_start:batch_start + batch_size]

                # 진행률 콜백 설정
                def progress_cb(current, total, msg):
                    self.sub_progress.emit(found_count + current, self.target_count, msg)

                checker.set_progress_callback(progress_cb)

                # 배치 처리
                results = await checker.check_keywords(
                    keywords=batch,
                    target_place_id=place_id,
                    max_rank=self.max_rank
                )

                # 결과 처리
                for result in results:
                    # RankResult 타입 변환 (API 버전 -> 기존 버전)
                    converted = RankResult(
                        keyword=result.keyword,
                        rank=result.rank,
                        map_type=result.map_type,
                        status=result.status,
                        error_message=result.error_message
                    )
                    self.all_results.append(converted)

                    if result.rank and self.min_rank <= result.rank <= self.max_rank:
                        found_count += 1

                # 진행률 표시
                processed = min(batch_start + batch_size, len(keywords_to_check))
                self.progress.emit(f"   진행: {processed}/{len(keywords_to_check)} ({found_count}개 발견)")

    async def _phase_4_browser_mode(self, place_id: str, proxy_configs: List[ProxyConfig]):
        """Phase 4 - 브라우저 모드 (안정적이지만 느림)"""
        found_count = self._get_valid_count()

        async with RankChecker(proxies=proxy_configs if proxy_configs else None, headless=True) as checker:
            self.rank_checker = checker

            for item in self.keyword_pool:
                if not self.is_running:
                    break

                if found_count >= self.target_count:
                    self.progress.emit(f"🎉 목표 달성! {found_count}개 완료")
                    break

                keyword = item["keyword"]

                if keyword in self.verified_keywords:
                    continue

                self.verified_keywords.add(keyword)

                results = await checker.check_keywords(
                    keywords=[keyword],
                    target_place_id=place_id,
                    max_rank=self.max_rank
                )

                if results:
                    result = results[0]
                    self.all_results.append(result)

                    if result.rank and self.min_rank <= result.rank <= self.max_rank:
                        found_count += 1
                        # 실시간 UI 업데이트
                        self.sub_progress.emit(
                            found_count,
                            self.target_count,
                            f"{keyword}: {result.rank}위 [{result.map_type}]"
                        )

    # ==================== 유틸리티 ====================
    def _finish(self):
        """작업 완료 처리 + 지도 비율 리포트"""
        valid_results = [r for r in self.all_results if r.rank is not None and self.min_rank <= r.rank <= self.max_rank]

        # 단일 지도 형태도 포함 (신지도, 신지도(단일) 모두 카운트)
        new_map_count = sum(1 for r in valid_results if r.map_type.startswith("신지도"))
        old_map_count = sum(1 for r in valid_results if r.map_type.startswith("구지도"))
        total_valid = len(valid_results)

        if total_valid > 0:
            new_pct = new_map_count * 100 // total_valid
            old_pct = old_map_count * 100 // total_valid
            self.progress.emit(f"📊 최종 비율: 신지도 {new_map_count}개({new_pct}%), 구지도 {old_map_count}개({old_pct}%)")

        self.progress.emit(f"✅ 작업 완료: {total_valid}개 유효 키워드")
        self.finished.emit(self.all_results)

    def _finish_early(self, reason: str = "중단됨"):
        """중간 중단 시 결과 반환 - 지금까지 찾은 결과 정리"""
        # cancelled 상태 제외하고 유효한 결과만 필터링
        completed_results = [r for r in self.all_results if r.status != "cancelled"]
        valid_results = [r for r in completed_results if r.rank is not None and self.min_rank <= r.rank <= self.max_rank]
        total_valid = len(valid_results)
        total_checked = len(completed_results)

        # 지도 비율 통계
        if total_valid > 0:
            new_map_count = sum(1 for r in valid_results if r.map_type.startswith("신지도"))
            old_map_count = sum(1 for r in valid_results if r.map_type.startswith("구지도"))
            new_pct = new_map_count * 100 // total_valid
            old_pct = old_map_count * 100 // total_valid
            self.progress.emit(f"📊 중단 시점 비율: 신지도 {new_map_count}개({new_pct}%), 구지도 {old_map_count}개({old_pct}%)")

        self.progress.emit(f"⏹️ {reason} - {total_checked}개 검사 완료, {total_valid}개 유효 키워드 저장됨")
        self.finished.emit(self.all_results)
    
    def _get_valid_count(self) -> int:
        """max_rank 이내 유효 결과 수"""
        return sum(1 for r in self.all_results if r.rank is not None and self.min_rank <= r.rank <= self.max_rank)
    
    def _get_place_id_from_url(self, url: str) -> str:
        """URL에서 Place ID 추출"""
        from .url_parser import parse_place_url
        parsed = parse_place_url(url)
        return parsed.mid if parsed.is_valid else ""
    
    def _get_proxy_configs(self) -> List[ProxyConfig]:
        """프록시 딕셔너리를 ProxyConfig로 변환

        Sticky 모드:
        - 포트 기반 (각 포트 = 다른 IP): session_id 불필요
        - 세션 기반 (단일 포트, 다중 세션): session_id 필요 (현재 미지원)
        """
        configs = []
        for p in self.proxies:
            if "host" in p and "port" in p:
                session_type = p.get("session_type", "rotating")

                # 포트 기반 Sticky: 각 포트가 다른 IP이므로 session_id 불필요
                # (Decodo endpoint:port 모드)
                configs.append(ProxyConfig(
                    host=p["host"],
                    port=p["port"],
                    username=p.get("username", ""),
                    password=p.get("password", ""),
                    proxy_type=p.get("type", "datacenter"),
                    session_type=session_type,
                    session_id=""  # 포트 기반이므로 session_id 불필요
                ))
        return configs
