# Phase 2 - Task 2.2 개발 완료

## 완료일시

2026-02-04

## 개발된 기능

### 1. NaverMapScraper 클래스

네이버 플레이스 URL에서 주변 명소를 추출하는 Playwright 기반 스크래퍼

#### 주요 기능

- 플레이스 URL에서 주변(around) 탭 자동 접속
- 주변 명소 목록 추출 (최대 N개)
- 상위 N개 명소 추출
- 랜덤 명소 선택 (상위 3개 중 1개)
- 광고 링크 필터링

#### 데이터 클래스

```python
@dataclass
class LandmarkInfo:
    name: str                    # 명소 이름
    url: Optional[str]           # 플레이스 URL
    place_id: Optional[str]      # 플레이스 ID
```

#### 주요 메서드

| 메서드 | 설명 | 반환값 |
|--------|------|--------|
| `get_nearby_landmarks(place_url, max_count)` | 주변 명소 목록 추출 | `List[LandmarkInfo]` |
| `get_top_landmarks(place_url, count)` | 상위 N개 명소 추출 | `List[LandmarkInfo]` |
| `select_random_landmark(place_url, top_n)` | 랜덤 명소 선택 | `LandmarkInfo` |
| `select_random_landmark_name(place_url, top_n)` | 랜덤 명소 이름만 반환 | `str` |

### 2. 셀렉터 분석

네이버 플레이스 모바일 페이지의 CSS 셀렉터 분석 완료

| 요소 | 셀렉터 |
|------|--------|
| 주변 탭 | `a[role="tab"]:has-text("주변")` |
| 리스트 컨테이너 | `ul.eDFz9` |
| 리스트 아이템 | `li.S0Ns3` |
| 장소 이름 | `span.xBZDS` |
| 장소 링크 | `a.place_bluelink, a.OiGhS` |

### 3. 에러 처리

| 예외 | 상황 |
|------|------|
| `NaverMapScraperError` | 스크래핑 실패 시 |
| - 주변 탭 없음 | 리스트 컨테이너를 찾을 수 없을 때 |
| - 페이지 로딩 실패 | 네트워크 오류, 타임아웃 |

## 생성/수정된 파일

| 파일 | 상태 | 설명 |
|------|------|------|
| `backend/app/services/naver_map.py` | 신규 | NaverMapScraper 클래스 |
| `backend/tests/test_naver_map.py` | 신규 | 단위/통합 테스트 (24개) |
| `docs/selectors/NAVER_PLACE_SELECTORS.md` | 신규 | 셀렉터 문서 |

## 테스트 현황

| 테스트 파일 | 테스트 수 | 상태 |
|-------------|----------|------|
| test_naver_map.py | 24 | ✅ 통과 |
| test_excel_parser.py | 17 | ✅ 통과 |
| test_upload_api.py | 13 | ✅ 통과 |
| test_health.py | 2 | ✅ 통과 |
| test_models.py | 10 | ✅ 통과 |
| test_relationships.py | 8 | ✅ 통과 |
| **총합** | **74** | **✅ 모두 통과** |

### 테스트 분류

#### 단위 테스트 (13개)

- URL에서 place_id 추출
- around URL 빌드
- 셀렉터 상수 정의 확인

#### 모킹 테스트 (8개)

- 명소 추출 성공/실패
- 상위 N개 추출
- 랜덤 선택
- 광고 링크 필터링

#### 통합 테스트 (3개)

- 실제 네이버 플레이스 스크래핑
- 실제 상위 명소 추출
- 실제 랜덤 선택

## 사용 예시

```python
from app.services.naver_map import NaverMapScraper

# 컨텍스트 매니저 사용 (권장)
async with NaverMapScraper(headless=True) as scraper:
    # 주변 명소 전체 추출
    landmarks = await scraper.get_nearby_landmarks(
        "https://m.place.naver.com/restaurant/1724563569"
    )

    # 상위 3개 중 랜덤 선택
    name = await scraper.select_random_landmark_name(
        "https://m.place.naver.com/restaurant/1724563569"
    )
    print(f"선택된 명소: {name}")
```

## 알려진 이슈

### 1. 동적 클래스명

네이버 플레이스의 CSS 클래스명은 빌드마다 변경될 수 있습니다.
- `eDFz9`, `S0Ns3`, `xBZDS` 등은 해시 기반 클래스
- 주기적인 셀렉터 검증 필요
- `place_bluelink`는 비교적 안정적

### 2. 네트워크 의존성

- 통합 테스트는 실제 네이버 서버 접속 필요
- CI 환경에서는 `@pytest.mark.integration` 스킵 가능

### 3. 광고 콘텐츠

- 주변 목록 상단에 광고 장소가 노출될 수 있음
- 광고 링크(`ader.naver.com`)는 URL/place_id 추출에서 제외됨
- 이름은 정상 추출됨

## 점검 시 확인해야 할 항목

### 1. 스크래핑 검증

- [ ] 테스트 URL로 주변 명소 추출 확인
- [ ] 상위 3개 명소 추출 확인
- [ ] 랜덤 선택 동작 확인

### 2. 셀렉터 검증

- [ ] 주변 탭 클릭 동작 확인
- [ ] 리스트 컨테이너 셀렉터 유효성
- [ ] 장소 이름 셀렉터 유효성

### 3. 에러 처리 검증

- [ ] 잘못된 URL 입력 시 에러 처리
- [ ] 주변 탭이 없는 플레이스 처리
- [ ] 네트워크 타임아웃 처리

## Git 커밋

| 항목 | 내용 |
|------|------|
| 커밋 해시 | 7f42c50 |
| 커밋 메시지 | feat(phase2-task2): 네이버맵 주변 명소 추출 구현 |

## 다음 Task 준비사항

### Task 2.3: 네이버맵 - 걸음수 계산

- 네이버 지도 길찾기 페이지 셀렉터 분석 필요
- 출발지/도착지 입력 필드 셀렉터
- 걸음수 텍스트 위치 분석
- `NaverMapScraper` 클래스에 `get_walking_steps()` 메서드 추가 예정

### 의존성

- Task 2.2의 `select_random_landmark_name()` 결과를 출발지로 사용
- 도착지는 `CampaignData.place_name` 사용
