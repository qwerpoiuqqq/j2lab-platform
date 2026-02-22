# Phase 3 - Task 3.7 개발 완료 문서

## 작업 개요
키워드 자동 변경 로직 구현 - 일일소진 또는 23:50 시점에 자동으로 키워드 변경

## 완료된 기능

### 1. rotate_keywords(campaign_id, db, superap_controller, trigger_type)
**파일**: `backend/app/services/keyword_rotation.py`

**처리 로직**:
1. 해당 캠페인의 미사용 키워드 조회 (is_used=False)
2. 랜덤 셔플 후 255자 이내로 조합 (쉼표 구분, 공백 없음)
3. superap.io에서 캠페인 수정 (키워드 필드만)
4. KeywordPool 업데이트 (is_used=True, used_at=now)
5. Campaign 업데이트 (last_keyword_change)

**trigger_type별 last_keyword_change 처리**:
- `"daily_exhausted"`: 현재 UTC 시간 저장
- `"time_2350"`: 오늘 KST 23:50:00으로 고정 (날짜 밀림 방지)

**반환값**:
```python
{
    "success": bool,
    "message": str,
    "keywords_used": int,      # 사용된 키워드 수
    "keywords_str": str,       # superap에 설정된 키워드 문자열
    "remaining": int,          # 남은 미사용 키워드 수
}
```

### 2. sync_campaign_status(campaign_id, db, superap_controller)
**파일**: `backend/app/services/keyword_rotation.py`

**처리 로직**:
1. superap.io에서 캠페인 상태 조회
2. 상태 매핑: 진행중 / 일일소진 / 캠페인소진 / 일시정지 / 대기중 / 종료
3. Campaign.status 업데이트 후 커밋

**반환값**:
```python
{
    "success": bool,
    "status": str,           # 새 상태
    "previous_status": str,  # 이전 상태
}
```

### 3. sync_all_campaign_statuses(db, superap_controller, account_id)
**파일**: `backend/app/services/keyword_rotation.py`

- 한 계정의 모든 캠페인 상태를 한번에 동기화
- get_all_campaign_statuses()로 한번의 페이지 로드로 전체 상태 추출
- 변경된 캠페인만 DB 업데이트

### 4. should_rotate_at_2350(campaign)
**파일**: `backend/app/services/keyword_rotation.py`

- 23:50 조건에서 해당 캠페인을 변경해야 하는지 판별
- 오늘 23:50:00 KST 이후로 이미 변경된 경우 → False (건너뜀)
- 그 외 → True (변경 필요)

### 5. APScheduler 스케줄러
**파일**: `backend/app/services/scheduler.py`

**check_and_rotate_keywords()** - 매 10분마다 실행:
1. 활성 계정 조회
2. 계정별로:
   - superap.io 로그인
   - 전체 캠페인 상태 동기화 (sync_all_campaign_statuses)
   - 조건 A: 상태='일일소진' 캠페인 → rotate_keywords(trigger="daily_exhausted")
   - 조건 B: 23:50 이후 AND 상태='진행중' 캠페인 → rotate_keywords(trigger="time_2350")
   - 계정 컨텍스트 정리

**start_scheduler() / stop_scheduler()**:
- FastAPI lifespan에서 호출
- AsyncIOScheduler(timezone=Asia/Seoul) 사용

### 6. SuperapController 확장
**파일**: `backend/app/services/superap.py`

**새 메서드 3개**:

1. `edit_campaign_keywords(account_id, campaign_code, new_keywords) -> bool`
   - 캠페인 수정 페이지에서 검색 키워드 필드만 변경
   - submit 후 성공 확인

2. `get_campaign_status(account_id, campaign_code) -> Optional[str]`
   - 캠페인 목록에서 특정 캠페인의 상태 텍스트 추출
   - JavaScript로 테이블 순회하여 매칭

3. `get_all_campaign_statuses(account_id) -> Dict[str, str]`
   - 캠페인 목록에서 모든 캠페인의 코드:상태 딕셔너리 추출
   - 한번의 페이지 로드로 전체 조회 (효율적)

### 7. main.py 수정
**파일**: `backend/app/main.py`

- `start_scheduler()` → lifespan 시작 시 호출
- `stop_scheduler()` → lifespan 종료 시 호출
- logging 기본 설정 추가

## 데이터 플로우

### 키워드 자동 변경 플로우
```
[APScheduler: 매 10분]
     |
     v
[check_and_rotate_keywords()]
     |
     ├── 계정별 superap 로그인
     │
     ├── sync_all_campaign_statuses()
     │   ├── superap.io 캠페인 목록 조회
     │   └── DB 상태 업데이트
     │
     ├── 조건 A: status='일일소진'
     │   └── rotate_keywords(trigger="daily_exhausted")
     │       ├── 미사용 키워드 랜덤 조합 (≤255자)
     │       ├── superap.io 키워드 수정
     │       ├── KeywordPool is_used=True
     │       └── Campaign last_keyword_change = now(UTC)
     │
     └── 조건 B: KST ≥ 23:50 AND status='진행중'
         └── rotate_keywords(trigger="time_2350")
             ├── 미사용 키워드 랜덤 조합 (≤255자)
             ├── superap.io 키워드 수정
             ├── KeywordPool is_used=True
             └── Campaign last_keyword_change = today 23:50:00 KST
```

### 23:50 날짜 밀림 방지 로직
```
23:50 → rotate → last_keyword_change = 23:50:00 KST
23:59 → 스케줄러 재실행 → should_rotate_at_2350() = False (이미 변경됨)
00:05 → 스케줄러 재실행 → is_after_2350 = False (00:05 < 23:50)
→ 다음날 23:50까지 변경하지 않음
```

## 파일 변경 목록

### 새 파일
- `backend/app/services/keyword_rotation.py` - 키워드 변경 + 상태 동기화 서비스
- `backend/app/services/scheduler.py` - APScheduler 스케줄러
- `backend/tests/test_keyword_rotation.py` - 테스트 39개
- `docs/handover/PHASE3_TASK7_DEV.md` - 개발 완료 문서

### 수정 파일
- `backend/app/services/superap.py`
  - `edit_campaign_keywords()` 메서드 추가
  - `get_campaign_status()` 메서드 추가
  - `get_all_campaign_statuses()` 메서드 추가
- `backend/app/main.py`
  - logging 설정 추가
  - `start_scheduler()` / `stop_scheduler()` lifespan 통합

## 테스트 결과

### 신규 테스트 (test_keyword_rotation.py) - 39개

| 카테고리 | 테스트 | 수 |
|---------|--------|-----|
| rotate_keywords 성공 | 기본 성공, KeywordPool 업데이트, last_keyword_change, 23:50 고정, 255자 제한, remaining 카운트, 쉼표 구분 | 7 |
| rotate_keywords 에러 | 미사용 없음, 전부 사용됨, 캠페인 없음, 코드 없음, superap 실패, superap 예외, 계정 없음 | 7 |
| sync_campaign_status | 진행중, 일일소진, 캠페인소진, 캠페인 없음, null 응답, 예외 | 6 |
| sync_all_campaign_statuses | 여러 캠페인, 변경 없음, 빈 응답 | 3 |
| should_rotate_at_2350 | None, 어제, 오늘 이전, 오늘 23:50, 오늘 이후 | 5 |
| 스케줄러 통합 | 계정 없음 건너뜀, 일일소진 처리, 23:50 진행중 처리 | 3 |
| 스케줄러 생명주기 | 시작, 정지, 미실행 시 정지 | 3 |
| 엣지 케이스 | 단일 키워드, 정확히 255자, 256자 초과, 공백 키워드, 2연속 변경 | 5 |

### 전체 테스트 (3회 연속)
```
1회차: 352 collected, 338 passed, 14 failed (기존 이슈)
2회차: 352 collected, 338 passed, 14 failed (동일)
3회차: 352 collected, 337 passed, 15 failed (naver_map flaky +1)
```

기존 실패 (Task 3.7 무관):
- `test_naver_map.py`: 4~5개 (mock 이슈, 기존)
- `test_templates.py`: 10개 (인코딩/상태 이슈, 기존)

## 캠페인 상태 값 정리

| 상태 | 의미 | 출처 |
|------|------|------|
| `pending` | 등록 대기 | 내부 (upload confirm) |
| `pending_extend` | 연장 대기 | 내부 (upload confirm) |
| `active` | 활성 (등록 완료) | 내부 (manual add) |
| `진행중` | 진행 중 | superap.io 동기화 |
| `일일소진` | 일일 예산 소진 | superap.io 동기화 |
| `캠페인소진` | 전체 예산 소진 | superap.io 동기화 |
| `일시정지` | 일시 정지됨 | superap.io 동기화 |
| `대기중` | 대기 상태 | superap.io 동기화 |
| `종료` | 종료됨 | superap.io 동기화 |

## 다음 단계 (Phase 3 - Task 3.8)
- 키워드 관리 (추가/잔량 확인)
- 캠페인에 키워드 추가 API
- 키워드 잔량 확인 및 경고 로직
