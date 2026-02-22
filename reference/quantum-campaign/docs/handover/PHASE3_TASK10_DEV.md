# Phase 3 - Task 3.10 개발 완료 문서

## 작업 개요
대시보드 UI - 프론트엔드 구현. React + TypeScript + TailwindCSS 기반 관리자 대시보드.

## 기술 스택
- React 18 + TypeScript
- Vite (빌드 도구)
- TailwindCSS v4 (@tailwindcss/vite 플러그인)
- React Router v7
- Axios (HTTP 클라이언트)

## 프로젝트 구조

```
frontend/src/
├── types/
│   └── index.ts              # 전체 타입 정의 (백엔드 API 스키마와 1:1 매핑)
├── services/
│   └── api.ts                # API 호출 함수 (axios)
├── hooks/
│   ├── useAccounts.ts        # 계정/대행사/통계 훅
│   ├── useCampaigns.ts       # 캠페인 목록 훅 (필터+페이지네이션)
│   ├── useUpload.ts          # 엑셀 업로드 훅
│   └── useTemplates.ts       # 템플릿/모듈 훅
├── components/
│   ├── common/
│   │   ├── Layout.tsx        # 사이드바 + 메인 레이아웃
│   │   ├── Modal.tsx         # 범용 모달
│   │   ├── Tabs.tsx          # 탭 컴포넌트
│   │   └── KeywordBadge.tsx  # 키워드 상태 뱃지 (🟢🟡🔴)
│   ├── Dashboard/
│   │   ├── StatsBar.tsx      # 통계 카드 4개 (전체/진행중/소진/경고)
│   │   ├── FilterBar.tsx     # 대행사/상태/검색 필터
│   │   └── CampaignTable.tsx # 캠페인 목록 테이블 + 페이지네이션
│   ├── Upload/
│   │   ├── FileUploader.tsx  # 엑셀 파일 업로드 UI
│   │   └── PreviewTable.tsx  # 미리보기 테이블 (연장/신규 선택)
│   ├── Campaign/
│   │   └── KeywordAddModal.tsx  # 키워드 추가 모달
│   └── Template/
│       └── TemplateEditModal.tsx # 템플릿 편집 모달 (모듈 켜기/끄기)
├── pages/
│   ├── Dashboard.tsx         # 메인 대시보드 (/dashboard)
│   ├── Upload.tsx            # 엑셀 업로드 (/upload)
│   ├── CampaignAdd.tsx       # 캠페인 직접 추가 (/campaigns/add)
│   └── TemplateSettings.tsx  # 템플릿 관리 (/settings/templates)
├── App.tsx                   # 라우팅 설정
├── main.tsx                  # 엔트리포인트
└── index.css                 # TailwindCSS import
```

## 페이지별 기능

### 1. 메인 대시보드 (/dashboard)
- **계정 탭**: 전체 + 각 계정별 탭 전환
- **통계 바**: 전체/진행중/오늘소진/경고 4개 카드
- **필터**: 대행사 드롭다운, 상태 드롭다운, 상호명 검색 (클라이언트사이드)
- **캠페인 테이블**: 번호, 상호명, 상태, 전환수, 작업일, 키워드잔량, 최근변경, 작업
- **키워드 뱃지**: normal(🟢), warning(🟡), critical(🔴)
- **페이지네이션**: 이전/다음 버튼
- **키워드 추가**: 각 캠페인에서 +키워드 버튼 → 모달

### 2. 엑셀 업로드 (/upload)
- **파일 업로더**: 드래그 영역 + 파일 선택 버튼
- **미리보기 테이블**: 체크박스, 상호명, 타입, 기간, 연장가능 여부
- **연장/신규 선택**: 연장 가능한 행에 드롭다운
- **최종 등록**: 선택된 항목만 일괄 등록

### 3. 캠페인 직접 추가 (/campaigns/add)
- **캠페인 번호 확인**: 입력 + 확인 버튼 (DB 중복 체크)
- **폼 입력**: 계정, 플레이스명/URL, 타입, 날짜, 일일한도, 키워드
- **검증 피드백**: 성공/실패 메시지 표시

### 4. 템플릿 관리 (/settings/templates)
- **템플릿 목록**: 이름, 캠페인타입, 모듈, 상태, 편집 버튼
- **편집 모달**: 모듈 켜기/끄기 체크박스, 텍스트 편집, 링크 관리

## API 연동

| 프론트엔드 호출 | 백엔드 엔드포인트 | 용도 |
|----------------|-------------------|------|
| `fetchAccounts()` | GET /accounts | 계정 목록 (탭) |
| `fetchAgencies()` | GET /agencies | 대행사 목록 (필터) |
| `fetchDashboardStats()` | GET /dashboard/stats | 통계 카드 |
| `fetchCampaigns()` | GET /campaigns | 캠페인 목록 (필터+페이지네이션) |
| `fetchCampaignDetail()` | GET /campaigns/{id} | 캠페인 상세 |
| `addManualCampaign()` | POST /campaigns/manual | 수기 캠페인 추가 |
| `verifyCampaign()` | GET /campaigns/manual/verify/{code} | 캠페인 번호 확인 |
| `addKeywords()` | POST /campaigns/{id}/keywords | 키워드 추가 |
| `uploadPreview()` | POST /upload/preview | 엑셀 미리보기 |
| `confirmUpload()` | POST /upload/confirm | 엑셀 확정 등록 |
| `fetchTemplates()` | GET /templates | 템플릿 목록 |
| `fetchTemplateDetail()` | GET /templates/{id} | 템플릿 상세 |
| `updateTemplate()` | PUT /templates/{id} | 템플릿 수정 |
| `fetchModules()` | GET /modules | 모듈 목록 |

## Vite 설정

```typescript
// vite.config.ts
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  },
}
```

- 개발 서버: http://localhost:3000
- API 프록시: `/api/*` → `http://localhost:8000/*`
- 백엔드 CORS: `http://localhost:3000` 허용 (이미 설정됨)

## 빌드 결과

```
3회 연속 빌드 성공:
- tsc --noEmit: 에러 없음
- vite build: 성공
  - index.html: 0.46 kB
  - CSS: 16.35 kB (gzip: 4.07 kB)
  - JS: 295.96 kB (gzip: 95.64 kB)
```

## 파일 목록

### 새 파일 (22개)
- `frontend/src/types/index.ts`
- `frontend/src/services/api.ts`
- `frontend/src/hooks/useAccounts.ts`
- `frontend/src/hooks/useCampaigns.ts`
- `frontend/src/hooks/useUpload.ts`
- `frontend/src/hooks/useTemplates.ts`
- `frontend/src/components/common/Layout.tsx`
- `frontend/src/components/common/Modal.tsx`
- `frontend/src/components/common/Tabs.tsx`
- `frontend/src/components/common/KeywordBadge.tsx`
- `frontend/src/components/Dashboard/StatsBar.tsx`
- `frontend/src/components/Dashboard/FilterBar.tsx`
- `frontend/src/components/Dashboard/CampaignTable.tsx`
- `frontend/src/components/Upload/FileUploader.tsx`
- `frontend/src/components/Upload/PreviewTable.tsx`
- `frontend/src/components/Campaign/KeywordAddModal.tsx`
- `frontend/src/components/Template/TemplateEditModal.tsx`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/Upload.tsx`
- `frontend/src/pages/CampaignAdd.tsx`
- `frontend/src/pages/TemplateSettings.tsx`
- `docs/handover/PHASE3_TASK10_DEV.md`

### 수정 파일
- `frontend/vite.config.ts` - TailwindCSS 플러그인 + 프록시 설정
- `frontend/src/index.css` - TailwindCSS import
- `frontend/src/App.tsx` - 라우팅 설정
- `frontend/src/main.tsx` - (변경 없음, 기존 유지)

### 삭제 파일
- `frontend/src/App.css` - 기본 CSS 삭제 (TailwindCSS 사용)
- `frontend/src/assets/react.svg` - 기본 에셋 삭제
- `frontend/public/vite.svg` - 기본 에셋 삭제

## 다음 단계 (Phase 3 - Task 3.11)
- 통합 테스트 & 안정화
- 전체 플로우 E2E 테스트
- 에러 핸들링 강화
- 로깅 추가
