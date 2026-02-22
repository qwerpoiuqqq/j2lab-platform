# J2LAB Platform

네이버 플레이스 광고 자동화 통합 플랫폼.
**접수 → 키워드 추출 → 캠페인 세팅 → 관리** 파이프라인을 하나의 시스템으로 통합합니다.

## 아키텍처

```
[React SPA] → [Nginx] → [api-server :8000] ← 메인 FastAPI (인증, CRUD, 오케스트레이션)
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
```

- **api-server**가 외부 CRUD 담당 (사용자 요청은 모두 api-server를 거침)
- **worker**들은 내부 HTTP (`/internal/`) 호출로 작업 수신, DB에 직접 결과 저장 후 콜백으로 api-server에 알림
- **React SPA**는 api-server만 호출
- Docker Compose로 AWS EC2 배포

## 디렉토리 구조

| 디렉토리 | 설명 | Phase |
|----------|------|-------|
| `api-server/` | FastAPI 메인 서버 (인증, 주문, 관리, 오케스트레이션) | 1 |
| `keyword-worker/` | 네이버 플레이스 키워드 추출 서비스 | 2 |
| `campaign-worker/` | 슈퍼앱 캠페인 자동 등록 + 키워드 로테이션 | 3 |
| `frontend/` | React + TypeScript SPA | 4 |
| `docs/` | 계획서, 워크플로우, 체크리스트 | - |
| `reference/` | 기존 시스템 소스 코드 + 운영 데이터 (아래 참조) | - |

### `reference/` 폴더 상세

통합 대상인 기존 2개 시스템의 원본 코드를 그대로 복사해둔 폴더입니다.
새 환경에서 clone해도 기존 코드를 바로 참조할 수 있습니다.

| 경로 | 원본 | 핵심 파일 |
|------|------|----------|
| `reference/keyword-extract/` | Keyword Extract 프로그램 (30개 파일) | `src/smart_worker.py`, `src/models.py`, `web/app.py` |
| `reference/quantum-campaign/` | Quantum Campaign 자동화 (147개 파일) | `backend/app/services/superap.py`, `backend/app/models/` |
| `reference/quantum-campaign/data/quantum.db` | 운영 SQLite DB 스냅샷 (25MB) | PostgreSQL 마이그레이션용 참조 데이터 |

> `.env`, `settings.json` 등 크리덴셜 파일은 제외되어 있습니다.

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

## 개발 시작하기

### 1. 새 환경에서 처음 시작할 때

```bash
# 1. clone
git clone https://github.com/qwerpoiuqqq/j2lab-platform.git
cd j2lab-platform

# 2. 환경변수 설정
cp .env.example .env
# .env 파일을 열어서 실제 값으로 수정

# 3. Claude Code 실행
# CLAUDE.md가 자동 로드되어 프로젝트 맥락을 파악합니다
```

### 2. Phase 1 개발 시작 (현재 단계)

```bash
# Phase 브랜치 생성
git checkout -b phase-1/db-api

# Claude Code에게 지시
# → "Phase 1 개발 시작해줘" (Agent A 역할)
# → docs/DEVELOPMENT_WORKFLOW.md 에 구체적인 프롬프트 가이드 있음
```

### 3. Docker 실행 (Phase 1 완료 후)

```bash
# 개발용 (PostgreSQL만)
docker compose -f docker-compose.dev.yml up -d

# 전체 서비스 (Phase 5 이후)
docker compose up -d

# DB 마이그레이션
docker compose exec api-server alembic upgrade head

# API 문서
open http://localhost:8000/docs
```

## 개발 패턴 (Agent A → B → C)

각 Phase마다 3단계 검증을 거칩니다:

1. **Agent A** (새 세션): 기능 개발 + 테스트 작성 → commit + push
2. **Agent B** (새 세션): 코드 리뷰 + 버그 수정 + 엣지케이스 → commit + push
3. **Agent C** (새 세션): 최종 검증 + 통합 확인 + 보안 리뷰 → commit + push

각 Agent에게 줄 구체적인 프롬프트는 [개발 워크플로우](docs/DEVELOPMENT_WORKFLOW.md)를 참조하세요.

## 문서

| 문서 | 설명 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | 세션 자동 로드 - 전체 맥락 요약 |
| [통합 계획서](docs/INTEGRATION_PLAN.md) | DB 스키마 20개 테이블, API 60+ 명세, 아키텍처 상세 |
| [개발 워크플로우](docs/DEVELOPMENT_WORKFLOW.md) | Agent A/B/C 구체적 프롬프트, 오케스트레이션 가이드 |
| [Phase 체크리스트](docs/PHASE_CHECKLIST.md) | Phase 0~5 진행 상태 추적 |

## 보안 주의사항

- 이 repo는 **반드시 Private 유지** (내부 코드 + 운영 데이터 포함)
- `.env` 파일은 절대 커밋하지 않음 (.gitignore 등록됨)
- `quantum.db`는 마이그레이션 참조용 스냅샷 (원본 운영 DB는 건드리지 않음)
