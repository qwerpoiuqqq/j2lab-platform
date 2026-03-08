# J2LAB Platform

네이버 플레이스 광고 자동화 통합 플랫폼.
**주문 접수 → 키워드 추출 → 계정 배정 → 캠페인 등록 → 키워드 로테이션 → 자동 완료** 전 과정을 하나의 시스템으로 운영합니다.

> 운영 URL: http://52.78.114.92/

---

## 전체 작업 플로우

### 1단계: 상품/카테고리 세팅 (관리자)

```
[상품 관리] → 카테고리 생성 (트래픽, 저장, 자동완성, 영수증)
           → 상품 생성 (트래픽 30일, 저장 30일, 트래픽 60일, 저장 60일)
           → 각 상품에 주문 폼 스키마 설정 (place_url, campaign_type, daily_limit 등)
           → 가격 매트릭스에서 역할별 차등 가격 설정 (총판 85%, 하위계정 90%)
```

| 메뉴 | 경로 | 역할 | 설명 |
|------|------|------|------|
| 상품 관리 | `/products` | system_admin, company_admin | 상품 CRUD + 폼 스키마 빌더 |
| 카테고리 | `/products/categories` | system_admin, company_admin | 상품 분류 관리 + 순서 변경 |
| 가격 매트릭스 | `/products/prices/matrix` | system_admin, company_admin | 상품 x 역할 가격 스프레드시트 편집 |

### 2단계: 주문 접수 (총판/하위계정)

```
[주문 접수] → 상품 선택 → 폼 작성 (플레이스 URL, 캠페인 유형, 기간, 한도)
           → 주문 제출 (draft → submitted)
           → 관리자 입금확인 (submitted → payment_confirmed)
```

| 메뉴 | 경로 | 역할 | 설명 |
|------|------|------|------|
| 주문 접수 | `/orders/grid` | 총판, 하위계정 | 상품 그리드에서 주문 생성 |
| 주문 내역 | `/orders` | 전체 | 주문 목록 + 상태별 필터 |
| 주문 상세 | `/orders/:id` | 전체 | 주문 정보 + 항목 + 파이프라인 진행 현황 |

### 3단계: 자동 파이프라인 (시스템)

```
입금확인 → [keyword-worker] 플레이스 URL에서 키워드 자동 추출
        → [api-server] 3단계 자동 배정 알고리즘
           1) 연장 체크: 같은 플레이스에 최근 캠페인 있으면 연장
           2) 네트워크 선택: 미사용 네트워크 중 최저 tier 선택
           3) 계정 선택: 배정순서 + 동시캠페인 50개 제한
        → 관리자 배정 확인/오버라이드
        → [campaign-worker] 슈퍼앱 캠페인 자동 등록
```

| 메뉴 | 경로 | 역할 | 설명 |
|------|------|------|------|
| 배정 대기열 | `/assignments` | 관리자, 담당자 | 자동배정 확인/오버라이드/벌크확인 |
| 캠페인 대시보드 | `/campaigns` | 관리자, 담당자 | 캠페인 목록 + 상태 모니터링 |
| 계정 관리 | `/campaigns/accounts` | 관리자, 담당자 | 슈퍼앱 계정 CRUD |
| 템플릿 관리 | `/campaigns/templates` | 관리자, 담당자 | 캠페인 등록 템플릿 |

### 4단계: 운영/관리 (자동 + 관리자)

```
캠페인 활성 → [campaign-worker] 매 10분 키워드 자동 로테이션
           → [campaign-worker] 매일 00:30 만료 캠페인 자동 완료
           → 전 항목 완료 시 주문 자동 완료
```

| 메뉴 | 경로 | 역할 | 설명 |
|------|------|------|------|
| 마감 캘린더 | `/calendar` | 관리자, 담당자, 총판 | 주문 마감일 + 캠페인 종료일 캘린더 |
| 정산 현황 | `/settlements` | system_admin, company_admin | 주문별 정산 관리 |
| 수익 분석 | `/settlements/secret` | system_admin | 원가/마진/순수익 분석 (비밀번호 보호) |

### 5단계: 시스템 관리

| 메뉴 | 경로 | 역할 | 설명 |
|------|------|------|------|
| 대시보드 | `/` | 전체 | 주문/캠페인 통계, 파이프라인 현황 |
| 유저 관리 | `/users` | system_admin, company_admin | 유저 CRUD + 역할 배정 |
| 회사 관리 | `/companies` | system_admin | 멀티테넌트 회사 관리 |
| 공지사항 | `/notices` | 전체 (관리: 관리자만) | 공지 작성/읽기 |
| 시스템 설정 | `/settings` | system_admin | 시스템 전역 설정 |

---

## 파이프라인 14단계 상세

```
임시저장 → 제출 → 입금확인 → 추출대기 → 추출중 → 추출완료
→ 계정배정 → 배정확인 → 등록중 → 캠페인활성 → 운영중 → 완료
                                                    ↘ 실패 / 취소
```

각 주문 항목별로 독립적인 파이프라인이 실행되며, 주문 상세 페이지에서 진행 현황 바로 확인 가능.

---

## 역할 체계 (5단계)

| 역할 | 코드 | 권한 |
|------|------|------|
| 시스템 관리자 | `system_admin` | 전체 시스템 관리, 회사/유저/상품/설정 |
| 회사 관리자 | `company_admin` | 소속 회사 내 주문/유저/정산 관리 |
| 담당자 | `order_handler` | 캠페인 관리, 배정 확인/오버라이드 |
| 총판 | `distributor` | 주문 접수, 하위계정 관리 |
| 하위계정 | `sub_account` | 주문 접수만 |

---

## 아키텍처

```
[React SPA] → [Nginx :80/443] → [api-server :8000]
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
                                22개 테이블
                             멀티테넌트 (일류기획, 제이투랩)
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| API 서버 | FastAPI + SQLAlchemy 2.0 (async) + Alembic |
| DB | PostgreSQL 15 (22 tables, 7 migrations) |
| Workers | Playwright + curl_cffi + APScheduler |
| 인증 | JWT (access 30분 + refresh 7일) |
| 프론트엔드 | React 18 + TypeScript + Vite + TailwindCSS |
| 배포 | Docker Compose + Nginx + AWS EC2 (t3.medium, 서울) |

---

## 디렉토리 구조

```
├── api-server/            # FastAPI 메인 서버 (인증, 주문, 관리, 오케스트레이션)
│   ├── alembic/versions/  # DB 마이그레이션 (001~007)
│   ├── app/models/        # SQLAlchemy ORM (22개 모델)
│   ├── app/routers/       # API 엔드포인트 (60+)
│   └── app/services/      # 비즈니스 로직 (배정, 파이프라인, 정산 등)
│
├── keyword-worker/        # 키워드 추출 서비스 (Playwright)
├── campaign-worker/       # 캠페인 자동 등록 + 키워드 로테이션 (APScheduler)
│
├── frontend/              # React SPA
│   ├── src/api/           # API 클라이언트 (20개)
│   ├── src/pages/         # 페이지 컴포넌트 (20+)
│   ├── src/components/    # 공용/기능별 컴포넌트
│   └── src/types/         # TypeScript 인터페이스
│
├── scripts/               # 운영 스크립트
│   ├── seed-data.sh       # 초기 데이터 (회사, 유저, 카테고리, 상품, 가격)
│   └── reencrypt-superap-passwords.sh
│
├── docs/                  # 설계 문서
├── reference/             # 기존 시스템 원본 코드 (읽기 전용)
└── docker-compose.yml     # 배포 구성
```

---

## 시작하기

### 로컬 개발

```bash
git clone https://github.com/qwerpoiuqqq/j2lab-platform.git
cd j2lab-platform
cp .env.example .env   # 환경변수 편집
docker compose up -d
docker compose exec api-server alembic upgrade head
bash scripts/seed-data.sh
# http://localhost/ 접속
```

### EC2 배포

```bash
ssh ubuntu@52.78.114.92
cd /home/ubuntu/j2lab-platform
git pull origin main
docker compose build api-server frontend campaign-worker
docker compose up -d
docker compose exec api-server alembic upgrade head
bash scripts/seed-data.sh
```

### EC2 CLI 배포 (AWS CLI + SSM)

GitHub Actions 없이도 로컬에서 AWS CLI만으로 EC2 배포 가능.

선행조건:
- EC2에 SSM Agent + IAM Role 연결
- 로컬에 `aws` CLI 로그인 완료
- EC2의 `/home/ubuntu/j2lab-platform/.env` 와 `nginx/ssl` 유지
- EC2 `.env` 에 `DB_PASSWORD`, `SECRET_KEY`, `AES_ENCRYPTION_KEY`, `INTERNAL_API_SECRET`, `DRY_RUN` 설정

```bash
AWS_REGION=ap-northeast-2 \
EC2_INSTANCE_ID=i-0070e75146cac1672 \
./scripts/deploy-ec2-cli.sh

AWS_REGION=ap-northeast-2 \
EC2_INSTANCE_ID=i-0070e75146cac1672 \
./scripts/deploy-ec2-cli.sh status
```

옵션 예시:

```bash
AWS_REGION=ap-northeast-2 \
EC2_INSTANCE_ID=i-0070e75146cac1672 \
COMMIT_SHA=$(git rev-parse HEAD) \
BUILD_SERVICES="api-server frontend keyword-worker campaign-worker" \
RUN_SEED=false \
./scripts/deploy-ec2-cli.sh
```

GitHub에서 자동 배포하려면 `.github/workflows/deploy-ec2.yml`를 사용하고,
다음 Secrets를 저장:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `EC2_INSTANCE_ID`
- `EC2_DEPLOY_PATH`

---

## 기본 로그인 계정

| 역할 | 이메일 | 비밀번호 | 소속 |
|------|--------|----------|------|
| 시스템 관리자 | admin@jtwolab.kr | jjlab1234!j | 제이투랩 |
| 회사 관리자 | ilryu_accountant@jtwolab.kr | ilryu1234! | 일류기획 |
| 담당자 | j2lab_handler@jtwolab.kr | j2lab1234! | 제이투랩 |
| 총판 | j2lab_distributor@jtwolab.kr | j2lab1234! | 제이투랩 |

---

## 보안 주의사항

- 이 repo는 **반드시 Private 유지**
- `.env` 파일은 절대 커밋하지 않음 (.gitignore 등록)
- 운영 배포 시 `SECRET_KEY`, `AES_ENCRYPTION_KEY`, `INTERNAL_API_SECRET`는 반드시 실제 값으로 설정
- `reference/quantum-campaign/data/quantum.db`는 마이그레이션 참조용 스냅샷
- superap.io 실제 캠페인 생성은 `DRY_RUN=true` (기본값)으로 방지
