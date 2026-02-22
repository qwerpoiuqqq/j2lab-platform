"""
Async Smart Keyword Worker (Web/FastAPI version)
SmartWorker(QThread)를 asyncio 기반으로 리팩토링

[핵심 변경사항]
- QThread → plain async class
- pyqtSignal → asyncio.Queue (SSE event stream)
- threading.Event → asyncio.Event (cancel)
- 사용자 확인 대기 제거 (auto-confirm)
- 실시간 예약 기능 제거 (_apply_booking_replacement 삭제)
- booking_keyword_ratio / has_booking / booking_type 참조 제거

[아키텍처]
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
import time
from itertools import combinations
from typing import List, Set, Dict, Tuple

from src.place_scraper import PlaceScraper, PlaceData
from src.keyword_generator import KeywordGenerator
from src.rank_checker import RankResult
from src.gemini_client import GeminiClient

# API 모드 (속도 10배 향상) - aiohttp 필요
try:
    from src.rank_checker_api import RankCheckerAPI, check_ranks_api
    HAS_API_MODE = True
except ImportError:
    HAS_API_MODE = False

# GraphQL 모드 (가장 안정적이고 빠름)
try:
    from src.rank_checker_graphql import RankCheckerGraphQL, ProxyConfig, check_ranks_graphql, CITY_COORDINATES
    HAS_GRAPHQL_MODE = True
except ImportError:
    HAS_GRAPHQL_MODE = False
    from src.rank_checker import ProxyConfig


def _is_plt(r) -> bool:
    """PLT 판정: 상호명 + 1위 + 검색결과 1개"""
    if getattr(r, 'source', None) != "name" or r.rank != 1:
        return False
    tc = getattr(r, 'total_count', None)
    return tc is None or tc == 1


class AsyncSmartWorker:
    """
    비동기 키워드 작업 워커 (FastAPI/웹 서비스용)

    [주요 개선점]
    - 대표 1개 검증 -> 전체 확정 (크롤링 85% 감소)
    - 계층적 키워드 조합 (L1~L4)
    - 실시간 SSE 이벤트 스트리밍
    - 조기 중단 지원 (asyncio.Event)
    """

    # ==================== 상수 정의 ====================
    # 리뷰 테마 -> 검색 필터/수식어 매핑 테이블 (1:N)
    # 브라우저 분석 기반: 실제 플레이스 필터와 연동되는 키워드로 변환
    # NOTE: 맛집(restaurant) 업종에만 적용
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

    # 지역 접미 수식어 (역/동 뒤에 붙는 수식어)
    LOCATION_SUFFIXES = ["근처", "주변", "부근", "가까운"]

    # 전국에 중복으로 존재하는 동 이름 (단독 사용 시 검색 결과 부정확)
    DUPLICATE_DONG_NAMES = {
        # 서울/경기 중복
        "역삼동", "역삼", "신사동", "신사", "삼성동", "삼성", "대치동", "대치",
        "청담동", "청담", "논현동", "논현", "서초동", "서초", "방배동", "방배",
        "잠실동", "잠실", "송파동", "송파", "강동", "강서동", "강서",
        "고덕동", "고덕",
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
    RESTAURANT_CATEGORIES = {
        "음식", "요리", "식당", "카페", "주점", "호프", "맛집",
        "한식", "양식", "일식", "중식", "분식", "뷔페", "레스토랑",
        "고기", "구이", "회", "돈가스", "파스타", "피자", "버거",
        "갈비", "곱창", "국밥", "면", "제과", "베이커리", "디저트",
        "치킨", "족발", "보쌈", "찜", "탕", "전골", "냉면", "칼국수",
        "커피", "브런치", "펍", "바", "이자카야", "선술집"
    }

    HOSPITAL_CATEGORIES = {
        "병원", "의원", "치과", "한의원", "클리닉", "피부과",
        "정형외과", "신경외과", "내과", "외과", "안과", "이비인후과",
        "재활의학과", "산부인과", "비뇨기과", "성형외과", "마취통증의학과",
        "소아과", "정신과", "신경과", "흉부외과", "심장내과",
        "동물병원", "수의과", "펫클리닉"
    }

    BUSINESS_TYPE_KEYWORDS = {
        "restaurant": ["맛집", "음식점", "식당"],
        "hospital":   ["병원", "의원", "병의원"],
        "general":    ["전문점", "매장"],
    }

    # 필수 수식어 (모든 업종, 하드코딩) - "위치" 추가
    MANDATORY_MODIFIERS = ["지도", "위치", "추천"]

    # 상호명 1위 조합 비율 기본값 (맛집 한정, 목표 개수 대비 %)
    NAME_RANK1_COMBO_RATIO_DEFAULT = 0.40  # 기본 40%

    def __init__(self, url: str, target_count: int, event_queue: asyncio.Queue, job_id: str,
                 max_rank: int = 50, min_rank: int = 1,
                 proxies: List[Dict] = None, new_map_ratio: int = 70,
                 use_api_mode: bool = True, use_own_ip: bool = True,
                 user_slot: int = 0, total_instances: int = 1,
                 modifiers: Dict = None, basic_only: bool = False,
                 name_rank1_combo_ratio: float = 0.40,
                 name_keyword_ratio: float = 0.30,
                 gemini_api_key: str = None, gemini_model: str = None):
        self.url = url
        self.target_count = target_count
        self._event_queue = event_queue
        self._job_id = job_id
        self.max_rank = max_rank
        self.min_rank = min_rank
        self.proxies = proxies or []
        self.new_map_ratio = new_map_ratio
        self.use_api_mode = use_api_mode and HAS_API_MODE
        self.use_own_ip = use_own_ip
        self.user_slot = user_slot
        self.total_instances = total_instances
        self.modifiers = modifiers or {}
        self.basic_only = basic_only
        self.name_rank1_combo_ratio = name_rank1_combo_ratio
        self.name_keyword_ratio = name_keyword_ratio

        # Cancel event (replaces self.is_running boolean)
        self._cancel_event = asyncio.Event()
        self._place_name = ""

        # 클래스 변수를 인스턴스로 복사 (멀티 JobWorker 간 오염 방지)
        self._instance_biz_keywords = copy.deepcopy(self.BUSINESS_TYPE_KEYWORDS)

        # 웹 버전: 사용자 편집 데이터 없음 (auto-confirm)
        self.user_regions = None
        self.user_keywords = []
        self.user_name_parts = []
        self.user_modifiers_list = []
        self.user_region_keyword_combos = []
        self._user_regions_set = False
        self.provided_place_data = None

        # 내부 상태
        self.scraper = None
        self.generator = KeywordGenerator()
        self.rank_checker = None

        # GeminiClient: 워커별 인스턴스 생성
        if gemini_api_key:
            self.gemini_client = GeminiClient(api_key=gemini_api_key, model_name=gemini_model)
        else:
            self.gemini_client = GeminiClient()  # disabled

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

    # ==================== Event emission ====================
    def _emit_nowait(self, event_type: str, data):
        """SSE 이벤트 큐에 이벤트 전송 (비블로킹 - 큐 꽉 차면 오래된 이벤트 버림)"""
        # sub_progress일 때 확정 키워드 수 자동 추가
        if event_type == "sub_progress" and isinstance(data, dict):
            data["found_count"] = len(self.all_results)
        event = {
            "type": event_type,
            "job_id": self._job_id,
            "data": data,
            "timestamp": time.time()
        }
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # 큐가 꽉 참 (브라우저 미연결) → 오래된 이벤트 버리고 새 이벤트 추가
            try:
                self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def _emit(self, event_type: str, data):
        """SSE 이벤트 큐에 이벤트 전송 (하위호환용 - 내부적으로 비블로킹)"""
        self._emit_nowait(event_type, data)

    # ==================== Running check ====================
    @property
    def is_running(self) -> bool:
        return not self._cancel_event.is_set()

    def stop(self):
        """작업 중단"""
        self._cancel_event.set()
        if self.rank_checker:
            self.rank_checker.stop()

    # ==================== 사용자 수식어 적용 ====================
    def _apply_user_modifiers(self):
        """사용자 정의 수식어 적용 (업종 대표 키워드 + GUI 수식어)"""
        if not self.modifiers:
            return

        print(f"[AsyncSmartWorker] 사용자 수식어 적용: {list(self.modifiers.keys())}")

        # 업종별 대표 키워드 덮어쓰기 (인스턴스 변수에만 적용)
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

    # ==================== 업종 판별 ====================
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

    # ==================== Main run ====================
    async def run(self):
        try:
            # Phase 0: 데이터 추출
            place_data = await self._phase_0_extract_data()
            if not place_data:
                return
            if not self.is_running:
                await self._finish_early("Phase 0에서 중단됨")
                return

            # AI 기반 키워드 분류 (Phase 0 이후, Phase 1 이전)
            await self._classify_with_ai(place_data)
            if not self.is_running:
                return

            # Phase 1: 키워드 검증 (API 모드로 빠르게)
            await self._phase_1_validate_samples(place_data)
            if not self.is_running:
                await self._finish_early("Phase 1에서 중단됨")
                return

            # AUTO-CONFIRM: go directly to Phase 2 (NO user confirmation)
            await self._emit("progress", "Phase 1 완료 → Phase 2 자동 시작")

            # Phase 2: 계층적 키워드 풀 생성
            await self._phase_2_generate_pool(place_data)
            if not self.is_running:
                await self._finish_early("Phase 2에서 중단됨")
                return

            # Phase 3: 비율 조정
            await self._phase_3_adjust_ratio(place_data)
            if not self.is_running:
                await self._finish_early("Phase 3에서 중단됨")
                return

            # Preview
            preview_keywords = [item["keyword"] for item in self.keyword_pool]
            await self._emit("preview", {"keywords": preview_keywords, "count": len(preview_keywords)})
            await self._emit("progress", f"{len(preview_keywords)}개 키워드 생성 → 바로 순위 체크 시작")

            # Phase 4: 최종 순위 크롤링 (목표까지 무한 루프)
            await self._phase_4_final_ranking(place_data)

            # 중단되었든 완료되었든 결과 반환
            if self.is_running:
                await self._finish()
            else:
                await self._finish_early("사용자가 중단함")

        except Exception as e:
            import traceback
            traceback.print_exc()
            await self._emit("error_event", str(e))

    # ==================== Phase 0: 데이터 추출 ====================
    async def _phase_0_extract_data(self) -> PlaceData:
        """Phase 0: 플레이스 데이터 추출 + 상호명 파싱"""
        # 이미 추출된 데이터가 있으면 사용
        if self.provided_place_data:
            place_data = self.provided_place_data
            self._place_name = place_data.name
            await self._emit("progress", f"{place_data.name} (기존 데이터 사용)")

            if self.user_keywords:
                place_data.keywords = self.user_keywords
                await self._emit("progress", f"   사용자 키워드: {len(self.user_keywords)}개")
            if self.user_name_parts:
                place_data.name_parts = self.user_name_parts
                await self._emit("progress", f"   사용자 상호명: {self.user_name_parts}")

            return place_data

        # 새로 추출
        await self._emit("progress", "Phase 0: 플레이스 데이터 분석 중...")

        self.scraper = PlaceScraper(headless=True)
        async with self.scraper:
            place_data = await self.scraper.get_place_data_by_url(self.url)
            if not place_data:
                raise Exception("플레이스 데이터를 가져올 수 없습니다.")

        self._place_name = place_data.name
        await self._emit("progress", f"{place_data.name} ({place_data.category})")

        # 상호명 띄어쓰기 파싱
        name_parts = self._parse_business_name(place_data.name)
        if name_parts:
            await self._emit("progress", f"   상호명 파싱: {name_parts}")

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
                print(f"[AsyncSmartWorker] 새 카테고리 저장: {category}")
        except Exception as e:
            print(f"[AsyncSmartWorker] 카테고리 저장 실패: {e}")

    # ==================== AI 기반 키워드 분류 ====================
    async def _classify_with_ai(self, place_data: PlaceData):
        """Gemini API로 키워드를 지역/메뉴/수식어 등으로 분류 (1회 호출)

        결과를 self._ai_classification에 캐싱.
        실패 시 None 유지 -> 기존 규칙 기반 로직으로 폴백.
        """
        if not self.gemini_client or not self.gemini_client.is_available():
            print("[AsyncSmartWorker] AI 분류 스킵: Gemini API 사용 불가")
            return

        try:
            await self._emit("progress", "AI 키워드 분류 중...")

            result = await asyncio.to_thread(
                self.gemini_client.comprehensive_parse,
                name=place_data.name,
                category=place_data.category,
                address=getattr(place_data, 'address', '') or '',
                keywords=place_data.keywords[:15] if place_data.keywords else None,
                menus=place_data.menus[:15] if place_data.menus else None
            )

            if result.success:
                self._ai_classification = result
                ai_regions = result.get_all_regions()
                await self._emit("progress",
                    f"   AI 분류 완료: 지역 {len(ai_regions)}개, "
                    f"업종 {len(result.business_types)}개, "
                    f"서비스 {len(result.services)}개, "
                    f"수식어 {len(result.modifiers)}개, "
                    f"테마 {len(result.themes)}개"
                )
                if ai_regions:
                    await self._emit("progress", f"   AI 지역: {ai_regions}")
                if result.business_types:
                    await self._emit("progress", f"   AI 업종: {result.business_types}")
                if result.services:
                    await self._emit("progress", f"   AI 서비스: {result.services}")
            else:
                print(f"[AsyncSmartWorker] AI 분류 실패: {result.error_message}")
                await self._emit("progress", f"   AI 분류 실패 → 규칙 기반 폴백")

        except Exception as e:
            print(f"[AsyncSmartWorker] AI 분류 예외: {e}")
            await self._emit("progress", f"   AI 분류 예외 → 규칙 기반 폴백")

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
            print(f"[AsyncSmartWorker] 발견된 지역 키워드: {place_data.discovered_regions}")

    # ==================== Phase 1: 키워드 검증 ====================
    async def _phase_1_validate_samples(self, place: PlaceData):
        """Phase 1: 각 키워드 검증 (API 모드로 10배 빠름, 배치 처리)"""
        print("[Phase1] 시작")

        # 업종 판별
        business_type = self._detect_business_type(place.category)
        use_html_mode = False

        if self.use_api_mode and HAS_GRAPHQL_MODE:
            mode_name = f"GraphQL ({business_type})"
        elif HAS_API_MODE:
            mode_name = f"HTML ({business_type})"
            use_html_mode = True
        else:
            mode_name = "브라우저"
        await self._emit("progress", f"Phase 1: 키워드 검증 중... [{mode_name} 모드]")

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
            await self._emit("progress", "지역 정보 없음")
            return

        # 업종 판별 (이미 위에서 수행)
        await self._emit("progress", f"   업종: {business_type}")

        # 검증할 키워드 수집
        base_keywords_set: set = set()

        # 1. 상호명 파싱 (모든 업종 공통)
        name_parts = getattr(place, 'name_parts', self._parse_business_name(place.name))
        base_keywords_set.update(name_parts)
        if name_parts:
            await self._emit("progress", f"   상호명 파싱: {list(name_parts)[:5]}")

        # 2. 카테고리 (모든 업종 공통, 쉼표로 분리)
        if place.category:
            for cat in place.category.split(','):
                cat = cat.strip()
                if cat:
                    base_keywords_set.add(cat)
            await self._emit("progress", f"   카테고리: {place.category}")

        # 3. keywordList에서 - 모든 업종 공통
        if place.keywords:
            for compound_kw in place.keywords:
                base_keywords_set.add(compound_kw)
                await self._emit("progress", f"   키워드: '{compound_kw}'")

        # 4. 메뉴 (맛집만 해당)
        if business_type == "restaurant" and place.menus:
            base_keywords_set.update(place.menus)
            await self._emit("progress", f"   메뉴 키워드: {len(place.menus)}개")

        # 5. 병원 전용: 진료과목
        if business_type == "hospital" and place.medical_subjects:
            base_keywords_set.update(place.medical_subjects)
            await self._emit("progress", f"   진료과목: {place.medical_subjects}")

        # 6. 리뷰 테마 키워드 (맛집만 - 분위기, 가성비 등)
        if business_type == "restaurant" and place.review_theme_keywords:
            theme_labels = [t.label for t in place.review_theme_keywords if t.label]
            # 테마 -> 검색 키워드 매핑 적용
            for theme in theme_labels:
                mapped = self.THEME_MAPPING.get(theme, [])
                if mapped:
                    base_keywords_set.update(mapped[:2])  # 상위 2개만
            await self._emit("progress", f"   리뷰 테마: {len(theme_labels)}개")

        # 2글자 이상만 필터링 (지역명 제외)
        base_keywords = list(k for k in base_keywords_set
                           if k and len(k) >= 2 and k not in place.discovered_regions)

        await self._emit("progress", f"   테스트 대상: {len(base_keywords)}개 키워드")
        await self._emit("progress", f"   메인 지역: {main_region} / 폴백 지역: {fallback_region or '없음'}")

        # 프록시 설정
        proxy_configs = self._get_proxy_configs()
        place_id = self._get_place_id_from_url(self.url)

        print(f"[Phase1] base_keywords={len(base_keywords)}개, main_region={main_region}, place_id={place_id}")
        print(f"[Phase1] use_api_mode={self.use_api_mode}, HAS_GRAPHQL_MODE={HAS_GRAPHQL_MODE}")

        # 모드 선택
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

        await self._emit("progress", f"Phase 1 완료: {len(self.validated_keywords)}/{len(base_keywords)}개 키워드 확정")

    async def _phase_1_graphql_batch(self, base_keywords: List[str], main_region: str,
                                      fallback_region: str, place_id: str, proxy_configs: List[ProxyConfig]):
        """Phase 1 - GraphQL 배치 처리 (가장 빠르고 안정적)"""
        print(f"[GraphQL Batch] 시작: main_region={main_region}, keywords={len(base_keywords)}개")

        from src.rank_checker_graphql import RankCheckerGraphQL
        print("[GraphQL Batch] import 성공")

        # 지역에서 좌표 추출 (긴 지역명 우선 매칭)
        coords = None
        matched_region = None

        sorted_regions = sorted(CITY_COORDINATES.keys(), key=len, reverse=True)
        for region in sorted_regions:
            if region in main_region:
                coords = CITY_COORDINATES[region]
                matched_region = region
                print(f"[GraphQL Batch] 좌표 매칭: {region} -> {coords}")
                await self._emit("progress", f"   좌표 감지: {region}")
                break

        if not coords:
            print(f"[GraphQL Batch] 좌표 없음 (main_region={main_region}), 기본값 서울 사용")
            coords = CITY_COORDINATES.get("서울")
            matched_region = "서울"

        # 1차: 메인 지역 + 키워드 (배치)
        test_keywords_main = [f"{main_region} {kw}" for kw in base_keywords]
        kw_map_main = {f"{main_region} {kw}": kw for kw in base_keywords}

        await self._emit("progress", f"   GraphQL 1차 배치: {len(test_keywords_main)}개 키워드")
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
                    # Fire-and-forget: put_nowait for sync callback
                    try:
                        self._event_queue.put_nowait({
                            "type": "sub_progress",
                            "job_id": self._job_id,
                            "data": {"current": current, "total": total, "message": msg, "found_count": self._get_valid_count()},
                            "timestamp": time.time()
                        })
                    except asyncio.QueueFull:
                        pass
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

                    print(f"[Phase1 DEBUG] {result.keyword}: status={result.status}, rank={result.rank}, error={result.error_message}")

                    if result.status == "error":
                        await self._emit("progress", f"   {original_kw} 에러: {result.error_message}")
                        failed_keywords.append(original_kw)
                    elif result.rank and self.min_rank <= result.rank <= self.max_rank:
                        self.validated_keywords.append(original_kw)
                        self.validated_map_types[original_kw] = result.map_type
                        await self._emit("progress", f"   {original_kw} 확정 (GraphQL, {result.rank}위)")
                        converted = RankResult(
                            keyword=result.keyword, rank=result.rank,
                            map_type=result.map_type, status=result.status
                        )
                        self.all_results.append(converted)
                    else:
                        await self._emit("progress", f"   {original_kw} 순위권 외 ({result.status})")
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

                    await self._emit("progress", f"   GraphQL 2차 폴백: {len(test_keywords_fallback)}개 키워드")

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
                            await self._emit("progress", f"   {original_kw} 폴백 확정 (GraphQL, {result.rank}위)")
                            converted = RankResult(
                                keyword=result.keyword, rank=result.rank,
                                map_type=result.map_type, status=result.status
                            )
                            self.all_results.append(converted)
                        else:
                            await self._emit("progress", f"   {original_kw} 제외")

        except Exception as e:
            print(f"[GraphQL Batch] ERROR: {type(e).__name__}: {e}")
            await self._emit("progress", f"   GraphQL 에러: {e}")
            import traceback
            traceback.print_exc()

    async def _phase_1_api_batch(self, base_keywords: List[str], main_region: str,
                                  fallback_region: str, place_id: str, proxy_configs: List[ProxyConfig],
                                  use_html_only: bool = False):
        """Phase 1 - API 배치 처리 (10배 빠름)

        Args:
            use_html_only: True면 HTML 스크래핑만 사용 (병원 검색용)
        """
        from src.rank_checker_api import RankCheckerAPI

        # 1차: 메인 지역 + 키워드 (배치)
        test_keywords_main = [f"{main_region} {kw}" for kw in base_keywords]
        kw_map_main = {f"{main_region} {kw}": kw for kw in base_keywords}

        mode_desc = "HTML" if use_html_only else "API"
        await self._emit("progress", f"   1차 배치 ({mode_desc}): {len(test_keywords_main)}개 키워드")

        async with RankCheckerAPI(proxies=proxy_configs if proxy_configs else None, use_api_mode=not use_html_only) as checker:
            # 진행률 콜백
            def progress_cb(current, total, msg):
                try:
                    self._event_queue.put_nowait({
                        "type": "sub_progress",
                        "job_id": self._job_id,
                        "data": {"current": current, "total": total, "message": msg, "found_count": self._get_valid_count()},
                        "timestamp": time.time()
                    })
                except asyncio.QueueFull:
                    pass
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
                    await self._emit("progress", f"   {original_kw} 확정 ({result.map_type}, {result.rank}위)")
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

                await self._emit("progress", f"   2차 폴백: {len(test_keywords_fallback)}개 키워드")

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
                        await self._emit("progress", f"   {original_kw} 폴백 확정 ({result.map_type}, {result.rank}위)")
                        converted = RankResult(
                            keyword=result.keyword, rank=result.rank,
                            map_type=result.map_type, status=result.status
                        )
                        self.all_results.append(converted)
                    else:
                        await self._emit("progress", f"   {original_kw} 제외")

    async def _phase_1_browser_sequential(self, base_keywords: List[str], main_region: str,
                                           fallback_region: str, place_id: str, proxy_configs: List[ProxyConfig]):
        """Phase 1 - 브라우저 순차 처리 (안정적이지만 느림)"""
        from src.rank_checker import RankChecker
        async with RankChecker(proxies=proxy_configs if proxy_configs else None, headless=True) as checker:
            self.rank_checker = checker

            total_keywords = len(base_keywords)
            for i, kw in enumerate(base_keywords):
                if not self.is_running:
                    return

                await self._emit("sub_progress", {"current": i + 1, "total": total_keywords, "message": f"검사 중: {kw}"})

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
                    await self._emit("progress", f"   {kw} 확정 ({results[0].map_type}, {results[0].rank}위)")
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
                        await self._emit("progress", f"   {kw} 폴백 확정 ({results_fallback[0].map_type}, {results_fallback[0].rank}위)")
                        self.all_results.extend(results_fallback)
                        continue

                await self._emit("progress", f"   {kw} 제외")

    # ==================== _prepare_phase1_data (auto-confirm용 간소화) ====================
    async def _prepare_phase1_data(self, place_data: PlaceData) -> dict:
        """Phase 1 완료 후 데이터 준비 (형태소 분석 적용)"""
        # 1. 기본 지역 정보 수집
        base_regions = []

        if place_data.region.si:
            base_regions.append(place_data.region.si)
        if place_data.region.si_without_suffix:
            base_regions.append(place_data.region.si_without_suffix)
        if place_data.region.major_area:
            base_regions.append(place_data.region.major_area)
        if place_data.region.gu:
            base_regions.append(place_data.region.gu)
        if place_data.region.gu_without_suffix:
            base_regions.append(place_data.region.gu_without_suffix)
        if place_data.region.dong:
            base_regions.append(place_data.region.dong)
        if place_data.region.dong_without_suffix:
            base_regions.append(place_data.region.dong_without_suffix)
        if place_data.region.station:
            base_regions.append(place_data.region.station)
        for station in place_data.region.stations:
            if station and station not in base_regions:
                base_regions.append(station)
        if place_data.region.road:
            base_regions.append(place_data.region.road)

        if hasattr(place_data, 'discovered_regions'):
            base_regions.extend(list(place_data.discovered_regions))

        base_regions = list(dict.fromkeys([r for r in base_regions if r]))

        # 2. 지역 조합 자동 생성
        regions = self._generate_region_combinations(base_regions)
        print(f"[AsyncSmartWorker] 지역 조합 생성: {len(base_regions)}개 → {len(regions)}개")

        # 3. 키워드 수집
        keywords = []
        keywords.extend(place_data.keywords)
        keywords.extend(place_data.menus[:10])
        for rk in place_data.review_menu_keywords[:10]:
            if rk.label not in keywords:
                keywords.append(rk.label)
        keywords.extend(place_data.medical_subjects)

        # 4. 단독 사용 불가 키워드 필터링
        keywords = self._filter_standalone_keywords(keywords)

        # 5. 상호명 형태소 분석 (분리 + 조합)
        name_parts = await self._parse_business_name_morphemes(place_data.name)
        print(f"[AsyncSmartWorker] 상호명 형태소 분석: '{place_data.name}' → {name_parts}")

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
            print(f"[AsyncSmartWorker] 사용자 키워드 적용: {len(self.user_keywords)}개")
        if self.user_name_parts:
            place_data.name_parts = self.user_name_parts
            print(f"[AsyncSmartWorker] 사용자 상호명 적용: {self.user_name_parts}")

    # ==================== 지역 조합 생성 ====================
    def _generate_region_combinations(self, regions: List[str]) -> List[str]:
        """
        지역 조합 자동 생성
        1단계: 개별 지역 - 동 단위는 단독 사용 금지
        2단계: 지역끼리 2개 조합
        3단계: 도로명 조합
        4단계: 수식어 조합
        """
        result = set()

        # === 1단계: 개별 지역 및 분류 ===
        core_regions = []
        dong_regions = []
        station_list = []
        road_list = []

        for r in regions:
            r_stripped = r.strip()
            if not r_stripped:
                continue

            if r_stripped.endswith("역"):
                station_list.append(r_stripped)
                result.add(r_stripped)
                base = r_stripped[:-1]
                if len(base) >= 2 and base not in core_regions:
                    core_regions.append(base)
                    result.add(base)
            elif r_stripped.endswith("로") or r_stripped.endswith("길"):
                road_list.append(r_stripped)
            elif r_stripped.endswith("동"):
                base = r_stripped[:-1]
                if r_stripped in self.DUPLICATE_DONG_NAMES or base in self.DUPLICATE_DONG_NAMES:
                    dong_regions.append(r_stripped)
                    if len(base) >= 2 and base not in dong_regions:
                        dong_regions.append(base)
                else:
                    result.add(r_stripped)
                    if len(base) >= 2 and base not in core_regions:
                        core_regions.append(base)
                        result.add(base)
            elif r_stripped.endswith("시") or r_stripped.endswith("구"):
                result.add(r_stripped)
                base = r_stripped[:-1]
                if len(base) >= 2 and base not in core_regions:
                    core_regions.append(base)
                    result.add(base)
            else:
                if len(r_stripped) >= 2:
                    result.add(r_stripped)
                    if r_stripped not in core_regions:
                        core_regions.append(r_stripped)

        # === 2단계: 지역끼리 2개 조합 ===
        combo_regions = []

        for dong in dong_regions:
            for parent in core_regions[:6]:
                combo = f"{parent} {dong}"
                if combo not in result:
                    result.add(combo)
                    combo_regions.append(combo)

        for i, r1 in enumerate(core_regions[:6]):
            for j, r2 in enumerate(core_regions[:6]):
                if i != j and r1 != r2:
                    combo = f"{r1} {r2}"
                    if combo not in result:
                        result.add(combo)
                        combo_regions.append(combo)

        # === 3단계: 도로명 조합 ===
        for road in road_list:
            for region in core_regions[:4]:
                road_combo = f"{region} {road}"
                if road_combo not in result:
                    result.add(road_combo)

        # === 4단계: 수식어 조합 ===
        for region in core_regions[:6]:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{region} {suffix}")

        for station in station_list:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{station} {suffix}")
                result.add(f"{station}{suffix}")

        for combo in combo_regions[:8]:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{combo} {suffix}")

        return list(result)

    # ==================== 상호명 형태소 분석 ====================
    async def _parse_business_name_morphemes(self, name: str) -> List[str]:
        """
        상호명 형태소 분석 및 조합 생성
        예: "세라믹치과의원" -> ["세라믹", "치과", "의원", "세라믹치과", "치과의원", "세라믹치과의원"]
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
                ai_keywords = await asyncio.to_thread(self.gemini_client.parse_name, name, "")
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

    # ==================== 단독 사용 불가 키워드 필터링 ====================
    def _filter_standalone_keywords(self, keywords: List[str]) -> List[str]:
        """단독 사용 불가 키워드 필터링"""
        filtered = []
        for kw in keywords:
            kw_stripped = kw.strip()
            if kw_stripped in self.STANDALONE_BLOCKED:
                continue
            parts = kw_stripped.split()
            if len(parts) >= 2:
                filtered.append(kw_stripped)
            elif kw_stripped not in self.STANDALONE_BLOCKED:
                filtered.append(kw_stripped)
        return filtered

    # ==================== Phase 2: 계층적 키워드 풀 생성 ====================
    async def _phase_2_generate_pool(self, place: PlaceData):
        """Phase 2: 계층적 키워드 조합 생성 (R1~R18)

        [핵심 원칙] 기본 -> 수식어 -> 키워드 -> 수식어 -> 확장 -> 수식어 (각 단계 직후 수식어)
        """
        await self._emit("progress", "Phase 2: 키워드 풀 생성 중...")

        # ========== 지역 수집 (사용자 데이터 우선) ==========
        if self._user_regions_set:
            regions = [r.strip() for r in (self.user_regions or []) if r.strip()]
            if not regions:
                await self._emit("progress", "   사용자가 모든 지역 해제 → 지역 없이 진행")
            else:
                await self._emit("progress", f"   사용자 지역: {len(regions)}개")
        else:
            base_regions = []
            addr_regions = place.region.get_keyword_variations()
            if addr_regions:
                base_regions.extend(addr_regions)

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

            if place.discovered_regions:
                base_regions.extend(list(place.discovered_regions))

            regions = self._generate_region_combinations(base_regions)
            if not regions:
                regions = [place.region.gu] if place.region.gu else [""]

            await self._emit("progress", f"   지역 조합: {len(base_regions)}개 → {len(regions)}개")

        # ========== 업종 판별 + 대표 키워드/수식어 준비 ==========
        business_type = self._detect_business_type(place.category)
        biz_keywords = list(self._instance_biz_keywords.get(business_type,
                            self._instance_biz_keywords["general"]))

        # 수식어 풀 (하드코딩 + GUI, 배타적 사용)
        if self.user_modifiers_list:
            user_mods = [m.strip() for m in self.user_modifiers_list if m.strip()]
            all_modifiers = list(self.MANDATORY_MODIFIERS)
            for m in user_mods:
                if m not in all_modifiers:
                    all_modifiers.append(m)
            await self._emit("progress", f"   사용자 수식어 사용: {user_mods}")
        else:
            all_modifiers = list(self.MANDATORY_MODIFIERS)  # ["지도", "위치", "추천"]
            gui_mods = getattr(self, '_gui_modifiers', [])
            gui_mods_unique = [m for m in gui_mods if m not in all_modifiers]
            all_modifiers.extend(gui_mods_unique)

        # AI 수식어/테마 추가
        if self._ai_classification:
            for m in self._ai_classification.modifiers:
                if m not in all_modifiers:
                    all_modifiers.append(m)
            # 테마: 맛집 업종만 적용
            if business_type == "restaurant":
                for t in self._ai_classification.themes:
                    if t not in all_modifiers:
                        all_modifiers.append(t)

        # 맛집일 때 식당/음식점 수식어 추가
        if business_type == "restaurant":
            for extra in ["식당", "음식점"]:
                if extra not in all_modifiers:
                    all_modifiers.append(extra)

        await self._emit("progress", f"   업종: {business_type} → 대표키워드: {biz_keywords}")
        await self._emit("progress", f"   수식어: {all_modifiers} (필수: {self.MANDATORY_MODIFIERS})")

        # AI 분류 시 지역 세트 (priority_keywords 필터용)
        ai_region_set = set()
        if self._ai_classification:
            ai_region_set = set(self._ai_classification.get_all_regions())

        # ========== 키워드 소스 수집 ==========
        priority_keywords = []
        name_keywords = []

        if self.user_keywords:
            priority_keywords = [kw.strip() for kw in self.user_keywords if kw.strip()]
            await self._emit("progress", f"   사용자 키워드만 사용: {len(priority_keywords)}개")
        else:
            if self._ai_classification:
                for kw in self._ai_classification.business_types:
                    if kw and kw not in priority_keywords:
                        priority_keywords.append(kw)
                for kw in self._ai_classification.services:
                    if kw and kw not in priority_keywords:
                        priority_keywords.append(kw)
                for kw in self._ai_classification.related_keywords:
                    if kw and kw not in priority_keywords:
                        priority_keywords.append(kw)

                # 기존 소스에서 보충
                if place.category:
                    for cat in place.category.split(','):
                        cat = cat.strip()
                        if cat and cat not in priority_keywords and cat not in ai_region_set:
                            priority_keywords.append(cat)
                if business_type == "restaurant" and place.menus:
                    for menu in place.menus[:20]:
                        if menu and menu not in priority_keywords and menu not in ai_region_set:
                            priority_keywords.append(menu)
                if place.keywords:
                    for kw in place.keywords[:15]:
                        if kw and kw not in priority_keywords and kw not in ai_region_set:
                            priority_keywords.append(kw)

                await self._emit("progress", f"   AI 분류 기반 키워드 수집: {len(priority_keywords)}개")
            else:
                # 기존 규칙 기반 모드
                if place.category:
                    for cat in place.category.split(','):
                        cat = cat.strip()
                        if cat and cat not in priority_keywords:
                            priority_keywords.append(cat)

                if business_type == "restaurant" and place.menus:
                    for menu in place.menus[:20]:
                        if menu and menu not in priority_keywords:
                            priority_keywords.append(menu)

                if place.keywords:
                    for kw in place.keywords[:15]:
                        if kw and kw not in priority_keywords:
                            priority_keywords.append(kw)

        # Phase 1 검증 키워드 추가 (우선순위 높음)
        if self.validated_keywords:
            user_selected_set = set(self.user_keywords) if self.user_keywords else None
            for vk in list(self.validated_keywords):
                if user_selected_set is not None and vk not in user_selected_set:
                    continue
                if vk and vk not in priority_keywords:
                    priority_keywords.insert(0, vk)

        # 최종 필터: priority_keywords에서 AI 지역명 제거
        if ai_region_set:
            priority_keywords = [kw for kw in priority_keywords if kw not in ai_region_set]

        # 5. 상호명 (최후순위)
        if self.user_name_parts:
            name_parts = self.user_name_parts
        else:
            # 항상 morpheme 분석 실행 (Phase 0의 단순 split보다 정교한 결과)
            morpheme_parts = await self._parse_business_name_morphemes(place.name)
            simple_parts = getattr(place, 'name_parts', []) or []
            # morpheme 결과 + 단순 split 결과 합침 (중복 제거)
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

        await self._emit("progress", f"   메인 키워드: {len(priority_keywords)}개, 상호명: {name_keywords}")

        # ========== 키워드 생성 (R1~R18) ==========
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

        # === 대각선 레벨 0: 기본 ===

        # R1(L0): 지역 + 업종대표키워드
        await self._emit("progress", "   R1: 지역 + 업종대표키워드")
        for region in regions:
            for bk in biz_keywords:
                add(f"{region} {bk}", 0)
        await self._emit("progress", f"   R1: {len(self.keyword_pool)}개")

        # R2(L1): 지역 + 키워드
        await self._emit("progress", "   R2: 지역 + 키워드")
        for region in regions:
            for kw in priority_keywords:
                add(f"{region} {kw}", 1)
        await self._emit("progress", f"   R2: {len(self.keyword_pool)}개")

        # 사용자 편집 지역+키워드 조합
        if self.user_region_keyword_combos:
            for combo in self.user_region_keyword_combos:
                add(combo, 1)

        # === 대각선 레벨 1: 기본 확장 ===

        # R3(L2): 지역 + 업종대표 + 수식어
        await self._emit("progress", "   R3: 지역 + 업종대표 + 수식어")
        for region in regions:
            for bk in biz_keywords:
                for mod in all_modifiers:
                    add(f"{region} {bk} {mod}", 2)
        await self._emit("progress", f"   R3: {len(self.keyword_pool)}개")

        # R4(L3): 지역 + 키워드 + 수식어
        await self._emit("progress", "   R4: 지역 + 키워드 + 수식어")
        for region in regions:
            for kw in priority_keywords:
                for mod in all_modifiers:
                    add(f"{region} {kw} {mod}", 3)
        await self._emit("progress", f"   R4: {len(self.keyword_pool)}개")

        # basic_only 모드: R1-R4만 생성하고 조기 종료
        if self.basic_only:
            self.keyword_pool.sort(key=lambda x: x["level"])
            await self._emit("progress", f"Phase 2 완료 (기본 조합): {len(self.keyword_pool)}개 생성")
            lvl_counts = {}
            for k in self.keyword_pool:
                lvl = k["level"]
                lvl_counts[lvl] = lvl_counts.get(lvl, 0) + 1
            for lvl, cnt in sorted(lvl_counts.items()):
                await self._emit("progress", f"   Level {lvl}: {cnt}개")
            return

        # R5(L4): 지역 + 근처/가까운 + 업종대표키워드
        await self._emit("progress", "   R5: 지역 + 근처 + 업종대표키워드")
        for region in regions:
            for loc_suffix in self.LOCATION_SUFFIXES:
                for bk in biz_keywords:
                    add(f"{region} {loc_suffix} {bk}", 4)
        await self._emit("progress", f"   R5: {len(self.keyword_pool)}개")

        # R6(L5): 지역 + 근처/가까운 + 키워드
        await self._emit("progress", "   R6: 지역 + 근처 + 키워드")
        for region in regions:
            for loc_suffix in self.LOCATION_SUFFIXES:
                for kw in priority_keywords:
                    add(f"{region} {loc_suffix} {kw}", 5)
        await self._emit("progress", f"   R6: {len(self.keyword_pool)}개")

        # === 대각선 레벨 2: 중간 확장 ===

        # R7(L6): 지역 + 키워드 + 업종대표키워드
        await self._emit("progress", "   R7: 지역 + 키워드 + 업종대표키워드")
        for region in regions:
            for kw in priority_keywords:
                for bk in biz_keywords:
                    add(f"{region} {kw} {bk}", 6)
        await self._emit("progress", f"   R7: {len(self.keyword_pool)}개")

        # R8(L7): 지역 + 키워드1 + 키워드2
        await self._emit("progress", "   R8: 지역 + 키워드1 + 키워드2")
        for region in regions:
            for kw1, kw2 in combinations(priority_keywords[:15], 2):
                add(f"{region} {kw1} {kw2}", 7)
        await self._emit("progress", f"   R8: {len(self.keyword_pool)}개")

        # R9(L8): 지역 + 근처 + 업종대표 + 수식어
        await self._emit("progress", "   R9: 지역 + 근처 + 업종대표 + 수식어")
        for region in regions:
            for loc_suffix in self.LOCATION_SUFFIXES[:2]:
                for bk in biz_keywords[:2]:
                    for mod in all_modifiers:
                        add(f"{region} {loc_suffix} {bk} {mod}", 8)
        await self._emit("progress", f"   R9: {len(self.keyword_pool)}개")

        # R10(L9): 지역 + 근처 + 키워드 + 수식어
        await self._emit("progress", "   R10: 지역 + 근처 + 키워드 + 수식어")
        for region in regions:
            for loc_suffix in self.LOCATION_SUFFIXES[:2]:
                for kw in priority_keywords[:8]:
                    for mod in all_modifiers:
                        add(f"{region} {loc_suffix} {kw} {mod}", 9)
        await self._emit("progress", f"   R10: {len(self.keyword_pool)}개")

        # R11(L10): 지역1 + 지역2 + 업종대표키워드
        await self._emit("progress", "   R11: 지역2개 + 업종대표키워드")
        for r1, r2 in combinations(regions[:8], 2):
            for bk in biz_keywords:
                add(f"{r1} {r2} {bk}", 10)
        await self._emit("progress", f"   R11: {len(self.keyword_pool)}개")

        # R12(L11): 지역1 + 지역2 + 키워드
        await self._emit("progress", "   R12: 지역2개 + 키워드")
        for r1, r2 in combinations(regions[:8], 2):
            for kw in priority_keywords[:10]:
                add(f"{r1} {r2} {kw}", 11)
        await self._emit("progress", f"   R12: {len(self.keyword_pool)}개")

        # === 상호명 (별도) ===

        # R13(L12): 상호명
        self._name_kw_to_bare = {}
        if name_keywords:
            await self._emit("progress", f"   R13: 상호명 ({name_keywords})")

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
                    for bk in biz_keywords[:1]:
                        kw3 = f"{region} {bk} {name_kw}"
                        add(kw3, 12, source="name")
                        self._name_kw_to_bare[kw3] = name_kw
            await self._emit("progress", f"   R13: {len(self.keyword_pool)}개")

        # === 대각선 레벨 3: 추가 확장 ===

        # R14(L13): 지역2개 + 업종대표 + 수식어
        await self._emit("progress", "   R14: 지역2개 + 업종대표 + 수식어")
        for r1, r2 in combinations(regions[:8], 2):
            for bk in biz_keywords[:2]:
                for mod in all_modifiers:
                    add(f"{r1} {r2} {bk} {mod}", 13)
        await self._emit("progress", f"   R14: {len(self.keyword_pool)}개")

        # R15(L14): 지역2개 + 키워드 + 수식어
        await self._emit("progress", "   R15: 지역2개 + 키워드 + 수식어")
        for r1, r2 in combinations(regions[:8], 2):
            for kw in priority_keywords[:8]:
                for mod in all_modifiers:
                    add(f"{r1} {r2} {kw} {mod}", 14)
        await self._emit("progress", f"   R15: {len(self.keyword_pool)}개")

        # R16(L15): 지역2개 + 근처 + 업종대표
        await self._emit("progress", "   R16: 지역2개 + 근처 + 업종대표")
        for r1, r2 in combinations(regions[:6], 2):
            for loc_suffix in self.LOCATION_SUFFIXES[:2]:
                for bk in biz_keywords[:2]:
                    add(f"{r1} {r2} {loc_suffix} {bk}", 15)
        await self._emit("progress", f"   R16: {len(self.keyword_pool)}개")

        # === 고급 조합 + 특수 ===

        # R17(L16): 3개 키워드 조합
        await self._emit("progress", "   R17: 3개 키워드 조합")
        for region in regions:
            for combo in combinations(priority_keywords[:10], 3):
                add(f"{region} {' '.join(combo)}", 16)
        await self._emit("progress", f"   R17: {len(self.keyword_pool)}개")

        # R18(L17): 순서 변형
        await self._emit("progress", "   R18: 순서 변형")
        for region in regions:
            for kw in priority_keywords:
                add(f"{kw} {region}", 17)
            for kw in priority_keywords[:8]:
                for bk in biz_keywords[:1]:
                    add(f"{bk} {region} {kw}", 17)
        await self._emit("progress", f"   R18: {len(self.keyword_pool)}개")

        # Phase 4 스킵 로직용 지역 세트 저장
        self._phase2_region_set = set(regions)

        # Level 기준 정렬 (낮은 레벨 = 우선순위 높음)
        self.keyword_pool.sort(key=lambda x: x["level"])

        await self._emit("progress", f"Phase 2 완료: {len(self.keyword_pool)}개 생성")
        lvl_counts = {}
        for k in self.keyword_pool:
            lvl_counts[k["level"]] = lvl_counts.get(k["level"], 0) + 1
        await self._emit("progress", f"   레벨별: {lvl_counts}")

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
        """Phase 4에서 상호명 단독 1위 확인 후 -> 업종대표키워드와 추가 조합 (R-POST)

        restaurant 한정: "OO숯불구이" 1위 -> "OO숯불구이 맛집/음식점/식당" 추가

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
            for region in regions[:5]:
                for bk in biz_keywords:
                    new_keywords.append({
                        "keyword": f"{region} {name_kw} {bk}",
                        "map_type": "unknown", "level": 3,
                        "source": "name_combo"
                    })
        return new_keywords

    # ==================== Phase 3: 비율 조정 ====================
    async def _phase_3_adjust_ratio(self, place: PlaceData):
        """Phase 3: 신/구지도 비율 조정 (지도 키워드 추가)"""
        await self._emit("progress", "Phase 3: 지도 비율 조정 중...")

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
            jido_count = deficit

            await self._emit("progress", f"   구지도 부족 → '지도' 키워드 {jido_count}개 추가 (후순위)")

            regions = place.region.get_keyword_variations()
            if not regions:
                regions = [place.region.gu] if place.region.gu else []

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
                        self.keyword_pool.append({
                            "keyword": new_keyword,
                            "map_type": "구지도",
                            "level": 10
                        })
                        added += 1
                if added >= jido_count:
                    break

        await self._emit("progress", f"Phase 3 완료: 최종 {len(self.keyword_pool)}개 키워드")

    # ==================== Phase 4: 최종 순위 크롤링 ====================
    async def _phase_4_final_ranking(self, place: PlaceData):
        """Phase 4: 목표 개수만 실제 순위 크롤링 + 실시간 UI"""
        place_id = self._get_place_id_from_url(self.url)
        proxy_configs = self._get_proxy_configs()

        business_type = self._detect_business_type(place.category)

        if self.use_api_mode and HAS_GRAPHQL_MODE:
            mode_name = "GraphQL"
            await self._emit("progress", f"Phase 4: 순위 크롤링 시작... [{mode_name} 모드]")
            await self._phase_4_graphql_mode(place_id, proxy_configs, place)
        elif self.use_api_mode and HAS_API_MODE:
            mode_name = "API"
            await self._emit("progress", f"Phase 4: 순위 크롤링 시작... [{mode_name} 모드]")
            await self._phase_4_api_mode(place_id, proxy_configs)
        else:
            mode_name = "브라우저"
            await self._emit("progress", f"Phase 4: 순위 크롤링 시작... [{mode_name} 모드]")
            await self._phase_4_browser_mode(place_id, proxy_configs)

    async def _phase_4_graphql_mode(self, place_id: str, proxy_configs: List[ProxyConfig], place: PlaceData):
        """Phase 4 - GraphQL API 모드 (가장 빠르고 안정적)
        R-POST: 상호명 1위 키워드 -> 업종대표키워드 추가 조합 (restaurant 한정)
        """
        from src.rank_checker_graphql import RankCheckerGraphQL, RankResult as GqlRankResult

        found_count = self._get_valid_count()
        business_type = self._detect_business_type(place.category)

        # 상호명(PLT) vs 리스트(PLL) 목표 분배
        plt_target = max(1, int(self.target_count * self.name_keyword_ratio))
        pll_target = self.target_count - plt_target
        pll_found = found_count  # 기존 발견은 모두 PLL
        plt_found = 0

        # 좌표 추출 (주소에서 지역 감지)
        coords = None
        address = place.jibun_address or place.road_address
        if address:
            for region, coord in CITY_COORDINATES.items():
                if region in address:
                    coords = coord
                    await self._emit("progress", f"   지역 감지: {region}")
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

        # 검증할 키워드 분리: 메인 vs 상호명
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

        await self._emit("progress", f"   GraphQL 모드: 메인 {len(main_keywords_to_check)}개 + 상호명 {len(name_keywords_to_check)}개")
        if name_keyword_set and business_type == "restaurant":
            await self._emit("progress", f"   R-POST 대기: 상호명 {len(name_keyword_set)}개 (최대 {max_name_combos}개 조합)")

        batch_size = 20  # 50→20: 중단 응답 속도 개선

        # === 업종대표 실패 지역 스킵 준비 ===
        biz_keywords = list(self._instance_biz_keywords.get(
            business_type, self._instance_biz_keywords["general"]))
        first_biz = biz_keywords[0] if biz_keywords else ""
        ok_first_biz_set = set()
        failed_first_biz_set = set()
        failed_biz_regions = set()
        total_skipped = 0

        # "지역(들)+대표업종(맛집)" 선행 체크용 분리
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
            await self._emit("progress",
                f"   선행 체크: '{first_biz}' {len(primary_biz_kws)}개 → 미노출 지역 업종대표 조합 스킵")

        async with RankCheckerGraphQL(
            proxies=proxy_configs if proxy_configs else None,
            default_coords=coords,
            use_own_ip=self.use_own_ip,
            user_slot=self.user_slot,
            total_instances=self.total_instances
        ) as checker:

            # === Phase 4A-1: 선행 배치 ===
            if primary_biz_kws and self.is_running and pll_found < pll_target:
                pb_start = 0
                while pb_start < len(primary_biz_kws) and self.is_running and pll_found < pll_target:
                    pb_batch = primary_biz_kws[pb_start:pb_start + batch_size]

                    def primary_progress_cb(current, total, msg):
                        try:
                            self._event_queue.put_nowait({
                                "type": "sub_progress",
                                "job_id": self._job_id,
                                "data": {"current": found_count + current, "total": self.target_count, "message": msg, "found_count": self._get_valid_count()},
                                "timestamp": time.time()
                            })
                        except asyncio.QueueFull:
                            pass
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
                        converted.total_count = getattr(result, 'total_count', None)
                        self.all_results.append(converted)

                        if result.rank and self.min_rank <= result.rank <= self.max_rank:
                            found_count += 1
                            pll_found += 1
                            ok_first_biz_set.add(result.keyword)
                        elif result.status != "error":
                            failed_first_biz_set.add(result.keyword)
                            prefix = result.keyword[:-len(f" {first_biz}")].strip()
                            prefix_parts = prefix.split()
                            if len(prefix_parts) == 1:
                                failed_biz_regions.add(prefix_parts[0])
                            await self._emit("progress",
                                f"   '{result.keyword}' 미노출 → 업종대표 조합 스킵")

                    pb_start += len(pb_batch)

                skip_info = []
                if failed_biz_regions:
                    skip_info.append(f"단일지역: {failed_biz_regions}")
                if failed_first_biz_set:
                    skip_info.append(f"지역쌍: {len(failed_first_biz_set) - len(failed_biz_regions)}개")
                await self._emit("progress",
                    f"   선행 완료: {len(primary_biz_kws)}개 체크, {found_count}개 발견, "
                    f"OK {len(ok_first_biz_set)}개, 스킵 대상: {', '.join(skip_info) if skip_info else '없음'}")

            # === PLL 키워드 체크 헬퍼 (Phase 4A-2 및 4C에서 공용) ===
            keywords_to_check = remaining_main_kws
            pll_scan_pos = 0  # PLL 키워드 처리 위치 (Phase 4C에서 이어서 사용)

            async def _check_pll_batch(target_pll, label="PLL"):
                """PLL 키워드를 target_pll까지 체크. (pll_found, found_count, pll_scan_pos 갱신)"""
                nonlocal pll_found, found_count, pll_scan_pos, total_skipped

                while pll_scan_pos < len(keywords_to_check):
                    if not self.is_running:
                        break
                    if pll_found >= target_pll:
                        await self._emit("progress", f"   {label} 목표 달성! {pll_found}/{target_pll}개 완료")
                        break

                    # 배치 구성 (실패 지역 + 업종대표 키워드 조합 스킵)
                    batch = []
                    scan_end = pll_scan_pos
                    while scan_end < len(keywords_to_check) and len(batch) < batch_size:
                        kw = keywords_to_check[scan_end]
                        scan_end += 1

                        if failed_first_biz_set or failed_biz_regions:
                            parts = kw.split()
                            biz_hit = None
                            biz_pos = -1
                            for bk in biz_keywords:
                                if bk in parts:
                                    biz_pos = parts.index(bk)
                                    biz_hit = bk
                                    break

                            if biz_hit:
                                prefix = " ".join(parts[:biz_pos])
                                test_kw = f"{prefix} {first_biz}" if prefix else first_biz

                                if test_kw in ok_first_biz_set:
                                    pass
                                elif test_kw in failed_first_biz_set:
                                    total_skipped += 1
                                    if total_skipped <= 10:
                                        await self._emit("progress", f"   스킵: {kw}")
                                    elif total_skipped == 11:
                                        await self._emit("progress", f"   ... (이후 스킵 로그 생략)")
                                    continue
                                else:
                                    if any(p in failed_biz_regions for p in parts[:biz_pos]):
                                        total_skipped += 1
                                        if total_skipped <= 10:
                                            await self._emit("progress", f"   스킵: {kw}")
                                        elif total_skipped == 11:
                                            await self._emit("progress", f"   ... (이후 스킵 로그 생략)")
                                        continue

                        batch.append(kw)
                    pll_scan_pos = scan_end

                    if not batch:
                        continue

                    def progress_cb(current, total, msg):
                        try:
                            self._event_queue.put_nowait({
                                "type": "sub_progress",
                                "job_id": self._job_id,
                                "data": {"current": found_count + current, "total": self.target_count, "message": msg, "found_count": self._get_valid_count()},
                                "timestamp": time.time()
                            })
                        except asyncio.QueueFull:
                            pass

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
                        converted.total_count = getattr(result, 'total_count', None)
                        self.all_results.append(converted)

                        if result.rank and self.min_rank <= result.rank <= self.max_rank:
                            found_count += 1
                            pll_found += 1

                    processed = min(pll_scan_pos, len(keywords_to_check))
                    skip_msg = f", {total_skipped}개 스킵" if total_skipped > 0 else ""
                    await self._emit("progress",
                        f"   메인 진행({label}): {processed}/{len(keywords_to_check)} ({pll_found}/{target_pll}개 발견{skip_msg})")

            # === Phase 4A-2: 메인 키워드 1차 (PLL 목표까지) ===
            await _check_pll_batch(pll_target, "PLL")

            # === Phase 4B: 상호명 키워드 (PLT = rank 1만 카운트) ===
            if name_keywords_to_check and self.is_running:
                original_name_count = len(name_keywords_to_check)
                target_reached_logged = False
                await self._emit("progress", f"   상호명 체크: {original_name_count}개 (PLT 목표: {plt_target}개, 기준: 1위)")
                batch_start = 0
                while batch_start < len(name_keywords_to_check):
                    if not self.is_running:
                        break

                    if plt_found >= plt_target:
                        if not target_reached_logged:
                            await self._emit("progress", f"   PLT 목표 달성 ({plt_found}/{plt_target}개) → 상호명 체크 종료")
                        break

                    batch = name_keywords_to_check[batch_start:batch_start + batch_size]

                    def name_progress_cb(current, total, msg):
                        try:
                            self._event_queue.put_nowait({
                                "type": "sub_progress",
                                "job_id": self._job_id,
                                "data": {"current": found_count + current, "total": self.target_count, "message": msg, "found_count": self._get_valid_count()},
                                "timestamp": time.time()
                            })
                        except asyncio.QueueFull:
                            pass

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
                        converted.total_count = getattr(result, 'total_count', None)
                        self.all_results.append(converted)

                        if result.rank and self.min_rank <= result.rank <= self.max_rank:
                            found_count += 1
                            # PLT = 상호명 키워드 + rank 1 + 검색결과 1개
                            tc = getattr(result, 'total_count', None)
                            if result.rank == 1 and (tc is None or tc == 1):
                                plt_found += 1
                                if plt_found >= plt_target and not target_reached_logged:
                                    await self._emit("progress", f"   PLT 목표 달성! {plt_found}/{plt_target}개 완료")
                                    target_reached_logged = True
                            else:
                                # rank 2~max_rank 또는 total_count>1: PLL로 카운트
                                pll_found += 1

                        # R-POST: 상호명 1위+결과1개 -> 업종대표키워드 추가 조합 (restaurant 한정)
                        if (result.rank == 1 and (tc is None or tc == 1)
                                and result.keyword in name_keyword_set
                                and business_type == "restaurant"
                                and name_combo_count < max_name_combos
                                and plt_found < plt_target):
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
                                await self._emit("progress",
                                    f"   R-POST: '{result.keyword}' 1위 → {added_count}개 조합 추가 "
                                    f"({name_combo_count}/{max_name_combos})")

                    processed = min(batch_start + len(batch), len(name_keywords_to_check))
                    await self._emit("progress", f"   상호명 진행(PLT): {processed}/{len(name_keywords_to_check)} ({plt_found}/{plt_target}개 발견)")
                    batch_start += len(batch)

            # === Phase 4C: PLT 부족 시 PLL 보충 (총 target_count 달성) ===
            total_found = pll_found + plt_found
            if total_found < self.target_count and self.is_running and pll_scan_pos < len(keywords_to_check):
                deficit = self.target_count - total_found
                new_pll_target = pll_found + deficit
                await self._emit("progress",
                    f"   PLT 부족분 PLL 보충: {deficit}개 추가 필요 (현재 PLL:{pll_found} + PLT:{plt_found} = {total_found}/{self.target_count})")
                await _check_pll_batch(new_pll_target, "PLL보충")

    async def _phase_4_api_mode(self, place_id: str, proxy_configs: List[ProxyConfig], use_html_only: bool = False):
        """Phase 4 - API 직접 호출 모드 (빠름)

        Args:
            use_html_only: True면 HTML 스크래핑만 사용 (병원 검색용)
        """
        from src.rank_checker_api import RankCheckerAPI, RankResult as ApiRankResult

        found_count = self._get_valid_count()

        # 검증할 키워드 목록 준비 (중복 제외)
        keywords_to_check = []
        for item in self.keyword_pool:
            kw = item["keyword"]
            if kw not in self.verified_keywords:
                keywords_to_check.append(kw)
                self.verified_keywords.add(kw)

        mode_desc = "HTML 스크래핑" if use_html_only else "API"
        await self._emit("progress", f"   {mode_desc} 모드: {len(keywords_to_check)}개 키워드 배치 처리")

        batch_size = 20

        async with RankCheckerAPI(proxies=proxy_configs if proxy_configs else None, use_api_mode=not use_html_only) as checker:
            for batch_start in range(0, len(keywords_to_check), batch_size):
                if not self.is_running:
                    break

                if found_count >= self.target_count:
                    await self._emit("progress", f"목표 달성! {found_count}개 완료")
                    break

                batch = keywords_to_check[batch_start:batch_start + batch_size]

                def progress_cb(current, total, msg):
                    try:
                        self._event_queue.put_nowait({
                            "type": "sub_progress",
                            "job_id": self._job_id,
                            "data": {"current": found_count + current, "total": self.target_count, "message": msg, "found_count": self._get_valid_count()},
                            "timestamp": time.time()
                        })
                    except asyncio.QueueFull:
                        pass

                checker.set_progress_callback(progress_cb)

                results = await checker.check_keywords(
                    keywords=batch,
                    target_place_id=place_id,
                    max_rank=self.max_rank
                )

                for result in results:
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

                processed = min(batch_start + batch_size, len(keywords_to_check))
                await self._emit("progress", f"   진행: {processed}/{len(keywords_to_check)} ({found_count}개 발견)")

    async def _phase_4_browser_mode(self, place_id: str, proxy_configs: List[ProxyConfig]):
        """Phase 4 - 브라우저 모드 (안정적이지만 느림)"""
        from src.rank_checker import RankChecker
        found_count = self._get_valid_count()

        async with RankChecker(proxies=proxy_configs if proxy_configs else None, headless=True) as checker:
            self.rank_checker = checker

            for item in self.keyword_pool:
                if not self.is_running:
                    break

                if found_count >= self.target_count:
                    await self._emit("progress", f"목표 달성! {found_count}개 완료")
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
                        is_name = any(item.get("source") == "name" for item in self.keyword_pool if item["keyword"] == keyword)
                        tc = getattr(result, 'total_count', None)
                        kw_type = "PLT" if (is_name and result.rank == 1 and (tc is None or tc == 1)) else "PLL"
                        await self._emit("sub_progress", {
                            "current": found_count,
                            "total": self.target_count,
                            "message": f"{keyword}: {result.rank}위 [{kw_type}]"
                        })

    # ==================== 유틸리티 ====================
    async def _finish(self):
        """작업 완료 처리 + PLL/PLT 비율 리포트"""
        valid_results = [r for r in self.all_results if r.rank is not None and self.min_rank <= r.rank <= self.max_rank]

        plt_count = sum(1 for r in valid_results if _is_plt(r))
        pll_count = len(valid_results) - plt_count
        total_valid = len(valid_results)

        if total_valid > 0:
            pll_pct = pll_count * 100 // total_valid
            plt_pct = plt_count * 100 // total_valid
            await self._emit("progress", f"최종 비율: PLL {pll_count}개({pll_pct}%), PLT {plt_count}개({plt_pct}%)")

        await self._emit("progress", f"작업 완료: {total_valid}개 유효 키워드")
        results_data = [{"keyword": r.keyword, "rank": r.rank, "keyword_type": "PLT" if _is_plt(r) else "PLL", "status": r.status} for r in self.all_results]
        await self._emit("finished", results_data)

    async def _finish_early(self, reason: str = "중단됨"):
        """중간 중단 시 결과 반환"""
        completed_results = [r for r in self.all_results if r.status != "cancelled"]
        valid_results = [r for r in completed_results if r.rank is not None and self.min_rank <= r.rank <= self.max_rank]
        total_valid = len(valid_results)
        total_checked = len(completed_results)

        if total_valid > 0:
            plt_count = sum(1 for r in valid_results if _is_plt(r))
            pll_count = total_valid - plt_count
            pll_pct = pll_count * 100 // total_valid
            plt_pct = plt_count * 100 // total_valid
            await self._emit("progress", f"중단 시점 비율: PLL {pll_count}개({pll_pct}%), PLT {plt_count}개({plt_pct}%)")

        await self._emit("progress", f"{reason} - {total_checked}개 검사 완료, {total_valid}개 유효 키워드 저장됨")
        results_data = [{"keyword": r.keyword, "rank": r.rank, "keyword_type": "PLT" if _is_plt(r) else "PLL", "status": r.status} for r in self.all_results]
        await self._emit("finished", results_data)

    def _get_valid_count(self) -> int:
        """max_rank 이내 유효 결과 수"""
        return sum(1 for r in self.all_results if r.rank is not None and self.min_rank <= r.rank <= self.max_rank)

    def _get_place_id_from_url(self, url: str) -> str:
        """URL에서 Place ID 추출"""
        from src.url_parser import parse_place_url
        parsed = parse_place_url(url)
        return parsed.mid if parsed.is_valid else ""

    def _get_proxy_configs(self) -> List[ProxyConfig]:
        """프록시 딕셔너리를 ProxyConfig로 변환"""
        configs = []
        for p in self.proxies:
            if "host" in p and "port" in p:
                session_type = p.get("session_type", "rotating")

                configs.append(ProxyConfig(
                    host=p["host"],
                    port=p["port"],
                    username=p.get("username", ""),
                    password=p.get("password", ""),
                    proxy_type=p.get("type", "datacenter"),
                    session_type=session_type,
                    session_id=""
                ))
        return configs
