# Phase 3 - Task 3.9 개발 완료 문서

## 작업 개요
대시보드 UI - 백엔드 API 구현. 캠페인 목록/상세 조회, 계정/대행사 목록, 대시보드 통계 API.

## 완료된 기능

### 1. GET /campaigns - 캠페인 목록 조회
**파일**: `backend/app/routers/campaigns.py`

**필터**:
- `account_id` (int, 선택) - 계정 ID
- `agency_name` (str, 선택) - 대행사명
- `status` (str, 선택) - 상태

**페이지네이션**:
- `page` (int, 기본값 1) - 페이지 번호
- `limit` (int, 기본값 50, 최대 100) - 페이지당 항목 수

**반환값**:
```python
class CampaignListResponse(BaseModel):
    campaigns: List[CampaignListItem]
    total: int
    page: int
    pages: int

class CampaignListItem(BaseModel):
    id: int
    campaign_code: Optional[str]
    account_id: Optional[int]
    agency_name: Optional[str]
    place_name: str
    campaign_type: str
    status: str
    current_conversions: int
    total_limit: Optional[int]
    daily_limit: int
    start_date: date
    end_date: date
    days_running: int            # 작업 O일째
    keyword_status: str          # 'normal' | 'warning' | 'critical'
    last_keyword_change: Optional[datetime]
```

**최적화**: 키워드 상태 계산 시 N+1 쿼리 방지를 위해 미사용 키워드 수를 배치 쿼리로 조회.

### 2. GET /campaigns/{campaign_id} - 캠페인 상세 조회
**파일**: `backend/app/routers/campaigns.py`

**반환값**:
```python
class CampaignDetailResponse(BaseModel):
    # 기본 정보
    id, campaign_code, account_id, agency_name
    place_name, place_url, place_id, campaign_type
    status, start_date, end_date, daily_limit, total_limit
    current_conversions, landmark_name, step_count

    # 계산 필드
    days_running: int
    keyword_status: str
    keyword_remaining: int    # 미사용 키워드 수
    keyword_total: int        # 전체 키워드 수
    keyword_used: int         # 사용된 키워드 수

    # 키워드 풀
    keywords: List[KeywordInfo]   # id, keyword, is_used, used_at

    # 메타
    last_keyword_change, registered_at, created_at
```

### 3. GET /accounts - 계정 목록 조회
**파일**: `backend/app/routers/dashboard.py`

대시보드 탭용 계정 목록. 각 계정의 캠페인 수 포함.

**반환값**:
```python
class AccountListResponse(BaseModel):
    accounts: List[AccountListItem]

class AccountListItem(BaseModel):
    id: int
    user_id: str
    agency_name: Optional[str]
    is_active: bool
    campaign_count: int
```

### 4. GET /agencies - 대행사 목록 조회
**파일**: `backend/app/routers/dashboard.py`

필터용 대행사 목록. 캠페인에 등록된 대행사명 기준으로 중복 제거.

**반환값**:
```python
class AgencyListResponse(BaseModel):
    agencies: List[AgencyListItem]

class AgencyListItem(BaseModel):
    agency_name: str
    campaign_count: int
```

### 5. GET /dashboard/stats - 대시보드 통계
**파일**: `backend/app/routers/dashboard.py`

**필터**: `account_id` (int, 선택) - 특정 계정만 집계

**반환값**:
```python
class DashboardStatsResponse(BaseModel):
    total_campaigns: int      # 전체 캠페인 수
    active_campaigns: int     # 활성 캠페인 (active + 진행중)
    exhausted_today: int      # 오늘 일일소진 캠페인 수
    keyword_warnings: int     # 키워드 부족 경고 수 (warning + critical)
```

**keyword_warnings 계산 로직**:
- 활성 + 미종료 캠페인 대상
- 미사용 키워드 수 < 남은 일수 * 1.5이면 경고로 카운트

## 헬퍼 함수

### _compute_keyword_status()
**파일**: `backend/app/routers/campaigns.py`

캠페인 목록과 상세에서 공통으로 사용하는 키워드 상태 계산 함수.
기존 `check_keyword_shortage()` 서비스 함수와 동일한 로직이지만 DB 쿼리 없이 값만 받아 계산.

```python
def _compute_keyword_status(unused_count, end_date, today) -> str:
    # 종료 → normal
    # unused < remaining_days → critical
    # unused < remaining_days * 1.5 → warning
    # 그 외 → normal
```

## 데이터 플로우

### 캠페인 목록 조회
```
[GET /campaigns?account_id=1&status=active&page=1&limit=50]
     |
     v
[필터 적용] → WHERE account_id=1 AND status='active'
     |
     v
[페이지네이션] → total count + OFFSET/LIMIT
     |
     v
[배치 키워드 쿼리] → SELECT campaign_id, COUNT(*)
                      FROM keyword_pool
                      WHERE is_used=False AND campaign_id IN (...)
                      GROUP BY campaign_id
     |
     v
[각 캠페인: days_running + keyword_status 계산]
     |
     v
[CampaignListResponse 반환]
```

### 대시보드 통계
```
[GET /dashboard/stats?account_id=1]
     |
     v
[base_query] → WHERE account_id=1
     |
     ├── total: COUNT(*)
     ├── active: COUNT(*) WHERE status IN ('active', '진행중')
     ├── exhausted: COUNT(*) WHERE status = '일일소진'
     └── keyword_warnings:
          ├── 활성+미종료 캠페인 조회
          ├── 배치 미사용 키워드 수 조회
          └── 경고 상태 카운트
```

## 파일 변경 목록

### 수정 파일
- `backend/app/routers/campaigns.py`
  - `CampaignListItem`, `CampaignListResponse` 스키마 추가
  - `KeywordInfo`, `CampaignDetailResponse` 스키마 추가
  - `_compute_keyword_status()` 헬퍼 함수 추가
  - `GET /campaigns` (list) 엔드포인트 추가
  - `GET /campaigns/{campaign_id}` (detail) 엔드포인트 추가
  - `math`, `func` import 추가
- `backend/app/main.py`
  - `dashboard_router` import 및 등록 추가

### 새 파일
- `backend/app/routers/dashboard.py` - 대시보드 라우터 (accounts, agencies, stats)
- `backend/tests/test_dashboard_api.py` - 테스트 45개
- `docs/handover/PHASE3_TASK9_DEV.md` - 개발 완료 문서

## 테스트 결과

### 신규 테스트 (test_dashboard_api.py) - 45개

| 카테고리 | 테스트 | 수 |
|---------|--------|-----|
| GET /campaigns (목록) | empty, list_all, filter_account, filter_agency, filter_status, filter_exhausted, pagination_page1/2/last, combined_filters, days_running, keyword_status, order_desc, response_fields | 14 |
| GET /campaigns/{id} (상세) | detail, includes_keywords, keyword_counts, keyword_status, days_running, not_found, no_keywords, all_fields | 8 |
| GET /accounts | empty, list, fields, campaign_count, inactive_included, no_campaigns_zero | 6 |
| GET /agencies | empty, list, campaign_count, sorted | 4 |
| GET /dashboard/stats | empty, total, active, exhausted, filter_by_account, keyword_warnings_zero, keyword_warnings_critical, response_fields | 8 |
| 통합 시나리오 | full_flow, filter_then_detail, stats_match_list, agencies_match, pagination_covers_all | 5 |

### 전체 테스트 (3회 연속)
```
1회차: 428 collected, 414 passed, 14 failed (기존 이슈)
2회차: 428 collected, 414 passed, 14 failed (동일)
3회차: 428 collected, 414 passed, 14 failed (동일)
```

기존 실패 (Task 3.9 무관):
- `test_naver_map.py`: 4개 (mock 이슈, 기존)
- `test_templates.py`: 10개 (인코딩/상태 이슈, 기존)

## API 엔드포인트 정리

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/campaigns` | 캠페인 목록 (필터+페이지네이션) |
| GET | `/campaigns/{campaign_id}` | 캠페인 상세 (키워드 풀 포함) |
| GET | `/accounts` | 계정 목록 (캠페인 수 포함) |
| GET | `/agencies` | 대행사 목록 (중복 제거) |
| GET | `/dashboard/stats` | 대시보드 통계 |

## 다음 단계 (Phase 3 - Task 3.10)
- 대시보드 UI - 프론트엔드
- React + TypeScript + TailwindCSS
- 위 API 엔드포인트 연동
