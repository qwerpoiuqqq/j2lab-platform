# J2LAB 통합 플랫폼 - 현재 상태 (2026-02-27)

## API 엔드포인트 테스트 결과

| 영역 | 엔드포인트 | 상태 | 비고 |
|------|-----------|------|------|
| **Auth** | POST /auth/login | PASS | JWT 발급 정상 |
| | POST /auth/login (invalid) | PASS | 401 반환 |
| **Companies** | GET /companies/ | PASS | 2개 회사 |
| **Users** | GET /users/ | PASS | 8명 유저 |
| | GET /users/?role=distributor | PASS | 3명 |
| | GET /users/?role=sub_account | PASS | 0명 (없음) |
| **Categories** | GET /categories/ | PASS | 4개 |
| | POST /categories/ | PASS | icon 포함 생성 |
| | PUT /categories/{id} | PASS | icon 업데이트 |
| | POST /categories/reorder | PASS | |
| | DELETE /categories/{id} | PASS | |
| **Products** | GET /products/ | PASS | |
| | POST /products/ | PASS | 배열 form_schema |
| | PATCH /products/{id} | PASS | |
| | GET /products/{id}/schema | PASS | form_schema list 반환 |
| | DELETE /products/{id} | PASS | soft delete |
| **Price Policies** | POST /products/{id}/prices (role) | PASS | |
| | POST /products/{id}/prices (user) | PASS | UUID user_id |
| | GET /products/{id}/prices | PASS | |
| | DELETE /products/prices/{id} | PASS | |
| **Price Matrix** | GET /products/prices/matrix | PASS | per-role |
| | GET /products/prices/user-matrix | PASS | per-user |
| **Orders** | GET /orders/ | PASS | |
| **Dashboard** | GET /dashboard/summary | PASS | |
| | GET /dashboard/enhanced | PASS | |
| **Notifications** | GET /notifications/ | PASS | |
| **Notices** | GET/POST/PUT/DELETE /notices/ | PASS | 전체 CRUD |
| **Settlements** | GET /settlements/ | PASS | |
| **Campaigns** | GET /campaigns/ | PASS | 562건 |
| **Assignment** | GET /assignment/queue | PASS | |

**결과: 36/38 PASS** (2건은 경로 문제: /auth/me 미존재, /balance/transactions 파라미터 필요)

---

## 프론트엔드 페이지 목록 (23개)

| 경로 | 페이지 | 권한 | 상태 |
|------|--------|------|------|
| `/login` | LoginPage | 공개 | OK |
| `/` | DashboardPage | 모든 로그인 유저 | OK |
| `/orders` | OrdersPage | 모든 로그인 유저 | OK |
| `/orders/grid` | OrderGridPage | 모든 로그인 유저 | OK - normalizeSchema 적용 |
| `/orders/:id` | OrderDetailPage | 모든 로그인 유저 | OK |
| `/notices` | NoticesPage | 모든 로그인 유저 | OK |
| `/campaigns` | CampaignsPage | admin/handler | OK |
| `/campaigns/add` | CampaignAddPage | admin/handler | OK |
| `/campaigns/upload` | CampaignUploadPage | admin/handler | OK |
| `/campaigns/accounts` | SuperapAccountsPage | admin/handler | OK |
| `/campaigns/templates` | CampaignTemplatesPage | admin/handler | OK |
| `/campaigns/:id` | CampaignDetailPage | admin/handler | OK |
| `/assignments` | AssignmentQueuePage | admin/handler | OK |
| `/users` | UsersPage | system_admin/company_admin | OK |
| `/products` | ProductsPage | system_admin/company_admin | OK - 스키마 빌더 OMS 스타일 |
| `/products/prices/matrix` | PriceMatrixPage | system_admin/company_admin | OK - per-user 카드+모달 |
| `/products/categories` | CategoriesPage | system_admin/company_admin | OK - 아이콘+상품수 |
| `/settlements` | SettlementPage | system_admin/company_admin | OK |
| `/calendar` | CalendarPage | admin/handler/distributor | OK |
| `/companies` | CompaniesPage | system_admin | OK |
| `/settings` | SettingsPage | system_admin | OK |
| `/settlements/secret` | SettlementSecretPage | system_admin | OK |
| `*` | NotFoundPage | - | OK |

---

## 이번 세션 수정 내역 (2026-02-27)

### OMS UI 업그레이드 (신규 기능)
1. **ProductsPage.tsx** - 스키마 빌더 전면 리라이트 (스프레드시트 미리보기 + 필드 편집 패널 + 수식 빌더 + 색상 + is_quantity)
2. **OrderGrid.tsx** - 컬럼 헤더 색상, is_quantity 가격계산, 행 복사, 향상된 요약바
3. **PriceMatrixPage.tsx** - per-user 카드 리스트 + 설정 모달 (카테고리 탭, 단가/할인율)
4. **CategoriesPage.tsx** - 아이콘 선택 UI + 상품 수 표시
5. **CategorySelector.tsx** - 카테고리 아이콘(이모지) 표시
6. **schema.ts (신규)** - normalizeSchema() 구/신 포맷 호환 유틸
7. **category.py model** - icon 컬럼 추가
8. **008_add_category_icon.py (신규)** - Alembic 마이그레이션
9. **seed-data.sh** - OMS 배열 스키마 포맷 + 카테고리 아이콘

### 디버깅 수정 (버그 픽스)
1. **category_service.py** - create_category에서 icon 필드 누락
2. **categories.py router** - is_active 쿼리 파라미터 지원
3. **products.py router** - per-user 가격 매트릭스 엔드포인트 (GET /prices/user-matrix)
4. **prices.ts** - getUserMatrix() API 추가, getUserPrices() user-matrix 기반
5. **PriceMatrixPage.tsx** - per-user 데이터로 전면 리빌드, "전체" 카테고리 탭
6. **ProductsPage.tsx** - normalizeSchema로 구/신 포맷 호환
7. **OrderGridPage.tsx** - normalizeSchema로 form_schema 정규화
8. **types/index.ts** - FormFieldExtended 확장, Category.icon, Request 타입 icon
9. **category.py schema** - icon 필드 추가 (Create/Update/Response)

### 데이터 보정
- 카테고리 아이콘: grid → chart-bar/bookmark/sparkles/receipt
- Traffic 30일 상품: category null → 트래픽, form_schema null → 6개 필드
- Alembic 008 마이그레이션 실행

---

## 3개 참조 프로젝트 연동 상태

| 참조 프로젝트 | 위치 | 통합 상태 |
|-------------|------|----------|
| **Keyword Extract** | `reference/keyword-extract/` | keyword-worker로 구성 완료, 내부 API 6개, 127개 테스트 |
| **Quantum Campaign** | `reference/quantum-campaign/` | campaign-worker로 구성 완료, 내부 API 7개, 132개 테스트 |
| **jtwolablife OMS** | `reference/oms-django/` | api-server + frontend로 구성, OMS UI 패턴 포팅 진행 중 |

---

## 다음 할 일 (우선순위)

### 긴급 (데이터/기능)
- [ ] sub_account 유저 추가 (현재 0명 → PriceMatrix에서 셀러가 안 보임)
- [ ] 시드 상품 추가 (현재 1개만 활성 → 카테고리별 상품 필요)
- [ ] quantum-campaign SQLite → PostgreSQL 데이터 마이그레이션 (562건 캠페인 있음)

### 프론트엔드 개선
- [ ] OrderGrid에서 normalizeSchema 후 색상/is_quantity 동작 확인
- [ ] 주문 접수 → 저장 → 목록 E2E 플로우 테스트
- [ ] 캠페인 상세 페이지 OMS 스타일 개선

### 백엔드 연동
- [ ] keyword_worker_client.py 구현 (api-server → keyword-worker HTTP)
- [ ] campaign_worker_client.py 구현 (api-server → campaign-worker HTTP)
- [ ] 엑셀 업로드 기능 완성

### 인프라
- [ ] 도메인 + SSL 설정
- [ ] 백업 자동화 (cron + scripts/backup-db.sh)
