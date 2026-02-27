# J2LAB 통합 플랫폼 — 시스템 아키텍처

## 1. 전체 시스템 구조

```
                         ┌──────────────────────────────────────────────┐
                         │              Client (Browser)                │
                         └─────────────────┬────────────────────────────┘
                                           │ HTTP/HTTPS (80/443)
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │              Nginx (j2lab-nginx)              │
                    │  ┌────────────────────────────────────────┐  │
                    │  │ /api/v1/*    → proxy to api-server:8000│  │
                    │  │ /internal/*  → deny all (403)          │  │
                    │  │ /health      → proxy to api-server:8000│  │
                    │  │ /docs        → proxy to api-server:8000│  │
                    │  │ /*           → React SPA (static files)│  │
                    │  └────────────────────────────────────────┘  │
                    │  Rate Limit: API 30r/s | Auth 5r/s           │
                    └──────────────┬───────────────────────────────┘
                                   │ [public network]
                                   ▼
          ┌─────────────────────────────────────────────────────────┐
          │              api-server (j2lab-api-server :8000)         │
          │                                                         │
          │  FastAPI + SQLAlchemy 2.0 (async) + Alembic             │
          │                                                         │
          │  역할:                                                    │
          │  - 외부 API (인증, CRUD, 오케스트레이션)                      │
          │  - Worker 작업 디스패치 (HTTP POST)                        │
          │  - Worker 콜백 수신 (/internal/callback/*)                │
          │  - 파이프라인 상태 관리                                      │
          └─────┬──────────────────┬──────────────────┬─────────────┘
                │ HTTP dispatch     │ HTTP dispatch     │ asyncpg
                ▼                  ▼                    ▼
   ┌────────────────────┐ ┌────────────────────┐ ┌──────────────────┐
   │ keyword-worker     │ │ campaign-worker    │ │  PostgreSQL 15   │
   │ (j2lab-keyword     │ │ (j2lab-campaign    │ │  (j2lab-postgres) │
   │  -worker :8001)    │ │  -worker :8002)    │ │                  │
   │                    │ │                    │ │  23개 테이블       │
   │ Playwright         │ │ Playwright         │ │  멀티테넌트        │
   │ + curl_cffi        │ │ + APScheduler      │ │  (일류기획/제이투랩)│
   │ + Decodo proxy     │ │ + DRY_RUN mode     │ │                  │
   │                    │ │                    │ │                  │
   │ 키워드 추출          │ │ 캠페인 등록          │ │                  │
   │ 플레이스 스크래핑     │ │ 키워드 자동 변경      │ │                  │
   │ 랭킹 체크           │ │ 상태 동기화          │ │                  │
   └────────┬───────────┘ └────────┬───────────┘ └──────────────────┘
            │ HTTP callback         │ HTTP callback        ▲ ▲ ▲
            │ + X-Internal-Secret   │ + X-Internal-Secret   │ │ │
            └───────────┬───────────┘                       │ │ │
                        ▼                                   │ │ │
              api-server /internal/callback/*               │ │ │
                                                            │ │ │
              [internal network — Docker 내부만 접근 가능]     ─┘ │ │
              keyword-worker ──────── DB 직접 접근 ──────────────┘ │
              campaign-worker ─────── DB 직접 접근 ────────────────┘
```

## 2. Docker 네트워크 토폴로지

```
┌─ public network ──────────────────────┐
│                                       │
│  nginx ◄──── api-server               │
│                                       │
└───────────────────────────────────────┘

┌─ internal network (격리) ──────────────┐
│                                       │
│  api-server ──── keyword-worker       │
│       │                               │
│       ├──── campaign-worker           │
│       │                               │
│       └──── PostgreSQL                │
│                                       │
│  ※ Worker는 외부 접근 불가             │
└───────────────────────────────────────┘
```

## 3. 서비스 사양

| 서비스 | 컨테이너 | 포트 | 기술 스택 | 메모리 | CPU |
|--------|---------|------|----------|--------|-----|
| PostgreSQL 15 | j2lab-postgres | 5432 (내부) | postgres:15-alpine | 1G | 1.0 |
| API 서버 | j2lab-api-server | 8000 (내부) | FastAPI + SQLAlchemy async | 512M | 1.0 |
| 키워드 워커 | j2lab-keyword-worker | 8001 (내부) | FastAPI + Playwright + curl_cffi | 2G | 2.0 |
| 캠페인 워커 | j2lab-campaign-worker | 8002 (내부) | FastAPI + Playwright + APScheduler | 1G | 1.0 |
| Nginx | j2lab-nginx | 80/443 (외부) | nginx:1.27-alpine | 128M | 0.5 |
| 프론트엔드 빌드 | j2lab-frontend-build | - (일회성) | React + Vite + TailwindCSS | - | - |

## 4. 데이터 모델 (23개 테이블)

### 4.1 테이블 관계도

```
companies ─────────────────────────────────────────────────────────┐
  │                                                                │
  ├─► users ◄── (self: parent_id)                                  │
  │     │                                                          │
  │     ├─► orders ──► order_items ──► pipeline_states ──► pipeline_logs
  │     │                  │                │
  │     │                  │                ├─► extraction_jobs ──► places ──► keywords
  │     │                  │                │                          │
  │     │                  │                └─► campaigns ──► campaign_keyword_pool
  │     │                  │                       │
  │     │                  └─► products ──► price_policies
  │     │
  │     ├─► balance_transactions
  │     ├─► refresh_tokens
  │     ├─► notifications
  │     └─► notices (author)
  │
  ├─► superap_accounts ──► network_presets
  │         │
  │         └─► campaigns (superap_account_id)
  │
  ├─► categories (독립 — products.category는 문자열 매칭)
  │
  ├─► campaign_templates
  │
  └─► system_settings
```

### 4.2 서비스별 DB 접근 범위

| 서비스 | 접근 테이블 | 모드 |
|--------|-----------|------|
| **api-server** | 전체 23개 | 전체 CRUD + 오케스트레이션 |
| **keyword-worker** | extraction_jobs, places, keywords, keyword_rank_history | 직접 쓰기 + 콜백 |
| **campaign-worker** | campaigns, campaign_keyword_pool, superap_accounts, campaign_templates | 직접 쓰기 + 콜백 |

## 5. API 구조

### 5.1 외부 API (22개 라우터)

| 그룹 | 프리픽스 | 설명 |
|------|---------|------|
| **인증** | /api/v1/auth | 로그인, 리프레시, 로그아웃, 회원가입 |
| **회사** | /api/v1/companies | 회사 CRUD |
| **유저** | /api/v1/users | 유저 CRUD |
| **상품** | /api/v1/products | 상품/가격정책 CRUD |
| **카테고리** | /api/v1/categories | 카테고리 CRUD + 정렬 |
| **주문** | /api/v1/orders | 주문 생명주기 (접수→완료) |
| **잔액** | /api/v1/balance | 입금/출금 |
| **배정** | /api/v1/assignment | 자동배정, 확인, 오버라이드 |
| **파이프라인** | /api/v1/pipeline | 파이프라인 상태/로그/재시도 |
| **캠페인** | /api/v1/campaigns | 캠페인 CRUD + 등록/연장/키워드 |
| **캠페인 템플릿** | /api/v1/campaign-templates | 등록 폼 템플릿 |
| **superap 계정** | /api/v1/superap-accounts | superap.io 계정 관리 |
| **네트워크 프리셋** | /api/v1/network-presets | 계정그룹 + 미디어 타겟팅 |
| **추출 작업** | /api/v1/extraction-jobs | 키워드 추출 조회 |
| **플레이스** | /api/v1/places | 네이버 플레이스 데이터 |
| **대시보드** | /api/v1/dashboard | 요약, 강화, 캠페인통계 |
| **스케줄러** | /api/v1/scheduler | 스케줄러 상태/수동실행 (프록시) |
| **정산** | /api/v1/settlements | 수익/이익 분석 |
| **알림** | /api/v1/notifications | 인앱 알림 |
| **공지** | /api/v1/notices | 회사 공지 |
| **설정** | /api/v1/system-settings | 런타임 설정 KV |
| **헬스** | /health | 헬스체크 |

### 5.2 내부 API (Worker 간 통신)

```
api-server → keyword-worker:
  POST /internal/jobs                          키워드 추출 디스패치
  GET  /internal/jobs/{id}/status              추출 상태 조회
  POST /internal/jobs/{id}/cancel              추출 취소

api-server → campaign-worker:
  POST /internal/campaigns/register            캠페인 등록 디스패치
  POST /internal/campaigns/{id}/extend         캠페인 연장
  POST /internal/campaigns/{id}/rotate-keywords 키워드 변경
  POST /internal/campaigns/bulk-sync           상태 일괄 동기화
  GET  /internal/scheduler/status              스케줄러 상태
  POST /internal/scheduler/trigger             수동 실행

keyword-worker → api-server:
  POST /internal/callback/extraction/{job_id}  추출 완료/실패 콜백

campaign-worker → api-server:
  POST /internal/callback/campaign/{campaign_id} 등록 완료/실패 콜백

※ 모든 콜백에 X-Internal-Secret 헤더 필수
```

### 5.3 인증 플로우

```
[로그인]
  POST /auth/login {email, password}
    → bcrypt 검증
    → JWT access_token (HS256, 30분) + refresh_token (랜덤, 7일)
    → refresh_token은 SHA-256 해시로 DB 저장

[토큰 갱신]
  POST /auth/refresh {refresh_token}
    → DB에서 해시 검증 + 만료 확인 + 폐기 여부
    → 새 access_token + 새 refresh_token (로테이션)

[보호]
  Authorization: Bearer <access_token>
    → get_current_user: JWT 디코딩 → DB에서 유저 조회
    → get_current_active_user: is_active 확인
    → RoleChecker: 역할 확인
```

## 6. 역할 체계

### 6.1 5단계 역할 계층

```
system_admin (0)  ── 전체 시스템 관리, 모든 회사 접근
  │
  └─ company_admin (1)  ── 회사 관리, 주문/캠페인/정산/유저
       │
       └─ order_handler (2)  ── 주문 처리, 본인 담당 캠페인만
            │
            └─ distributor (3)  ── 주문 접수, 하위 계정 관리
                 │
                 └─ sub_account (4)  ── 주문만 접수
```

### 6.2 역할별 데이터 범위

| 데이터 | system_admin | company_admin | order_handler | distributor | sub_account |
|--------|:---:|:---:|:---:|:---:|:---:|
| 주문 | 전체 | 자기 회사 | 자기 회사 | 본인+하위 | 본인만 |
| 캠페인 | 전체 | 자기 회사 | managed_by=본인 | 접근불가 | 접근불가 |
| 대시보드 매출 | 전체 | 자기 회사 | 자기 회사 | 본인+하위 | 본인만 |
| 파이프라인 | 전체 | 자기 회사 | 자기 회사 | 숨김 | 숨김 |
| 유저 생성 | 모든 역할 | handler/dist/sub | sub_account만 | - | - |

### 6.3 역할별 페이지 접근

```
                        sys  comp  handler  dist  sub
대시보드         /         ●     ●      ●      ●     ●
주문 접수       /orders/grid  ●     ●      -      ●     ●
주문 내역       /orders      ●     ●      ●      ●     ●
공지사항        /notices     ●     ●      ●      ●     ●
마감 캘린더     /calendar    ●     ●      ●      ●     -
캠페인 대시보드  /campaigns   ●     ●      ●      -     -
캠페인 추가     /campaigns/* ●     ●      ●      -     -
상품 관리       /products    ●     ●      -      -     -
유저 관리       /users       ●     ●      -      -     -
정산 관리       /settlements ●     ●      -      -     -
회사 관리       /companies   ●     -      -      -     -
시스템 설정     /settings    ●     -      -      -     -
수익 분석       /settlements ●     -      -      -     -
              /secret
```
