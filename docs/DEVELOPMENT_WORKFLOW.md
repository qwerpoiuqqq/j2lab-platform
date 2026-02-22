# 개발 워크플로우

## 에이전트 오케스트레이션 패턴

각 Phase마다 3개의 독립 세션(Agent A → B → C)으로 개발-검증-재검증을 반복합니다.
**git이 세션 간 컨텍스트 브릿지 역할**을 하므로 새 세션에서도 코드를 바로 이어받을 수 있습니다.

```
Phase N 시작
│
├── [Agent A] 기능 개발 (새 세션)
│   ├── PHASE_CHECKLIST.md에서 현재 할 일 확인
│   ├── INTEGRATION_PLAN.md에서 스펙 참조
│   ├── reference/ 폴더에서 기존 코드 참조
│   ├── 코드 작성 + 테스트 작성
│   ├── 모든 테스트 통과 확인
│   └── git commit + push
│
├── [Agent B] 검증 (새 세션)
│   ├── git pull → 변경 사항 확인
│   ├── INTEGRATION_PLAN.md 대비 코드 리뷰
│   ├── 테스트 실행 → 실패 시 버그 수정
│   ├── 엣지케이스 테스트 추가
│   ├── 코드 품질 개선
│   └── git commit + push
│
├── [Agent C] 재검증 (새 세션)
│   ├── git pull → 전체 코드 리뷰
│   ├── 전체 테스트 실행
│   ├── 이전 Phase와의 통합 확인
│   ├── 보안 기본 검토
│   └── git commit + push
│
├── PHASE_CHECKLIST.md 체크 업데이트
├── Phase 브랜치 → main merge
└── 다음 Phase로
```

---

## Agent별 구체적 프롬프트 가이드

### 사전 준비 (모든 Agent 공통)

새 세션을 열고 프로젝트 폴더에서 Claude Code를 실행합니다.
CLAUDE.md가 자동 로드되어 프로젝트 맥락이 주입됩니다.

```bash
# 맥에서
cd ~/your-workspace
git clone https://github.com/qwerpoiuqqq/j2lab-platform.git  # 처음일 때
cd j2lab-platform
git pull origin main  # 이미 clone한 경우
```

---

### Agent A: 기능 개발

> 새 Claude Code 세션을 열고 아래 프롬프트를 입력합니다.

#### Phase 1A 프롬프트 (기반 인프라 + 인증)

```
Phase 1A 개발을 시작해줘. (Agent A - 기능 개발)

할 일:
1. docs/PHASE_CHECKLIST.md에서 Phase 1A 체크리스트 확인
2. docs/INTEGRATION_PLAN.md에서 DB 스키마, API 명세 참조
3. 아래 순서대로 구현:

[1A.1] 프로젝트 셋업
- api-server/ 폴더에 FastAPI 프로젝트 초기화
- SQLAlchemy 2.0 async 설정
- Alembic 초기화
- PostgreSQL 개발용 docker-compose.dev.yml
- Pydantic Settings (.env 로딩)
- 프로젝트 구조: models/, routers/, schemas/, services/, utils/

[1A.2] 핵심 모델 (3개 테이블)
- companies (회사/테넌트: 일류기획, 제이투랩)
- users (5단계 역할: system_admin, company_admin, order_handler, distributor, sub_account)
- refresh_tokens (JWT 관리)
- Alembic 마이그레이션 생성

[1A.3] JWT 인증
- login, refresh, logout (블랙리스트)
- bcrypt 비밀번호 해싱
- 역할 기반 접근 제어 (RoleChecker dependency)
  역할 계층: system_admin > company_admin > order_handler > distributor > sub_account
- 공통 페이지네이션 스키마 (PaginationParams)

[1A.4] CRUD API
- Companies CRUD (system_admin 전용)
- Users CRUD + 역할별 권한 + 하위 유저 트리

[1A.5] 테스트
- pytest 설정 + 인증/유저 테스트
- Swagger 문서 확인 (/docs)

완료되면 git commit + push 해줘.
브랜치: phase-1a/auth
커밋 형식: [Phase 1A] type: 설명
```

#### Phase 1B 프롬프트 (주문/상품/정산)

```
Phase 1B 개발을 시작해줘. (Agent A - 기능 개발)

할 일:
1. docs/PHASE_CHECKLIST.md에서 Phase 1B 체크리스트 확인
2. docs/INTEGRATION_PLAN.md에서 DB 스키마, API 명세 참조
3. Phase 1A에서 만든 api-server/ 기반 위에 구현

[1B.1] 모델 (6개 테이블)
- products (상품 + daily_deadline 마감시간)
- price_policies (가격 정책: 유저별→역할별→기본)
- orders (주문: draft→submitted→payment_confirmed)
- order_items (주문 항목 + assigned_account_id 계정배정)
- balance_transactions (잔액 거래)
- system_settings (시스템 설정)
- Alembic 마이그레이션 생성

[1B.2] CRUD + 비즈니스 로직
- Products CRUD + 마감시간 체크
- Price Policies CRUD + 가격 결정 로직 (유저별→역할별→기본)
- Orders CRUD + 상태 전이 (submit, confirm-payment, reject)
- 엑셀 업로드 (미리보기→확인) + 템플릿 다운로드
- BalanceTransactions + 잔액 차감 (입금확인 시점, SELECT FOR UPDATE)

[1B.3] 테스트
- 각 엔드포인트 테스트

기존 코드 참조:
- jtwolablife OMS의 주문/정산 로직 참고 (INTEGRATION_PLAN.md 섹션 7.3)
  ⚠ 역할명 주의: OMS의 agency→distributor, seller→sub_account로 매핑

완료되면 git commit + push 해줘.
브랜치: phase-1b/orders
커밋 형식: [Phase 1B] type: 설명
```

#### Phase 1C 프롬프트 (파이프라인/통합 모델)

```
Phase 1C 개발을 시작해줘. (Agent A - 기능 개발)

할 일:
1. docs/PHASE_CHECKLIST.md에서 Phase 1C 체크리스트 확인
2. docs/INTEGRATION_PLAN.md에서 DB 스키마, API 명세, 파이프라인 흐름 참조
3. Phase 1A+1B 기반 위에 나머지 모델 + 서비스 구현

[1C.1] 모델 (11개 테이블, 이것으로 전체 20개 완성)
- places (네이버 플레이스 정보, PK=네이버 Place ID, UPSERT 필요)
- keywords + keyword_rank_history
- extraction_jobs (키워드 추출 작업)
- network_presets (네트워크 프리셋: 계정군 + 매체 타겟팅)
- superap_accounts (슈퍼앱 계정 + network_preset_id + unit_cost)
- campaigns (campaign_type 영문 + module_context + network_preset_id)
- campaign_keyword_pool (UNIQUE 제약으로 중복 제외)
- campaign_templates (code 컬럼: traffic/save/landmark)
- pipeline_states (UNIQUE order_item_id) + pipeline_logs
- Alembic 마이그레이션 (전체 20개 테이블 완성 확인)

[1C.2] CRUD + 서비스
- Places CRUD (UPSERT: 같은 place_id 재수집 시 UPDATE)
- Keywords + RankHistory CRUD
- ExtractionJobs CRUD
- NetworkPresets CRUD (company_admin 전용, 매체 타겟팅 JSONB)
- SuperapAccounts CRUD (AES 암호화, 프리셋 연결)
- Campaigns CRUD
- CampaignKeywordPool CRUD (UNIQUE 제약 중복 제외)
- CampaignTemplates CRUD
- PipelineStates + Logs CRUD
- 자동 배정 서비스 (연장 판정 7일/10,000타 + 네트워크 순서)
- 계정 배정 API (company_admin 전용, 응답 필드 필터링)
- 워커 콜백 API (/internal/callback/*)

[1C.3] 테스트
- 각 엔드포인트 + 자동 배정 로직 테스트

기존 코드 참조:
- reference/keyword-extract/src/models.py → places 테이블 필드
- reference/quantum-campaign/backend/app/models/ → campaigns, templates 등

완료되면 git commit + push 해줘.
브랜치: phase-1c/pipeline
커밋 형식: [Phase 1C] type: 설명
```

#### Phase 2 프롬프트

```
Phase 2 개발을 시작해줘. (Agent A - 기능 개발)

할 일:
1. docs/PHASE_CHECKLIST.md에서 Phase 2 체크리스트 확인
2. reference/keyword-extract/ 코드를 분석하고 keyword-worker/ 구현

[2.1] 워커 셋업
- keyword-worker/ 폴더에 FastAPI 프로젝트 생성
- reference/keyword-extract/src/의 핵심 로직 가져오기
  (smart_worker.py, rank_checker_graphql.py, place_scraper.py 등)
- Dockerfile (Playwright + Chromium)
- /internal/ API 엔드포인트 구현

[2.2] 기능 연동
- web/app.py의 엔드포인트 → /internal/ 내부 API로 변환
- SessionManager → DB 기반으로 전환
- 결과를 PostgreSQL places, keywords 테이블에 저장

[2.3] api-server 연동
- api-server/에 keyword_worker_client.py 추가 (httpx 비동기 호출)
- 추출 시작/상태/결과 API 구현
- PipelineState 자동 전이

완료되면 phase-2/keyword 브랜치에 commit + push.
```

#### Phase 3 프롬프트

```
Phase 3 개발을 시작해줘. (Agent A - 기능 개발)

할 일:
1. docs/PHASE_CHECKLIST.md에서 Phase 3 체크리스트 확인
2. reference/quantum-campaign/ 코드를 분석하고 campaign-worker/ 구현

[3.1] 워커 셋업
- campaign-worker/ 폴더에 FastAPI 프로젝트 생성
- reference/quantum-campaign/backend/app/의 핵심 로직 가져오기
  (services/superap.py, services/keyword_rotation.py, services/scheduler.py)
- SQLite → PostgreSQL 전환
- Dockerfile (Playwright + Chromium)

[3.2] 기능 연동
- 캠페인 등록 자동화 (superap.py 유지)
- 키워드 로테이션 (APScheduler 유지)
- 캠페인 연장, 상태 동기화

[3.3] api-server 연동
- campaign_worker_client.py 추가
- 캠페인 등록/연장/로테이션 API
- PipelineState 전이

[3.4] 데이터 마이그레이션
- reference/quantum-campaign/data/quantum.db에서 PostgreSQL로 마이그레이션 스크립트 작성

완료되면 phase-3/campaign 브랜치에 commit + push.
```

#### Phase 4 프롬프트

```
Phase 4 개발을 시작해줘. (Agent A - 기능 개발)

할 일:
1. docs/PHASE_CHECKLIST.md에서 Phase 4 체크리스트 확인
2. frontend/ 폴더에 React SPA 구현

[4.1] 셋업
- React + TypeScript + Vite 초기화
- TailwindCSS 설정
- React Router 구성
- API 클라이언트 (axios + JWT 인터셉터)

[4.2] 페이지 구현
- 로그인/로그아웃
- 대시보드 (역할별 다른 뷰)
- 주문 접수 (단건 + 엑셀 벌크)
- 주문 목록/상세
- 플레이스/키워드 관리
- 캠페인 관리
- 파이프라인 현황 (실시간)
- 정산/잔액 관리

완료되면 phase-4/frontend 브랜치에 commit + push.
```

#### Phase 5 프롬프트

```
Phase 5 배포 설정을 시작해줘. (Agent A - 기능 개발)

할 일:
1. docker-compose.yml (5개 서비스: nginx, api-server, keyword-worker, campaign-worker, postgres)
2. Nginx 설정 (리버스 프록시, / → frontend, /api → api-server)
3. 각 서비스 Dockerfile
4. 헬스체크 설정
5. 볼륨 설정 (DB 데이터 영속화)
6. AWS EC2 배포 스크립트

완료되면 phase-5/deploy 브랜치에 commit + push.
```

---

### Agent B: 검증

> Agent A의 작업이 push된 후, **새 Claude Code 세션**을 열고 아래 프롬프트를 입력합니다.

```
Phase N 검증을 시작해줘. (Agent B - 코드 리뷰 + 디버깅)

너는 Agent A가 개발한 코드를 검증하는 역할이야.
Agent A와는 다른 세션이므로 선입견 없이 코드를 봐줘.

할 일:
1. git pull로 최신 코드 받기
2. docs/INTEGRATION_PLAN.md와 비교하며 코드 리뷰
   - 스펙대로 구현되었는지?
   - 빠진 필드, 빠진 API, 잘못된 로직은 없는지?
3. 테스트 실행
   - 기존 테스트 전부 실행
   - 실패하는 테스트가 있으면 원인 파악 후 수정
4. 엣지케이스 테스트 추가
   - 잘못된 입력, 권한 없는 접근, 중복 데이터 등
5. 코드 품질 확인
   - 불필요한 코드, 하드코딩, 보안 이슈
   - import 정리, 타입 힌트 누락

수정 사항이 있으면 commit + push 해줘.
커밋 형식: [Phase N] fix/test/refactor: 설명
```

---

### Agent C: 재검증 (최종)

> Agent B의 작업이 push된 후, **새 Claude Code 세션**을 열고 아래 프롬프트를 입력합니다.

```
Phase N 최종 재검증을 시작해줘. (Agent C - Fresh Eyes 최종 검증)

너는 Agent A, B 모두와 다른 세션이야.
완전히 새로운 눈으로 전체 코드를 리뷰해줘.

할 일:
1. git pull로 최신 코드 받기
2. 전체 테스트 실행 → 100% 통과 확인
3. INTEGRATION_PLAN.md 대비 최종 체크
   - 모든 테이블이 올바른지
   - 모든 API가 스펙대로 동작하는지
   - 인증/권한이 제대로 적용되었는지
4. 이전 Phase와의 통합 확인
   - Phase 1 API가 Phase 2 워커와 잘 연동되는지 (해당 시)
   - DB 모델 간 관계가 올바른지
5. 보안 기본 검토
   - SQL injection 가능성
   - JWT 토큰 처리
   - 비밀번호 해싱
   - CORS 설정
   - 민감 정보 노출
6. PHASE_CHECKLIST.md 업데이트
   - 완료된 항목 체크
   - Agent C 검증 완료 표시

모든 것이 OK이면:
- PHASE_CHECKLIST.md 업데이트 commit + push
- "Phase N 검증 완료. main merge 가능합니다." 라고 알려줘

문제가 있으면:
- 수정 후 commit + push
- 문제점과 수정 내용을 상세히 알려줘
```

---

### Phase 브랜치 → main Merge

Agent C 검증 완료 후 사용자가 직접 merge합니다:

```bash
git checkout main
git merge phase-N/branch-name
git push origin main
```

---

## 커밋 컨벤션

```
[Phase N] type: 설명

type:
  feat     - 새 기능
  fix      - 버그 수정
  refactor - 리팩토링
  test     - 테스트 추가/수정
  docs     - 문서 업데이트
  chore    - 설정, 빌드 등

예시:
  [Phase 1A] feat: companies, users, refresh_tokens 모델 + Alembic 마이그레이션
  [Phase 1B] feat: orders, products, balance 모델 + CRUD API
  [Phase 1C] feat: 파이프라인 + 자동 배정 서비스
  [Phase 1A] fix: users 테이블 role enum 타입 수정
  [Phase 1B] fix: orders 상태 전이 로직 수정
  [Phase 2] test: keyword-worker 추출 작업 엣지케이스 테스트 추가
```

## 브랜치 전략

```
main                     ← 검증 완료된 안정 코드
├── phase-1a/auth        ← Phase 1A 작업 (기반 인프라 + 인증)
├── phase-1b/orders      ← Phase 1B 작업 (주문/상품/정산)
├── phase-1c/pipeline    ← Phase 1C 작업 (파이프라인/통합 모델)
├── phase-2/keyword      ← Phase 2 작업
├── phase-3/campaign     ← Phase 3 작업
├── phase-4/frontend     ← Phase 4 작업
└── phase-5/deploy       ← Phase 5 작업
```

Phase 브랜치 → Agent A/B/C 검증 완료 → main merge
(Phase 1은 1A → 1B → 1C 순서로 각각 독립 검증 후 merge)

---

## 최종 통합 검증 (5라운드)

모든 Phase 완료 후 5라운드 통합 검증을 수행합니다.
**각 라운드 = 새 세션 (fresh eyes)**

| Round | 목적 | 검증 항목 |
|-------|------|----------|
| 1 | E2E 파이프라인 | 접수 → 추출 → 등록 → 관리 전체 흐름 |
| 2 | 보안 취약점 | bandit, SQL injection, JWT, CORS |
| 3 | 성능/안정성 | 동시 요청, DB 쿼리, 메모리 |
| 4 | 엣지케이스 | 잘못된 입력, 네트워크 실패, 워커 다운 |
| 5 | 최종 리뷰 | 코드 품질, API 문서, README 업데이트 |

### 최종 검증 프롬프트 (예시: Round 1)

```
통합 검증 Round 1을 시작해줘. (E2E 파이프라인 테스트)

전체 서비스를 Docker Compose로 띄운 후:
1. 유저 생성 → 로그인 → JWT 토큰 획득
2. 상품 + 가격정책 생성
3. 주문 접수 (플레이스 URL 포함)
4. 키워드 추출 시작 → 완료 대기 → 결과 확인
5. 캠페인 생성 → 등록 → 활성화 확인
6. 파이프라인 상태가 intake → ... → active로 전이되는지 확인
7. 키워드 로테이션이 정상 동작하는지 확인

각 단계에서 실패하면 원인 파악 + 수정 후 다음 단계로.
모든 단계 통과 시 PHASE_CHECKLIST.md에 Round 1 완료 체크.
```

---

## 테스트 실행

```bash
# 개발용 DB 실행
docker compose -f docker-compose.dev.yml up -d

# 단위 테스트
docker compose exec api-server pytest tests/ -v

# 커버리지
docker compose exec api-server pytest tests/ --cov=app --cov-report=term-missing

# 보안 스캔
docker compose exec api-server bandit -r app/ -ll
```
