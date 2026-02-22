# superap.io 캠페인 등록 셀렉터 문서

## 개요

superap.io 캠페인 등록 폼 자동화를 위한 CSS 셀렉터 문서입니다.

## 분석 일자

2026-02-04

## 테스트 URL

```
https://superap.io/service/reward/adver/campaign/create
```

## 캠페인 등록 폼

### 1. 폼 컨테이너

```css
form.campaign-form, form#campaignForm, form[action*="campaign"]
```

### 2. 입력 필드

#### 캠페인명 (campaign_name)

```css
input[name="campaignName"], input#campaignName, input[placeholder*="캠페인"]
```

| 속성 | 값 | 설명 |
|------|-----|------|
| type | text | 텍스트 입력 |
| name | campaignName | 필드명 |
| 필수 | O | 캠페인 이름 |

#### 참여 안내문 (participation_guide)

```css
textarea[name="participationGuide"], textarea#participationGuide, textarea[placeholder*="참여"]
```

| 속성 | 값 | 설명 |
|------|-----|------|
| type | textarea | 멀티라인 텍스트 |
| name | participationGuide | 필드명 |
| 필수 | O | 참여 방법 안내 |

**템플릿 치환:**
- `&상호명&` → 실제 상호명으로 치환
- `&명소명&` → 실제 명소명으로 치환

예시:
```
&명소명&에서 &상호명&까지 걸어오세요
→ 서울타워에서 맛있는식당까지 걸어오세요
```

#### 검색 키워드 (keywords)

```css
input[name="keywords"], input#keywords, textarea[name="keywords"], input[placeholder*="키워드"]
```

| 속성 | 값 | 설명 |
|------|-----|------|
| type | text / textarea | 텍스트 입력 |
| name | keywords | 필드명 |
| 최대 길이 | 255자 | 콤마로 구분된 키워드 |

**키워드 처리 규칙:**
- 키워드는 콤마(`, `)로 구분
- 전체 길이가 255자를 초과하면 마지막 키워드부터 제외
- 빈 키워드는 자동 제거
- 키워드 앞뒤 공백 자동 제거

예시:
```
키워드1, 키워드2, 키워드3
```

#### 힌트 (hint)

```css
input[name="hint"], input#hint, input[placeholder*="힌트"], textarea[name="hint"]
```

| 속성 | 값 | 설명 |
|------|-----|------|
| type | text / textarea | 텍스트 입력 |
| name | hint | 필드명 |
| 필수 | O | 참여자에게 보여질 힌트 |

#### 걸음 수 (walking_steps)

```css
input[name="walkingSteps"], input#walkingSteps, input[name="steps"], input[type="number"][placeholder*="걸음"]
```

| 속성 | 값 | 설명 |
|------|-----|------|
| type | number | 숫자 입력 |
| name | walkingSteps | 필드명 |
| 필수 | O | 도보 걸음 수 |

### 3. 버튼

#### 등록 버튼 (submit_button)

```css
button[type="submit"]:has-text("등록"), button:has-text("캠페인 등록"), input[type="submit"][value*="등록"]
```

| 속성 | 값 | 설명 |
|------|-----|------|
| type | submit | 제출 버튼 |
| text | 등록 / 캠페인 등록 | 버튼 텍스트 |

**주의:** `fill_campaign_form()` 메서드는 이 버튼을 클릭하지 않습니다.
제출은 별도의 `submit_campaign()` 메서드를 사용해야 합니다.

## 데이터 클래스

### CampaignFormData

캠페인 폼 입력 데이터를 담는 데이터 클래스입니다.

```python
from app.services.superap import CampaignFormData

form_data = CampaignFormData(
    campaign_name="테스트 캠페인",
    place_name="맛있는식당",         # 상호명
    landmark_name="서울타워",        # 명소명
    participation_guide="&명소명&에서 &상호명&까지 걸어오세요",
    keywords=["키워드1", "키워드2", "키워드3"],
    hint="힌트 메시지",
    walking_steps=1000,
)

# 템플릿 치환된 안내문
print(form_data.processed_guide)
# 출력: "서울타워에서 맛있는식당까지 걸어오세요"

# 255자 제한 적용된 키워드
print(form_data.processed_keywords)
# 출력: "키워드1, 키워드2, 키워드3"

# 키워드 개수
print(form_data.get_keywords_count())
# 출력: 3
```

### CampaignFormResult

폼 입력 결과를 담는 데이터 클래스입니다.

```python
from app.services.superap import CampaignFormResult

# 성공 결과
result = CampaignFormResult(
    success=True,
    screenshot_path="/path/to/screenshot.png",
    filled_fields=["campaign_name", "keywords", "hint", "walking_steps"],
    errors=[],
)

# 실패 결과
result = CampaignFormResult(
    success=False,
    errors=["campaign_name 필드를 찾을 수 없습니다"],
)
```

## 사용 예시

### Python (Playwright)

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
        keywords=["키워드1", "키워드2"],
        hint="힌트",
        walking_steps=1000,
    )

    # 3. 폼 입력 (제출 X)
    result = await controller.fill_campaign_form(
        account_id="user1",
        form_data=form_data,
        take_screenshot=True,
    )

    if result.success:
        print(f"입력 완료: {result.filled_fields}")
        print(f"스크린샷: {result.screenshot_path}")
    else:
        print(f"입력 실패: {result.errors}")

    # 4. 별도로 제출 (필요한 경우)
    # submit_result = await controller.submit_campaign("user1")
```

## 셀렉터 상수 위치

파일: `backend/app/services/superap.py`

```python
class SuperapController:
    CAMPAIGN_SELECTORS = {
        "campaign_name": 'input[name="campaignName"], input#campaignName, input[placeholder*="캠페인"]',
        "participation_guide": 'textarea[name="participationGuide"], textarea#participationGuide, textarea[placeholder*="참여"]',
        "keywords": 'input[name="keywords"], input#keywords, textarea[name="keywords"], input[placeholder*="키워드"]',
        "hint": 'input[name="hint"], input#hint, input[placeholder*="힌트"], textarea[name="hint"]',
        "walking_steps": 'input[name="walkingSteps"], input#walkingSteps, input[name="steps"], input[type="number"][placeholder*="걸음"]',
        "submit_button": 'button[type="submit"]:has-text("등록"), button:has-text("캠페인 등록"), input[type="submit"][value*="등록"]',
        "form_container": 'form.campaign-form, form#campaignForm, form[action*="campaign"]',
    }

    CAMPAIGN_CREATE_URL = "https://superap.io/service/reward/adver/campaign/create"
```

## 폴백 셀렉터 전략

각 필드는 여러 대체 셀렉터를 콤마로 구분하여 지정합니다.
Playwright는 첫 번째 매칭되는 요소를 사용합니다.

```
input[name="campaignName"], input#campaignName, input[placeholder*="캠페인"]
```

1. `input[name="campaignName"]` - name 속성으로 검색
2. `input#campaignName` - id 속성으로 검색
3. `input[placeholder*="캠페인"]` - placeholder 속성으로 검색

## 주의사항

### 1. 로그인 필수

캠페인 등록 페이지는 로그인 후에만 접근 가능합니다.

```python
# 먼저 로그인 확인
if not await controller.check_login_status("user1"):
    await controller.login("user1", "username", "password")
```

### 2. 페이지 재사용

superap.io는 새 탭에서 세션이 유지되지 않으므로, 로그인된 페이지를 재사용합니다.

```python
# 로그인된 페이지 가져오기
page = await controller.get_page("user1")
```

### 3. 스크린샷 검증

폼 입력 후 스크린샷을 저장하여 입력 내용을 검증할 수 있습니다.

```python
result = await controller.fill_campaign_form(
    account_id="user1",
    form_data=form_data,
    take_screenshot=True,  # 스크린샷 저장
)
# 스크린샷 경로: screenshots/campaigns/user1_YYYYMMDD_HHMMSS.png
```

### 4. 제출 분리

`fill_campaign_form()`은 폼 입력만 수행하고 제출하지 않습니다.
실제 등록은 `submit_campaign()` 메서드를 별도로 호출해야 합니다.

```python
# 폼 입력만 (검토용)
result = await controller.fill_campaign_form("user1", form_data)

# 검토 후 제출
# submit_result = await controller.submit_campaign("user1")
```

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-04 | 최초 작성 - 캠페인 등록 폼 셀렉터 |
