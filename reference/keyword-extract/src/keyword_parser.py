"""
KeywordParser: 사전 기반 복합 키워드 파싱 모듈
AdLog 데이터로 구축된 keyword_dictionary.json을 활용하여
복합 키워드를 개별 토큰으로 분해합니다.

예시:
    "강남역피부과스킨부스터추천" → ["강남역", "피부과", "스킨부스터", "추천"]
    "서면쭈꾸미" → ["서면", "쭈꾸미"]
"""

import json
import os
from typing import List, Dict, Set, Optional, NamedTuple
from dataclasses import dataclass

# EXE 빌드용 리소스 경로 헬퍼
try:
    from src.resource_path import get_resource_path
except ImportError:
    from resource_path import get_resource_path


@dataclass
class ParseResult:
    """파싱 결과를 담는 데이터 클래스"""
    original: str
    tokens: List[str]
    categories: Dict[str, List[str]]
    
    def get_regions(self) -> List[str]:
        """지역 토큰만 반환"""
        return self.categories.get("지역", [])
    
    def get_industries(self) -> List[str]:
        """업종 토큰만 반환"""
        return self.categories.get("업종", [])
    
    def get_modifiers(self) -> List[str]:
        """수식어 토큰만 반환"""
        return self.categories.get("수식어", []) + self.categories.get("일반_수식어", [])


class KeywordParser:
    """
    사전 기반 복합 키워드 파서
    
    Longest-Match-First 알고리즘을 사용하여 복합어를 분해합니다.
    예: "강남역피부과" → ["강남역", "피부과"] (not ["강남", "역", "피부", "과"])
    """
    
    def __init__(self, dict_path: str = None, min_word_length: int = 2):
        """
        Args:
            dict_path: keyword_dictionary.json 경로 (None이면 기본 경로 사용)
            min_word_length: 추출할 최소 단어 길이
        """
        if dict_path is None:
            # EXE/개발 환경 모두 지원하는 경로
            dict_path = get_resource_path(os.path.join("data", "keyword_dictionary.json"))
        
        self.dict_path = dict_path
        self.min_word_length = min_word_length
        
        # 사전 로드 및 데이터 구조 초기화
        self.dictionary = self._load_dictionary()
        self.all_words: List[str] = []
        self.word_to_category: Dict[str, str] = {}
        self._build_data_structures()
    
    def _load_dictionary(self) -> Dict:
        """JSON 사전 파일 로드"""
        try:
            with open(self.dict_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[KeywordParser] Warning: Dictionary not found at {self.dict_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"[KeywordParser] Error: Invalid JSON in dictionary - {e}")
            return {}
    
    def _build_data_structures(self):
        """
        사전에서 모든 단어를 추출하고 길이순 정렬
        카테고리 매핑 테이블 구축
        """
        words_set: Set[str] = set()
        
        def extract_words(obj, category_path: str = ""):
            """재귀적으로 모든 단어 추출"""
            if isinstance(obj, list):
                for word in obj:
                    if isinstance(word, str) and len(word) >= self.min_word_length:
                        words_set.add(word)
                        # 첫 번째 카테고리만 저장 (중복 방지)
                        if word not in self.word_to_category:
                            self.word_to_category[word] = category_path
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{category_path}/{key}" if category_path else key
                    extract_words(value, new_path)
        
        extract_words(self.dictionary)
        
        # 길이 내림차순 정렬 (Longest-Match-First)
        self.all_words = sorted(list(words_set), key=len, reverse=True)
        
        print(f"[KeywordParser] Loaded {len(self.all_words)} words from dictionary")
    
    def parse(self, text: str) -> ParseResult:
        """
        복합 키워드를 개별 토큰으로 파싱
        
        Args:
            text: 파싱할 복합 키워드 (예: "강남역피부과스킨부스터추천")
            
        Returns:
            ParseResult: 원본, 토큰 리스트, 카테고리별 분류
        """
        if not text or not self.all_words:
            return ParseResult(original=text, tokens=[], categories={})
        
        tokens = self._extract_tokens(text)
        categories = self._categorize_tokens(tokens)
        
        return ParseResult(
            original=text,
            tokens=tokens,
            categories=categories
        )
    
    def _extract_tokens(self, text: str) -> List[str]:
        """
        Longest-Match-First 그리디 토큰 추출
        사전에 없는 단어도 2글자 이상이면 유지 (fallback)
        
        Args:
            text: 입력 문자열
            
        Returns:
            추출된 토큰 리스트 (순서 유지)
        """
        result = []
        remaining = text
        unknown_buffer = ""  # 알 수 없는 문자 버퍼
        
        while remaining:
            matched = False
            
            # 긴 단어부터 매칭 시도
            for word in self.all_words:
                if remaining.startswith(word):
                    # 매칭 전에 unknown_buffer 처리
                    if unknown_buffer and len(unknown_buffer) >= self.min_word_length:
                        result.append(unknown_buffer)
                    unknown_buffer = ""
                    
                    result.append(word)
                    remaining = remaining[len(word):]
                    matched = True
                    break
            
            if not matched:
                # 알 수 없는 문자는 버퍼에 추가
                unknown_buffer += remaining[0]
                remaining = remaining[1:]
        
        # 마지막 남은 unknown_buffer 처리
        if unknown_buffer and len(unknown_buffer) >= self.min_word_length:
            result.append(unknown_buffer)
        
        return result
    
    def _categorize_tokens(self, tokens: List[str]) -> Dict[str, List[str]]:
        """
        토큰들을 카테고리별로 분류
        
        Args:
            tokens: 추출된 토큰 리스트
            
        Returns:
            카테고리 → 토큰 리스트 매핑
        """
        categories: Dict[str, List[str]] = {}
        
        for token in tokens:
            if token in self.word_to_category:
                category_path = self.word_to_category[token]
                # 최상위 카테고리만 사용 (지역, 업종, 수식어)
                top_category = category_path.split("/")[0]
                
                if top_category not in categories:
                    categories[top_category] = []
                
                if token not in categories[top_category]:
                    categories[top_category].append(token)
        
        return categories
    
    def parse_multiple(self, texts: List[str]) -> List[ParseResult]:
        """여러 키워드를 한번에 파싱"""
        return [self.parse(text) for text in texts]
    
    def extract_unique_tokens(self, texts: List[str]) -> Set[str]:
        """여러 키워드에서 고유 토큰만 추출"""
        all_tokens: Set[str] = set()
        for text in texts:
            result = self.parse(text)
            all_tokens.update(result.tokens)
        return all_tokens
    
    def get_category_tokens(self, texts: List[str], category: str) -> Set[str]:
        """특정 카테고리의 토큰만 추출"""
        tokens: Set[str] = set()
        for text in texts:
            result = self.parse(text)
            tokens.update(result.categories.get(category, []))
        return tokens

    def add_word(self, word: str, category_path: str):
        """
        사전에 새로운 단어 추가 (메모리 업데이트)
        
        Args:
            word: 추가할 단어
            category_path: 카테고리 경로 (예: "지역/동_역")
        """
        if len(word) < self.min_word_length:
            return
            
        # 1. dictionary 구조 업데이트
        parts = category_path.split("/")
        current = self.dictionary
        
        try:
            for part in parts[:-1]: # 마지막 전까진 dict 탐색
                current = current[part]
            
            target_list_key = parts[-1]
            if target_list_key in current and isinstance(current[target_list_key], list):
                if word not in current[target_list_key]:
                    current[target_list_key].append(word)
            else:
                # 경로가 없거나 리스트가 아니면 추가 불가 (안전장치)
                print(f"[KeywordParser] Cannot add word '{word}' to path '{category_path}' (invalid structure)")
                return
                
        except KeyError:
             print(f"[KeywordParser] Invalid category path: {category_path}")
             return
        
        # 2. 캐시 데이터 업데이트
        if word not in self.word_to_category:
            self.word_to_category[word] = category_path
            self.all_words.append(word)
            # 길이순 재정렬 (Longest-Match)
            self.all_words.sort(key=len, reverse=True)
            print(f"[KeywordParser] Added new word: {word} ({category_path})")

    def save(self):
        """현재 사전을 파일로 저장"""
        try:
            with open(self.dict_path, 'w', encoding='utf-8') as f:
                json.dump(self.dictionary, f, indent=4, ensure_ascii=False)
            print(f"[KeywordParser] Saved dictionary to {self.dict_path}")
        except Exception as e:
            print(f"[KeywordParser] Error saving dictionary: {e}")


# === 테스트 코드 ===
if __name__ == "__main__":
    parser = KeywordParser()
    
    test_cases = [
        "강남역피부과스킨부스터추천",
        "서면쭈꾸미",
        "브라질리언왁싱창원",
        "압구정모발이식전문",
        "해운대맛집회식단체모임",
        "곤지암스키강습렌탈샵",
        "강남이혼전문변호사상담",
    ]
    
    print("\n=== KeywordParser 테스트 ===\n")
    
    for text in test_cases:
        result = parser.parse(text)
        print(f"원본: {result.original}")
        print(f"토큰: {result.tokens}")
        print(f"카테고리: {result.categories}")
        print(f"  - 지역: {result.get_regions()}")
        print(f"  - 업종: {result.get_industries()}")
        print(f"  - 수식어: {result.get_modifiers()}")
        print()
