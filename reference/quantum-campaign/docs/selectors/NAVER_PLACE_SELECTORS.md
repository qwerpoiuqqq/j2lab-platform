# 네이버 플레이스 셀렉터 문서

## 개요

네이버 플레이스 모바일 페이지(`m.place.naver.com`)에서 주변 명소를 추출하기 위한 CSS 셀렉터 문서입니다.

## 분석 일자

2026-02-04

## 테스트 URL

```
https://m.place.naver.com/restaurant/1724563569
https://m.place.naver.com/restaurant/1724563569/around
```

## URL 구조

### 플레이스 페이지 기본 URL
```
https://m.place.naver.com/{category}/{place_id}
```

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| category | 장소 카테고리 | `restaurant`, `cafe`, `place` |
| place_id | 고유 장소 ID | `1724563569` |

### 탭 URL 패턴
```
https://m.place.naver.com/{category}/{place_id}/{tab}
```

| 탭 | URL 경로 | 설명 |
|----|---------|------|
| 홈 | `/home` | 기본 정보 |
| 소식 | `/feed` | 업체 소식 |
| 메뉴 | `/menu` | 메뉴 정보 |
| 예약 | `/booking` | 예약 기능 |
| 리뷰 | `/review` | 방문자 리뷰 |
| 사진 | `/photo` | 사진 갤러리 |
| 위치 | `/location` | 지도 및 위치 |
| **주변** | `/around` | **주변 장소 (타겟)** |
| 정보 | `/information` | 상세 정보 |

## 셀렉터 목록

### 1. 탭 메뉴

#### 주변 탭 (텍스트 기반)
```css
a[role="tab"]:has-text("주변")
```

#### 주변 탭 (href 기반)
```css
a[href*="/around"]
```

**사용 예시:**
```python
nearby_tab = await page.query_selector('a[role="tab"]:has-text("주변")')
await nearby_tab.click()
```

### 2. 주변 장소 목록

#### 리스트 컨테이너
```css
ul.eDFz9
```

#### 리스트 아이템 (개별 장소)
```css
li.S0Ns3
```

#### 장소 이름
```css
span.xBZDS
```

#### 장소 링크
```css
a.place_bluelink
a.OiGhS
```

**복합 셀렉터:**
```css
a.place_bluelink, a.OiGhS
```

### 3. 장소 카테고리
```css
span.LF32u
```

예시 값: `일식당`, `카페,디저트`, `한식당`

## HTML 구조

```html
<ul class="eDFz9">
  <li class="S0Ns3">
    <div class="YgcU0">
      <div class="on194">
        <a href="https://m.place.naver.com/place/12345?entry=par"
           role="button"
           class="place_bluelink OiGhS aKxn4">
          <span class="xBZDS">장소명</span>
          <span class="LF32u">카테고리</span>
        </a>
      </div>
      <div class="vzxNd hpbbP">
        <a href="..." role="button" class="zpGq2 aKxn4">
          <span class="iMW4a mOcpa">평점 정보</span>
          <span class="iMW4a">리뷰 수</span>
          <span class="iMW4a c_haf">거리 정보</span>
        </a>
      </div>
    </div>
    <div class="lazyload-wrapper">
      <!-- 이미지 영역 -->
    </div>
  </li>
  <!-- 추가 아이템... -->
</ul>
```

## 주의사항

### 광고 링크 필터링

일부 장소는 광고로 표시되며, 링크가 `ader.naver.com`으로 시작합니다.

**광고 링크 패턴:**
```
https://ader.naver.com/v1/...
```

**일반 링크 패턴:**
```
https://m.place.naver.com/place/{place_id}?entry=par
```

**필터링 코드:**
```python
if "m.place.naver.com" in href:
    # 일반 장소 링크
    pass
elif "ader.naver.com" in href:
    # 광고 링크 - 필터링 또는 별도 처리
    pass
```

### 동적 클래스명

네이버 플레이스는 CSS 클래스명이 빌드마다 변경될 수 있습니다. 주기적인 모니터링이 필요합니다.

| 클래스 | 역할 | 변경 가능성 |
|--------|------|------------|
| `eDFz9` | 리스트 컨테이너 | 높음 |
| `S0Ns3` | 리스트 아이템 | 높음 |
| `xBZDS` | 장소 이름 | 높음 |
| `place_bluelink` | 장소 링크 | 낮음 (의미 있는 이름) |
| `OiGhS` | 장소 링크 | 높음 |

### 권장 셀렉터 우선순위

1. **안정적**: `a[role="tab"]`, `role` 속성 기반
2. **중간**: `a.place_bluelink`, 의미 있는 클래스명
3. **불안정**: `ul.eDFz9`, 해시 기반 클래스명

## 브라우저 설정

### 모바일 뷰포트
```python
VIEWPORT = {"width": 375, "height": 812}
```

### User-Agent
```python
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
    "Mobile/15E148 Safari/604.1"
)
```

## 구현 코드 참조

- 파일: `backend/app/services/naver_map.py`
- 클래스: `NaverMapScraper`
- 셀렉터 상수: `NaverMapScraper.SELECTORS`

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-04 | 최초 작성 |
