"""플레이스 데이터 수집 서비스.

Naver Place 페이지에서 좌표, 블로그 URL 등을 추출한다.
auto_registration에서 스마트 트래픽 캠페인 등록 시 호출.
"""

import json
import logging
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# 요청 타임아웃
TIMEOUT = 10

# User-Agent (모바일)
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; SM-S911B) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)


async def collect_place_data(place_id: str, place_url: str = "") -> dict[str, Any]:
    """플레이스 페이지에서 메타데이터를 수집한다.

    Returns:
        {
            "place_x": "126.xxx",  # 경도
            "place_y": "37.xxx",   # 위도
            "blog_url": "https://blog.naver.com/...",
            "share_url": "https://map.naver.com/p/entry/place/{place_id}",
        }
    """
    result = {
        "place_x": "",
        "place_y": "",
        "blog_url": "",
        "share_url": "",
        "plr_available": False,
    }

    if not place_id:
        return result

    # 지도앱 딥링크 (place_id만 있으면 생성 가능)
    result["share_url"] = f"https://m.map.naver.com/map.naver?pinId={place_id}"

    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={"User-Agent": MOBILE_UA},
            follow_redirects=True,
        ) as client:
            # 1. 좌표 추출
            coords = await _extract_coordinates(client, place_id)
            if coords:
                result["place_x"] = coords["x"]
                result["place_y"] = coords["y"]

            # 2. 예약 가능 여부 체크 (PLR 채널 활성화 판단)
            result["plr_available"] = await _check_plr_available(client, place_id)

            # 3. 블로그 URL 추출
            blog_url = await _extract_blog_url(client, place_id)
            if blog_url:
                result["blog_url"] = blog_url

    except Exception as e:
        logger.warning(f"[데이터수집] place_id={place_id} 수집 실패: {e}")

    return result


async def _extract_coordinates(
    client: httpx.AsyncClient, place_id: str
) -> Optional[dict[str, str]]:
    """플레이스 페이지에서 좌표(x, y)를 추출한다."""
    url = f"https://m.place.naver.com/restaurant/{place_id}/home"

    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning(f"[좌표추출] HTTP {resp.status_code} for {url}")
            return None

        html = resp.text

        # 방법 1: __NEXT_DATA__ JSON에서 추출
        coords = _parse_next_data_coords(html)
        if coords:
            return coords

        # 방법 2: meta 태그에서 추출
        coords = _parse_meta_coords(html)
        if coords:
            return coords

        # 방법 3: JavaScript 변수에서 추출
        coords = _parse_js_coords(html)
        if coords:
            return coords

        logger.warning(f"[좌표추출] place_id={place_id} 좌표를 찾지 못함")
        return None

    except Exception as e:
        logger.warning(f"[좌표추출] place_id={place_id} 오류: {e}")
        return None


def _parse_next_data_coords(html: str) -> Optional[dict[str, str]]:
    """__NEXT_DATA__ script 태그에서 좌표 추출."""
    match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*({.+?})\s*</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        # 다양한 경로 탐색
        for path_fn in [
            lambda d: d["props"]["pageProps"]["initialState"]["place"]["detail"],
            lambda d: d["props"]["pageProps"]["initialState"]["place"],
            lambda d: d["props"]["pageProps"]["place"],
        ]:
            try:
                place = path_fn(data)
                x = str(place.get("x", place.get("lng", place.get("longitude", ""))))
                y = str(place.get("y", place.get("lat", place.get("latitude", ""))))
                if x and y and x != "" and y != "":
                    return {"x": x, "y": y}
            except (KeyError, TypeError):
                continue
    except json.JSONDecodeError:
        pass

    return None


def _parse_meta_coords(html: str) -> Optional[dict[str, str]]:
    """meta 태그에서 좌표 추출."""
    lat_match = re.search(
        r'<meta\s+(?:property|name)="(?:og:latitude|latitude|place:location:latitude)"\s+content="([^"]+)"',
        html,
    )
    lng_match = re.search(
        r'<meta\s+(?:property|name)="(?:og:longitude|longitude|place:location:longitude)"\s+content="([^"]+)"',
        html,
    )
    if lat_match and lng_match:
        return {"x": lng_match.group(1), "y": lat_match.group(1)}
    return None


def _parse_js_coords(html: str) -> Optional[dict[str, str]]:
    """JavaScript 코드에서 좌표 추출."""
    # "x":"126.xxx","y":"37.xxx" 패턴
    match = re.search(
        r'"x"\s*:\s*"?([\d.]+)"?\s*,\s*"y"\s*:\s*"?([\d.]+)"?',
        html,
    )
    if match:
        x, y = match.group(1), match.group(2)
        # 한국 좌표 범위 검증 (대략)
        if 124 < float(x) < 132 and 33 < float(y) < 43:
            return {"x": x, "y": y}
    return None


async def _extract_blog_url(
    client: httpx.AsyncClient, place_id: str
) -> Optional[str]:
    """플레이스 블로그 리뷰 페이지에서 블로그 URL을 추출한다."""
    url = f"https://m.place.naver.com/restaurant/{place_id}/blog/review"

    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None

        html = resp.text

        # 블로그 URL 패턴 매칭
        blog_urls = re.findall(
            r'https?://blog\.naver\.com/[A-Za-z0-9_]+/\d+',
            html,
        )
        if blog_urls:
            return blog_urls[0]

        # in.naver.com/... 형식 블로그
        in_urls = re.findall(
            r'https?://in\.naver\.com/[A-Za-z0-9_]+/\d+',
            html,
        )
        if in_urls:
            return in_urls[0]

        return None

    except Exception as e:
        logger.warning(f"[블로그추출] place_id={place_id} 오류: {e}")
        return None


async def _check_plr_available(
    client: httpx.AsyncClient, place_id: str
) -> bool:
    """플레이스에 실시간예약(네이버예약) 기능이 있는지 확인한다."""
    url = f"https://m.place.naver.com/restaurant/{place_id}/home"

    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return False

        html = resp.text

        # 예약 관련 키워드 존재 여부 체크
        booking_indicators = [
            "realTimeBooking",
            "네이버 예약",
            "네이버예약",
            "booking",
            "예약하기",
            '"booking"',
            "naverbooking",
        ]
        html_lower = html.lower()
        for indicator in booking_indicators:
            if indicator.lower() in html_lower:
                logger.info(f"[PLR체크] place_id={place_id} 예약 가능 ('{indicator}' 발견)")
                return True

        logger.info(f"[PLR체크] place_id={place_id} 예약 불가 (키워드 미발견)")
        return False

    except Exception as e:
        logger.warning(f"[PLR체크] place_id={place_id} 오류: {e}")
        return False
