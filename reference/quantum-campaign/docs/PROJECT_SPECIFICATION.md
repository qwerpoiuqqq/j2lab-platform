# 퀀텀 캠페인 자동화 시스템 - 프로젝트 설계서

## 1. 프로젝트 개요

### 1.1 목적
superap.io(퀀텀) 리워드 광고 캠페인의 대량 등록 및 일일 키워드 자동 교체 시스템

### 1.2 핵심 기능
1. **엑셀 기반 대량 캠페인 등록**
2. **네이버 플레이스 주변 명소 자동 추출 & 걸음수 계산**
3. **일일소진/23:50 키워드 자동 교체**
4. **캠페인 현황 대시보드 (계정별 탭)**

---

## 2. 시스템 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        관리자 웹 (Frontend)                       │
│                     React + TypeScript + TailwindCSS             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │엑셀 업로드│  │미리보기   │  │캠페인    │  │템플릿/링크 관리  │ │
│  │          │  │& 수정    │  │대시보드  │  │                  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │ REST API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend Server (FastAPI)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ API Router   │  │ Scheduler    │  │ Browser Manager        │ │
│  │ (FastAPI)    │  │ (APScheduler)│  │ (Playwright)           │ │
│  └──────────────┘  └──────────────┘  │ ┌────────────────────┐ │ │
│                                       │ │  Context Pool      │ │ │
│  ┌──────────────┐  ┌──────────────┐  │ │ ┌──┐ ┌──┐ ┌──┐    │ │ │
│  │ Naver Map    │  │ superap.io   │  │ │ │A │ │B │ │C │    │ │ │
│  │ Service      │  │ Controller   │  │ │ └──┘ └──┘ └──┘    │ │ │
│  └──────────────┘  └──────────────┘  │ └────────────────────┘ │ │
│                                       └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Database (SQLite)                         │
│      accounts | campaigns | campaign_templates | keyword_pool    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 브라우저 컨텍스트 전략 (Phase 1 테스트 결과 확정)

> **확정 결과**: superap.io는 **쿠키/세션 기반**으로 계정 판별
> **권장 방식**: Playwright 브라우저 컨텍스트 분리

```
┌─────────────────────────────────────────────────────────┐
│                    Playwright Browser                    │
├─────────────────┬─────────────────┬─────────────────────┤
│   Context A     │   Context B     │   Context C         │
│   (계정A)        │   (계정B)        │   (계정C)            │
├─────────────────┼─────────────────┼─────────────────────┤
│ - 독립 쿠키     │ - 독립 쿠키     │ - 독립 쿠키         │
│ - 독립 세션     │ - 독립 세션     │ - 독립 세션         │
│ - 독립 스토리지 │ - 독립 스토리지 │ - 독립 스토리지     │
└─────────────────┴─────────────────┴─────────────────────┘
```

### 2.3 캠페인 처리 전략 (Phase 1 테스트 결과 확정)

| 항목 | 방식 | 이유 |
|------|------|------|
| 계정 간 | 병렬 처리 (asyncio.gather) | 컨텍스트 분리로 충돌 없음 |
| 계정 내 | 순차 처리 (for loop) | 세션 혼선 방지 |
| 프록시 | **불필요** | IP 기반 판별 아님 |

```python
# 확정된 처리 패턴
await asyncio.gather(
    worker(context_a, 계정A_캠페인들),  # 내부는 순차
    worker(context_b, 계정B_캠페인들),  # 내부는 순차
    worker(context_c, 계정C_캠페인들),  # 내부는 순차
)
```

---

## 3. 데이터베이스 스키마

### 3.1 accounts (계정 관리)
```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    user_id VARCHAR(100) UNIQUE NOT NULL,  -- 사용자ID (예: 월보장 일류기획)
    password_encrypted TEXT,                -- 암호화된 비밀번호
    agency_name VARCHAR(100),               -- 대행사명
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 campaign_templates (캠페인 타입 템플릿)
```sql
CREATE TABLE campaign_templates (
    id INTEGER PRIMARY KEY,
    type_name VARCHAR(50) UNIQUE NOT NULL,  -- '트래픽', '저장하기'
    description_template TEXT NOT NULL,      -- 참여 방법 설명 템플릿
    hint_text TEXT NOT NULL,                 -- 정답 맞추기 힌트
    campaign_type_selection VARCHAR(100),    -- '플레이스 퀴즈', '검색 후 정답 입력'
    links JSON NOT NULL,                     -- ["링크1", "링크2", "링크3"]
    hashtag VARCHAR(100),                    -- '#cpc_detail_place'
    image_url_200x600 TEXT,                  -- 소재 이미지 URL
    image_url_720x780 TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 campaigns (캠페인 목록)
```sql
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY,
    campaign_code VARCHAR(20),               -- superap 캠페인 번호
    account_id INTEGER REFERENCES accounts(id),
    agency_name VARCHAR(100),                -- 대행사명
    place_name VARCHAR(200) NOT NULL,        -- 플레이스 상호명
    place_url TEXT NOT NULL,                 -- 플레이스 URL
    campaign_type VARCHAR(50) NOT NULL,      -- '트래픽' or '저장하기'
    
    -- 날짜
    registered_at TIMESTAMP,                 -- 작업 등록일
    start_date DATE NOT NULL,                -- 작업 시작일
    end_date DATE NOT NULL,                  -- 작업 종료일
    
    -- 작업량
    daily_limit INTEGER NOT NULL,            -- 일일 한도
    total_limit INTEGER,                     -- 전체 한도 (자동계산 가능)
    current_conversions INTEGER DEFAULT 0,   -- 실시간 전환수
    
    -- 미션 정보
    landmark_name VARCHAR(200),              -- 선택된 명소명
    step_count INTEGER,                      -- 걸음수 (정답)
    
    -- 키워드
    original_keywords TEXT,                  -- 원본 키워드 풀 (,구분)
    
    -- 상태
    status VARCHAR(20) DEFAULT 'pending',    -- pending, active, daily_exhausted, completed
    last_keyword_change TIMESTAMP,           -- 최근 키워드 변경 시간
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 keyword_usage (키워드 사용 이력)
```sql
CREATE TABLE keyword_usage (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    keyword VARCHAR(255) NOT NULL,
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, keyword)
);
```

### 3.5 keyword_pool (캠페인별 키워드 풀)
```sql
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

## 4. 핵심 로직 상세

### 4.1 캠페인 등록 플로우

```
[엑셀 업로드]
     │
     ▼
[파싱 & 검증]
     │
     ▼
[미리보기 테이블 표시] ◄───┐
     │                      │
     ▼                      │
[개별 수정 가능]  ──────────┘
  - 참여방법
  - 키워드
  - 힌트
  - 링크 추가/제거
     │
     ▼
[최종 등록 버튼]
     │
     ▼
[각 캠페인별 처리 시작]
     │
     ├──► [네이버맵: 주변 명소 1~3번째 랜덤 선택]
     │
     ├──► [네이버맵: 명소→플레이스 도보 걸음수 추출]
     │
     ├──► [키워드 255자 랜덤 조합]
     │
     ├──► [템플릿 치환]
     │         - &상호명& → 실제 상호명
     │         - &명소명& → 선택된 명소
     │
     └──► [superap.io 캠페인 등록]
               │
               ▼
         [DB 저장 & 캠페인 코드 기록]
```

### 4.2 키워드 조합 로직

```python
def select_keywords(keyword_pool: list, max_chars: int = 255) -> str:
    """
    키워드 풀에서 255자 이내로 랜덤 조합
    - 미사용 키워드만 대상
    - 단어가 잘리면 그 앞 단어까지만 포함
    """
    available = [k for k in keyword_pool if not k.is_used]
    random.shuffle(available)
    
    result = []
    current_length = 0
    
    for keyword in available:
        # 콤마 포함 길이 계산 (첫 키워드 제외)
        add_length = len(keyword) + (1 if result else 0)
        
        if current_length + add_length <= max_chars:
            result.append(keyword)
            current_length += add_length
        else:
            break
    
    return ','.join(result)
```

### 4.3 자동 키워드 교체 스케줄러

```python
# 매 10분마다 실행
@scheduler.scheduled_job('interval', minutes=10)
async def check_and_rotate_keywords():
    now = datetime.now()
    
    # 조건 A: 상태가 '일일소진'인 캠페인
    exhausted = get_campaigns_by_status('daily_exhausted')
    
    # 조건 B: 상태가 '진행중'이고 현재 시간이 23:50 이후
    if now.hour == 23 and now.minute >= 50:
        active = get_campaigns_by_status('active')
        # DB 업데이트 시간은 전날 23:50:00으로 고정
        update_time = now.replace(hour=23, minute=50, second=0)
    else:
        active = []
        update_time = now
    
    targets = exhausted + active
    
    for campaign in targets:
        # 새 키워드 조합 (기존 사용 키워드 제외)
        new_keywords = select_keywords(
            campaign.keyword_pool, 
            exclude=campaign.used_keywords
        )
        
        # superap.io에서 수정
        await update_campaign_keywords(campaign.id, new_keywords)
        
        # DB 업데이트
        campaign.last_keyword_change = update_time
        db.commit()
```

### 4.4 키워드 부족 경고 로직

```python
def check_keyword_shortage(campaign) -> str:
    """
    남은 일수 대비 키워드 부족 여부 체크
    반환: 'normal', 'warning', 'critical'
    """
    remaining_days = (campaign.end_date - date.today()).days
    remaining_keywords = len([k for k in campaign.keyword_pool if not k.is_used])
    
    # 하루 평균 교체 1회 가정
    if remaining_keywords < remaining_days:
        return 'critical'  # 빨간색
    elif remaining_keywords < remaining_days * 1.5:
        return 'warning'   # 노란색
    else:
        return 'normal'    # 기본
```

---

## 5. superap.io 웹 자동화 분석 포인트

### 5.1 Phase 1 테스트 완료 항목

#### A. 계정 세션 이슈 - **분석 완료**
```
현상: 같은 기기에서 다른 브라우저로 다른 계정 로그인 시
      캠페인이 해당 계정으로 세팅됨

✅ 분석 결과 (2026-02-04 테스트 완료):
- 세션 관리 방식: 쿠키/세션 기반 (확인됨)
- IP 기반 판별: 아님 (프록시 불필요)
- 해결 방안: Playwright 브라우저 컨텍스트 분리

✅ 확정 아키텍처:
- 계정별 독립 브라우저 컨텍스트 사용
- 계정 간 병렬 처리 가능
- 계정 내 순차 처리 권장
```

#### B. 날짜 설정 버튼 동작
```
현상: '+O일' 버튼 → 23:59:59 자동 세팅
      수기 입력 → 시간 제대로 안됨

분석 필요:
- JavaScript 이벤트 핸들러 분석
- 날짜 필드의 실제 값 전송 방식
- 버튼 클릭 시 트리거되는 함수 확인
```

#### C. 캠페인 등록 폼 필드 맵핑
```
확인된 필드:
- 캠페인 이름
- 참여 방법 설명 (이미지 URL 포함)
- 검색키워드 (248/255자 제한)
- 정답 맞추기 힌트
- 링크 3개 슬롯 (+/- 버튼)
- 캠페인 타입 라디오 버튼
- 매체 타겟팅 체크박스
- 날짜 설정 (시작/종료)
- 전체 한도 / 일일 한도
- 전환 인식 기준(텍스트) - 걸음수

분석 필요:
- 각 필드의 name/id 속성
- 필수 입력 필드 검증 로직
- 등록 API 엔드포인트 및 페이로드 구조
```

---

## 6. 관리자 웹 UI 구성

### 6.1 메인 대시보드
```
┌─────────────────────────────────────────────────────────────────┐
│ [탭: 계정A] [탭: 계정B] [탭: 계정C] [+ 계정 추가]               │
├─────────────────────────────────────────────────────────────────┤
│ 필터: [대행사 선택 ▼] [상태 선택 ▼] [검색...]                  │
├─────────────────────────────────────────────────────────────────┤
│ 캠페인번호 │상호명│상태│전환수│작업일│키워드잔량│최근변경│작업│
│ 1336101   │일류..│진행│840/840│D+5 │🟢 충분   │02-04  │[+] │
│ 1336102   │스시..│소진│1768/..│D+3 │🟡 주의   │02-04  │[+] │
│ 1336103   │떡볶..│진행│420/490│D+2 │🔴 부족   │02-03  │[+] │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 엑셀 업로드 & 미리보기
```
┌─────────────────────────────────────────────────────────────────┐
│ [📁 엑셀 파일 선택] [업로드]                                    │
├─────────────────────────────────────────────────────────────────┤
│ 미리보기 (등록 전 수정 가능)                                    │
├─────────────────────────────────────────────────────────────────┤
│ ☑│상호명      │타입  │시작일  │키워드(편집)│힌트(편집)│링크    │
│ ✓│일류곱창    │트래픽│02-04  │[편집]     │[편집]   │[+][-] │
│ ✓│스시오마카세│저장  │02-04  │[편집]     │[편집]   │[+][-] │
├─────────────────────────────────────────────────────────────────┤
│                                          [취소] [최종 등록]     │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 템플릿 관리
```
┌─────────────────────────────────────────────────────────────────┐
│ 캠페인 타입 템플릿 관리                                         │
├─────────────────────────────────────────────────────────────────┤
│ [타입: 트래픽 ▼]                                                │
│                                                                 │
│ 참여 방법 설명:                                                 │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │[참여방법]                                                   ││
│ │{{image|https://i.ibb.co/...}}                               ││
│ │1. 하단의 검색키워드 복사 후...                              ││
│ │2. 네이버 홈에서... [&상호명&] 클릭                          ││
│ │5. 출발지를 [&명소명&]으로 설정...                           ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ 정답 맞추기 힌트:                                               │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수...││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ 링크 (해시태그 자동 추가):                                      │
│ 1. [https://nid.naver.com/...                        ] [삭제] │
│ 2. [https://link.naver.com/...                       ] [삭제] │
│ 3. [https://app.map.naver.com/...                    ] [삭제] │
│ [+ 링크 추가]                                                   │
│                                                                 │
│ 해시태그: [#cpc_detail_place]                                   │
│                                                                 │
│                                              [저장]             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. 기술 스택

| 구분 | 기술 |
|------|------|
| Frontend | React + TypeScript + TailwindCSS |
| Backend | Python FastAPI |
| Database | SQLite |
| 웹 자동화 | Playwright |
| 스케줄러 | APScheduler |
| 컨테이너 | Docker + Docker Compose |
| 환경 | 사내 로컬 PC (Windows/Mac) |

---

## 7.1 Docker 구성 (PC 이동 대비)

### docker-compose.yml
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data          # SQLite DB 영속화
      - ./logs:/app/logs          # 로그 영속화
    environment:
      - DATABASE_URL=sqlite:///./data/quantum.db
    depends_on:
      - playwright

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  playwright:
    image: mcr.microsoft.com/playwright:v1.40.0-jammy
    volumes:
      - ./backend:/app
    working_dir: /app
    command: ["python", "-m", "playwright", "install"]

volumes:
  data:
  logs:
```

### backend/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Playwright 의존성
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install chromium
RUN playwright install-deps

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### frontend/Dockerfile
```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
```

---

## 7.2 PC 이동 가이드

### 개발 PC → 운영 PC 이동 절차

**1단계: 개발 PC에서**
```bash
# Git 커밋 (코드)
git add .
git commit -m "배포 준비"
git push

# 데이터 백업 (DB + 설정)
cp data/quantum.db ./backup/
cp .env ./backup/
```

**2단계: 운영 PC에서**
```bash
# 1. Docker Desktop 설치 (Windows/Mac)
# https://www.docker.com/products/docker-desktop

# 2. 코드 가져오기
git clone [저장소 URL]
cd quantum-campaign-automation

# 3. 환경 설정
cp .env.example .env
# .env 파일 편집 (계정 정보 입력)

# 4. 데이터 복원 (기존 DB 사용 시)
cp backup/quantum.db ./data/

# 5. 실행
docker-compose up -d

# 6. 확인
# 브라우저에서 http://localhost:3000 접속
```

### 필수 이동 파일
```
quantum-campaign-automation/
├── .env                    # ⚠️ 계정 정보 (Git 제외)
├── data/
│   └── quantum.db          # ⚠️ 캠페인 DB (Git 제외)
└── (나머지는 Git으로 관리)
```

### .env 예시
```env
# superap.io 계정들
SUPERAP_ACCOUNTS='[
  {"user_id": "월보장 일류기획", "password": "xxx"},
  {"user_id": "계정2", "password": "xxx"}
]'

# 앱 설정
SECRET_KEY=your-secret-key-here
DEBUG=false
```

### 자주 쓰는 명령어
```bash
# 시작
docker-compose up -d

# 중지
docker-compose down

# 로그 확인
docker-compose logs -f backend

# 재시작 (코드 수정 후)
docker-compose up -d --build
```

---

## 8. 개발 로드맵

### Phase 1: 기반 구축 (1주)
- [ ] 프로젝트 초기 세팅 (FastAPI + React)
- [ ] DB 스키마 생성 및 마이그레이션
- [ ] superap.io 웹 구조 분석 (Claude Code)
- [ ] 계정 관리 기능

### Phase 2: 핵심 자동화 (2주)
- [ ] 엑셀 파싱 & 검증 로직
- [ ] 네이버맵 명소 추출 + 걸음수 계산
- [ ] superap.io 캠페인 등록 자동화
- [ ] 키워드 255자 조합 로직

### Phase 3: 대시보드 & 모니터링 (1주)
- [ ] 캠페인 목록 대시보드
- [ ] 계정별 탭 구분
- [ ] 키워드 잔량 경고 표시
- [ ] 실시간 전환수 동기화

### Phase 4: 자동 키워드 교체 (1주)
- [ ] 상태 모니터링 스케줄러
- [ ] 일일소진 감지 & 키워드 교체
- [ ] 23:50 자동 교체 로직
- [ ] 키워드 사용 이력 추적

### Phase 5: 안정화 & 최적화 (1주)
- [ ] 에러 핸들링 & 재시도 로직
- [ ] 로깅 & 알림 시스템
- [ ] 성능 최적화
- [ ] 문서화

---

## 9. 파일 구조

```
quantum-campaign-automation/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 앱
│   │   ├── config.py               # 설정
│   │   ├── database.py             # DB 연결
│   │   │
│   │   ├── models/
│   │   │   ├── account.py
│   │   │   ├── campaign.py
│   │   │   ├── template.py
│   │   │   └── keyword.py
│   │   │
│   │   ├── routers/
│   │   │   ├── accounts.py
│   │   │   ├── campaigns.py
│   │   │   ├── templates.py
│   │   │   └── upload.py
│   │   │
│   │   ├── services/
│   │   │   ├── excel_parser.py     # 엑셀 파싱
│   │   │   ├── naver_map.py        # 네이버맵 스크래핑
│   │   │   ├── superap.py          # superap.io 자동화
│   │   │   ├── keyword_manager.py  # 키워드 관리
│   │   │   └── scheduler.py        # 스케줄러
│   │   │
│   │   └── utils/
│   │       ├── encryption.py
│   │       └── validators.py
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard/
│   │   │   ├── Upload/
│   │   │   ├── Templates/
│   │   │   └── common/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```

---

## 10. 보안 고려사항

1. **계정 정보 암호화**: 비밀번호는 AES-256 암호화 저장
2. **API 인증**: JWT 토큰 기반 인증
3. **브라우저 격리**: 각 계정별 별도 브라우저 컨텍스트
4. **로그 마스킹**: 민감 정보 로그 제외
5. **Rate Limiting**: superap.io 요청 제한 준수

