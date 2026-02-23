# Phase 체크리스트

> 현재 진행 상태를 추적합니다. 각 Phase 완료 시 체크 표시를 업데이트하세요.

---

## Phase 0: 프로젝트 구조 및 문서

- [x] 프로젝트 폴더 구조 생성
- [x] CLAUDE.md (세션 컨텍스트)
- [x] README.md (프로젝트 개요)
- [x] INTEGRATION_PLAN.md (전체 계획서)
- [x] DEVELOPMENT_WORKFLOW.md (개발 워크플로우)
- [x] PHASE_CHECKLIST.md (이 파일)
- [x] .gitignore
- [x] .env.example
- [x] GitHub Private Repo 생성 + push

---

## Phase 1A: 기반 인프라 + 인증 (`phase-1a/auth`)

### 1A.1 프로젝트 셋업
- [x] FastAPI 프로젝트 초기화 (`api-server/`)
- [x] SQLAlchemy 2.0 async 설정
- [x] Alembic 초기화
- [x] PostgreSQL Docker 컨테이너 (docker-compose.dev.yml)
- [x] Pydantic Settings (.env 로딩)

### 1A.2 핵심 모델
- [x] companies (회사/테넌트: 일류기획, 제이투랩)
- [x] users (5단계 역할: system_admin~sub_account, company_id)
- [x] refresh_tokens (JWT 관리)

### 1A.3 인증
- [x] JWT 발급 (login) + 리프레시 + 로그아웃 (블랙리스트)
- [x] bcrypt 비밀번호 해싱
- [x] 역할 기반 접근 제어 (RoleChecker dependency)
- [x] 공통 페이지네이션 스키마

### 1A.4 CRUD + 테스트
- [x] Companies CRUD (system_admin 전용)
- [x] Users CRUD + 역할별 권한 + 하위 유저 트리
- [x] pytest 설정 + 인증/유저 테스트 (121개 테스트 통과)
- [x] Swagger 문서 확인

### 1A.5 검증
- [x] Agent B 검증 완료
- [x] Agent C 재검증 완료 (2026-02-23)
- [ ] main 브랜치 merge

---

## Phase 1B: 주문/상품/정산 (`phase-1b/orders`)

### 1B.1 모델
- [x] products (상품 + daily_deadline 마감시간)
- [x] price_policies (가격 정책)
- [x] orders (주문: draft→submitted→payment_confirmed)
- [x] order_items (주문 항목 + assigned_account_id 계정배정)
- [x] balance_transactions (잔액 거래)
- [x] system_settings (시스템 설정)

### 1B.2 CRUD + 비즈니스 로직
- [x] Products CRUD + 마감시간 체크
- [x] Price Policies CRUD + 가격 결정 로직 (유저별→역할별→기본)
- [x] Orders CRUD + 상태 전이 (submit, confirm-payment, reject, cancel)
- [ ] 엑셀 업로드 (미리보기→확인) + 템플릿 다운로드 *(Phase 4 프론트엔드와 함께 구현 예정)*
- [ ] 마감시간 체크 로직 (deadline-status API) *(Phase 4 프론트엔드와 함께 구현 예정)*
- [x] BalanceTransactions + 잔액 차감 (입금확인 시점, SELECT FOR UPDATE)
- [x] SystemSettings CRUD (system_admin 전용, JSONB 값 upsert)
- [x] 테스트 (229개 통과: 121 Phase 1A + 108 Phase 1B)

### 1B.3 검증
- [x] Agent B 검증 완료 (2026-02-23, 59개 엣지케이스 추가)
- [x] Agent C 재검증 완료 (2026-02-23, 229개 테스트 100% 통과, 보안 리뷰 완료)
- [ ] main 브랜치 merge

---

## Phase 1C: 파이프라인/통합 모델 (`phase-1c/pipeline`)

### 1C.1 모델
- [x] places (플레이스 + virtual_phone)
- [x] keywords + keyword_rank_history
- [x] extraction_jobs (추출 작업)
- [x] network_presets (네트워크 프리셋: 계정군 + 매체 타겟팅 설정)
- [x] superap_accounts (슈퍼앱 계정 + network_preset_id + unit_cost)
- [x] campaigns (campaign_type 영문 + module_context + network_preset_id)
- [x] campaign_keyword_pool (중복 제외 로직)
- [x] campaign_templates (code 컬럼으로 영문 매핑: traffic/save/landmark)
- [x] pipeline_states (cancelled 포함, UNIQUE order_item_id) + pipeline_logs

### 1C.2 CRUD + 서비스
- [x] Places/Keywords/RankHistory CRUD
- [x] ExtractionJobs CRUD
- [x] NetworkPresets CRUD (company_admin 전용, 매체 타겟팅 JSONB)
- [x] SuperapAccounts CRUD (company_admin 전용, AES 암호화, 프리셋 연결)
- [x] Campaigns CRUD
- [x] CampaignKeywordPool CRUD (UNIQUE 제약 중복 제외)
- [x] CampaignTemplates CRUD
- [x] PipelineStates + Logs CRUD
- [x] 자동 배정 서비스 (연장 판정 + 네트워크 순서 + 10,000타 제한)
- [x] 계정 배정 API (company_admin 전용, 응답 필드 필터링)
- [x] 워커 콜백 API (/internal/callback/*)
- [x] Alembic 마이그레이션 (전체 20개 테이블)
- [x] 테스트 (332개 통과: 284 Phase 1A-C + 48 Phase 1C 엣지케이스)

### 1C.3 검증
- [x] Agent B 검증 완료 (2026-02-23, 48개 엣지케이스 추가, pipeline_state 중복 전이 수정)
- [x] Agent C 재검증 완료 (2026-02-23, 332개 테스트 100% 통과, 20개 테이블 마이그레이션 확인, 보안 리뷰 완료)
- [ ] main 브랜치 merge

---

## Phase 2: keyword-worker 연동

### 2.1 워커 셋업
- [x] Keyword Extract 코드를 `keyword-worker/`로 구성
- [ ] Dockerfile (Playwright + Chromium) *(Phase 5 배포 시 구현)*
- [x] `/internal/` API 엔드포인트 구현 (6개: jobs CRUD, health, capacity)
- [x] PostgreSQL 연결 설정 (SQLAlchemy 2.0 async, 동일 DB 공유)

### 2.2 기능 연동
- [x] `web/app.py` → 내부 API로 변환 (routers/internal.py)
- [x] `SessionManager` → DB 기반으로 변환 (extraction_service.py)
- [x] PlaceData → places 테이블 저장 (upsert 지원)
- [x] 추출 결과 → keywords 테이블 저장 (중복 UNIQUE 제약 처리)
- [x] ExtractionJob 상태 관리 (queued→running→completed/failed/cancelled)
- [x] 키워드 생성 엔진 (10단계 R1-R10 조합, 업종별 분기)
- [x] 랭킹 체크 (GraphQL API, 배치 병렬 처리)
- [x] 예약 키워드 자동 생성 (신지도 레스토랑 한정)
- [x] api-server 콜백 (완료/실패 알림)

### 2.3 api-server 연동
- [ ] keyword_worker_client.py (httpx 비동기 호출) *(Phase 3와 함께 통합 구현 예정)*
- [ ] 추출 시작/상태/결과 API *(api-server 측 라우터 추가 필요)*
- [ ] PipelineState 자동 전이 (extraction_queued → running → done) *(콜백 수신 라우터 Phase 1C에서 구현 완료)*

### 2.4 테스트
- [x] 워커 헬스체크 (127개 테스트 통과: 47 기본 + 80 엣지케이스)
- [x] URL 파서 테스트 (11개: 모든 URL 형식 + 엣지케이스)
- [x] 키워드 생성 테스트 (업종별 + 지역 조합 + 중복 제거)
- [x] 랭킹 체크 테스트 (mock HTTP + PLT/PLL 판정)
- [x] 추출 서비스 테스트 (DB 저장 + 상태 전이 + 취소)
- [x] API 라우터 테스트 (검증 + 에러 응답)
- [x] api-server 회귀 테스트 (332개 테스트 100% 통과)

### 2.5 검증
- [x] Agent B 검증 완료 (2026-02-23, 80개 엣지케이스 추가, 6건 버그 수정)
- [x] Agent C 재검증 완료 (2026-02-23, 127+332 테스트 100% 통과, Internal API 6개 엔드포인트 준수, 콜백 형식 확인, 모델 일관성 확인, 보안 리뷰 완료)
- [ ] main 브랜치 merge

---

## Phase 3: campaign-worker 연동

### 3.1 워커 셋업
- [x] Quantum Campaign 코드를 `campaign-worker/`로 구성
- [ ] Dockerfile (Playwright + Chromium) *(Phase 5 배포 시 구현)*
- [x] SQLite → PostgreSQL 전환 (SQLAlchemy 2.0 async, 동일 DB 공유)
- [x] `/internal/` API 엔드포인트 구현 (7개: register, extend, rotate, bulk-sync, scheduler/status, scheduler/trigger, health)

### 3.2 기능 연동
- [x] 캠페인 등록 자동화 (superap_client.py - SuperapController → SuperapClient 리팩토링)
- [x] 키워드 로테이션 (APScheduler 10분 간격, 255자 제한, 재활용 로직)
- [x] 캠페인 연장 (total_limit/daily_limit/end_date 수정)
- [x] 캠페인 상태 동기화 (한글→영문 정규화 + 전환수 업데이트)

### 3.3 api-server 연동
- [ ] campaign_worker_client.py *(Phase 5 배포 시 api-server 측 구현)*
- [x] 캠페인 등록/연장/로테이션 Internal API (BackgroundTasks 비동기 실행)
- [x] api-server 콜백 발송 (campaign_registrar → /internal/callback/campaign/{id})

### 3.4 테스트
- [x] 워커 헬스체크 (132개 테스트 통과: 41 기본 + 91 엣지케이스)
- [x] 캠페인 등록 흐름 (mock 기반 API 테스트)
- [x] 키워드 로테이션 테스트 (rotation check, 255자 제한, 빈 풀 재활용)
- [x] API 검증 테스트 (422 입력 검증, 409 스케줄러 충돌, 404/405 라우팅)
- [x] 보안 테스트 (AES 암호화/복호화, 레거시 호환, 키 파생)

### 3.5 검증
- [x] Agent B+C 통합 검증 완료 (2026-02-23, 91개 엣지케이스 추가, reference 대비 코드 확인, INTEGRATION_PLAN 7개 엔드포인트 준수, 보안 리뷰 완료)
- [ ] main 브랜치 merge

---

## Phase 4: React 프론트엔드

### 4.1 셋업
- [x] React + TypeScript + Vite 초기화
- [x] TailwindCSS 설정
- [x] React Router 구성
- [x] API 클라이언트 (axios + JWT 인터셉터)

### 4.2 페이지
- [x] 로그인/로그아웃
- [x] 대시보드 (역할별)
- [x] 주문 접수 (단건 폼)
- [ ] 주문 접수 (엑셀 벌크) *(Phase 5 또는 후속 개선 시 구현 예정)*
- [x] 주문 목록/상세
- [ ] 플레이스/키워드 관리 *(캠페인 상세에서 키워드 풀 표시, 별도 페이지는 후속 구현 예정)*
- [x] 캠페인 관리
- [x] 파이프라인 현황 (대시보드에 파이프라인 차트 포함)
- [ ] 정산/잔액 관리 *(후속 개선 시 구현 예정)*
- [x] 시스템 설정 (admin)

### 4.3 테스트
- [x] 각 페이지 렌더링 확인 (빌드 성공 + ESLint 통과)
- [ ] API 연동 확인 *(현재 mock 데이터 사용, 실제 API 연동은 배포 후 검증)*
- [x] 역할별 접근 제어 확인 (ProtectedRoute + Sidebar 역할 필터링)

### 4.4 검증
- [x] Agent B+C 통합 검증 완료 (2026-02-23, 빌드 성공, ESLint 0 에러, 보안 리뷰 완료)
- [ ] main 브랜치 merge

---

## Phase 5: Docker Compose + AWS 배포

### 5.1 Docker
- [x] Dockerfile: api-server (python:3.11-slim, multi-stage)
- [x] Dockerfile: keyword-worker (mcr.microsoft.com/playwright/python)
- [x] Dockerfile: campaign-worker (mcr.microsoft.com/playwright/python)
- [x] Dockerfile: frontend (node:22-alpine build -> nginx:1.27-alpine serve, multi-stage)
- [x] docker-compose.yml (6개 서비스: db, api-server, keyword-worker, campaign-worker, nginx, frontend-build)
- [x] docker-compose.dev.yml 확장 (full 서비스 + hot reload, profiles 지원)
- [x] Nginx 설정 (리버스 프록시, gzip, rate limiting, security headers, /internal/ 차단)
- [x] 헬스체크 설정 (모든 서비스)
- [x] 볼륨 설정 (postgres_data, frontend_dist)
- [x] 네트워크 분리 (internal: DB+workers, public: nginx+api-server)
- [x] .dockerignore (api-server, keyword-worker, campaign-worker, frontend)

### 5.2 배포 스크립트
- [x] scripts/deploy.sh (deploy, update, status, logs, stop)
- [x] scripts/init-db.sh (DB 초기화 + Alembic migration)
- [x] scripts/seed-data.sh (초기 데이터: 회사 2개, system_admin 1명)
- [x] scripts/backup-db.sh (PostgreSQL 백업 + 7일 보관 + 자동 정리)
- [x] .env.example 업데이트 (전체 환경변수 템플릿)

### 5.3 AWS 배포 (인프라 구성은 실 환경에서 진행)
- [ ] EC2 인스턴스 생성 (t3.medium+)
- [ ] Docker + Docker Compose 설치
- [ ] 도메인 + SSL 설정 (Let's Encrypt)
- [ ] DB 마이그레이션 실행

### 5.4 검증
- [x] Agent B+C 통합 검증 완료 (2026-02-23, 591개 테스트 100% 통과, Dockerfile non-root user 보완, Nginx server_tokens off 추가, 네트워크 분리/보안 헤더/rate limiting/내부 API 차단 확인, seed-data 명세 일치 확인)
- [ ] main 브랜치 merge

---

## 최종 검증 (5라운드)

- [ ] Round 1: E2E 파이프라인 테스트
- [ ] Round 2: 보안 취약점 스캔
- [ ] Round 3: 성능/안정성 테스트
- [ ] Round 4: 엣지케이스 + 에러 핸들링
- [ ] Round 5: 최종 리뷰 + 문서 정리

---

## 데이터 마이그레이션

- [ ] quantum-campaign SQLite → PostgreSQL 마이그레이션
- [ ] Keyword Extract JSON → PostgreSQL 마이그레이션
