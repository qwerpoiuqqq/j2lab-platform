"""
네이버 플레이스 순위 체크 엔진 - GraphQL API 버전 (curl_cffi 기반, Chrome TLS 핑거프린트)

[핵심 원리]
1. 입력: 검색 키워드 + 업체 place_id
2. 처리: GraphQL API(순위) + 검색HTML(지도형태) 병렬 요청
3. 출력: 해당 place_id의 순위와 지도 형태

[API 엔드포인트]
- 순위: https://nx-api.place.naver.com/graphql
- 지도형태: https://m.search.naver.com/search.naver (queryType 추출)

[지도 형태 판단 - 2025-01 분석]
- queryType이 있음 (restaurant, hospital, hairshop 등) → 신지도
- queryType이 null → 구지도
- "지도" 키워드가 붙으면 queryType이 null이 됨

[스마트 세션 관리]
- 세션별 독립 헬스 체크
- 차단된 세션만 쿨다운, 나머지는 풀스피드 유지
- 즉시 재시도 with 다른 세션
"""

import re
import random
import json
import asyncio
import threading
import time as time_module
import hashlib
import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from curl_cffi.requests import Session as CurlSession
    from curl_cffi.requests.errors import RequestsError as CurlRequestsError
    _curl_cffi_available = True
except ImportError:
    print("[RankCheckerGraphQL] curl_cffi가 설치되지 않았습니다. pip install curl_cffi")
    _curl_cffi_available = False
    CurlSession = None
    CurlRequestsError = Exception


@dataclass
class RankResult:
    """순위 체크 결과"""
    keyword: str
    rank: Optional[int] = None
    map_type: str = "신지도"  # gdid에서 추출 (기본값: 신지도)
    status: str = "pending"
    error_message: str = ""
    place_name: str = ""  # 발견된 업체명
    business_category: str = ""  # 업종 카테고리 (restaurant, hospital 등)
    total_count: Optional[int] = None  # 검색 결과 총 개수 (PLT 판정용)


@dataclass
class ProxyConfig:
    """프록시 설정

    Decodo 세션 타입:
    - rotating: 매 요청마다 새 IP (기본값, 권장)
    - sticky: 세션 ID로 같은 IP 유지 (1분 등)
    """
    host: str
    port: int
    username: str = ""
    password: str = ""
    proxy_type: str = "datacenter"  # "decodo" 또는 "datacenter"
    session_type: str = "rotating"  # "rotating" 또는 "sticky"
    session_id: str = ""  # sticky 세션용 ID

    @property
    def url(self) -> str:
        """프록시 URL 생성 (Decodo rotating/sticky 지원)"""
        if self.username and self.password:
            # Decodo rotating 세션: 기본값 (매 요청 새 IP)
            # Decodo sticky 세션: username-session-{id}:password
            if self.proxy_type.lower() == "decodo" and self.session_type == "sticky" and self.session_id:
                modified_user = f"{self.username}-session-{self.session_id}"
                return f"http://{modified_user}:{self.password}@{self.host}:{self.port}"
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"

    @property
    def is_decodo(self) -> bool:
        return self.proxy_type.lower() == "decodo"

    @property
    def is_rotating(self) -> bool:
        """Rotating 세션 여부 (Decodo에서 매 요청 새 IP)"""
        return self.proxy_type.lower() == "decodo" and self.session_type == "rotating"

    @property
    def label(self) -> str:
        """프록시 식별용 라벨"""
        return f"{self.host}:{self.port}"


class SessionHealth:
    """세션 헬스 상태 (Site Unblocker 스타일)"""
    HEALTHY = "healthy"
    COOLING_DOWN = "cooling_down"
    BLOCKED = "blocked"


@dataclass
class SessionState:
    """개별 세션 상태 추적"""
    client: any  # curl_cffi Session
    label: str
    status: str = SessionHealth.HEALTHY
    cooldown_until: float = 0.0  # 쿨다운 종료 시간 (timestamp)
    block_count: int = 0  # 연속 차단 횟수
    success_count: int = 0  # 연속 성공 횟수
    total_requests: int = 0
    total_blocks: int = 0
    last_request_time: float = 0.0
    proxy_type: str = "datacenter"  # "decodo" 또는 "datacenter" (하이브리드 지원)
    is_sticky: bool = False  # Sticky 프록시 여부 (동일 포트=동일 IP)

    @property
    def is_decodo(self) -> bool:
        """Decodo(Residential) 프록시인지"""
        return self.proxy_type.lower() == "decodo"

    @property
    def cooldown_duration(self) -> float:
        """프록시 타입별 쿨다운 시간 (고속화)
        - Sticky: 3초 (헤더 다양화로 보완)
        - Rotating/Decodo: 1초 (매 요청 새 IP)
        - Datacenter: 30초 (쿨다운 축소)
        """
        if self.is_sticky:
            return 3.0  # Sticky: IP당 3초 쿨다운 (헤더 다양화로 보완)
        return 1.0 if self.is_decodo else 30.0

    def is_available(self) -> bool:
        """사용 가능한 상태인지"""
        if self.status == SessionHealth.HEALTHY:
            return True
        if self.status == SessionHealth.COOLING_DOWN:
            # 쿨다운 끝났으면 복구
            if time_module.time() >= self.cooldown_until:
                self.status = SessionHealth.HEALTHY
                self.block_count = 0
                return True
        return False

    def mark_success(self):
        """요청 성공 시 호출"""
        self.success_count += 1
        self.block_count = 0  # 성공하면 차단 카운트 리셋
        self.total_requests += 1
        self.last_request_time = time_module.time()
        # 쿨다운 중이었다면 복구
        if self.status == SessionHealth.COOLING_DOWN:
            self.status = SessionHealth.HEALTHY

    def mark_blocked(self, cooldown_seconds: float = 30.0):
        """차단 감지 시 호출"""
        self.block_count += 1
        self.success_count = 0
        self.total_blocks += 1
        self.total_requests += 1
        self.last_request_time = time_module.time()

        if self.is_sticky:
            # Sticky: StealthEngine이 IP 쿨다운 관리 → 세션 쿨다운은 짧게
            actual_cooldown = min(10.0 * self.block_count, 30.0)
        else:
            actual_cooldown = min(cooldown_seconds * self.block_count, 120.0)
        self.cooldown_until = time_module.time() + actual_cooldown
        self.status = SessionHealth.COOLING_DOWN
        return actual_cooldown

    def mark_rate_limited(self):
        """429 Rate Limit 시 호출 (연속 429시 쿨다운 증가)"""
        self.block_count += 1
        self.total_requests += 1
        self.last_request_time = time_module.time()
        if self.is_sticky:
            # Sticky: StealthEngine이 IP 쿨다운 관리 → 세션 쿨다운은 짧게
            cooldown = min(10.0 * self.block_count, 30.0)
        else:
            cooldown = min(30.0 * self.block_count, 180.0)
        self.cooldown_until = time_module.time() + cooldown
        self.status = SessionHealth.COOLING_DOWN
        return cooldown


class StealthEngine:
    """프록시 타입별 스텔스 엔진 - 네이버 429 우회

    [Decodo (Residential) 모드]
    - 빠른 병렬 처리 (5-10 workers)
    - 짧은 딜레이 (0.1-0.3초)
    - Decodo가 자동 IP 로테이션 처리
    - 429 거의 없음

    [Datacenter IP 모드]
    - 순차 처리 (1 worker)
    - IP당 60초 쿨다운
    - 불량 IP 자동 제외
    """

    # 불량 IP 영구 제외 임계값
    PERMANENT_BLOCK_THRESHOLD = 5  # Datacenter: 5회 차단 시 영구 제외
    PERMANENT_BLOCK_THRESHOLD_STICKY = 20  # Sticky: 20회 (IP 고정이라 쉽게 제외 불가)

    # 슬롯별 고유 브라우저 프로필 (10개 슬롯 = 10개 다른 환경)
    BROWSER_PROFILES = [
        # 0: Chrome 131 Windows 10
        {
            "impersonate": "chrome131",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Not A(Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_platform": '"Windows"',
            "accept_lang": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "platform": "Win32",
        },
        # 1: Chrome 124 Mac
        {
            "impersonate": "chrome124",
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_platform": '"macOS"',
            "accept_lang": "ko-KR,ko;q=0.9",
            "platform": "MacIntel",
        },
        # 2: Chrome 131 Android (Samsung Galaxy S24)
        {
            "impersonate": "chrome131_android",
            "ua": "Mozilla/5.0 (Linux; Android 15; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "sec_ch_ua": '"Not A(Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"',
            "sec_ch_ua_mobile": "?1",
            "sec_ch_ua_platform": '"Android"',
            "accept_lang": "ko-KR,ko;q=0.9",
            "platform": "Linux armv8l",
        },
        # 3: Safari 18.4 iPhone 15
        {
            "impersonate": "safari184_ios",
            "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
            "sec_ch_ua": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_platform": None,
            "accept_lang": "ko-KR,ko;q=0.9",
            "platform": "iPhone",
        },
        # 4: Safari 18.0 iPhone (네이버 앱 iOS)
        {
            "impersonate": "safari180_ios",
            "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NAVER(inapp; search; 1260; 12.8.0; 14PRO)",
            "sec_ch_ua": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_platform": None,
            "accept_lang": "ko-KR,ko;q=0.9",
            "platform": "iPhone",
        },
        # 5: Chrome 99 Android (네이버 앱 Android - 구버전)
        {
            "impersonate": "chrome99_android",
            "ua": "Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36 NAVER(inapp; search; 1260; 12.8.0)",
            "sec_ch_ua": '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
            "sec_ch_ua_mobile": "?1",
            "sec_ch_ua_platform": '"Android"',
            "accept_lang": "ko-KR,ko;q=0.9",
            "platform": "Linux armv8l",
        },
        # 6: Edge 101 Windows 11
        {
            "impersonate": "edge101",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.53",
            "sec_ch_ua": '" Not A;Brand";v="99", "Microsoft Edge";v="101", "Chromium";v="101"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_platform": '"Windows"',
            "accept_lang": "ko-KR,ko;q=0.9,en;q=0.8",
            "platform": "Win32",
        },
        # 7: Chrome 136 Android (Galaxy Tab S9 - 최신)
        {
            "impersonate": "chrome136",
            "ua": "Mozilla/5.0 (Linux; Android 15; SM-X916B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_platform": '"Android"',
            "accept_lang": "ko-KR,ko;q=0.9",
            "platform": "Linux aarch64",
        },
        # 8: Safari 18.0 macOS (Safari Desktop)
        {
            "impersonate": "safari180",
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
            "sec_ch_ua": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_platform": None,
            "accept_lang": "ko-KR,ko;q=0.9",
            "platform": "MacIntel",
        },
        # 9: Firefox 133 Windows
        {
            "impersonate": "firefox133",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "sec_ch_ua": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_platform": None,
            "accept_lang": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "platform": "Win32",
        },
        # 10: Chrome 120 Linux
        {
            "impersonate": "chrome120",
            "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_platform": '"Linux"',
            "accept_lang": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "platform": "Linux x86_64",
        },
        # 11: Chrome 123 Windows (다른 Chrome 버전)
        {
            "impersonate": "chrome123",
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_platform": '"Windows"',
            "accept_lang": "ko-KR,ko;q=0.9,en;q=0.8",
            "platform": "Win32",
        },
    ]

    # === 컴포넌트 기반 프로필 생성 시스템 (세션별 고유 조합) ===

    # impersonate별 UA 변형 (장치 모델, OS 버전, 빌드번호)
    UA_VARIANTS = {
        "chrome131": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.86 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.109 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.140 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.205 Safari/537.36",
        ],
        "chrome124": [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.60 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.155 Safari/537.36",
        ],
        "chrome131_android": [
            "Mozilla/5.0 (Linux; Android 15; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 15; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 15; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; SM-A556B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; SM-F731N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; Pixel 7a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        ],
        "safari184_ios": [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0.1 Mobile/15E148 Safari/604.1",
        ],
        "safari180_ios": [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NAVER(inapp; search; 1260; 12.8.0; 14PRO)",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NAVER(inapp; search; 1260; 12.8.0; 15PROMAX)",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NAVER(inapp; search; 1250; 12.7.0; 14PRO)",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NAVER(inapp; search; 1260; 12.8.0; 15)",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 NAVER(inapp; search; 1240; 12.6.0; 13PRO)",
        ],
        "chrome99_android": [
            "Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36 NAVER(inapp; search; 1260; 12.8.0)",
            "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36 NAVER(inapp; search; 1260; 12.8.0)",
            "Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36 NAVER(inapp; search; 1250; 12.7.0)",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36 NAVER(inapp; search; 1260; 12.8.0)",
            "Mozilla/5.0 (Linux; Android 13; SM-A346B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.88 Mobile Safari/537.36 NAVER(inapp; search; 1240; 12.6.0)",
        ],
        "edge101": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.53",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36 Edg/101.0.1210.47",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36 Edg/101.0.1210.39",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32",
        ],
        "chrome136": [
            "Mozilla/5.0 (Linux; Android 15; SM-X916B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 15; SM-X810B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; SM-X710B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 15; SM-T736B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; Pixel Tablet) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        ],
        "safari180": [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        ],
        "firefox133": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0.2",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0.3",
        ],
        "chrome120": [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.109 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.129 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.199 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.216 Safari/537.36",
        ],
        "chrome123": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.58 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.86 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.105 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.124 Safari/537.36",
        ],
    }

    # sec-ch-ua 브랜드 순서 변형 (Chromium계 전용, Safari/Firefox는 None)
    SEC_CH_UA_VARIANTS = {
        "chrome131": [
            '"Not A(Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"',
            '"Chromium";v="131", "Not A(Brand";v="99", "Google Chrome";v="131"',
            '"Google Chrome";v="131", "Chromium";v="131", "Not A(Brand";v="99"',
        ],
        "chrome124": [
            '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            '"Google Chrome";v="124", "Chromium";v="124", "Not-A.Brand";v="99"',
            '"Not-A.Brand";v="99", "Google Chrome";v="124", "Chromium";v="124"',
        ],
        "chrome131_android": [
            '"Not A(Brand";v="99", "Google Chrome";v="131", "Chromium";v="131"',
            '"Chromium";v="131", "Google Chrome";v="131", "Not A(Brand";v="99"',
            '"Google Chrome";v="131", "Not A(Brand";v="99", "Chromium";v="131"',
        ],
        "chrome99_android": [
            '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
            '"Chromium";v="99", "Google Chrome";v="99", " Not A;Brand";v="99"',
        ],
        "edge101": [
            '" Not A;Brand";v="99", "Microsoft Edge";v="101", "Chromium";v="101"',
            '"Microsoft Edge";v="101", "Chromium";v="101", " Not A;Brand";v="99"',
            '"Chromium";v="101", " Not A;Brand";v="99", "Microsoft Edge";v="101"',
        ],
        "chrome136": [
            '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            '"Google Chrome";v="136", "Not.A/Brand";v="99", "Chromium";v="136"',
            '"Not.A/Brand";v="99", "Chromium";v="136", "Google Chrome";v="136"',
        ],
        "chrome120": [
            '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            '"Chromium";v="120", "Not_A Brand";v="8", "Google Chrome";v="120"',
            '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="8"',
        ],
        "chrome123": [
            '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            '"Chromium";v="123", "Google Chrome";v="123", "Not:A-Brand";v="8"',
            '"Not:A-Brand";v="8", "Chromium";v="123", "Google Chrome";v="123"',
        ],
    }

    # Accept-Language 변형
    LANG_VARIANTS = [
        "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "ko-KR,ko;q=0.9",
        "ko-KR,ko;q=0.9,en;q=0.8",
        "ko,ko-KR;q=0.9,en-US;q=0.8",
        "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
    ]

    # impersonate → 플랫폼 메타데이터 매핑
    PLATFORM_MAP = {
        "chrome131": {"platform": "Win32", "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"Windows"'},
        "chrome124": {"platform": "MacIntel", "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"macOS"'},
        "chrome131_android": {"platform": "Linux armv8l", "sec_ch_ua_mobile": "?1", "sec_ch_ua_platform": '"Android"'},
        "safari184_ios": {"platform": "iPhone", "sec_ch_ua_mobile": None, "sec_ch_ua_platform": None},
        "safari180_ios": {"platform": "iPhone", "sec_ch_ua_mobile": None, "sec_ch_ua_platform": None},
        "chrome99_android": {"platform": "Linux armv8l", "sec_ch_ua_mobile": "?1", "sec_ch_ua_platform": '"Android"'},
        "edge101": {"platform": "Win32", "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"Windows"'},
        "chrome136": {"platform": "Linux aarch64", "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"Android"'},
        "safari180": {"platform": "MacIntel", "sec_ch_ua_mobile": None, "sec_ch_ua_platform": None},
        "firefox133": {"platform": "Win32", "sec_ch_ua_mobile": None, "sec_ch_ua_platform": None},
        "chrome120": {"platform": "Linux x86_64", "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"Linux"'},
        "chrome123": {"platform": "Win32", "sec_ch_ua_mobile": "?0", "sec_ch_ua_platform": '"Windows"'},
    }

    # impersonate 키 리스트 (순서 고정)
    _IMPERSONATE_KEYS = list(UA_VARIANTS.keys())

    def __init__(self, proxy_count: int = 50, bad_ip_file: str = None, proxy_type: str = "decodo", user_slot: int = 0, is_rotating: bool = False, is_sticky: bool = False):
        self._lock = threading.Lock()
        self._proxy_count = proxy_count
        self._proxy_type = proxy_type  # "decodo" 또는 "datacenter"
        self._user_slot = user_slot  # 슬롯별 독립 프로필용
        self._is_rotating = is_rotating  # Rotating 세션 여부
        self._is_sticky = is_sticky  # Sticky 세션 여부

        # === 프록시 타입별 설정 ===
        if is_rotating:
            # Rotating 모드: 매 요청 새 IP → 쿨다운 불필요
            self._ip_cooldown = 0.0
            self._min_delay = 0.02
            self._max_delay = 0.08
            self._slot_extra_delay = 0
        elif is_sticky:
            # Sticky 모드: 동일 포트=동일 IP → IP당 쿨다운 필수!
            # 50개 IP, 3초 쿨다운 → 50/3 = 16.7 req/s (고속)
            # 250개 IP, 3초 쿨다운 → 250/3 = 83 req/s (초고속)
            self._ip_cooldown = 3.0   # IP당 3초 쿨다운 (헤더 다양화로 보완)
            self._min_delay = 0.05
            self._max_delay = 0.15
            self._slot_extra_delay = 0
        elif proxy_type == "decodo":
            # Decodo (구버전 호환): Sticky처럼 동작
            self._ip_cooldown = 3.0   # IP당 3초 쿨다운
            self._min_delay = 0.05
            self._max_delay = 0.15
            self._slot_extra_delay = 0
        else:
            # Datacenter: 쿨다운 축소 (헤더 다양화로 보완)
            self._ip_cooldown = 30.0  # IP당 30초 쿨다운
            self._min_delay = 0.1
            self._max_delay = 0.3

        self._proxy_last_used = {}  # {label: timestamp}
        self._proxy_block_count = {}  # {label: 연속 429 횟수}
        self._blocked_proxies = set()  # 일시 차단된 IP들
        self._proxy_use_order = []  # 라운드로빈 순서

        # === 불량 IP 영구 제외 시스템 (Datacenter 전용) ===
        self._proxy_total_blocks = {}  # {label: 총 차단 횟수 (세션 전체)}
        self._permanently_blocked = set()  # 영구 차단된 IP들
        self._bad_ip_file = bad_ip_file or "bad_ips.json"  # 불량 IP 저장 파일
        if proxy_type == "datacenter":
            self._load_bad_ips()  # Datacenter만 불량 IP 로드

        # 프록시별 상태 저장
        self._proxy_profiles = {}  # {label: profile_index} (레거시)
        self._generated_profiles = {}  # {label: profile_dict} (동적 생성 프로필)
        self._proxy_cookies = {}   # {label: {cookie_dict}}
        self._proxy_sessions = {}  # {label: session_id}
        self._proxy_request_count = {}  # {label: count}

        # 휴먼 타이밍 패턴
        self._timing_mode = proxy_type
        self._last_batch_end = 0
        self._batch_request_count = 0

        # 요청 히스토리 (패턴 감지 방지)
        self._request_timestamps = []

        # 통계
        self._total_requests = 0
        self._total_429 = 0

        # 모드별 초기화 메시지
        if is_sticky:
            print(f"[Stealth] [STICKY] Sticky 모드: {proxy_count}개 IP, IP당 {self._ip_cooldown:.0f}초 쿨다운")
        elif is_rotating:
            print(f"[Stealth] [ROTATING] Rotating 모드: {proxy_count}개 엔드포인트, 쿨다운 없음 (매 요청 새 IP)")
        elif proxy_type == "decodo":
            print(f"[Stealth] [DECODO] Residential 모드: {proxy_count}개 엔드포인트, IP당 {self._ip_cooldown:.0f}초 쿨다운")
        else:
            # Datacenter 모드
            if self._permanently_blocked:
                print(f"[Stealth] [!] 이전 불량 IP {len(self._permanently_blocked)}개 제외됨")
            available = proxy_count - len(self._permanently_blocked)
            print(f"[Stealth] [DC] Datacenter IP 모드: {available}/{proxy_count}개 IP 사용 가능, IP당 {self._ip_cooldown:.0f}초 쿨다운")

    def _get_proxy_hash(self, label: str) -> int:
        """프록시 라벨을 일관된 해시값으로 변환"""
        return int(hashlib.md5(label.encode()).hexdigest()[:8], 16)

    def generate_unique_profile(self, session_index: int) -> dict:
        """세션별 고유 프로필 생성 (impersonate × UA × 언어 × sec-ch-ua 조합)

        12 impersonate × ~5 UA × 5 언어 × ~3 sec-ch-ua = 500+ 고유 조합
        동일 TLS 핑거프린트라도 UA/헤더가 달라 서로 다른 사용자처럼 보임
        """
        keys = self._IMPERSONATE_KEYS
        num_types = len(keys)

        # 1. impersonate 타입 선택 (라운드로빈)
        imp_type = keys[session_index % num_types]

        # 2. UA 변형 선택 (세션 인덱스로 분산)
        ua_list = self.UA_VARIANTS[imp_type]
        ua_idx = (session_index // num_types) % len(ua_list)
        ua = ua_list[ua_idx]

        # 3. Accept-Language 변형 선택
        lang_idx = (session_index // (num_types * max(len(v) for v in self.UA_VARIANTS.values()))) % len(self.LANG_VARIANTS)
        lang = self.LANG_VARIANTS[lang_idx]

        # 4. sec-ch-ua 변형 (Chromium계만, Safari/Firefox는 None)
        sec_variants = self.SEC_CH_UA_VARIANTS.get(imp_type)
        if sec_variants:
            sec_idx = (session_index // 3) % len(sec_variants)
            sec_ch_ua = sec_variants[sec_idx]
        else:
            sec_ch_ua = None

        # 5. 플랫폼 정보 (impersonate 타입에서 고정 결정)
        pinfo = self.PLATFORM_MAP[imp_type]

        return {
            "impersonate": imp_type,
            "ua": ua,
            "sec_ch_ua": sec_ch_ua,
            "sec_ch_ua_mobile": pinfo["sec_ch_ua_mobile"],
            "sec_ch_ua_platform": pinfo["sec_ch_ua_platform"],
            "accept_lang": lang,
            "platform": pinfo["platform"],
        }

    def get_browser_profile(self, proxy_label: str) -> dict:
        """세션별 브라우저 프로필 반환 (TLS 핑거프린트와 일치하는 헤더)"""
        with self._lock:
            # 1. 동적 생성 프로필 (새 시스템)
            if proxy_label in self._generated_profiles:
                return self._generated_profiles[proxy_label]

            # 2. 레거시 인덱스 기반 프로필 (하위 호환)
            if proxy_label in self._proxy_profiles:
                return self.BROWSER_PROFILES[self._proxy_profiles[proxy_label]]

            # 3. Rotating 모드: 해시 기반 동적 프로필 생성
            if self._is_rotating:
                h = self._get_proxy_hash(proxy_label)
                profile = self.generate_unique_profile(h)
                self._generated_profiles[proxy_label] = profile
                return profile

            # 4. 슬롯 기반 (Sticky/기타): 해시 기반 동적 프로필
            h = self._get_proxy_hash(proxy_label)
            profile = self.generate_unique_profile(h + self._user_slot * 1000)
            self._generated_profiles[proxy_label] = profile
            return profile

    def generate_naver_cookies(self, proxy_label: str) -> Dict[str, str]:
        """슬롯별 독립 쿠키 시뮬레이션 - NNB, NACT 등 생성"""
        with self._lock:
            # 슬롯 기반 쿠키 키 (슬롯별로 독립된 쿠키)
            cookie_key = f"slot_{self._user_slot}" if self._user_slot > 0 else proxy_label

            if cookie_key not in self._proxy_cookies:
                # 슬롯 기반 해시 (슬롯별 고유 쿠키)
                if self._user_slot > 0:
                    seed_hash = self._user_slot * 12345
                else:
                    seed_hash = self._get_proxy_hash(proxy_label)

                # NNB: 네이버 브라우저 ID (슬롯별 고유)
                nnb_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                random.seed(seed_hash)
                nnb = ''.join(random.choice(nnb_chars) for _ in range(11))

                # NACT: 액션 트래킹 (슬롯별 오프셋)
                nact = str(int(time_module.time() * 1000) - random.randint(0, 86400000) - self._user_slot * 3600000)

                # NV_WETR_LOCATION_RGN_M: 위치 (슬롯별 다른 지역)
                location_codes = ["09140104", "09140105", "09140106", "11110101", "11110102",
                                  "11140101", "11140102", "26110101", "26110102", "28110101"]
                random.seed(seed_hash + 1)
                location = location_codes[self._user_slot % len(location_codes)] if self._user_slot > 0 else random.choice(location_codes)

                self._proxy_cookies[cookie_key] = {
                    "NNB": nnb,
                    "NACT": nact,
                    "NV_WETR_LOCATION_RGN_M": location,
                    "NV_WETR_LAST_ACCESS_RGN_M": location,
                }

                random.seed()  # 시드 리셋

            return self._proxy_cookies[cookie_key].copy()

    def _load_bad_ips(self):
        """저장된 불량 IP 목록 로드"""
        import os
        try:
            if os.path.exists(self._bad_ip_file):
                with open(self._bad_ip_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # IP 주소만 저장 (라벨에서 IP 추출)
                    bad_ips = data.get("bad_ips", [])
                    self._permanently_blocked = set(bad_ips)
                    self._proxy_total_blocks = data.get("block_counts", {})
        except Exception as e:
            print(f"[Stealth] 불량 IP 파일 로드 실패: {e}")
            self._permanently_blocked = set()
            self._proxy_total_blocks = {}

    def _save_bad_ips(self):
        """불량 IP 목록 파일로 저장"""
        try:
            data = {
                "bad_ips": list(self._permanently_blocked),
                "block_counts": self._proxy_total_blocks,
                "saved_at": time_module.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self._bad_ip_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Stealth] 불량 IP 저장 실패: {e}")

    def is_permanently_blocked(self, label: str) -> bool:
        """IP가 영구 차단 상태인지 확인"""
        with self._lock:
            # 라벨에서 IP 추출 (IP1(xxx.xxx.xxx.xxx) → xxx.xxx.xxx.xxx)
            ip = self._extract_ip_from_label(label)
            return ip in self._permanently_blocked or label in self._permanently_blocked

    def _extract_ip_from_label(self, label: str) -> str:
        """라벨에서 IP 주소 추출"""
        # IP1(xxx.xxx.xxx.xxx) → xxx.xxx.xxx.xxx
        import re
        match = re.search(r'\(([0-9.]+)\)', label)
        if match:
            return match.group(1)
        return label

    def generate_human_delay(self) -> float:
        """휴먼 패턴 딜레이 생성 (2026-01-27 429 분석 기반 최적화)

        [핵심 원리]
        - 429 분석 결과: 프록시 로테이션이 핵심 (딜레이는 부가적)
        - 로테이션이 보장되면 딜레이는 최소화 가능
        - 여전히 약간의 랜덤성 유지 (패턴 감지 회피)
        """
        # 가우시안 분포: 중앙값 기준으로 자연스럽게 분포
        mean = (self._min_delay + self._max_delay) / 2
        std_dev = (self._max_delay - self._min_delay) / 4
        base_delay = max(self._min_delay, random.gauss(mean, std_dev))

        # 랜덤 휴식 (빈도 낮춤 - 로테이션이 메인)
        roll = random.random()
        if roll < 0.02:  # 2% 확률: 긴 휴식 (3->2%)
            extra = random.uniform(2.0, 4.0)
        elif roll < 0.10:  # 8% 확률: 중간 휴식 (10->8%)
            extra = random.uniform(0.5, 1.0)
        else:
            extra = 0

        # 슬롯별 추가 딜레이 적용 (다중 인스턴스 분산)
        slot_delay = getattr(self, '_slot_extra_delay', 0)

        total_delay = base_delay + extra + slot_delay
        return min(total_delay, 5.0)  # 최대 5초로 축소 (10->5)

    def generate_batch_pause(self) -> float:
        """Datacenter IP 모드에서는 배치 휴식 불필요 (IP 쿨다운이 대신함)"""
        return 0

    def get_available_proxy(self, sessions: list) -> tuple:
        """쿨다운 지난 IP 중 가장 오래된 것 선택 (Sticky/Datacenter 공용)

        선택된 IP는 즉시 사용 기록됨 (race condition 방지)

        Returns:
            (session, wait_time) - 사용할 세션과 필요한 대기 시간
        """
        with self._lock:
            now = time_module.time()
            available = []
            min_wait = float('inf')
            earliest_session = None

            for session in sessions:
                if not session.is_available():
                    continue

                label = session.label
                ip = self._extract_ip_from_label(label)

                # 영구 차단된 IP 스킵
                if ip in self._permanently_blocked:
                    continue

                # 일시 차단된 IP 스킵
                if label in self._blocked_proxies:
                    continue

                last_used = self._proxy_last_used.get(label, 0)
                time_since_use = now - last_used

                if time_since_use >= self._ip_cooldown:
                    # 쿨다운 완료 - 사용 가능
                    available.append((last_used, session))
                else:
                    # 쿨다운 중 - 얼마나 기다려야 하는지
                    wait = self._ip_cooldown - time_since_use
                    if wait < min_wait:
                        min_wait = wait
                        earliest_session = session

            if available:
                # 가장 오래 쉰 IP 선택 (골고루 분산)
                available.sort(key=lambda x: x[0])
                selected = available[0][1]
                # 즉시 사용 기록 (다른 스레드가 같은 IP 선택 방지)
                self._proxy_last_used[selected.label] = time_module.time()
                self._total_requests += 1
                return (selected, 0)

            if earliest_session:
                # 모든 IP가 쿨다운 중 - 가장 빨리 사용 가능한 IP 대기
                # 선택 예약: 즉시 last_used 갱신 (다른 스레드 대기 유도)
                self._proxy_last_used[earliest_session.label] = time_module.time()
                self._total_requests += 1
                return (earliest_session, min_wait)

            return (None, 0)

    def mark_proxy_used(self, label: str):
        """프록시 사용 기록"""
        with self._lock:
            self._proxy_last_used[label] = time_module.time()
            self._total_requests += 1

    def mark_proxy_success(self, label: str):
        """프록시 성공 - 차단 카운트 리셋"""
        with self._lock:
            self._proxy_block_count[label] = 0
            # 차단 목록에서 제거 (복구)
            self._blocked_proxies.discard(label)

    def mark_proxy_429(self, label: str):
        """프록시 429 발생 - 즉시 추가 쿨다운 + 연속 실패 시 일시 차단"""
        with self._lock:
            self._total_429 += 1

            # Rotating 모드: 매 요청 새 IP이므로 영구 제외/일시 차단 의미 없음
            if self._is_rotating:
                return

            count = self._proxy_block_count.get(label, 0) + 1
            self._proxy_block_count[label] = count

            # 429 받은 IP는 즉시 추가 쿨다운 부여 (다른 스레드가 바로 재사용 못하게)
            # last_used를 미래 시점으로 설정 → get_available_proxy에서 쿨다운 미완료로 판단
            extra_cooldown = min(5.0 * count, 15.0)  # 1회: 5초, 2회: 10초, 3회: 15초 (고속화)
            self._proxy_last_used[label] = time_module.time() + extra_cooldown - self._ip_cooldown

            # 총 차단 횟수 증가 (세션 전체)
            ip = self._extract_ip_from_label(label)
            total_count = self._proxy_total_blocks.get(ip, 0) + 1
            self._proxy_total_blocks[ip] = total_count

            # 영구 차단 체크 - Sticky는 IP 고정이라 임계값 높게
            threshold = self.PERMANENT_BLOCK_THRESHOLD_STICKY if self._is_sticky else self.PERMANENT_BLOCK_THRESHOLD
            if total_count >= threshold:
                self._permanently_blocked.add(ip)
                self._blocked_proxies.add(label)
                print(f"[Stealth] [BAN] IP {label} 영구 제외! (총 {total_count}회 429 발생)")
                self._save_bad_ips()  # 파일로 저장
                return  # 영구 차단이면 일시 차단 로직 스킵

            if count >= 3:
                # 연속 3회 429 → 5분간 일시 차단
                self._blocked_proxies.add(label)
                print(f"[Stealth] [X] IP {label} 일시 차단 (연속 {count}회, 총 {total_count}회)")

                # 5분 후 자동 해제 스케줄 (영구 차단이 아닌 경우만)
                def unblock():
                    time_module.sleep(300)  # 5분
                    with self._lock:
                        # 영구 차단이 아닌 경우만 해제
                        if ip not in self._permanently_blocked:
                            self._blocked_proxies.discard(label)
                            self._proxy_block_count[label] = 0
                            print(f"[Stealth] [OK] IP {label} 일시 차단 해제")

                threading.Thread(target=unblock, daemon=True).start()
            else:
                # 연속 3회 미만이지만 총 횟수가 높으면 경고
                if total_count >= 3:
                    remaining = threshold - total_count
                    print(f"[Stealth] [!] IP {label} 429 발생 (총 {total_count}회, {remaining}회 더 발생 시 영구 제외)")

    def get_stats(self) -> dict:
        """통계 반환"""
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "total_429": self._total_429,
                "blocked_count": len(self._blocked_proxies),
                "permanently_blocked": len(self._permanently_blocked),
                "available_ips": self._proxy_count - len(self._permanently_blocked) - len(self._blocked_proxies),
                "bad_ips": list(self._permanently_blocked),  # 영구 차단된 IP 목록
            }

    def get_bad_ip_report(self) -> str:
        """불량 IP 리포트 생성"""
        with self._lock:
            if not self._permanently_blocked and not self._proxy_total_blocks:
                return "불량 IP 없음"

            lines = ["=== 불량 IP 리포트 ==="]

            # 영구 차단된 IP
            if self._permanently_blocked:
                lines.append(f"\n[BAN] 영구 제외된 IP ({len(self._permanently_blocked)}개):")
                for ip in sorted(self._permanently_blocked):
                    count = self._proxy_total_blocks.get(ip, 0)
                    lines.append(f"  - {ip} ({count}회 429)")

            # 주의가 필요한 IP (3회 이상)
            warning_ips = {
                ip: count for ip, count in self._proxy_total_blocks.items()
                if count >= 3 and ip not in self._permanently_blocked
            }
            if warning_ips:
                threshold = self.PERMANENT_BLOCK_THRESHOLD_STICKY if self._is_sticky else self.PERMANENT_BLOCK_THRESHOLD
                lines.append(f"\n[!] 주의 필요 IP ({len(warning_ips)}개):")
                for ip, count in sorted(warning_ips.items(), key=lambda x: -x[1]):
                    remaining = threshold - count
                    lines.append(f"  - {ip} ({count}회, {remaining}회 더 실패 시 영구 제외)")

            return "\n".join(lines)

    def clear_bad_ips(self):
        """불량 IP 목록 초기화 (모든 IP 다시 사용)"""
        with self._lock:
            self._permanently_blocked.clear()
            self._proxy_total_blocks.clear()
            self._blocked_proxies.clear()
            self._proxy_block_count.clear()
            self._save_bad_ips()
            print("[Stealth] [OK] 불량 IP 목록 초기화됨 - 모든 IP 사용 가능")

    def get_stealth_headers(self, proxy_label: str, is_api: bool = False) -> Dict[str, str]:
        """스텔스 헤더 생성 - 프록시별 일관된 핑거프린트

        Args:
            proxy_label: 프록시 식별자
            is_api: True면 API 요청용, False면 HTML 요청용
        """
        profile = self.get_browser_profile(proxy_label)

        headers = {
            "User-Agent": profile["ua"],
            "Accept-Language": profile["accept_lang"],
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
        }

        # Chrome 계열만 sec-ch-ua 헤더 추가
        if profile.get("sec_ch_ua"):
            headers["sec-ch-ua"] = profile["sec_ch_ua"]
            headers["sec-ch-ua-mobile"] = profile["sec_ch_ua_mobile"]
            headers["sec-ch-ua-platform"] = profile["sec_ch_ua_platform"]

        if is_api:
            # GraphQL API 요청용
            headers.update({
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://m.search.naver.com",
                "Referer": "https://m.search.naver.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
            })
        else:
            # HTML 요청용
            headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            })

        return headers

    def get_referer_chain(self, keyword: str) -> str:
        """Referer Chain 생성 - 실제 검색 흐름 시뮬레이션

        네이버 검색 흐름: 메인 → 검색창 입력 → 검색 결과
        """
        # 검색어를 URL 인코딩
        from urllib.parse import quote
        encoded_keyword = quote(keyword)

        # 랜덤하게 다양한 Referer 패턴
        referers = [
            f"https://m.search.naver.com/search.naver?query={encoded_keyword}",
            "https://m.naver.com/",
            f"https://search.naver.com/search.naver?query={encoded_keyword}",
            "https://www.naver.com/",
        ]

        return random.choice(referers)

    def should_reset_session(self, proxy_label: str) -> bool:
        """세션 리셋 필요 여부 - 너무 많은 요청 후 세션 갱신"""
        with self._lock:
            count = self._proxy_request_count.get(proxy_label, 0)
            self._proxy_request_count[proxy_label] = count + 1

            # 50~100개 요청마다 세션 리셋 권장
            if count > 0 and count % random.randint(50, 100) == 0:
                # 쿠키 갱신
                if proxy_label in self._proxy_cookies:
                    del self._proxy_cookies[proxy_label]
                return True

            return False

    def record_request(self):
        """요청 타임스탬프 기록 - 패턴 분석용"""
        with self._lock:
            now = time_module.time()
            self._request_timestamps.append(now)

            # 최근 60초만 유지
            cutoff = now - 60
            self._request_timestamps = [t for t in self._request_timestamps if t > cutoff]

    def get_request_rate(self) -> float:
        """최근 요청 속도 (req/sec)"""
        with self._lock:
            if len(self._request_timestamps) < 2:
                return 0

            elapsed = self._request_timestamps[-1] - self._request_timestamps[0]
            if elapsed <= 0:
                return 0

            return len(self._request_timestamps) / elapsed

    def apply_anti_pattern(self) -> float:
        """패턴 감지 방지 - 요청 속도가 너무 일정하면 변동 추가"""
        with self._lock:
            if len(self._request_timestamps) < 5:
                return 0

            # 최근 요청 간격 분석
            intervals = []
            for i in range(1, min(10, len(self._request_timestamps))):
                intervals.append(
                    self._request_timestamps[-i] - self._request_timestamps[-i-1]
                )

            if not intervals:
                return 0

            # 표준편차 계산 - 너무 일정하면 (std < 0.3) 랜덤 딜레이 추가
            avg = sum(intervals) / len(intervals)
            variance = sum((x - avg) ** 2 for x in intervals) / len(intervals)
            std = math.sqrt(variance)

            if std < 0.3:  # 너무 일정한 패턴
                extra_delay = random.uniform(0.5, 2.0)
                return extra_delay

            return 0


class SmartRateLimiter:
    """Datacenter IP용 속도 제한기

    핵심 원리:
    1. IP당 60초 쿨다운 - 같은 IP 재사용 간격 길게
    2. 100개 IP 라운드로빈 - 분당 100개 요청 가능
    3. 순차 처리 - 동시 요청 최소화
    """

    # 429 분석 결과 기반 상수 (2026-01-27 테스트)
    # 단일 프록시에서 ~11회 요청 후 429 발생 → 8회로 제한
    # Rotating 모드에서는 매 요청마다 새 IP이므로 제한 불필요
    MAX_REQUESTS_PER_PROXY = 8
    MAX_REQUESTS_PER_PROXY_ROTATING = 99999  # Rotating: 사실상 무제한

    def __init__(self, max_rps: float = 2.0, per_proxy_interval: float = 60.0, is_rotating: bool = False, is_sticky: bool = False):
        """
        Args:
            max_rps: 전체 초당 최대 요청 수 (Datacenter: 분당 IP 수)
            per_proxy_interval: 프록시당 최소 요청 간격 (Datacenter: 60초)
            is_rotating: Rotating 세션 여부 (True면 쿨다운 비활성화)
            is_sticky: Sticky 세션 여부 (True면 글로벌 쿨다운 30초)
        """
        self._lock = threading.Lock()
        self._is_rotating = is_rotating  # Rotating 모드: 매 요청 새 IP
        self._is_sticky = is_sticky  # Sticky 모드: 고정 IP

        # Rotating 모드도 전달된 값 그대로 사용 (SessionManager에서 설정)
        # 이전 버전 기준: max_rps=10.0, per_proxy_interval=0.5
        # (기존 코드가 강제로 20.0, 0.0으로 덮어쓰던 것이 429 에러 원인)

        # Datacenter IP 모드 - 속도보다 안정성
        self._max_rps = max_rps
        self._current_rps = max_rps
        self._min_rps = 0.5  # 최소 초당 0.5 요청
        self._tokens = max_rps  # 초기 토큰
        self._last_token_update = time_module.time()

        # 프록시별 상태 {label: {"last_use": time, "cooldown_until": time, "consecutive_429": int, "request_count": int}}
        self._proxy_states = {}
        self._per_proxy_interval = per_proxy_interval

        # 429 추적 (슬라이딩 윈도우)
        self._recent_429s = []  # [(timestamp, proxy_label), ...]
        self._recent_successes = []
        self._window_size = 30.0  # 30초 윈도우

        # 상태
        self._total_requests = 0
        self._total_429s = 0
        self._last_status_print = time_module.time()

    def _update_tokens(self):
        """토큰 리필 (내부 호출, lock 필요)"""
        now = time_module.time()
        elapsed = now - self._last_token_update
        self._tokens = min(self._current_rps * 2, self._tokens + elapsed * self._current_rps)  # 최대 2초분 버퍼
        self._last_token_update = now

    def acquire_token(self) -> float:
        """글로벌 토큰 획득 - 대기 시간 반환"""
        with self._lock:
            self._update_tokens()

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0

            # 토큰 부족 - 대기 시간 계산
            wait_time = (1.0 - self._tokens) / max(0.1, self._current_rps)
            wait_time = min(wait_time, 5.0)  # 최대 5초
            self._tokens = 0.0
            return wait_time

    def get_best_proxy(self, sessions: List['SessionState'], stealth_engine=None) -> Optional['SessionState']:
        """최적의 프록시 선택 - 가장 오래 쉰 프록시 우선 (하이브리드 모드 지원)

        Args:
            sessions: 세션 리스트
            stealth_engine: StealthEngine 인스턴스 (영구 차단 체크용)

        하이브리드 모드:
        - Decodo: 5초 간격 (빠른 재사용)
        - Datacenter: 60초 간격 (IP 쿨다운)
        """
        with self._lock:
            now = time_module.time()
            available = []

            for session in sessions:
                if not session.is_available():
                    continue

                # 영구 차단된 IP 스킵
                if stealth_engine and stealth_engine.is_permanently_blocked(session.label):
                    continue

                state = self._proxy_states.get(session.label, {
                    "last_use": 0,
                    "cooldown_until": 0,
                    "consecutive_429": 0,
                    "request_count": 0
                })

                # 쿨다운 중이면 스킵
                if state["cooldown_until"] > now:
                    continue

                # 하이브리드: 세션별 프록시 타입에 따른 최소 간격
                # Decodo: 5초, Datacenter: 60초 (SessionState.cooldown_duration 사용)
                base_interval = session.cooldown_duration
                min_interval = base_interval * (1 + state["consecutive_429"] * 0.5)
                if now - state["last_use"] < min_interval:
                    continue

                # 사용 가능 - (마지막 사용 시간, 세션) 저장
                # Decodo 우선: 더 빠른 세션을 우선 선택하도록 가중치 적용
                priority = state["last_use"]
                if session.is_decodo:
                    priority -= 1000  # Decodo 세션에 높은 우선순위
                available.append((priority, session))

            if not available:
                # 모두 쿨다운 중 - 가장 빨리 사용 가능한 것 찾기
                earliest_available = None
                earliest_time = float('inf')

                for session in sessions:
                    if not session.is_available():
                        continue

                    # 영구 차단된 IP 스킵
                    if stealth_engine and stealth_engine.is_permanently_blocked(session.label):
                        continue

                    state = self._proxy_states.get(session.label, {"last_use": 0, "cooldown_until": 0, "consecutive_429": 0})

                    # 하이브리드: 세션별 쿨다운 시간 사용
                    base_interval = session.cooldown_duration
                    min_interval = base_interval * (1 + state.get("consecutive_429", 0) * 0.5)
                    available_at = max(state["cooldown_until"], state["last_use"] + min_interval)

                    if available_at < earliest_time:
                        earliest_time = available_at
                        earliest_available = session

                if earliest_available:
                    wait_needed = max(0, earliest_time - now)
                    if wait_needed > 0 and wait_needed < 10:
                        return (earliest_available, wait_needed)  # (세션, 대기시간) 반환
                    elif wait_needed == 0:
                        return earliest_available
                return None

            # 가장 오래 쉰 프록시들 중 랜덤 선택 (상위 3개)
            available.sort(key=lambda x: x[0])  # 오래된 순
            candidates = [s for _, s in available[:min(3, len(available))]]
            return random.choice(candidates)

    def mark_proxy_used(self, label: str):
        """프록시 사용 마킹 + 요청 횟수 추적

        429 분석 결과: 단일 프록시에서 ~11회 요청 후 429 발생
        → 8회 요청 후 강제 로테이션으로 예방
        → Rotating 모드에서는 매 요청 새 IP이므로 쿨다운 불필요
        """
        with self._lock:
            now = time_module.time()
            if label not in self._proxy_states:
                self._proxy_states[label] = {"last_use": 0, "cooldown_until": 0, "consecutive_429": 0, "request_count": 0}

            state = self._proxy_states[label]
            state["last_use"] = now
            state["request_count"] = state.get("request_count", 0) + 1
            self._total_requests += 1

            # Rotating 모드에서는 쿨다운 건너뛰기 (매 요청 새 IP)
            if self._is_rotating:
                return

            # Sticky 모드: 요청 횟수 제한 도달 → 강제 쿨다운 (30초)
            if state["request_count"] >= self.MAX_REQUESTS_PER_PROXY:
                state["cooldown_until"] = now + 30.0  # 30초 쿨다운
                state["request_count"] = 0  # 카운트 리셋

    def report_429(self, label: str):
        """429 발생 보고 - 해당 프록시 쿨다운 + 글로벌 쿨다운 체크

        [글로벌 쿨다운 전략]
        - 30초 내 10회 이상 429 발생 → 60초 글로벌 쿨다운
        - 모든 프록시 쿨다운 후 점진적 복구
        - Rotating 모드: 프록시별 쿨다운 스킵, 글로벌 속도 조절만 적용
        """
        with self._lock:
            now = time_module.time()

            # 429 통계는 항상 기록
            self._total_429s += 1

            # 429 기록 (Rotating 모드에서도 글로벌 속도 조절용)
            self._recent_429s.append((now, label))

            # 오래된 기록 정리
            self._recent_429s = [(t, l) for t, l in self._recent_429s if now - t < self._window_size]

            # Rotating 모드: 프록시별 쿨다운 스킵 (매 요청 새 IP이므로)
            # 하지만 글로벌 속도 조절은 적용 (다중 인스턴스 시 필요)
            if not self._is_rotating:
                # 프록시별 처리 (Sticky/Datacenter 모드만)
                if label not in self._proxy_states:
                    self._proxy_states[label] = {"last_use": now, "cooldown_until": 0, "consecutive_429": 0, "request_count": 0}

                state = self._proxy_states[label]
                state["consecutive_429"] = state.get("consecutive_429", 0) + 1
                state["request_count"] = 0  # 429 발생 시 카운트 리셋

                # 연속 429에 따른 쿨다운 (지수 백오프)
                cooldown = min(60.0, 5.0 * (2 ** min(state["consecutive_429"] - 1, 4)))
                state["cooldown_until"] = now + cooldown

            # 글로벌 슬로우다운 (모든 모드에서 적용 - Sticky 포함)
            # 429가 다발적으로 발생하면 전체 RPS를 줄여야 함
            recent_429_count = len(self._recent_429s)
            unique_proxies_blocked = len(set(l for _, l in self._recent_429s))

            if self._is_rotating:
                # Rotating: 매번 새 IP이므로 글로벌 프록시 쿨다운은 불필요
                # 단, RPS 감소는 적용 (대역 수준 차단 방지)
                if recent_429_count >= 10 or unique_proxies_blocked >= 5:
                    old_rps = self._current_rps
                    self._current_rps = max(self._min_rps, self._current_rps * 0.3)
                    self._tokens = 0
                    self._recent_429s = []
                    print(f"[RateLimiter] [SLOWDOWN] Rotating 429 다발: {old_rps:.1f} → {self._current_rps:.1f} req/s")
                elif recent_429_count >= 5:
                    old_rps = self._current_rps
                    self._current_rps = max(self._min_rps, self._current_rps * 0.5)
                    print(f"[RateLimiter] [!] 429 증가({recent_429_count}회/30초) → {old_rps:.1f} → {self._current_rps:.1f} req/s")
                return

            # Sticky / Datacenter: 글로벌 슬로우다운 + 프록시 쿨다운
            # 글로벌 차단 감지: 30초 내 10회 이상 429, 또는 5개 이상 다른 프록시에서 429
            if recent_429_count >= 10 or unique_proxies_blocked >= 5:
                global_cooldown = 30.0 if self._is_sticky else 60.0
                old_rps = self._current_rps
                self._current_rps = max(self._min_rps, self._current_rps * 0.3)
                print(f"\n[RateLimiter] [GLOBAL SLOWDOWN] 429 다발 감지!")
                print(f"  - 최근 30초 내 429: {recent_429_count}회 ({unique_proxies_blocked}개 IP)")
                print(f"  - RPS: {old_rps:.1f} → {self._current_rps:.1f}, {global_cooldown:.0f}초 대기")

                for proxy_label in self._proxy_states:
                    self._proxy_states[proxy_label]["cooldown_until"] = now + global_cooldown
                    self._proxy_states[proxy_label]["consecutive_429"] = 0
                    self._proxy_states[proxy_label]["request_count"] = 0

                self._tokens = 0
                self._recent_429s = []

            elif recent_429_count >= 5:
                old_rps = self._current_rps
                self._current_rps = max(self._min_rps, self._current_rps * 0.5)
                print(f"[RateLimiter] [!] 429 증가({recent_429_count}회/30초) → {old_rps:.1f} → {self._current_rps:.1f} req/s")

    def report_success(self, label: str):
        """성공 보고 - 프록시 상태 개선 + 글로벌 속도 복구"""
        with self._lock:
            now = time_module.time()

            # 프록시 연속 429 카운트 리셋
            if label in self._proxy_states:
                self._proxy_states[label]["consecutive_429"] = 0

            # 성공 기록
            self._recent_successes.append(now)
            self._recent_successes = [t for t in self._recent_successes if now - t < self._window_size]

            # 429 기록 정리
            self._recent_429s = [(t, l) for t, l in self._recent_429s if now - t < self._window_size]

            # 최근 429 없고 성공이 많으면 속도 점진적 복구
            if len(self._recent_429s) == 0 and len(self._recent_successes) >= 10:
                if self._current_rps < self._max_rps:
                    self._current_rps = min(self._max_rps, self._current_rps * 1.1)
                    self._recent_successes = []  # 리셋

            # 상태 출력 (10초마다)
            if now - self._last_status_print > 10:
                self._print_status()
                self._last_status_print = now

    def _print_status(self):
        """현재 상태 출력"""
        if self._total_requests > 0:
            rate = self._total_429s / self._total_requests * 100
            print(f"[RateLimiter] 속도: {self._current_rps:.1f} req/s, 429율: {rate:.1f}% ({self._total_429s}/{self._total_requests})")

    def get_current_rps(self) -> float:
        """현재 요청 속도 반환"""
        return self._current_rps

    def get_global_cooldown_remaining(self) -> float:
        """글로벌 쿨다운 남은 시간 반환 (모든 프록시가 쿨다운 중일 때)"""
        # Rotating 모드에서는 쿨다운 없음
        if self._is_rotating:
            return 0.0

        with self._lock:
            if not self._proxy_states:
                return 0.0

            now = time_module.time()
            # 모든 프록시의 최소 cooldown_until 확인
            min_cooldown = float('inf')
            for state in self._proxy_states.values():
                cooldown_until = state.get("cooldown_until", 0)
                if cooldown_until > now:
                    min_cooldown = min(min_cooldown, cooldown_until)
                else:
                    # 사용 가능한 프록시가 있으면 0 반환
                    return 0.0

            if min_cooldown == float('inf'):
                return 0.0

            return max(0.0, min_cooldown - now)

    def wait_for_cooldown(self, max_wait: float = 60.0) -> bool:
        """글로벌 쿨다운 대기 (차단 복구용)

        Returns:
            True if waited and can retry, False if timeout
        """
        remaining = self.get_global_cooldown_remaining()
        if remaining <= 0:
            return True

        wait_time = min(remaining, max_wait)
        print(f"[RateLimiter] 글로벌 쿨다운 대기: {wait_time:.0f}초...")
        time_module.sleep(wait_time)
        return True


class SessionManager:
    """Datacenter IP 전용 세션 관리자

    핵심 원리:
    - IP당 60초 쿨다운 (같은 IP 재사용 간격)
    - 100개 IP 라운드로빈 (분당 ~100개 요청 가능)
    - 순차 처리 (동시 요청 1개)
    - 차단된 IP 자동 제외
    - Rotating 모드: 쿨다운 없이 고속 처리 (매 요청 새 IP)
    """

    def __init__(self, endpoint_count: int = 20, stealth_engine=None, proxy_type: str = "decodo", is_rotating: bool = False, is_sticky: bool = False, user_slot: int = 0, total_instances: int = 1):
        self._sessions: List[SessionState] = []
        self._lock = threading.Lock()
        # 슬롯별 라운드로빈 시작 오프셋 (각 슬롯이 다른 IP부터 시작)
        # 500개 프록시 기준: 슬롯1=0, 슬롯2=50, 슬롯3=100, ...
        slot_offset = (user_slot - 1) * (endpoint_count // 10) if user_slot > 0 else 0
        self._round_robin_idx = slot_offset
        self._endpoint_count = endpoint_count
        self._stealth_engine = stealth_engine  # StealthEngine 참조
        self._proxy_type = proxy_type
        self._is_rotating = is_rotating  # Rotating 세션 여부
        self._is_sticky = is_sticky  # Sticky 세션 여부
        self._user_slot = user_slot  # 사용자 슬롯 (다중 인스턴스 시 RPS 분할용)
        self._total_instances = max(1, total_instances)  # 총 인스턴스 수

        # === 프록시 타입별 설정 (이전 버전 기준 - 안정성 우선) ===
        if is_rotating:
            # Rotating 모드: 새 IP + 쿠키 클리어 + 다양한 TLS 핑거프린트
            per_proxy_interval = 0.3

            if user_slot > 0:
                max_global_rps = 18.0
                initial_rps = max(2.0, max_global_rps / self._total_instances)
                print(f"[SessionManager] [ROTATING] 슬롯 {user_slot}: RPS={initial_rps:.1f} (전체 {max_global_rps:.0f}/{self._total_instances}인스턴스)")
            else:
                initial_rps = 18.0
                print(f"[SessionManager] [ROTATING] 단독 모드: RPS={initial_rps}")

            self._recommended_batch_size = 20
            self._min_batch_size = 8
            self._max_batch_size = 35

        elif is_sticky:
            # Sticky 모드: IP당 5초 쿨다운 (StealthEngine에서 실제 쿨다운 관리)
            # RPS = 프록시수 / 쿨다운 (50개/5초=10 req/s, 250개/5초=50 req/s)
            per_proxy_interval = 5.0  # IP당 5초 쿨다운

            # RPS 계산: 프록시수 / 쿨다운초
            safe_rps = max(1.0, endpoint_count / 5.0)

            # 동적 RPS: 이론치의 50%만 사용 → IP당 최소 10초 간격 (쿨다운 2배 여유)
            # endpoint_count는 이미 인스턴스별 분배된 값 → 추가 분할 불필요
            STICKY_SAFETY_FACTOR = 0.5
            initial_rps = max(1.0, safe_rps * STICKY_SAFETY_FACTOR)

            if user_slot > 0:
                print(f"[SessionManager] [STICKY] 슬롯 {user_slot}: {endpoint_count}개 IP → RPS={initial_rps:.1f} (안전계수 {STICKY_SAFETY_FACTOR})")
            else:
                print(f"[SessionManager] [STICKY] 단독: {endpoint_count}개 IP → RPS={initial_rps:.1f} (IP당 {per_proxy_interval:.0f}초 쿨다운)")

            # 배치/워커를 RPS에 비례하여 동적 설정
            self._recommended_batch_size = max(5, min(30, round(initial_rps)))
            self._min_batch_size = 5
            self._max_batch_size = max(15, min(40, round(initial_rps * 1.5)))

        elif proxy_type == "decodo":
            # Decodo (구버전 호환): Sticky처럼 동작
            per_proxy_interval = 5.0
            initial_rps = 5.0
            self._recommended_batch_size = 10
            self._min_batch_size = 5
            self._max_batch_size = 20
            print(f"[SessionManager] [DECODO] Residential 모드: RPS={initial_rps}")

        else:
            # Datacenter: 보수적 설정
            per_proxy_interval = 60.0
            initial_rps = endpoint_count / 60.0
            self._recommended_batch_size = endpoint_count
            self._min_batch_size = 10
            self._max_batch_size = endpoint_count
            print(f"[SessionManager] [DC] Datacenter 모드: {endpoint_count}개 IP, IP당 60초 쿨다운")

        self._rate_limiter = SmartRateLimiter(max_rps=initial_rps, per_proxy_interval=per_proxy_interval, is_rotating=is_rotating, is_sticky=is_sticky)

        # 하위 호환성 (이전 버전 기준으로 더 보수적)
        self._global_delay = 0.1 if is_rotating else (0.5 if is_sticky else 0.8)
        self._recent_429_count = 0
        self._last_429_reset = time_module.time()

        # === 배치 설정 ===
        self._batch_429_count = 0
        self._batch_total_count = 0
        self._consecutive_good_batches = 0

        # === 모드별 설정 ===
        self._use_random_selection = (proxy_type == "decodo" or is_sticky)

    def report_429(self, session_label: str = ""):
        """429 발생 보고 → SmartRateLimiter에 위임"""
        with self._lock:
            self._batch_429_count += 1
            self._recent_429_count += 1

        # SmartRateLimiter에 보고
        self._rate_limiter.report_429(session_label)

    def report_request(self, is_success: bool):
        """요청 결과 보고 (배치 통계용)"""
        with self._lock:
            self._batch_total_count += 1

    def start_new_batch(self):
        """새 배치 시작 - 이전 배치 통계 기반으로 배치 크기 조절"""
        with self._lock:
            if self._batch_total_count > 0:
                error_rate = self._batch_429_count / self._batch_total_count

                if error_rate > 0.10:  # 429가 10% 초과 (더 민감하게)
                    # 배치 크기 절반으로 줄이기
                    old_size = self._recommended_batch_size
                    self._recommended_batch_size = max(
                        self._min_batch_size,
                        self._recommended_batch_size // 2
                    )
                    self._consecutive_good_batches = 0
                    if old_size != self._recommended_batch_size:
                        print(f"[Rate] [!] 429 {error_rate:.0%} → 배치 {old_size} → {self._recommended_batch_size}")

                    # 딜레이 더 적극적으로 증가
                    self._global_delay = min(self._global_delay + 1.0, 8.0)

                elif error_rate < 0.05:  # 429가 5% 미만 (거의 없음)
                    self._consecutive_good_batches += 1

                    # 3번 연속 성공하면 배치 크기 복구
                    if self._consecutive_good_batches >= 3:
                        old_size = self._recommended_batch_size
                        self._recommended_batch_size = min(
                            self._max_batch_size,
                            self._recommended_batch_size + 2
                        )
                        if old_size != self._recommended_batch_size:
                            print(f"[Rate] [OK] 안정 → 배치 {old_size} → {self._recommended_batch_size}")
                        self._consecutive_good_batches = 0

                        # 딜레이 감소
                        self._global_delay = max(0.1, self._global_delay - 0.2)

            # 배치 통계 리셋
            self._batch_429_count = 0
            self._batch_total_count = 0

    def get_recommended_batch_size(self) -> int:
        """현재 권장 배치 크기 반환"""
        return self._recommended_batch_size

    def get_global_delay(self) -> float:
        """현재 글로벌 딜레이 반환 (RateLimiter 기반)"""
        # RateLimiter의 토큰 기반 대기 시간
        wait = self._rate_limiter.acquire_token()
        return max(0.1, wait)  # 최소 0.1초

    def reduce_delay(self, session_label: str = ""):
        """성공 시 속도 복구"""
        self._rate_limiter.report_success(session_label)

    def add_session(self, client, label: str, proxy_type: str = "datacenter"):
        """세션 추가 (하이브리드 모드 지원)

        Args:
            client: curl_cffi Session
            label: 세션 식별 라벨
            proxy_type: "decodo" 또는 "datacenter"
        """
        self._sessions.append(SessionState(
            client=client, label=label, proxy_type=proxy_type,
            is_sticky=self._is_sticky
        ))

    def set_stealth_engine(self, stealth_engine):
        """StealthEngine 설정 (영구 차단 체크용)"""
        self._stealth_engine = stealth_engine

    def get_healthy_session(self) -> Optional[SessionState]:
        """세션 반환 (모드별 분기)

        - Rotating: 단순 라운드로빈 (매 요청 새 IP → 쿨다운 불필요)
        - Sticky: IP 쿨다운 기반 선택 (동일 포트=동일 IP → 재사용 간격 필수)
        """
        if self._is_sticky and self._stealth_engine:
            # Sticky 모드: StealthEngine의 IP 쿨다운 기반 선택
            # SessionManager lock 밖에서 호출 (StealthEngine은 자체 lock 사용)
            with self._lock:
                sessions_copy = list(self._sessions)
            if not sessions_copy:
                return None
            session, wait_time = self._stealth_engine.get_available_proxy(sessions_copy)
            if session is None:
                return None
            if wait_time > 0:
                # 쿨다운 대기 (최대 5초)
                time_module.sleep(min(wait_time, 5.0))
            return session

        # Rotating/기타: 단순 라운드로빈
        with self._lock:
            if not self._sessions:
                return None
            session = self._sessions[self._round_robin_idx % len(self._sessions)]
            self._round_robin_idx += 1
            return session

    def get_alternative_session(self, exclude_label: str) -> Optional[SessionState]:
        """다른 세션으로 즉시 재시도용"""
        if self._is_sticky and self._stealth_engine:
            # Sticky: 쿨다운 기반 선택 (exclude_label 제외)
            with self._lock:
                sessions_copy = [s for s in self._sessions if s.label != exclude_label]
            if not sessions_copy:
                return None
            session, wait_time = self._stealth_engine.get_available_proxy(sessions_copy)
            if session is None:
                return None
            if wait_time > 0:
                time_module.sleep(min(wait_time, 5.0))
            return session

        # Rotating/기타: 라운드로빈 계속
        with self._lock:
            if not self._sessions:
                return None
            session = self._sessions[self._round_robin_idx % len(self._sessions)]
            self._round_robin_idx += 1
            return session

    @property
    def healthy_count(self) -> int:
        """현재 사용 가능한 세션 수"""
        return sum(1 for s in self._sessions if s.is_available())

    @property
    def total_count(self) -> int:
        """전체 세션 수"""
        return len(self._sessions)

    def get_stats(self) -> Dict:
        """통계 반환 (하이브리드 모드 지원)"""
        decodo_sessions = [s for s in self._sessions if s.is_decodo]
        datacenter_sessions = [s for s in self._sessions if not s.is_decodo]
        return {
            "total": len(self._sessions),
            "healthy": self.healthy_count,
            "cooling_down": sum(1 for s in self._sessions if s.status == SessionHealth.COOLING_DOWN),
            "total_requests": sum(s.total_requests for s in self._sessions),
            "total_blocks": sum(s.total_blocks for s in self._sessions),
            # 하이브리드 모드 통계
            "decodo_count": len(decodo_sessions),
            "datacenter_count": len(datacenter_sessions),
            "decodo_healthy": sum(1 for s in decodo_sessions if s.is_available()),
            "datacenter_healthy": sum(1 for s in datacenter_sessions if s.is_available()),
        }

    def close_all(self):
        """모든 세션 종료"""
        for session in self._sessions:
            try:
                session.client.close()
            except:
                pass
        self._sessions.clear()


# 주요 도시 좌표 (하위 호환성 - 실제로는 사용하지 않음)
CITY_COORDINATES = {
    "서울": {"x": "126.978388", "y": "37.566610"},
    "강남": {"x": "127.027926", "y": "37.497942"},
    "홍대": {"x": "126.924623", "y": "37.556725"},
    "부산": {"x": "129.075642", "y": "35.179554"},
    "대구": {"x": "128.601445", "y": "35.871435"},
    "인천": {"x": "126.705206", "y": "37.456256"},
    "광주": {"x": "126.851675", "y": "35.160068"},
    "대전": {"x": "127.384548", "y": "36.350412"},
    "울산": {"x": "129.311360", "y": "35.538377"},
    "제주": {"x": "126.531188", "y": "33.499621"},
    "수원": {"x": "127.009732", "y": "37.291060"},
    "성남": {"x": "127.126124", "y": "37.420024"},
    "분당": {"x": "127.108670", "y": "37.382790"},
    "남양주": {"x": "127.216599", "y": "37.636030"},
    "용인": {"x": "127.177530", "y": "37.241044"},
    "고양": {"x": "126.855368", "y": "37.658117"},
    "일산": {"x": "126.775086", "y": "37.658598"},
    "천안": {"x": "127.114211", "y": "36.815149"},
    "청주": {"x": "127.489853", "y": "36.642544"},
    "전주": {"x": "127.148933", "y": "35.824051"},
}


class RankCheckerGraphQL:
    """
    네이버 플레이스 순위 체크 - GraphQL API 버전 (curl_cffi 기반)

    - GraphQL API로 순위 조회
    - 검색 HTML에서 queryType으로 지도 형태 판단
    - 두 요청을 병렬로 처리하여 속도 최적화
    """

    GRAPHQL_URL = "https://nx-api.place.naver.com/graphql"
    SEARCH_URL = "https://m.search.naver.com/search.naver"

    USER_AGENTS = [
        # iOS
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        # Android
        "Mozilla/5.0 (Linux; Android 15; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        # Naver App
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile NAVER(inapp; search; 1250; 12.7.0)",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36 NAVER(inapp; search; 1200; 12.5.0)",
    ]

    # queryType → 지도형태 매핑
    QUERY_TYPE_MAP = {
        "restaurant": "신지도",
        "hospital": "신지도",
        "hairshop": "신지도",
        "cafe": "신지도",
        "nailshop": "신지도",
        "bar": "신지도",
        # null/없음 → 구지도
    }

    # GraphQL 쿼리 - nxPlaces (모든 업종 지원, 지도형태 추출 가능)
    PLACE_LIST_QUERY = """
        query getAdditionalPlaces($input: PlacesInput) {
            businesses: nxPlaces(input: $input) {
                total
                items {
                    id
                    name
                    businessCategory
                    gdid
                }
            }
        }
    """

    # 쿼리 변형용 - 랜덤 필드 추가로 요청 패턴 다양화
    PLACE_LIST_QUERY_VARIANTS = [
        """
        query getAdditionalPlaces($input: PlacesInput) {
            businesses: nxPlaces(input: $input) {
                total
                items {
                    id
                    name
                    businessCategory
                    gdid
                }
            }
        }
        """,
        """
        query getAdditionalPlaces($input: PlacesInput) {
            businesses: nxPlaces(input: $input) {
                items {
                    id
                    name
                    businessCategory
                    gdid
                }
                total
            }
        }
        """,
        """
        query getAdditionalPlaces($input: PlacesInput) {
            businesses: nxPlaces(input: $input) {
                total
                items {
                    name
                    id
                    gdid
                    businessCategory
                }
            }
        }
        """,
    ]

    # 쿠키 워밍용 검색어 (자연스러운 검색어)
    _WARMUP_KEYWORDS = [
        "맛집", "카페", "피부과", "치과", "미용실", "병원", "약국",
        "네일샵", "학원", "헬스장", "필라테스", "요가", "정형외과",
        "안과", "이비인후과", "한의원", "동물병원", "세탁소", "꽃집",
    ]

    def __init__(
        self,
        proxies: List[ProxyConfig] = None,
        max_workers: int = 3,  # 멀티 인스턴스 안정성 위해 3으로 감소
        default_coords: Dict[str, str] = None,  # 하위 호환성 (무시됨)
        debug: bool = False,
        use_own_ip: bool = True,  # 내 IP 사용 여부
        user_slot: int = 0,  # 사용자 슬롯 (0=전체, 1~10=분할 슬롯)
        total_instances: int = 1,  # 총 실행 인스턴스 수 (프록시 분배용)
        proxy_type: str = "decodo",  # "decodo" 또는 "datacenter"
    ):
        """
        Args:
            proxies: 프록시 설정 리스트 (선택) - IP:Port 형식
            max_workers: 최대 동시 워커 수
            default_coords: 좌표 (무시됨 - 하위 호환성)
            debug: 디버그 모드
            use_own_ip: 내 IP 사용 여부 (False면 프록시만 사용)
            user_slot: 사용자 슬롯
                       0=전체 프록시 사용 (단독 실행)
                       1~10=프록시를 10등분하여 해당 슬롯만 사용 (다중 인스턴스)
            total_instances: 총 실행 인스턴스 수 (프록시를 이 수로 나눠 사용)
            proxy_type: 프록시 타입 ("decodo"=Residential, "datacenter"=고정IP)
        """
        self.max_workers = max_workers
        self.default_coords = default_coords  # 무시됨
        self.debug = debug
        self.use_own_ip = use_own_ip
        self.user_slot = user_slot
        self.total_instances = max(1, total_instances)  # 총 실행 인스턴스 수
        self.proxy_type = proxy_type  # 프록시 타입 저장

        # 프록시 슬롯 분할 로직
        all_proxies = proxies or []

        # 세션 타입 감지 (session_type 속성을 우선 확인 - is_rotating은 프로퍼티라 항상 존재)
        is_rotating_proxy = False
        is_sticky_proxy = False
        if all_proxies:
            first_proxy = all_proxies[0]
            # session_type을 먼저 체크 (is_rotating은 프로퍼티라 hasattr가 항상 True)
            if hasattr(first_proxy, 'session_type') and first_proxy.session_type:
                is_rotating_proxy = first_proxy.session_type == "rotating"
                is_sticky_proxy = first_proxy.session_type == "sticky"
            elif hasattr(first_proxy, 'is_rotating'):
                is_rotating_proxy = first_proxy.is_rotating

        if all_proxies:
            if is_rotating_proxy or is_sticky_proxy:
                # Rotating/Sticky 모드: 전체 프록시 공유 필수
                # - Rotating: 매 요청 새 IP라 분할 불필요
                # - Sticky: IP 고정이라 분할하면 IP 부족 → 429 폭탄
                self.proxies = list(all_proxies)
                mode_str = "ROTATING" if is_rotating_proxy else "STICKY"
                if user_slot > 0:
                    # 슬롯별 라운드로빈 시작점만 다르게 (IP 분산)
                    print(f"[프록시] [{mode_str}] 슬롯 {user_slot}: 전체 {len(self.proxies)}개 공유 (오프셋 분산)")
                else:
                    print(f"[프록시] [{mode_str}] 슬롯 0 (전체): {len(self.proxies)}개 IP")
            elif user_slot == 0:
                # DC 슬롯 0: 전체 프록시 사용 (단독 실행)
                self.proxies = list(all_proxies)
                print(f"[프록시] [DC] 슬롯 0 (전체): {len(self.proxies)}개 IP")
            else:
                # DC 슬롯 1~10: 프록시를 10등분하여 해당 슬롯만 사용
                total = len(all_proxies)
                slot_size = max(1, total // 10)  # 최소 1개
                start_idx = (user_slot - 1) * slot_size
                end_idx = start_idx + slot_size if user_slot < 10 else total
                self.proxies = list(all_proxies)[start_idx:end_idx]
                print(f"[프록시] [DC] 슬롯 {user_slot}/10: {len(self.proxies)}개 IP (전체 {total}개 중 {start_idx+1}~{end_idx}번)")

            if proxy_type == "datacenter":
                random.shuffle(self.proxies)  # Datacenter만 셔플
        else:
            self.proxies = []
            if user_slot > 0:
                print(f"[경고] 슬롯 {user_slot} 지정됨, 프록시 없음")

        # Rotating 모드 플래그 저장 (Sticky는 Rotating이 아님)
        self._is_rotating = is_rotating_proxy
        self._is_sticky = is_sticky_proxy

        # 클라이언트 풀 크기 계산 (인스턴스 수로 동적 분배)
        # Sticky: 전체 프록시 / 인스턴스 수 (예: 500개/2인스턴스 = 250개씩)
        if is_sticky_proxy:
            if user_slot > 0 and self.total_instances > 0:
                dynamic_pool = len(self.proxies) // self.total_instances
                self._client_pool_size = max(50, min(dynamic_pool, 250))  # 50~250 범위
                print(f"[프록시] 동적 풀: {len(self.proxies)}개 / {self.total_instances}인스턴스 = {self._client_pool_size}개")
            else:
                self._client_pool_size = min(100, len(self.proxies))
        else:
            self._client_pool_size = len(self.proxies)  # DC/Rotating은 전체

        # 실제 사용할 클라이언트 수 (풀 크기와 프록시 수 중 작은 값)
        self.endpoint_count = min(self._client_pool_size, len(self.proxies)) if self.proxies else 1

        # 스텔스 엔진 초기화 (추적 방지 + 불량 IP 관리)
        # user_slot을 전달하여 슬롯별 독립된 브라우저 프로필 사용
        self._stealth = StealthEngine(
            proxy_count=self.endpoint_count,
            proxy_type=proxy_type,
            user_slot=user_slot,
            is_rotating=self._is_rotating,
            is_sticky=self._is_sticky
        )

        # 세션 매니저 초기화 (스텔스 엔진 연결)
        self._session_manager = SessionManager(
            endpoint_count=max(self.endpoint_count, 10),
            stealth_engine=self._stealth,
            proxy_type=proxy_type,
            is_rotating=self._is_rotating,
            is_sticky=self._is_sticky,  # Sticky 모드
            user_slot=user_slot,  # 다중 인스턴스 시 RPS 분할
            total_instances=self.total_instances  # 총 인스턴스 수 (RPS 분배용)
        )
        self._clients: List = []
        self._client_labels: List[str] = []
        self._client_index = 0
        self._progress_callback: Optional[Callable] = None
        self._stop_flag = False

    @property
    def total_ips(self) -> int:
        """사용 가능한 총 IP 수 (내 IP + 프록시)"""
        own_ip_count = 1 if self.use_own_ip else 0
        return own_ip_count + len(self.proxies)

    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        self._progress_callback = callback

    def stop(self):
        """즉시 중단 - 현재 진행 중인 작업 취소"""
        self._stop_flag = True
        print("[RankChecker] [STOP] 중단 요청됨 - 즉시 중단합니다")

    def _interruptible_sleep(self, seconds: float, interval: float = 0.1) -> bool:
        """중단 가능한 sleep. _stop_flag 체크하며 대기. 중단 시 True 반환."""
        elapsed = 0.0
        while elapsed < seconds:
            if self._stop_flag:
                return True
            time_module.sleep(min(interval, seconds - elapsed))
            elapsed += interval
        return False

    def __enter__(self):
        self._init_clients()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_clients()

    async def __aenter__(self):
        self._init_clients()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._close_clients()

    def _init_clients(self):
        """여러 클라이언트 초기화 (내 IP + 프록시들)

        고정 IP 프록시 사용 (CSV에서 로드된 IP:Port 목록)
        SessionManager를 통한 스마트 세션 관리
        """
        if not _curl_cffi_available:
            raise ImportError("curl_cffi가 설치되지 않았습니다. pip install curl_cffi")

        self._clients = []
        self._client_labels = []

        # SessionManager는 __init__에서 이미 생성됨 (is_rotating 포함)

        # Chrome 임퍼소네이션 버전 (TLS 핑거프린트 완벽 모방)
        _DEFAULT_IMPERSONATE = "chrome131"
        _generate_profile = self._stealth.generate_unique_profile

        # 1. 내 IP용 클라이언트 (프록시 없음) - use_own_ip가 True일 때만
        if self.use_own_ip:
            direct_client = CurlSession(
                impersonate=_DEFAULT_IMPERSONATE,
                timeout=12.0,
                allow_redirects=True,
            )
            self._clients.append(direct_client)
            self._client_labels.append("내 IP")
            self._session_manager.add_session(direct_client, "내 IP", proxy_type="datacenter")
            print(f"[IP] 내 IP 추가됨")

        # 2. 프록시별 클라이언트 (CPU/메모리 절약: 풀 크기만큼만 생성)
        # 500개 프록시 → 50개 클라이언트만 생성 (슬롯별로 다른 범위 사용)
        decodo_count = 0
        datacenter_count = 0

        # 클라이언트 풀 크기 제한 (메모리/CPU 절약)
        pool_size = getattr(self, '_client_pool_size', len(self.proxies))

        # Rotating 모드: 프록시가 1개(단일 포트)면 세션을 복제하여 멀티스레드 안전하게
        # curl_cffi Session은 스레드 안전하지 않으므로, 워커 수 이상의 세션 필요
        if self._is_rotating and len(self.proxies) <= 1 and self.proxies:
            _ROTATING_SESSION_COUNT = 20  # 워커 수보다 충분히 많게
            base_proxy = self.proxies[0]
            proxies_to_create = [base_proxy] * _ROTATING_SESSION_COUNT
            pool_size = _ROTATING_SESSION_COUNT
            print(f"[IP] Rotating 모드: 단일 프록시 → {_ROTATING_SESSION_COUNT}개 세션 복제 (스레드 안전)")
        elif self.user_slot > 0 and len(self.proxies) > pool_size:
            # 슬롯별로 다른 프록시 범위 사용 (429 방지)
            # 슬롯 1: 0~49, 슬롯 2: 50~99, ..., 슬롯 10: 450~499
            slot_offset = (self.user_slot - 1) * pool_size
            # 순환 처리 (프록시 수 초과 시)
            if slot_offset >= len(self.proxies):
                slot_offset = slot_offset % len(self.proxies)
            end_idx = min(slot_offset + pool_size, len(self.proxies))
            proxies_to_create = self.proxies[slot_offset:end_idx]
            # 부족하면 처음부터 채우기
            if len(proxies_to_create) < pool_size:
                remaining = pool_size - len(proxies_to_create)
                proxies_to_create.extend(self.proxies[:remaining])
            print(f"[IP] 슬롯 {self.user_slot}: 포트 {slot_offset+1}~{slot_offset+len(proxies_to_create)} 범위 사용")
        else:
            proxies_to_create = self.proxies[:pool_size]

        _is_rotating_single = self._is_rotating and len(self.proxies) <= 1

        def create_proxy_client(idx_proxy):
            """단일 프록시 클라이언트 생성 - 세션별 고유 브라우저 핑거프린트"""
            i, proxy = idx_proxy
            try:
                # 세션별 고유 프로필 동적 생성 (500+ 조합)
                profile = _generate_profile(i)
                impersonate_val = profile.get("impersonate", _DEFAULT_IMPERSONATE)

                proxy_client = CurlSession(
                    impersonate=impersonate_val,
                    timeout=12.0,
                    allow_redirects=True,
                    proxy=proxy.url,
                )
                p_type = proxy.proxy_type
                if _is_rotating_single:
                    # Rotating 단일 프록시: R1, R2, ... (같은 포트, 다른 세션)
                    label = f"R{i}({proxy.host}:{proxy.port})"
                elif proxy.is_decodo:
                    label = f"D{i}({proxy.host}:{proxy.port})"
                else:
                    label = f"DC{i}({proxy.host})"
                # 세션별 동적 프로필 반환 (헤더 생성 시 사용)
                return (i, proxy_client, label, p_type, proxy.is_decodo, None, profile)
            except Exception as e:
                return (i, None, None, None, None, f"{proxy.host}:{proxy.port} - {e}", None)

        # 병렬 클라이언트 생성 (제한된 수만)
        print(f"[IP] {len(proxies_to_create)}개 클라이언트 생성 중 (전체 {len(self.proxies)}개 중)...")
        with ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(create_proxy_client, enumerate(proxies_to_create, 1)))

        # 결과 정리 (순서 유지)
        for i, proxy_client, label, p_type, is_decodo, error, prof_data in sorted(results, key=lambda x: x[0]):
            if error:
                print(f"[IP] 프록시{i} 실패: {error}")
                continue

            self._clients.append(proxy_client)
            self._client_labels.append(label)
            self._session_manager.add_session(proxy_client, label, proxy_type=p_type)

            # 세션별 동적 프로필 매핑 저장 (헤더 생성 시 TLS와 일치시킴)
            if prof_data is not None:
                self._stealth._generated_profiles[label] = prof_data

            if is_decodo:
                decodo_count += 1
            else:
                datacenter_count += 1

            if self.debug:
                print(f"[IP] {label} ({p_type}) 추가됨")

        if self._session_manager.total_count == 0:
            raise RuntimeError("사용 가능한 IP가 없습니다. 프록시를 추가하거나 '내 IP 사용'을 활성화하세요.")

        # 하이브리드 모드 통계 출력
        print(f"[IP] 총 {self._session_manager.total_count}개 세션 (Decodo: {decodo_count}, Datacenter: {datacenter_count})")

        # Sticky 모드: 쿠키 워밍 (진짜 네이버 쿠키 획득)
        if self._is_sticky and decodo_count > 0:
            self._warm_sessions()

    def _warm_sessions(self):
        """Sticky 세션 쿠키 워밍 - 네이버 방문으로 진짜 쿠키 획득

        세션 생성 후 1회만 실행. 각 세션이 m.search.naver.com을 방문하여
        NNB, NACT 등 진짜 쿠키를 Set-Cookie로 받아 세션에 저장.
        이후 GraphQL 요청 시 이 쿠키가 자동 포함됨.
        """
        sessions = self._session_manager._sessions
        sticky_sessions = [s for s in sessions if s.is_sticky or s.is_decodo]

        if not sticky_sessions:
            return

        print(f"[CookieWarm] {len(sticky_sessions)}개 세션 쿠키 워밍 시작...")
        warmup_start = time_module.time()

        def warm_single(session_state):
            """단일 세션 워밍"""
            try:
                # 랜덤 검색어로 자연스러운 검색 시뮬레이션
                keyword = random.choice(self._WARMUP_KEYWORDS)
                profile = self._stealth.get_browser_profile(session_state.label)

                headers = {
                    "User-Agent": profile["ua"],
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": profile["accept_lang"],
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                }
                if profile.get("sec_ch_ua"):
                    headers["sec-ch-ua"] = profile["sec_ch_ua"]
                    headers["sec-ch-ua-mobile"] = profile["sec_ch_ua_mobile"]
                    headers["sec-ch-ua-platform"] = profile["sec_ch_ua_platform"]

                resp = session_state.client.get(
                    "https://m.search.naver.com/search.naver",
                    params={"query": keyword},
                    headers=headers,
                )
                if resp.status_code == 200:
                    return (session_state.label, True)
                else:
                    return (session_state.label, False)
            except Exception:
                return (session_state.label, False)

        # 병렬 워밍 (동시 30개 제한 - Decodo 게이트웨이 부하 방지)
        success = 0
        fail = 0
        with ThreadPoolExecutor(max_workers=30) as executor:
            results = list(executor.map(warm_single, sticky_sessions))

        for label, ok in results:
            if ok:
                success += 1
            else:
                fail += 1

        elapsed = time_module.time() - warmup_start
        print(f"[CookieWarm] 완료: {success}/{len(sticky_sessions)}개 성공 ({elapsed:.1f}초)")
        if fail > 0:
            print(f"[CookieWarm] {fail}개 실패 (무시 가능 - 본 요청 시 재시도)")

    def _close_clients(self):
        """모든 클라이언트 종료"""
        # 세션 매니저 종료
        self._session_manager.close_all()
        # 하위 호환성
        for client in self._clients:
            try:
                client.close()
            except:
                pass
        self._clients = []

        # 스텔스 엔진 통계 및 불량 IP 리포트 출력
        stealth_stats = self._stealth.get_stats()
        if stealth_stats["total_requests"] > 0:
            rate_429 = stealth_stats["total_429"] / stealth_stats["total_requests"] * 100
            print(f"[Stealth] 완료 - 총 {stealth_stats['total_requests']}개 요청, 429: {stealth_stats['total_429']}회 ({rate_429:.1f}%)")

            if stealth_stats["permanently_blocked"] > 0:
                print(f"[Stealth] [BAN] 영구 제외된 IP: {stealth_stats['permanently_blocked']}개")
                # 불량 IP 목록 출력
                for ip in stealth_stats["bad_ips"]:
                    print(f"  - {ip}")

        # 통계 출력
        stats = self._session_manager.get_stats()
        if stats["total_requests"] > 0:
            print(f"[SessionManager] 완료 - 총 {stats['total_requests']}개 요청, {stats['total_blocks']}개 차단 감지")

    def _get_next_client(self) -> Tuple:
        """다음 클라이언트 반환 (로테이션)

        Returns:
            (client, label) - 클라이언트와 식별 라벨
        """
        if not self._clients:
            raise RuntimeError("클라이언트가 초기화되지 않았습니다.")
        idx = self._client_index % len(self._clients)
        client = self._clients[idx]
        label = self._client_labels[idx] if idx < len(self._client_labels) else f"IP{idx}"
        self._client_index += 1
        return client, label

    # 하위 호환성을 위한 프로퍼티
    @property
    def _client(self):
        """기존 코드 호환용 - 첫 번째 클라이언트 반환"""
        if self._clients:
            return self._clients[0]
        return None

    def _get_headers(self, for_html: bool = False, proxy_label: str = "") -> Dict[str, str]:
        """스텔스 헤더 생성 (StealthEngine 사용)

        프록시별로 일관된 브라우저 핑거프린트 유지
        """
        # StealthEngine에서 프록시별 일관된 헤더 가져오기
        return self._stealth.get_stealth_headers(proxy_label, is_api=not for_html)

    def _apply_stealth_delay(self, proxy_label: str = ""):
        """스텔스 딜레이 적용

        Sticky 모드: Rate Limiter가 RPS 제한 (핵심 429 방지) + 소량 랜덤 지터
        기타 모드: Human-like 타이밍 + 패턴 방지
        """
        if self._is_sticky or self._is_rotating:
            # Rate Limiter 기반 딜레이 (RPS 실제 적용)
            rate_delay = self._session_manager.get_global_delay()
            if self._is_rotating:
                # Rotating: 다양한 브라우저 + 새 IP → 최소 지터 (고속)
                jitter = random.uniform(0.02, 0.08)
            else:
                # Sticky: 같은 IP 유지 → 짧은 지터 (헤더 다양화로 커버)
                jitter = random.uniform(0.1, 0.3)
            total_delay = max(rate_delay, jitter)
            self._stealth.record_request()
            if total_delay > 0:
                time_module.sleep(total_delay)
            return total_delay

        # Datacenter/기타: 풀 스텔스 적용
        delay = self._stealth.generate_human_delay()
        anti_pattern_delay = self._stealth.apply_anti_pattern()
        delay += anti_pattern_delay
        batch_pause = self._stealth.generate_batch_pause()
        delay += batch_pause
        self._stealth.record_request()

        if delay > 0:
            time_module.sleep(delay)

        return delay

    def _fetch_map_type(self, keyword: str, max_retries: int = 3) -> str:
        """검색 HTML에서 queryType을 추출하여 지도 형태 판단

        [2025-01 분석 결과]
        - queryType이 있음 (restaurant, hospital, hairshop 등) → 신지도
        - queryType이 null/없음 → 구지도
        - "지도" 키워드가 붙으면 queryType이 null이 됨

        [스마트 세션 관리]
        - 차단 시 즉시 다른 세션으로 재시도 (대기 없음)
        - 차단된 세션만 쿨다운, 나머지는 풀스피드 유지
        """
        last_session_label = None

        for attempt in range(max_retries):
            # 스마트 세션 선택
            if attempt > 0 and last_session_label:
                # 이전 시도가 실패했으면 다른 세션 선택
                session = self._session_manager.get_alternative_session(last_session_label)
                if not session:
                    session = self._session_manager.get_healthy_session()
            else:
                session = self._session_manager.get_healthy_session()

            if not session:
                return "신지도"  # 세션 없으면 기본값

            last_session_label = session.label

            try:
                # Datacenter IP: 짧은 딜레이만
                self._apply_stealth_delay(session.label)

                # 프록시 사용 마킹 (StealthEngine + RateLimiter)
                self._stealth.mark_proxy_used(session.label)
                self._session_manager._rate_limiter.mark_proxy_used(session.label)

                # 스텔스 헤더 (프록시별 일관된 핑거프린트)
                headers = self._get_headers(for_html=True, proxy_label=session.label)

                # 쿠키 처리 (모드별 분기)
                cookies = None
                if self._is_sticky:
                    # Sticky: 워밍된 진짜 쿠키 사용 (세션에 저장됨)
                    cookies = None
                elif self._is_rotating:
                    # Rotating: 쿠키 클리어 (추적 방지)
                    try:
                        session.client.cookies.clear()
                    except Exception:
                        pass
                    cookies = None
                else:
                    # Datacenter/기타: 합성 쿠키
                    cookies = self._stealth.generate_naver_cookies(session.label)

                response = session.client.get(
                    self.SEARCH_URL,
                    params={"query": keyword},
                    headers=headers,
                    cookies=cookies
                )

                # 403 차단 → IP 마킹 후 즉시 다른 IP로
                if response.status_code == 403:
                    session.mark_blocked()
                    self._stealth.mark_proxy_429(session.label)
                    print(f"[MapType] [BAN] 403 [{session.label}] → 다음 IP로")
                    continue

                # 429 Rate Limit → IP 마킹 후 즉시 다른 IP로
                if response.status_code == 429:
                    session.mark_rate_limited()
                    self._stealth.mark_proxy_429(session.label)
                    self._session_manager.report_429(session.label)
                    print(f"[MapType] [!] 429 [{session.label}] → 다음 IP로")
                    continue

                # 500+ 서버 에러 → 짧은 대기(지터 포함) 후 재시도
                if response.status_code >= 500:
                    if self.debug:
                        print(f"[MapType] [!] HTTP {response.status_code} [{session.label}]")
                    time_module.sleep(random.uniform(0.5, 1.0))
                    continue

                if response.status_code != 200:
                    return "신지도"

                # 성공!
                session.mark_success()
                self._stealth.mark_proxy_success(session.label)  # 성공 기록
                self._session_manager._rate_limiter.report_success(session.label)

                # 인코딩 처리
                try:
                    html = response.text
                except Exception:
                    html = response.content.decode('utf-8', errors='ignore')

                # queryType 추출
                match = re.search(r'"queryType"\s*:\s*"([^"]+)"', html)
                if match:
                    query_type = match.group(1)
                    return self.QUERY_TYPE_MAP.get(query_type, "신지도")

                return "구지도"

            except Exception as e:
                if self.debug:
                    print(f"[MapType] {keyword} 오류 [{session.label}]: {e}")
                continue

        return "신지도"

    def _fetch_map_type_direct(self, keyword: str) -> str:
        """내 IP로 직접 HTML 요청 (프록시 우회, Phase 2 전용)

        GraphQL과 다른 서버(m.search.naver.com)라서 rate limit 별도.
        공유 클라이언트 재사용으로 커넥션 효율 향상.
        """
        try:
            headers = {
                "User-Agent": random.choice(self.USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Connection": "keep-alive",
            }

            # 기존 내 IP 클라이언트가 있으면 재사용, 없으면 새로 생성
            if hasattr(self, '_direct_client') and self._direct_client:
                client = self._direct_client
                response = client.get(
                    self.SEARCH_URL,
                    params={"query": keyword},
                    headers=headers
                )
            else:
                # 공유 클라이언트 없으면 세션 매니저의 내 IP 세션 사용
                session = None
                for s in self._session_manager._sessions:
                    if s.label == "내 IP":
                        session = s
                        break
                
                if session:
                    response = session.client.get(
                        self.SEARCH_URL,
                        params={"query": keyword},
                        headers=headers
                    )
                else:
                    # 최후 수단: 임시 클라이언트 (Chrome TLS 핑거프린트)
                    with CurlSession(impersonate="chrome131", timeout=10.0, allow_redirects=True) as temp_client:
                        response = temp_client.get(
                            self.SEARCH_URL,
                            params={"query": keyword},
                            headers=headers
                        )

            if response.status_code != 200:
                return "신지도"

            html = response.text
            match = re.search(r'"queryType"\s*:\s*"([^"]+)"', html)
            if match:
                query_type = match.group(1)
                return self.QUERY_TYPE_MAP.get(query_type, "신지도")

            return "구지도"

        except Exception as e:
            if self.debug:
                print(f"[MapType Direct] {keyword} 오류: {e}")
            return "신지도"

    def _fetch_rank_from_graphql(
        self,
        keyword: str,
        target_place_id: str,
        max_rank: int,
        max_retries: int = 5  # 다중 인스턴스 안정성을 위해 5회로 증가
    ) -> Tuple[Optional[int], str, str, str, Optional[int]]:
        """GraphQL API에서 순위 조회 (스마트 세션 관리)

        Returns:
            (rank, status, place_name, business_category, total_count)

        [스마트 세션 관리]
        - 403 차단 시 즉시 다른 세션으로 재시도 (대기 없음!)
        - 429 Rate Limit은 짧은 쿨다운 (5초)
        - 차단된 세션만 쿨다운, 나머지는 풀스피드 유지
        """
        last_session_label = None

        for attempt in range(max_retries):
            if self._stop_flag:
                return None, "cancelled", "", "", None
            # 스마트 세션 선택
            if attempt > 0 and last_session_label:
                # 이전 시도가 실패했으면 다른 세션 선택 (즉시!)
                session = self._session_manager.get_alternative_session(last_session_label)
                if not session:
                    session = self._session_manager.get_healthy_session()
            else:
                session = self._session_manager.get_healthy_session()

            # 세션 없음 → 반복 대기 후 재시도 (다중 인스턴스에서 중요!)
            if not session:
                for wait_attempt in range(5):  # 최대 5번 × 0.15초 = 0.75초 대기
                    time_module.sleep(0.15)
                    session = self._session_manager.get_healthy_session()
                    if session:
                        break
                if not session:
                    if attempt < max_retries - 1:
                        continue  # 다음 메인 시도로
                    return None, "error", "", "No available session", None

            last_session_label = session.label

            try:
                # Datacenter IP: 짧은 딜레이만
                self._apply_stealth_delay(session.label)

                # 프록시 사용 마킹 (StealthEngine + RateLimiter)
                self._stealth.mark_proxy_used(session.label)
                self._session_manager._rate_limiter.mark_proxy_used(session.label)

                # 스텔스 헤더 (프록시별 일관된 핑거프린트)
                headers = self._get_headers(for_html=False, proxy_label=session.label)

                # Referer Chain (실제 검색 흐름 시뮬레이션)
                headers["Referer"] = self._stealth.get_referer_chain(keyword)

                # 쿠키 처리 (모드별 분기)
                cookies = None
                if self._is_sticky:
                    # Sticky: 워밍된 진짜 쿠키가 세션에 저장되어 있음 → 명시적 쿠키 불필요
                    cookies = None
                elif self._is_rotating:
                    # Rotating: 매 요청 새 IP → 쿠키 클리어 (추적 방지), 명시적 쿠키도 안 보냄
                    try:
                        session.client.cookies.clear()
                    except Exception:
                        pass
                    cookies = None
                else:
                    # Datacenter/기타: 기존 방식 (합성 쿠키)
                    cookies = self._stealth.generate_naver_cookies(session.label)

                # display 값 소폭 변형 (요청 패턴 다양화)
                display_val = max_rank + random.randint(0, 3)

                variables = {
                    "input": {
                        "query": keyword,
                        "display": display_val,
                        "start": 1
                    }
                }

                # 쿼리 변형 랜덤 선택 (필드 순서 다양화)
                query_variant = random.choice(self.PLACE_LIST_QUERY_VARIANTS)

                payload = {
                    "operationName": "getAdditionalPlaces",
                    "query": query_variant,
                    "variables": variables
                }

                response = session.client.post(
                    self.GRAPHQL_URL,
                    json=payload,
                    headers=headers,
                    cookies=cookies
                )

                # 403 차단 → 해당 IP만 차단 마킹, 즉시 다른 IP로 (대기 없음!)
                if response.status_code == 403:
                    session.mark_blocked()
                    self._stealth.mark_proxy_429(session.label)
                    print(f"[GraphQL] [BAN] 403 [{session.label}] → 즉시 다른 IP로")
                    continue  # 대기 없이 즉시 다른 세션으로

                # 429 Rate Limit → 해당 IP만 쿨다운, 즉시 다른 IP로 (이전 버전 방식)
                if response.status_code == 429:
                    session.mark_rate_limited()
                    self._stealth.mark_proxy_429(session.label)
                    self._session_manager.report_429(session.label)
                    print(f"[GraphQL] [!] 429 [{session.label}] → 즉시 다른 IP로")
                    continue  # 대기 없이 즉시 다른 세션으로

                # 500+ 서버 에러 → 짧은 대기 후 재시도
                if response.status_code >= 500:
                    if self.debug:
                        print(f"[GraphQL] [!] HTTP {response.status_code} [{session.label}]")
                    time_module.sleep(0.8)  # 서버 에러는 0.8초 대기 (고속화)
                    continue

                if response.status_code != 200:
                    session.mark_blocked(10)  # 기타 에러도 짧은 쿨다운
                    return None, "error", "", f"HTTP {response.status_code}", None

                # JSON 파싱 (인코딩 에러 방지 - 다중 시도)
                data = None
                try:
                    data = response.json()
                except Exception as json_err:
                    # 폴백 1: 명시적 UTF-8 디코딩
                    try:
                        text = response.content.decode('utf-8', errors='ignore')
                        data = json.loads(text)
                    except Exception:
                        # 폴백 2: response.text 사용
                        try:
                            data = json.loads(response.text)
                        except Exception as final_err:
                            if self.debug:
                                print(f"[GraphQL] JSON 파싱 에러 [{session.label}]: {final_err}")
                            continue  # 다른 세션으로 재시도

                if data is None:
                    continue

                if "errors" in data:
                    error_msg = data["errors"][0].get("message", "Unknown error")[:100]
                    # API 에러는 다른 세션으로 즉시 재시도
                    if attempt < max_retries - 1:
                        if self.debug:
                            print(f"[GraphQL] [!] API 에러 [{session.label}]: {error_msg}")
                        continue
                    return None, "error", "", error_msg, None

                # 성공!
                session.mark_success()
                self._stealth.mark_proxy_success(session.label)  # 성공 기록
                self._session_manager._rate_limiter.report_success(session.label)

                businesses = data.get("data", {}).get("businesses", {})
                items = businesses.get("items", [])
                total_count = businesses.get("total")

                # 순위 확인
                for rank, item in enumerate(items[:max_rank], 1):
                    item_id = str(item.get("id", ""))
                    if item_id == target_place_id:
                        return rank, "found", item.get("name", ""), item.get("businessCategory", ""), total_count

                return None, "not_found", "", "", total_count

            except CurlRequestsError as e:
                err_msg = str(e).lower()
                if "timeout" in err_msg:
                    if self.debug:
                        print(f"[GraphQL] [!] Timeout [{session.label}]")
                else:
                    if self.debug:
                        print(f"[GraphQL] [!] Network [{session.label}]: {type(e).__name__}")
                continue  # 즉시 재시도
            except Exception as e:
                # 인코딩 에러 등도 재시도
                if self.debug:
                    print(f"[GraphQL] [!] 에러 [{session.label}]: {type(e).__name__}: {str(e)[:50]}")
                continue  # 즉시 재시도

        # 최대 재시도 후에도 실패 → error로 반환 (not_found가 아님!)
        return None, "error", "", "Max retries exceeded", None

    def _check_single_keyword_sync(
        self,
        keyword: str,
        target_place_id: str,
        max_rank: int
    ) -> RankResult:
        """단일 키워드 순위 체크 (동기, 병렬 요청)

        GraphQL(순위)와 검색HTML(지도형태)를 병렬로 요청하여 속도 최적화
        """
        result = RankResult(keyword=keyword)

        if self.debug:
            print(f"[Check] {keyword}: 순차 요청 시작")

        # 순차 요청: GraphQL(순위) → 검색HTML(지도형태)
        # 중첩 ThreadPoolExecutor 제거로 안정성 향상
        rank, status, place_name, error_or_category, total_count = self._fetch_rank_from_graphql(
            keyword, target_place_id, max_rank
        )

        # 최적화: 랭킹된 키워드만 map_type 체크 (not_found는 스킵 → 요청 70-90% 절감)
        if rank is not None:
            map_type = self._fetch_map_type(keyword)
        else:
            map_type = "신지도"  # 랭킹 없으면 기본값 (표시용)

        # 결과 조합
        result.rank = rank
        result.status = status
        result.map_type = map_type
        result.place_name = place_name
        result.total_count = total_count

        if status == "error":
            result.error_message = error_or_category
        else:
            result.business_category = error_or_category

        if self.debug:
            if rank:
                print(f"[Check] {keyword}: {rank}위 ({map_type})")
            else:
                print(f"[Check] {keyword}: {status} ({map_type})")

        return result

    def check_keywords_sync(
        self,
        keywords: List[str],
        target_place_id: str,
        max_rank: int = 30,
        batch_size: int = None,  # 배치 크기 (None이면 동적 조절)
        batch_delay: float = 0.3  # 배치 간 기본 딜레이
    ) -> List[RankResult]:
        """여러 키워드 순위 체크 (스마트 세션 관리 + 동적 배치 조절)

        [핵심 원리]
        - SessionManager가 세션별 헬스를 독립 관리
        - 429 다발 시 자동으로 배치 크기 축소 (10 → 5 → 3)
        - 안정화되면 배치 크기 복구
        - 요청 실패 시 다른 세션으로 재시도
        """
        # === 프록시 타입별 워커 설정 ===
        session_count = self._session_manager.total_count
        is_rotating = self._session_manager._is_rotating

        is_sticky = self._session_manager._is_sticky

        # 다중 인스턴스 여부 확인
        is_multi_instance = self.user_slot > 0

        if is_rotating:
            # Rotating 프록시: 매 요청마다 새 IP → 동시 15개 요청 (고속)
            actual_workers = 15
            current_batch_size = 30
            print(f"[RankChecker] [ROTATING] 고속 모드: {len(keywords)}개 키워드")
            print(f"[RankChecker] 배치 30개씩, 동시 15개 요청 (매 요청 새 IP)")
        elif is_sticky:
            # Sticky 프록시: 프록시 수에 따라 워커/배치 동적 조절 (상향)
            proxy_based_workers = max(3, min(20, session_count // 15))
            proxy_based_batch = max(8, min(40, session_count // 8))

            if is_multi_instance:
                actual_workers = min(proxy_based_workers, 15)
                current_batch_size = min(proxy_based_batch, 30)
                print(f"[RankChecker] [STICKY] 슬롯 {self.user_slot}: {session_count}개 IP → 워커 {actual_workers}, 배치 {current_batch_size}")
            else:
                actual_workers = min(proxy_based_workers, 20)
                current_batch_size = min(proxy_based_batch, 40)
                print(f"[RankChecker] [STICKY] 단독: {session_count}개 IP → 워커 {actual_workers}, 배치 {current_batch_size}")
        elif self.proxy_type == "decodo":
            # Decodo (기타): max_workers 준수
            actual_workers = min(self.max_workers, session_count)
            print(f"[RankChecker] [DECODO] 기본 모드: {len(keywords)}개 키워드")
            print(f"[RankChecker] {session_count}개 엔드포인트, {actual_workers}개 병렬 처리")
        else:
            # Datacenter: 2개 병렬 처리 (쿨다운 간 교차 사용)
            actual_workers = min(2, session_count)
            print(f"[RankChecker] [DC] Datacenter IP 모드: {len(keywords)}개 키워드")
            print(f"[RankChecker] {session_count}개 IP, {actual_workers}개 병렬 처리 (IP당 60초 쿨다운)")

        self._stop_flag = False
        all_results = []
        completed = 0
        total = len(keywords)

        # 다중 인스턴스: 슬롯별 시작 지연 (버스트 방지)
        if is_multi_instance and (is_sticky or is_rotating):
            stagger_delay = (self.user_slot - 1) * 5  # 슬롯당 5초 오프셋 (고속화)
            if stagger_delay > 0:
                print(f"[RankChecker] 슬롯 {self.user_slot}: {stagger_delay:.1f}초 후 시작 (버스트 방지)")
                if self._interruptible_sleep(stagger_delay):
                    return []
        remaining_keywords = list(keywords)  # 남은 키워드

        def worker(keyword: str) -> RankResult:
            nonlocal completed

            # 즉시 중단 체크
            if self._stop_flag:
                return RankResult(keyword=keyword, status="cancelled")

            # 스텔스 딜레이는 _fetch_* 함수 내에서 자동 적용됨
            # (Human-like 타이밍 + 패턴 감지 방지)

            result = self._check_single_keyword_sync(keyword, target_place_id, max_rank)

            # 요청 결과 보고
            is_success = result.status in ("found", "not_found")
            self._session_manager.report_request(is_success)

            # 성공하면 속도 복구 (프록시 라벨 불필요 - 전체적 복구)
            if is_success:
                self._session_manager.reduce_delay("")

            completed += 1
            if self._progress_callback:
                status_msg = f"{keyword}: {result.status}"
                if result.rank:
                    status_msg = f"{keyword}: {result.rank}위"
                # 현재 배치 크기 표시
                current_batch = self._session_manager.get_recommended_batch_size()
                stats = self._session_manager.get_stats()
                if stats["cooling_down"] > 0 or current_batch < 10:
                    status_msg += f" [배치:{current_batch}]"
                self._progress_callback(completed, total, status_msg)

            return result

        # 동적 배치 처리
        batch_num = 0

        # Rotating 모드: 배치 15개 고정 (고속화)
        rotating_batch_size = 15 if is_rotating else None

        while remaining_keywords and not self._stop_flag:
            # 매 배치마다 권장 배치 크기 확인
            self._session_manager.start_new_batch()

            # 동적 배치 크기 결정 (Rotating 모드는 10개 고정)
            if rotating_batch_size:
                current_batch_size = rotating_batch_size
            elif batch_size is not None:
                current_batch_size = batch_size  # 고정 배치 크기 사용
            else:
                current_batch_size = self._session_manager.get_recommended_batch_size()

            # 동적 워커 수 결정 (고속화: 워커 제한 완화)
            # 429 발생으로 배치가 줄면 워커도 축소하되, 기존보다 여유있게
            if current_batch_size <= 5:
                dynamic_workers = min(5, actual_workers)
            elif current_batch_size <= 10:
                dynamic_workers = min(8, actual_workers)
            else:
                dynamic_workers = actual_workers

            # 현재 배치 추출
            batch = remaining_keywords[:current_batch_size]
            remaining_keywords = remaining_keywords[current_batch_size:]
            batch_num += 1

            remaining_count = len(remaining_keywords)
            total_estimated = batch_num + (remaining_count // current_batch_size) + (1 if remaining_count % current_batch_size else 0)

            if self.debug or dynamic_workers != actual_workers:
                stats = self._session_manager.get_stats()
                print(f"[Batch {batch_num}] {len(batch)}개 처리 (배치:{current_batch_size}, 워커:{dynamic_workers}, 세션:{stats['healthy']}/{stats['total']})")

            # 배치 내 병렬 처리 (즉시 중단 지원)
            with ThreadPoolExecutor(max_workers=dynamic_workers) as executor:
                # submit()으로 제출하여 취소 가능하게
                futures = {executor.submit(worker, kw): kw for kw in batch}

                for future in as_completed(futures):
                    # 중단 요청 시 나머지 futures 취소
                    if self._stop_flag:
                        for f in futures:
                            f.cancel()
                        break

                    try:
                        result = future.result(timeout=60)  # 60초 타임아웃 (다중 인스턴스 대응)
                        all_results.append(result)
                    except Exception as e:
                        kw = futures[future]
                        error_msg = str(e)
                        # 타임아웃은 재시도하지 않고 기록만
                        all_results.append(RankResult(keyword=kw, status="error", error_message=error_msg))
                        if "timeout" in error_msg.lower():
                            print(f"[Timeout] {kw}: 60초 초과")

            # 중단 시 즉시 탈출
            if self._stop_flag:
                break

            # 다음 배치 전 딜레이
            if remaining_keywords and not self._stop_flag:
                # Rotating/Sticky 모드: 429 비율에 따라 동적 딜레이
                if is_rotating or is_sticky:
                    stealth_stats = self._stealth.get_stats()
                    total_reqs = stealth_stats.get("total_requests", 0)
                    total_429 = stealth_stats.get("total_429", 0)
                    rate_429 = total_429 / max(1, total_reqs)

                    if rate_429 > 0.50:
                        batch_wait = 8.0
                        print(f"[Rate] [!!] 429율 {rate_429:.0%} → 8초 대기, 배치 축소")
                        current_batch_size = max(3, current_batch_size // 2)
                    elif rate_429 > 0.30:
                        batch_wait = 4.0
                        print(f"[Rate] [!] 429율 {rate_429:.0%} → 4초 대기")
                    elif rate_429 > 0.10:
                        batch_wait = 1.5
                    else:
                        batch_wait = 0.05 if is_multi_instance else 0.02
                else:
                    current_delay = self._session_manager.get_global_delay()
                    batch_wait = max(0.1, current_delay)

                    # 429가 많을 때만 추가 딜레이
                    if current_batch_size < 5:
                        batch_wait += 0.5
                        if self.debug:
                            print(f"[Rate] 429 다발 → {batch_wait:.1f}초 대기")

                # 작은 단위로 나눠서 중단 체크
                if batch_wait > 0.1:
                    wait_chunks = int(batch_wait / 0.1)
                    for _ in range(max(1, wait_chunks)):
                        if self._stop_flag:
                            break
                        time_module.sleep(0.1)
                else:
                    if self._interruptible_sleep(batch_wait):
                        break

        # 완료/중단 통계 출력
        stats = self._session_manager.get_stats()
        final_batch_size = self._session_manager.get_recommended_batch_size()

        # 유효 결과 카운트 (cancelled 제외)
        valid_results = [r for r in all_results if r.status != "cancelled"]
        found_results = [r for r in all_results if r.rank is not None]

        if self._stop_flag:
            print(f"[RankChecker] [STOP] 중단됨: {len(valid_results)}개 완료, {len(found_results)}개 발견")
        else:
            print(f"[RankChecker] [OK] 완료: {len(all_results)}개 결과 (최종 배치크기: {final_batch_size})")

        if stats["total_blocks"] > 0:
            print(f"[RankChecker] 429 {stats['total_blocks']}회 발생 → 자동 복구됨")

        # 불량 IP 통계 출력
        stealth_stats = self._stealth.get_stats()
        if stealth_stats["permanently_blocked"] > 0:
            print(f"[RankChecker] [BAN] 불량 IP {stealth_stats['permanently_blocked']}개 영구 제외됨")
            print(f"[RankChecker] 사용 가능 IP: {stealth_stats['available_ips']}개")

        return all_results

    def _check_rank_only(
        self,
        keyword: str,
        target_place_id: str,
        max_rank: int = 30
    ) -> RankResult:
        """순위만 체크 (HTML 파싱 없이 - 1단계용)

        GraphQL API로 순위만 확인, map_type은 "미확인"으로 설정
        """
        result = RankResult(keyword=keyword)

        # GraphQL로 순위만 조회
        rank, status, place_name, error_or_category, total_count = self._fetch_rank_from_graphql(
            keyword, target_place_id, max_rank
        )

        result.rank = rank
        result.status = status
        result.place_name = place_name
        result.map_type = "미확인"  # 2단계에서 확인
        result.total_count = total_count

        if status == "error":
            result.error_message = error_or_category
        else:
            result.business_category = error_or_category

        return result

    def check_keywords_two_phase(
        self,
        keywords: List[str],
        target_place_id: str,
        max_rank: int = 30,
        target_rank: int = 10  # 이 순위 이내만 2단계 진행
    ) -> List[RankResult]:
        """2단계 키워드 체크 (비용 최적화)

        [1단계] GraphQL로 순위만 체크 (저렴)
        - 모든 키워드에 대해 순위만 확인
        - map_type은 "미확인"으로 설정

        [2단계] HTML 파싱으로 키워드 형태 구분 (순위 이내만)
        - target_rank 이내 키워드만 HTML 파싱
        - 신지도/구지도 구분

        Args:
            keywords: 키워드 리스트
            target_place_id: 플레이스 ID
            max_rank: 최대 검색 순위 (기본 30)
            target_rank: 형태 확인할 순위 기준 (기본 10)

        Returns:
            RankResult 리스트
        """
        print(f"[2Phase] === 1단계: 순위 체크 ({len(keywords)}개 키워드) ===")

        import time as time_module
        import random as random_module

        # === 슬롯별 시작 시간 분산 (429 방지: 인스턴스 간 충분한 간격) ===
        if self.user_slot > 0:
            # 슬롯당 5초 간격 (고속화)
            stagger_delay = (self.user_slot - 1) * 5
            if stagger_delay > 0:
                print(f"[2Phase] 슬롯 {self.user_slot}: {stagger_delay}초 대기")
                if self._interruptible_sleep(stagger_delay):
                    return []

        # === 1단계: 순위만 체크 ===
        self._stop_flag = False
        phase1_results = []
        completed = 0
        total = len(keywords)

        # 워커 수 제한 (프록시 수에 따라 자동 조절)
        session_count = self._session_manager.total_count
        is_rotating = self._session_manager._is_rotating
        is_sticky = self._session_manager._is_sticky

        if is_rotating:
            actual_workers = 8  # Rotating: 다양한 브라우저 + 새 IP
        elif is_sticky:
            actual_workers = max(2, min(10, session_count // 30))
        elif self.proxy_type == "decodo":
            actual_workers = max(2, min(10, session_count // 30))
        else:
            actual_workers = 1
        print(f"[2Phase] 워커 수: {actual_workers} (프록시: {session_count}개)")

        # === Soft Start: 처음 3개만 순차 (빠른 시작) ===
        soft_start_count = min(3, len(keywords))
        soft_start_results = []
        for i, kw in enumerate(keywords[:soft_start_count]):
            result = self._check_rank_only(kw, target_place_id, max_rank)
            soft_start_results.append(result)
            completed += 1
            if self._progress_callback:
                status_msg = f"[1단계] {kw}: {result.rank}위" if result.rank else f"[1단계] {kw}: {result.status}"
                self._progress_callback(completed, total * 2, status_msg)

        # 남은 키워드는 병렬 처리
        remaining_keywords = keywords[soft_start_count:]

        def phase1_worker(keyword: str) -> RankResult:
            nonlocal completed
            if self._stop_flag:
                return RankResult(keyword=keyword, status="cancelled")

            result = self._check_rank_only(keyword, target_place_id, max_rank)
            completed += 1

            # 요청 결과 보고 (배치 크기 동적 조절에 필수!)
            is_success = result.status in ("found", "not_found")
            self._session_manager.report_request(is_success)
            if is_success:
                self._session_manager.reduce_delay("")

            if self._progress_callback:
                status_msg = f"[1단계] {keyword}: {result.rank}위" if result.rank else f"[1단계] {keyword}: {result.status}"
                self._progress_callback(completed, total * 2, status_msg)  # total*2 (2단계 포함)

            return result

        # Soft Start 결과 추가
        phase1_results.extend(soft_start_results)

        # 남은 키워드 배치 처리
        if remaining_keywords:
            if is_rotating:
                max_workers = min(8, actual_workers)
                max_batch = 20
            elif is_sticky:
                max_workers = min(8, actual_workers)
                max_batch = 25
            else:
                max_workers = min(5, actual_workers)
                max_batch = 10
            print(f"[2Phase] 병렬 처리: {len(remaining_keywords)}개 키워드... (배치:{max_batch}, 워커:{max_workers})")

            idx = 0
            while idx < len(remaining_keywords) and not self._stop_flag:
                self._session_manager.start_new_batch()
                recommended = self._session_manager.get_recommended_batch_size()
                batch_size = min(max_batch, recommended)
                dynamic_workers = min(max_workers, batch_size)

                batch = remaining_keywords[idx:idx + batch_size]
                idx += len(batch)

                with ThreadPoolExecutor(max_workers=dynamic_workers) as executor:
                    futures = {executor.submit(phase1_worker, kw): kw for kw in batch}
                    for future in as_completed(futures):
                        if self._stop_flag:
                            break
                        result = future.result()
                        phase1_results.append(result)

                # 배치 간 429율 기반 적응형 백오프
                if idx < len(remaining_keywords) and not self._stop_flag:
                    stealth_stats = self._stealth.get_stats()
                    total_429 = stealth_stats.get("total_429", 0)
                    total_reqs = stealth_stats.get("total_requests", 0)
                    if total_429 > 0 and total_reqs > 0:
                        rate = total_429 / total_reqs
                        if rate > 0.50:
                            # 429 폭발: 8초 대기 + 배치/워커 축소
                            print(f"[2Phase] [!!] 429율 {rate:.0%} → 8초 대기, 배치 축소")
                            if self._interruptible_sleep(8.0):
                                break
                            max_batch = max(3, max_batch // 2)
                            max_workers = max(1, max_workers // 2)
                        elif rate > 0.30:
                            # 429 경고: 4초 대기
                            print(f"[2Phase] [!] 429율 {rate:.0%} → 4초 대기")
                            if self._interruptible_sleep(4.0):
                                break
                        elif rate > 0.10:
                            # 429 소량: 1.5초 대기
                            if self._interruptible_sleep(1.5):
                                break

        if self._stop_flag:
            print(f"[2Phase] 1단계 중단됨")
            return phase1_results

        # === 에러 키워드 재시도 (바로 재시도 - 프록시 흘리기) ===
        error_results = [r for r in phase1_results if r.status == "error"]
        if error_results and not self._stop_flag:
            error_keywords = [r.keyword for r in error_results]
            print(f"[2Phase] [재시도] {len(error_keywords)}개 에러 키워드 → 즉시 재시도")

            # 에러 결과 제거 후 재시도
            phase1_results = [r for r in phase1_results if r.status != "error"]
            if is_sticky:
                retry_batch_size = min(25, len(error_keywords))
                retry_workers = min(8, retry_batch_size)
            else:
                retry_batch_size = min(10, len(error_keywords))
                retry_workers = min(5, retry_batch_size)
            print(f"[2Phase] [재시도] {len(error_keywords)}개 재시도 시작 (배치:{retry_batch_size}, 워커:{retry_workers})")

            retry_idx = 0
            while retry_idx < len(error_keywords) and not self._stop_flag:
                retry_batch = error_keywords[retry_idx:retry_idx + retry_batch_size]
                retry_idx += len(retry_batch)

                with ThreadPoolExecutor(max_workers=retry_workers) as executor:
                    futures = {executor.submit(phase1_worker, kw): kw for kw in retry_batch}
                    for future in as_completed(futures):
                        if self._stop_flag:
                            break
                        result = future.result()
                        phase1_results.append(result)

                # 재시도 배치 간 1초 대기 (프록시 흘리기)
                if retry_idx < len(error_keywords) and not self._stop_flag:
                    if self._interruptible_sleep(1.0):
                        break

            retry_success = sum(1 for r in phase1_results if r.keyword in error_keywords and r.status != "error")
            retry_still_error = len(error_keywords) - retry_success
            print(f"[2Phase] [재시도] 완료: {retry_success}/{len(error_keywords)}개 복구")

            # 2차 재시도 (아직 에러인 키워드)
            if retry_still_error > 0 and not self._stop_flag:
                error_results_2 = [r for r in phase1_results if r.keyword in error_keywords and r.status == "error"]
                if error_results_2:
                    error_keywords_2 = [r.keyword for r in error_results_2]
                    phase1_results = [r for r in phase1_results if not (r.keyword in error_keywords_2 and r.status == "error")]
                    print(f"[2Phase] [2차 재시도] {len(error_keywords_2)}개 → 2초 대기 후 재시도")
                    for _ in range(20):
                        if self._stop_flag:
                            break
                        time_module.sleep(0.1)

                    retry2_idx = 0
                    while retry2_idx < len(error_keywords_2) and not self._stop_flag:
                        retry2_batch = error_keywords_2[retry2_idx:retry2_idx + 5]
                        retry2_idx += len(retry2_batch)
                        with ThreadPoolExecutor(max_workers=min(3, len(retry2_batch))) as executor:
                            futures = {executor.submit(phase1_worker, kw): kw for kw in retry2_batch}
                            for future in as_completed(futures):
                                if self._stop_flag:
                                    break
                                result = future.result()
                                phase1_results.append(result)
                        if retry2_idx < len(error_keywords_2) and not self._stop_flag:
                            if self._interruptible_sleep(1.0):
                                break

                    retry2_success = sum(1 for r in phase1_results if r.keyword in error_keywords_2 and r.status != "error")
                    print(f"[2Phase] [2차 재시도] 완료: {retry2_success}/{len(error_keywords_2)}개 복구")

        # === 순위 이내 키워드 필터링 ===
        in_rank_results = [r for r in phase1_results if r.rank and r.rank <= target_rank]
        out_rank_results = [r for r in phase1_results if not r.rank or r.rank > target_rank]

        print(f"[2Phase] 1단계 완료: {len(in_rank_results)}개 순위 이내, {len(out_rank_results)}개 순위 외")

        if not in_rank_results:
            print(f"[2Phase] 순위 이내 키워드 없음 - 2단계 생략")
            return phase1_results

        # === Phase 전환 (바로 진행) ===

        # === 2단계: 순위 이내 키워드만 HTML 파싱 ===
        print(f"[2Phase] === 2단계: 키워드 형태 구분 ({len(in_rank_results)}개) ===")

        phase1_count = len(keywords)

        def phase2_worker(result: RankResult) -> RankResult:
            nonlocal completed
            if self._stop_flag:
                return result

            # HTML 파싱으로 map_type 확인 (프록시 사용)
            map_type = self._fetch_map_type(result.keyword)
            result.map_type = map_type
            completed += 1

            if self._progress_callback:
                status_msg = f"[2단계] {result.keyword}: {result.rank}위 ({map_type})"
                self._progress_callback(phase1_count + completed, phase1_count + len(in_rank_results), status_msg)

            if self.debug:
                print(f"[2Phase] {result.keyword}: {result.rank}위 → {map_type}")

            return result

        completed = 0  # 리셋

        # 2단계는 내 IP로 빠르게 처리 (GraphQL과 다른 엔드포인트라 rate limit 별도)
        # HTML 요청은 상대적으로 관대하므로 병렬 처리 가능
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(phase2_worker, r) for r in in_rank_results]
            for future in as_completed(futures):
                if self._stop_flag:
                    break
                future.result()

        print(f"[2Phase] 완료: {len(in_rank_results)}개 형태 확인됨")

        # 모든 결과 반환 (순위 내 + 순위 외)
        return phase1_results

    async def check_keywords(
        self,
        keywords: List[str],
        target_place_id: str,
        max_rank: int = 30,
        coords: Dict[str, str] = None  # 하위 호환성 (무시됨)
    ) -> List[RankResult]:
        """여러 키워드 순위 체크 (비동기 래퍼) - 2단계 모드"""
        # 2단계 모드: 순위 체크 후 순위 이내만 형태 확인
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.check_keywords_two_phase(keywords, target_place_id, max_rank, target_rank=max_rank)
        )


# 간편 사용 함수 (비동기)
async def check_ranks_graphql(
    keywords: List[str],
    place_id: str,
    max_rank: int = 30,
    coords: Dict[str, str] = None,  # 하위 호환성 (무시됨)
    proxies: List[dict] = None,
    progress_callback: Callable = None
) -> List[RankResult]:
    """
    GraphQL API로 순위 체크 (간편 함수)

    Args:
        keywords: 키워드 리스트
        place_id: 플레이스 ID
        max_rank: 최대 순위 (기본 30)
        coords: 좌표 (무시됨 - 하위 호환성)
        proxies: 프록시 리스트
        progress_callback: 진행 콜백

    Returns:
        RankResult 리스트
    """
    proxy_configs = []
    if proxies:
        for p in proxies:
            proxy_configs.append(ProxyConfig(
                host=p.get("host", ""),
                port=p.get("port", 8080),
                username=p.get("username", ""),
                password=p.get("password", ""),
                proxy_type=p.get("type", "datacenter")
            ))

    with RankCheckerGraphQL(proxies=proxy_configs) as checker:
        if progress_callback:
            checker.set_progress_callback(progress_callback)

        return checker.check_keywords_sync(keywords, place_id, max_rank)


# 동기 버전 간편 함수
def check_ranks_graphql_sync(
    keywords: List[str],
    place_id: str,
    max_rank: int = 30,
    progress_callback: Callable = None
) -> List[RankResult]:
    """
    GraphQL API로 순위 체크 (동기 버전)

    Args:
        keywords: 키워드 리스트
        place_id: 플레이스 ID
        max_rank: 최대 순위 (기본 30)
        progress_callback: 진행 콜백

    Returns:
        RankResult 리스트
    """
    with RankCheckerGraphQL() as checker:
        if progress_callback:
            checker.set_progress_callback(progress_callback)

        return checker.check_keywords_sync(keywords, place_id, max_rank)


# 테스트
if __name__ == "__main__":
    import time

    def test():
        keywords = ["남양주 카페", "남양주 브런치 카페", "남양주 분위기좋은카페"]
        place_id = "31422965"

        def progress(current, total, msg):
            print(f"[{current}/{total}] {msg}")

        print("=== GraphQL API 테스트 (curl_cffi) ===")
        start = time.time()

        results = check_ranks_graphql_sync(
            keywords=keywords,
            place_id=place_id,
            max_rank=30,
            progress_callback=progress
        )

        elapsed = time.time() - start
        print(f"\n소요 시간: {elapsed:.2f}초")

        print("\n=== 결과 ===")
        for r in results:
            if r.rank:
                print(f"[OK] {r.keyword}: {r.rank}위 ({r.place_name})")
            elif r.status == "not_found":
                print(f"⚪ {r.keyword}: 순위권 외")
            else:
                print(f"❌ {r.keyword}: {r.status} - {r.error_message}")

    test()
