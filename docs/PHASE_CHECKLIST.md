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

## Phase 1A: 기반 인프라 + 인증

### 1A.1 프로젝트 셋업
- [ ] FastAPI 프로젝트 초기화 (`api-server/`)
- [ ] SQLAlchemy 2.0 async 설정
- [ ] Alembic 초기화
- [ ] PostgreSQL Docker 컨테이너 (docker-compose.dev.yml)
- [ ] Pydantic Settings (.env 로딩)

### 1A.2 핵심 모델
- [ ] companies (회사/테넌트: 일류기획, 제이투랩)
- [ ] users (5단계 역할: system_admin~sub_account, company_id)
- [ ] refresh_tokens (JWT 관리)

### 1A.3 인증
- [ ] JWT 발급 (login) + 리프레시 + 로그아웃 (블랙리스트)
- [ ] bcrypt 비밀번호 해싱
- [ ] 역할 기반 접근 제어 (RoleChecker dependency)
- [ ] 공통 페이지네이션 스키마

### 1A.4 CRUD + 테스트
- [ ] Companies CRUD (system_admin 전용)
- [ ] Users CRUD + 역할별 권한 + 하위 유저 트리
- [ ] pytest 설정 + 인증/유저 테스트
- [ ] Swagger 문서 확인

### 1A.5 검증
- [ ] Agent B 검증 완료
- [ ] Agent C 재검증 완료
- [ ] main 브랜치 merge

---

## Phase 1B: 주문/상품/정산

### 1B.1 모델
- [ ] products (상품 + daily_deadline 마감시간)
- [ ] price_policies (가격 정책)
- [ ] orders (주문: draft→submitted→payment_confirmed)
- [ ] order_items (주문 항목 + assigned_account_id 계정배정)
- [ ] balance_transactions (잔액 거래)
- [ ] system_settings (시스템 설정)

### 1B.2 CRUD + 비즈니스 로직
- [ ] Products CRUD + 마감시간 체크
- [ ] Price Policies CRUD + 가격 결정 로직 (유저별→역할별→기본)
- [ ] Orders CRUD + 상태 전이 (submit, confirm-payment, reject)
- [ ] 엑셀 업로드 (미리보기→확인) + 템플릿 다운로드
- [ ] BalanceTransactions + 잔액 차감 (입금확인 시점, SELECT FOR UPDATE)
- [ ] 테스트

### 1B.3 검증
- [ ] Agent B 검증 완료
- [ ] Agent C 재검증 완료
- [ ] main 브랜치 merge

---

## Phase 1C: 파이프라인/통합 모델

### 1C.1 모델
- [ ] places (플레이스 + virtual_phone)
- [ ] keywords + keyword_rank_history
- [ ] extraction_jobs (추출 작업)
- [ ] superap_accounts (슈퍼앱 계정 + company_id + 자동배정 필드)
- [ ] campaigns (campaign_type 영문 + module_context)
- [ ] campaign_keyword_pool (중복 제외 로직)
- [ ] campaign_templates
- [ ] pipeline_states (cancelled 포함) + pipeline_logs

### 1C.2 CRUD + 서비스
- [ ] Places/Keywords/RankHistory CRUD
- [ ] ExtractionJobs CRUD
- [ ] SuperapAccounts CRUD (company_admin 전용, AES 암호화)
- [ ] Campaigns CRUD
- [ ] CampaignKeywordPool CRUD (UNIQUE 제약 중복 제외)
- [ ] CampaignTemplates CRUD
- [ ] PipelineStates + Logs CRUD
- [ ] 계정 자동 배정 서비스 (AssignmentService)
- [ ] 계정 배정 API (company_admin 전용, 응답 필드 필터링)
- [ ] 워커 콜백 API (/internal/callback/*)
- [ ] Alembic 마이그레이션 (전체 19개 테이블)
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
