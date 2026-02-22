# Keyword Extract - Reference Code

이 디렉토리는 **원본 키워드 추출 프로젝트** (`Keyword_extract_program_backup/`)의 소스 코드를 참조용으로 복사한 것입니다.

통합 플랫폼의 `keyword-worker` 서비스 개발 시 참고 자료로 사용합니다.

## 디렉토리 구조

```
keyword-extract/
├── README.md              # 이 파일
├── main.py                # CLI 진입점
├── gui_app.py             # GUI (tkinter) 진입점
├── requirements.txt       # CLI/GUI 의존성
├── requirements-web.txt   # 웹 서버 의존성
├── Dockerfile             # Docker 빌드 설정
├── docker-compose.yml     # Docker Compose 설정
├── DEVELOPMENT_LOG.md     # 개발 일지
├── src/                   # 핵심 로직
│   ├── smart_worker.py          # 메인 작업 오케스트레이터
│   ├── keyword_generator.py     # 키워드 생성
│   ├── keyword_parser.py        # 키워드 파싱
│   ├── keyword_rank_checker.py  # 키워드 순위 체크
│   ├── keyword_type_checker.py  # 키워드 유형 분류
│   ├── keyword_checker_v2.py    # 키워드 체커 v2
│   ├── rank_checker.py          # 순위 체커 (Playwright)
│   ├── rank_checker_api.py      # 순위 체커 (API)
│   ├── rank_checker_graphql.py  # 순위 체커 (GraphQL)
│   ├── place_scraper.py         # 네이버 플레이스 스크래퍼
│   ├── gemini_client.py         # Gemini AI 연동
│   ├── address_parser.py        # 주소 파싱
│   ├── models.py                # 데이터 모델
│   ├── learning_manager.py      # 학습 데이터 관리
│   ├── learning_data.json       # 학습 데이터
│   ├── playwright_installer.py  # Playwright 자동 설치
│   ├── resource_path.py         # 리소스 경로 유틸
│   └── url_parser.py            # URL 파싱 유틸
└── web/                   # 웹 인터페이스
    ├── app.py                   # FastAPI 웹 서버
    ├── async_smart_worker.py    # 비동기 작업 워커
    ├── proxy_pool.py            # 프록시 풀 관리
    ├── session_manager.py       # 세션 관리
    └── static/
        ├── index.html           # 웹 UI
        ├── app.js               # 프론트엔드 JS
        └── style.css            # 스타일시트
```

## 보안 관련 제외 파일

다음 파일/디렉토리는 **보안상의 이유로 의도적으로 제외**되었습니다:

| 제외 항목 | 사유 |
|-----------|------|
| `settings.json` | 프록시 서버 인증 정보 (IP, 포트, 사용자명, 비밀번호) 포함 |
| `.env` | 환경 변수 (API 키 등) 포함 |
| `data/` | 작업 결과 데이터 (고객 업소 정보 포함 가능) |
| `build/`, `dist/` | 빌드 산출물 (.exe 등), 용량 과다 |
| `__pycache__/` | Python 캐시, 불필요 |

## 핵심 파일 안내

통합 플랫폼 `keyword-worker` 개발 시 주로 참고할 파일:

1. **`src/smart_worker.py`** - 전체 키워드 추출 워크플로우의 메인 오케스트레이터
2. **`web/app.py`** - FastAPI 기반 웹 서버 (API 엔드포인트 설계 참고)
3. **`web/async_smart_worker.py`** - 비동기 버전 워커 (통합 플랫폼에서 채택할 패턴)
4. **`src/models.py`** - 데이터 모델 정의 (DB 스키마 설계 참고)
5. **`src/place_scraper.py`** - 네이버 플레이스 스크래핑 로직

## 복사 일자

2026-02-23 (원본: `../../../Keyword_extract_program_backup/`)
