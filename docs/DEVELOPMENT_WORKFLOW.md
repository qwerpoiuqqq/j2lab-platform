# 개발 워크플로우

## 에이전트 오케스트레이션 패턴

```
Phase N 시작
│
├── [Agent A] 기능 개발
│   ├── PHASE_CHECKLIST.md 확인
│   ├── INTEGRATION_PLAN.md 스펙 참조
│   ├── 코드 작성 + 테스트 작성
│   └── git commit + push
│
├── [Agent B] 검증 (새 세션)
│   ├── git pull
│   ├── 코드 리뷰 (INTEGRATION_PLAN 대비)
│   ├── 테스트 실행 → 버그 수정
│   ├── 엣지케이스 테스트 추가
│   └── git commit + push
│
├── [Agent C] 재검증 (새 세션)
│   ├── git pull
│   ├── 전체 테스트 실행
│   ├── 이전 Phase 통합 확인
│   ├── 보안 기본 검토
│   └── git commit + push
│
├── PHASE_CHECKLIST.md 업데이트
└── 다음 Phase로
```

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
```

## 브랜치 전략

```
main                    ← 검증 완료된 안정 코드
├── phase-1/db-api      ← Phase 1 작업
├── phase-2/keyword     ← Phase 2 작업
├── phase-3/campaign    ← Phase 3 작업
├── phase-4/frontend    ← Phase 4 작업
└── phase-5/deploy      ← Phase 5 작업
```

Phase 브랜치 → A/B/C 검증 완료 → main merge

## 최종 통합 검증 (5라운드)

모든 Phase 완료 후:

| Round | 목적 | 검증 항목 |
|-------|------|----------|
| 1 | E2E 파이프라인 | 접수 → 추출 → 등록 → 관리 전체 흐름 |
| 2 | 보안 취약점 | bandit, SQL injection, JWT, CORS |
| 3 | 성능/안정성 | 동시 요청, DB 쿼리, 메모리 |
| 4 | 엣지케이스 | 잘못된 입력, 네트워크 실패, 워커 다운 |
| 5 | 최종 리뷰 | 코드 품질, API 문서, README 업데이트 |

각 라운드 = 새 세션 (fresh eyes)

## 테스트 실행

```bash
# 단위 테스트
docker compose exec api-server pytest tests/ -v

# 커버리지
docker compose exec api-server pytest tests/ --cov=app --cov-report=term-missing

# 보안 스캔
docker compose exec api-server bandit -r app/ -ll
```
