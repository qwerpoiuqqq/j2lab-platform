# 네이버 지도 길찾기 셀렉터 문서

## 개요

네이버 지도 데스크톱 페이지(`map.naver.com`)에서 도보 경로 검색 및 걸음수 추출을 위한 CSS 셀렉터 문서입니다.

## 분석 일자

2026-02-04

## 테스트 URL

```
https://map.naver.com/p/directions/-/-/-/walk?c=15.00,0,0,0,dh
```

## URL 구조

### 길찾기 페이지 기본 URL
```
https://map.naver.com/p/directions/{출발지}/{도착지}/{경유지}/{이동수단}
```

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| 출발지 | 출발지 좌표/ID | `-` (미입력) |
| 도착지 | 도착지 좌표/ID | `-` (미입력) |
| 경유지 | 경유지 (선택) | `-` (없음) |
| 이동수단 | 이동 방법 | `walk`, `car`, `transit`, `bicycle` |

### 쿼리 파라미터
| 파라미터 | 설명 |
|---------|------|
| `c` | 지도 카메라 설정 (줌, 회전 등) |

## 셀렉터 목록

### 1. 검색 입력 필드

#### 출발지 입력
```css
.search_input_box_wrap.start input.input_search
```

#### 도착지 입력
```css
.search_input_box_wrap.goal input.input_search
```

**HTML 구조:**
```html
<div class="search_input_box_wrap start">
  <div class="input_box search_input">
    <label for="input_search«r6»" class="label_search">출발지 입력</label>
    <input id="input_search«r6»" class="input_search"
           autocomplete="off" maxlength="255"
           role="combobox" type="text" value="">
  </div>
</div>
```

### 2. 자동완성 결과

#### 자동완성 리스트 아이템
```css
li.item_place div.link_place
```

**HTML 구조:**
```html
<li role="none" class="item_place">
  <div id="«r8»" role="option" tabindex="-1"
       class="link_place" aria-selected="false">
    <!-- 장소 정보 -->
  </div>
</li>
```

**사용 예시:**
```python
autocomplete = page.locator('li.item_place div.link_place').first
await autocomplete.click()
```

### 3. 버튼

#### 길찾기 버튼
```css
button.btn_direction.search
```

#### 다시입력 버튼
```css
button.btn_direction.refresh
```

#### 경유지 추가 버튼
```css
button.btn_direction.via
```

**HTML 구조:**
```html
<div class="search_btn_area">
  <button type="button" class="btn_direction refresh">다시입력</button>
  <button type="button" class="btn_direction via">경유지</button>
  <button type="button" class="btn_direction search">길찾기</button>
</div>
```

### 4. 걸음수 결과

#### 걸음수 값 (숫자)
```css
.walk_direction_value
```

#### 걸음수 단위
```css
.walk_direction_unit
```

#### 걸음수 정보 컨테이너
```css
.walk_direction_info
```

**HTML 구조:**
```html
<span class="walk_direction_info">
  <span class="walk_direction_value">789</span>
  <span class="walk_direction_unit">걸음</span>
</span>
```

**파싱 예시:**
```python
steps_text = await page.locator('.walk_direction_value').first.inner_text()
# "789" -> int(789)
# "1,234" -> int(1234) (콤마 제거 필요)
```

### 5. 이동수단 탭

#### 탭 컨테이너
```css
ul.StyledSearchTabs-sc-1m406fl-0[role="tablist"]
```

#### 개별 탭 (대중교통, 자동차, 도보, 자전거)
```css
li.item_search_tab button.btn_search_tab
```

#### 활성화된 탭
```css
li.item_search_tab.active button.btn_search_tab
```

## 브라우저 설정

### 데스크톱 뷰포트
```python
DESKTOP_VIEWPORT = {"width": 1280, "height": 900}
```

### User-Agent
```python
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
```

## 주의사항

### 1. 데스크톱 vs 모바일

길찾기 페이지는 **데스크톱 환경**에서만 정상 작동합니다.
- 모바일 User-Agent/Viewport 사용 시 DOM 구조가 다름
- 별도의 데스크톱 context 생성 필요

```python
# 데스크톱 전용 context 생성
desktop_context = await browser.new_context(
    viewport={"width": 1280, "height": 900},
    user_agent=DESKTOP_USER_AGENT,
    locale="ko-KR",
)
```

### 2. 자동완성 대기

입력 후 자동완성 결과가 나타나기까지 시간이 필요합니다.

```python
await start_input.fill("서울역")
await page.wait_for_timeout(1500)  # 자동완성 대기

autocomplete = page.locator('li.item_place div.link_place').first
await autocomplete.wait_for(state="visible", timeout=5000)
await autocomplete.click()
```

### 3. 경로 검색 결과 대기

길찾기 버튼 클릭 후 결과가 로딩되기까지 대기가 필요합니다.

```python
await search_btn.click()
await page.wait_for_timeout(3000)  # 결과 대기

steps_element = page.locator('.walk_direction_value').first
await steps_element.wait_for(state="visible", timeout=10000)
```

### 4. 걸음수 파싱

걸음수는 천 단위 콤마가 포함될 수 있습니다.

```python
def parse_steps(steps_text: str) -> int:
    # "1,234" -> 1234
    cleaned = re.sub(r"[^\d,]", "", steps_text)
    cleaned = cleaned.replace(",", "")
    return int(cleaned)
```

## 에러 케이스

| 상황 | 처리 |
|------|------|
| 출발지 검색 결과 없음 | 자동완성 대기 타임아웃 |
| 도착지 검색 결과 없음 | 자동완성 대기 타임아웃 |
| 도보 경로 없음 | 걸음수 요소 없음 |
| 네트워크 오류 | 페이지 로딩 타임아웃 |

## 구현 코드 참조

- 파일: `backend/app/services/naver_map.py`
- 클래스: `NaverMapScraper`
- 메서드: `get_walking_steps()`, `parse_steps()`
- 셀렉터 상수: `NaverMapScraper.SELECTORS`

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-04 | 최초 작성 |
