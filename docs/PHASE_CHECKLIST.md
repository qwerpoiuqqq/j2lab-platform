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
- [ ] places (플레이스 + virtual_phone)
- [ ] keywords + keyword_rank_history
- [ ] extraction_jobs (추출 작업)
- [ ] network_presets (네트워크 프리셋: 계정군 + 매체 타겟팅 설정)
- [ ] superap_accounts (슈퍼앱 계정 + network_preset_id + unit_cost)
- [ ] campaigns (campaign_type 영문 + module_context + network_preset_id)
- [ ] campaign_keyword_pool (중복 제외 로직)
- [ ] campaign_templates (code 컬럼으로 영문 매핑: traffic/save/landmark)
- [ ] pipeline_states (cancelled 포함, UNIQUE order_item_id) + pipeline_logs

### 1C.2 CRUD + 서비스
- [ ] Places/Keywords/RankHistory CRUD
- [ ] ExtractionJobs CRUD
- [ ] NetworkPresets CRUD (company_admin 전용, 매체 타겟팅 JSONB)
- [ ] SuperapAccounts CRUD (company_admin 전용, AES 암호화, 프리셋 연결)
- [ ] Campaigns CRUD
- [ ] CampaignKeywordPool CRUD (UNIQUE 제약 중복 제외)
- [ ] CampaignTemplates CRUD
- [ ] PipelineStates + Logs CRUD
- [ ] 자동 배정 서비스 (연장 판정 + 네트워크 순서 + 10,000타 제한)
- [ ] 계정 배정 API (company_admin 전용, 응답 필드 필터링)
- [ ] 워커 콜백 API (/internal/callback/*)
- [ ] Alembic 마이그레이션 (전체 20개 테이블)
- [ ] 테스트

### 1C.3 검증
- [ ] Agent B 검증 완료
- [ ] Agent C 재검증 완료
- [ ] main 브랜치 merge

---

## Phase 2: keyword-worker 연동

### 2.1 워커 셋업
- [ ] Keyword Extract 코드를 `keyword-worker/`로 구성
- [ ] Dockerfile (Playwright + Chromium)
- [ ] `/internal/` API 엔드포인트 구현
- [ ] PostgreSQL 연결 설정

### 2.2 기능 연동
- [ ] `web/app.py` → 내부 API로 변환
- [ ] `SessionManager` → DB 기반으로 변환
- [ ] PlaceData → places 테이블 저장
- [ ] 추출 결과 → keywords 테이블 저장
- [ ] ExtractionJob 상태 관리

### 2.3 api-server 연동
- [ ] keyword_worker_client.py (httpx 비동기 호출)
- [ ] 추출 시작/상태/결과 API
- [ ] PipelineState 자동 전이 (extraction_queued → running → done)

### 2.4 테스트
- [ ] 워커 헬스체크
- [ ] 추출 작업 생성 → 완료 흐름
- [ ] api-server → keyword-worker 연동 테스트

### 2.5 검증
- [ ] Agent B 검증 완료
- [ ] Agent C 재검증 완료
- [ ] main 브랜치 merge

---

## Phase 3: campaign-worker 연동

### 3.1 워커 셋업
- [ ] Quantum Campaign 코드를 `campaign-worker/`로 구성
- [ ] Dockerfile (Playwright + Chromium)
- [ ] SQLite → PostgreSQL 전환
- [ ] `/internal/` API 엔드포인트 구현

### 3.2 기능 연동
- [ ] 캠페인 등록 자동화 (superap.py 유지)
- [ ] 키워드 로테이션 (APScheduler 유지)
- [ ] 캠페인 연장
- [ ] 캠페인 상태 동기화

### 3.3 api-server 연동
- [ ] campaign_worker_client.py
- [ ] 캠페인 등록/연장/로테이션 API
- [ ] PipelineState 전이 (campaign_setup → registering → active)

### 3.4 테스트
- [ ] 워커 헬스체크
- [ ] 캠페인 등록 흐름 (목 서비스 또는 실 테스트)
- [ ] 키워드 로테이션 테스트
- [ ] api-server → campaign-worker 연동 테스트

### 3.5 검증
- [ ] Agent B 검증 완료
- [ ] Agent C 재검증 완료
- [ ] main 브랜치 merge

---

## Phase 4: React 프론트엔드

### 4.1 셋업
- [ ] React + TypeScript + Vite 초기화
- [ ] TailwindCSS 설정
- [ ] React Router 구성
- [ ] API 클라이언트 (axios + JWT 인터셉터)

### 4.2 페이지
- [ ] 로그인/로그아웃
- [ ] 대시보드 (역할별)
- [ ] 주문 접수 (단건 폼)
- [ ] 주문 접수 (엑셀 벌크)
- [ ] 주문 목록/상세
- [ ] 플레이스/키워드 관리
- [ ] 캠페인 관리
- [ ] 파이프라인 현황
- [ ] 정산/잔액 관리
- [ ] 시스템 설정 (admin)

### 4.3 테스트
- [ ] 각 페이지 렌더링 확인
- [ ] API 연동 확인
- [ ] 역할별 접근 제어 확인

### 4.4 검증
- [ ] Agent B 검증 완료
- [ ] Agent C 재검증 완료
- [ ] main 브랜치 merge

---

## Phase 5: Docker Compose + AWS 배포

### 5.1 Docker
- [ ] docker-compose.yml (5개 서비스)
- [ ] Nginx 설정 (리버스 프록시)
- [ ] 헬스체크 설정
- [ ] 볼륨 설정 (DB 데이터 영속화)

### 5.2 AWS 배포
- [ ] EC2 인스턴스 생성
- [ ] Docker + Docker Compose 설치
- [ ] 도메인 + SSL 설정
- [ ] 배포 스크립트
- [ ] DB 마이그레이션

### 5.3 운영
- [ ] 로그 모니터링
- [ ] 백업 설정 (PostgreSQL)
- [ ] 환경변수 관리

### 5.4 검증
- [ ] Agent B 검증 완료
- [ ] Agent C 재검증 완료
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
