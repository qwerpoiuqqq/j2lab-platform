"""
네이버 플레이스 데이터 수집기
어뷰징 방지를 위해 검색창 입력 -> 엔터 방식으로 동작
"""
import asyncio
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Optional, List
from playwright.async_api import async_playwright, Page, Browser

from .models import PlaceData, ReviewKeyword, RegionInfo
from .address_parser import AddressParser

# 참고: PLAYWRIGHT_BROWSERS_PATH는 gui_app.py에서 먼저 설정됨
# (playwright import 전에 설정해야 적용됨)


class PlaceScraper:
    """네이버 플레이스 데이터 수집기"""
    
    # 모바일 User-Agent 목록 (랜덤 선택용)
    USER_AGENTS = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
    ]
    
    # Viewport 크기 목록 (모바일 기기 시뮬레이션)
    VIEWPORTS = [
        {"width": 390, "height": 844},   # iPhone 14
        {"width": 393, "height": 873},   # Pixel 7
        {"width": 360, "height": 800},   # 일반 Android
        {"width": 414, "height": 896},   # iPhone 11 Pro Max
    ]
    
    # 네이버 모바일 검색 (지도 직접 접근보다 자연스러움)
    NAVER_SEARCH_URL = "https://m.search.naver.com/search.naver"
    
    def __init__(self, headless: bool = False):
        """
        Args:
            headless: True면 브라우저 창을 숨김 (테스트 시 False 권장)
        """
        self.headless = headless
        self.address_parser = AddressParser()
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
    
    async def __aenter__(self):
        await self._init_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_browser()
    
    async def _init_browser(self):
        """브라우저 초기화 (익명성 강화 + 랜덤 User-Agent)"""
        self._playwright = await async_playwright().start()
        
        # 랜덤 설정 선택
        user_agent = random.choice(self.USER_AGENTS)
        viewport = random.choice(self.VIEWPORTS)
        
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        
        # 익명성 강화 설정
        context = await self._browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            locale="ko-KR",
            # Referer 정책: 출처 정보 제거
            extra_http_headers={
                "Referer": "",  # 빈 Referer
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
            },
            # 추적 방지
            bypass_csp=True,
            ignore_https_errors=True,
        )
        
        self._page = await context.new_page()
        
        # JavaScript로 추적 관련 속성 제거
        await self._page.add_init_script("""
            // Referer 제거
            Object.defineProperty(document, 'referrer', { get: () => '' });
            // WebDriver 감지 방지
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
    
    async def _close_browser(self):
        """브라우저 종료"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def _simulate_search(self, keyword: str) -> bool:
        """
        네이버 모바일 검색을 통해 플레이스 검색 (어뷰징 방지)
        
        Args:
            keyword: 검색할 키워드 (예: "강남 맛집", "홍대 미용실")
        
        Returns:
            검색 성공 여부
        """
        page = self._page
        
        # 1. 네이버 모바일 검색 페이지로 이동 (쿼리 파라미터 사용)
        import urllib.parse
        search_url = f"{self.NAVER_SEARCH_URL}?query={urllib.parse.quote(keyword)}"
        await page.goto(search_url, wait_until="load")
        await asyncio.sleep(random.uniform(2.0, 3.0))  # 렌더링 대기
        
        return True
    
    async def _click_first_result(self) -> bool:
        """네이버 모바일 검색 결과에서 플레이스 링크를 클릭"""
        page = self._page
        
        # 모바일 검색 결과에서 place.naver.com 링크 찾기
        # .place_bluelink가 가장 정확함 (제목 링크)
        selectors = [
            '.place_bluelink',
            'a[href*="place.naver.com"]',
            'a[href*="m.place.naver.com"]',
            '[class*="place"] a'
        ]
        
        for selector in selectors:
            try:
                print(f"[DEBUG] 셀렉터 시도: {selector}")
                elements = await page.locator(selector).all()
                print(f"[DEBUG] 발견된 요소 개수: {len(elements)}")
                
                for element in elements:
                    if not await element.is_visible():
                        continue
                        
                    href = await element.get_attribute("href")
                    if href and "place.naver.com" in href and "/my" not in href:
                        print(f"[DEBUG] 유효한 링크 발견: {href}")
                        await page.goto(href, wait_until="load")
                        await asyncio.sleep(random.uniform(2.0, 3.0))
                        
                        # 최종 URL 확인
                        if "place.naver.com" in page.url and "/my" not in page.url:
                            return True
            except Exception as e:
                print(f"[DEBUG] 셀렉터 처리 중 오류 ({selector}): {e}")
                continue
        
        print("[DEBUG] 유효한 플레이스 링크를 찾지 못함")
        return False
    
    async def _extract_apollo_state(self, page: Optional[Page] = None) -> Optional[dict]:
        """
        페이지에서 window.__APOLLO_STATE__ 추출
        
        Args:
            page: Playwright Page 객체 (None이면 self._page 사용)
        Returns:
            Apollo State 딕셔너리 또는 None
        """
        target_page = page or self._page
        if not target_page:
            return None
        
        try:
            apollo_data = await target_page.evaluate("""
                () => {
                    if (window.__APOLLO_STATE__) {
                        return window.__APOLLO_STATE__;
                    }
                    return null;
                }
            """)
            return apollo_data
        except Exception as e:
            print(f"Apollo State 추출 실패: {e}")
            return None
    
    def _parse_apollo_data(self, apollo_state: dict) -> Optional[PlaceData]:
        """
        Apollo State에서 PlaceData 객체 생성
        
        Args:
            apollo_state: window.__APOLLO_STATE__ 딕셔너리
        """
        # PlaceDetailBase 키 찾기
        place_key = None
        for key in apollo_state.keys():
            if key.startswith("PlaceDetailBase:"):
                place_key = key
                break
        
        if not place_key:
            print("[DEBUG] PlaceDetailBase 키를 찾을 수 없음. 가능한 키 목록:")
            for k in list(apollo_state.keys())[:20]: # 상위 20개만 출력
                print(f"  - {k}")
            return None
        
        data = apollo_state[place_key]
        place_id = place_key.split(":")[1]
        
        place_id = place_key.split(":")[1]
        
        # 기본 정보 추출
        # 키워드: themes(상단 테마) 우선 -> 없으면 keywords/keywordList
        keyword_data = []
        themes = data.get("themes")
        if themes and isinstance(themes, list):
            keyword_data = [t.get("name") for t in themes if isinstance(t, dict) and t.get("name")]
        
        if not keyword_data:
            keyword_data = data.get("keywords") or data.get("keywordList") or []
        
        place = PlaceData(
            id=place_id,
            name=data.get("name", ""),
            category=data.get("category", ""),
            road_address=data.get("roadAddress", ""),
            jibun_address=data.get("address", ""),
            phone=data.get("phone", ""),
            keywords=keyword_data if isinstance(keyword_data, list) else [],
            conveniences=data.get("conveniences", []) or [],
            payment_info=data.get("paymentInfo", []) or [],
        )
        
        # === 병원 전용 데이터 추출 (Apollo State 구조가 다름) ===
        # 병원은 keywordList가 ROOT_QUERY.placeDetail.informationTab에 있음
        # 진료과목은 ROOT_QUERY.placeDetail.hospitalInfo.sortedSubjects에 있음
        
        # 1. ROOT_QUERY에서 placeDetail 찾기
        root_query = apollo_state.get("ROOT_QUERY", {})
        print(f"[DEBUG] ROOT_QUERY 존재: {'ROOT_QUERY' in apollo_state}")
        print(f"[DEBUG] ROOT_QUERY 키 목록: {list(root_query.keys())[:10]}")
        
        place_detail_key = None
        for key in root_query.keys():
            if "placeDetail" in key:
                place_detail_key = key
                break
        
        print(f"[DEBUG] placeDetail 키: {place_detail_key}")
        
        if place_detail_key:
            place_detail = root_query[place_detail_key]
            print(f"[DEBUG] placeDetail 내용 키: {list(place_detail.keys()) if isinstance(place_detail, dict) else type(place_detail)}")
            
            # 2. informationTab에서 keywordList 추출
            # Note: informationTab 키가 "informationTab({"providerSource":...})" 형태일 수 있음
            info_tab_key = None
            for key in place_detail.keys():
                if key.startswith("informationTab"):
                    info_tab_key = key
                    break
            
            info_tab = None
            if info_tab_key:
                info_tab_ref = place_detail.get(info_tab_key)
                if info_tab_ref:
                    if isinstance(info_tab_ref, dict):
                        ref_key = info_tab_ref.get("__ref")
                        if ref_key and ref_key in apollo_state:
                            info_tab = apollo_state[ref_key]
                        elif "keywordList" in info_tab_ref:
                            info_tab = info_tab_ref
            
            if info_tab:
                keyword_list = info_tab.get("keywordList", [])
                if keyword_list:
                    place.keywords = keyword_list
                    print(f"[DEBUG] keywordList 발견: {keyword_list}")
            
            # 3. hospitalInfo에서 진료과목 추출
            hospital_info_ref = place_detail.get("hospitalInfo")
            print(f"[DEBUG] hospitalInfo 타입: {type(hospital_info_ref)}")
            
            hospital_info = None
            if hospital_info_ref:
                if isinstance(hospital_info_ref, dict):
                    ref_key = hospital_info_ref.get("__ref")
                    if ref_key and ref_key in apollo_state:
                        hospital_info = apollo_state[ref_key]
                    elif "sortedSubjects" in hospital_info_ref or "subjects" in hospital_info_ref:
                        hospital_info = hospital_info_ref
            
            if hospital_info:
                print(f"[DEBUG] hospitalInfo 키들: {list(hospital_info.keys())[:15]}")
                sorted_subjects = hospital_info.get("sortedSubjects") or hospital_info.get("subjects") or []
                if sorted_subjects:
                    place.medical_subjects = [s.get("name") for s in sorted_subjects if isinstance(s, dict) and s.get("name")]
                    print(f"[DEBUG] 진료과목 발견: {place.medical_subjects}")
        
        # 소개글 (introduction or description)
        place.introduction = data.get("introduction") or data.get("description") or ""

        # 마이크로 리뷰 추출 (문자열 리스트 또는 객체 리스트 둘 다 처리)
        micro_reviews = data.get("microReviews", [])
        if micro_reviews:
            for r in micro_reviews:
                if isinstance(r, str):
                    place.micro_reviews.append(r)
                elif isinstance(r, dict) and r.get("name"):
                    place.micro_reviews.append(r.get("name"))
        
        # 리뷰 탭 키워드 추출 (VisitorReviewStatsResult:{ID})
        review_stats_key = None
        for key in apollo_state.keys():
            if key.startswith("VisitorReviewStatsResult:"):
                review_stats_key = key
                break
        
        if review_stats_key:
            review_data = apollo_state[review_stats_key]
            analysis = review_data.get("analysis") or {}
            
            # 디버그: analysis 구조 출력
            print(f"[DEBUG] review_stats_key: {review_stats_key}")
            print(f"[DEBUG] analysis 키: {list(analysis.keys()) if analysis else 'None'}")
            
            # 메뉴 키워드 (파스타, 스테이크 등)
            menus = analysis.get("menus") or []
            print(f"[DEBUG] menus 개수: {len(menus)}")
            if menus and len(menus) > 0:
                print(f"[DEBUG] menus 첫번째 아이템: {menus[0] if menus else 'None'}")
                print(f"[DEBUG] menus 전체 라벨: {[m.get('label', '') if isinstance(m, dict) else m for m in menus[:10]]}")
            
            if menus:
                for m in menus:
                    if isinstance(m, dict):
                        place.review_menu_keywords.append(ReviewKeyword(
                            label=m.get("label", ""),
                            count=m.get("count", 0)
                        ))
            
            # 특징 키워드 (맛, 분위기, 가성비 등)
            themes = analysis.get("themes") or []
            if themes:
                for t in themes:
                    if isinstance(t, dict):
                        place.review_theme_keywords.append(ReviewKeyword(
                            label=t.get("label", ""),
                            count=t.get("count", 0)
                        ))
            
            # 투표 키워드 (이런 점이 주차하기 편해요 등)
            voted_keywords = review_data.get("votedKeyword") or []
            if voted_keywords:
                for v in voted_keywords:
                    if isinstance(v, dict):
                        place.voted_keywords.append(ReviewKeyword(
                            label=v.get("displayName", "") or v.get("label", ""), # displayName 또는 label 사용
                            count=v.get("count", 0)
                        ))

        # 좌석 정보 추출 (RestaurantBase 또는 RestaurantSeatItems)
        # 1. PlaceDetailBase나 RestaurantBase에서 seatItems 참조를 찾거나
        # 2. 단순히 Apollo State에 있는 모든 RestaurantSeatItems를 수집 (상세 페이지이므로 안전)
        for key, value in apollo_state.items():
            if key.startswith("RestaurantSeatItems:"):
                seat_name = value.get("value", "") or value.get("name", "")
                if seat_name:
                    place.seat_items.append(seat_name)
        
        # 역 정보 추출 (SubwayStationInfo)
        station_name = ""
        for key, value in apollo_state.items():
            if key.startswith("SubwayStationInfo"):
                station_name = value.get("name", "")
                if station_name:
                    break
        
        # 주소 파싱 (road 필드에서 지하철역 정보 추출)
        road_info = data.get("road", "")  # 길찾기/교통 정보
        place.region = self.address_parser.parse(
            place.jibun_address or place.road_address,
            road_info=road_info
        )
        # 도로명 보완: 지번 주소에 도로명이 없으면 도로명 주소에서 추출
        if place.road_address and not place.region.road:
            road_region = self.address_parser.parse(place.road_address)
            if road_region.road:
                place.region.road = road_region.road
        # 역 정보가 없으면 SubwayStationInfo에서 추가
        if station_name and not place.region.station:
            place.region.station = f"{station_name}역"
            
        # 메뉴 정보 추출 (리뷰 탭의 메뉴 키워드 사용)
        place.menus = [rk.label for rk in place.review_menu_keywords if rk.label]
        
        return place
    
    async def get_place_data(self, keyword: str) -> Optional[PlaceData]:
        """
        키워드로 검색하여 첫 번째 결과의 플레이스 데이터 수집
        
        Args:
            keyword: 검색 키워드 (예: "강남 파스타", "홍대 미용실")
        
        Returns:
            PlaceData 객체 또는 None
        """
        # 검색 수행
        if not await self._simulate_search(keyword):
            return None
        
        # 첫 번째 결과 클릭
        if not await self._click_first_result():
            return None
        
        # Apollo State 추출
        apollo_state = await self._extract_apollo_state()
        if not apollo_state:
            return None
        
        # 데이터 파싱
        place_data = self._parse_apollo_data(apollo_state)
        if place_data:
            place_data.url = self._page.url
        
        return place_data
    
    async def get_place_data_by_url(self, url: str) -> Optional[PlaceData]:
        """
        플레이스 URL로 직접 접근하여 데이터 수집
        (주의: 반복 사용 시 어뷰징 위험)
        
        Args:
            url: 플레이스 URL (예: https://m.place.naver.com/restaurant/12345/home)
        """
        if not self._browser:
            await self._init_browser()
            
        # 기존 컨텍스트 사용 또는 새 페이지 생성
        # _init_browser에서 생성한 페이지가 있으면 그것을 사용하지 않고 새로 만듦 (독립성)
        # 하지만 _init_browser에서 _page를 만드므로 그걸 써도 됨. 
        # 여기서는 독립적인 페이지를 생성해서 닫는 것이 안전함.
        
        # _browser가 있다면 새 컨텍스트/페이지 생성
        context = await self._browser.new_context(
            user_agent=random.choice(self.USER_AGENTS),
            viewport={"width": 375, "height": 812},
            locale="ko-KR"
        )
        page = await context.new_page()
        
        try:
            # 페이지 이동
            await page.goto(url, wait_until="networkidle")
            
            # Apollo State 추출
            apollo_state = await self._extract_apollo_state(page)
            
            if not apollo_state:
                return None
            
            place_data = self._parse_apollo_data(apollo_state)
            
            # === 리뷰 탭에서 메뉴/특징 키워드 DOM 스크랩 ===
            if place_data:
                await self._scrape_review_keywords_from_dom(page, place_data, url)
            
            return place_data
            
        except Exception as e:
            print(f"데이터 수집 중 오류: {e}")
            return None
        finally:
            await page.close()
            await context.close()
    
    async def _scrape_review_keywords_from_dom(self, page: Page, place_data: PlaceData, base_url: str):
        """리뷰 탭에서 메뉴/특징 키워드를 DOM에서 직접 스크랩
        
        Apollo State보다 정확한 데이터를 제공
        """
        try:
            # 리뷰 탭 URL 생성
            review_url = base_url.replace("/home", "/review").replace("/information", "/review")
            if "/review" not in review_url:
                review_url = review_url.rstrip("/") + "/review"
            
            print(f"[DEBUG] 리뷰 탭 접근: {review_url}")
            
            # 리뷰 탭으로 이동
            await page.goto(review_url, wait_until="networkidle")
            await asyncio.sleep(1)  # 추가 로딩 대기
            
            # DOM에서 메뉴/특징 키워드 추출
            keywords_data = await page.evaluate("""
                () => {
                    const result = { menus: [], themes: [] };
                    
                    // YYh8o 클래스를 가진 컨테이너 찾기
                    const containers = document.querySelectorAll('.YYh8o');
                    
                    containers.forEach(container => {
                        // 첫 번째 span에서 카테고리 (메뉴/특징) 확인
                        const categorySpan = container.querySelector('span');
                        if (!categorySpan) return;
                        
                        const category = categorySpan.textContent.trim();
                        
                        // T00ux 클래스를 가진 키워드 링크들 추출
                        const keywordLinks = container.querySelectorAll('a.T00ux');
                        const keywords = [];
                        
                        keywordLinks.forEach(link => {
                            const spans = link.querySelectorAll('span');
                            if (spans.length >= 2) {
                                keywords.push({
                                    label: spans[0].textContent.trim(),
                                    count: parseInt(spans[1].textContent.replace(/,/g, '')) || 0
                                });
                            }
                        });
                        
                        if (category === '메뉴') {
                            result.menus = keywords;
                        } else if (category === '특징') {
                            result.themes = keywords;
                        }
                    });
                    
                    return result;
                }
            """)
            
            print(f"[DEBUG] DOM에서 추출된 메뉴: {len(keywords_data.get('menus', []))}개")
            print(f"[DEBUG] DOM에서 추출된 특징: {len(keywords_data.get('themes', []))}개")
            
            # 기존 데이터 덮어쓰기 (DOM 데이터가 더 정확함)
            if keywords_data.get('menus'):
                place_data.review_menu_keywords = [
                    ReviewKeyword(label=m['label'], count=m['count'])
                    for m in keywords_data['menus']
                ]
                place_data.menus = [m['label'] for m in keywords_data['menus']]
                print(f"[DEBUG] 메뉴 키워드: {[m['label'] for m in keywords_data['menus'][:5]]}...")
            
            if keywords_data.get('themes'):
                place_data.review_theme_keywords = [
                    ReviewKeyword(label=t['label'], count=t['count'])
                    for t in keywords_data['themes']
                ]
                print(f"[DEBUG] 특징 키워드: {[t['label'] for t in keywords_data['themes'][:5]]}...")
                
        except Exception as e:
            print(f"[DEBUG] 리뷰 탭 스크랩 실패: {e}")

    def scrape(self, url: str) -> Optional[PlaceData]:
        """
        동기식 실행 래퍼 (하위 호환성 및 편의성 제공)
        내부적으로 비동기 이벤트 루프를 생성하여 실행합니다.
        """
        try:
            return asyncio.run(self.get_place_data_by_url(url))
        except Exception as e:
            print(f"[ERROR] Scrape execution failed: {e}")
            return None


# 테스트용 헬퍼 함수
async def test_scraper(input_str: str):
    """URL 또는 키워드로 테스트"""
    async with PlaceScraper(headless=False) as scraper:
        # URL인지 키워드인지 확인
        if "place.naver.com" in input_str:
            print(f"[URL 직접 접근] {input_str}")
            result = await scraper.get_place_data_by_url(input_str)
        else:
            print(f"[검색] {input_str}")
            result = await scraper.get_place_data(input_str)
        
        if result:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("데이터 수집 실패")


if __name__ == "__main__":
    import sys
    
    # URL 또는 키워드
    input_str = sys.argv[1] if len(sys.argv) > 1 else "https://m.place.naver.com/restaurant/1181608808/home"
    asyncio.run(test_scraper(input_str))

