"""스마트 트래픽/저장하기 리다이렉트 서비스.

2단계 가중치 랜덤: 진입 방식 → 목적지.
GET /r/{slug} 에서 호출.
"""

from __future__ import annotations

import copy
import logging
import random
from typing import Any, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

NIDLOGIN = "https://nid.naver.com/nidlogin.login"

# 네이버앱 bridge 템플릿
BRIDGE_NAVER_APP = (
    "https://link.naver.com/bridge"
    "?url={fallback_url}"
    "&dst=naversearchapp%3A%2F%2Finappbrowser"
    "%3Furl%3D{dst_url}%26version%3D10"
)

# 지도앱 탭별 URL
MAP_TAB_URLS = {
    "map": "https://app.map.naver.com/launchApp/map",
    "map?tab=discovery": "https://app.map.naver.com/launchApp/map?tab=discovery",
    "map?tab=booking": "https://app.map.naver.com/launchApp/map?tab=booking",
    "map?tab=navi": "https://app.map.naver.com/launchApp/map?tab=navi",
    "map?tab=pubtrans": "https://app.map.naver.com/launchApp/map?tab=pubtrans",
    "map?tab=bookmark": (
        f"{NIDLOGIN}?url="
        + quote("https://app.map.naver.com/launchApp/map?tab=bookmark", safe="")
    ),
    "favorite": (
        f"{NIDLOGIN}?url="
        + quote("https://app.map.naver.com/launchApp/map?tab=bookmark", safe="")
    ),
}

# 기본 채널 비중 설정
DEFAULT_REDIRECT_CONFIG = {
    "channels": {
        "naver_app": {
            "weight": 25,
            "sub": {
                "home": {"weight": 97},
                "blog": {"weight": 3},
            },
        },
        "map_app": {
            "weight": 50,
            "tabs": {
                "map?tab=discovery": {"weight": 25},
                "map?tab=booking": {"weight": 20},
                "map?tab=navi": {"weight": 20},
                "map?tab=pubtrans": {"weight": 15},
                "map?tab=bookmark": {"weight": 20},
            },
        },
        "browser": {
            "weight": 25,
            "sub": {
                "home": {"weight": 97},
                "blog": {"weight": 3},
            },
        },
    },
    "place_id": "",
    "blog_url": "",
}


def get_effective_channels(config: dict) -> dict:
    """실제 적용되는 채널 비중 반환 (blog 없으면 자동 조정).

    blog_url이 없으면 blog 비중을 home에 합산한다.
    """
    channels = copy.deepcopy(config.get("channels", {}))
    adjustments = []

    blog_urls = config.get("blog_urls", [])
    blog_url = config.get("blog_url", "")
    has_blog = bool(blog_urls or blog_url)

    if not has_blog:
        for ch_key in ("naver_app", "browser"):
            sub = channels.get(ch_key, {}).get("sub", {})
            if "blog" in sub and "home" in sub:
                blog_weight = sub["blog"].get("weight", 0)
                if blog_weight > 0:
                    sub["home"]["weight"] = sub["home"].get("weight", 0) + blog_weight
                    sub["blog"]["weight"] = 0
                    adjustments.append(f"{ch_key}: blog {blog_weight}% → home에 합산")

    return {"channels": channels, "adjustments": adjustments}


def build_redirect_url(config: dict) -> tuple[str, str]:
    """2단계 가중치 랜덤으로 최종 리다이렉트 URL + 채널명 반환.

    1단계: 진입 방식 (네이버앱 / 지도앱 / 브라우저)
    2단계: 목적지 (홈 / 블로그) — 네이버앱, 브라우저만 해당

    Returns: (redirect_url, channel_name)
    """
    channels = get_effective_channels(config)["channels"]

    # 1단계: 진입 방식 선택
    channel = _pick_weighted(channels)

    # 2단계: 목적지 선택 + URL 생성
    if channel == "naver_app":
        ch_config = channels.get("naver_app", {})
        sub = ch_config.get("sub", {})
        dest = _pick_weighted(sub)
        url = _build_naver_app_url(config, dest)
        return url, f"naver_app:{dest}"

    elif channel == "map_app":
        ch_config = channels.get("map_app", {})
        tabs = ch_config.get("tabs", {})
        tab = _pick_weighted(tabs) if tabs else "favorite"
        url = MAP_TAB_URLS.get(tab, "https://app.map.naver.com/launchApp/map")
        return url, f"map_app:{tab}"

    elif channel == "browser":
        ch_config = channels.get("browser", {})
        sub = ch_config.get("sub", {})
        dest = _pick_weighted(sub)
        url = _build_browser_url(config, dest)
        return url, f"browser:{dest}"

    else:
        return f"{NIDLOGIN}?url={quote('https://m.naver.com', safe='')}", "fallback"


def _pick_weighted(items: dict) -> str:
    """가중치 기반 랜덤 선택."""
    if not items:
        return "browser"

    names = []
    weights = []
    for name, val in items.items():
        w = val.get("weight", 0) if isinstance(val, dict) else 0
        if w > 0:
            names.append(name)
            weights.append(w)

    if not names:
        return "browser"

    return random.choices(names, weights=weights, k=1)[0]


def _get_destination_url(dest: str, config: dict) -> str:
    """목적지 이름 → 실제 URL."""
    if dest == "home":
        return "https://m.naver.com"
    elif dest == "blog":
        blog_urls = config.get("blog_urls", [])
        if blog_urls:
            return random.choice(blog_urls)
        blog_url = config.get("blog_url", "")
        return blog_url if blog_url else "https://m.naver.com"
    else:
        return "https://m.naver.com"


def _build_naver_app_url(config: dict, dest: str) -> str:
    """네이버앱 인앱브라우저로 열기."""
    dest_url = _get_destination_url(dest, config)
    nidlogin_url = f"{NIDLOGIN}?url={quote(dest_url, safe='')}"
    fallback_encoded = quote(nidlogin_url, safe="")
    dst_encoded = quote(quote(nidlogin_url, safe=""), safe="")

    return BRIDGE_NAVER_APP.format(
        fallback_url=fallback_encoded,
        dst_url=dst_encoded,
    )


def _build_browser_url(config: dict, dest: str) -> str:
    """브라우저에서 nidlogin으로 열기."""
    dest_url = _get_destination_url(dest, config)
    return f"{NIDLOGIN}?mode=form&url={quote(dest_url, safe='')}"
