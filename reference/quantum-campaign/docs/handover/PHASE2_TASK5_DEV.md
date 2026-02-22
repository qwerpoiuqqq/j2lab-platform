# Phase 2 - Task 2.5 개발 완료

## 완료일시

2026-02-04

## 개발된 기능

### 1. 캠페인 폼 데이터 클래스

#### CampaignFormData

캠페인 등록 폼 데이터를 담는 데이터 클래스입니다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `campaign_name` | str | 캠페인 이름 |
| `place_name` | str | 상호명 (템플릿 치환용) |
| `landmark_name` | str | 명소명 (템플릿 치환용) |
| `participation_guide` | str | 참여 안내문 |
| `keywords` | List[str] | 검색 키워드 목록 |
| `hint` | str | 힌트 메시지 |
| `walking_steps` | int | 걸음 수 |

**자동 처리 기능:**
- `processed_guide`: 템플릿 치환 적용된 안내문
- `processed_keywords`: 255자 제한 적용된 키워드 문자열
- `get_keywords_count()`: 처리된 키워드 개수 반환

#### CampaignFormResult

폼 입력 결과를 담는 데이터 클래스입니다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `success` | bool | 성공 여부 |
| `screenshot_path` | Optional[str] | 스크린샷 경로 |
| `filled_fields` | List[str] | 입력된 필드 목록 |
| `errors` | List[str] | 에러 메시지 목록 |

### 2. 템플릿 치환 기능

참여 안내문에서 다음 템플릿을 자동 치환합니다:

| 템플릿 | 치환 값 |
|--------|---------|
| `&상호명&` | `place_name` 필드 값 |
| `&명소명&` | `landmark_name` 필드 값 |

**예시:**
```
입력: "&명소명&에서 &상호명&까지 걸어오세요"
치환: "서울타워에서 맛있는식당까지 걸어오세요"
```

### 3. 키워드 255자 제한

키워드 목록을 처리할 때:
1. 각 키워드의 앞뒤 공백 제거
2. 빈 키워드 제거
3. 콤마(`, `)로 구분
4. 전체 길이가 255자 초과 시 마지막 키워드부터 제거

### 4. 메서드 추가

#### fill_campaign_form()

```python
async def fill_campaign_form(
    self,
    account_id: str,
    form_data: CampaignFormData,
    take_screenshot: bool = True,
) -> CampaignFormResult:
```

- 캠페인 등록 페이지로 이동
- 폼 필드 자동 입력
- 스크린샷 저장 (선택)
- **등록 버튼 클릭하지 않음**

#### submit_campaign()

```python
async def submit_campaign(self, account_id: str) -> CampaignFormResult:
```

- 등록 버튼 클릭
- 별도 분리하여 안전한 테스트 가능

#### get_form_field_values()

```python
async def get_form_field_values(self, account_id: str) -> Dict[str, str]:
```

- 현재 폼 필드의 값 조회 (검증용)

### 5. 캠페인 셀렉터

| 셀렉터 키 | CSS 셀렉터 |
|-----------|-----------|
| `campaign_name` | `input[name="campaignName"], input#campaignName, input[placeholder*="캠페인"]` |
| `participation_guide` | `textarea[name="participationGuide"], textarea#participationGuide, textarea[placeholder*="참여"]` |
| `keywords` | `input[name="keywords"], input#keywords, textarea[name="keywords"], input[placeholder*="키워드"]` |
| `hint` | `input[name="hint"], input#hint, input[placeholder*="힌트"], textarea[name="hint"]` |
| `walking_steps` | `input[name="walkingSteps"], input#walkingSteps, input[name="steps"], input[type="number"][placeholder*="걸음"]` |
| `submit_button` | `button[type="submit"]:has-text("등록"), button:has-text("캠페인 등록"), input[type="submit"][value*="등록"]` |
| `form_container` | `form.campaign-form, form#campaignForm, form[action*="campaign"]` |

### 6. 예외 클래스

| 예외 | 상황 |
|------|------|
| `SuperapCampaignError` | 캠페인 폼 관련 에러 |

## 생성/수정된 파일

| 파일 | 상태 | 설명 |
|------|------|------|
| `backend/app/services/superap.py` | 수정 | 캠페인 폼 기능 추가 |
| `backend/tests/test_superap_campaign.py` | 신규 | 캠페인 폼 테스트 (12개) |
| `docs/selectors/SUPERAP_CAMPAIGN_SELECTORS.md` | 신규 | 캠페인 셀렉터 문서 |
| `docs/handover/PHASE2_TASK5_DEV.md` | 신규 | 본 문서 |

## 테스트 현황

| 테스트 파일 | 테스트 수 | 상태 |
|-------------|----------|------|
| test_superap_campaign.py | 12 | 12 passed |
| test_superap.py | 31 | 30 passed, 1 integration |
| test_naver_map.py | 51 | 46 passed, 5 integration |
| test_excel_parser.py | 17 | passed |
| test_upload_api.py | 13 | passed |
| test_health.py | 2 | passed |
| test_models.py | 10 | passed |
| test_relationships.py | 8 | passed |
| **총합** | **144** | **138 passed** |

### 신규 테스트 상세

#### TestCampaignFormData (9개)
- 상호명 템플릿 치환
- 명소명 템플릿 치환
- 상호명+명소명 동시 치환
- 키워드 255자 미만
- 키워드 255자 초과
- 빈 키워드 처리
- 키워드 개수 카운트
- 키워드 공백 제거

#### TestCampaignFormResult (2개)
- 기본값 확인
- 값 설정 확인

#### TestCampaignSelectors (2개)
- 캠페인 셀렉터 정의 확인
- 캠페인 URL 정의 확인

## 사용 예시

```python
from app.services.superap import SuperapController, CampaignFormData

async with SuperapController(headless=True) as controller:
    # 1. 로그인
    await controller.login(
        account_id="user1",
        username="myid",
        password="mypassword"
    )

    # 2. 폼 데이터 생성
    form_data = CampaignFormData(
        campaign_name="테스트 캠페인",
        place_name="맛있는식당",
        landmark_name="서울타워",
        participation_guide="&명소명&에서 &상호명&까지 걸어오세요",
        keywords=["키워드1", "키워드2", "키워드3"],
        hint="힌트 메시지",
        walking_steps=1000,
    )

    # 3. 폼 입력 (제출 X)
    result = await controller.fill_campaign_form(
        account_id="user1",
        form_data=form_data,
        take_screenshot=True,
    )

    if result.success:
        print(f"입력된 필드: {result.filled_fields}")
        print(f"스크린샷: {result.screenshot_path}")
    else:
        print(f"에러: {result.errors}")
```

## 의존성

### Task 2.4 의존성
- `login()` → 로그인 상태 확보
- `get_page()` → 로그인된 페이지 반환

### 다른 모듈 연동
- Task 2.2 `select_random_landmark_name()` → `landmark_name` 제공
- Task 2.3 `get_walking_steps()` → `walking_steps` 제공

## 알려진 이슈

### 1. 실제 셀렉터 검증 필요

현재 셀렉터는 일반적인 패턴 기반으로 정의되었습니다.
실제 superap.io 캠페인 등록 페이지에서 셀렉터 검증이 필요합니다.

### 2. 추가 필드 가능성

실제 캠페인 등록 폼에 더 많은 필드가 있을 수 있습니다.
추후 필드 추가 시 `CAMPAIGN_SELECTORS`와 `fill_campaign_form()` 확장 필요.

## 다음 Task 준비사항

### Task 2.6: 캠페인 등록 확장

가능한 추가 기능:
- 캠페인 타입 선택 (트래픽/저장하기)
- 플레이스 URL 입력
- 날짜/시간 설정
- 예산 설정
- 등록 확인 및 검증
