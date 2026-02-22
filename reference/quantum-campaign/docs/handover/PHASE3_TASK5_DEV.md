# Phase 3 - Task 3.5 개발 완료 문서

## 작업 개요
대량 등록 미리보기에서 연장/신규 선택 기능 구현

## 완료된 기능

### 1. POST /upload/preview 수정
**파일**: `backend/app/routers/upload.py`

**변경사항**:
- 각 행마다 `extract_place_id()` + `check_extension_eligible()` 호출
- 유효한 행만 연장 체크 (에러 있는 행은 건너뜀)
- total_count 자동 계산: `daily_limit * (end_date - start_date + 1)`

**응답에 추가된 필드** (CampaignPreviewItem):
- `extension_eligible: bool` - 연장 가능 여부
- `existing_campaign_code: Optional[str]` - 기존 캠페인 번호
- `existing_campaign_id: Optional[int]` - 기존 캠페인 DB ID
- `existing_total_count: Optional[int]` - 기존 총 타수

### 2. POST /upload/confirm 수정
**파일**: `backend/app/routers/upload.py`

**변경사항**:
- 각 행의 `action` 필드 확인 ("new" / "extend")
- action에 따라 분기 처리:
  - `"new"`: 기존과 동일하게 `status="pending"` 캠페인 생성
  - `"extend"`: `status="pending_extend"`, `extend_target_id` 설정
- 연장 대상 캠페인 존재 및 active 상태 검증
- 모든 캠페인에 `place_id` 자동 설정

**요청에 추가된 필드** (CampaignConfirmItem):
- `action: str = "new"` - "new" 또는 "extend" (기본값 "new", 하위 호환)
- `existing_campaign_id: Optional[int] = None` - 연장 시 기존 캠페인 DB ID

**응답에 추가된 필드** (ConfirmResponse):
- `new_count: int` - 신규 등록 수
- `extend_count: int` - 연장 등록 수

### 3. Campaign 모델 수정
**파일**: `backend/app/models/campaign.py`

**추가 컬럼**:
- `extend_target_id = Column(Integer, nullable=True)` - 연장 대상 캠페인 DB ID

### 4. 스키마 유효성 검증
- `action` 필드: "new" 또는 "extend"만 허용 (Pydantic validator)
- `campaign_type` 필드: 기존 검증 유지

## 데이터 플로우

### 미리보기 (Preview)
```
[엑셀 업로드]
     |
     v
[ExcelParser.parse()] → 행 단위 검증
     |
     v
[각 유효한 행마다]
  ├── extract_place_id(place_url) → place_id 추출
  └── check_extension_eligible(place_id, total_count, db) → ExtensionInfo
     |
     v
[CampaignPreviewItem]
  ├── 기존 필드 (row_number, agency_name, ...)
  └── 연장 정보 (extension_eligible, existing_campaign_code, ...)
```

### 확정 (Confirm)
```
[ConfirmRequest]
  campaigns: [{action: "new"}, {action: "extend", existing_campaign_id: 5}]
     |
     v
[각 캠페인마다]
  ├── action == "new"
  |     └── Campaign(status="pending") 생성
  |
  └── action == "extend"
        ├── 대상 캠페인 존재 + active 검증
        └── Campaign(status="pending_extend", extend_target_id=5) 생성
     |
     v
[ConfirmResponse]
  ├── created_count: 2
  ├── new_count: 1
  └── extend_count: 1
```

### 워커 처리 (후속 Task에서 구현)
```
[워커가 pending 캠페인 조회]
  ├── status == "pending" → register_campaign() 호출
  └── status == "pending_extend" → extend_campaign() 호출
        └── extend_target_id로 대상 캠페인 찾기
```

## 하위 호환성
- `action` 기본값 "new" → 기존 클라이언트가 action 없이 요청해도 정상 동작
- `existing_campaign_id` 기본값 None → 기존 요청 형식 유지
- `ConfirmResponse`에 `new_count`, `extend_count` 추가 (기존 `created_count` 유지)
- 기존 테스트 13건 모두 통과 확인

## 파일 변경 목록

### 수정 파일
- `backend/app/routers/upload.py`
  - import 추가 (extract_place_id, check_extension_eligible, ExtensionInfo)
  - CampaignPreviewItem: 연장 정보 필드 4개 추가, from_parsed() 시그니처 변경
  - CampaignConfirmItem: action, existing_campaign_id 필드 추가, validate_action() 추가
  - ConfirmResponse: new_count, extend_count 필드 추가
  - preview_upload(): 연장 조건 체크 로직 추가
  - confirm_upload(): extend/new 분기 처리, place_id 자동 설정

- `backend/app/models/campaign.py`
  - `extend_target_id` 컬럼 추가

### 새 파일
- `backend/tests/test_upload_extension.py` - 연장/신규 선택 테스트 (20개)

## 테스트 결과

### 신규 테스트 (test_upload_extension.py) - 20개
| 카테고리 | 테스트 | 수 |
|---------|--------|-----|
| Preview 연장 정보 | 기존 없음, active 있음, 총 타수 초과, pending 제외, 혼합, invalid 건너뜀 | 6 |
| Confirm 분기 처리 | 신규, 연장, ID 없이 extend, 존재하지 않는 대상, 비활성 대상, 혼합, 메시지 | 8 |
| 스키마 검증 | 잘못된 action, 기본값, place_id 추출 | 3 |
| 하위 호환성 | 응답 필드 포함, action 없이 요청, 카운트 필드 | 3 |

### 전체 테스트 (3회 연속)
```
1회차: 287 collected, 283 passed, 4 failed (기존 test_naver_map.py mock 이슈)
2회차: 287 collected, 283 passed, 4 failed (동일)
3회차: 287 collected, 283 passed, 4 failed (동일)
```

## 다음 단계 (Phase 3 - Task 3.6)
- 캠페인 직접 추가 (수기 입력)
- POST /campaigns/manual API
- 캠페인 존재 확인 API
