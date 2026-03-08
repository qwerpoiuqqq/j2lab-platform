# 일류 리워드 플랫폼 — 워크플로우 설계 문서 (Claude Code 구현 가이드)

> **문서 목적**: Claude Code에 전달하여 구현 방향성을 잡기 위한 전체 워크플로우 명세서
> **작성일**: 2026-03-02
> **버전**: v2.0
> **운영 회사**: 제이투랩, 일류기획
> **연동 시스템**: Quantum Campaign Automation (superap.io)

---

## 1. 시스템 개요

일류 리워드 플랫폼은 네이버 플레이스 리워드 캠페인의 **접수 → 정산 확인 → 자동 세팅 → 캠페인 운영 → 정산 관리**를 하나의 시스템에서 처리하는 통합 플랫폼이다.

상품은 **트래픽**과 **저장하기** 두 가지이며, 이 상품들을 superap.io(퀀텀)에 세팅하여 운영한다.

---

## 2. 계정 체계 (6단계 계층)

```mermaid
graph TD
    SA["🔑 시스템 관리자"]
    SA --> C1["🏢 제이투랩"]
    SA --> C2["🏢 일류기획"]
    C1 --> SM1["💰 제이투랩 정산 관리자"]
    C2 --> SM2["💰 일류기획 정산 관리자"]
    SM1 --> M1["👤 담당자(영업) A, B, ...N"]
    SM2 --> M2["👤 담당자(영업) A, B, ...N"]
    M1 --> D1["🏪 총판 A, B, ..."]
    M2 --> D2["🏪 총판 C, D, ..."]
    D1 --> SUB1["📋 하부계정 1, 2, ..."]
    D2 --> SUB2["📋 하부계정 3, 4, ..."]

    style SA fill:#ff6b6b,color:#fff
    style C1 fill:#4ecdc4,color:#fff
    style C2 fill:#4ecdc4,color:#fff
    style SM1 fill:#45b7d1,color:#fff
    style SM2 fill:#45b7d1,color:#fff
```

### 계정별 권한

| 계정 등급 | 접수 | 하부계정 접수건 선택 | 정산 체크 | 승인여부 조회 | 대시보드 | 정산 관리 | 네트워크 관리 |
|-----------|:----:|:-------------------:|:---------:|:-------------:|:--------:|:---------:|:------------:|
| 시스템 관리자 | - | - | - | ✅ | ✅ 전체 | ✅ 전체 | ✅ |
| 정산 관리자 | - | - | ✅ | ✅ | ✅ 자사 | ✅ 자사 | - |
| 담당자(영업) | - | - | ❌ | ✅ 자기라인 | ✅ 자기라인 | ✅ 자기라인 | - |
| 총판 | ✅ | ✅ | ❌ | ❌ | ✅ 자기건 | ❌ | - |
| 하부계정 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | - |

**핵심 규칙:**
- 하부계정은 **접수만** 가능. 정산 프로세스 없음, 대시보드 없음.
- 총판은 대시보드에서 하부계정 접수건을 **해당일 접수에 포함시킬지 선택** 가능.
- 정산 체크 버튼은 **각 회사의 정산 관리자(메인 계정)만** 누를 수 있음.
- 담당자는 자기 라인의 총판 접수건 승인 여부를 **조회만** 가능.

---

## 3. 네트워크 구조

### 개념

네트워크는 superap.io에서 캠페인을 세팅하는 **계정 그룹** 단위이다. 각 회사별로 지정된 세팅 계정들이 있고, 계정마다 매체 단가가 다르다. 매체 단가가 높을수록 더 많은 앱/서버를 사용할 수 있고 상위 노출 확률이 높아진다.

### 네트워크 프리셋 예시

| 네트워크명 | 회사 | 상품 | 매체 단가 | tier_order |
|-----------|------|------|----------|:----------:|
| 트래픽 제이투랩 | 제이투랩 | 트래픽 | 21원 | 1 |
| 트래픽 제이투랩24 | 제이투랩 | 트래픽 | 25원 | 2 |
| 저장 제이투랩 | 제이투랩 | 저장하기 | 별도 | 1 |
| 트래픽 일류기획 | 일류기획 | 트래픽 | 21원 | 1 |
| 트래픽 일류기획24 | 일류기획 | 트래픽 | 25원 | 2 |
| 저장 일류기획24 | 일류기획 | 저장하기 | 별도 | 1 |

### 동적 관리 (필수)

네트워크 프리셋은 **언제든 추가/수정/삭제가 가능**해야 한다. 새로운 단가 버전의 계정이 나올 수 있기 때문이다.

```mermaid
graph LR
    subgraph NETWORK["네트워크 프리셋"]
        NP["트래픽 제이투랩 (21원, tier 1)"]
    end

    subgraph ACCOUNTS["연동된 superap 계정들"]
        A1["계정 A (assignment_order: 1)"]
        A2["계정 B (assignment_order: 2)"]
        A3["계정 C (assignment_order: 3)"]
    end

    NP --> A1
    NP --> A2
    NP --> A3

    ADMIN["관리자"] -->|"추가/수정/삭제"| NETWORK
    ADMIN -->|"계정 연동/해제"| ACCOUNTS

    style NETWORK fill:#e3f2fd,stroke:#1565c0
    style ACCOUNTS fill:#fff3e0,stroke:#e65100
```

네트워크 프리셋 관리에서 할 수 있는 것:
- 새 네트워크 프리셋 생성 (이름, 회사, 상품 타입, 단가, 순서 지정)
- 기존 프리셋 정보 수정 (단가 변경, 순서 변경, 활성/비활성)
- 프리셋에 superap 계정 연동/해제
- 프리셋 삭제 (연결된 캠페인이 없는 경우)

---

## 4. 메인 워크플로우 (End-to-End)

```mermaid
flowchart TD
    START(("시작"))

    subgraph PHASE1["📥 PHASE 1: 접수"]
        A1["총판 또는 하부계정 로그인"]
        A2["상품 접수 양식 작성<br/>━━━━━━━━━━━━━<br/>• 작업 시작일<br/>• 일 작업량(타수)<br/>• 작업 기간<br/>• 목표 노출 키워드<br/>• 플레이스 URL"]
        A_AI["🤖 AI 추천 표시<br/>━━━━━━━━━━━━━<br/>MID 기반 이력 조회 →<br/>신규/기존 판별 →<br/>최적 네트워크·상품 추천"]
        A3{"접수 주체?"}
        A4["총판 대시보드에 즉시 반영"]
        A5["하부계정 접수건 →<br/>총판 대시보드에 대기"]
        A6["총판: 하부계정 접수건<br/>해당일 포함 여부 선택"]
    end

    subgraph PHASE2["💰 PHASE 2: 정산 확인"]
        B1["정산 관리자 대시보드<br/>총판별 당일 접수 물량 확인<br/>━━━━━━━━━━━━━<br/>제이투랩 정산관리자 → 제이투랩 라인만<br/>일류기획 정산관리자 → 일류기획 라인만"]
        B2{"정산 체크<br/>(입금 확인)"}
        B3["✅ 승인 → 접수건 확정"]
        B4["❌ 미승인 → 보류/반려"]
        B5["담당자: 자기 라인 승인 여부 조회"]
    end

    subgraph PHASE3["⏳ PHASE 3: 대기열"]
        C1["접수 마감 시간 도달"]
        C2["세팅 대기 시간 경과"]
        C3["🔄 자동으로 세팅 대기열 이동"]
    end

    subgraph PHASE4["⚙️ PHASE 4: 자동 세팅 + 담당자 확인"]
        D0["담당자(영업):<br/>신규 세팅 / 연장 세팅<br/>택 1 선택"]
        D1{"선택 결과"}
        D_NEW["🆕 신규 세팅<br/>AI 추천 네트워크로<br/>새 캠페인 생성"]
        D_EXT["🔄 연장 세팅<br/>기존 캠페인에<br/>타수·기간 추가"]
        D_AUTO["자동 세팅 로직 실행<br/>(Quantum 연동)<br/>━━━━━━━━━━━━━<br/>• 키워드 자동 추출 & 세팅<br/>• 네트워크 자동 배정<br/>• 네트워크별 기준 타수 초과 시<br/>  다음 네트워크 자동 변경"]
    end

    subgraph PHASE5["📊 PHASE 5: 캠페인 운영"]
        E1["캠페인 라이브 🟢"]
        E2["유입 키워드 자동 변경 ✅"]
        E3["캠페인별 구동 기간 &<br/>일 타수 기록·모니터링"]
        E4["연장 이력 관리 ✅"]
    end

    subgraph PHASE6["📈 PHASE 6: 정산 관리"]
        F1["담당자별 총판 수익 확인"]
        F2["담당자별 영업 이익"]
        F3["회사별 총 매출 & 영업 이익"]
        F4["일자별 매출·영업이익 현황"]
        F5["총판별 상품 단가 별도 지정"]
    end

    START --> A1 --> A2 --> A_AI --> A3
    A3 -->|"총판 직접"| A4
    A3 -->|"하부계정"| A5 --> A6 --> A4
    A4 --> B1
    B1 --> B2
    B2 -->|"YES"| B3
    B2 -->|"NO"| B4
    B1 -.->|"조회"| B5
    B3 --> C1 --> C2 --> C3
    C3 --> D0 --> D1
    D1 -->|"신규"| D_NEW --> D_AUTO
    D1 -->|"연장"| D_EXT --> D_AUTO
    D_AUTO --> E1
    E1 --> E2
    E1 --> E3
    E1 --> E4
    E1 -.->|"정산 데이터"| F1
    F1 --> F2 --> F3 --> F4
    F3 -.-> F5

    style PHASE1 fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style PHASE2 fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style PHASE3 fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style PHASE4 fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style PHASE5 fill:#e0f7fa,stroke:#00695c,stroke-width:2px
    style PHASE6 fill:#fce4ec,stroke:#c62828,stroke-width:2px
```

---

## 5. PHASE 1 상세: 접수 + AI 추천

### 접수 양식 입력 필드

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| 플레이스 URL | URL | ✅ | 네이버 플레이스 URL (MID값 자동 추출) |
| 작업 시작일 | Date | ✅ | 캠페인 시작 날짜 |
| 일 작업량 | Integer | ✅ | 하루 타수 (일일 전환 목표) |
| 작업 기간 | Integer | ✅ | 작업 일수 |
| 목표 노출 키워드 | Text | ✅ | 원하는 노출 키워드 |

### AI 추천 로직

총판/하부계정이 플레이스 URL을 입력하는 시점에 시스템이 즉시 분석하여 추천을 표시한다.

```mermaid
flowchart TD
    INPUT["플레이스 URL 입력"]
    EXTRACT["MID값 자동 추출"]
    CHECK{"해당 MID로<br/>기존 캠페인 이력 존재?"}

    subgraph NEW["🆕 신규 플레이스"]
        N1["네트워크 순서대로 추천 표시"]
        N2["트래픽 네트워크1 (21원)<br/>→ 트래픽 네트워크2 (24원)<br/>→ 저장하기 네트워크1<br/>→ 저장하기 네트워크2<br/>→ ..."]
    end

    subgraph EXIST["🔄 기존 플레이스"]
        E1["이전 캠페인 정보 표시<br/>━━━━━━━━━━━━━<br/>• 사용한 네트워크<br/>• 마지막 만료일<br/>• 누적 전환수"]
        E2["연장 가능 여부 표시"]
        E3["다음 추천 네트워크 표시"]
    end

    SHOW["🤖 AI 추천 결과 화면에 표시<br/>(접수자가 참고하여 상품 선택)"]

    INPUT --> EXTRACT --> CHECK
    CHECK -->|"없음"| N1 --> N2 --> SHOW
    CHECK -->|"있음"| E1 --> E2 --> E3 --> SHOW

    style NEW fill:#e8f5e9,stroke:#2e7d32
    style EXIST fill:#fff3e0,stroke:#e65100
```

**AI 추천은 참고용이다.** 접수자(총판/하부계정)는 추천을 보고 트래픽 또는 저장하기를 선택하여 접수하면 된다. 최종 세팅 결정은 담당자가 한다.

---

## 6. PHASE 2 상세: 정산 확인

### 정산 관리자 대시보드 흐름

```mermaid
sequenceDiagram
    participant SUB as 하부계정
    participant DIST as 총판
    participant MGR as 담당자
    participant SETTLE as 정산 관리자

    SUB->>DIST: 접수건 제출
    DIST->>DIST: 대시보드에서 해당일 포함 여부 선택
    DIST->>SETTLE: 선택된 접수건 → 정산 대기열
    DIST->>SETTLE: 총판 직접 접수건 → 정산 대기열

    SETTLE->>SETTLE: 총판별 당일 접수 물량 확인
    alt 입금 확인됨
        SETTLE->>SETTLE: 정산 체크 ✅ (승인)
    else 미입금
        SETTLE->>SETTLE: 보류/반려 ❌
    end

    MGR->>MGR: 자기 라인 총판 승인 여부 조회 (읽기 전용)
```

**회사별 분리:** 제이투랩 정산 관리자는 제이투랩 라인의 총판만 보이고, 일류기획 정산 관리자는 일류기획 라인만 보인다. 교차 조회 불가.

---

## 7. PHASE 3 상세: 대기열 → 자동 이동

정산 체크(승인)된 접수건은 바로 세팅으로 넘어가지 않는다.

1. 해당 상품의 **접수 마감 시간**이 도달해야 함
2. 마감 후 **세팅 대기 시간**이 경과해야 함
3. 두 조건 충족 시 **자동으로** 세팅 대기열로 이동

이 과정은 시간 기반 자동 트리거이며, 수동 개입이 필요 없다.

---

## 8. PHASE 4 상세: 담당자 확인 + 자동 세팅

### 담당자(영업)의 역할

세팅 대기열에 올라온 접수건을 보고, 담당자는 **단 두 가지만 선택**하면 된다.

```mermaid
flowchart LR
    QUEUE["세팅 대기열<br/>접수건 도착"]
    HANDLER["담당자(영업)"]
    CHOICE{"선택"}
    NEW["🆕 신규 세팅"]
    EXT["🔄 연장 세팅"]
    AUTO["자동 세팅 로직 실행"]

    QUEUE --> HANDLER --> CHOICE
    CHOICE -->|"신규"| NEW --> AUTO
    CHOICE -->|"연장"| EXT --> AUTO

    style HANDLER fill:#96ceb4,stroke:#333
```

- **신규 세팅**: AI가 추천한 네트워크/계정으로 새 캠페인을 생성
- **연장 세팅**: 기존 캠페인에 타수·기간을 추가하여 연장

담당자는 네트워크 배정이나 계정 선택 같은 복잡한 결정을 할 필요 없다. 시스템이 알아서 처리한다.

### 자동 세팅 로직 (Quantum 연동, 구현 완료)

담당자가 선택한 후 실행되는 자동 세팅 로직의 상세 흐름:

```mermaid
flowchart TD
    INPUT["접수건 + 담당자 선택 결과"]

    subgraph NEW_FLOW["🆕 신규 세팅 플로우"]
        NF1["접수 상품(트래픽/저장하기)에 맞는<br/>네트워크 프리셋 자동 선택<br/>(tier_order 순서)"]
        NF2["선택된 네트워크의<br/>superap 계정 자동 배정<br/>(assignment_order 순서)"]
        NF3["플레이스 키워드 자동 추출"]
        NF4["superap.io에 캠페인 자동 등록"]
    end

    subgraph EXT_FLOW["🔄 연장 세팅 플로우"]
        EF1["기존 캠페인 정보 조회<br/>(MID + 동일 구좌)"]
        EF2{"누적 전환수 체크<br/>기존 타수 + 신규 타수<br/>> 네트워크별 기준값?"}
        EF3["⚠️ 동일 구좌 내<br/>네트워크 변경"]
        EF4["✅ 기존 네트워크 유지"]
        EF5["superap.io에서<br/>캠페인 연장 처리"]
    end

    KW["키워드 자동 추출 & 세팅<br/>(기존 수기 전달 → 자동화)"]
    LIVE["캠페인 라이브 🟢"]

    INPUT -->|"신규"| NF1 --> NF2 --> NF3 --> NF4 --> LIVE
    INPUT -->|"연장"| EF1 --> EF2
    EF2 -->|"> 기준값"| EF3 --> EF5
    EF2 -->|"≤ 기준값"| EF4 --> EF5
    EF5 --> KW --> LIVE

    style NEW_FLOW fill:#e8f5e9,stroke:#2e7d32
    style EXT_FLOW fill:#fff3e0,stroke:#e65100
```

### 자동 연장 조건 (의사코드)

```
# 연장 세팅 시 자동 판단 로직
IF 담당자가 "연장 세팅" 선택:
    기존캠페인 = DB조회(동일 MID + 동일 구좌 + 만료일 차이 ≤ 6일)

    IF 기존캠페인.누적타수 + 신규타수 > 기존캠페인.네트워크기준타수:
        → 동일 구좌 내 다음 네트워크로 변경하여 세팅
    ELSE:
        → 기존 네트워크 유지하고 타수·기간 연장

# 신규 세팅 시 네트워크 선택 로직
IF 담당자가 "신규 세팅" 선택:
    네트워크목록 = 해당 회사 + 해당 상품타입의 네트워크 프리셋 (tier_order ASC)
    사용이력 = 해당 MID로 이미 사용한 네트워크 목록
    선택네트워크 = 네트워크목록에서 사용이력에 없는 첫 번째
    계정 = 선택네트워크에 연동된 계정 (assignment_order ASC, 활성 캠페인 수 최소)
```

---

## 9. PHASE 5 상세: 캠페인 운영

| 기능 | 상태 | 설명 |
|------|:----:|------|
| 유입 키워드 자동 변경 | ✅ 구현 완료 | APScheduler로 주기적 키워드 로테이션 |
| 연장 이력 관리 | ✅ 구현 완료 | JSON 배열로 연장 회차별 기록 |
| 캠페인 구동 기간 & 일 타수 기록 | 🔧 보완 필요 | 현재 연장 기록만 있음 → 전체 기간 표시 추가 |
| 키워드 자동 추출 & 세팅 | 🆕 신규 | 기존 수기 전달 → 접수 시 자동 추출로 전환 |

---

## 10. PHASE 6 상세: 정산 관리

### 대시보드 뷰 구성

```mermaid
graph TD
    subgraph VIEWS["📊 정산 관리 대시보드"]
        V1["👤 담당자별 뷰<br/>━━━━━━━━<br/>담당자에 귀속된 총판들의<br/>접수건 수익 확인"]
        V2["💼 영업 이익 뷰<br/>━━━━━━━━<br/>회사 내 담당자별<br/>영업 이익 비교"]
        V3["🏢 회사별 뷰<br/>━━━━━━━━<br/>회사별 총 매출 &<br/>영업 이익 합산"]
        V4["📅 일자별 뷰<br/>━━━━━━━━<br/>일자별 매출·영업이익<br/>추이 그래프"]
    end

    subgraph CONFIG["⚙️ 정산 설정"]
        V5["💲 총판별 상품 단가<br/>별도 지정 기능<br/>━━━━━━━━<br/>같은 상품이라도<br/>총판마다 다른 단가 적용"]
    end

    DATA["접수·캠페인·운영 데이터"] --> VIEWS
    CONFIG -.->|"단가 정책 반영"| VIEWS

    style VIEWS fill:#fce4ec,stroke:#c62828
    style CONFIG fill:#fff3e0,stroke:#e65100
```

### 정산 계산 로직

```
# 매출 (총판에게 청구하는 금액)
매출 = Σ(접수건별 일_타수 × 작업_기간 × 해당_총판_상품_단가)

# 원가 (superap.io에 지불하는 금액)
원가 = Σ(접수건별 일_타수 × 작업_기간 × 네트워크_매체_단가)
  └ 매체_단가: 네트워크별 상이 (21원, 25원 등)

# 영업이익
영업이익 = 매출 - 원가

# 총판별 단가 커스텀
총판_A_트래픽_단가 = 기본값 존재, 총판별 오버라이드 가능
```

---

## 11. 데이터 모델 (핵심 엔티티 관계)

```mermaid
erDiagram
    COMPANY ||--o{ USER : has
    USER ||--o{ USER : parent_children
    USER ||--o{ ORDER : submits
    ORDER ||--o{ ORDER_ITEM : contains
    ORDER_ITEM ||--|| PIPELINE_STATE : tracks
    ORDER_ITEM }o--|| PRODUCT : references
    ORDER_ITEM }o--o| PLACE : targets
    ORDER_ITEM }o--o| SUPERAP_ACCOUNT : assigned_to
    CAMPAIGN }o--|| ORDER_ITEM : generated_from
    CAMPAIGN }o--o| SUPERAP_ACCOUNT : registered_on
    CAMPAIGN }o--o| NETWORK_PRESET : uses
    CAMPAIGN ||--o{ CAMPAIGN_KEYWORD : has
    NETWORK_PRESET ||--o{ SUPERAP_ACCOUNT : contains
    NETWORK_PRESET }o--|| COMPANY : belongs_to
    USER }o--o| COMPANY : belongs_to
    PRICE_POLICY }o--|| USER : applies_to
    PRICE_POLICY }o--|| PRODUCT : prices

    COMPANY {
        int id PK
        string name "제이투랩 / 일류기획"
        string code
    }

    USER {
        uuid id PK
        string email
        string role "system_admin~sub_account"
        uuid parent_id FK
        int company_id FK
        decimal balance "예치금"
    }

    ORDER {
        int id PK
        uuid user_id FK
        int company_id FK
        string status "draft~completed"
        string payment_status
        decimal total_amount
    }

    ORDER_ITEM {
        int id PK
        int order_id FK
        int product_id FK
        int place_id FK
        json item_data "작업시작일/타수/기간/키워드/URL"
        string assignment_status "pending→auto_assigned→confirmed"
        int assigned_account_id FK
    }

    PIPELINE_STATE {
        int id PK
        int order_item_id FK
        string current_stage "draft~completed (14단계)"
        int campaign_id FK
    }

    CAMPAIGN {
        int id PK
        int order_item_id FK
        int superap_account_id FK
        int network_preset_id FK
        string campaign_type "트래픽/저장하기"
        date start_date
        date end_date
        int daily_limit
        int total_limit
        int current_conversions
        string status
        json extension_history
    }

    NETWORK_PRESET {
        int id PK
        int company_id FK
        string campaign_type
        int tier_order "낮을수록 우선"
        string name
        json media_config
        boolean is_active
    }

    SUPERAP_ACCOUNT {
        int id PK
        string user_id_superap
        int company_id FK
        int network_preset_id FK
        int unit_cost "매체 단가 (21/25원 등)"
        int assignment_order
        boolean is_active
    }

    PRICE_POLICY {
        int id PK
        uuid user_id FK "총판 사용자"
        int product_id FK
        decimal price "해당 총판에 적용되는 단가"
    }
```

---

## 12. 파이프라인 상태 머신

하나의 접수건(OrderItem)이 거치는 전체 라이프사이클:

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> submitted: 접수 제출
    submitted --> payment_confirmed: 정산 관리자 승인
    submitted --> cancelled: 취소/반려

    payment_confirmed --> extraction_queued: 대기열 이동 (시간 트리거)
    extraction_queued --> extraction_running: keyword-worker 시작
    extraction_running --> extraction_done: 키워드 추출 완료

    extraction_done --> account_assigned: AI 자동 배정 (추천)
    account_assigned --> assignment_confirmed: 담당자 확인 (신규/연장 선택)

    assignment_confirmed --> campaign_registering: 캠페인 등록 시작
    campaign_registering --> campaign_active: superap.io 등록 완료

    campaign_active --> management: 운영 관리 단계
    management --> completed: 캠페인 종료

    extraction_queued --> failed: 오류
    extraction_running --> failed: 오류
    campaign_registering --> failed: 오류
    failed --> extraction_queued: 재시도
    failed --> campaign_registering: 재시도
```

---

## 13. 구현 현황 & TODO 요약

| 기능 | 상태 | 비고 |
|------|:----:|------|
| 자동 세팅 로직 (Quantum) | ✅ | 캠페인 등록, 연장, 네트워크 변경 |
| 유입 키워드 자동 변경 | ✅ | APScheduler 키워드 로테이션 |
| 캠페인 연장 이력 관리 | ✅ | JSON 배열 기록 |
| 계정 자동 배정 (assignment) | ✅ | auto_assign → confirm/override |
| 네트워크 프리셋 CRUD | ✅ | 동적 추가/수정/삭제 |
| 파이프라인 상태 추적 | ✅ | 14단계 상태 머신 |
| 접수 시 AI 추천 표시 | 🆕 | MID 기반 이력 조회 → 추천 UI |
| 담당자 신규/연장 선택 UI | 🆕 | 기존 confirm/override 대신 단순화 |
| 총판 → 하부계정 접수건 선택 | 🆕 | 총판 대시보드 기능 |
| 키워드 자동 추출 & 세팅 | 🆕 | 수기 전달 → 자동화 |
| 캠페인 구동 기간 & 일 타수 기록 | 🔧 | 연장 기록만 → 전체 기간 표시 |
| 접수 마감 → 대기열 자동 이동 | 🆕 | 시간 기반 자동 트리거 |
| 정산 관리 대시보드 | 🆕 | 담당자/회사/일자별 뷰 |
| 총판별 상품 단가 지정 | 🆕 | 커스텀 가격 정책 |
| 정산 프로세스 (회사별 분리) | 🔧 | 정산관리자 전용 체크 기능 |

---

## 14. 핵심 비즈니스 룰 요약

1. **하부계정은 접수만 가능.** 정산 프로세스 없음, 대시보드 없음.
2. **총판이 하부계정 접수건 선택.** 대시보드에서 해당일 포함 여부를 골라야 정산 대기열에 올라감.
3. **정산 체크는 정산 관리자만.** 담당자는 자기 라인의 승인 여부 조회만 가능.
4. **회사별 정산 분리.** 제이투랩 정산관리자 ↔ 일류기획 정산관리자 교차 조회 불가.
5. **접수 시 AI 추천.** MID 기반으로 신규/기존 판별, 네트워크 추천은 tier_order 순.
6. **담당자는 신규/연장만 선택.** 네트워크·계정 배정은 시스템이 자동 처리.
7. **자동 연장 조건.** 동일 MID + 동일 구좌 + 만료↔시작 차이 ≤ 6일.
8. **네트워크 변경 트리거.** 연장 시 누적 전환수 > 해당 네트워크 기준 타수이면 동일 구좌 내 다음 네트워크로 이동.
9. **키워드 자동 추출.** 기존 수기 전달 → 접수 시 자동 추출로 전환.
10. **네트워크 동적 관리.** 프리셋은 언제든 추가/수정/삭제 가능. 새 단가 계정 나오면 새 네트워크로 연동.
11. **총판별 단가 커스텀.** 같은 상품이라도 총판마다 다른 단가 적용 가능.
12. **마감 후 자동 큐잉.** 접수 마감 시간 + 세팅 대기 시간 경과 시 자동으로 세팅 대기열 이동.
