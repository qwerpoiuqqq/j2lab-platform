# superap.io API 및 서버 구조 문서

## 서버 계층 구조

```
superap.io (프론트엔드)
├── /service/reward/adver/report  - 캠페인 리포트 대시보드
├── /service/reward/adver/add     - 캠페인 등록/수정 폼
│   └── ?mode=add                 - 신규 등록
│   └── ?mode=modify&id={code}    - 수정
└── /j_spring_security_check      - 로그인 인증 (Spring Security)

report/list API (내부 XHR)
├── GET /service/reward/adver/report/list  - 캠페인 목록 JSON
└── 응답 형식: { data: [...], ... }
```

## report/list API 응답 형식

```json
{
  "data": [
    {
      "ad_idx": "12345",
      "ad_title": "캠페인 이름",
      "status_text": "진행중",
      "total_budget": 1000,
      "day_budget": 50,
      "begin_date": "2024-01-01 00:00:00",
      "end_date": "2024-12-31 23:59:59",
      "current_count": 150,
      "total_count": 300
    }
  ]
}
```

## 상태 값 (status_text)

| superap 한글 | 내부 영문 코드 | 설명 |
|---|---|---|
| 진행중 | active | 정상 진행 |
| 일일소진 | daily_exhausted | 오늘 일일 한도 도달 |
| 캠페인소진 | campaign_exhausted | 전체 한도 도달 |
| 일시정지 | paused | 관리자 일시정지 |
| 대기중 | pending | 시작일 미도래 |
| 종료 | completed | 캠페인 종료 |

## 전환수 필드 매핑

| superap 필드 | DB 컬럼 | 설명 |
|---|---|---|
| current_count | current_conversions | 현재까지 전환 수 |
| total_count / total_budget | total_limit | 전체 전환 한도 |
| day_budget | daily_limit | 일일 전환 한도 |

## 데이터 수집 방법

1. **테이블 파싱**: 리포트 페이지 HTML 테이블에서 상태 텍스트 + 전환수 추출
2. **API 인터셉트**: report/list XHR 응답에서 JSON 구조 추출 (캠페인 코드 추출 시 사용)
3. **개별 검색**: 검색창에 캠페인 코드 입력 → 결과 테이블에서 파싱
