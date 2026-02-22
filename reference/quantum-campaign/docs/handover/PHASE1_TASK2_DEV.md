# Phase 1 - Task 1.2 개발 완료

## 완료일시
2026-02-04 (개발 세션)

## 개발된 기능
- SQLAlchemy 모델 정의 (4개 테이블)
- 초기 템플릿 데이터 시딩
- CRUD 및 관계(relationship) 테스트

## 생성/수정된 파일

### 새로 생성된 파일
| 파일 | 설명 |
|------|------|
| `backend/app/models/account.py` | Account 모델 (superap.io 계정) |
| `backend/app/models/template.py` | CampaignTemplate 모델 (캠페인 타입 템플릿) |
| `backend/app/models/campaign.py` | Campaign 모델 (캠페인 정보) |
| `backend/app/models/keyword.py` | KeywordPool 모델 (키워드 풀) |
| `backend/app/seed.py` | 초기 데이터 시딩 스크립트 |
| `backend/tests/conftest.py` | pytest fixtures (인메모리 DB) |
| `backend/tests/test_models.py` | 모델 CRUD 테스트 (12개) |
| `backend/tests/test_relationships.py` | 관계 테스트 (6개) |

### 수정된 파일
| 파일 | 변경 내용 |
|------|-----------|
| `backend/app/config.py` | 절대 경로로 DATABASE_URL 설정 변경 |
| `backend/app/database.py` | declarative_base import 위치 수정 |
| `backend/app/models/__init__.py` | 모든 모델 export |

## DB 스키마

### accounts 테이블
```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    user_id VARCHAR(100) UNIQUE NOT NULL,
    password_encrypted TEXT,
    agency_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP
);
```

### campaign_templates 테이블
```sql
CREATE TABLE campaign_templates (
    id INTEGER PRIMARY KEY,
    type_name VARCHAR(50) UNIQUE NOT NULL,
    description_template TEXT NOT NULL,
    hint_text TEXT NOT NULL,
    campaign_type_selection VARCHAR(100),
    links JSON NOT NULL,
    hashtag VARCHAR(100),
    image_url_200x600 TEXT,
    image_url_720x780 TEXT,
    updated_at TIMESTAMP
);
```

### campaigns 테이블
```sql
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY,
    campaign_code VARCHAR(20),
    account_id INTEGER REFERENCES accounts(id),
    agency_name VARCHAR(100),
    place_name VARCHAR(200) NOT NULL,
    place_url TEXT NOT NULL,
    campaign_type VARCHAR(50) NOT NULL,
    registered_at TIMESTAMP,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    daily_limit INTEGER NOT NULL,
    total_limit INTEGER,
    current_conversions INTEGER DEFAULT 0,
    landmark_name VARCHAR(200),
    step_count INTEGER,
    original_keywords TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    last_keyword_change TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### keyword_pool 테이블
```sql
CREATE TABLE keyword_pool (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    keyword VARCHAR(255) NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP,
    UNIQUE(campaign_id, keyword)
);
```

## 초기 시딩 데이터

### 템플릿 2개
1. **트래픽** - 플레이스 퀴즈 타입
2. **저장하기** - 검색 후 정답 입력 타입

시딩 실행:
```bash
cd backend
python -c "from app.seed import init_db; init_db()"
```

## 테스트 결과

### 테스트 목록 (20개)
```
tests/test_health.py (2개 - 기존)
├── test_health_check
└── test_root_endpoint

tests/test_models.py (12개)
├── TestAccountModel
│   ├── test_create_account
│   ├── test_account_user_id_unique
│   └── test_account_repr
├── TestCampaignTemplateModel
│   ├── test_create_template
│   └── test_template_type_name_unique
├── TestCampaignModel
│   ├── test_create_campaign
│   └── test_campaign_with_optional_fields
└── TestKeywordPoolModel
    ├── test_create_keyword
    ├── test_keyword_used_at
    └── test_keyword_unique_constraint

tests/test_relationships.py (6개)
├── TestAccountCampaignRelationship
│   ├── test_account_has_campaigns
│   ├── test_campaign_has_account
│   └── test_campaign_without_account
├── TestCampaignKeywordRelationship
│   ├── test_campaign_has_keywords
│   ├── test_keyword_has_campaign
│   └── test_cascade_delete_keywords
└── TestComplexRelationship
    ├── test_full_hierarchy
    └── test_multiple_accounts_campaigns_keywords
```

### 실행 결과
```
3회 연속 테스트 통과
20 passed in ~0.40s
```

## 점검 시 확인해야 할 항목

### 1. 테이블 생성 확인
```bash
cd backend
python -c "from app.seed import create_tables; create_tables()"
sqlite3 ../data/quantum.db ".tables"
# 기대 결과: accounts campaign_templates campaigns keyword_pool
```

### 2. 시딩 데이터 확인
```bash
sqlite3 ../data/quantum.db "SELECT type_name FROM campaign_templates"
# 기대 결과:
# 트래픽
# 저장하기
```

### 3. CRUD 테스트
```bash
cd backend
python -m pytest tests/test_models.py -v
# 기대 결과: 12 passed
```

### 4. 관계 테스트
```bash
cd backend
python -m pytest tests/test_relationships.py -v
# 기대 결과: 6 passed
```

### 5. 전체 테스트
```bash
cd backend
python -m pytest tests/ -v
# 기대 결과: 20 passed
```

## 알려진 이슈
- 없음

## Git 커밋
- 커밋 해시: 243d881
- 메시지: feat(phase1-task2): DB 스키마 구현 완료

## 다음 Task 준비사항
- Task 1.3: superap.io 계정 판별 테스트
- Playwright 설치 필요: `playwright install chromium`
- superap.io 테스트 계정 2개 준비 필요
