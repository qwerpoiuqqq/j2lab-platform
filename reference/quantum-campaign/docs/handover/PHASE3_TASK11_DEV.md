# Phase 3 - Task 3.11: 통합 테스트 & 안정화

## 작업 요약

전체 플로우 E2E 테스트 및 안정화 작업을 수행했습니다.

## 수행 내용

### 1. 실패 테스트 수정 (14개 -> 0개)

#### test_templates.py (10개 실패 수정)
- **원인**: `app.dependency_overrides[get_db]`를 모듈 레벨에서 설정했으나, 다른 테스트 파일(dashboard_api, manual_campaign 등)의 fixture teardown에서 `app.dependency_overrides.clear()`를 호출하여 override가 제거됨
- **수정**: fixture 기반 override로 변경 (다른 테스트 파일과 동일한 패턴)
  - `db_session` fixture에서 DB 생성 + 모듈 등록
  - `client` fixture에서 override 설정 + teardown 시 clear

#### test_naver_map.py (4개 실패 수정)
1. `test_get_nearby_landmarks_no_list`: 에러 메시지 불일치 수정 ("주변 장소 목록" -> "명소 목록")
2. `test_filter_ad_links`: 광고 URL 필터링 로직이 아이템 자체를 skip하는 것으로 변경되었으므로 테스트 수정
3. `test_get_walking_steps_success`: `query_selector_all` mock을 AsyncMock으로 변경
4. `test_get_walking_steps_with_comma`: 동일한 mock 수정

### 2. DB 자동 마이그레이션

- **문제**: 실제 DB(`data/quantum.db`)에 `place_id`, `extend_target_id` 컬럼 누락
- **수정**: `database.py`에 `init_db()` 및 `_migrate_missing_columns()` 함수 추가
  - 앱 시작 시 자동으로 누락 컬럼 탐지 및 `ALTER TABLE ADD COLUMN` 실행
  - SQLAlchemy Inspector 기반으로 모델과 실제 DB 비교

### 3. 백엔드 안정화

#### 글로벌 에러 핸들러 (main.py)
- `SQLAlchemyError` 핸들러: DB 오류 시 500 + 사용자 친화적 메시지
- `Exception` 핸들러: 예기치 않은 오류 캐치 + 로깅

#### 요청 로깅 미들웨어 (main.py)
- 5초 초과 느린 요청 경고 로그
- 4xx/5xx 에러 응답 경고 로그

#### 앱 생명주기 로깅
- 시작/종료 시 로그 기록

### 4. 프론트엔드 안정화

#### 네트워크 재시도 로직 (api.ts)
- axios 인터셉터를 통한 자동 재시도
- 네트워크 오류 또는 5xx 서버 오류 시 최대 2회 재시도
- 재시도 간 1초 * retryCount 딜레이
- 요청 timeout 30초 설정

#### 에러 메시지 유틸리티 (api.ts)
- `getErrorMessage()` 함수: API 에러에서 사용자 친화적 메시지 추출
- 네트워크 오류, 서버 오류, 일반 오류별 분기 처리

### 5. 백엔드 + 프론트엔드 동시 실행 검증

- Health check: `/health` -> 정상
- Dashboard stats: `/dashboard/stats` -> 정상
- Campaigns: `/campaigns` -> 정상
- Accounts: `/accounts` -> 정상
- Agencies: `/agencies` -> 정상
- Templates: `/templates` -> 정상
- Modules: `/modules` -> 정상
- Frontend build: `npm run build` -> 성공

## 변경 파일

### 수정된 파일
| 파일 | 변경 내용 |
|------|-----------|
| `backend/tests/test_templates.py` | fixture 기반 DB override로 변경 |
| `backend/tests/test_naver_map.py` | mock 수정 + 에러 메시지 수정 + 광고 필터 테스트 수정 |
| `backend/app/database.py` | `init_db()`, `_migrate_missing_columns()` 추가 |
| `backend/app/main.py` | 글로벌 에러 핸들러, 로깅 미들웨어, `init_db()` 호출 추가 |
| `frontend/src/services/api.ts` | 재시도 인터셉터, `getErrorMessage()` 추가 |

## 테스트 결과

```
428 passed, 0 failed, 4 warnings
```

- 전체 428개 테스트 통과
- warnings: `pytest.mark.integration` 미등록 (기능에 영향 없음)

## 주의 사항

- DB 마이그레이션은 시작 시 자동 실행 (컬럼 추가만 지원, 삭제/변경 미지원)
- 프론트엔드 재시도 로직은 GET 요청뿐 아니라 POST에도 적용됨 (멱등성 주의)
