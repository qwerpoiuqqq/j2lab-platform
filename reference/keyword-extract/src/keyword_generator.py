"""
맛집 키워드 생성기 (Advanced Keyword Generator)
규칙 기반으로 500~2,000개의 유효 키워드를 생성합니다.
"""
import re
from typing import List, Set, Dict, Optional
from dataclasses import dataclass
from .models import PlaceData, ReviewKeyword

class KeywordGenerator:
    """
    네이버 플레이스 데이터를 기반으로 다양한 검색 키워드 조합을 생성하는 클래스
    """
    
    # === 매핑 테이블 (Mapping Tables) ===
    
    # 1. 특징 키워드 변환 (Review Theme -> Search Term)
    THEME_MAP = {
        "분위기": ["분위기좋은", "분위기", "감성", "무드있는"],
        "가성비": ["가성비", "가성비좋은", "저렴한"],
        "친절": ["친절한", "서비스좋은"],
        "청결": ["깨끗한", "청결한"],
        "뷰": ["뷰좋은", "전망좋은", "뷰맛집"],
        "인테리어": ["인테리어예쁜", "사진찍기좋은"],
        "혼밥": ["혼밥", "1인식사"],
    }
    
    # 2. 투표 키워드 변환 (Voted Keyword -> Search Term)
    VOTED_MAP = {
        "together": ["단체", "회식", "모임", "단체모임"],
        "spacious": ["넓은", "쾌적한", "대형"],
        "comfy": ["좌석편한", "편한"],
        "room_nice": ["룸", "개인룸", "프라이빗"],
        "mood_good": ["분위기좋은", "데이트"],
        "parking": ["주차", "주차가능", "주차무료"],
        "view_good": ["뷰좋은", "야경"],
        "solo": ["혼밥", "혼술"],
    }
    
    # 3. 편의시설 변환 (Convenience -> Search Term)
    CONVENIENCE_MAP = {
        "포장": ["포장", "테이크아웃"],
        "배달": ["배달"],
        "예약": ["예약", "예약가능"],
        "단체": ["단체", "단체석"],
        "주차": ["주차", "주차장"],
        "발렛": ["발렛", "발렛파킹"],
        "반려동물": ["애견동반", "반려동물동반"],
        "유아시설": ["놀이방", "키즈존"],
        "콜키지": ["콜키지", "콜키지프리"],
    }
    
    # 4. 좌석 정보 변환 (Seat -> Search Term)
    SEAT_MAP = {
        "단체석": ["단체석", "단체"],
        "연인석": ["데이트", "커플석"],
        "룸": ["룸", "개인실", "프라이빗룸"],
        "테라스": ["테라스", "야외석", "루프탑"],
        "창가": ["창가석", "뷰좋은"],
        "1인석": ["혼밥", "1인석"],
    }

    # 5. 블랙리스트 (제외할 패턴)
    BLACKLIST_EXACT = {"맛", "맛집", "음식", "식사", "메뉴", "추천", "리뷰"}
    BLACKLIST_PATTERNS = [
        r".*만족도.*",
        r".*재방문.*",
        r".*무선인터넷.*",
        r".*화장실.*",
    ]

    def __init__(self, top_menu_count: int = 20):
        self.top_menu_count = top_menu_count

    def generate(self, place: PlaceData, simple_mode: bool = False) -> List[str]:
        """
        메인 생성 함수 (업종별 분기)
        Args:
            place: 플레이스 데이터
            simple_mode: 단순 모드 (1차 테스트용, 기본 조합만 생성)
        """
        # 업종 분류 (확장된 병의원 카테고리)
        hospital_categories = [
            "병원", "의원", "치과", "한의원", "클리닉", "피부과",
            "정형외과", "신경외과", "내과", "외과", "안과", "이비인후과",
            "재활의학과", "산부인과", "비뇨기과", "성형외과", "마취통증의학과"
        ]
        # 업종 분류
        is_hospital = any(c in place.category for c in ["병원", "의원", "치과", "한의원", "클리닉", "피부과", "성형외과", "동물병원"])
        
        # 맛집 키워드 확장
        restaurant_keywords = [
            "음식", "요리", "식당", "카페", "주점", "호프", "맛집", 
            "한식", "양식", "일식", "중식", "분식", "뷔페", "레스토랑",
            "고기", "구이", "회", "돈가스", "파스타", "피자", "버거",
            "갈비", "곱창", "국밥", "면", "제과", "베이커리"
        ]
        is_restaurant = any(c in place.category for c in restaurant_keywords)
        
        
        if is_hospital:
            print(f"[DEBUG] >>> 병의원 로직 실행 (simple_mode={simple_mode})")
            return self._generate_hospital_keywords(place, simple_mode)
        elif is_restaurant:
            return self._generate_restaurant_keywords(place, simple_mode)
        else:
            return self._generate_general_keywords(place, simple_mode)

    def _generate_hospital_keywords(self, place: PlaceData, simple_mode: bool = False) -> List[str]:
        """
        병의원 전용 키워드 생성 (최대 물량)
        우선순위: 지역 + 업종 카테고리 > 지역 + 진료과목 > 기타
        """
        # 우선순위 키워드 (지역 + 업종 카테고리)
        priority_keywords: List[str] = []
        keywords: Set[str] = set()

        # === 1. 데이터 준비 ===
        regions = place.region.get_keyword_variations()
        if not regions:
            regions = [place.region.gu] if place.region.gu else []

        # 대표 키워드 (keywordList + 진료과목)
        rep_kw = list(place.keywords) + list(place.medical_subjects)
        rep_kw = [k for k in rep_kw if k and len(k) > 1]

        # 업종 카테고리
        category = place.category if place.category else ""

        # 상호명 파츠
        name_parts = self._extract_name_parts(place.name)

        # 편의시설
        amenities = self._get_amenities(place)

        # 병의원 접미사/수식어
        hospital_suffixes = ["의원", "병원", "병의원"]
        recommend_suffixes = ["추천", "잘하는곳", "유명한곳", "전문", "잘하는"]
        hospital_features = ["야간진료", "일요일진료", "주말진료", "전문의", "예약"]

        # === 최우선: 지역 + 업종 카테고리 (메인 키워드) ===
        main_categories = self._get_main_medical_categories(category)

        # 지역 + 메인 카테고리 (최우선 조합)
        for r in regions:
            for cat in main_categories:
                if r and cat:
                    priority_keywords.append(f"{r} {cat}")

        # 지역 + 메인 카테고리 + 추천/잘하는곳
        for r in regions:
            for cat in main_categories:
                if r and cat:
                    priority_keywords.append(f"{r} {cat} 추천")
                    priority_keywords.append(f"{r} {cat} 잘하는곳")

        # === 2. 기본 조합 ===

        # 지역 + 업종
        for r in regions:
            if category:
                keywords.add(f"{r} {category}")

        # 단순 모드면 여기서 반환 (기본만, 수식어 제외)
        if simple_mode:
            # 지역 × 업종 카테고리 (최우선)
            keywords.update(self._combine_2(regions, main_categories))
            # 지역 + 진료과목(대표키워드)
            for r in regions:
                for kw in rep_kw:
                    keywords.add(f"{r} {kw}")
            # 지역 + 상호명
            for r in regions:
                for name in name_parts:
                    keywords.add(f"{r} {name}")
            # 우선순위 키워드를 앞에 배치
            result = self._filter_and_sort(keywords)
            filtered_priority = [k for k in priority_keywords if k and len(k) >= 2]
            seen = set(filtered_priority)
            final_result = filtered_priority + [k for k in result if k not in seen]
            return final_result
            
        # 지역 + 업종 + 의원/병원
        for r in regions:
            for suffix in hospital_suffixes:
                if category:
                    keywords.add(f"{r} {category}{suffix}")
                    keywords.add(f"{r} {category} {suffix}")
        
        # 지역 + 대표키워드
        for r in regions:
            for kw in rep_kw:
                keywords.add(f"{r} {kw}")
        
        # 지역 + 대표키워드 + 업종
        for r in regions:
            for kw in rep_kw:
                if category:
                    keywords.add(f"{r} {kw} {category}")
        
        # 지역 + 업종 + 추천
        for r in regions:
            for suffix in recommend_suffixes:
                if category:
                    keywords.add(f"{r} {category} {suffix}")
        
        # 지역 + 특징 + 업종
        for r in regions:
            for feat in hospital_features + amenities:
                if category:
                    keywords.add(f"{r} {feat} {category}")
        
        # === 3. 대표키워드 2~4개 조합 ===
        from itertools import permutations
        
        # 2개 조합
        for perm in permutations(rep_kw[:8], 2):
            combo = " ".join(perm)
            for r in regions:
                keywords.add(f"{r} {combo}")
                if category:
                    keywords.add(f"{r} {combo} {category}")
        
        # 3개 조합
        if len(rep_kw) >= 3:
            for perm in permutations(rep_kw[:6], 3):
                combo = " ".join(perm)
                for r in regions:
                    keywords.add(f"{r} {combo}")
        
        # === 4. 상호명 조합 ===
        for r in regions:
            for name in name_parts:
                keywords.add(f"{r} {name}")
                if category:
                    keywords.add(f"{r} {name} {category}")
        
        # 상호명 단독
        for name in name_parts:
            if len(name) > 2:
                keywords.add(name)
        
        # === 5. 4단 조합 ===
        for r in regions:
            for kw in rep_kw[:5]:
                for suffix in recommend_suffixes[:3]:
                    if category:
                        keywords.add(f"{r} {kw} {category} {suffix}")
        
        # === 6. 필터링 및 우선순위 적용 ===
        result = []
        for k in keywords:
            k = k.strip()
            if len(k) < 3 or len(k) > 50:
                continue
            if not k:
                continue
            result.append(k)

        result = sorted(set(result), key=lambda x: (len(x), x))
        # 우선순위 키워드를 앞에 배치
        filtered_priority = [k for k in priority_keywords if k and len(k) >= 2]
        seen = set(filtered_priority)
        final_result = filtered_priority + [k for k in result if k not in seen]
        return final_result

    def _extract_name_parts(self, name: str) -> List[str]:
        """
        상호명에서 검색용 이름 추출
        예: "강남리더스피부과의원" -> ["리더스피부과의원", "리더스피부과", "리더스"]
        """
        parts = []
        if not name:
            return parts
        
        # 전체 상호명
        parts.append(name)
        
        # 지역명 제거 시도
        region_prefixes = ["강남", "홍대", "신촌", "일원", "도곡", "잠실", "서초", "송파"]
        cleaned_name = name
        for prefix in region_prefixes:
            if name.startswith(prefix):
                cleaned_name = name[len(prefix):]
                break
        if cleaned_name != name:
            parts.append(cleaned_name)
        
        # 의원/병원/클리닉 제거
        for suffix in ["의원", "병원", "클리닉", "센터"]:
            if cleaned_name.endswith(suffix):
                base_name = cleaned_name[:-len(suffix)]
                if len(base_name) > 1:
                    parts.append(base_name)
        
        return list(set(parts))

    def _generate_general_keywords(self, place: PlaceData, simple_mode: bool = False) -> List[str]:
        """
        일반 업종 키워드 생성 (병의원 로직 기반, 최대 물량)
        우선순위: 지역 + 업종 카테고리 > 지역 + 대표키워드 > 기타
        """
        # 우선순위 키워드 (지역 + 업종 카테고리)
        priority_keywords: List[str] = []
        keywords: Set[str] = set()

        # === 1. 데이터 준비 ===
        regions = place.region.get_keyword_variations()
        if not regions:
            regions = [place.region.gu] if place.region.gu else []

        # 대표 키워드 (keywordList)
        rep_kw = list(place.keywords)
        rep_kw = [k for k in rep_kw if k and len(k) > 1]

        # 업종 카테고리
        category = place.category if place.category else ""

        # 상호명 파츠
        name_parts = self._extract_general_name_parts(place.name)

        # 편의시설
        amenities = self._get_amenities(place)

        # 추천 접미사 (의원/병원 제외)
        recommend_suffixes = ["추천", "잘하는곳", "유명한곳", "전문", "잘하는"]
        general_features = ["주차", "예약", "상담"]

        # === 최우선: 지역 + 업종 카테고리 (메인 키워드) ===
        main_categories = self._get_main_general_categories(category)

        # 지역 + 메인 카테고리 (최우선 조합)
        for r in regions:
            for cat in main_categories:
                if r and cat:
                    priority_keywords.append(f"{r} {cat}")

        # 지역 + 메인 카테고리 + 추천
        for r in regions:
            for cat in main_categories:
                if r and cat:
                    priority_keywords.append(f"{r} {cat} 추천")

        # === 2. 기본 조합 ===

        # 지역 + 업종
        for r in regions:
            if category:
                keywords.add(f"{r} {category}")

        # 단순 모드 처리 (수식어 제외)
        if simple_mode:
            # 지역 × 업종 카테고리 (최우선)
            keywords.update(self._combine_2(regions, main_categories))
            # 지역 + 대표키워드
            for r in regions:
                for kw in rep_kw:
                    keywords.add(f"{r} {kw}")
            # 지역 + 상호명
            for r in regions:
                for name in name_parts:
                    keywords.add(f"{r} {name}")
            # 우선순위 키워드를 앞에 배치
            result = self._filter_and_sort(keywords)
            filtered_priority = [k for k in priority_keywords if k and len(k) >= 2]
            seen = set(filtered_priority)
            final_result = filtered_priority + [k for k in result if k not in seen]
            return final_result
            
        # 지역 + 대표키워드
        for r in regions:
            for kw in rep_kw:
                keywords.add(f"{r} {kw}")
        
        # 지역 + 대표키워드 + 업종
        for r in regions:
            for kw in rep_kw:
                if category:
                    keywords.add(f"{r} {kw} {category}")
        
        # 지역 + 업종 + 추천
        for r in regions:
            for suffix in recommend_suffixes:
                if category:
                    keywords.add(f"{r} {category} {suffix}")
        
        # 지역 + 특징 + 업종
        for r in regions:
            for feat in general_features + amenities:
                if category:
                    keywords.add(f"{r} {feat} {category}")
        
        # === 3. 대표키워드 2~3개 조합 ===
        from itertools import permutations
        
        # 2개 조합
        if len(rep_kw) >= 2:
            for perm in permutations(rep_kw[:8], 2):
                combo = " ".join(perm)
                for r in regions:
                    keywords.add(f"{r} {combo}")
                    if category:
                        keywords.add(f"{r} {combo} {category}")
        
        # 3개 조합
        if len(rep_kw) >= 3:
            for perm in permutations(rep_kw[:6], 3):
                combo = " ".join(perm)
                for r in regions:
                    keywords.add(f"{r} {combo}")
        
        # === 4. 상호명 조합 ===
        for r in regions:
            for name in name_parts:
                keywords.add(f"{r} {name}")
                if category:
                    keywords.add(f"{r} {name} {category}")
        
        # 상호명 단독
        for name in name_parts:
            if len(name) > 2:
                keywords.add(name)
        
        # === 5. 4단 조합 ===
        for r in regions:
            for kw in rep_kw[:5]:
                for suffix in recommend_suffixes[:3]:
                    if category:
                        keywords.add(f"{r} {kw} {category} {suffix}")
        
        # === 6. 상호명 띄어쓰기 기반 파싱 (키워드 부족시 물량 확보용) ===
        name_words = [w for w in place.name.split() if len(w) > 1]
        if len(keywords) < 100 and name_words:
            for r in regions:
                for word in name_words[:6]:
                    keywords.add(f"{r} {word}")
                    if category:
                        keywords.add(f"{r} {word} {category}")
            
            # 상호명 단어 2개 조합
            if len(name_words) >= 2:
                from itertools import permutations
                for perm in permutations(name_words[:5], 2):
                    combo = " ".join(perm)
                    for r in regions:
                        keywords.add(f"{r} {combo}")
        
        # === 7. 필터링 및 우선순위 적용 ===
        result = []
        for k in keywords:
            k = k.strip()
            if len(k) < 3 or len(k) > 50:
                continue
            if not k:
                continue
            result.append(k)

        result = sorted(set(result), key=lambda x: (len(x), x))
        # 우선순위 키워드를 앞에 배치
        filtered_priority = [k for k in priority_keywords if k and len(k) >= 2]
        seen = set(filtered_priority)
        final_result = filtered_priority + [k for k in result if k not in seen]
        return final_result

    def _extract_general_name_parts(self, name: str) -> List[str]:
        """
        일반 업종 상호명에서 검색용 이름 추출
        """
        parts = []
        if not name:
            return parts
        
        # 전체 상호명
        parts.append(name)
        
        # 지역명 제거 시도
        region_prefixes = ["강남", "홍대", "신촌", "서초", "잠실", "송파", "마포", "역삼", "삼성"]
        cleaned_name = name
        for prefix in region_prefixes:
            if name.startswith(prefix):
                cleaned_name = name[len(prefix):]
                break
        if cleaned_name != name and len(cleaned_name) > 1:
            parts.append(cleaned_name)
        
        return list(set(parts))

    def _generate_restaurant_keywords(self, place: PlaceData, simple_mode: bool = False) -> List[str]:
        """
        맛집 키워드 생성 로직 (확장)
        우선순위: 지역 + 업종 카테고리 > 지역 + 메뉴 > 기타
        """
        # 우선순위 키워드 (지역 + 업종 카테고리)
        priority_keywords: List[str] = []
        all_keywords: Set[str] = set()

        # 1. 데이터 전처리 및 추출
        regions = place.region.get_keyword_variations()
        menus = self._get_menus(place)
        themes = self._get_themes(place)
        amenities = self._get_amenities(place)
        industries = self._get_industries(place.category)
        purposes = self._get_purposes(place)

        # 상호명
        name_parts = self._extract_name_parts(place.name)

        if not regions:
            regions = [place.region.gu] if place.region.gu else [""]

        # === 최우선: 지역 + 업종 카테고리 (메인 키워드) ===
        # 업종 카테고리를 더 세분화하여 추출
        main_categories = self._get_main_categories(place.category)

        # 지역 + 메인 카테고리 (최우선 조합)
        for r in regions:
            for cat in main_categories:
                if r and cat:
                    priority_keywords.append(f"{r} {cat}")

        # 지역 + 메인 카테고리 + 맛집/추천 (중복 방지)
        for r in regions:
            for cat in main_categories:
                if r and cat:
                    # "맛집 맛집" 같은 중복 방지
                    if cat != "맛집":
                        priority_keywords.append(f"{r} {cat} 맛집")
                    priority_keywords.append(f"{r} {cat} 추천")

        # 2. 기본 조합 패턴
        all_keywords.update(self._combine_2(regions, menus))
        all_keywords.update(self._combine_2(regions, industries))

        # 단순 모드 처리 (Phase 1용 - 수식어 없이 순수 조합만)
        if simple_mode:
            # 지역 × 업종 카테고리 (최우선)
            all_keywords.update(self._combine_2(regions, main_categories))
            # 지역 × 메뉴
            all_keywords.update(self._combine_2(regions, menus))
            # 지역 × 업종
            all_keywords.update(self._combine_2(regions, industries))
            # 지역 × 상호명
            all_keywords.update(self._combine_2(regions, name_parts))
            # 지역 × 테마(keywordList에서 온 키워드)
            theme_keywords = list(place.keywords) if place.keywords else []
            all_keywords.update(self._combine_2(regions, theme_keywords))

            # 우선순위 키워드를 앞에 배치
            result = self._filter_and_sort(all_keywords)
            # 우선순위 키워드 필터링
            filtered_priority = [k for k in priority_keywords if k and len(k) >= 2]
            # 중복 제거 후 우선순위 키워드를 앞에 배치
            seen = set(filtered_priority)
            final_result = filtered_priority + [k for k in result if k not in seen]
            return final_result
            
        all_keywords.update(self._combine_3(regions, themes + purposes, industries))
        all_keywords.update(self._combine_3(regions, menus, ["맛집", "식당", "전문점", "추천"]))
        all_keywords.update(self._combine_4(regions, purposes + themes, menus, ["맛집", "추천"]))
        all_keywords.update(self._combine_3(regions, amenities, menus + industries))
        
        # 3. 메뉴 2~3개 조합 (물량 확보용)
        # "강남 파스타 스테이크", "홍대 피자 파스타 맛집"
        multi_menu_pairs = self._combine_multi_keywords(menus, 2)
        multi_menu_triples = self._combine_multi_keywords(menus, 3)
        
        all_keywords.update(self._combine_2(regions, multi_menu_pairs))
        all_keywords.update(self._combine_3(regions, multi_menu_pairs, ["맛집", "식당"]))
        all_keywords.update(self._combine_2(regions, multi_menu_triples[:30]))
        
        # 4. 상호명 조합
        all_keywords.update(self._combine_2(regions, name_parts))
        all_keywords.update(self._combine_3(regions, name_parts, ["맛집"]))
        
        # 5. 상호명 띄어쓰기 기반 파싱 (물량 확보용)
        name_words = [w for w in place.name.split() if len(w) > 1]
        if name_words:
            for r in regions:
                for word in name_words[:6]:
                    all_keywords.add(f"{r} {word}")
                    all_keywords.add(f"{r} {word} 맛집")
            
            # 상호명 단어 2개 조합
            if len(name_words) >= 2:
                from itertools import permutations
                for perm in permutations(name_words[:5], 2):
                    combo = " ".join(perm)
                    for r in regions:
                        all_keywords.add(f"{r} {combo}")

        # 우선순위 키워드를 앞에 배치하여 반환
        result = self._filter_and_sort(all_keywords)
        filtered_priority = [k for k in priority_keywords if k and len(k) >= 2]
        seen = set(filtered_priority)
        final_result = filtered_priority + [k for k in result if k not in seen]
        return final_result

    def _get_menus(self, place: PlaceData) -> List[str]:
        # 1. 리뷰 키워드에서 추출 (상위 N개)
        review_menus = [
            re.sub(r"\s가격$", "", k.label)
            for k in place.review_menu_keywords[:self.top_menu_count]
            if len(k.label) > 1
        ]
        
        # 2. 메뉴 탭 데이터에서 추출
        # (리뷰 키워드가 부족할 때 보완하거나 함께 사용)
        tab_menus = [
            m for m in place.menus 
            if len(m) > 1 and "세트" not in m and "음료" not in m
        ]
        
        # 중복 제거 및 병합
        all_menus = list(set(review_menus + tab_menus[:self.top_menu_count]))
        return all_menus

    def _get_themes(self, place: PlaceData) -> List[str]:
        # 리뷰 특징 키워드를 변환 테이블을 통해 확장
        result = set()
        for k in place.review_theme_keywords:
            for key, values in self.THEME_MAP.items():
                if key in k.label:
                    result.update(values)
        return list(result)

    def _get_amenities(self, place: PlaceData) -> List[str]:
        # 편의시설, 좌석, 결제수단, 투표 키워드 통합
        result = set()
        
        # 편의시설
        for conv in place.conveniences:
            for key, values in self.CONVENIENCE_MAP.items():
                if key in conv:
                    result.update(values)
        
        # 좌석
        for seat in place.seat_items:
            for key, values in self.SEAT_MAP.items():
                if key in seat:
                    result.update(values)
                    
        # 투표 키워드 (ReviewKeyword 리스트임)
        for vote in place.voted_keywords:
            # vote.label이 영어 키(key)일 수도 있고 한글일 수도 있음
            # models.py에서 label에 displayName을 넣도록 했으므로 한글일 가능성 높음.
            # 하지만 안전을 위해 key 매핑도 고려해야 함.
            # 현재 로직: 한글 텍스트에 포함된 의미를 찾음
            found = False
            for key, values in self.VOTED_MAP.items():
                # 만약 vote.label이 key("together")와 같거나, 한글 설명에 매핑된 단어가 있다면
                # 여기서는 간단히 한글 매칭을 시도
                pass
            
            # 맵핑 로직 보강:
            # 데이터 수집 시 voted_keywords에는 한글 라벨이 들어감 (예: "단체모임 하기 좋아요")
            # 따라서 텍스트 매칭으로 변환
            if "단체" in vote.label or "회식" in vote.label:
                result.update(["단체", "회식", "모임"])
            if "주차" in vote.label:
                 result.update(["주차", "주차가능"])
            if "넓" in vote.label:
                result.update(["넓은", "대형"])
            if "룸" in vote.label:
                result.update(["룸", "프라이빗"])
            if "혼밥" in vote.label:
                result.update(["혼밥"])
            if "뷰" in vote.label or "경치" in vote.label:
                result.update(["뷰좋은", "전망좋은"])

        # 결제 (제로페이 등)
        for payment in place.payment_info:
            if "제로" in payment:
                result.add("제로페이")
            if "네이버" in payment:
                result.add("네이버페이")
                
        return list(result)

    def _get_main_medical_categories(self, category: str) -> List[str]:
        """
        병의원 카테고리에서 메인 키워드(업종)를 추출
        예: "피부과" -> ["피부과", "피부과의원", "피부클리닉"]
            "정형외과" -> ["정형외과", "정형외과의원"]
        """
        result = []

        if not category:
            return ["병원", "의원"]

        # 병의원 카테고리 -> 메인 키워드 매핑 테이블
        MEDICAL_CATEGORY_MAP = {
            # 피부/성형 계열
            "피부과": ["피부과", "피부과의원", "피부클리닉", "피부"],
            "성형외과": ["성형외과", "성형외과의원", "성형", "미용외과"],
            "피부성형": ["피부과", "성형외과", "피부성형"],

            # 치과 계열
            "치과": ["치과", "치과의원", "치과병원"],
            "교정치과": ["교정치과", "치아교정", "교정"],
            "임플란트": ["임플란트", "임플란트치과"],

            # 안과/이비인후과
            "안과": ["안과", "안과의원", "눈"],
            "이비인후과": ["이비인후과", "이비인후과의원", "귀코목"],

            # 내과 계열
            "내과": ["내과", "내과의원"],
            "소화기내과": ["소화기내과", "위장내과", "내과"],
            "호흡기내과": ["호흡기내과", "폐", "내과"],
            "심장내과": ["심장내과", "순환기내과", "내과"],

            # 외과 계열
            "외과": ["외과", "외과의원"],
            "정형외과": ["정형외과", "정형외과의원", "뼈", "관절"],
            "신경외과": ["신경외과", "신경외과의원", "척추"],

            # 산부인과/비뇨기과
            "산부인과": ["산부인과", "산부인과의원", "여성병원"],
            "비뇨기과": ["비뇨기과", "비뇨의학과", "비뇨기과의원"],

            # 한의원
            "한의원": ["한의원", "한방", "한방병원"],
            "한방병원": ["한방병원", "한의원", "한방"],

            # 정신과/신경과
            "정신건강의학과": ["정신과", "정신건강의학과", "심리상담"],
            "신경과": ["신경과", "신경과의원", "두통"],

            # 재활/통증
            "재활의학과": ["재활의학과", "재활병원", "재활"],
            "마취통증의학과": ["통증의학과", "통증클리닉", "마취통증"],

            # 소아과
            "소아청소년과": ["소아과", "소아청소년과", "어린이병원"],
            "소아과": ["소아과", "소아청소년과"],

            # 기타
            "가정의학과": ["가정의학과", "가정의"],
            "영상의학과": ["영상의학과", "방사선과"],
            "응급의학과": ["응급실", "응급의학과"],

            # 동물병원
            "동물병원": ["동물병원", "동물의료센터", "펫병원"],
            "수의과": ["동물병원", "수의과"],
        }

        # 카테고리에서 매칭되는 키워드 추출
        for key, values in MEDICAL_CATEGORY_MAP.items():
            if key in category:
                result.extend(values)

        # 원본 카테고리도 추가
        result.append(category)

        # 중복 제거 및 빈 값 제거
        result = list(dict.fromkeys([r for r in result if r and len(r) > 0]))

        return result

    def _get_main_general_categories(self, category: str) -> List[str]:
        """
        일반 업종 카테고리에서 메인 키워드(업종)를 추출
        예: "네일아트" -> ["네일", "네일아트", "네일샵"]
            "헬스장" -> ["헬스", "헬스장", "피트니스"]
        """
        result = []

        if not category:
            return [category] if category else []

        # 일반 업종 카테고리 -> 메인 키워드 매핑 테이블
        GENERAL_CATEGORY_MAP = {
            # 뷰티
            "미용실": ["미용실", "헤어샵", "헤어"],
            "헤어샵": ["헤어샵", "미용실", "헤어"],
            "네일아트": ["네일", "네일아트", "네일샵"],
            "네일샵": ["네일샵", "네일", "네일아트"],
            "피부관리": ["피부관리", "피부샵", "에스테틱"],
            "속눈썹": ["속눈썹", "속눈썹연장", "래쉬"],
            "왁싱": ["왁싱", "왁싱샵", "제모"],
            "마사지": ["마사지", "마사지샵", "스파"],
            "스파": ["스파", "마사지", "사우나"],

            # 피트니스
            "헬스장": ["헬스", "헬스장", "피트니스", "헬스클럽"],
            "피트니스": ["피트니스", "헬스", "헬스장"],
            "필라테스": ["필라테스", "필라테스학원"],
            "요가": ["요가", "요가학원", "요가원"],
            "크로스핏": ["크로스핏", "크로스핏박스"],
            "수영장": ["수영장", "수영", "스위밍"],
            "골프연습장": ["골프연습장", "골프", "스크린골프"],

            # 교육
            "학원": ["학원"],
            "영어학원": ["영어학원", "영어", "어학원"],
            "수학학원": ["수학학원", "수학"],
            "피아노학원": ["피아노학원", "피아노", "음악학원"],
            "미술학원": ["미술학원", "미술"],
            "태권도": ["태권도", "태권도장", "무술"],
            "검도": ["검도", "검도장"],

            # 생활서비스
            "세탁소": ["세탁소", "세탁", "드라이클리닝"],
            "수선집": ["수선", "수선집", "옷수선"],
            "열쇠": ["열쇠", "열쇠집", "자물쇠"],
            "이사": ["이사", "이사업체", "포장이사"],
            "청소": ["청소", "청소업체", "가사도우미"],
            "인테리어": ["인테리어", "인테리어업체", "리모델링"],

            # 자동차
            "자동차정비": ["자동차정비", "카센터", "정비소"],
            "세차장": ["세차", "세차장", "손세차"],
            "타이어": ["타이어", "타이어샵"],
            "자동차용품": ["자동차용품", "카용품"],

            # 반려동물
            "펫샵": ["펫샵", "애견샵", "반려동물"],
            "애견미용": ["애견미용", "펫미용", "반려견미용"],
            "애견호텔": ["애견호텔", "펫호텔", "반려동물호텔"],
            "애견카페": ["애견카페", "펫카페"],

            # 꽃/선물
            "꽃집": ["꽃집", "플라워샵", "꽃배달"],
            "선물가게": ["선물", "선물가게", "기프트샵"],

            # 사진
            "사진관": ["사진관", "스튜디오", "사진"],
            "증명사진": ["증명사진", "여권사진"],
        }

        # 카테고리에서 매칭되는 키워드 추출
        for key, values in GENERAL_CATEGORY_MAP.items():
            if key in category:
                result.extend(values)

        # 원본 카테고리도 추가
        result.append(category)

        # 중복 제거 및 빈 값 제거
        result = list(dict.fromkeys([r for r in result if r and len(r) > 0]))

        return result

    def _get_main_categories(self, category: str) -> List[str]:
        """
        맛집 카테고리에서 메인 키워드(업종)를 추출
        예: "이탈리아음식" -> ["이탈리안", "파스타", "양식"]
            "한식" -> ["한식", "한정식"]
            "삼겹살,구이" -> ["삼겹살", "고기", "구이"]
        """
        result = []

        if not category:
            return ["맛집"]

        # 카테고리 -> 메인 키워드 매핑 테이블
        CATEGORY_MAP = {
            # 한식 계열
            "한식": ["한식", "한정식", "밥집"],
            "한정식": ["한정식", "한식"],
            "국밥": ["국밥", "해장"],
            "냉면": ["냉면", "면"],
            "국수": ["국수", "면"],
            "칼국수": ["칼국수", "면"],
            "삼계탕": ["삼계탕", "보양식"],
            "백반": ["백반", "가정식"],
            "분식": ["분식", "떡볶이"],
            "죽": ["죽"],

            # 고기 계열
            "고기": ["고기", "고깃집", "구이"],
            "구이": ["구이", "고기"],
            "삼겹살": ["삼겹살", "고기", "구이"],
            "갈비": ["갈비", "고기"],
            "소고기": ["소고기", "한우", "고기"],
            "한우": ["한우", "소고기"],
            "곱창": ["곱창", "막창"],
            "막창": ["막창", "곱창"],
            "족발": ["족발", "보쌈"],
            "보쌈": ["보쌈", "족발"],
            "닭갈비": ["닭갈비", "닭요리"],
            "치킨": ["치킨", "닭요리"],
            "오리": ["오리", "오리고기"],
            "양꼬치": ["양꼬치", "양고기"],

            # 해산물 계열
            "해산물": ["해산물", "해물"],
            "횟집": ["회", "횟집", "초밥"],
            "회": ["회", "횟집"],
            "초밥": ["초밥", "스시"],
            "생선구이": ["생선구이", "해산물"],
            "조개": ["조개", "해물"],
            "게요리": ["게", "대게", "킹크랩"],
            "랍스터": ["랍스터", "해산물"],
            "장어": ["장어", "민물장어"],
            "아구찜": ["아구찜", "해물찜"],

            # 일식 계열
            "일식": ["일식", "일본음식"],
            "라멘": ["라멘", "라면"],
            "우동": ["우동", "면"],
            "돈가스": ["돈까스", "돈가스"],
            "돈까스": ["돈까스", "돈가스"],
            "덮밥": ["덮밥", "일식"],
            "오마카세": ["오마카세", "스시"],
            "스시": ["스시", "초밥"],
            "이자카야": ["이자카야", "일본술집"],
            "카레": ["카레"],

            # 양식 계열
            "양식": ["양식", "레스토랑"],
            "이탈리아": ["이탈리안", "파스타"],
            "이탈리안": ["이탈리안", "파스타"],
            "파스타": ["파스타", "이탈리안"],
            "피자": ["피자"],
            "스테이크": ["스테이크", "고기"],
            "브런치": ["브런치"],
            "버거": ["버거", "햄버거"],
            "햄버거": ["햄버거", "버거"],
            "샐러드": ["샐러드"],
            "프랑스": ["프렌치", "프랑스요리"],
            "프렌치": ["프렌치", "프랑스요리"],
            "스페인": ["스페인요리", "타파스"],
            "멕시코": ["멕시칸", "타코"],

            # 중식 계열
            "중식": ["중식", "중국음식", "중화요리"],
            "중국": ["중식", "중국음식"],
            "짜장면": ["짜장면", "중식"],
            "짬뽕": ["짬뽕", "중식"],
            "마라탕": ["마라탕", "마라"],
            "마라": ["마라", "마라탕"],
            "훠궈": ["훠궈", "샤브샤브"],
            "딤섬": ["딤섬", "중식"],
            "양꼬치": ["양꼬치", "중식"],

            # 아시안 계열
            "태국": ["태국음식", "타이"],
            "베트남": ["베트남음식", "쌀국수"],
            "쌀국수": ["쌀국수", "베트남"],
            "인도": ["인도음식", "커리"],
            "동남아": ["동남아음식", "아시안"],

            # 카페/디저트
            "카페": ["카페", "커피"],
            "디저트": ["디저트", "케이크"],
            "베이커리": ["베이커리", "빵집"],
            "빵": ["빵집", "베이커리"],
            "케이크": ["케이크", "디저트"],
            "아이스크림": ["아이스크림", "디저트"],
            "와플": ["와플", "디저트"],

            # 주점
            "술집": ["술집", "호프"],
            "호프": ["호프", "술집", "맥주"],
            "이자카야": ["이자카야", "술집"],
            "포차": ["포차", "술집"],
            "와인바": ["와인바", "와인"],
            "바": ["바", "술집"],
            "칵테일": ["칵테일바", "바"],

            # 뷔페
            "뷔페": ["뷔페", "무한리필"],
            "무한리필": ["무한리필", "뷔페"],
            "샤브샤브": ["샤브샤브"],

            # 기타
            "레스토랑": ["레스토랑"],
            "식당": ["식당", "맛집"],
            "음식점": ["맛집", "식당"],
        }

        # 카테고리에서 매칭되는 키워드 추출
        category_lower = category.lower()
        for key, values in CATEGORY_MAP.items():
            if key in category:
                result.extend(values)

        # 원본 카테고리도 추가 (쉼표로 분리된 경우 처리)
        if "," in category:
            parts = [p.strip() for p in category.split(",")]
            result.extend(parts)
        else:
            result.append(category)

        # "맛집"은 항상 포함
        if "맛집" not in result:
            result.append("맛집")

        # 중복 제거 및 빈 값 제거
        result = list(dict.fromkeys([r for r in result if r and len(r) > 0]))

        return result

    def _get_industries(self, category: str) -> List[str]:
        # 카테고리 기반 업종 키워드
        base = [category]
        if "음식" in category or "요리" in category:
            base.append("맛집")
            base.append("식당")
        
        # 카테고리 분해 (예: "이탈리아음식" -> "이탈리안", "파스타")
        if "이탈리아" in category:
            base.extend(["이탈리안", "레스토랑", "파스타맛집"])
        if "한식" in category:
            base.append("밥집")
        if "카페" in category:
            base.extend(["카페", "디저트", "커피"])
        if "고기" in category or "구이" in category:
            base.append("고깃집")
        
        return list(set(base))

    def _get_purposes(self, place: PlaceData) -> List[str]:
        # 목적 키워드 (데이트, 회식 등)
        result = set()
        # 편의시설/좌석 등에서 유추
        amenities = self._get_amenities(place)
        
        if "단체" in amenities or "단체석" in amenities:
            result.update(["회식", "모임", "단체모임", "가족모임"])
        if "데이트" in amenities or "분위기좋은" in amenities:
            result.update(["데이트", "소개팅", "기념일"])
        if "혼밥" in amenities:
            result.update(["혼밥", "혼술"])
            
        return list(result)

    # === 조합 함수 ===
    
    def _combine_multi_keywords(self, keywords: List[str], count: int) -> List[str]:
        """
        키워드 리스트에서 count개를 조합하여 새 키워드 문자열 생성
        예: ["울쎄라", "보톡스", "필러"], 2 -> ["울쎄라 보톡스", "보톡스 울쎄라", "울쎄라 필러", ...]
        """
        from itertools import permutations
        
        result = []
        if len(keywords) < count:
            return result
        
        # 상위 N개만 사용 (너무 많으면 조합 폭발)
        limited = keywords[:10] if count == 2 else keywords[:6]
        
        for perm in permutations(limited, count):
            result.append(" ".join(perm))
        
        return result
    
    def _combine_2(self, list1: List[str], list2: List[str]) -> Set[str]:
        res = set()
        for i in list1:
            for j in list2:
                if i and j:
                    res.add(f"{i} {j}")
        return res

    def _combine_3(self, list1: List[str], list2: List[str], list3: List[str]) -> Set[str]:
        res = set()
        for i in list1:
            for j in list2:
                for k in list3:
                    if i and j and k:
                        res.add(f"{i} {j} {k}")
        return res

    def _combine_4(self, list1: List[str], list2: List[str], list3: List[str], list4: List[str]) -> Set[str]:
        res = set()
        for i in list1:
            for j in list2:
                for k in list3:
                    for l in list4:
                        if i and j and k and l:
                            res.add(f"{i} {j} {k} {l}")
        return res

    def _filter_and_sort(self, keywords: Set[str]) -> List[str]:
        """
        생성된 키워드 필터링 및 정렬
        """
        filtered = []
        
        for k in keywords:
            # 1. 길이 필터 (너무 짧거나 긴 것)
            if len(k) < 2 or len(k) > 30:  # 최소 2자로 완화
                continue
                
            parts = k.split()
            # 2. 단어 수 필터 완화 (1어절 이상 - 상호명 단독 키워드 허용)
            # 단, 너무 짧은 단일 단어는 제외
            if len(parts) < 1:
                continue
            if len(parts) == 1 and len(k) < 2:
                continue
            
            # 3. 중복 단어 제거 (예: "강남 맛집 맛집")
            if len(parts) != len(set(parts)):
                continue
                
            # 4. 블랙리스트 패턴
            is_blacklisted = False
            for pattern in self.BLACKLIST_PATTERNS:
                if re.match(pattern, k):
                    is_blacklisted = True
                    break
            if is_blacklisted:
                continue
            
            # 5. 의미적 중복 필터 (간단 버전)
            # "맛집"과 "식당"이 같이 있으면 어색할 수 있음 (선택적)
            
            filtered.append(k)
            
        # 정렬: 길이 순 -> 가나다 순
        return sorted(filtered, key=lambda x: (len(x), x))
