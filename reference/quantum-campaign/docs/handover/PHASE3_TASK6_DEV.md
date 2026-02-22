# Phase 3 - Task 3.6 개발 완료 문서

## 작업 개요
캠페인 수기 추가 기능 구현 - 기존에 superap.io에서 수동으로 세팅한 캠페인을 자동 키워드 변경 대상에 포함

## 완료된 기능

### 1. POST /campaigns/manual - 수기 캠페인 추가
**파일**: `backend/app/routers/campaigns.py`

**입력 (ManualCampaignInput)**:
- `campaign_code: str` - superap 캠페인 번호
- `account_id: int` - 계정 DB ID
- `place_name: str` - 플레이스 상호명
- `place_url: str` - 플레이스 URL
- `campaign_type: str` - '트래픽' 또는 '저장하기'
- `start_date: date` - 시작일
- `end_date: date` - 종료일
- `daily_limit: int` - 일일 한도
- `keywords: str` - 쉼표 구분 키워드 풀

**처리 로직**:
1. 계정 존재 및 활성 상태 확인
2. 캠페인 코드 중복 확인 (409 Conflict)
3. 날짜 유효성 검증 (종료일 >= 시작일)
4. `extract_place_id()`로 place_id 자동 추출
5. `total_limit` 자동 계산 (daily_limit * 기간일수)
6. 키워드 파싱 (쉼표 구분, 공백 제거, 중복 제거)
7. Campaign 테이블 저장 (status='active')
8. KeywordPool 테이블에 키워드 개별 저장

**응답 (ManualCampaignResponse)**:
- `success: bool`
- `message: str`
- `campaign_id: int`
- `campaign_code: str`
- `place_id: str`
- `keyword_count: int`

### 2. GET /campaigns/manual/verify/{campaign_code} - 캠페인 확인
**파일**: `backend/app/routers/campaigns.py`

**쿼리 파라미터**:
- `account_id: Optional[int]` - 특정 계정으로 필터링 (선택)

**처리 로직**:
1. DB에서 campaign_code로 검색
2. account_id가 있으면 해당 계정으로 필터
3. 존재 여부 + 상태 정보 반환

**응답 (VerifyCampaignResponse)**:
- `campaign_code: str`
- `exists_in_db: bool`
- `db_campaign_id: Optional[int]`
- `db_status: Optional[str]`
- `message: str`

### 3. 입력 유효성 검증
Pydantic field_validator로 다음 항목 검증:
- `campaign_type`: '트래픽' 또는 '저장하기'만 허용
- `campaign_code`: 공백만 있으면 거부
- `place_name`: 공백만 있으면 거부
- `place_url`: 공백만 있으면 거부
- `daily_limit`: 1 이상만 허용
- `keywords`: 공백만 있으면 거부

## 데이터 플로우

### 수기 캠페인 추가 플로우
```
[사용자 입력]
  campaign_code, account_id, place_name, place_url,
  campaign_type, start_date, end_date, daily_limit, keywords
     |
     v
[검증]
  ├── 계정 존재 + 활성 확인 → 404
  ├── 캠페인 코드 중복 확인 → 409
  └── 날짜 유효성 확인 → 400
     |
     v
[자동 처리]
  ├── extract_place_id(place_url) → place_id
  ├── total_limit = daily_limit * days
  └── 키워드 파싱 + 중복 제거
     |
     v
[DB 저장]
  ├── Campaign(status='active', registered_at=now)
  └── KeywordPool × N개 (is_used=False)
     |
     v
[응답]
  success, campaign_id, campaign_code, place_id, keyword_count
```

### 캠페인 확인 플로우
```
[GET /campaigns/manual/verify/{campaign_code}]
     |
     v
[DB 조회]
  Campaign.campaign_code == campaign_code
  + Optional: Campaign.account_id == account_id
     |
     v
[응답]
  exists_in_db, db_campaign_id, db_status, message
```

## 파일 변경 목록

### 새 파일
- `backend/app/routers/campaigns.py` - 캠페인 수기 추가 라우터
- `backend/tests/test_manual_campaign.py` - 테스트 26개
- `docs/handover/PHASE3_TASK6_DEV.md` - 개발 완료 문서

### 수정 파일
- `backend/app/main.py`
  - `campaigns_router` import 추가
  - `app.include_router(campaigns_router)` 추가
- `backend/app/routers/__init__.py`
  - `campaigns_router` import 및 `__all__` 추가

## 테스트 결과

### 신규 테스트 (test_manual_campaign.py) - 26개

| 카테고리 | 테스트 | 수 |
|---------|--------|-----|
| 수기 추가 성공 | 기본 추가, DB 저장, total_limit 계산, 키워드 저장, 중복 키워드, 원본 보존, 저장하기 타입, URL별 place_id | 8 |
| 수기 추가 에러 | 계정 없음, 비활성 계정, 중복 코드, 날짜 오류, 잘못된 타입, 빈 코드, 빈 키워드, 0 한도, 쉼표만 키워드 | 9 |
| 캠페인 확인 | 없는 코드, 있는 코드, account_id 필터, pending 상태, 필터 없이 | 5 |
| 통합 플로우 | 확인→추가, 중복 시도, 여러 캠페인, 대량 키워드 | 4 |

### 전체 테스트 (3회 연속)
```
1회차: 313 collected, 300 passed, 13 failed (기존 naver_map + templates 이슈)
2회차: 313 collected, 299 passed, 14 failed (동일)
3회차: 313 collected, 299 passed, 14 failed (동일)
```

기존 실패 (Task 3.6 무관):
- `test_naver_map.py`: 4개 (mock 이슈, 기존)
- `test_templates.py`: 9~10개 (인코딩/상태 이슈, 기존)

## 다음 단계 (Phase 3 - Task 3.7)
- 키워드 자동 변경 로직 (일일소진/23:50)
- rotate_keywords() 구현
- APScheduler 스케줄러 설정
- 상태 동기화 로직
