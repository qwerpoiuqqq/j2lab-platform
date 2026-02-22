# J2LAB 통합 플랫폼

> Claude Code가 세션 시작 시 자동 로드하는 프로젝트 컨텍스트 파일

## 한 줄 요약

네이버 플레이스 광고 자동화: **접수 → 키워드 추출 → 캠페인 등록 → 관리** 통합 플랫폼

## 현재 진행 상태

| Phase | 내용 | 상태 |
|-------|------|------|
| 0 | 문서/구조 정리 | 완료 |
| 1 | DB 스키마 + api-server 골격 | **← 다음** |
| 2 | keyword-worker 연동 | 미시작 |
| 3 | campaign-worker 연동 | 미시작 |
| 4 | React 프론트엔드 | 미시작 |
| 5 | Docker/AWS 배포 | 미시작 |

> 상세 진행률: `docs/PHASE_CHECKLIST.md`

## 아키텍처

```
[React SPA] → [Nginx] → [api-server :8000]
                              ├── [keyword-worker :8001]  ← Playwright 키워드 추출
                              ├── [campaign-worker :8002]  ← Playwright 캠페인 등록
                              └── [PostgreSQL]              ← 16개 테이블 통합 DB
```

## Repo 구조

```
├── CLAUDE.md                  # ← 이 파일
├── README.md                  # 프로젝트 개요
├── docs/
│   ├── INTEGRATION_PLAN.md    # 전체 계획서 (DB스키마, API명세, 아키텍처)
│   ├── DEVELOPMENT_WORKFLOW.md # 에이전트 개발 워크플로우
│   └── PHASE_CHECKLIST.md     # 진행 추적 체크리스트
├── api-server/                # [Phase 1] FastAPI 메인 서버
├── keyword-worker/            # [Phase 2] 키워드 추출 서비스
├── campaign-worker/           # [Phase 3] 캠페인 자동화 서비스
├── frontend/                  # [Phase 4] React SPA
├── reference/oms-django/      # Django OMS 참고 코드
├── docker-compose.yml         # [Phase 5]
└── .env.example
```

## 기존 시스템 참조

원본 코드가 필요할 때 (이 repo 외부):

| 시스템 | 참조 경로 | 핵심 파일 |
|--------|----------|----------|
| Keyword Extract | `../Keyword_extract_program_backup/` | `src/smart_worker.py`, `web/app.py` |
| Quantum Campaign | `../quantum-campaign-automation/` | `backend/app/services/superap.py`, `models/` |

## 중요 경고

- `quantum-campaign-automation/` 의 Docker 데이터 = **운영 데이터** → 절대 수정 금지
- `.env`, `settings.json` = **실제 크리덴셜** → git 커밋 금지
- 이 repo = **반드시 Private 유지**

## 개발 패턴

```
Agent A (개발) → commit → Agent B (검증) → commit → Agent C (재검증) → commit
```

상세: `docs/DEVELOPMENT_WORKFLOW.md`

## 기술 스택

FastAPI + SQLAlchemy 2.0 async + Alembic + PostgreSQL 15 + Playwright + React + TypeScript + Docker Compose + AWS EC2

## 작업 시작 방법

```bash
cat docs/PHASE_CHECKLIST.md          # 현재 진행 상태 확인
cat docs/INTEGRATION_PLAN.md         # 상세 스펙 확인
cat docs/DEVELOPMENT_WORKFLOW.md     # 개발 규칙 확인
```
