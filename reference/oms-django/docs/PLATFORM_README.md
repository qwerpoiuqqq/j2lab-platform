# J2LAB Unified Platform

접수 → 키워드 추출 → 캠페인 세팅 → 관리 통합 플랫폼

## 구조

```
unified-platform/
├── api-server/          # 메인 FastAPI 서버 (Phase 1)
├── keyword-worker/      # 키워드 추출 워커 (Phase 2)
├── campaign-worker/     # 캠페인 자동화 워커 (Phase 3)
├── frontend/            # React SPA (Phase 4)
├── docker-compose.yml   # 통합 배포 (Phase 5)
└── docs/                # 계획 및 문서
    └── INTEGRATION_PLAN.md
```

## 기술 스택

- **Backend**: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL
- **Frontend**: React + TypeScript + Vite
- **Infra**: Docker Compose + AWS EC2 + Nginx

## 연관 프로젝트 (참조용, 이 repo에 포함되지 않음)

- `Keyword_extract_program_backup/` - 기존 키워드 추출 서비스
- `quantum-campaign-automation/` - 기존 캠페인 자동화 서비스
- `jtwolablife` (GitHub) - OMS 프론트엔드 참고

## 상세 계획

[docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md) 참조
