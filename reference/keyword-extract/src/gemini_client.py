"""
Gemini API Client for Keyword Extraction
AI 기반 종합 키워드 파싱 - 지역, 업종, 수식어, 상호명 분석

새로운 google-genai SDK 사용 (google.generativeai는 지원 종료됨)
"""
import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# 새로운 SDK 사용
try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    print("[GeminiClient] google-genai 패키지가 설치되어 있지 않습니다.")
    print("  설치: pip install google-genai")


@dataclass
class GeminiResult:
    """Gemini API 응답 결과"""
    name_keywords: List[str]  # 상호명에서 추출한 키워드
    related_keywords: List[str]  # 연관 키워드
    success: bool
    error_message: str = ""


@dataclass
class ComprehensiveParseResult:
    """종합 파싱 결과"""
    # 지역 관련
    regions: List[str] = field(default_factory=list)  # 발견된 지역명
    landmarks: List[str] = field(default_factory=list)  # 랜드마크 (역, 건물 등)

    # 업종/서비스 관련
    business_types: List[str] = field(default_factory=list)  # 업종 키워드
    services: List[str] = field(default_factory=list)  # 서비스/메뉴 키워드

    # 수식어/테마
    modifiers: List[str] = field(default_factory=list)  # 수식어 (맛집, 추천 등)
    themes: List[str] = field(default_factory=list)  # 테마/상황 (데이트, 회식 등)

    # 상호명 분석
    name_tokens: List[str] = field(default_factory=list)  # 상호명에서 분리된 의미 단위

    # 연관 키워드
    related_keywords: List[str] = field(default_factory=list)  # AI 생성 연관 키워드

    # 메타 정보
    success: bool = False
    error_message: str = ""

    def get_all_regions(self) -> List[str]:
        """모든 지역 관련 키워드 반환 (지역명 + 랜드마크)"""
        return list(set(self.regions + self.landmarks))

    def get_all_keywords(self) -> List[str]:
        """모든 키워드 반환 (중복 제거)"""
        all_kw = (self.regions + self.landmarks + self.business_types +
                  self.services + self.modifiers + self.themes +
                  self.name_tokens + self.related_keywords)
        return list(set(all_kw))


class GeminiClient:
    """
    Gemini API를 사용한 키워드 추출 클라이언트 (새 SDK 버전)

    기능:
    1. 상호명 형태소 분석 - 붙어있는 단어 분리
    2. 연관 키워드 생성 - 대표키워드에서 검색 키워드 확장
    """

    # 모델 설정 (기본값, __init__에서 오버라이드 가능)
    DEFAULT_MODEL_NAME = "gemini-2.0-flash-lite"

    # 프롬프트 템플릿
    # 상호명 변형 생성용 프롬프트 (브랜드명만 추출, 업종/지역 키워드 제외)
    PROMPT_NAME_VARIATIONS = """당신은 한국어 상호명 분석 전문가입니다.

다음 상호명에서 **브랜드명/가게이름의 변형만** 추출해주세요.
업종, 메뉴, 서비스, 지역 관련 키워드는 절대 포함하지 마세요.

상호명: {name}
카테고리(참고용): {category}

=== 규칙 ===
1. 상호명의 핵심 브랜드명 추출
2. 브랜드명의 약칭/줄임말 생성 (2~3글자)
3. 지점명이 있으면 지점명과 결합한 변형 생성
4. 띄어쓰기 없는 버전도 포함

=== 예시 ===
- "르글라스 압구정점" → ["르글라스", "르글", "르글라스압구정", "르글라스압구정점"]
- "스타벅스 강남역점" → ["스타벅스", "스벅", "스타벅스강남역", "스타벅스강남역점"]
- "한재농사꾼박진동" → ["한재농사꾼박진동", "한재농사꾼", "한재"]
- "미나리삼겹살" → ["미나리삼겹살"] (브랜드명 자체가 메뉴 포함)

=== 제외할 것 ===
- 순수 지역명만 있는 것 (압구정, 강남 등) - 제외
- 업종/메뉴 키워드 (와인, 삼겹살, 카페 등) - 제외
- 일반 수식어 (맛집, 추천 등) - 제외

JSON 형식으로 응답:
{{"name_variations": ["변형1", "변형2", ...]}}"""

    # 기존 키워드 추출용 (deprecated, 호환성 유지)
    PROMPT_NAME_PARSE = """당신은 한국어 상호명 분석 전문가입니다.

다음 상호명에서 검색에 유용한 키워드를 추출해주세요.

상호명: {name}
카테고리: {category}

규칙:
1. 붙어있는 단어를 의미 단위로 분리 (예: "한재농사꾼박진동" → "한재", "농사꾼", "박진동")
2. 지역명이 포함되어 있으면 추출 (예: "강남리더스" → "강남", "리더스")
3. 업종/서비스 관련 단어 추출 (예: "미나리삼겹살" → "미나리", "삼겹살")
4. 의미없는 조사, 접속사는 제외
5. 최소 2글자 이상만 추출

JSON 형식으로 응답:
{{"keywords": ["키워드1", "키워드2", ...]}}"""

    PROMPT_RELATED_KEYWORDS = """당신은 네이버 플레이스 검색 키워드 전문가입니다.

다음 업체 정보를 바탕으로 사람들이 검색할 만한 연관 키워드를 생성해주세요.

업체명: {name}
카테고리: {category}
대표 키워드: {keywords}
메뉴/서비스: {menus}

규칙:
1. 실제 사람들이 네이버에서 검색할 법한 키워드만
2. 너무 일반적인 키워드는 제외 (맛집, 음식점 등은 이미 있음)
3. 업종 특성을 반영한 구체적인 키워드
4. 메뉴나 서비스의 다른 표현 방식
5. 최대 10개까지만

JSON 형식으로 응답:
{{"keywords": ["키워드1", "키워드2", ...]}}"""

    # 종합 파싱 프롬프트 - 한 번의 API 호출로 모든 정보 추출
    PROMPT_COMPREHENSIVE_PARSE = """당신은 네이버 플레이스 키워드 분석 전문가입니다.

다음 업체 정보를 분석하여 검색에 유용한 키워드를 카테고리별로 추출해주세요.

=== 업체 정보 ===
업체명: {name}
카테고리: {category}
주소: {address}
대표 키워드: {keywords}
메뉴/서비스: {menus}

=== 추출 규칙 ===

1. regions (지역명): 행정구역 단위의 지역명
   - 시/도: 서울, 부산, 경기, 인천 등
   - 시/군/구: 강남구, 일산동구, 청도군, 수원시 등
   - 동/읍/면: 장항동, 역삼동, 청도읍 등
   - 주요 지역명: 강남, 일산, 분당, 판교 등

2. landmarks (랜드마크): 역명, 건물, 명소
   - 지하철역: 강남역, 홍대역, 판교역 등 (반드시 "역" 포함)
   - 유명 건물/지역: 코엑스, 타임스퀘어, 가로수길 등

3. business_types (업종): 업종/분야 키워드
   - 음식: 삼겹살, 한식, 일식, 카페 등
   - 의료: 치과, 피부과, 한의원 등
   - 서비스: 미용실, 네일, 필라테스 등

4. services (서비스/메뉴): 구체적인 서비스나 메뉴
   - 음식점: 미나리삼겹살, 된장찌개, 오마카세 등
   - 의료: 임플란트, 도수치료, 스킨부스터 등
   - 뷰티: 속눈썹연장, 브라질리언왁싱 등

5. modifiers (수식어): 검색 수식어
   - 평가: 맛집, 추천, 유명한, 잘하는 등
   - 편의: 주차, 예약, 24시, 무한리필 등

6. themes (테마/상황): 방문 목적/상황
   - 모임: 회식, 데이트, 가족모임, 생일파티 등
   - 시간: 점심, 저녁, 야식, 브런치 등

7. name_tokens (상호명 분석): 상호명을 의미 단위로 분리
   - 붙어있는 단어 분리: "한재농사꾼박진동" → "한재", "농사꾼", "박진동"
   - 의미있는 단어만 추출 (2글자 이상)

8. related_keywords (연관 키워드): 위 항목에 없지만 검색에 유용한 키워드
   - 동의어, 유사 표현, 연관 검색어
   - 최대 10개

=== JSON 응답 형식 ===
{{
    "regions": ["지역1", "지역2"],
    "landmarks": ["랜드마크1", "랜드마크2"],
    "business_types": ["업종1", "업종2"],
    "services": ["서비스1", "서비스2"],
    "modifiers": ["수식어1", "수식어2"],
    "themes": ["테마1", "테마2"],
    "name_tokens": ["토큰1", "토큰2"],
    "related_keywords": ["연관1", "연관2"]
}}

중요: 모든 키워드는 2글자 이상이어야 합니다. 빈 카테고리는 빈 배열 []로 응답하세요."""

    # 키워드 분해 프롬프트 - 복합 키워드를 단어 단위로 분해
    PROMPT_KEYWORD_DECOMPOSE = """당신은 한국어 키워드 분해 전문가입니다.

다음 키워드들을 단어 단위로 분해해주세요.
지역명은 제외하고 순수 서비스/메뉴/업종 키워드만 분해합니다.

키워드: {keywords}
카테고리(참고용): {category}

=== 규칙 ===
1. 복합 키워드를 의미 단위로 분해
   예: "갈치구이" → ["갈치", "구이", "갈치구이"]
   예: "통갈치구이" → ["통갈치", "갈치", "구이", "통갈치구이"]
   예: "생선구이정식" → ["생선", "생선구이", "구이", "정식", "생선구이정식"]
   예: "해물탕정식" → ["해물", "해물탕", "정식", "해물탕정식"]
   예: "보톡스필러" → ["보톡스", "필러", "보톡스필러"]
   예: "피부미백" → ["피부", "미백", "피부미백"]

2. 분해 시 고려사항:
   - 원본 키워드도 반드시 포함
   - 의미있는 중간 조합도 포함 (예: "생선구이정식" → "생선구이"도 포함)
   - 너무 일반적인 단어는 제외 (음식, 맛, 식사 등)
   - 2글자 이상만 포함

3. 제외 대상:
   - 지역명 (강남, 서울, 압구정 등)
   - 너무 일반적인 수식어 (맛집, 추천, 유명 등)
   - 1글자 단어

JSON 형식으로 응답:
{{"decomposed": ["단어1", "단어2", "원본키워드1", "원본키워드2", ...]}}"""

    def __init__(self, api_key: str = None, model_name: str = None):
        """
        Args:
            api_key: Gemini API 키 (None이면 비활성화)
            model_name: 사용할 모델명 (None이면 DEFAULT_MODEL_NAME 사용)
        """
        self.api_key = api_key
        self.model_name = model_name or self.DEFAULT_MODEL_NAME
        self.client = None
        self.enabled = False

        if api_key and HAS_GEMINI:
            self._initialize(api_key)

    def _initialize(self, api_key: str) -> bool:
        """API 초기화"""
        try:
            self.client = genai.Client(api_key=api_key)
            self.enabled = True
            print(f"[GeminiClient] 초기화 완료 (모델: {self.model_name})")
            return True
        except Exception as e:
            print(f"[GeminiClient] 초기화 실패: {e}")
            self.enabled = False
            return False

    def set_api_key(self, api_key: str) -> bool:
        """API 키 설정/변경"""
        self.api_key = api_key
        if api_key and HAS_GEMINI:
            return self._initialize(api_key)
        else:
            self.enabled = False
            return False

    def is_available(self) -> bool:
        """API 사용 가능 여부"""
        return self.enabled and self.client is not None

    def _generate_content(self, prompt: str) -> str:
        """새 SDK로 콘텐츠 생성"""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        return response.text

    def parse_business_name_variations(self, name: str, category: str = "") -> List[str]:
        """
        상호명의 브랜드명 변형 생성 (업종/지역 키워드 제외)

        예: "르글라스 압구정점" → ["르글라스", "르글", "르글라스압구정", "르글라스압구정점"]
        """
        if not self.is_available():
            return []

        try:
            prompt = self.PROMPT_NAME_VARIATIONS.format(
                name=name,
                category=category
            )

            response_text = self._generate_content(prompt)
            result = self._parse_json_response(response_text)

            variations = result.get("name_variations", [])
            variations = list(dict.fromkeys([v for v in variations if len(v) >= 2]))

            print(f"[GeminiClient] 상호명 변형 생성: '{name}' → {variations}")
            return variations

        except Exception as e:
            print(f"[GeminiClient] 상호명 변형 생성 실패: {e}")
            return []

    def parse_name(self, name: str, category: str = "") -> List[str]:
        """
        상호명에서 키워드 추출 (형태소 분석)
        NOTE: 상호명 변형만 필요하면 parse_business_name_variations() 사용 권장
        """
        if not self.is_available():
            return []

        try:
            prompt = self.PROMPT_NAME_PARSE.format(
                name=name,
                category=category
            )

            response_text = self._generate_content(prompt)
            result = self._parse_json_response(response_text)

            keywords = result.get("keywords", [])
            keywords = list(set([k for k in keywords if len(k) >= 2]))

            print(f"[GeminiClient] 상호명 파싱: '{name}' → {keywords}")
            return keywords

        except Exception as e:
            print(f"[GeminiClient] 상호명 파싱 실패: {e}")
            return []

    def generate_related_keywords(
        self,
        name: str,
        category: str,
        keywords: List[str],
        menus: List[str] = None
    ) -> List[str]:
        """연관 키워드 생성"""
        if not self.is_available():
            return []

        try:
            prompt = self.PROMPT_RELATED_KEYWORDS.format(
                name=name,
                category=category,
                keywords=", ".join(keywords[:10]) if keywords else "없음",
                menus=", ".join(menus[:10]) if menus else "없음"
            )

            response_text = self._generate_content(prompt)
            result = self._parse_json_response(response_text)

            related = result.get("keywords", [])
            existing = set(keywords) if keywords else set()
            related = list(set([k for k in related if len(k) >= 2 and k not in existing]))

            print(f"[GeminiClient] 연관 키워드 생성: {len(related)}개")
            return related

        except Exception as e:
            print(f"[GeminiClient] 연관 키워드 생성 실패: {e}")
            return []

    def analyze_place(
        self,
        name: str,
        category: str,
        keywords: List[str] = None,
        menus: List[str] = None
    ) -> GeminiResult:
        """업체 정보 종합 분석"""
        if not self.is_available():
            return GeminiResult(
                name_keywords=[],
                related_keywords=[],
                success=False,
                error_message="Gemini API가 비활성화되어 있습니다."
            )

        try:
            name_keywords = self.parse_name(name, category)
            related_keywords = self.generate_related_keywords(
                name, category, keywords or [], menus or []
            )

            return GeminiResult(
                name_keywords=name_keywords,
                related_keywords=related_keywords,
                success=True
            )

        except Exception as e:
            return GeminiResult(
                name_keywords=[],
                related_keywords=[],
                success=False,
                error_message=str(e)
            )

    def comprehensive_parse(
        self,
        name: str,
        category: str,
        address: str = "",
        keywords: List[str] = None,
        menus: List[str] = None
    ) -> ComprehensiveParseResult:
        """종합 키워드 파싱"""
        if not self.is_available():
            return ComprehensiveParseResult(
                success=False,
                error_message="Gemini API가 비활성화되어 있습니다."
            )

        try:
            prompt = self.PROMPT_COMPREHENSIVE_PARSE.format(
                name=name,
                category=category,
                address=address or "정보 없음",
                keywords=", ".join(keywords[:15]) if keywords else "없음",
                menus=", ".join(menus[:15]) if menus else "없음"
            )

            response_text = self._generate_content(prompt)
            result = self._parse_json_response(response_text)

            def filter_keywords(kw_list):
                if not kw_list:
                    return []
                return list(set([k for k in kw_list if isinstance(k, str) and len(k) >= 2]))

            parsed_result = ComprehensiveParseResult(
                regions=filter_keywords(result.get("regions", [])),
                landmarks=filter_keywords(result.get("landmarks", [])),
                business_types=filter_keywords(result.get("business_types", [])),
                services=filter_keywords(result.get("services", [])),
                modifiers=filter_keywords(result.get("modifiers", [])),
                themes=filter_keywords(result.get("themes", [])),
                name_tokens=filter_keywords(result.get("name_tokens", [])),
                related_keywords=filter_keywords(result.get("related_keywords", [])),
                success=True
            )

            total_keywords = len(parsed_result.get_all_keywords())
            print(f"[GeminiClient] 종합 파싱 완료: {total_keywords}개 키워드 추출")

            return parsed_result

        except Exception as e:
            print(f"[GeminiClient] 종합 파싱 실패: {e}")
            return ComprehensiveParseResult(
                success=False,
                error_message=str(e)
            )

    def _parse_json_response(self, text: str) -> dict:
        """응답에서 JSON 추출 (중첩 JSON 지원)"""
        # 1. 코드 블록 내 JSON (우선)
        code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_match:
            json_str = self._fix_trailing_commas(code_match.group(1))
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 2. 균형 잡힌 중괄호 탐색 (중첩 JSON 지원)
        json_str = self._extract_balanced_json(text)
        if json_str:
            json_str = self._fix_trailing_commas(json_str)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 3. 단순 패턴 폴백
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            json_str = self._fix_trailing_commas(json_match.group())
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        return {}

    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """균형 잡힌 중괄호로 JSON 블록 추출"""
        start = text.find('{')
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for i in range(start, len(text)):
            ch = text[i]

            if escape:
                escape = False
                continue

            if ch == '\\' and in_string:
                escape = True
                continue

            if ch == '"' and not escape:
                in_string = not in_string
                continue

            if in_string:
                continue

            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]

        return None

    @staticmethod
    def _fix_trailing_commas(json_str: str) -> str:
        """JSON 문자열에서 트레일링 콤마 제거"""
        # ,] 또는 ,} 패턴 제거 (공백 포함)
        json_str = re.sub(r',\s*(\])', r'\1', json_str)
        json_str = re.sub(r',\s*(\})', r'\1', json_str)
        return json_str

    def decompose_keywords(self, keywords: List[str], category: str = "") -> List[str]:
        """
        복합 키워드를 단어 단위로 분해

        예: ["갈치구이", "통갈치구이", "생선구이정식"]
        → ["갈치", "구이", "갈치구이", "통갈치", "통갈치구이", "생선", "생선구이", "정식", "생선구이정식"]

        Args:
            keywords: 분해할 키워드 리스트
            category: 카테고리 (참고용)

        Returns:
            분해된 키워드 리스트 (원본 포함, 중복 제거)
        """
        if not self.is_available():
            print("[GeminiClient] API 사용 불가 - 원본 키워드 반환")
            return keywords

        if not keywords:
            return []

        try:
            # 최대 20개까지만 처리 (API 비용 절감)
            keywords_to_process = keywords[:20]

            prompt = self.PROMPT_KEYWORD_DECOMPOSE.format(
                keywords=", ".join(keywords_to_process),
                category=category
            )

            response_text = self._generate_content(prompt)
            result = self._parse_json_response(response_text)

            decomposed = result.get("decomposed", [])

            # 필터링: 2글자 이상, 문자열만
            decomposed = [k for k in decomposed if isinstance(k, str) and len(k) >= 2]

            # 원본 키워드도 포함되었는지 확인하고 없으면 추가
            decomposed_set = set(decomposed)
            for kw in keywords_to_process:
                if kw not in decomposed_set:
                    decomposed.append(kw)

            # 중복 제거하면서 순서 유지
            seen = set()
            unique_decomposed = []
            for kw in decomposed:
                if kw not in seen:
                    seen.add(kw)
                    unique_decomposed.append(kw)

            print(f"[GeminiClient] 키워드 분해: {len(keywords_to_process)}개 → {len(unique_decomposed)}개")
            print(f"  원본: {keywords_to_process[:5]}...")
            print(f"  분해: {unique_decomposed[:10]}...")

            return unique_decomposed

        except Exception as e:
            print(f"[GeminiClient] 키워드 분해 실패: {e}")
            # 실패 시 원본 반환
            return keywords

    def test_connection(self) -> Tuple[bool, str]:
        """API 연결 테스트 (모델 목록 조회로 할당량 소모 없이 확인)"""
        if not HAS_GEMINI:
            return False, "google-genai 패키지가 설치되어 있지 않습니다."

        if not self.api_key:
            return False, "API 키가 설정되지 않았습니다."

        try:
            # 모델 목록 조회 (할당량 소모 없음)
            models = list(self.client.models.list())
            if models:
                model_names = [m.name for m in models[:3]]
                return True, f"연결 성공! 사용 가능 모델: {len(models)}개"
            return False, "모델 목록이 비어있습니다."
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                return False, "할당량 초과 - 결제 반영까지 24시간 대기 필요"
            return False, f"연결 실패: {error_str}"


# 싱글톤 인스턴스
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """싱글톤 Gemini 클라이언트 반환"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client


def init_gemini(api_key: str, model_name: str = None) -> bool:
    """Gemini API 초기화"""
    client = get_gemini_client()
    if model_name:
        client.model_name = model_name
    return client.set_api_key(api_key)


# 테스트
if __name__ == "__main__":
    API_KEY = "YOUR_API_KEY"

    client = GeminiClient(API_KEY)

    if client.is_available():
        keywords = client.parse_name(
            "한재농사꾼박진동 한재 미나리 식당",
            "삼겹살,구이"
        )
        print(f"상호명 키워드: {keywords}")
