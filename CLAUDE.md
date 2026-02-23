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

## 현재 진행 상태

| Phase | 내용 | 상태 |
|-------|------|------|
| 0 | 문서/구조/reference 코드 정리 | 완료 |
| 1A | 기반 인프라 + 인증 (companies, users, JWT) | **← 현재** |
| 1B | 주문/상품/정산 (orders, products, balance) | 미시작 |
| 1C | 파이프라인/통합 모델 (places, campaigns, 자동배정) | 미시작 |
| 2 | keyword-worker 연동 | 미시작 |
| 3 | campaign-worker 연동 | 미시작 |
| 4 | React 프론트엔드 | 미시작 |
| 5 | Docker/AWS 배포 | 미시작 |

상세 체크리스트: `docs/PHASE_CHECKLIST.md`

## 아키텍처

```
[React SPA] → [Nginx] → [api-server :8000] ← 메인 FastAPI (인증, 외부 CRUD, 오케스트레이션)
                              │
                    ┌─────────┼─────────┐
                    ▼                   ▼
          [keyword-worker :8001]  [campaign-worker :8002]
          Playwright 키워드 추출   Playwright 캠페인 등록
          curl_cffi 랭킹 체크     APScheduler 키워드 로테이션
                    │                   │
                    └─────────┬─────────┘
                              ▼
                    [PostgreSQL 15 통합 DB]
                       20개 테이블
                    멀티테넌트 (일류기획, 제이투랩)

※ api-server = 외부 CRUD + 오케스트레이션 담당
※ workers = 내부 작업 수행 + DB 직접 저장 후 콜백으로 api-server에 알림
※ 3개 서비스 모두 같은 PostgreSQL에 직접 연결 (Docker 내부 네트워크)
```

## Repo 구조

```
├── CLAUDE.md                            # ← 이 파일 (세션 자동 로드)
├── README.md                            # 프로젝트 개요
├── .env.example                         # 환경변수 템플릿
│
├── docs/
│   ├── INTEGRATION_PLAN.md              # 전체 계획서 (DB 20테이블, API 60+, 아키텍처)
│   ├── DEVELOPMENT_WORKFLOW.md          # 에이전트 오케스트레이션 상세 가이드
│   └── PHASE_CHECKLIST.md              # Phase별 진행 추적 체크리스트
│
├── reference/                           # 기존 시스템 원본 코드 + 데이터
│   ├── keyword-extract/                 # 키워드 추출 소스 (src/, web/)
│   └── quantum-campaign/               # 캠페인 자동화 소스 + 운영 DB
│       └── data/quantum.db             # SQLite 운영 데이터 (마이그레이션용)
│
├── api-server/                          # [Phase 1] FastAPI 메인 서버
├── keyword-worker/                      # [Phase 2] 키워드 추출 워커
├── campaign-worker/                     # [Phase 3] 캠페인 자동화 워커
└── frontend/                            # [Phase 4] React SPA
```

## 핵심 문서 가이드

| 문서 | 언제 읽는지 |
|------|-----------|
| `docs/PHASE_CHECKLIST.md` | **가장 먼저** - 현재 뭘 해야 하는지 확인 |
| `docs/INTEGRATION_PLAN.md` | 구현할 때 - DB 스키마, API 명세, 파이프라인 흐름 |
| `docs/DEVELOPMENT_WORKFLOW.md` | 개발 시작 전 - 에이전트 역할, 프롬프트, 규칙 |

## 기존 코드 참조

모든 원본 코드는 `reference/` 폴더에 있습니다 (외부 경로 의존 없음):

| 기존 시스템 | 참조 경로 | 핵심 파일 |
|------------|----------|----------|
| Keyword Extract | `reference/keyword-extract/` | `src/smart_worker.py`, `src/models.py`, `web/app.py` |
| Quantum Campaign | `reference/quantum-campaign/` | `backend/app/models/`, `backend/app/services/superap.py` |
| Quantum 운영 DB | `reference/quantum-campaign/data/quantum.db` | 마이그레이션 대상 SQLite |

## 중요 경고

1. `.env`, `settings.json` = **실제 크리덴셜** → git 커밋 절대 금지
2. 이 repo = **반드시 Private 유지** (내부 코드 + 운영 데이터 포함)
3. `quantum.db` = 운영 데이터 스냅샷 → 마이그레이션 참조용, 원본은 건드리지 않음
4. **superap.io 실제 캠페인 생성 절대 금지**
   - 테스트 시 슈퍼앱 로그인, 폼 입력, 등록 버튼 클릭 직전까지는 OK
   - **캠페인 최종 제출(submit)은 절대 실행하지 않음** → 실제 광고비 발생
   - campaign-worker 테스트는 반드시 **mock/stub**으로 superap.py의 최종 제출 단계를 대체
   - E2E 테스트에서도 campaign registration은 mock 응답 사용
   - `DRY_RUN=true` 환경변수로 제어: true이면 최종 제출 스킵 + 가짜 campaign_code 반환

## 개발 패턴 요약

```
[사용자] "Phase N 개발 시작해줘"
     ↓
[Agent A] 기능 개발 → git commit + push
     ↓
[사용자] 새 세션에서 "Phase N 검증해줘"
     ↓
[Agent B] 코드 리뷰 + 디버깅 → git commit + push
     ↓
[사용자] 새 세션에서 "Phase N 재검증해줘"
     ↓
[Agent C] 최종 검증 → git commit + push
     ↓
PHASE_CHECKLIST.md 업데이트 → 다음 Phase
```

각 Agent에게 줄 구체적 프롬프트: `docs/DEVELOPMENT_WORKFLOW.md` 참조

## 기술 스택

| 영역 | 기술 |
|------|------|
| API 서버 | FastAPI + SQLAlchemy 2.0 (async) + Alembic |
| DB | PostgreSQL 15 |
| Workers | Playwright + curl_cffi + APScheduler |
| 인증 | JWT (access + refresh) |
| 프론트엔드 | React + TypeScript + Vite + TailwindCSS |
| 배포 | Docker Compose + Nginx + AWS EC2 |
| Python | 3.11+ |
