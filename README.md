# J2LAB Platform

접수 → 키워드 추출 → 캠페인 세팅 → 관리 통합 자동화 플랫폼

## 아키텍처

```
┌─────────────────────────────────────────────┐
│  AWS EC2 (Docker Compose)                   │
│                                              │
│  Nginx (HTTPS)                               │
│    ├── React SPA (접수/관리 UI)              │
│    └── api-server :8000 (메인 FastAPI)       │
│          ├── keyword-worker :8001            │
│          ├── campaign-worker :8002           │
│          └── PostgreSQL 15                   │
└─────────────────────────────────────────────┘
```

## 구조

| 디렉토리 | 설명 | Phase |
|----------|------|-------|
| `api-server/` | FastAPI 메인 서버 (인증, 주문, 관리, 오케스트레이션) | 1 |
| `keyword-worker/` | 네이버 플레이스 키워드 추출 서비스 | 2 |
| `campaign-worker/` | 슈퍼앱 캠페인 자동 등록 + 키워드 로테이션 | 3 |
| `frontend/` | React + TypeScript SPA | 4 |
| `docs/` | 계획서, 워크플로우, 체크리스트 | - |
| `reference/` | 기존 시스템 참고 코드 | - |

## 기술 스택

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 15
- **Workers**: Playwright, curl_cffi, APScheduler
- **Frontend**: React, TypeScript, Vite, TailwindCSS
- **Auth**: JWT
- **Infra**: Docker Compose, Nginx, AWS EC2

## 시작하기

```bash
# 환경 설정
cp .env.example .env
# .env 편집

# 실행
docker compose up -d

# DB 마이그레이션
docker compose exec api-server alembic upgrade head

# API 문서
open http://localhost:8000/docs
```

## 문서

- [통합 계획서](docs/INTEGRATION_PLAN.md) - DB 스키마, API 명세, 아키텍처 상세
- [개발 워크플로우](docs/DEVELOPMENT_WORKFLOW.md) - 에이전트 기반 개발/검증 패턴
- [Phase 체크리스트](docs/PHASE_CHECKLIST.md) - 진행 상태 추적
