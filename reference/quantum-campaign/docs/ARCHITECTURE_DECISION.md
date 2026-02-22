# 퀀텀 캠페인 자동화 시스템 - 아키텍처 최종 결정

> Phase 1 테스트 결과를 바탕으로 확정된 시스템 아키텍처

---

## 1. 결정 배경

### 테스트 수행 (Task 1.3, 1.4)

| 테스트 | 목적 | 결과 |
|--------|------|------|
| 계정 판별 테스트 | superap.io 계정 식별 방식 파악 | 쿠키/세션 기반 확인 |
| 동시 업로드 테스트 | 병렬 처리 가능 여부 확인 | 계정 간 병렬 가능 |

### 핵심 발견
1. superap.io는 **쿠키/세션**으로 계정을 판별 (IP 기반 아님)
2. Playwright 브라우저 **컨텍스트 분리**로 다중 계정 처리 가능
3. 계정 내에서는 **순차 처리**가 안전함

---

## 2. 계정 관리 방식

### 확정: 브라우저 컨텍스트 분리

```
┌─────────────────────────────────────────────────────────┐
│                    Playwright Browser                    │
├─────────────────┬─────────────────┬─────────────────────┤
│   Context A     │   Context B     │   Context C         │
│   (계정A)        │   (계정B)        │   (계정C)            │
├─────────────────┼─────────────────┼─────────────────────┤
│ - 독립 쿠키     │ - 독립 쿠키     │ - 독립 쿠키         │
│ - 독립 세션     │ - 독립 세션     │ - 독립 세션         │
│ - 독립 스토리지 │ - 독립 스토리지 │ - 독립 스토리지     │
└─────────────────┴─────────────────┴─────────────────────┘
```

### 장점
- 계정 간 완전 격리
- 추가 프록시 비용 불필요 (0원)
- Playwright 네이티브 기능 활용
- 세션 유지 및 재사용 가능

### 구현 코드

```python
from playwright.async_api import async_playwright

class BrowserManager:
    def __init__(self):
        self.browser = None
        self.contexts = {}  # account_id -> context

    async def initialize(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)

    async def get_context(self, account_id: int) -> BrowserContext:
        """계정별 독립 컨텍스트 반환 (없으면 생성)"""
        if account_id not in self.contexts:
            self.contexts[account_id] = await self.browser.new_context()
        return self.contexts[account_id]

    async def close_context(self, account_id: int):
        """계정 컨텍스트 정리"""
        if account_id in self.contexts:
            await self.contexts[account_id].close()
            del self.contexts[account_id]
```

---

## 3. 캠페인 등록 처리 방식

### 확정: 계정 간 병렬 + 계정 내 순차

```
┌─────────────────────────────────────────────────────────┐
│                    Campaign Queue                        │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   Worker A    │   │   Worker B    │   │   Worker C    │
│   (계정A)      │   │   (계정B)      │   │   (계정C)      │
├───────────────┤   ├───────────────┤   ├───────────────┤
│ 캠페인1 →     │   │ 캠페인4 →     │   │ 캠페인7 →     │
│ 캠페인2 →     │   │ 캠페인5 →     │   │ 캠페인8 →     │
│ 캠페인3 →     │   │ 캠페인6 →     │   │ 캠페인9 →     │
│   (순차)       │   │   (순차)       │   │   (순차)       │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │ (병렬 실행)
                            ▼
                    ┌───────────────┐
                    │   완료 취합    │
                    └───────────────┘
```

### 처리 로직

```python
import asyncio
from typing import Dict, List

async def process_campaigns(campaigns_by_account: Dict[int, List[Campaign]]):
    """계정별로 캠페인 처리 - 계정 간 병렬, 계정 내 순차"""

    tasks = []
    for account_id, campaigns in campaigns_by_account.items():
        task = asyncio.create_task(
            process_account_campaigns(account_id, campaigns)
        )
        tasks.append(task)

    # 모든 계정 병렬 처리
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

async def process_account_campaigns(account_id: int, campaigns: List[Campaign]):
    """단일 계정의 캠페인들을 순차 처리"""

    context = await browser_manager.get_context(account_id)
    page = await context.new_page()

    results = []
    for campaign in campaigns:
        try:
            result = await register_single_campaign(page, campaign)
            results.append(result)
        except Exception as e:
            results.append({"campaign_id": campaign.id, "error": str(e)})

    return results
```

---

## 4. 브라우저 자동화 전략

### Playwright 설정

```python
# config.py
PLAYWRIGHT_CONFIG = {
    "browser": "chromium",
    "headless": True,
    "args": [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
    "timeout": 30000,  # 30초 기본 타임아웃
}

# 컨텍스트 기본 설정
CONTEXT_CONFIG = {
    "viewport": {"width": 1920, "height": 1080},
    "locale": "ko-KR",
    "timezone_id": "Asia/Seoul",
}
```

### 재시도 전략

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def register_campaign_with_retry(page, campaign):
    """재시도 로직이 적용된 캠페인 등록"""
    return await register_single_campaign(page, campaign)
```

---

## 5. 시스템 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                        관리자 웹 (Frontend)                       │
│                     React + TypeScript + TailwindCSS             │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST API
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend Server (FastAPI)                  │
│ ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐  │
│ │ API Router  │  │ Scheduler   │  │ Browser Manager          │  │
│ │             │  │ (APScheduler)│  │ (Playwright)             │  │
│ │ - /campaigns│  │             │  │ ┌──────────────────────┐ │  │
│ │ - /accounts │  │ - 10분마다  │  │ │ Context Pool         │ │  │
│ │ - /upload   │  │ - 23:50     │  │ │ ┌────┐ ┌────┐ ┌────┐│ │  │
│ │ - /templates│  │ - 일일소진  │  │ │ │ A  │ │ B  │ │ C  ││ │  │
│ └─────────────┘  └─────────────┘  │ │ └────┘ └────┘ └────┘│ │  │
│                                    │ └──────────────────────┘ │  │
│                                    └──────────────────────────┘  │
│ ┌─────────────┐  ┌─────────────────────────────────────────────┐ │
│ │ Naver Map   │  │ superap.io Controller                       │ │
│ │ Service     │  │ - 로그인 관리                                │ │
│ │ - 명소 추출 │  │ - 캠페인 등록/수정                           │ │
│ │ - 걸음수    │  │ - 키워드 교체                                │ │
│ └─────────────┘  └─────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SQLite Database                           │
│      accounts | campaigns | campaign_templates | keyword_pool    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 비용 분석

| 항목 | 필요 여부 | 비용 |
|------|-----------|------|
| Playwright | 필수 | 무료 (오픈소스) |
| Chromium 브라우저 | 필수 | 무료 |
| 프록시 (Decodo) | **불필요** | 0원 |
| 서버 | 사내 PC | 0원 |

**총 추가 비용: 0원**

---

## 7. 리스크 및 대응

### 리스크 1: superap.io 차단
- **가능성**: 낮음 (정상 사용 패턴)
- **대응**: 요청 간격 조절 (2~5초), User-Agent 로테이션

### 리스크 2: 세션 만료
- **가능성**: 중간
- **대응**: 작업 전 로그인 상태 확인, 자동 재로그인

### 리스크 3: DOM 구조 변경
- **가능성**: 낮음 (대규모 개편 시)
- **대응**: Selector 외부 설정 파일화, 빠른 수정 가능

---

## 8. 성능 목표

| 지표 | 목표 |
|------|------|
| 단일 캠페인 등록 | 30~60초 |
| 10캠페인/계정 | 5~10분 |
| 3계정 × 10캠페인 병렬 | 5~10분 |
| 키워드 교체 (1건) | 10~20초 |
| 일일 키워드 교체 (50건) | 10~15분 |

---

## 9. 구현 우선순위

### Phase 2에서 구현할 내용

1. **BrowserManager 클래스** - 컨텍스트 풀 관리
2. **AccountWorker 클래스** - 계정별 작업 처리
3. **CampaignQueue 클래스** - 작업 큐 관리
4. **superap.io 로그인/등록 자동화**
5. **네이버맵 명소/걸음수 추출**

---

## 10. 결론

| 결정 사항 | 내용 |
|-----------|------|
| 계정 관리 | Playwright 브라우저 컨텍스트 분리 |
| 캠페인 처리 | 계정 간 병렬 + 계정 내 순차 |
| 프록시 | 불필요 (비용 절감) |
| 브라우저 | Chromium (headless) |

Phase 1 기반 구축 완료. Phase 2에서 핵심 자동화 구현 진행.
