# J2LAB 통합 플랫폼 - 현재 상태

> 최종 업데이트: 2026-02-28

## 운영 환경

| 항목 | 값 |
|------|---|
| EC2 인스턴스 | i-0070e75146cac1672 (t3.medium, ap-northeast-2) |
| IP | 52.78.114.92 |
| URL | http://52.78.114.92/ |
| API Docs | http://52.78.114.92/docs |
| 키페어 | j2lab-platform-key |
| 로그인 | admin@jtwolab.kr / jjlab1234!j (system_admin) |

## 컨테이너 상태 (5개, 모두 healthy)

| 컨테이너 | 이미지 | 포트 | 상태 |
|----------|--------|------|------|
| j2lab-api-server | j2lab-platform-api-server | 8000 | healthy |
| j2lab-keyword-worker | j2lab-platform-keyword-worker | 8001 (내부) | healthy |
| j2lab-campaign-worker | j2lab-platform-campaign-worker | 8002 (내부) | healthy |
| j2lab-nginx | nginx:1.27-alpine | 80, 443 | running |
| j2lab-postgres | postgres:15-alpine | 5432 (내부) | healthy |

## API 테스트 결과 (108/108 PASS)

21개 섹션, 매 섹션 세션 초기화:

| # | 섹션 | 테스트 수 | 결과 |
|---|------|:---------:|:----:|
| 1 | Auth (로그인/토큰갱신/인증체크) | 7 | PASS |
| 2 | Companies CRUD | 5 | PASS |
| 3 | Users (역할별 필터 + ID/하위계정) | 8 | PASS |
| 4 | Categories CRUD + 삭제확인 | 6 | PASS |
| 5 | Products CRUD + 스키마 + 가격정책 | 12 | PASS |
| 6 | Orders E2E (생성→제출→반려→승인→결제→취소 + Excel) | 20 | PASS |
| 7 | Settlements (리스트/필터/Secret/비번/Excel) | 11 | PASS |
| 8 | Balance (잔액/충전/출금/유효성) | 5 | PASS |
| 9 | Dashboard (summary/enhanced/campaign-stats) | 3 | PASS |
| 10 | Campaigns (리스트/필터/페이징/등록/템플릿/키워드) | 7 | PASS |
| 11 | Notifications & Notices CRUD | 6 | PASS |
| 12 | Places & Extraction | 2 | PASS |
| 13 | Pipeline | 1 | PASS |
| 14 | Assignment | 1 | PASS |
| 15 | Settings | 1 | PASS |
| 16 | Superap Accounts | 2 | PASS |
| 17 | Templates (라우트 순서 수정 완료) | 3 | PASS |
| 18 | Network Presets CRUD | 4 | PASS |
| 19 | Scheduler | 1 | PASS |
| 20 | Worker Health | 1 | PASS |
| 21 | Internal Callbacks (보안 검증) | 2 | PASS |

## 프론트엔드 페이지 검증 (23/23 OK)

| # | 라우트 | 페이지 | Nginx | API |
|---|--------|--------|:-----:|:---:|
| 1 | `/` | DashboardPage | 200 | OK |
| 2 | `/login` | LoginPage | 200 | OK |
| 3 | `/orders` | OrdersPage | 200 | OK |
| 4 | `/orders/grid` | OrderGridPage | 200 | OK |
| 5 | `/orders/:id` | OrderDetailPage | 200 | OK |
| 6 | `/campaigns` | CampaignsPage | 200 | OK |
| 7 | `/campaigns/add` | CampaignAddPage | 200 | OK |
| 8 | `/campaigns/upload` | CampaignUploadPage | 200 | OK |
| 9 | `/campaigns/accounts` | SuperapAccountsPage | 200 | OK |
| 10 | `/campaigns/templates` | CampaignTemplatesPage | 200 | OK |
| 11 | `/campaigns/:id` | CampaignDetailPage | 200 | OK |
| 12 | `/users` | UsersPage | 200 | OK |
| 13 | `/companies` | CompaniesPage | 200 | OK |
| 14 | `/products` | ProductsPage | 200 | OK |
| 15 | `/products/prices/matrix` | PriceMatrixPage | 200 | OK |
| 16 | `/products/categories` | CategoriesPage | 200 | OK |
| 17 | `/settings` | SettingsPage | 200 | OK |
| 18 | `/settlements` | SettlementPage | 200 | OK |
| 19 | `/settlements/secret` | SettlementSecretPage | 200 | OK |
| 20 | `/calendar` | CalendarPage | 200 | OK |
| 21 | `/assignments` | AssignmentQueuePage | 200 | OK |
| 22 | `/notices` | NoticesPage | 200 | OK |
| 23 | `/*` | NotFoundPage | 200 | - |

### Static Assets

| 파일 | 크기 | Cache |
|------|------|-------|
| index.js | 478 KB | 1년 immutable |
| vendor.js | 95 KB | 1년 immutable |
| query.js | 35 KB | 1년 immutable |
| charts.js | 338 KB | 1년 immutable |
| index.css | 39 KB | 1년 immutable |

## DB 현재 상태 (2026-02-28 초기화 후)

| 테이블 | 건수 | 비고 |
|--------|:----:|------|
| users | 1 | admin@jtwolab.kr (system_admin) |
| companies | 1 | 제이투랩 |
| categories | 4 | 유지 |
| campaign_templates | 3 | 유지 |
| 그 외 모든 테이블 | 0 | 2026-02-28 초기화 |

## Nginx 보안/성능

- SPA fallback: `try_files $uri $uri/ /index.html`
- Rate limiting: API 30r/s, Auth 5r/s
- Security headers: X-Frame-Options, X-Content-Type-Options, XSS-Protection
- `/internal/` 외부 차단 (403)
- Gzip 압축: JS/CSS/JSON
- Static assets: 1년 immutable cache
- index.html: no-cache

## 수정 이력

### 2026-02-28
- DB 데이터 초기화 (admin + 제이투랩 + 카테고리/템플릿만 유지)
- API 테스트 108/108 PASS 달성
- 프론트엔드 23페이지 전체 검증 완료
- `/templates/modules` 라우트 순서 버그 수정

### 2026-02-27
- 4대 기능 구현: 주문 E2E 수정, Worker 클라이언트 확장, 정산 프론트 정합
- OrderGridPage: is_quantity 기반 수량 매핑
- validate_item_data: 구 포맷 스키마 호환
- worker_clients.py: 3개 엔드포인트 추가 (총 13개)
- Settlement: 프론트 타입/API/페이지를 백엔드에 정합
- OMS UI 업그레이드: 스키마 빌더, 가격 매트릭스, OrderGrid, 카테고리

## 남은 TODO

### 데이터
- [ ] quantum-campaign SQLite → PostgreSQL 캠페인 마이그레이션
- [ ] 운영 유저/회사/상품/가격정책 데이터 입력

### 인프라
- [ ] 도메인 + SSL 설정 (Let's Encrypt)
- [ ] 백업 자동화 (cron + scripts/backup-db.sh)
- [ ] CI/CD (GitHub Actions)

### 알려진 이슈
- Scheduler: Campaign.superap_account FK mapper 에러 (키워드 로테이션 비동작, 백엔드 ORM 설정 수정 필요)
