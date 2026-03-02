# J2LAB 통합 플랫폼

> 이 파일은 Claude Code 세션 시작 시 자동 로드됩니다.
> 새 환경에서 clone 후 이 파일 하나로 전체 맥락을 파악할 수 있습니다.

## 프로젝트 요약

네이버 플레이스 광고 자동화 플랫폼.
**접수 → 키워드 추출 → 캠페인 등록 → 관리** 파이프라인을 하나의 시스템으로 통합.

기존에 독립적으로 운영하던 2개 시스템 + OMS를 FastAPI로 통합:
- **Keyword Extract**: 네이버 플레이스 URL → 키워드 자동 추출 + 랭킹 체크
- **Quantum Campaign**: 슈퍼앱(superap.io) 캠페인 자동 등록 + 키워드 로테이션
- **jtwolablife OMS**: 주문 접수 / 유저 관리 / 정산 (Django → FastAPI 전환)

## 현재 상태 (2026-02-28 기준)

**모든 Phase 완료, EC2 운영 중**

| Phase | 내용 | 상태 |
|-------|------|:----:|
| 0 | 문서/구조/reference 코드 정리 | 완료 |
| 1A | 기반 인프라 + 인증 (companies, users, JWT) | 완료 |
| 1B | 주문/상품/정산 (orders, products, balance) | 완료 |
| 1C | 파이프라인/통합 모델 (places, campaigns, 자동배정) | 완료 |
| 2 | keyword-worker 연동 | 완료 |
| 3 | campaign-worker 연동 | 완료 |
| 4 | React 프론트엔드 (23페이지) | 완료 |
| 5 | Docker/AWS 배포 | **운영 중** |

### 운영 환경

- **EC2**: `52.78.114.92` (t3.medium, Ubuntu 22.04, ap-northeast-2)
- **URL**: http://52.78.114.92/
- **API 문서**: http://52.78.114.92/docs (Swagger)
- **컨테이너**: 5개 (api-server, keyword-worker, campaign-worker, nginx, postgres) 모두 healthy
- **로그인**: admin@jtwolab.kr / jjlab1234!j (system_admin)

### 시스템 규모

| 항목 | 수치 |
|------|------|
| API 엔드포인트 | 124개 |
| DB 테이블 | 24개 (20 + alembic + 3 추가) |
| 프론트엔드 페이지 | 23개 |
| API 테스트 (scripts/api-test-full.py) | 108/108 PASS |
| 페이지 검증 (scripts/page-verify.py) | 65/66 OK |

### DB 현재 상태 (2026-02-28 초기화 후)

- users: 1명 (admin@jtwolab.kr)
- companies: 1개 (제이투랩)
- categories: 4개, campaign_templates: 3개 — 유지
- 나머지 테이블: 비어있음 (캠페인 데이터는 추후 퀀텀에서 마이그레이션 예정)

## 아키텍처

```
[React SPA] → [Nginx :80] → [api-server :8000] ← 메인 FastAPI
                  │                │
                  │      ┌─────────┼─────────┐
                  │      ▼                   ▼
                  │  [keyword-worker :8001]  [campaign-worker :8002]
                  │  Playwright 키워드 추출   Playwright 캠페인 등록
                  │  curl_cffi 랭킹 체크     APScheduler 키워드 로테이션
                  │      │                   │
                  │      └─────────┬─────────┘
                  │                ▼
                  │      [PostgreSQL 15 통합 DB]
                  │         24개 테이블
                  │
                  └── try_files → SPA fallback (/index.html)

Nginx 설정:
  /api/*     → proxy_pass api-server (rate limit: 30r/s)
  /api/v1/auth/* → proxy_pass api-server (rate limit: 5r/s)
  /internal/ → deny all (403)
  /health    → proxy_pass api-server
  /*         → try_files → /index.html (SPA)
```

## Repo 구조

```
├── CLAUDE.md                            # ← 이 파일 (세션 자동 로드)
├── README.md                            # 프로젝트 개요
├── .env.example                         # 환경변수 템플릿
├── docker-compose.yml                   # 프로덕션 (5 서비스)
├── nginx/nginx.conf                     # Nginx 리버스 프록시 설정
│
├── docs/
│   ├── INTEGRATION_PLAN.md              # 전체 계획서 (초기 설계 문서)
│   ├── DEVELOPMENT_WORKFLOW.md          # 에이전트 오케스트레이션 가이드
│   ├── PHASE_CHECKLIST.md              # Phase별 완료 체크리스트
│   └── CURRENT_STATUS.md              # 현재 상태 상세 (업데이트 필요 시 여기)
│
├── scripts/
│   ├── api-test-full.py                # 108건 API 통합 테스트 (21개 섹션)
│   ├── page-verify.py                  # 프론트엔드 23페이지 + API 검증
│   ├── cleanup-test-data.py            # 테스트 데이터 정리
│   ├── verify-clean.py                 # 초기화 상태 확인
│   ├── migrate-quantum-data.py         # quantum SQLite → PostgreSQL (미사용)
│   ├── deploy.sh                       # 배포 스크립트
│   ├── init-db.sh                      # DB 초기화
│   ├── seed-data.sh                    # 초기 데이터
│   └── backup-db.sh                    # PostgreSQL 백업
│
├── reference/                           # 기존 시스템 원본 코드 (수정 금지)
│   ├── keyword-extract/
│   ├── quantum-campaign/
│   └── oms-django/
│
├── api-server/                          # FastAPI 메인 서버
│   └── app/
│       ├── core/        (config, database, security, deps)
│       ├── models/      (24개 테이블)
│       ├── schemas/     (Pydantic v2)
│       ├── routers/     (16개 라우터)
│       ├── services/    (25개 서비스 + worker_clients.py)
│       └── tests/       (332개 단위 테스트)
│
├── keyword-worker/                      # 키워드 추출 워커
├── campaign-worker/                     # 캠페인 자동화 워커
└── frontend/                            # React SPA
    └── src/
        ├── api/         (20개 API 모듈)
        ├── pages/       (23개 페이지)
        ├── components/  (공통 + feature 컴포넌트)
        ├── routes/      (React Router + ProtectedRoute)
        ├── utils/       (format.ts, schema.ts)
        └── types/       (TypeScript 타입 정의)
```

## 프론트엔드 라우트 (실제 경로)

| 경로 | 페이지 | 권한 |
|------|--------|------|
| `/login` | LoginPage | 공개 |
| `/` | DashboardPage | 모든 로그인 유저 |
| `/orders` | OrdersPage | 모든 로그인 유저 |
| `/orders/grid` | OrderGridPage | 모든 로그인 유저 |
| `/orders/:id` | OrderDetailPage | 모든 로그인 유저 |
| `/notices` | NoticesPage | 모든 로그인 유저 |
| `/campaigns` | CampaignsPage | admin/handler |
| `/campaigns/add` | CampaignAddPage | admin/handler |
| `/campaigns/upload` | CampaignUploadPage | admin/handler |
| `/campaigns/accounts` | SuperapAccountsPage | admin/handler |
| `/campaigns/templates` | CampaignTemplatesPage | admin/handler |
| `/campaigns/:id` | CampaignDetailPage | admin/handler |
| `/assignments` | AssignmentQueuePage | admin/handler |
| `/users` | UsersPage | system_admin/company_admin |
| `/products` | ProductsPage | system_admin/company_admin |
| `/products/prices/matrix` | PriceMatrixPage | system_admin/company_admin |
| `/products/categories` | CategoriesPage | system_admin/company_admin |
| `/settlements` | SettlementPage | system_admin/company_admin |
| `/calendar` | CalendarPage | admin/handler/distributor |
| `/companies` | CompaniesPage | system_admin |
| `/settings` | SettingsPage | system_admin |
| `/settlements/secret` | SettlementSecretPage | system_admin |
| `*` | NotFoundPage | - |

## Worker 클라이언트 (api-server → worker HTTP 호출)

`api-server/app/services/worker_clients.py`에 13개 함수 구현:

**Keyword Worker** (6개):
- `dispatch_extraction_job` → POST /internal/jobs
- `get_extraction_job_status` → GET /internal/jobs/{id}/status
- `get_extraction_job_results` → GET /internal/jobs/{id}/results
- `cancel_extraction_job` → POST /internal/jobs/{id}/cancel
- `get_keyword_worker_capacity` → GET /internal/capacity
- `check_worker_health("keyword")` → GET /internal/health

**Campaign Worker** (7개):
- `dispatch_campaign_registration` → POST /internal/campaigns/register
- `dispatch_campaign_extension` → POST /internal/campaigns/{id}/extend
- `dispatch_keyword_rotation` → POST /internal/campaigns/{id}/rotate-keywords
- `dispatch_campaign_bulk_sync` → POST /internal/campaigns/bulk-sync
- `get_campaign_worker_scheduler_status` → GET /internal/scheduler/status
- `trigger_campaign_worker_scheduler` → POST /internal/scheduler/trigger
- `check_worker_health("campaign")` → GET /internal/health

## 핵심 문서 가이드

| 문서 | 용도 |
|------|------|
| `CLAUDE.md` (이 파일) | 세션 시작 시 전체 맥락 파악 |
| `docs/CURRENT_STATUS.md` | 현재 상태 + 수정 이력 상세 |
| `docs/PHASE_CHECKLIST.md` | Phase별 완료 추적 + 남은 TODO |
| `docs/INTEGRATION_PLAN.md` | 초기 설계서 (DB 스키마, API 명세) |
| `docs/DEVELOPMENT_WORKFLOW.md` | 에이전트 개발 프로세스 |

## 중요 경고

1. `.env`, `settings.json` = **실제 크리덴셜** → git 커밋 절대 금지
2. 이 repo = **반드시 Private 유지** (내부 코드 + 운영 데이터 포함)
3. `reference/` 폴더 = 기존 코드 원본 → **수정 금지**
4. **superap.io 실제 캠페인 생성 절대 금지**
   - `DRY_RUN=true` 환경변수로 제어: true이면 최종 제출 스킵
5. quantum-campaign Docker 데이터 = 운영 데이터, 절대 건드리지 않기

## 기술 스택

| 영역 | 기술 |
|------|------|
| API 서버 | FastAPI + SQLAlchemy 2.0 (async) + Alembic |
| DB | PostgreSQL 15 |
| Workers | Playwright + curl_cffi + APScheduler |
| 인증 | JWT (access + refresh) + bcrypt + AES |
| 프론트엔드 | React 18 + TypeScript + Vite + TailwindCSS |
| 배포 | Docker Compose + Nginx + AWS EC2 (t3.medium) |
| Python | 3.11+ |

## 워크플로우 기능 보완 (2026-03-02)

| Phase | 기능 | 상태 |
|-------|------|:----:|
| 0 | 원가 계산 오류 수정 (cost_unit_price) | 구현 완료 |
| 1 | 접수 시 AI 추천 (GET /places/recommend) | 구현 완료 |
| 3 | 마감 트리거 (APScheduler, setup_delay_minutes) | 구현 완료 |
| 4 | 신규/연장 선택 UI (POST /assignment/{id}/choose) | 구현 완료 |
| 6 | 정산 대시보드 강화 (by-handler/company/date) | 구현 완료 |
| - | 총판 접수건 선택 (include/exclude) | 구현 완료 |

### 추가 API 엔드포인트

- `GET /places/recommend` — AI 추천 (PHASE 1)
- `POST /assignment/{id}/choose` — 신규/연장 선택 (PHASE 4)
- `GET /settlements/by-handler` — 담당자별 정산 (PHASE 6)
- `GET /settlements/by-company` — 회사별 정산 (PHASE 6)
- `GET /settlements/by-date` — 일자별 정산 (PHASE 6)
- `GET /orders/sub-account-pending` — 하부계정 대기 접수건
- `POST /orders/{id}/include` — 접수건 포함
- `POST /orders/{id}/exclude` — 접수건 제외
- `POST /orders/bulk-include` — 일괄 포함

### DB 마이그레이션 필요 (009)

```
alembic upgrade head  # order_items.cost_unit_price, products.setup_delay_minutes, orders.selection_*
```

### 새 파일

- `api-server/app/core/scheduler.py` — APScheduler 설정
- `frontend/src/api/places.ts` — 추천 API 모듈
- `frontend/src/components/features/orders/SubAccountOrders.tsx` — 총판 접수건 선택

## 남은 TODO

- [ ] quantum-campaign SQLite → PostgreSQL 캠페인 데이터 마이그레이션
- [ ] 도메인 + SSL 설정 (Let's Encrypt)
- [ ] 백업 자동화 (cron + scripts/backup-db.sh)
- [ ] CI/CD 파이프라인 (GitHub Actions)
- [ ] EC2에 apscheduler 패키지 설치 필요 (`pip install apscheduler`)
