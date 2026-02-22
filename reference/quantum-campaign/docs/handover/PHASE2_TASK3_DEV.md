# Phase 2 - Task 2.3 개발 완료

## 완료일시

2026-02-04

## 개발된 기능

### 1. 도보 걸음수 계산 기능

NaverMapScraper에 출발지에서 도착지까지의 도보 걸음수를 계산하는 기능 추가

#### 주요 메서드

| 메서드 | 설명 | 반환값 |
|--------|------|--------|
| `get_walking_steps(start, dest)` | 도보 경로 걸음수 추출 | `int` |
| `parse_steps(text)` | 걸음수 텍스트 파싱 | `int` |

#### 데이터 흐름

```
출발지(명소) → 네이버 지도 길찾기 → 걸음수 추출 → 정수 반환
```

### 2. 셀렉터 상수

| 상수 | 셀렉터 | 설명 |
|------|--------|------|
| `directions_start_input` | `.search_input_box_wrap.start input.input_search` | 출발지 입력 |
| `directions_goal_input` | `.search_input_box_wrap.goal input.input_search` | 도착지 입력 |
| `directions_autocomplete_item` | `li.item_place div.link_place` | 자동완성 결과 |
| `directions_search_btn` | `button.btn_direction.search` | 길찾기 버튼 |
| `directions_steps_value` | `.walk_direction_value` | 걸음수 값 |
| `directions_steps_unit` | `.walk_direction_unit` | 걸음수 단위 |

### 3. 에러 처리

| 예외 | 상황 |
|------|------|
| `NaverMapScraperError` | 경로 검색 실패 시 |
| - 출발지 검색 결과 없음 | 자동완성 타임아웃 |
| - 도착지 검색 결과 없음 | 자동완성 타임아웃 |
| - 걸음수 찾을 수 없음 | 도보 경로 없음 |
| `ValueError` | 걸음수 파싱 실패 |

## 생성/수정된 파일

| 파일 | 상태 | 설명 |
|------|------|------|
| `backend/app/services/naver_map.py` | 수정 | get_walking_steps(), parse_steps() 추가 |
| `backend/tests/test_naver_map.py` | 수정 | 걸음수 관련 테스트 추가 (14개) |
| `docs/selectors/NAVER_MAP_DIRECTIONS_SELECTORS.md` | 신규 | 길찾기 셀렉터 문서 |

## 테스트 현황

| 테스트 파일 | 테스트 수 | 상태 |
|-------------|----------|------|
| test_naver_map.py | 51 | 46 passed, 5 integration |
| test_excel_parser.py | 17 | passed |
| test_upload_api.py | 13 | passed |
| test_health.py | 2 | passed |
| test_models.py | 10 | passed |
| test_relationships.py | 8 | passed |
| **총합** | **101** | **96 passed** |

### 테스트 분류

#### 단위 테스트 (11개 추가)
- parse_steps 파싱 테스트 (8개)
- 셀렉터 상수 정의 확인 (3개)

#### 모킹 테스트 (3개 추가)
- 걸음수 추출 성공
- 콤마 포함 걸음수 추출
- 출발지 검색 결과 없음

#### 통합 테스트 (2개 추가)
- 실제 도보 걸음수 추출 (서울역 → 남대문시장)
- 긴 경로 걸음수 추출 (서울역 → 명동역)

## 사용 예시

```python
from app.services.naver_map import NaverMapScraper

async with NaverMapScraper(headless=True) as scraper:
    # 1. 주변 명소 중 랜덤 선택
    landmark = await scraper.select_random_landmark_name(
        "https://m.place.naver.com/restaurant/1724563569"
    )
    # 예: "남대문시장"

    # 2. 명소 → 플레이스 걸음수 계산
    steps = await scraper.get_walking_steps(
        start_landmark=landmark,
        destination_place="강남역 맛집"
    )
    # 예: 789

    print(f"걸음수: {steps}")
```

## 알려진 이슈

### 1. 데스크톱 환경 필수

길찾기 페이지는 데스크톱 환경에서만 정상 작동합니다.
- 모바일 User-Agent/Viewport 사용 시 DOM 구조가 다름
- `get_walking_steps()`는 내부적으로 데스크톱 전용 context 생성

### 2. 검색 결과 의존성

자동완성 검색 결과에 의존합니다.
- 검색어와 정확히 일치하지 않아도 첫 번째 결과 선택
- 너무 모호한 검색어는 원하지 않는 결과 선택 가능

### 3. 네트워크 의존성

- 실제 네이버 서버 접속 필요
- 통합 테스트는 `@pytest.mark.integration` 마크 적용
- CI 환경에서는 통합 테스트 스킵 가능

## 점검 시 확인해야 할 항목

### 1. 기능 검증

- [ ] 서울역 → 남대문시장 걸음수 추출 확인
- [ ] 콤마 포함 걸음수 (1,234) 파싱 확인
- [ ] 검색 결과 없는 경우 에러 처리 확인

### 2. 셀렉터 검증

- [ ] 출발지/도착지 입력 필드 셀렉터 유효성
- [ ] 자동완성 결과 셀렉터 유효성
- [ ] 걸음수 값 셀렉터 유효성

### 3. 에러 처리 검증

- [ ] 잘못된 출발지 입력 시 에러 처리
- [ ] 잘못된 도착지 입력 시 에러 처리
- [ ] 도보 경로 없는 경우 에러 처리

## 다음 Task 준비사항

### Task 2.4: superap - 로그인 자동화

- superap 로그인 페이지 셀렉터 분석 필요
- 아이디/비밀번호 입력 필드 셀렉터
- 로그인 버튼 셀렉터
- 로그인 성공/실패 판단 기준

### 의존성

- Task 2.2의 `select_random_landmark_name()` → 출발지
- Task 2.3의 `get_walking_steps()` → 걸음수
- 추후 캠페인 등록 시 "n걸음 내" 필드에 사용
