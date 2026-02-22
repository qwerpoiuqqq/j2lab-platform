# Phase 3 - Task 3.8 개발 완료 문서

## 작업 개요
키워드 관리 기능 구현 - 캠페인에 키워드 추가 + 키워드 잔량 확인 및 경고

## 완료된 기능

### 1. POST /campaigns/{campaign_id}/keywords - 키워드 추가 API
**파일**: `backend/app/routers/campaigns.py`

**처리 로직**:
1. 캠페인 존재 확인
2. 쉼표 구분으로 키워드 파싱 (앞뒤 공백 trim)
3. 기존 KeywordPool과 중복 체크 (정확한 문자열 비교)
4. 새 키워드만 KeywordPool에 추가 (is_used=False)
5. 총 키워드 수/미사용 키워드 수 반환

**입력**:
```python
class AddKeywordsInput(BaseModel):
    keywords: str  # 쉼표 구분 (validator로 빈 문자열 검증)
```

**반환값**:
```python
class AddKeywordsResponse(BaseModel):
    success: bool
    message: str
    added_count: int       # 추가된 키워드 수
    duplicates: List[str]  # 중복된 키워드 목록
    total_keywords: int    # 전체 키워드 수
    unused_keywords: int   # 미사용 키워드 수
```

### 2. check_keyword_shortage(campaign_id, db) - 잔량 확인 함수
**파일**: `backend/app/services/keyword_rotation.py`

**처리 로직**:
1. 캠페인 조회
2. 미사용 키워드 수 카운트 (is_used=False)
3. 남은 일수 계산 (end_date - today + 1, 오늘 포함)
4. 상태 판별

**상태 판별 기준**:
| 조건 | 상태 | 색상 |
|------|------|------|
| remaining_keywords < remaining_days | `critical` | 빨간색 |
| remaining_keywords < remaining_days * 1.5 | `warning` | 노란색 |
| 그 외 | `normal` | 기본 |
| remaining_days == 0 (종료) | `normal` | 기본 |

**반환값**:
```python
{
    "remaining_keywords": int,
    "remaining_days": int,
    "status": "normal" | "warning" | "critical",
    "message": str,
}
```

### 3. GET /campaigns/{campaign_id}/keywords/status - 잔량 상태 조회 API
**파일**: `backend/app/routers/campaigns.py`

**처리 로직**:
1. 캠페인 존재 확인 (404 처리)
2. check_keyword_shortage() 호출
3. KeywordStatusResponse 반환

**반환값**:
```python
class KeywordStatusResponse(BaseModel):
    campaign_id: int
    remaining_keywords: int
    remaining_days: int
    status: str           # 'normal' | 'warning' | 'critical'
    message: str
```

## 데이터 플로우

### 키워드 추가 플로우
```
[POST /campaigns/{id}/keywords]
     |
     v
[키워드 파싱] → "마포 곱창,공덕역 맛집,새키워드" → ["마포 곱창", "공덕역 맛집", "새키워드"]
     |
     v
[기존 키워드 조회] → existing_set = {"마포 곱창", "공덕역 맛집", ...}
     |
     v
[중복 체크]
     ├── "마포 곱창" → 중복 → duplicates 목록에 추가
     ├── "공덕역 맛집" → 중복 → duplicates 목록에 추가
     └── "새키워드" → 신규 → KeywordPool에 추가 (is_used=False)
     |
     v
[응답: added_count=1, duplicates=["마포 곱창", "공덕역 맛집"]]
```

### 잔량 확인 플로우
```
[GET /campaigns/{id}/keywords/status]
     |
     v
[check_keyword_shortage()]
     |
     ├── remaining_keywords = COUNT(is_used=False)
     ├── remaining_days = (end_date - today).days + 1
     |
     v
[상태 판별]
     ├── 15 키워드 / 10일 → 15 >= 15.0 → "normal"
     ├── 12 키워드 / 10일 → 10 <= 12 < 15 → "warning"
     └── 5 키워드 / 10일 → 5 < 10 → "critical"
```

## 파일 변경 목록

### 수정 파일
- `backend/app/routers/campaigns.py`
  - `AddKeywordsInput` 스키마 추가
  - `AddKeywordsResponse` 스키마 추가
  - `KeywordStatusResponse` 스키마 추가
  - `POST /{campaign_id}/keywords` 엔드포인트 추가
  - `GET /{campaign_id}/keywords/status` 엔드포인트 추가
- `backend/app/services/keyword_rotation.py`
  - `check_keyword_shortage()` 함수 추가
  - `date` import 추가

### 새 파일
- `backend/tests/test_keyword_management.py` - 테스트 31개
- `docs/handover/PHASE3_TASK8_DEV.md` - 개발 완료 문서

## 테스트 결과

### 신규 테스트 (test_keyword_management.py) - 31개

| 카테고리 | 테스트 | 수 |
|---------|--------|-----|
| check_keyword_shortage | normal, enough_keywords, warning, critical, expired, no_keywords, not_found, all_used, boundary_critical, boundary_warning, boundary_normal, ends_today | 12 |
| POST keywords API | success, with_duplicates, all_duplicates, not_found, empty, whitespace, spaces, single, counts, duplicate_in_input | 10 |
| GET status API | normal, warning, critical, not_found, expired, no_keywords | 6 |
| 통합 시나리오 | add_then_check, incremental, status_change | 3 |

### 전체 테스트 (3회 연속)
```
1회차: 383 collected, 368 passed, 15 failed (기존 이슈)
2회차: 383 collected, 369 passed, 14 failed (동일)
3회차: 383 collected, 369 passed, 14 failed (동일)
```

기존 실패 (Task 3.8 무관):
- `test_naver_map.py`: 4개 (mock 이슈, 기존)
- `test_templates.py`: 10개 (인코딩/상태 이슈, 기존)

## API 엔드포인트 정리

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/campaigns/{campaign_id}/keywords` | 키워드 추가 |
| GET | `/campaigns/{campaign_id}/keywords/status` | 잔량 상태 조회 |

## 다음 단계 (Phase 3 - Task 3.9)
- 대시보드 UI - 백엔드 API
- 캠페인 목록/상세 조회, 계정/대행사 목록, 대시보드 통계 API
