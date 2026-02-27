# J2LAB 통합 플랫폼 — 워크플로우 다이어그램

## 1. 전체 파이프라인 (접수 → 세팅 → 관리)

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 상품등록  │───►│ 주문접수  │───►│ 입금확인   │───►│ 키워드추출 │───►│ 자동배정  │
│ (admin)  │    │ (총판)   │    │ (경리)    │    │ (자동)    │    │ (자동)   │
└─────────┘    └─────────┘    └──────────┘    └──────────┘    └─────┬────┘
                                                                    │
                                                          ┌─────────┴────────┐
                                                          │                  │
                                                    ┌─────▼────┐     ┌──────▼─────┐
                                                    │ 배정확인   │     │ 자동연장    │
                                                    │ (담당자)   │     │ (7일이내)   │
                                                    └─────┬────┘     └──────┬─────┘
                                                          │                 │
                                                    ┌─────▼────┐     ┌─────▼──────┐
                                                    │ 캠페인등록 │     │ 연장 디스패치│
                                                    │ (자동)    │     │ (자동)      │
                                                    └─────┬────┘     └─────┬──────┘
                                                          │                │
                                                          └────────┬───────┘
                                                                   │
                                                             ┌─────▼─────┐
                                                             │ 캠페인활성  │
                                                             │ 키워드변경  │
                                                             │ (10분 주기) │
                                                             └─────┬─────┘
                                                                   │
                                                             ┌─────▼─────┐
                                                             │ 주문완료   │
                                                             │ (자동)    │
                                                             └──────────┘
```

## 2. 파이프라인 상태 머신

```
                          ┌──────────────────────────────────────────────────┐
                          │              정상 흐름 (Happy Path)                │
                          │                                                  │
 ┌───────┐  submit  ┌──────────┐  입금확인  ┌────────────┐  추출디스패치  ┌──────────────┐
 │ draft │────────►│ submitted │────────►│ payment_   │───────────►│ extraction_  │
 └───┬───┘         └─────┬────┘         │ confirmed  │            │ queued       │
     │                   │              └────────────┘            └──────┬───────┘
     │                   │                                              │
     │ cancel       cancel/reject                                  worker 시작
     │                   │                                              │
     ▼                   ▼                                        ┌─────▼────────┐
 ┌──────────┐      ┌──────────┐                                  │ extraction_  │
 │cancelled │      │ rejected │                                  │ running      │
 └──────────┘      └──────────┘                                  └──────┬───────┘
                                                                       │
                                                                  추출 완료
                                                                       │
 ┌──────────┐                                                    ┌─────▼────────┐
 │  failed  │◄─── 에러 발생 시 ──────────────────────────────────│ extraction_  │
 │          │     (어느 단계든)                                    │ done         │
 │  재시도 →├────────────────────┐                                └──────┬───────┘
 │extraction│                    │                                      │
 │_queued   │                    │                                 자동 배정
 │  or      │                    │                                      │
 │campaign_ │              ┌─────▼────────┐  배정확인  ┌────────────────▼┐  캠페인생성
 │registerin│              │ account_     │─────────►│ assignment_     │──────────►
 │g         │              │ assigned     │          │ confirmed       │
 └──────────┘              └──────────────┘          └────────────────┬┘
                                                                     │
                           ┌──────────────┐  등록성공  ┌──────────────▼┐
                           │ campaign_    │◄─────────│ campaign_     │
                           │ active       │          │ registering   │
                           └──────┬───────┘          └───────────────┘
                                  │
                           ┌──────▼───────┐
                           │ management   │
                           └──────┬───────┘
                                  │
                           ┌──────▼───────┐
                           │ completed    │
                           └──────────────┘
```

## 3. 역할별 워크플로우

### 3.1 총판 (distributor) 워크플로우

```
총판 로그인
  │
  ├─► 주문 접수 (/orders/grid)
  │     │
  │     ├─ 1. 카테고리 선택
  │     ├─ 2. 상품 선택
  │     ├─ 3. 주문 폼 입력 (place_url, 키워드, 기간 등)
  │     │     또는 Excel 업로드 → 미리보기 → 확정
  │     └─ 4. 주문 생성 (draft 상태)
  │
  ├─► 주문 접수 완료 (submit)
  │     │
  │     └─ draft → submitted (경리 승인 대기)
  │
  ├─► 주문 내역 확인 (/orders)
  │     │
  │     └─ 본인 + 하위 셀러 주문만 표시
  │
  ├─► 하위 셀러 관리
  │     │
  │     └─ sub_account 생성 (parent_id = 본인)
  │
  ├─► 마감 캘린더 (/calendar)
  │     │
  │     └─ 본인 관련 마감일 확인
  │
  └─► 공지사항 확인 (/notices)

  ✗ 캠페인 대시보드 접근 불가
  ✗ 상품/유저/정산 접근 불가
```

### 3.2 경리 (company_admin) 워크플로우

```
경리 로그인
  │
  ├─► 대시보드 확인 (/)
  │     │
  │     ├─ 회사 주문 통계 (총 주문, 대기, 매출)
  │     ├─ 활성 캠페인 수
  │     ├─ 파이프라인 현황
  │     ├─ 마감 임박 주문
  │     └─ 키워드 경고
  │
  ├─► 주문 관리 (/orders)
  │     │
  │     ├─ 회사 전체 주문 조회
  │     ├─ 주문 상세 → 입금확인 (submitted → payment_confirmed)
  │     │                  → 파이프라인 자동 시작
  │     ├─ 주문 반려 (submitted → rejected)
  │     ├─ 주문 취소 (draft/submitted → cancelled)
  │     └─ 일괄 상태 변경, Excel 내보내기
  │
  ├─► 캠페인 대시보드 (/campaigns)
  │     │
  │     ├─ 회사 캠페인 모니터링
  │     ├─ 계정별 필터링 (탭)
  │     ├─ 대행사/상태/검색 필터
  │     ├─ 스케줄러 상태 확인 + 수동 실행
  │     ├─ 캠페인 등록/연장/키워드변경/동기화
  │     └─ 캠페인 Excel 업로드
  │
  ├─► 상품 관리 (/products)
  │     │
  │     └─ 상품 조회 (수정 불가 — system_admin만)
  │
  ├─► 가격 매트릭스 (/products/prices/matrix)
  │     │
  │     └─ 역할별 가격 설정 + 원가/할인율 확인
  │
  ├─► 유저 관리 (/users)
  │     │
  │     └─ handler/distributor/sub_account 생성/관리
  │
  ├─► 정산 관리 (/settlements)
  │     │
  │     └─ 매출/이익 분석 + Excel 내보내기
  │
  └─► 마감 캘린더 + 공지사항
```

### 3.3 담당자 (order_handler) 워크플로우

```
담당자 로그인
  │
  ├─► 대시보드 (/)
  │     │
  │     └─ 회사 범위 주문 + 본인 담당 캠페인 통계
  │
  ├─► 주문 내역 (/orders)
  │     │
  │     └─ 회사 전체 주문 조회 (처리 담당)
  │
  ├─► 캠페인 대시보드 (/campaigns)
  │     │
  │     ├─ ★ managed_by = 본인인 캠페인만 표시
  │     ├─ 캠페인 등록/연장/키워드변경
  │     ├─ 스케줄러 모니터링
  │     └─ 배정 확인 (POST /assignment/{id}/confirm)
  │
  ├─► 캠페인 추가/업로드
  │     │
  │     ├─ 수동 캠페인 생성 (/campaigns/add)
  │     ├─ Excel 일괄 업로드 (/campaigns/upload)
  │     └─ 계정/템플릿 관리
  │
  └─► 마감 캘린더 + 공지사항

  ✗ 상품/유저/정산 접근 불가
  ✗ 주문 접수(submit) 불가
```

### 3.4 시스템 관리자 (system_admin) 워크플로우

```
시스템 관리자 로그인
  │
  ├─► 대시보드 — 전체 시스템 현황
  │
  ├─► 전체 관리
  │     ├─ 회사 관리 (생성/수정/삭제)
  │     ├─ 유저 관리 (모든 역할 생성)
  │     ├─ 상품 관리 (생성/수정/비활성화 + 스키마 빌더)
  │     ├─ 카테고리 관리 (생성/정렬)
  │     └─ 시스템 설정 (KV 런타임 설정)
  │
  ├─► 주문 — 전체 주문 조회/처리/일괄변경
  │
  ├─► 캠페인 — 전체 캠페인 + 파이프라인 재시도
  │     │
  │     └─ POST /pipeline/retry-stuck (5분이상 stuck 재시도)
  │
  ├─► 정산 — 전체 분석 + 수익 분석 (비밀번호 보호)
  │
  └─► 전체 모니터링 (대시보드, 캘린더, 공지)
```

## 4. 상품 → 주문 → 캠페인 데이터 플로우

```
[상품 등록]                          [주문 접수]                    [파이프라인]

Product                              Order                         PipelineState
├─ name: "트래픽 캠페인"              ├─ order_number: ORD-xxx       ├─ current_stage
├─ code: "traffic_30"                ├─ user_id (주문자)            ├─ extraction_job_id
├─ form_schema: [                    ├─ company_id                  ├─ campaign_id
│   {name:"place_url", type:"url"}   ├─ status: draft→...→completed│
│   {name:"campaign_type"}           ├─ total_amount (자동계산)     │
│   {name:"duration_days"}           ├─ vat_amount (10%)           │
│   {name:"quantity"}                ├─ completed_at (deadline)    │
│  ]                                 │                              │
├─ base_price: 10000                 └─► OrderItem                  ExtractionJob
├─ cost_price: 5000                      ├─ product_id ─────────►  ├─ naver_url
├─ reduction_rate: 10%                   ├─ item_data: {           ├─ results: [{keyword, rank}]
├─ max_work_days: 7                      │    place_url,           ├─ place_id → Place
│                                        │    campaign_type,       │
│                                        │    duration_days        │
PricePolicy                              │  }                     │
├─ product_id                            ├─ unit_price (자동조회)   Campaign
├─ role: "sub_account"                   ├─ quantity               ├─ campaign_code (from superap)
├─ unit_price: 8000                      ├─ subtotal (할인 적용)    ├─ superap_account_id
├─ effective_from: 2026-01-01            ├─ assigned_account_id    ├─ place_url, place_name
                                         └─ assignment_status      ├─ start_date, end_date
                                                                   ├─ daily_limit, total_limit
                                                                   ├─ managed_by (담당자)
                                                                   └─► CampaignKeywordPool
                                                                       ├─ keyword
                                                                       ├─ is_used
                                                                       └─ round_number
```

## 5. 키워드 자동 변경 사이클

```
┌─────────────────────────────────────────────────────────────────┐
│                    APScheduler (10분 간격)                        │
│                                                                 │
│  1. 활성 superap 계정 조회                                       │
│     │                                                           │
│  2. 계정별 Playwright 브라우저 로그인                              │
│     │                                                           │
│  3. 캠페인 상태 동기화 (superap → DB)                             │
│     │                                                           │
│  4. 캠페인별 키워드 변경:                                         │
│     │                                                           │
│     ├─ 만료? (end_date < 오늘) → 건너뜀                          │
│     ├─ 오늘 이미 변경? (last_keyword_change) → 건너뜀              │
│     │                                                           │
│     ├─ 미사용 키워드 조회 (is_used = false)                       │
│     │   └─ 없으면? → 전체 재활용 (is_used 리셋)                   │
│     │                                                           │
│     ├─ 랜덤 셔플 → 255자 이내로 선택                              │
│     │                                                           │
│     ├─ DRY_RUN=true? → 스킵 (실제 변경 안 함)                    │
│     ├─ DRY_RUN=false? → superap.io에서 키워드 수정                │
│     │                                                           │
│     └─ DB 업데이트: is_used=true, last_keyword_change=now        │
│                                                                 │
│  별도 잡: Retry Stuck (5분 간격)                                  │
│     └─ pending 5분+ stuck → 최대 3회 재시도                       │
└─────────────────────────────────────────────────────────────────┘
```

## 6. 자동 배정 알고리즘

```
auto_assign(order_item, campaign_type, place_id, company_id)
│
├─ Step 1: 연장 확인
│   │
│   ├─ 같은 place_id + campaign_type인 기존 캠페인 검색
│   │   (end_date가 7일 이내)
│   │
│   ├─ 있으면:
│   │   ├─ 기존 total_limit + 신규 total_limit < 10,000?
│   │   │   └─ YES → 연장 (같은 계정, 같은 네트워크)
│   │   │         → 자동 dispatch_campaign_extension()
│   │   └─ NO → 새 캠페인 필요 (Step 2로)
│   │
│   └─ 없으면: Step 2로
│
├─ Step 2: 네트워크 선택
│   │
│   ├─ company_id + campaign_type으로 network_presets 조회
│   ├─ 이 place_id에서 이미 사용한 네트워크 제외
│   ├─ tier_order ASC로 미사용 네트워크 선택
│   │
│   └─ 전부 사용됨? → 캠페인 타입 변경 추천
│
└─ Step 3: 계정 선택
    │
    ├─ 선택된 네트워크의 활성 계정 조회
    ├─ assignment_order ASC로 첫 번째 선택
    │
    └─ 없으면? → 에러 반환 (수동 배정 필요)
```

## 7. 보안 계층

```
┌── 1. Nginx ──────────────────────────────┐
│  Rate limiting (API 30r/s, Auth 5r/s)    │
│  /internal/* 외부 차단 (deny all)          │
│  보안 헤더 (X-Frame, CSP, HSTS 준비)      │
└──────────────────────────────────────────┘

┌── 2. JWT 인증 ───────────────────────────┐
│  Access Token (HS256, 30분)               │
│  Refresh Token (랜덤, 7일, 로테이션)       │
│  bcrypt 비밀번호 해싱                      │
└──────────────────────────────────────────┘

┌── 3. 역할 기반 접근 제어 ─────────────────┐
│  RoleChecker: 엔드포인트별 역할 검증        │
│  데이터 스코핑: company_id, managed_by     │
│  유저 생성 제한: 하위 역할만 생성 가능       │
└──────────────────────────────────────────┘

┌── 4. Worker 통신 보안 ───────────────────┐
│  X-Internal-Secret 헤더 검증              │
│  Docker internal 네트워크 격리             │
│  superap 비밀번호 AES 암호화               │
└──────────────────────────────────────────┘

┌── 5. 데이터 보안 ────────────────────────┐
│  정산 비밀번호 보호 (SETTLEMENT_SECRET)    │
│  DRY_RUN 안전 모드 (실제 광고 생성 방지)    │
│  .env 파일 git 제외                       │
└──────────────────────────────────────────┘
```

---

## 8. 문제점 및 개선 필요 사항

### 🔴 구조적 문제

| # | 문제 | 설명 | 권장 해결방안 |
|---|------|------|-------------|
| 1 | **campaign_active → completed 자동 전환 없음** | 캠페인이 활성화되면 `management` → `completed` 전환이 수동. 캠페인 end_date 도달 시 자동 완료 필요 | campaign-worker에 캠페인 만료 감지 잡 추가 |
| 2 | **order_handler 배정 확인 UI 없음** | 자동 배정 후 `account_assigned` 상태에서 담당자가 확인해야 하는데 프론트엔드에 배정 대기열 페이지 없음 | AssignmentQueuePage 추가 |
| 3 | **주문 상세에서 파이프라인 상태 안 보임** | 관리자가 주문 상세를 봐도 현재 파이프라인 단계, 추출 결과, 캠페인 링크 없음 | OrderDetail에 PipelineStatus 위젯 추가 |
| 4 | **카테고리-상품 관계가 문자열** | FK 아닌 문자열 매칭 → 카테고리 이름 변경 시 상품 불일치 | category_id FK 추가 또는 상품 폼에서 드롭다운 강제 (완료) |

### 🟡 운영 관련

| # | 문제 | 설명 | 권장 해결방안 |
|---|------|------|-------------|
| 5 | **시드 데이터 없음** | 배포 후 상품/카테고리 0개 → 주문 불가 | 기본 상품/카테고리 시드 스크립트 작성 |
| 6 | **superap 계정 비밀번호 키 불일치** | 기존 퀀텀 SECRET_KEY로 암호화된 비밀번호 → 통합 플랫폼 SECRET_KEY와 다를 수 있음 | 비밀번호 재암호화 또는 키 통일 |
| 7 | **알림 테이블 미생성** | `notifications` 테이블 관련 에러 발생 (Alembic에 누락?) | 마이그레이션 확인 + 누락 시 추가 |
| 8 | **계정별 동시 캠페인 제한 없음** | 하나의 superap 계정에 캠페인 무한 배정 가능 | max_campaigns_per_account 설정 추가 |

### 🟠 불필요/중복

| # | 항목 | 설명 |
|---|------|------|
| 9 | `ordersApi.getItems()` | 사용 안 됨 — order.items가 임베디드로 로드됨 |
| 10 | `ordersApi.getDeadlineStatus()` | 사용 안 됨 — deadlines 엔드포인트로 대체됨 |
| 11 | `usersApi.getDescendants()` | 사용 안 됨 — 유저 계층 조회 미사용 |
| 12 | `settingsApi.delete()` | 사용 안 됨 — 설정 삭제 UI 없음 |
| 13 | `companiesApi.get()` | 사용 안 됨 — 개별 회사 조회 불필요 |

### 🟢 향후 확장 고려

| # | 항목 | 설명 |
|---|------|------|
| 14 | WebSocket 실시간 업데이트 | 현재 30초 폴링 → 스케줄러/파이프라인 상태 실시간 |
| 15 | 벌크 배정 확인 | 여러 주문 항목 한번에 배정 확인 |
| 16 | 캠페인 성과 리포트 | 전환수/비용 대비 효율 분석 |
| 17 | 모바일 반응형 개선 | 현재 기본 TailwindCSS 반응형만 적용 |
| 18 | 다국어 지원 | 현재 한국어 하드코딩 |
