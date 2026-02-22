# J2LAB 통합 플랫폼 구축 계획서

> **문서 버전**: v2.0
> **작성일**: 2026-02-17 | **최종 수정**: 2026-02-23
> **목표**: 접수 → 키워드 추출 → 캠페인 세팅 → 관리 전체 파이프라인 통합
> **기술 스택**: FastAPI 통일 + PostgreSQL + React + Docker + AWS
> **운영 회사**: 일류기획, 제이투랩 (멀티 테넌트)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [현재 시스템 분석](#2-현재-시스템-분석)
3. [통합 아키텍처](#3-통합-아키텍처)
4. [통합 DB 스키마](#4-통합-db-스키마)
5. [파이프라인 상세 흐름](#5-파이프라인-상세-흐름)
6. [API 명세](#6-api-명세)
7. [기존 코드 → 통합 매핑 가이드](#7-기존-코드--통합-매핑-가이드)
8. [단계별 구현 체크리스트](#8-단계별-구현-체크리스트)
9. [Docker / AWS 배포 가이드](#9-docker--aws-배포-가이드)
10. [데이터 마이그레이션](#10-데이터-마이그레이션)
11. [보안 고려사항](#11-보안-고려사항)
12. [향후 확장 (+α)](#12-향후-확장-α)

---

## 1. 프로젝트 개요

### 1.1 배경

현재 3개의 독립 시스템이 각각 Docker 컨테이너에서 운영 중:

| 시스템 | 기술 스택 | 역할 | 현재 상태 |
|--------|----------|------|----------|
| **Keyword Extract** | FastAPI + Playwright | 네이버 플레이스 키워드 자동 추출 | 운영 중 (Docker) |
| **Quantum Campaign** | FastAPI + React + Playwright | 슈퍼앱 캠페인 자동 등록/키워드 로테이션 | 운영 중 (Docker) |
| **jtwolablife (OMS)** | Django + DRF | 접수/주문/정산/유저관리 | 코어 기능 완성 (GitHub) |

### 1.2 목표

- 3개 시스템을 **FastAPI 기반 하나의 플랫폼**으로 통합
- **접수 → 키워드 추출 → 계정 자동 배정 → 캠페인 세팅 → 관리** 전체 자동화 파이프라인 구축
- **AWS EC2**에 Docker Compose로 배포
- 단일 **PostgreSQL** 데이터베이스로 모든 데이터 통합 관리
- **멀티 테넌트**: 일류기획, 제이투랩 2개 회사가 독립적으로 운영

### 1.3 운영 구조

```
시스템 관리자 (system_admin)
│
├── 일류기획 (company)
│   ├── 메인 관리자 (company_admin) ─ 정산, 입금확인, 계정배정
│   ├── 접수 담당자 (order_handler) ─ 세팅, 영업
│   ├── 총판 A (distributor) ─ 하부계정 관리, 접수건 확인
│   │   ├── 하부 a1 (sub_account) ─ 접수만
│   │   └── 하부 a2 (sub_account)
│   └── 총판 B (distributor)
│       └── 하부 b1 (sub_account)
│
└── 제이투랩 (company)
    ├── 메인 관리자 (company_admin)
    ├── 접수 담당자 (order_handler)
    └── 총판 C (distributor)
        └── 하부 c1 (sub_account)
```

### 1.4 기술 스택 결정

| 항목 | 선택 | 이유 |
|------|------|------|
| 백엔드 프레임워크 | **FastAPI** | 기존 두 서비스가 FastAPI, async 네이티브, Playwright와 궁합 |
| DB | **PostgreSQL 15** | JSONB 지원, 확장성, AWS RDS 호환 |
| ORM | **SQLAlchemy 2.0 (async)** | Quantum Campaign에서 이미 사용, Alembic 마이그레이션 |
| 프론트엔드 | **React + TypeScript + Vite** | Quantum Campaign에 이미 React 존재, jtwolablife UI 참고 |
| 인증 | **JWT** | API 기반 SPA에 적합 |
| 컨테이너 | **Docker Compose** | 이미 두 서비스 Docker 운영 중 |
| 배포 | **AWS EC2 (t3.medium+)** | Playwright 메모리 요구, 초기 비용 절감 |

---

## 2. 현재 시스템 분석

### 2.1 Keyword Extract (키워드 추출)

**위치**: `reference/keyword-extract/`

**핵심 기능**: 네이버 플레이스 URL 입력 → 4단계 파이프라인으로 키워드 추출 + 랭킹 확인

**4단계 파이프라인 (smart_worker.py):**
1. **Phase 0**: Playwright로 플레이스 데이터 수집 (이름, 카테고리, 주소, 리뷰, 메뉴 등)
2. **Phase 1**: 샘플 키워드 1개로 노출 검증 (신지도/구지도 판별)
3. **Phase 2**: 계층적 키워드 생성 (지역조합 × 업종 × 수식어 = 500~2,000개)
4. **Phase 3**: 생성된 키워드 랭킹 체크 (GraphQL API + curl_cffi)

**핵심 파일:**

| 파일 | 라인수 | 역할 |
|------|--------|------|
| `src/smart_worker.py` | 2,349 | 메인 파이프라인 로직 |
| `src/rank_checker_graphql.py` | 3,311 | 랭킹 체크 (GraphQL + curl_cffi) |
| `src/place_scraper.py` | 599 | Playwright 스크래핑 |
| `src/models.py` | 443 | PlaceData, RegionInfo 데이터 클래스 |
| `src/address_parser.py` | ~400 | 한국 주소 파싱 (시/구/동/역) |
| `src/keyword_generator.py` | ~400 | 규칙 기반 키워드 생성 엔진 |
| `src/gemini_client.py` | ~200 | Google Gemini AI 연동 |
| `web/app.py` | - | FastAPI 웹 서비스 (API 엔드포인트) |
| `web/session_manager.py` | - | 세션/작업 관리 (인메모리 + JSON 파일) |

**현재 데이터 저장 방식:**
- 세션: 인메모리 (최대 5개 동시 세션)
- 작업 결과: `data/jobs/{username}/{job_id}.json` (JSON 파일)
- 설정: `settings.json` (프록시, 크리덴셜)

**의존성 (requirements-web.txt):**
```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
playwright>=1.40.0
curl_cffi>=0.7.0
aiohttp>=3.9.0
google-genai>=1.0.0
httpx>=0.25.0
```

### 2.2 Quantum Campaign (캠페인 자동화)

**위치**: `reference/quantum-campaign/`

**핵심 기능**: 슈퍼앱(superap.io) 캠페인 자동 등록 + 일일 키워드 로테이션

**핵심 파일:**

| 파일 | 역할 |
|------|------|
| `backend/app/services/superap.py` | Playwright 브라우저 자동화 (슈퍼앱 로그인, 폼 입력) |
| `backend/app/services/campaign_registration.py` | 등록 플로우 오케스트레이션 |
| `backend/app/services/keyword_rotation.py` | 일일 키워드 교체 로직 |
| `backend/app/services/campaign_extension.py` | 캠페인 연장 |
| `backend/app/services/scheduler.py` | APScheduler (10분 간격 실행) |
| `backend/app/services/naver_map.py` | 네이버 맵 API 연동 |
| `backend/app/services/excel_parser.py` | 엑셀 파싱 |
| `backend/app/modules/landmark.py` | 랜드마크 추출 모듈 |
| `backend/app/modules/place_info.py` | 플레이스 정보 모듈 |
| `backend/app/modules/steps.py` | 도보 스텝 계산 모듈 |
| `backend/app/models/account.py` | 슈퍼앱 계정 모델 |
| `backend/app/models/campaign.py` | 캠페인 모델 |
| `backend/app/models/keyword.py` | 키워드풀 모델 |
| `backend/app/models/template.py` | 캠페인 템플릿 모델 |

**현재 DB 구조 (SQLite):**
- `accounts`: 슈퍼앱 계정 (ID, 암호화된 비밀번호, 대행사명)
- `campaigns`: 캠페인 정보 (코드, 플레이스, 기간, 한도, 상태)
- `keyword_pool`: 캠페인별 키워드 (사용 여부 추적)
- `campaign_templates`: 캠페인 유형별 템플릿

**스케줄러 동작:**
- 10분마다 실행
- 활성 캠페인의 키워드 사용량 체크
- 일일 한도 도달 또는 23:50 KST에 자동 교체
- 소진된 키워드 풀 자동 재활용

**의존성:**
```
fastapi>=0.115.0
sqlalchemy>=2.0.0
playwright>=1.40.0
apscheduler>=3.10.4
cryptography  # AES 암호화
httpx
aiofiles
```

### 2.3 jtwolablife (OMS - 참고용)

**위치**: GitHub `minjunrl-netizen/jtwolablife`

**참고할 기능:**
- **유저/역할 관리**: 5단계 역할 (admin → accountant → manager → agency → seller), 계층적 parent-child
- **상품 관리**: JSON schema 기반 동적 입력 필드
- **주문/접수**: 그리드 인터페이스, 엑셀 벌크 업로드
- **정산**: 잔액 관리, 입금/출금/환불, VAT 계산

---

## 3. 통합 아키텍처

### 3.1 시스템 구성도

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS EC2 (Docker Compose)                  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Nginx                                                  │ │
│  │  - HTTPS 종단 (Let's Encrypt / ACM)                     │ │
│  │  - /              → React SPA (프론트엔드)               │ │
│  │  - /api/*         → api-server:8000                     │ │
│  │  - /ws/*          → api-server:8000 (WebSocket)         │ │
│  │  Port: 80, 443                                          │ │
│  └───────────────────────┬────────────────────────────────┘ │
│                          │                                   │
│  ┌───────────────────────▼────────────────────────────────┐ │
│  │  api-server (메인 FastAPI 서버)                          │ │
│  │                                                          │ │
│  │  담당 영역:                                               │ │
│  │  ├── 인증/인가 (JWT, 역할 기반 접근 제어)                  │ │
│  │  ├── 유저 관리 (계층적 조직 구조)                          │ │
│  │  ├── 상품/가격 정책                                       │ │
│  │  ├── 주문 접수 (단건 + 엑셀 벌크)                         │ │
│  │  ├── 플레이스/키워드 CRUD                                 │ │
│  │  ├── 캠페인 관리                                          │ │
│  │  ├── 정산/잔액 관리                                       │ │
│  │  ├── 파이프라인 오케스트레이션                              │ │
│  │  └── 대시보드/통계                                        │ │
│  │                                                          │ │
│  │  Port: 8000                                              │ │
│  └──────┬─────────────────────────┬─────────────────────────┘ │
│         │ (내부 HTTP)              │ (내부 HTTP)              │
│  ┌──────▼──────────┐   ┌──────────▼──────────────────┐     │
│  │ keyword-worker  │   │ campaign-worker              │     │
│  │                  │   │                              │     │
│  │ 담당:            │   │ 담당:                         │     │
│  │ - 플레이스 수집   │   │ - 슈퍼앱 캠페인 자동 등록      │     │
│  │ - 키워드 생성     │   │ - 키워드 로테이션 (스케줄러)   │     │
│  │ - 랭킹 체크      │   │ - 캠페인 연장                  │     │
│  │ - 프록시 관리     │   │ - 캠페인 상태 동기화           │     │
│  │                  │   │                              │     │
│  │ Port: 8001      │   │ Port: 8002                   │     │
│  │ Playwright      │   │ Playwright + APScheduler     │     │
│  └──────────────────┘   └──────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL 15 (단일 통합 DB)                           │ │
│  │  Port: 5432                                             │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 서비스 간 통신

```
[React Frontend] ──HTTP/WS──→ [Nginx] ──→ [api-server]
                                              │
                              ┌───────────────┼───────────────┐
                              │               │               │
                         내부 HTTP         내부 HTTP        직접 DB
                              │               │               │
                    [keyword-worker]  [campaign-worker]  [PostgreSQL]
                              │               │               │
                              └───────────────┴───────────────┘
                                        직접 DB 읽기/쓰기
```

**통신 규칙:**
1. **프론트엔드 → api-server**: 모든 요청은 api-server를 거침 (외부 노출은 api-server만)
2. **api-server → workers**: 내부 Docker 네트워크에서 HTTP 호출 (`http://keyword-worker:8001/internal/...`)
3. **workers → DB**: 같은 Docker 네트워크에서 PostgreSQL 직접 접근 (읽기/쓰기)
4. **workers ↛ 외부**: workers는 외부에 노출되지 않음

### 3.3 핵심 설계 원칙

| 원칙 | 설명 |
|------|------|
| **api-server = 외부 CRUD 담당** | 사용자 요청은 모두 api-server를 거침 |
| **workers = 작업 수행 + DB 직접 저장** | 무거운 작업 수행 후 결과를 DB에 직접 쓰고, 콜백으로 api-server에 알림 |
| **공유 DB** | 3개 서비스가 같은 PostgreSQL 사용 (Docker 내부 네트워크) |
| **내부 API** | workers는 `/internal/` prefix로 내부 전용 엔드포인트만 노출 |
| **기존 로직 보존** | Playwright 자동화, 프록시 관리 등 핵심 로직은 그대로 유지 |
| **네트워크 ≠ 템플릿** | 네트워크 프리셋(계정+매체)과 캠페인 템플릿(폼내용)은 독립적 축 |

---

## 4. 통합 DB 스키마

### 4.1 ER 다이어그램 (관계도)

```
companies ──── superap_accounts
  │                  │
  │ (1:N)            │
  ▼                  │
users ─────────────────┐
  │                     │
  │ (1:N)               │ (1:N)
  ▼                     ▼
orders              balance_transactions
  │
  │ (1:N)
  ▼
order_items ────────── products
  │         ────────── price_policies ── users
  │
  │ (1:1)              assigned_account_id
  ▼                     │
pipeline_states         ▼
  │         │      superap_accounts
  │ (1:1)   │ (1:1)
  ▼         ▼
extraction_jobs    campaigns ────── superap_accounts
  │                  │         ────── campaign_templates
  │                  │
  │ (N:1)            │ (1:N)
  ▼                  ▼
places            campaign_keyword_pool
  │
  │ (1:N)
  ▼
keywords
  │
  │ (1:N)
  ▼
keyword_rank_history

별도: refresh_tokens (JWT 관리)
별도: network_presets (네트워크 프리셋 → superap_accounts, campaigns)
```

> **테이블 수: 20개** (기존 16 + companies, refresh_tokens, system_settings, network_presets 신규)

### 4.2 전체 테이블 정의

#### 테이블 0: `companies` (회사/테넌트)
> 신규: 멀티 테넌트 지원

```sql
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    -- 예: '일류기획', '제이투랩'
    code VARCHAR(50) UNIQUE NOT NULL,
    -- 예: 'ilryu', 'j2lab'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

---

#### 테이블 1: `users` (유저/인증)
> 소스: jtwolablife 참고 + 멀티 테넌트 역할 구조 반영

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    name VARCHAR(50) NOT NULL,
    phone VARCHAR(20),

    company_id INT REFERENCES companies(id) ON DELETE SET NULL,
    -- 소속 회사 (system_admin은 NULL)

    role VARCHAR(20) NOT NULL DEFAULT 'sub_account',
    -- 역할 계층:
    -- system_admin   : 시스템 최고 관리자 (company_id = NULL)
    -- company_admin  : 회사별 메인 관리자 (정산, 입금확인, 계정배정)
    -- order_handler  : 접수 담당자/영업 (세팅, 캠페인 관리)
    -- distributor    : 총판 (거래처, 하부계정 생성 가능)
    -- sub_account    : 하부 계정 (접수만 가능)

    parent_id UUID REFERENCES users(id) ON DELETE SET NULL,
    -- 계층 구조: distributor → sub_account (총판의 하부계정)

    balance NUMERIC(12,0) DEFAULT 0,
    -- 현재 잔액 (원 단위)
    -- ⚠ 동시성 주의: 잔액 변경 시 반드시 SELECT FOR UPDATE 사용
    -- balance_transactions 테이블이 source of truth

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_company_id ON users(company_id);
CREATE INDEX idx_users_parent_id ON users(parent_id);
CREATE INDEX idx_users_is_active ON users(is_active);
```

**역할 권한 매트릭스:**

| 역할 | 접수 | 하부접수 확인 | 입금확인 | 세팅/캠페인 | 계정배정 보기 | 정산 | 하부계정 관리 | 시스템 설정 |
|------|------|------------|---------|-----------|-------------|------|------------|-----------|
| system_admin | R/W | R/W | R/W | R/W | ✅ | R/W | R/W | R/W |
| company_admin | R/W | R/W (본사) | ✅ | R/W | ✅ | R/W (본사) | R/W (본사) | - |
| order_handler | R/W | R (본사) | - | R/W | ❌ | R (본인) | - | - |
| distributor | R/W | R/W (본인 하부) | - | R (본인건) | ❌ | R (본인) | R/W (하부) | - |
| sub_account | R/W (접수만) | - | - | R (본인건) | ❌ | - | - | - |

> ❌ = 슈퍼앱 계정 배정 정보는 company_admin, system_admin에게만 노출

---

#### 테이블 2: `products` (상품/서비스)
> 소스: jtwolablife의 products.Product 모델 참고

```sql
CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    -- 예: "네이버 트래픽 캠페인", "저장하기 캠페인", "월보장"
    code VARCHAR(50) UNIQUE NOT NULL,
    -- 예: "traffic", "save", "monthly_guarantee"
    category VARCHAR(100),
    -- 예: "campaign", "keyword_service", "monthly"
    description TEXT,
    form_schema JSONB,
    -- 동적 입력 필드 정의 (주문 시 고객이 입력할 항목)
    -- 예: [
    --   {"name": "place_url", "type": "url", "label": "네이버 플레이스 URL", "required": true},
    --   {"name": "campaign_days", "type": "number", "label": "캠페인 기간(일)", "default": 30},
    --   {"name": "daily_limit", "type": "number", "label": "일일 한도", "default": 100}
    -- ]
    base_price NUMERIC(12,0),
    -- 기본 가격 (원)
    min_work_days INT,
    max_work_days INT,

    daily_deadline TIME NOT NULL DEFAULT '18:00',
    -- 상품별 일일 접수 마감 시간 (KST)
    -- 이 시간까지 총판이 접수건을 올려야 함
    -- 예: 트래픽 = 18:00, 저장하기 = 17:00
    deadline_timezone VARCHAR(30) DEFAULT 'Asia/Seoul',

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

---

#### 테이블 3: `price_policies` (가격 정책)
> 소스: jtwolablife의 products.PricePolicy 모델 참고

```sql
CREATE TABLE price_policies (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    -- NULL이면 기본 가격, 특정 유저면 개별 가격
    role VARCHAR(20),
    -- 역할별 가격 (agency 가격, seller 가격 등)
    unit_price NUMERIC(12,0) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    -- NULL이면 무기한
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_price_policies_product_id ON price_policies(product_id);
CREATE INDEX idx_price_policies_user_id ON price_policies(user_id);
```

---

#### 테이블 4: `orders` (주문)
> 소스: jtwolablife의 orders.Order 모델 참고

```sql
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    order_number VARCHAR(30) UNIQUE NOT NULL,
    -- 자동 생성 형식: "ORD-20260217-0001"
    user_id UUID NOT NULL REFERENCES users(id),
    -- 주문한 유저 (distributor 또는 sub_account)
    company_id INT REFERENCES companies(id),
    -- 소속 회사 (유저에서 자동 설정)

    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft(하부계정 임시저장) → submitted(총판이 올림)
    -- → payment_confirmed(입금확인) → processing(처리중)
    -- → completed(완료) / cancelled(취소) / rejected(반려)

    payment_status VARCHAR(20) DEFAULT 'unpaid',
    -- unpaid(미입금) → confirmed(입금확인) → settled(정산완료)

    total_amount NUMERIC(12,0) DEFAULT 0,
    -- 총 결제 금액 (물량 × 단가)
    vat_amount NUMERIC(12,0) DEFAULT 0,
    -- VAT (10%)
    notes TEXT,
    -- 관리자 메모
    source VARCHAR(20) DEFAULT 'web',
    -- web(웹 시트), excel(엑셀 업로드)

    submitted_by UUID REFERENCES users(id),
    -- 총판이 올린 경우 총판 ID
    submitted_at TIMESTAMPTZ,

    payment_confirmed_by UUID REFERENCES users(id),
    -- 입금 확인한 company_admin
    payment_confirmed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
```

---

#### 테이블 5: `order_items` (주문 항목)
> 소스: jtwolablife의 orders.OrderItem 모델 참고

```sql
CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id),
    place_id BIGINT REFERENCES places(id),
    -- 플레이스 연결 (키워드 추출 후 자동 연결)
    row_number INT,
    -- 주문 내 순번
    quantity INT NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,0) NOT NULL,
    subtotal NUMERIC(12,0) NOT NULL,
    -- unit_price × quantity
    item_data JSONB,
    -- 동적 폼 데이터
    -- 예: {"place_url": "https://map.naver.com/...", "start_date": "2026-03-01",
    --       "end_date": "2026-03-31", "daily_limit": 300, "campaign_type": "traffic"}
    -- 주의: 키워드는 접수 폼에서 받지 않음 (추출 후 자동 배정)

    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending → processing → completed / failed
    result_message TEXT,

    -- === 슈퍼앱 계정 배정 (company_admin만 볼 수 있음) ===
    assigned_account_id INT REFERENCES superap_accounts(id),
    -- 자동 배정된 슈퍼앱 계정
    assignment_status VARCHAR(20) DEFAULT 'pending',
    -- pending(미배정) → auto_assigned(자동배정) → confirmed(확인됨) → overridden(수동변경)
    assigned_at TIMESTAMPTZ,
    assigned_by UUID REFERENCES users(id),
    -- 배정 확인/변경한 company_admin

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_place_id ON order_items(place_id);
CREATE INDEX idx_order_items_status ON order_items(status);
```

---

#### 테이블 6: `places` (플레이스)
> **핵심**: Keyword Extract의 `PlaceData` 클래스를 완전히 반영
> 소스: `reference/keyword-extract/src/models.py` (PlaceData, RegionInfo)

```sql
CREATE TABLE places (
    id BIGINT PRIMARY KEY,
    -- 네이버 Place ID (auto-increment 아님, 네이버에서 부여한 ID)

    -- === 기본 정보 ===
    name VARCHAR(200) NOT NULL,
    place_type VARCHAR(20) NOT NULL DEFAULT 'place',
    -- restaurant(신지도-음식점), hospital(병원), hairshop(헤어샵),
    -- nailshop(네일샵), cafe(카페), accommodation(숙박), place(구지도-일반)
    category VARCHAR(500),
    -- 네이버 카테고리 원본 (예: "음식점>이탈리안>파스타,피자")
    main_category VARCHAR(100),
    -- 최상위 카테고리 (예: "음식점", "병원")

    -- === 주소 분해 (RegionInfo 기반) ===
    city VARCHAR(50),
    -- 시/도 (서울특별시, 경기도, 부산광역시 등)
    si VARCHAR(50),
    -- 시 (고양시, 수원시 등, 서울은 NULL)
    gu VARCHAR(50),
    -- 구 (강남구, 일산동구 등)
    dong VARCHAR(50),
    -- 동 (역삼동, 장항동 등)
    major_area VARCHAR(50),
    -- 주요 지역명 (일산, 분당, 강남 등 - 키워드 조합에 사용)
    road_address VARCHAR(500),
    -- 도로명 주소
    jibun_address VARCHAR(500),
    -- 지번 주소
    stations JSONB DEFAULT '[]',
    -- 인근 지하철역 목록 (예: ["강남역", "역삼역"])

    -- === 연락처 ===
    phone VARCHAR(20),
    virtual_phone VARCHAR(20),
    -- 가상 전화번호 (네이버 제공)
    introduction TEXT,
    -- 업체 소개글
    naver_url VARCHAR(500),
    -- 네이버 플레이스 URL

    -- === 리뷰/키워드 데이터 (PlaceData 필드 1:1 매핑) ===
    keywords JSONB DEFAULT '[]',
    -- 플레이스 대표 키워드 (예: ["파스타맛집", "분위기좋은"])
    conveniences JSONB DEFAULT '[]',
    -- 편의시설 (예: ["주차", "예약", "와이파이"])
    micro_reviews JSONB DEFAULT '[]',
    -- 마이크로 리뷰 태그 (예: ["분위기가 좋아요", "음식이 맛있어요"])
    review_menu_keywords JSONB DEFAULT '[]',
    -- 리뷰 메뉴 키워드 [{label: "파스타", count: 42}, ...]
    review_theme_keywords JSONB DEFAULT '[]',
    -- 리뷰 테마 키워드 [{label: "분위기", count: 35}, ...]
    voted_keywords JSONB DEFAULT '[]',
    -- 투표 키워드 [{label: "넓어요", count: 28}, ...]
    payment_info JSONB DEFAULT '[]',
    -- 결제 수단 (예: ["네이버페이", "제로페이"])
    seat_items JSONB DEFAULT '[]',
    -- 좌석 종류 (예: ["단체석", "커플석"])
    specialties JSONB DEFAULT '[]',
    -- 특기사항 (의료: 진료과목, 미용: 스타일 등)
    menus JSONB DEFAULT '[]',
    -- 메뉴 목록
    medical_subjects JSONB DEFAULT '[]',
    -- 의료 진료과목 (병원 전용) (예: ["피부과", "정형외과"])
    discovered_regions JSONB DEFAULT '[]',
    -- 키워드에서 발견된 지역명

    -- === 예약 정보 ===
    has_booking BOOLEAN DEFAULT FALSE,
    booking_type VARCHAR(20),
    -- "realtime"(네이버 실시간 예약) 또는 "url"(외부 예약 링크)
    booking_hub_id VARCHAR(100),
    booking_url TEXT,

    -- === 메타 ===
    last_scraped_at TIMESTAMPTZ,
    -- 마지막 스크래핑 시각
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_places_place_type ON places(place_type);
CREATE INDEX idx_places_gu ON places(gu);
CREATE INDEX idx_places_major_area ON places(major_area);
```

---

#### 테이블 7: `keywords` (추출된 키워드)

```sql
CREATE TABLE keywords (
    id BIGSERIAL PRIMARY KEY,
    place_id BIGINT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    keyword VARCHAR(200) NOT NULL,
    -- 추출된 키워드 (예: "강남 파스타", "역삼역 이탈리안 맛집")
    keyword_type VARCHAR(20),
    -- representative(대표), menu(메뉴), theme(테마),
    -- voted(투표), medical(의료), region(지역조합)
    search_query VARCHAR(300),
    -- 실제 검색에 사용된 쿼리 (키워드와 다를 수 있음)
    current_rank INT,
    -- 현재 랭킹 (1~50, NULL이면 50위 밖)
    current_map_type VARCHAR(10),
    -- "new_map"(신지도) 또는 "old_map"(구지도)
    last_checked_at TIMESTAMPTZ,
    -- 마지막 랭킹 체크 시각
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (place_id, keyword)
);

CREATE INDEX idx_keywords_place_id ON keywords(place_id);
CREATE INDEX idx_keywords_current_rank ON keywords(current_rank);
CREATE INDEX idx_keywords_keyword_type ON keywords(keyword_type);
```

---

#### 테이블 8: `keyword_rank_history` (키워드 랭킹 이력)

```sql
CREATE TABLE keyword_rank_history (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    rank_position INT,
    map_type VARCHAR(10),
    recorded_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (keyword_id, recorded_date)
);

CREATE INDEX idx_rank_history_keyword_id ON keyword_rank_history(keyword_id);
CREATE INDEX idx_rank_history_recorded_date ON keyword_rank_history(recorded_date);
```

---

#### 테이블 9: `extraction_jobs` (키워드 추출 작업)
> 소스: `reference/keyword-extract/web/session_manager.py` Job 클래스

```sql
CREATE TABLE extraction_jobs (
    id BIGSERIAL PRIMARY KEY,
    order_item_id BIGINT REFERENCES order_items(id) ON DELETE SET NULL,
    -- 주문 항목과 연결 (단독 실행 시 NULL)
    place_id BIGINT REFERENCES places(id) ON DELETE SET NULL,
    -- 추출 완료 후 연결
    naver_url TEXT NOT NULL,
    -- 입력된 네이버 플레이스 URL

    -- === 작업 파라미터 ===
    target_count INT DEFAULT 100,
    -- 목표 키워드 수
    max_rank INT DEFAULT 50,
    -- 최대 랭킹 (이 순위까지만 체크)
    min_rank INT DEFAULT 1,
    name_keyword_ratio FLOAT DEFAULT 0.30,
    -- 상호명 키워드 비율

    -- === 결과 ===
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    -- queued(대기) → running(실행중) → completed(완료) / failed(실패) / cancelled(취소)
    place_name VARCHAR(200),
    -- 추출된 업체명
    result_count INT DEFAULT 0,
    -- 추출된 키워드 수
    results JSONB,
    -- 결과 배열: [{keyword, rank, map_type, keyword_type}, ...]
    error_message TEXT,

    -- === 워커 정보 ===
    proxy_slot INT,
    worker_id VARCHAR(50),
    -- 어떤 워커 인스턴스에서 처리했는지

    -- === 타임스탬프 ===
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_extraction_jobs_status ON extraction_jobs(status);
CREATE INDEX idx_extraction_jobs_place_id ON extraction_jobs(place_id);
CREATE INDEX idx_extraction_jobs_order_item_id ON extraction_jobs(order_item_id);
```

---

#### 테이블 10: `superap_accounts` (슈퍼앱 계정)
> 소스: `reference/quantum-campaign/backend/app/models/account.py`

```sql
CREATE TABLE superap_accounts (
    id SERIAL PRIMARY KEY,
    user_id_superap VARCHAR(100) UNIQUE NOT NULL,
    -- 슈퍼앱 로그인 ID (예: "트래픽 제이투랩", "트래픽 제이투랩24")
    password_encrypted TEXT NOT NULL,
    -- AES 암호화된 비밀번호
    agency_name VARCHAR(100),
    -- 대행사명

    -- === 멀티 테넌트 ===
    company_id INT REFERENCES companies(id),
    -- 이 계정이 소속된 회사 (일류기획 or 제이투랩)

    -- === 네트워크 프리셋 연결 ===
    network_preset_id INT REFERENCES network_presets(id),
    -- 이 계정이 속한 네트워크 프리셋
    -- 네트워크 프리셋이 계정군 + 매체 타겟팅을 정의

    unit_cost INT NOT NULL DEFAULT 21,
    -- 실제 단가 (원). 예: 21원, 25원(24계정)

    assignment_order INT NOT NULL DEFAULT 0,
    -- 같은 프리셋 내에서의 배정 순서 (낮을수록 먼저)

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_superap_accounts_company_id ON superap_accounts(company_id);
CREATE INDEX idx_superap_accounts_network_preset_id ON superap_accounts(network_preset_id);
```

> **캠페인 템플릿과의 차이**: superap_accounts는 "어떤 계정으로 등록하는지",
> campaign_templates는 "폼을 어떻게 채우는지"(트래픽/저장하기/명소). 완전히 다른 축.

---

#### 테이블 11: `campaigns` (캠페인)
> 소스: `reference/quantum-campaign/backend/app/models/campaign.py`

```sql
CREATE TABLE campaigns (
    id BIGSERIAL PRIMARY KEY,
    campaign_code VARCHAR(20),
    -- 슈퍼앱에서 발급한 캠페인 코드
    superap_account_id INT REFERENCES superap_accounts(id),
    -- 어떤 슈퍼앱 계정으로 등록했는지
    order_item_id BIGINT REFERENCES order_items(id) ON DELETE SET NULL,
    -- 주문 항목 연결
    place_id BIGINT REFERENCES places(id),
    -- 플레이스 연결
    extraction_job_id BIGINT REFERENCES extraction_jobs(id) ON DELETE SET NULL,
    -- 어떤 추출 작업에서 키워드를 가져왔는지

    -- === 캠페인 기본 정보 ===
    agency_name VARCHAR(100),
    place_name VARCHAR(200) NOT NULL DEFAULT '',
    place_url TEXT NOT NULL,
    campaign_type VARCHAR(50) NOT NULL,
    -- 'traffic' 또는 'save' (영문 통일, products.code와 일치)
    -- 한국어 표시명은 campaign_templates.type_name 참조

    -- === 기간/한도 ===
    registered_at TIMESTAMPTZ,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    daily_limit INT NOT NULL,
    total_limit INT,
    current_conversions INT DEFAULT 0,

    -- === 모듈 결과 ===
    landmark_name VARCHAR(200),
    -- 랜드마크 모듈 결과
    step_count INT,
    -- 도보 스텝 모듈 결과
    module_context JSONB,
    -- 모듈 실행 결과 전체 (디버깅 + 연장 시 재활용)

    -- === 키워드 ===
    original_keywords TEXT,
    -- 최초 등록 시 키워드 원본

    -- === 상태 ===
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending(대기) → queued(등록대기) → registering(등록중) → active(활성)
    -- → paused(일시정지) → completed(완료) / failed(실패) / expired(만료)
    registration_step VARCHAR(30),
    -- 등록 진행 단계: queued, logging_in, running_modules, filling_form,
    --                submitting, extracting_code, completed, failed
    registration_message TEXT,
    -- 현재 단계 메시지

    -- === 연장 ===
    extend_target_id BIGINT,
    -- 연장 대상 캠페인 ID (campaigns.id와 동일 타입)
    extension_history JSONB,
    -- 연장 이력: [{round, date, keywords_added, ...}, ...]

    -- === 키워드 로테이션 ===
    last_keyword_change TIMESTAMPTZ,
    -- 마지막 키워드 교체 시각

    -- === 네트워크 + 회사 ===
    network_preset_id INT REFERENCES network_presets(id),
    -- 어떤 네트워크로 세팅되었는지 (리워드 중복참여 방지 추적용)
    company_id INT REFERENCES companies(id),
    -- 역정규화: 회사별 캠페인 조회 편의

    -- === 타임스탬프 ===
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_place_id ON campaigns(place_id);
CREATE INDEX idx_campaigns_superap_account_id ON campaigns(superap_account_id);
CREATE INDEX idx_campaigns_order_item_id ON campaigns(order_item_id);
CREATE INDEX idx_campaigns_end_date ON campaigns(end_date);
CREATE INDEX idx_campaigns_company_id ON campaigns(company_id);
CREATE INDEX idx_campaigns_network_preset_id ON campaigns(network_preset_id);
```

---

#### 테이블 12: `campaign_keyword_pool` (캠페인 키워드 풀)
> 소스: `reference/quantum-campaign/backend/app/models/keyword.py`

```sql
CREATE TABLE campaign_keyword_pool (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    -- 로테이션 대상 키워드
    is_used BOOLEAN DEFAULT FALSE,
    -- 오늘 사용 여부
    used_at TIMESTAMPTZ,
    -- 사용 시각
    round_number INT DEFAULT 1,
    -- 몇 번째 라운드에서 추가된 키워드인지

    UNIQUE (campaign_id, keyword)
);

CREATE INDEX idx_campaign_kw_pool_campaign_id ON campaign_keyword_pool(campaign_id);
CREATE INDEX idx_campaign_kw_pool_is_used ON campaign_keyword_pool(is_used);
```

---

#### 테이블 13: `campaign_templates` (캠페인 템플릿)
> 소스: `reference/quantum-campaign/backend/app/models/template.py`
>
> **네트워크 프리셋과의 차이**:
> - 캠페인 템플릿 = superap.io **폼 내용** (설명문구, 힌트, 이미지, 모듈)
> - 네트워크 프리셋 = **어떤 계정 + 어떤 매체**로 세팅할지
> - 독립적 축: "트래픽 템플릿"을 "네트워크1"으로도 "네트워크2"로도 세팅 가능

```sql
CREATE TABLE campaign_templates (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    -- 영문 코드: 'traffic', 'save', 'landmark'
    -- campaigns.campaign_type과 매칭
    type_name VARCHAR(50) UNIQUE NOT NULL,
    -- 한글 표시명: "트래픽", "저장하기", "명소"
    description_template TEXT NOT NULL,
    -- 참여 방법 설명 템플릿 (변수 치환 가능)
    hint_text TEXT NOT NULL,
    -- 정답 추측 힌트
    campaign_type_selection VARCHAR(100),
    -- 슈퍼앱 캠페인 유형 선택값 (예: "Place Quiz")
    links JSONB NOT NULL DEFAULT '[]',
    -- 캠페인 링크 목록
    hashtag VARCHAR(100),
    -- 해시태그 (예: "#cpc_detail_place")
    image_url_200x600 TEXT,
    image_url_720x780 TEXT,
    -- 캠페인 이미지 URL
    conversion_text_template TEXT,
    -- 텍스트 기반 전환 인식 템플릿 (step_count 대신 사용)
    steps_start TEXT,
    -- 도보 모듈 시작점
    modules JSONB DEFAULT '[]',
    -- 사용 모듈 목록 (예: ["landmark", "steps"])
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

---

#### 테이블 14: `balance_transactions` (잔액 거래)
> 소스: jtwolablife의 orders.BalanceTransaction 참고

```sql
CREATE TABLE balance_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    order_id BIGINT REFERENCES orders(id) ON DELETE SET NULL,
    amount NUMERIC(12,0) NOT NULL,
    -- 양수 = 입금(충전), 음수 = 출금(차감)
    balance_after NUMERIC(12,0) NOT NULL,
    -- 거래 후 잔액
    transaction_type VARCHAR(20) NOT NULL,
    -- deposit(입금), withdrawal(출금), order_charge(주문차감),
    -- refund(환불), adjustment(조정)
    description TEXT,
    -- 거래 설명
    created_by UUID REFERENCES users(id),
    -- 처리한 관리자
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_balance_tx_user_id ON balance_transactions(user_id);
CREATE INDEX idx_balance_tx_order_id ON balance_transactions(order_id);
CREATE INDEX idx_balance_tx_created_at ON balance_transactions(created_at);
```

---

#### 테이블 15: `pipeline_states` (파이프라인 상태)
> 신규: 주문 항목별 전체 파이프라인 진행 추적

```sql
CREATE TABLE pipeline_states (
    id BIGSERIAL PRIMARY KEY,
    order_item_id BIGINT NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
    -- 주문 항목과 1:1 대응

    current_stage VARCHAR(30) NOT NULL DEFAULT 'draft',
    -- 현재 단계:
    -- draft               : 하부계정 임시저장
    -- submitted           : 총판이 올림
    -- payment_confirmed   : 입금 확인됨
    -- extraction_queued   : 키워드 추출 대기
    -- extraction_running  : 키워드 추출 진행중
    -- extraction_done     : 키워드 추출 완료
    -- account_assigned    : 슈퍼앱 계정 자동 배정됨
    -- assignment_confirmed: 계정 배정 확인 (company_admin)
    -- campaign_registering: 캠페인 등록 진행중
    -- campaign_active     : 캠페인 활성
    -- management          : 관리/모니터링 단계
    -- completed           : 전체 완료
    -- failed              : 실패
    -- cancelled           : 취소

    previous_stage VARCHAR(30),
    extraction_job_id BIGINT REFERENCES extraction_jobs(id),
    campaign_id BIGINT REFERENCES campaigns(id),
    error_message TEXT,
    metadata JSONB,
    -- 단계별 추가 데이터

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (order_item_id)
    -- 주문 항목과 1:1 대응
);

CREATE INDEX idx_pipeline_order_item_id ON pipeline_states(order_item_id);
CREATE INDEX idx_pipeline_current_stage ON pipeline_states(current_stage);
```

---

#### 테이블 16: `pipeline_logs` (파이프라인 로그)

```sql
CREATE TABLE pipeline_logs (
    id BIGSERIAL PRIMARY KEY,
    pipeline_state_id BIGINT NOT NULL REFERENCES pipeline_states(id) ON DELETE CASCADE,
    from_stage VARCHAR(30),
    to_stage VARCHAR(30) NOT NULL,
    trigger_type VARCHAR(50),
    -- user_action, auto_extraction_complete, auto_registration_complete,
    -- scheduler, admin_override, error
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_logs_state_id ON pipeline_logs(pipeline_state_id);
```

---

#### 테이블 17: `refresh_tokens` (JWT 리프레시 토큰)
> 신규: JWT 토큰 관리 및 블랙리스트

```sql
CREATE TABLE refresh_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    -- 리프레시 토큰의 SHA-256 해시
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    -- NULL이면 유효, 값 있으면 폐기됨
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
```

---

#### 테이블 18: `system_settings` (시스템 설정)
> 신규: 런타임 변경 가능한 설정값

```sql
CREATE TABLE system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 초기 데이터 예시:
-- INSERT INTO system_settings VALUES
--   ('max_concurrent_extractions', '5', '동시 키워드 추출 작업 수'),
--   ('default_target_keyword_count', '200', '기본 키워드 추출 목표 수'),
--   ('extraction_target_count', '200', '접수당 추출 키워드 수');
```

---

#### 테이블 19: `network_presets` (네트워크 프리셋)
> 신규: 리워드 중복 참여자 제한을 위한 네트워크 단계 설정
>
> **핵심 개념**: 같은 업장에 동일 네트워크로 반복 세팅하면 리워드 참여자가 중복됨.
> 네트워크를 나누어 (계정군 + 매체 타겟팅 조합) 참여자 풀을 분산시킴.
>
> **캠페인 템플릿과 분리**: 템플릿은 "폼 내용"(트래픽/저장하기/명소),
> 네트워크는 "어떤 계정 + 어떤 매체로 세팅할지". 독립적 축.

```sql
CREATE TABLE network_presets (
    id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(id),
    -- 소속 회사

    campaign_type VARCHAR(20) NOT NULL,
    -- 'traffic' / 'save'
    -- 이 프리셋이 적용되는 캠페인 유형

    tier_order INT NOT NULL,
    -- 네트워크 우선순위 (1이 먼저, 2가 그 다음)
    -- 같은 업장에 네트워크1 사용 이력 있으면 → 네트워크2로 배정

    name VARCHAR(100) NOT NULL,
    -- 표시명 (예: "네트워크1 (21원+머니워크)", "네트워크2 (25원)")

    media_config JSONB NOT NULL DEFAULT '{}',
    -- 매체 타겟팅 설정
    -- key = 매체 slug/이름, value = ON(true)/OFF(false)
    -- 예: {"머니워크": true, "캐시워크": true, "앱테크A": false}
    -- ⚠ 매체 목록은 superap.io에서 변경될 수 있으므로 JSONB로 유연하게 저장

    description TEXT,
    -- 설명 (예: "21원 계정 + 전체 매체")

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    UNIQUE(company_id, campaign_type, tier_order)
);

CREATE INDEX idx_network_presets_company_id ON network_presets(company_id);
```

**초기 데이터 예시:**
```sql
-- 제이투랩 트래픽 네트워크 설정
INSERT INTO network_presets (company_id, campaign_type, tier_order, name, media_config) VALUES
(2, 'traffic', 1, '네트워크1 (21원+머니워크)', '{"머니워크": true}'),
(2, 'traffic', 2, '네트워크2 (25원, 머니워크 제외)', '{"머니워크": false}');

-- 제이투랩 저장하기 네트워크 설정
INSERT INTO network_presets (company_id, campaign_type, tier_order, name, media_config) VALUES
(2, 'save', 1, '네트워크1 (21원+머니워크)', '{"머니워크": true}'),
(2, 'save', 2, '네트워크2 (25원, 머니워크 제외)', '{"머니워크": false}');
```

---

### 4.3 테이블 요약

| # | 테이블명 | 소스 | 주요 용도 |
|---|---------|------|----------|
| 0 | **companies** | **신규** | **회사/테넌트 (일류기획, 제이투랩)** |
| 1 | users | jtwolablife + 신규 역할 | 유저/인증/5단계 역할 관리 |
| 2 | products | jtwolablife | 상품 정의 + 일일 마감시간 |
| 3 | price_policies | jtwolablife | 유저/역할별 가격 정책 |
| 4 | orders | jtwolablife + 신규 상태 | 주문 접수 (draft→submitted→payment_confirmed) |
| 5 | order_items | jtwolablife + 계정배정 | 주문 항목 + 슈퍼앱 계정 자동 배정 |
| 6 | places | Keyword Extract | 네이버 플레이스 정보 |
| 7 | keywords | Keyword Extract | 추출된 키워드 + 랭킹 |
| 8 | keyword_rank_history | Keyword Extract | 키워드 랭킹 변동 이력 |
| 9 | extraction_jobs | Keyword Extract | 키워드 추출 작업 관리 |
| 10 | superap_accounts | Quantum + 네트워크 | 슈퍼앱 계정 + network_preset 연결 |
| 11 | campaigns | Quantum Campaign | 캠페인 정보 (network_preset_id + company_id 추가) |
| 12 | campaign_keyword_pool | Quantum Campaign | 캠페인별 키워드 로테이션 |
| 13 | campaign_templates | Quantum Campaign | **폼 내용** 템플릿 (code: traffic/save/landmark) |
| 14 | balance_transactions | jtwolablife | 잔액/정산 |
| 15 | pipeline_states | 신규 | 파이프라인 상태 추적 (UNIQUE order_item_id) |
| 16 | pipeline_logs | 신규 | 파이프라인 로그 |
| 17 | refresh_tokens | 신규 | JWT 리프레시 토큰 관리 |
| 18 | system_settings | 신규 | 런타임 시스템 설정 |
| 19 | **network_presets** | **신규** | **네트워크 프리셋 (계정군 + 매체 타겟팅, 중복참여 방지)** |

---

## 5. 파이프라인 상세 흐름

### 5.1 전체 파이프라인

```
[1단계: 접수 (Intake)]
│  sub_account 또는 distributor가 주문 입력
│  ├── 웹 시트(그리드) UI: 플레이스 URL + 유형 + 기간 + 일일한도
│  └── 엑셀 벌크 업로드: 여러 플레이스 일괄 접수 (미리보기 → 확인)
│  ⚠ 키워드는 접수 폼에서 받지 않음 (추출 후 자동 배정)
│  ⚠ 상품별 마감시간 체크 (예: 트래픽 18:00 KST)
│
│  접수 폼 필드:
│  ├── 플레이스 URL (필수)
│  ├── 캠페인 유형 (traffic / save)
│  ├── 작업 시작일 (필수)
│  ├── 작업 만료일 (필수)
│  ├── 일일 작업량 (기본값 300)
│  └── 접수일 (자동 기록)
│
│  DB 동작:
│  ├── Order 생성 (status: draft, order_number 자동 부여)
│  ├── OrderItem 생성 (플레이스별 1건)
│  └── PipelineState 생성 (stage: draft)
│
▼
[2단계: 총판 확인 → 제출]
│  distributor가 하부계정 접수건 확인
│  ├── 하부계정별 접수 현황 조회
│  ├── 검토 후 총 접수건으로 올림
│  └── Order status: draft → submitted
│
▼
[3단계: 입금 확인 (company_admin)]
│  company_admin 화면에 총 합산 도착
│  ├── 총 물량 × 단가 = 총 금액 확인
│  ├── 입금 확인 버튼 클릭 (수동)
│  └── Order status: submitted → payment_confirmed
│      payment_status: unpaid → confirmed
│
│  DB 동작:
│  ├── BalanceTransaction 생성 (잔액 차감, 입금확인 시점)
│  └── PipelineState 업데이트 (payment_confirmed)
│
│  입금 미확인 시:
│  └── Order status: submitted → rejected (반려)
│
▼
[4단계: 키워드 추출 (Extraction)]
│  입금 확인 후 자동 시작
│
│  api-server → keyword-worker:
│  POST /internal/jobs
│  { "naver_url": "...", "target_count": 200, "order_item_id": 42 }
│
│  keyword-worker 실행:
│  ├── Phase 0: Playwright로 PlaceData 수집
│  ├── Phase 1: 샘플 키워드로 노출 검증 (신지도/구지도)
│  ├── Phase 2: 키워드 생성 (1,000~3,000개 풀)
│  └── Phase 3: 상위 200개 랭킹 체크 (GraphQL API)
│
│  키워드 전략:
│  ├── 접수당 200개 키워드 추출
│  ├── 같은 플레이스 재접수 시 → 기존 풀에 추가 (중복 제외)
│  ├── 중복 체크: UNIQUE(campaign_id, keyword) DB 제약으로 자동 처리
│  └── 기존 수기 키워드 입력과 비슷한 양, 자동화된 방식
│
│  DB 동작:
│  ├── Place 레코드 생성/업데이트
│  ├── Keyword 레코드 벌크 생성
│  ├── ExtractionJob 상태 업데이트 (completed)
│  └── PipelineState 업데이트 (extraction_done)
│
▼
[5단계: 자동 배정 - 연장 판정 + 네트워크 결정]
│  추출 완료 후 자동 실행
│
│  ┌─────────────────────────────────────────────────────┐
│  │  자동 배정 알고리즘 (리워드 중복참여 방지)             │
│  │                                                      │
│  │  Step 1: 연장 가능 여부 판정                          │
│  │  ├── 같은 place_id의 최근 캠페인 조회                 │
│  │  │   WHERE campaign.end_date >= 접수일 - 7일          │
│  │  │     AND campaign.end_date <= 접수일                │
│  │  ├── 있으면: 기존 total_limit + 신규 total_limit      │
│  │  │   ├── < 10,000 → 연장 (같은 계정, 같은 네트워크)  │
│  │  │   └── ≥ 10,000 → 신규 세팅 (다음 네트워크)        │
│  │  └── 없으면: 신규 세팅                                │
│  │                                                      │
│  │  Step 2: 네트워크 결정 (신규 세팅 시)                  │
│  │  ├── 이 place_id + campaign_type 조합으로             │
│  │  │   사용된 network_preset 이력 조회 (campaigns 테이블)│
│  │  ├── 미사용 프리셋 중 tier_order 가장 낮은 것 선택     │
│  │  │   예: 네트워크1 사용 이력 있으면 → 네트워크2        │
│  │  └── 모든 네트워크 소진 시 → 유형 변경 제안            │
│  │      (트래픽 → "저장하기 어때?", 저장 → "트래픽 어때?")│
│  │                                                      │
│  │  Step 3: 계정 선택 (선택된 네트워크 내)                │
│  │  ├── 해당 network_preset에 연결된 계정 조회            │
│  │  │   WHERE is_active = TRUE                          │
│  │  └── ORDER BY assignment_order ASC                    │
│  └─────────────────────────────────────────────────────┘
│
│  DB 동작:
│  ├── OrderItem.assigned_account_id = 선택된 계정
│  ├── OrderItem.assignment_status = 'auto_assigned'
│  └── PipelineState 업데이트 (account_assigned)
│
│  ⚠ 배정 결과는 company_admin/system_admin에게만 표시
│  ⚠ 유형 변경 제안은 알림으로 company_admin에게 전달
│
▼
[6단계: 배정 확인 (company_admin)]
│  company_admin 화면에서 배정 결과 확인
│  ├── 자동 배정된 계정 + 네트워크 확인
│  ├── 네트워크별 사용 이력 표시
│  ├── [변경]: 다른 계정/네트워크로 수동 변경
│  └── [최종 세팅 시작]: 캠페인 등록 트리거
│
│  DB 동작:
│  ├── OrderItem.assignment_status = 'confirmed' (또는 'overridden')
│  └── PipelineState 업데이트 (assignment_confirmed)
│
▼
[7단계: 캠페인 등록 (Campaign Registration)]
│  api-server → campaign-worker:
│  POST /internal/campaigns/register
│  { "campaign_id": 123, "account_id": 1, "template_id": 1 }
│
│  campaign-worker 실행:
│  ├── Step 1: 슈퍼앱 로그인 (Playwright)
│  ├── Step 2: 모듈 실행 (landmark, place_info, steps)
│  ├── Step 3: 캠페인 폼 입력 (템플릿 기반, 키워드 자동 배정)
│  ├── Step 4: 제출
│  └── Step 5: 캠페인 코드 추출
│
│  DB 동작:
│  ├── Campaign 업데이트 (campaign_code, status: active)
│  ├── CampaignKeywordPool 벌크 생성 (추출된 200개에서)
│  └── PipelineState 업데이트 (campaign_active)
│
▼
[8단계: 관리 (Management)]
│  APScheduler (campaign-worker, 10분 간격):
│  ├── 활성 캠페인 순회
│  ├── 키워드 사용량 체크
│  ├── 일일 한도 도달 시 → 미사용 키워드로 자동 교체
│  ├── 23:50 KST → 강제 교체
│  ├── 키워드 풀 소진 시 → 자동 재활용 (is_used 리셋)
│  └── 캠페인 상태 동기화
│
▼
[9단계: 완료/연장]
  ├── 캠페인 종료 → status: completed
  ├── 연장 접수 시:
  │   ├── 합산 < 10,000타 → 기존 캠페인 연장 (같은 계정/네트워크)
  │   │   └── 키워드 재추출 200개 → 기존 풀에 추가 (중복 제외)
  │   └── 합산 ≥ 10,000타 → 다음 네트워크로 신규 세팅
  │       └── 모든 네트워크 소진 시 → 유형 변경 제안
  └── PipelineState: completed
```

### 5.2 파이프라인 상태 전이도

```
draft (하부계정 임시저장)
  │
  ├── (총판 확인) ──→ submitted
  │                     │
  │                     ├── (입금 확인) ──→ payment_confirmed
  │                     │                      │
  │                     │                      ├── (자동) ──→ extraction_queued
  │                     │                      │                  │
  │                     │                      │                  ├── (워커 시작) ──→ extraction_running
  │                     │                      │                  │                      │
  │                     │                      │                  │                      ├── (성공) ──→ extraction_done
  │                     │                      │                  │                      │                  │
  │                     │                      │                  │                      │                  ├── (자동) ──→ account_assigned
  │                     │                      │                  │                      │                  │                  │
  │                     │                      │                  │                      │                  │                  ├── (확인) ──→ assignment_confirmed
  │                     │                      │                  │                      │                  │                  │                  │
  │                     │                      │                  │                      │                  │                  │                  ├── (등록) ──→ campaign_registering
  │                     │                      │                  │                      │                  │                  │                  │                  │
  │                     │                      │                  │                      │                  │                  │                  │                  ├── (성공) ──→ campaign_active ──→ management ──→ completed
  │                     │                      │                  │                      │                  │                  │                  │                  │
  │                     │                      │                  │                      │                  │                  │                  │                  └── (실패) ──→ failed
  │                     │                      │                  │                      │                  │                  │
  │                     │                      │                  │                      │                  │
  │                     │                      │                  │                      └── (실패) ──→ failed
  │                     │                      │
  │                     │
  │                     └── (반려) ──→ cancelled (rejected)
  │
  └── (취소) ──→ cancelled

  * failed 상태에서 재시도 가능 (이전 단계로 복귀)
  * cancelled/rejected에서 재접수 가능 (새 주문 생성)
```

---

## 6. API 명세

### 6.1 api-server 공개 API (Port 8000)

#### 인증

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/auth/register` | 회원가입 |
| POST | `/api/v1/auth/login` | 로그인 → JWT 토큰 발급 |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 |
| POST | `/api/v1/auth/logout` | 로그아웃 (토큰 블랙리스트) |

#### 유저 관리

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/api/v1/users` | 유저 목록 | system_admin, company_admin, order_handler |
| POST | `/api/v1/users` | 유저 생성 | system_admin, company_admin, distributor (하부만) |
| GET | `/api/v1/users/{id}` | 유저 상세 | 본인 + 상위 역할 |
| PATCH | `/api/v1/users/{id}` | 유저 수정 | system_admin, company_admin |
| DELETE | `/api/v1/users/{id}` | 유저 삭제 | system_admin |
| GET | `/api/v1/users/me` | 내 정보 | 모두 |
| GET | `/api/v1/users/{id}/descendants` | 하위 유저 트리 | system_admin, company_admin, distributor |

#### 상품

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/api/v1/products` | 상품 목록 | 모두 |
| POST | `/api/v1/products` | 상품 생성 | system_admin |
| GET | `/api/v1/products/{id}` | 상품 상세 + 마감시간 | 모두 |
| PATCH | `/api/v1/products/{id}` | 상품 수정 | system_admin |

#### 주문 접수

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/api/v1/orders` | 주문 목록 (필터링, 페이지네이션) | 역할별 범위 |
| POST | `/api/v1/orders` | 주문 생성 (status: draft) | distributor, sub_account |
| GET | `/api/v1/orders/{id}` | 주문 상세 | 역할별 범위 |
| GET | `/api/v1/orders/{id}/items` | 주문 항목 목록 | 역할별 범위 |
| PATCH | `/api/v1/orders/{id}` | 주문 수정 | system_admin, company_admin, order_handler |
| POST | `/api/v1/orders/{id}/submit` | 총판이 접수건 올림 (draft→submitted) | distributor |
| POST | `/api/v1/orders/{id}/confirm-payment` | 입금 확인 (submitted→payment_confirmed) | company_admin |
| POST | `/api/v1/orders/{id}/reject` | 주문 반려 | company_admin |
| POST | `/api/v1/orders/{id}/cancel` | 주문 취소 | system_admin, company_admin |
| POST | `/api/v1/orders/upload-excel` | 엑셀 벌크 업로드 (미리보기→확인) | distributor, sub_account |
| GET | `/api/v1/orders/template-download` | 엑셀 템플릿 다운로드 | 모두 |
| GET | `/api/v1/orders/deadline-status` | 상품별 마감시간 현황 | 모두 |

> **공통 페이지네이션**: 모든 목록 API는 `?page=1&size=20&sort=created_at&order=desc` 지원

#### 네트워크 프리셋 (company_admin 전용)

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/api/v1/network-presets` | 프리셋 목록 (회사별) | company_admin, system_admin |
| POST | `/api/v1/network-presets` | 프리셋 생성 (계정군 + 매체설정) | company_admin, system_admin |
| PATCH | `/api/v1/network-presets/{id}` | 프리셋 수정 (매체 토글 등) | company_admin, system_admin |
| DELETE | `/api/v1/network-presets/{id}` | 프리셋 삭제 | system_admin |
| GET | `/api/v1/network-presets/media-options` | superap.io 사용 가능 매체 목록 | company_admin, system_admin |

#### 계정 배정 (company_admin 전용)

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/api/v1/assignment/queue` | 배정 대기열 + 네트워크 이력 | company_admin, system_admin |
| POST | `/api/v1/assignment/auto-assign` | 자동 배정 실행 (연장 판정 + 네트워크 결정) | system (내부) |
| PATCH | `/api/v1/assignment/{item_id}/account` | 수동 계정/네트워크 변경 | company_admin, system_admin |
| POST | `/api/v1/assignment/{item_id}/confirm` | 배정 확인 | company_admin, system_admin |
| POST | `/api/v1/assignment/bulk-confirm` | 일괄 확인 + 세팅 시작 | company_admin, system_admin |
| GET | `/api/v1/assignment/place/{place_id}/history` | 업장별 네트워크 사용 이력 | company_admin, system_admin |

#### 플레이스

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/places` | 플레이스 목록 |
| GET | `/api/v1/places/{id}` | 플레이스 상세 |
| GET | `/api/v1/places/{id}/keywords` | 플레이스 키워드 목록 |
| GET | `/api/v1/places/{id}/keywords/rank-history` | 랭킹 이력 |

#### 키워드 추출

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/extraction/start` | 추출 작업 시작 |
| GET | `/api/v1/extraction/jobs` | 작업 목록 |
| GET | `/api/v1/extraction/jobs/{id}` | 작업 상세/결과 |
| POST | `/api/v1/extraction/jobs/{id}/cancel` | 작업 취소 |
| GET | `/api/v1/extraction/events` | SSE 실시간 진행상황 |

#### 캠페인

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/campaigns` | 캠페인 목록 |
| POST | `/api/v1/campaigns` | 캠페인 생성 |
| GET | `/api/v1/campaigns/{id}` | 캠페인 상세 |
| PATCH | `/api/v1/campaigns/{id}` | 캠페인 수정 |
| POST | `/api/v1/campaigns/{id}/register` | 슈퍼앱 등록 시작 |
| POST | `/api/v1/campaigns/{id}/extend` | 캠페인 연장 |
| POST | `/api/v1/campaigns/{id}/pause` | 캠페인 일시정지 |
| POST | `/api/v1/campaigns/{id}/resume` | 캠페인 재개 |
| GET | `/api/v1/campaigns/{id}/keywords` | 키워드 풀 조회 |
| POST | `/api/v1/campaigns/{id}/keywords` | 키워드 추가 |
| POST | `/api/v1/campaigns/{id}/rotate-keywords` | 수동 키워드 교체 |

#### 슈퍼앱 계정

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/api/v1/superap-accounts` | 계정 목록 | company_admin, system_admin |
| POST | `/api/v1/superap-accounts` | 계정 추가 | system_admin |
| PATCH | `/api/v1/superap-accounts/{id}` | 계정 수정 | system_admin |
| DELETE | `/api/v1/superap-accounts/{id}` | 계정 삭제 | system_admin |

#### 캠페인 템플릿

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/api/v1/templates` | 템플릿 목록 | system_admin |
| GET | `/api/v1/templates/{id}` | 템플릿 상세 | system_admin |
| PATCH | `/api/v1/templates/{id}` | 템플릿 수정 | system_admin |

#### 파이프라인

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/pipeline/{order_item_id}` | 파이프라인 현재 상태 |
| GET | `/api/v1/pipeline/{order_item_id}/logs` | 전이 이력 |
| GET | `/api/v1/pipeline/overview` | 전체 파이프라인 현황 |

#### 정산/잔액

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/api/v1/balance/{user_id}` | 유저 잔액 조회 | company_admin, 본인 |
| GET | `/api/v1/balance/{user_id}/transactions` | 거래 내역 | company_admin, 본인 |
| POST | `/api/v1/balance/deposit` | 입금 처리 | company_admin, system_admin |
| POST | `/api/v1/balance/withdraw` | 출금 처리 | company_admin, system_admin |
| GET | `/api/v1/settlement/report` | 정산 리포트 | company_admin, system_admin |

#### 대시보드

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/dashboard/summary` | 종합 통계 |
| GET | `/api/v1/dashboard/pipeline` | 파이프라인 단계별 현황 |
| GET | `/api/v1/dashboard/campaigns` | 캠페인 현황 |
| GET | `/api/v1/dashboard/calendar` | 캘린더 뷰 (마감일 기반) |

### 6.2 keyword-worker 내부 API (Port 8001)

> Docker 내부 네트워크에서만 접근 가능

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/internal/jobs` | 추출 작업 생성 |
| GET | `/internal/jobs/{id}/status` | 작업 상태 조회 |
| GET | `/internal/jobs/{id}/results` | 결과 조회 |
| POST | `/internal/jobs/{id}/cancel` | 작업 취소 |
| GET | `/internal/health` | 헬스체크 |
| GET | `/internal/capacity` | 현재 처리 가능 슬롯 수 |

**요청 예시:**
```json
POST /internal/jobs
{
    "job_id": "ext-001",
    "naver_url": "https://map.naver.com/p/entry/place/1234567890",
    "target_count": 100,
    "max_rank": 50,
    "min_rank": 1,
    "name_keyword_ratio": 0.30,
    "order_item_id": 42
}
```

**응답 예시:**
```json
{
    "job_id": "ext-001",
    "status": "queued",
    "message": "Job queued successfully"
}
```

### 6.3 campaign-worker 내부 API (Port 8002)

> Docker 내부 네트워크에서만 접근 가능

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/internal/campaigns/register` | 캠페인 등록 |
| POST | `/internal/campaigns/{id}/extend` | 캠페인 연장 |
| POST | `/internal/campaigns/{id}/rotate` | 수동 키워드 교체 |
| POST | `/internal/campaigns/bulk-sync` | 전체 캠페인 상태 동기화 |
| GET | `/internal/scheduler/status` | 스케줄러 상태 |
| POST | `/internal/scheduler/trigger` | 수동 트리거 |
| GET | `/internal/health` | 헬스체크 |

**등록 요청 예시:**
```json
POST /internal/campaigns/register
{
    "campaign_id": 123,
    "account_id": 1,
    "template_id": 1
}
```

### 6.4 워커 → api-server 콜백 API

> 워커가 작업 완료 시 api-server에 알림 (PipelineState 자동 전이)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/internal/callback/extraction/{job_id}` | 키워드 추출 완료/실패 알림 |
| POST | `/internal/callback/campaign/{campaign_id}` | 캠페인 등록 완료/실패 알림 |

**콜백 요청 예시:**
```json
POST /internal/callback/extraction/42
{
    "status": "completed",
    "result_count": 200,
    "place_id": 1234567890
}
```

api-server 처리:
1. PipelineState 업데이트 (extraction_done)
2. 자동 배정 엔진 트리거
3. SSE 이벤트 발송 (프론트엔드 실시간 알림)

---

## 7. 기존 코드 → 통합 매핑 가이드

### 7.1 Keyword Extract → keyword-worker

| 기존 파일 | 변경 사항 | 통합 위치 |
|-----------|---------|----------|
| `src/smart_worker.py` | **그대로 유지** | `keyword-worker/src/smart_worker.py` |
| `src/rank_checker_graphql.py` | **그대로 유지** | `keyword-worker/src/rank_checker_graphql.py` |
| `src/place_scraper.py` | **그대로 유지** | `keyword-worker/src/place_scraper.py` |
| `src/models.py` | PlaceData → DB 저장 로직 추가 | `keyword-worker/src/models.py` |
| `src/address_parser.py` | **그대로 유지** | `keyword-worker/src/address_parser.py` |
| `src/keyword_generator.py` | **그대로 유지** | `keyword-worker/src/keyword_generator.py` |
| `src/gemini_client.py` | **그대로 유지** | `keyword-worker/src/gemini_client.py` |
| `web/app.py` | 외부 API → `/internal/` 내부 API로 변환 | `keyword-worker/app.py` |
| `web/session_manager.py` | 인메모리 → PostgreSQL로 변경 | `keyword-worker/db_manager.py` |
| `settings.json` | 환경변수 + DB 설정으로 변경 | `.env` + `keyword-worker/config.py` |

**핵심 변경:**
1. `SessionManager` → PostgreSQL `extraction_jobs` 테이블로 대체
2. `Job` 결과 → `extraction_jobs.results` JSONB + `keywords` 테이블에 저장
3. `PlaceData` → `places` 테이블에 저장
4. 프록시 설정 → 환경변수 또는 DB 설정 테이블

### 7.2 Quantum Campaign → campaign-worker

| 기존 파일 | 변경 사항 | 통합 위치 |
|-----------|---------|----------|
| `backend/app/services/superap.py` | **그대로 유지** | `campaign-worker/services/superap.py` |
| `backend/app/services/campaign_registration.py` | **그대로 유지** | `campaign-worker/services/campaign_registration.py` |
| `backend/app/services/keyword_rotation.py` | **그대로 유지** | `campaign-worker/services/keyword_rotation.py` |
| `backend/app/services/campaign_extension.py` | **그대로 유지** | `campaign-worker/services/campaign_extension.py` |
| `backend/app/services/scheduler.py` | **그대로 유지** | `campaign-worker/services/scheduler.py` |
| `backend/app/services/naver_map.py` | **그대로 유지** | `campaign-worker/services/naver_map.py` |
| `backend/app/modules/*` | **그대로 유지** | `campaign-worker/modules/*` |
| `backend/app/models/*` | SQLite → PostgreSQL 연결 변경 | `campaign-worker/models.py` (shared) |
| `backend/app/routers/*` | 외부 API → `/internal/` 변환 | `campaign-worker/app.py` |
| `backend/app/utils/encryption.py` | **그대로 유지** | `campaign-worker/utils/encryption.py` |

**핵심 변경:**
1. `database.py`의 SQLite URL → PostgreSQL URL (`DATABASE_URL` 환경변수)
2. 외부 라우터들 → `/internal/` prefix 내부 API로 통합
3. 프론트엔드 React → 삭제 (통합 프론트엔드 사용)
4. 기존 모든 서비스 로직 (Playwright, 스케줄러, 모듈 시스템) → **변경 없이 유지**

### 7.3 jtwolablife → api-server (새로 구현)

| Django 기능 | FastAPI 구현 |
|------------|------------|
| `accounts.User` 모델 | `api-server/models/user.py` (5단계 역할 + company_id) |
| `accounts.views` (로그인, CRUD) | `api-server/routers/auth.py`, `users.py` |
| `products.Product` 모델 | `api-server/models/product.py` (daily_deadline 추가) |
| `orders.Order/OrderItem` 모델 | `api-server/models/order.py` (draft→submitted→payment_confirmed) |
| `orders.BalanceTransaction` | `api-server/models/balance.py` (입금확인 시점 차감) |
| Django Admin | React SPA 관리 페이지 |
| Django Template (HTML) | React SPA로 대체 |
| `orders/grid/` 그리드 UI | React 웹 시트 컴포넌트 (접수 + 관리) |
| `orders/settlement/` 정산 | `api-server/routers/settlement.py` |
| - (신규) | `api-server/services/assignment_service.py` (계정 자동 배정) |
| - (신규) | `api-server/routers/assignment.py` (배정 확인 API) |

### 7.4 네트워크 프리셋 vs 캠페인 템플릿 (핵심 분리)

| 구분 | 네트워크 프리셋 (`network_presets`) | 캠페인 템플릿 (`campaign_templates`) |
|------|----------------------------------|-------------------------------------|
| **역할** | **어디에** 세팅할지 (계정 + 매체) | **무엇을** 세팅할지 (폼 내용) |
| **내용** | 계정군 (21원/25원) + 매체 토글 (머니워크 ON/OFF) | 설명문구, 힌트, 이미지, 모듈 |
| **코드** | tier_order (1, 2) | code ('traffic', 'save', 'landmark') |
| **관리자** | company_admin (회사별 설정) | system_admin (전역 설정) |
| **목적** | 리워드 중복참여 방지 (참여자 풀 분산) | superap.io 폼 자동 입력 |
| **관계** | 독립적: 어떤 템플릿이든 어떤 네트워크로 세팅 가능 | 독립적: 네트워크와 무관 |

**조합 예시:**
- "트래픽" 템플릿 + 네트워크1 (21원+머니워크) → 트래픽 캠페인을 저렴하게
- "트래픽" 템플릿 + 네트워크2 (25원, 머니워크 제외) → 같은 업장 2회차
- "저장하기" 템플릿 + 네트워크1 → 네트워크1,2 다 쓴 후 유형 변경 시

### 7.5 접수 양식 변경 사항

**기존 퀀텀 엑셀 (8필드) → 통합 접수 (6필드):**

| 기존 퀀텀 필드 | 통합 접수 | 비고 |
|--------------|---------|------|
| 대행사명 | ❌ 제거 | 로그인 유저의 소속으로 자동 |
| 사용자ID | ❌ 제거 | 로그인 유저로 자동 |
| 시작일 | ✅ 작업 시작일 | 유지 |
| 마감일 | ✅ 작업 만료일 | 유지 |
| 일일 한도 | ✅ 일일 작업량 | 유지 (기본값 300) |
| **키워드** | ❌ **제거** | **추출 후 자동 배정 (200개)** |
| 플레이스 URL | ✅ 유지 | 유지 |
| 캠페인 이름 | ✅ 캠페인 유형 | traffic / save |
| - (신규) | ✅ 접수일 | 자동 기록 |

---

## 8. 단계별 구현 체크리스트

### Phase 1A: 기반 인프라 + 인증

- [ ] 프로젝트 구조 생성

```
unified-platform/
├── api-server/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 앱 초기화
│   │   ├── config.py            # 환경 설정 (Pydantic Settings)
│   │   ├── database.py          # SQLAlchemy async 엔진/세션
│   │   ├── dependencies.py      # 의존성 주입 (DB 세션, 현재 유저 등)
│   │   ├── models/              # SQLAlchemy 모델
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── product.py
│   │   │   ├── order.py
│   │   │   ├── place.py
│   │   │   ├── keyword.py
│   │   │   ├── extraction_job.py
│   │   │   ├── campaign.py
│   │   │   ├── superap_account.py
│   │   │   ├── template.py
│   │   │   ├── balance.py
│   │   │   └── pipeline.py
│   │   ├── schemas/             # Pydantic 스키마 (요청/응답)
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── order.py
│   │   │   ├── place.py
│   │   │   ├── campaign.py
│   │   │   └── ...
│   │   ├── routers/             # API 엔드포인트
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── products.py
│   │   │   ├── orders.py
│   │   │   ├── places.py
│   │   │   ├── extraction.py
│   │   │   ├── campaigns.py
│   │   │   ├── templates.py
│   │   │   ├── superap_accounts.py
│   │   │   ├── pipeline.py
│   │   │   ├── balance.py
│   │   │   ├── settlement.py
│   │   │   └── dashboard.py
│   │   ├── services/            # 비즈니스 로직
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── order_service.py
│   │   │   ├── pipeline_service.py
│   │   │   ├── keyword_worker_client.py   # keyword-worker HTTP 호출
│   │   │   └── campaign_worker_client.py  # campaign-worker HTTP 호출
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── security.py      # JWT, 비밀번호 해싱
│   ├── alembic/                 # DB 마이그레이션
│   │   ├── alembic.ini
│   │   └── versions/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│
├── keyword-worker/              # Phase 2에서 구현
├── campaign-worker/             # Phase 3에서 구현
├── frontend/                    # Phase 4에서 구현
├── docker-compose.yml
├── .env.example
└── docs/
    └── INTEGRATION_PLAN.md      # 이 문서
```

- [ ] FastAPI + SQLAlchemy 2.0 (async) 셋업
- [ ] Alembic 초기화
- [ ] PostgreSQL Docker 컨테이너 (docker-compose.dev.yml)
- [ ] Pydantic Settings (.env 로딩)
- [ ] companies 테이블 + 모델 (일류기획, 제이투랩 초기 데이터)
- [ ] users 테이블 + 모델 (5단계 역할: system_admin~sub_account)
- [ ] refresh_tokens 테이블 + 모델
- [ ] JWT 인증 (login, refresh, logout + 블랙리스트)
- [ ] bcrypt 비밀번호 해싱
- [ ] 역할 기반 접근 제어 (RoleChecker dependency)
- [ ] Users CRUD + 역할별 권한 + 하위 유저 트리
- [ ] 공통 페이지네이션 스키마 (PaginationParams)
- [ ] Swagger 문서 확인 (/docs)
- [ ] 기본 단위 테스트

### Phase 1B: 주문/상품/정산

- [ ] products 테이블 + 모델 (daily_deadline 포함)
- [ ] price_policies 테이블 + 모델
- [ ] orders 테이블 + 모델 (draft→submitted→payment_confirmed 상태)
- [ ] order_items 테이블 + 모델 (assigned_account_id 포함)
- [ ] balance_transactions 테이블 + 모델
- [ ] system_settings 테이블 + 모델
- [ ] Products CRUD
- [ ] Price Policies CRUD + 가격 결정 로직 (유저별→역할별→기본)
- [ ] Orders + OrderItems CRUD (상태 전이 포함)
- [ ] 주문 제출 (submit), 입금 확인 (confirm-payment), 반려 (reject) API
- [ ] 엑셀 업로드 (미리보기 → 확인) + 템플릿 다운로드
- [ ] 마감시간 체크 로직
- [ ] BalanceTransactions CRUD (입금확인 시점 잔액 차감)
- [ ] users.balance 동시성 보호 (SELECT FOR UPDATE)
- [ ] 단위 테스트

### Phase 1C: 파이프라인/통합 모델

- [ ] places 테이블 + 모델 (virtual_phone 포함)
- [ ] keywords + keyword_rank_history 테이블 + 모델
- [ ] extraction_jobs 테이블 + 모델
- [ ] network_presets 테이블 + 모델 (네트워크 프리셋: 계정군 + 매체 타겟팅)
- [ ] superap_accounts 테이블 + 모델 (network_preset_id, unit_cost, assignment_order)
- [ ] campaigns 테이블 + 모델 (network_preset_id, company_id 역정규화)
- [ ] campaign_keyword_pool + campaign_templates 테이블 + 모델 (templates에 code 컬럼)
- [ ] pipeline_states + pipeline_logs 테이블 + 모델 (UNIQUE order_item_id)
- [ ] Places CRUD + Keywords CRUD + Rank History
- [ ] ExtractionJobs CRUD
- [ ] NetworkPresets CRUD (company_admin 전용, 매체 타겟팅 JSONB)
- [ ] SuperapAccounts CRUD (AES 암호화, network_preset 연결)
- [ ] Campaigns CRUD
- [ ] CampaignKeywordPool CRUD (중복 제외 INSERT 로직)
- [ ] CampaignTemplates CRUD
- [ ] PipelineStates + PipelineLogs CRUD
- [ ] 자동 배정 서비스 (연장 판정 7일/10,000타 + 네트워크 순서 + 유형 변경 제안)
- [ ] 계정 배정 API (company_admin 전용, 업장별 네트워크 이력)
- [ ] 워커 콜백 API (/internal/callback/*)
- [ ] Alembic 마이그레이션 생성 + 실행 확인 (전체 20개 테이블)
- [ ] 단위 테스트

### Phase 2: keyword-worker 연동

- [ ] `reference/keyword-extract/` 코드를 `keyword-worker/`로 복사
- [ ] `web/app.py` → `/internal/` 엔드포인트로 리팩토링
- [ ] `SessionManager` → PostgreSQL `extraction_jobs` 테이블로 대체
- [ ] `Job` 완료 시 → `places`, `keywords` 테이블에 결과 저장
- [ ] `PlaceData` → `places` 테이블 저장 로직 추가
- [ ] 환경변수 기반 설정 (프록시, Gemini API 키 등)
- [ ] Dockerfile 작성 (Playwright + Chromium 포함)
- [ ] api-server에 `keyword_worker_client.py` 구현 (httpx 비동기 호출)
- [ ] api-server 추출 API 엔드포인트 구현
- [ ] SSE/WebSocket 실시간 진행상황 전달
- [ ] 연동 테스트 (api-server → keyword-worker → DB 저장)

### Phase 3: campaign-worker 연동

- [ ] `reference/quantum-campaign/backend/` 코드를 `campaign-worker/`로 복사
- [ ] `database.py` SQLite → PostgreSQL 연결 변경
- [ ] 외부 라우터 → `/internal/` 내부 API로 변환
- [ ] 기존 React 프론트엔드 제거
- [ ] APScheduler 유지 (키워드 로테이션, 캠페인 동기화)
- [ ] Dockerfile 작성 (Playwright + Chromium 포함)
- [ ] api-server에 `campaign_worker_client.py` 구현
- [ ] api-server 캠페인 API 엔드포인트 구현
- [ ] PipelineState 자동 전이 로직 구현
- [ ] 연동 테스트 (api-server → campaign-worker → 슈퍼앱)

### Phase 4: React 프론트엔드

- [ ] React + TypeScript + Vite + TailwindCSS 프로젝트 생성
- [ ] 라우터 구성 (React Router)
- [ ] 인증 (로그인/로그아웃, JWT 토큰 관리)
- [ ] 역할별 레이아웃/사이드바
- [ ] 접수 페이지 (단건 폼 + 엑셀 업로드)
- [ ] 주문 목록/상세 페이지
- [ ] 플레이스/키워드 관리 페이지
- [ ] 캠페인 관리 페이지
- [ ] 파이프라인 현황 대시보드
- [ ] 정산/잔액 페이지
- [ ] 실시간 알림 (WebSocket/SSE)

### Phase 5: Docker Compose + AWS 배포

- [ ] `docker-compose.yml` 작성 (5개 서비스)
- [ ] Nginx 설정 (리버스 프록시, HTTPS)
- [ ] `.env.example` 작성
- [ ] AWS EC2 인스턴스 생성 (t3.medium+)
- [ ] Docker + Docker Compose 설치
- [ ] 도메인 연결 + SSL 인증서
- [ ] 배포 스크립트 작성
- [ ] 모니터링 설정 (로그, 헬스체크)
- [ ] 백업 설정 (PostgreSQL 일일 백업)

---

## 9. Docker / AWS 배포 가이드

### 9.1 Docker Compose 구성

```yaml
# docker-compose.yml
version: '3.8'

services:
  # === PostgreSQL ===
  db:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_DB: ${DB_NAME:-j2lab_platform}
      POSTGRES_USER: ${DB_USER:-j2lab}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"  # 개발용, 프로덕션에서는 제거
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-j2lab}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # === 메인 API 서버 ===
  api-server:
    build: ./api-server
    restart: always
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-j2lab}:${DB_PASSWORD}@db:5432/${DB_NAME:-j2lab_platform}
      SECRET_KEY: ${SECRET_KEY}
      KEYWORD_WORKER_URL: http://keyword-worker:8001
      CAMPAIGN_WORKER_URL: http://campaign-worker:8002
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # === 키워드 추출 워커 ===
  keyword-worker:
    build: ./keyword-worker
    restart: always
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-j2lab}:${DB_PASSWORD}@db:5432/${DB_NAME:-j2lab_platform}
      DECODO_USERNAME: ${DECODO_USERNAME}
      DECODO_PASSWORD: ${DECODO_PASSWORD}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      db:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 2G  # Playwright Chromium 메모리

  # === 캠페인 워커 ===
  campaign-worker:
    build: ./campaign-worker
    restart: always
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-j2lab}:${DB_PASSWORD}@db:5432/${DB_NAME:-j2lab_platform}
      AES_ENCRYPTION_KEY: ${AES_ENCRYPTION_KEY}
    depends_on:
      db:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 1G

  # === Nginx (리버스 프록시) ===
  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - ./frontend/dist:/usr/share/nginx/html  # React 빌드 결과
    depends_on:
      - api-server

volumes:
  postgres_data:
```

### 9.2 AWS EC2 권장 사양

| 항목 | 최소 | 권장 |
|------|------|------|
| 인스턴스 | t3.medium | t3.large |
| vCPU | 2 | 2 |
| 메모리 | 4 GB | 8 GB |
| 스토리지 | 30 GB gp3 | 50 GB gp3 |
| OS | Amazon Linux 2023 / Ubuntu 22.04 | Ubuntu 22.04 |

**메모리 분배 (t3.large 8GB 기준):**
- PostgreSQL: ~1 GB
- api-server: ~512 MB
- keyword-worker: ~2 GB (Playwright Chromium)
- campaign-worker: ~1 GB (Playwright Chromium)
- Nginx: ~128 MB
- OS + 여유: ~3.3 GB

### 9.3 배포 절차

```bash
# 1. EC2 접속
ssh -i key.pem ubuntu@your-ec2-ip

# 2. Docker + Docker Compose 설치
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER

# 3. 프로젝트 클론
git clone https://github.com/your-org/unified-platform.git
cd unified-platform

# 4. 환경변수 설정
cp .env.example .env
nano .env  # 실제 값 입력

# 5. 빌드 & 실행
docker compose build
docker compose up -d

# 6. DB 마이그레이션
docker compose exec api-server alembic upgrade head

# 7. 확인
docker compose ps
curl http://localhost:8000/health
```

### 9.4 환경변수 (.env.example)

```env
# === Database ===
DB_NAME=j2lab_platform
DB_USER=j2lab
DB_PASSWORD=your_secure_password_here

# === API Server ===
SECRET_KEY=your_jwt_secret_key_here
DEBUG=false

# === Keyword Worker ===
DECODO_USERNAME=your_decodo_username
DECODO_PASSWORD=your_decodo_password
DECODO_ENDPOINT_COUNT=500
GEMINI_API_KEY=your_gemini_api_key

# === Campaign Worker ===
AES_ENCRYPTION_KEY=your_aes_key_here

# === Internal (워커 → api-server 콜백) ===
API_SERVER_URL=http://api-server:8000

# === CORS ===
CORS_ORIGINS=https://yourdomain.com
```

---

## 10. 데이터 마이그레이션

### 10.1 Quantum Campaign SQLite → PostgreSQL

```python
# scripts/migrate_quantum_data.py
"""
reference/quantum-campaign의 SQLite DB에서 PostgreSQL로 마이그레이션

대상 테이블:
- accounts → superap_accounts
- campaigns → campaigns
- keyword_pool → campaign_keyword_pool
- campaign_templates → campaign_templates
"""
import sqlite3
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

SQLITE_PATH = "reference/quantum-campaign/data/quantum.db"
POSTGRES_URL = "postgresql+asyncpg://..."

async def migrate():
    # 1. SQLite에서 데이터 읽기
    sqlite_conn = sqlite3.connect(SQLITE_PATH)

    # 2. PostgreSQL에 삽입
    # accounts → superap_accounts (필드명 매핑)
    # campaigns → campaigns (status 영문 변환은 이미 완료된 상태)
    # keyword_pool → campaign_keyword_pool
    # campaign_templates → campaign_templates

    sqlite_conn.close()
```

### 10.2 Keyword Extract JSON → PostgreSQL

```python
# scripts/migrate_keyword_data.py
"""
reference/keyword-extract/data/jobs/ 폴더의 JSON 파일들을
extraction_jobs + places + keywords 테이블로 마이그레이션
"""
import json
import glob

JOBS_DIR = "reference/keyword-extract/data/jobs/"

async def migrate():
    for json_file in glob.glob(f"{JOBS_DIR}/**/*.json"):
        with open(json_file) as f:
            job_data = json.load(f)
        # extraction_jobs 레코드 생성
        # 결과에서 place 정보 추출 → places 테이블
        # 키워드 목록 → keywords 테이블
```

---

## 11. 보안 고려사항

| 항목 | 현재 | 통합 후 |
|------|------|--------|
| 슈퍼앱 비밀번호 | AES 암호화 (quantum-campaign) | AES 유지 + 키를 환경변수로 분리 |
| JWT 시크릿 | 하드코딩 (quantum-campaign) | 환경변수 `SECRET_KEY` |
| 프록시 크리덴셜 | `settings.json`에 평문 | 환경변수 `DECODO_USERNAME/PASSWORD` |
| DB 비밀번호 | - | 환경변수 `DB_PASSWORD` |
| CORS | 전체 허용 | 특정 도메인만 (`CORS_ORIGINS`) |
| 내부 API | - | Docker 내부 네트워크만 (외부 비노출) |
| HTTPS | Cloudflare 터널 | Nginx + Let's Encrypt 또는 AWS ALB |

**체크리스트:**
- [ ] `.env`는 `.gitignore`에 포함
- [ ] 프로덕션에서 `DEBUG=false`
- [ ] 슈퍼앱 계정 비밀번호 AES 키 안전 관리
- [ ] PostgreSQL 비밀번호 강력하게 설정
- [ ] worker 포트 외부 비노출 확인
- [ ] SQL injection 방지 (SQLAlchemy ORM 사용)
- [ ] JWT 만료 시간 적절히 설정 (access: 30분, refresh: 7일)

---

## 12. 향후 확장 (+α)

### 단기 (Phase 5 이후)
- [ ] 고객 알림 시스템 (카카오톡/이메일)
- [ ] 자동 리포트 생성 (일간/주간/월간)
- [ ] 키워드 랭킹 변동 알림
- [ ] 캠페인 만료 사전 알림

### 중기
- [ ] 월보장 상품 관리
- [ ] 키워드 추천 AI (이전 성공 데이터 기반)
- [ ] 다중 EC2 → ECS 마이그레이션
- [ ] PostgreSQL → AWS RDS 전환
- [ ] Redis 캐싱 (대시보드 성능)
- [ ] CI/CD 파이프라인 (GitHub Actions → Docker Hub → EC2)

### 장기
- [ ] 외부 고객 포털 (셀러/대행사 전용)
- [ ] API 키 기반 외부 연동
- [ ] 모바일 대시보드
- [ ] 데이터 분석/BI 대시보드
- [ ] A/B 테스트 (키워드 전략 비교)

---

## 부록: 용어 정리

| 용어 | 설명 |
|------|------|
| 신지도 (new_map) | 네이버 새 지도 UI (음식점, 병원 등 주요 업종) |
| 구지도 (old_map) | 네이버 구 지도 UI (일반 업종) |
| 슈퍼앱 (superap) | superap.io - 리워드 광고 플랫폼 |
| 트래픽 (traffic) | 네이버 플레이스 방문(트래픽) 유도 캠페인 |
| 저장하기 (save) | 네이버 플레이스 "저장" 유도 캠페인 |
| 키워드 로테이션 | 일일 키워드를 자동으로 교체하는 기능 |
| 파이프라인 | 접수 → 추출 → 배정 → 세팅 → 관리 전체 흐름 |
| PlaceData | 키워드 추출 시 수집하는 플레이스 전체 정보 |
| curl_cffi | Chrome TLS 지문을 모방하는 HTTP 클라이언트 (안티봇 우회) |
| Decodo | 한국 IP 프록시 서비스 |
| 총판 (distributor) | 거래처 계정. 하부계정을 생성/관리할 수 있음 |
| 하부계정 (sub_account) | 총판 아래 계정. 접수만 가능 |
| 네트워크 프리셋 | 계정군 + 매체 타겟팅 조합. 리워드 중복참여 방지를 위해 네트워크를 분리 |
| 네트워크1 | 기본 네트워크 (21원 계정 + 머니워크 ON). 먼저 사용 |
| 네트워크2 | 차선 네트워크 (25원 계정 + 머니워크 OFF). 네트워크1 사용 후 전환 |
| 10,000타 제한 | 같은 업장의 연장 캠페인 합산이 10,000 전환을 넘으면 다른 네트워크로 신규 세팅 |
| 캠페인 템플릿 | superap.io 폼 내용 (트래픽/저장하기/명소). 네트워크와 독립적 |
| 계정 자동 배정 | 연장 판정(7일/10,000타) + 네트워크 순서 기반 자동 계정 선택 |
| 입금 확인 | company_admin이 총 접수 금액 입금을 확인하는 수동 절차 |
| 마감시간 | 상품별 일일 접수 마감 시간 (이후 접수 차단) |
| 머니워크 (MoneyWalk) | superap.io의 매체 중 하나. 네트워크1에서는 ON, 네트워크2에서는 OFF |
