# Claude Code 프롬프트 - 퀀텀 캠페인 자동화 시스템

## 프로젝트 컨텍스트

당신은 "퀀텀 캠페인 자동화 시스템" 개발을 담당합니다. 이 시스템은 superap.io(퀀텀) 리워드 광고 플랫폼에서 네이버 플레이스 캠페인을 대량으로 등록하고, 일일 키워드를 자동으로 교체하는 자동화 도구입니다.

---

## 1. 시스템 개요

### 핵심 워크플로우
```
[엑셀 업로드] → [미리보기/수정] → [캠페인 자동 등록] → [일일 키워드 자동 교체]
```

### 주요 기능
1. 엑셀 파일로 캠페인 정보 대량 업로드
2. 네이버 플레이스에서 주변 명소 추출 & 도보 걸음수 계산
3. superap.io에 캠페인 자동 등록
4. 일일소진/23:50 시점 키워드 자동 교체
5. 캠페인 현황 대시보드 (계정별 탭)

---

## 2. 엑셀 양식 구조

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| 대행사명 | 정산용 구분자 | 일류마케팅 |
| 사용자ID | superap.io 로그인 계정 | 월보장 일류기획 |
| 시작일 | 캠페인 시작일 | 2026-02-04 |
| 마감일 | 캠페인 종료일 | 2026-02-10 |
| 일일 한도 | 일 작업량 | 300 |
| 키워드 | `,` 구분 키워드 풀 | 마포 곱창,마포 맛집,... |
| 플레이스 상호명 | 타겟 업체명 | 일류곱창 마포공덕본점 |
| 플레이스 URL | 네이버 플레이스 URL | https://m.place.naver.com/restaurant/1724563569 |
| 타입구분 | 캠페인 타입 | 트래픽 또는 저장하기 |

---

## 3. 캠페인 등록 상세 플로우

### 3.1 명소 추출 (네이버 플레이스)
```
1. 플레이스 URL 접속
2. '주변' 탭 클릭
3. 명소 목록에서 1~3번째 중 랜덤 선택
4. 선택된 명소명 저장
```

### 3.2 걸음수 계산 (네이버 지도)
```
URL: https://map.naver.com/p/directions/-/-/-/walk?c=15.00,0,0,0,dh

1. 출발지: 선택된 명소명
2. 도착지: 플레이스 상호명
3. '추천' 기준 도보 경로의 걸음수 추출
4. 콤마 제거 후 숫자만 저장 (이것이 정답)
```

### 3.3 superap.io 캠페인 등록

#### 등록 페이지 접근
```
1. https://superap.io 로그인 (사용자ID로)
2. 오른쪽 상단 '캠페인 등록' 클릭
```

#### 필드 입력 (왼쪽 패널)
```
- 캠페인 이름: "[지역] [상호명] 퀴즈 맞추기" 형식
- 참여 방법 설명: 타입별 템플릿 사용 (치환 필요)
  - &상호명& → 실제 플레이스 상호명
  - &명소명& → 추출된 명소명
- 검색키워드: 255자 이내 랜덤 조합
- 정답 맞추기 힌트: 템플릿에서 가져옴
- 소재 이미지: 템플릿에서 가져옴
```

#### 필드 입력 (오른쪽 패널)
```
- 링크: '+' 버튼으로 3개 슬롯 추가, 각 링크 입력
  - 링크 끝에 해시태그 자동 추가 (#cpc_detail_place)
  
- 캠페인 타입 선택:
  - 트래픽 → '퀴즈 맞추기' 섹션의 '플레이스 퀴즈' 선택
  - 저장하기 → '플레이스' 섹션의 '검색 후 정답 입력' 선택

- 날짜 설정:
  - 시작일: 엑셀의 시작일 (YYYY-MM-DD 00:00:00)
  - 종료일: 엑셀의 마감일 (YYYY-MM-DD 23:59:59)
  ⚠️ 중요: '+7일' 같은 버튼 클릭 시에만 23:59:59가 자동 세팅됨
            수기 입력 시 시간이 제대로 안 됨 → 버튼 동작 분석 필요

- 전체 한도: (마감일 - 시작일 + 1) × 일일 한도
- 일일 한도: 엑셀의 일일 한도

- 전환 인식 기준(텍스트): 걸음수 (콤마 없이 숫자만)
```

#### 등록 완료
```
- 오른쪽 하단 '등록' 버튼 클릭
- 생성된 캠페인 번호 추출하여 DB 저장
```

---

## 4. 자동 키워드 교체 로직

### 4.1 트리거 조건
```python
# 조건 A: 상태가 '일일소진'
if campaign.status == 'daily_exhausted':
    rotate_keywords(campaign)

# 조건 B: 상태가 '진행중' AND 현재시간 >= 23:50
if campaign.status == 'active' and now.time() >= time(23, 50):
    rotate_keywords(campaign)
    # DB 업데이트 시간은 23:50:00으로 고정 (날짜 밀림 방지)
```

### 4.2 키워드 교체 절차
```
1. superap.io에서 해당 캠페인 클릭
2. 오른쪽 상단 '수정' 버튼 클릭
3. '검색키워드:' 필드에서:
   - 기존 사용 키워드 제외
   - 미사용 키워드 중 랜덤 선택
   - 255자 이내로 조합 (단어 중간에 잘리면 그 앞까지만)
4. '등록' 버튼 클릭
5. DB에 최근 키워드 변경 일자 업데이트
```

### 4.3 키워드 조합 규칙
```python
def select_keywords(available_keywords: list, max_chars: int = 255) -> str:
    """
    - 콤마(,)와 띄어쓰기 포함하여 255자 제한
    - 단어가 중간에 잘리면 그 앞 단어까지만 포함
    - 사용된 키워드는 제외
    """
    random.shuffle(available_keywords)
    result = []
    current_length = 0
    
    for kw in available_keywords:
        # 첫 키워드는 콤마 없음, 이후는 콤마 추가
        separator_len = 1 if result else 0
        total_add = len(kw) + separator_len
        
        if current_length + total_add <= max_chars:
            result.append(kw)
            current_length += total_add
        else:
            break  # 넘으면 추가 안 함 (중간 짤림 방지)
    
    return ','.join(result)
```

---

## 5. 캠페인 타입별 템플릿

### 5.1 트래픽 타입
```
[참여방법]
{{image|https://i.ibb.co/DgVqGSnW/image.png}}

1. 하단의 검색키워드 복사 후 미션페이지 클릭
2. 네이버 홈에서 키워드 붙여 넣어 검색 후 1~2페이지내에 있는 [&상호명&] 클릭
3. 플레이스에서 [지도] 탭 클릭 → [지도앱으로 보기] 버튼 클릭
4. 플레이스 탭에서 [도착] 버튼 클릭
5. 출발지를 [&명소명&]으로 설정 후 [도보] 설정 후 [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다.
```

**캠페인 타입 선택**: 퀴즈 맞추기 > 플레이스 퀴즈

### 5.2 저장하기 타입
```
참여 방법:
{{image|https://i.ibb.co/RGW629jv/image.png}}

1. 하단의 검색키워드 복사 후 미션페이지 클릭
2. 네이버 홈에서 키워드 붙여 넣어 검색 후 1~2페이지내에 있는 [&상호명&] 클릭
3. 플레이스에서 [지도] 탭 클릭 → [지도앱으로 보기] 버튼 클릭
4. 저장하기 버튼 클릭하여 완료한 후 [도착] 버튼 클릭
5. 출발지를 [&명소명&]으로 설정 후 [도보] 설정 후 [가장빠른] 걸음 수 맞추기

[주의사항]
이미 참여한 이력이 있다면 리워드가 지급되지 않을 수 있습니다.
WIFI가 아닌 환경에서는 데이터 이용료가 발생할 수 있습니다.
```

**캠페인 타입 선택**: 플레이스 > 검색 후 정답 입력

### 5.3 정답 맞추기 힌트 (공통)
```
참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수 맞추기
```

### 5.4 링크 목록 (공통)
```
1. https://nid.naver.com/nidlogin/login?mode=form&url=https%3A%2F%2Fm.naver.com%2F#cpc_detail_place
2. https://link.naver.com/bridge?url=https%3A%2F%2Fm.naver.com%2Fdst=naversearchapp%3A%2F%2Finappbrowser%3Fun%3Dhttps%253A%252F%252Fm%252Enaver%252Ecom%252F%26version...#cpc_detail_place
3. https://app.map.naver.com/launchApp/map?tab=discovery#cpc_detail_place
```

---

## 6. 웹사이트 분석 지침 (중요!)

### 6.1 superap.io 분석 필수 항목

#### A. 계정 판별 메커니즘 분석 (⚠️ 최우선)
```
⚠️ 발견된 이슈:
같은 기기에서 다른 브라우저로 다른 계정 로그인 시
캠페인이 해당 계정으로 세팅되는 현상

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 필수 테스트 케이스 (순서대로 진행)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

테스트 목적: superap.io가 "어떤 계정의 캠페인인지"를 판별하는 기준 파악

[테스트 1] 쿠키/세션 기반 여부
- 계정A 로그인 → 캠페인 등록 폼 진입
- 새 시크릿 창에서 계정B 로그인 → 캠페인 등록
- 결과: 각각 올바른 계정에 등록되는가?

[테스트 2] IP 기반 여부  
- 계정A 로그인 (IP: 1.1.1.1) → 캠페인 등록
- 계정B 로그인 (같은 IP: 1.1.1.1, 다른 브라우저) → 캠페인 등록
- 결과: 어떤 계정에 등록되는가?

[테스트 3] User-Agent 기반 여부
- 계정A 로그인 (Chrome UA)
- 계정B 로그인 (같은 IP, Firefox UA)
- 결과: UA로 구분 가능한가?

[테스트 4] 기기 Fingerprint 기반 여부
- 프록시로 IP 변경 후 계정A 로그인
- 동일 기기에서 다른 IP로 계정B 로그인  
- 결과: IP가 달라도 같은 계정으로 인식되는가?

[테스트 5] API 레벨 확인
- 캠페인 등록 시 네트워크 탭 확인
- 요청 헤더/바디에 계정 식별 정보가 있는가?
- Authorization 토큰? 세션 ID? 별도 파라미터?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 테스트 결과 기록 양식
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| 테스트 | 조건 | 예상 계정 | 실제 등록된 계정 | 판별 기준 추정 |
|--------|------|-----------|------------------|----------------|
| 1      | ... | A | ? | |
| 2      | ... | B | ? | |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 결과별 대응 방안
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IF 쿠키/세션 기반:
  → Playwright 브라우저 컨텍스트 분리로 해결
  
IF IP 기반:
  → 계정별 프록시 할당 필요
  → 또는 순차 처리 (한 계정 완료 후 다음 계정)

IF Fingerprint 기반:
  → Playwright fingerprint 스푸핑 필요
  → playwright-extra + stealth plugin 검토

IF API 토큰 기반:
  → 가장 깔끔. 요청 시 토큰만 바꾸면 됨
  → API 직접 호출 방식으로 전환 검토
```

#### B. 동시 업로드 충돌 테스트 (⚠️ 필수)
```
⚠️ 시나리오:
한 계정(계정A)에 캠페인 10개를 동시에 등록해야 하는 상황

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 테스트 케이스
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[테스트 1] 순차 등록 (기본)
- 캠페인1 등록 완료 → 캠페인2 등록 시작 → ...
- 결과: 정상 동작 확인 (기준점)

[테스트 2] 병렬 등록 - 같은 세션
- 탭1: 캠페인1 폼 작성 중
- 탭2: 캠페인2 폼 작성 시작
- 결과: 폼 데이터 충돌? 덮어쓰기?

[테스트 3] 병렬 등록 - 다른 세션 (같은 계정)
- 브라우저1: 계정A 로그인 → 캠페인1 등록
- 브라우저2: 계정A 로그인 → 캠페인2 동시 등록
- 결과: 둘 다 정상 등록? 하나만 등록?

[테스트 4] 등록 중 수정 충돌
- 브라우저1: 캠페인1 등록 중 (폼 작성)
- 브라우저2: 기존 캠페인X 수정 중
- 결과: 서로 영향 있는가?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 결과별 아키텍처 결정
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IF 병렬 가능 (세션 독립):
  → 계정별 워커 프로세스 병렬 실행
  → 처리 속도 ↑
  
IF 순차만 가능 (세션 공유):
  → 계정별 큐 시스템 구현
  → 한 계정의 작업은 순차 처리
  → 다른 계정은 병렬 가능
  
  예시:
  ┌─────────────────────────────────────┐
  │ 계정A 큐: [캠페인1] → [캠페인2] → [캠페인3] │ ← 순차
  │ 계정B 큐: [캠페인4] → [캠페인5]           │ ← 순차
  └─────────────────────────────────────┘
        ↑ 계정A와 계정B는 병렬 가능

IF API 직접 호출 가능:
  → 웹 자동화 대신 API 호출
  → 병렬 처리 제한 없음 (Rate limit만 준수)
```

#### B. 날짜 설정 필드 동작
```
⚠️ 발견된 이슈:
'+7일', '+15일', '+30일' 버튼 클릭 시 → 23:59:59 자동 세팅
수기 입력 시 → 시간이 제대로 반영 안 됨

분석해야 할 것:
1. 버튼 클릭 시 트리거되는 JavaScript 함수 확인
2. 날짜 필드의 실제 값 전송 방식 (hidden field 여부)
3. API 호출 시 날짜 포맷 확인
4. 버튼 없이 23:59:59 세팅하는 방법 (직접 JS 실행 등)
```

#### C. 캠페인 등록 폼 분석
```
확인해야 할 것:
1. 각 입력 필드의 name/id/selector
2. 필수 입력 검증 로직
3. 등록 API 엔드포인트 및 요청 페이로드
4. 성공/실패 응답 구조
5. 생성된 캠페인 번호 추출 위치
```

#### D. 캠페인 상태 값
```
캠페인 목록에서 확인되는 상태:
- 진행중 (파란색)
- 일일소진 (노란색)
- 캠페인소진 (분홍색)

확인해야 할 것:
1. 상태 값을 가져오는 API 또는 DOM 위치
2. 상태 변경 감지 방법 (폴링 주기)
3. 전환수(현재/최대) 추출 위치
```

### 6.2 네이버 지도 분석

#### A. 주변 명소 추출
```
URL: 플레이스 페이지 > '주변' 탭

확인해야 할 것:
1. '주변' 탭 클릭 selector
2. 명소 목록 DOM 구조
3. 명소 1~3번째 선택 로직
```

#### B. 도보 걸음수 추출
```
URL: https://map.naver.com/p/directions/-/-/-/walk

확인해야 할 것:
1. 출발지/도착지 입력 selector
2. '추천' 경로 선택 방법
3. 걸음수 텍스트 위치 및 파싱 로직
```

---

## 7. 데이터베이스 스키마

```sql
-- 계정 관리
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    user_id VARCHAR(100) UNIQUE NOT NULL,
    password_encrypted TEXT,
    agency_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 캠페인 타입 템플릿
CREATE TABLE campaign_templates (
    id INTEGER PRIMARY KEY,
    type_name VARCHAR(50) UNIQUE NOT NULL,  -- '트래픽', '저장하기'
    description_template TEXT NOT NULL,
    hint_text TEXT NOT NULL,
    campaign_type_selection VARCHAR(100),
    links JSON NOT NULL,
    hashtag VARCHAR(100),
    image_url_200x600 TEXT,
    image_url_720x780 TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 캠페인 목록
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY,
    campaign_code VARCHAR(20),
    account_id INTEGER REFERENCES accounts(id),
    agency_name VARCHAR(100),
    place_name VARCHAR(200) NOT NULL,
    place_url TEXT NOT NULL,
    campaign_type VARCHAR(50) NOT NULL,
    registered_at TIMESTAMP,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    daily_limit INTEGER NOT NULL,
    total_limit INTEGER,
    current_conversions INTEGER DEFAULT 0,
    landmark_name VARCHAR(200),
    step_count INTEGER,
    original_keywords TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    last_keyword_change TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 키워드 풀 (캠페인별)
CREATE TABLE keyword_pool (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    keyword VARCHAR(255) NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP,
    UNIQUE(campaign_id, keyword)
);
```

---

## 8. 관리자 웹 기능 요구사항

### 8.1 대시보드
- 계정별 탭 구분
- 캠페인 목록 테이블:
  - 캠페인 번호, 상호명, 상태, 전환수(현재/최대), 작업 O일째
  - 키워드 잔량 표시 (🟢충분/🟡주의/🔴부족)
  - 최근 키워드 변경 시간
- 대행사별 필터링

### 8.2 엑셀 업로드
- 파일 업로드 → 파싱 → 미리보기 테이블
- **등록 전 수정 가능**:
  - 참여 방법 설명
  - 검색 키워드
  - 정답 맞추기 힌트
  - 링크 추가/제거 (URL만 입력 → 해시태그 자동 추가)
- 최종 등록 버튼

### 8.3 등록 후 수정
- **오직 '유입 키워드 추가'만 가능**
- 키워드 추가 시:
  - 기존 접수된 키워드와 중복 체크
  - 새 키워드만 '세팅 가능 키워드' 풀에 추가

### 8.4 템플릿 관리
- 캠페인 타입별 템플릿 CRUD
- 참여 방법 설명, 힌트, 링크들 수정
- 실시간 반영

---

## 9. 기술 스택

- **Backend**: Python FastAPI
- **Frontend**: React + TypeScript + TailwindCSS
- **Database**: SQLite (초기) → PostgreSQL (확장)
- **Web Automation**: Playwright
- **Scheduler**: APScheduler
- **Deployment**: Oracle Cloud ARM64

---

## 10. 개발 우선순위

### Phase 1: 기반 (1주)
1. 프로젝트 초기 세팅
2. DB 스키마 구현
3. **superap.io 웹 구조 분석** ← 여기서 위의 분석 항목들 확인
4. 계정 관리 기능

### Phase 2: 핵심 자동화 (2주)
1. 엑셀 파싱 모듈
2. 네이버맵 스크래핑 (명소 + 걸음수)
3. superap.io 캠페인 등록 자동화
4. 키워드 조합 로직

### Phase 3: 대시보드 (1주)
1. 캠페인 목록 UI
2. 계정별 탭
3. 키워드 잔량 경고

### Phase 4: 키워드 자동 교체 (1주)
1. 상태 모니터링 스케줄러
2. 일일소진/23:50 감지
3. 키워드 자동 교체 실행

---

## 11. 주의사항

1. **브라우저 컨텍스트 격리**: 계정별로 독립된 브라우저 세션 유지
2. **Rate Limiting**: superap.io 요청 간 적절한 딜레이 (1-2초)
3. **에러 핸들링**: 네트워크 오류, 요소 미발견 시 재시도 로직
4. **로깅**: 모든 자동화 작업 상세 로깅 (디버깅용)
5. **날짜 밀림 방지**: 23:50 교체 시 DB 시간은 고정값 사용
