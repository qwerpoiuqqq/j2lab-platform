# Phase 3 - Task 3.4 개발 완료 문서

## 작업 개요
캠페인 연장 세팅 로직 구현 (같은 업체 판별 + 총 타수 조건 + 연장 실행)

## 완료된 기능

### 1. extract_place_id(url)
**파일**: `backend/app/services/campaign_extension.py`

```python
def extract_place_id(url: str) -> Optional[str]
```

**기능**:
- 네이버 플레이스 URL에서 업체 ID(숫자) 추출
- 지원 URL 형식:
  - `https://m.place.naver.com/restaurant/1724563569`
  - `https://m.place.naver.com/cafe/12345678`
  - `https://place.naver.com/restaurant/1724563569`
  - `https://map.naver.com/v5/entry/place/1724563569`
- 하위 경로, 쿼리 파라미터 포함 URL도 처리

### 2. check_extension_eligible()
**파일**: `backend/app/services/campaign_extension.py`

```python
def check_extension_eligible(
    place_id: str,
    new_total_count: int,
    db: Session,
) -> ExtensionInfo
```

**연장 조건**:
1. 같은 `place_id`의 진행 중인(active) 캠페인이 있음
2. 기존 총 타수 + 새로운 타수 <= 10,000

**반환값** (`ExtensionInfo`):
- `is_eligible`: 연장 가능 여부
- `existing_campaign_code`: 기존 캠페인 번호
- `existing_campaign_id`: 기존 캠페인 DB ID
- `existing_total_count`: 기존 총 타수
- `reason`: 사유 설명

### 3. extend_campaign()
**파일**: `backend/app/services/campaign_extension.py`

```python
async def extend_campaign(
    superap_controller: SuperapController,
    db: Session,
    account_id: str,
    existing_campaign_id: int,
    new_total_count: int,
    new_end_date: date,
    new_keywords: List[str],
) -> ExtensionResult
```

**처리**:
1. 기존 캠페인 조회
2. 총 타수 합산 검증 (<= 10,000)
3. superap.io에서 캠페인 수정 (총 타수, 만료일)
4. DB 캠페인 정보 업데이트
5. 키워드 풀에 새 키워드 추가 (중복 제외)
6. original_keywords 업데이트

**반환값** (`ExtensionResult`):
- `success`: 성공 여부
- `campaign_id`: 캠페인 DB ID
- `new_total_count`: 새 총 타수
- `new_end_date`: 새 만료일
- `added_keywords_count`: 추가된 키워드 수
- `error_message`: 실패 시 오류 메시지

### 4. SuperapController.edit_campaign()
**파일**: `backend/app/services/superap.py`

```python
async def edit_campaign(
    self,
    account_id: str,
    campaign_code: str,
    new_total_limit: Optional[int] = None,
    new_end_date: Optional[Union[date, datetime, str]] = None,
) -> bool
```

**기능**:
- 캠페인 수정 페이지(`mode=modify&id={code}`)로 이동
- 총 타수 변경 (autoNumeric 필드)
- 만료일 변경 (JS 직접 설정)
- 수정 버튼 클릭 및 결과 확인

### 5. DB 스키마 변경
**파일**: `backend/app/models/campaign.py`

```python
place_id = Column(String(50), index=True)  # 플레이스 ID (URL에서 추출)
```

- `campaigns` 테이블에 `place_id` 컬럼 추가
- 인덱스 설정 (연장 조건 조회 최적화)

### 6. campaign_registration.py 수정
**파일**: `backend/app/services/campaign_registration.py`

- `_save_campaign_to_db()`에서 `extract_place_id()` 호출하여 `place_id` 자동 저장

## 데이터 클래스

### ExtensionInfo
```python
@dataclass
class ExtensionInfo:
    is_eligible: bool
    existing_campaign_code: Optional[str] = None
    existing_campaign_id: Optional[int] = None
    existing_total_count: Optional[int] = None
    reason: str = ""
```

### ExtensionResult
```python
@dataclass
class ExtensionResult:
    success: bool
    campaign_id: Optional[int] = None
    new_total_count: Optional[int] = None
    new_end_date: Optional[date] = None
    added_keywords_count: int = 0
    error_message: Optional[str] = None
```

## 상수
- `MAX_TOTAL_COUNT = 10000` (최대 총 타수)

## 파일 변경 목록

### 새 파일
- `backend/app/services/campaign_extension.py` - 연장 세팅 서비스
- `backend/tests/test_campaign_extension.py` - 단위 테스트 (39개)

### 수정 파일
- `backend/app/models/campaign.py`
  - `place_id` 컬럼 추가
- `backend/app/services/superap.py`
  - `CAMPAIGN_EDIT_URL` 추가
  - `edit_campaign()` 메서드 추가
- `backend/app/services/campaign_registration.py`
  - `extract_place_id` import 추가
  - `_save_campaign_to_db()`에서 `place_id` 저장

## 테스트 결과

### 단위 테스트
```
tests/test_campaign_extension.py - 39 passed
tests/test_campaign_registration.py - 18 passed
tests/test_superap_campaign.py - 13 passed
```

### 테스트 커버리지
- extract_place_id: 15개 (다양한 URL 형식, 에지 케이스)
- check_extension_eligible: 9개 (가능/불가 조건, 경계값)
- extend_campaign: 10개 (성공/실패/예외/중복키워드)
- 데이터 클래스: 5개

### 전체 테스트 (3회차)
```
267 collected, 263 passed, 4 failed (기존 test_naver_map.py mock 이슈)
```

## 연장 플로우 요약

```
[엑셀 파싱]
     |
     v
[extract_place_id(url)] → place_id 추출
     |
     v
[check_extension_eligible(place_id, new_total, db)]
     |
     ├── 연장 가능 → extend_campaign() 호출
     |                  1. superap.io 수정 (총 타수 + 만료일)
     |                  2. 키워드 풀 추가
     |                  3. DB 업데이트
     |
     └── 연장 불가 → 신규 등록 (register_campaign)
```

## 다음 단계 (Phase 3 - Task 3.5)
- 대량 등록 미리보기에서 연장/신규 선택 UI
- POST /upload/preview에 연장 정보 포함
- POST /upload/confirm에서 연장/신규 분기 처리
