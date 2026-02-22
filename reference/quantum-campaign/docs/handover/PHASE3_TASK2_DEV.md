# Phase 3 - Task 3.2: 템플릿 관리 기능

## 완료 일자
2026-02-04

## 구현 내용

### 1. DB 스키마 수정 (`models/template.py`)

기존 `CampaignTemplate` 모델에 새로운 필드 추가:

```python
# 신규 필드
modules = Column(JSON, default=list)     # ["landmark", "steps"] 사용할 모듈 ID 목록
is_active = Column(Boolean, default=True) # 활성화 여부
created_at = Column(DateTime, default=...)
```

### 2. 템플릿 API (`routers/templates.py`)

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/templates` | GET | 템플릿 목록 조회 (is_active 필터 지원) |
| `/templates/{id}` | GET | 템플릿 상세 조회 |
| `/templates` | POST | 새 템플릿 생성 |
| `/templates/{id}` | PUT | 템플릿 수정 |

**응답 예시 (GET /templates):**
```json
{
  "templates": [
    {
      "id": 1,
      "type_name": "트래픽",
      "campaign_type_selection": "플레이스 퀴즈",
      "modules": ["landmark", "steps"],
      "module_descriptions": [
        "플레이스 주변 명소 1~3위 중 랜덤 추출",
        "명소→업체 도보 걸음수 계산"
      ],
      "is_active": true,
      "created_at": "2026-02-04T...",
      "updated_at": "2026-02-04T..."
    }
  ],
  "total": 1
}
```

### 3. 모듈 목록 API (`routers/templates.py`)

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/modules` | GET | 사용 가능한 모듈 목록 조회 |

**응답 예시 (GET /modules):**
```json
{
  "modules": [
    {
      "module_id": "landmark",
      "description": "플레이스 주변 명소 1~3위 중 랜덤 추출",
      "output_variables": ["landmark_name", "landmark_id"],
      "dependencies": []
    },
    {
      "module_id": "steps",
      "description": "명소→업체 도보 걸음수 계산",
      "output_variables": ["steps"],
      "dependencies": ["landmark"]
    }
  ],
  "total": 2
}
```

### 4. 변수 치환 함수 (`utils/template_vars.py`)

```python
# 주요 함수
apply_template_variables(template_text, context, strict=False) -> str
extract_variables(template_text) -> List[str]
validate_template_variables(template_text, available_variables) -> Tuple[bool, List[str]]
get_available_variables_for_modules(module_ids) -> List[str]
```

**사용 예시:**
```python
context = {
    "landmark_name": "마포역 2번출구",
    "place_name": "일류곱창 마포공덕본점",
    "steps": 863,
}
template = "&명소명&에서 &상호명&까지 &걸음수& 걸음"

result = apply_template_variables(template, context)
# → "마포역 2번출구에서 일류곱창 마포공덕본점까지 863 걸음"
```

**변수 매핑:**
| 한글 변수 | Context 키 |
|-----------|-----------|
| &명소명& | landmark_name |
| &상호명& | place_name |
| &걸음수& | steps |

### 5. 마이그레이션 함수 (`seed.py`)

기존 템플릿에 modules 필드를 추가하는 마이그레이션 함수:

```python
def migrate_templates_add_modules():
    """기존 템플릿에 modules 필드 추가 마이그레이션."""
    # 트래픽, 저장하기 → ["landmark", "steps"]
    # 그 외 → []
```

### 6. 애플리케이션 시작 시 모듈 등록 (`main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 모듈 등록
    register_default_modules()
    yield
```

## 테스트 결과

### 테스트 파일: `tests/test_templates.py`

```
총 34개 테스트 - 3회 연속 통과

TestApplyTemplateVariables: 7 tests
- 기본 치환, 부분 치환, 빈 템플릿, strict 모드 등

TestExtractVariables: 4 tests
- 변수 추출, 중복 제거 등

TestValidateTemplateVariables: 3 tests
- 유효성 검증, 영문 키 매핑 등

TestGetAvailableVariablesForModules: 4 tests
- 모듈별 사용 가능 변수 확인

TestTemplateListAPI: 3 tests
- 목록 조회, 필터링

TestTemplateDetailAPI: 2 tests
- 상세 조회, 404 처리

TestTemplateCreateAPI: 3 tests
- 생성, 중복 이름, 유효하지 않은 모듈

TestTemplateUpdateAPI: 4 tests
- 수정, 부분 수정, 중복 이름 체크

TestModulesAPI: 2 tests
- 모듈 목록 조회

TestTemplateModuleIntegration: 2 tests
- 통합 테스트
```

## 파일 목록

### 새로 생성된 파일
- `backend/app/routers/templates.py`
- `backend/app/utils/template_vars.py`
- `backend/tests/test_templates.py`
- `docs/handover/PHASE3_TASK2_DEV.md`

### 수정된 파일
- `backend/app/models/template.py` - modules, is_active, created_at 필드 추가
- `backend/app/main.py` - 라우터 등록 및 lifespan 이벤트 추가
- `backend/app/routers/__init__.py` - 템플릿/모듈 라우터 export
- `backend/app/utils/__init__.py` - 변수 치환 함수 export
- `backend/app/seed.py` - 템플릿 마이그레이션 함수 및 modules 필드 추가

## API 사용 예시

### 템플릿 생성
```bash
curl -X POST http://localhost:8000/templates \
  -H "Content-Type: application/json" \
  -d '{
    "type_name": "블로그",
    "description_template": "&상호명& 방문하기",
    "hint_text": "블로그 방문 완료",
    "campaign_type_selection": "블로그 방문",
    "links": ["https://blog.naver.com"],
    "hashtag": "#blog",
    "modules": []
  }'
```

### 템플릿 수정 (모듈 변경)
```bash
curl -X PUT http://localhost:8000/templates/1 \
  -H "Content-Type: application/json" \
  -d '{
    "modules": ["landmark", "steps"],
    "is_active": true
  }'
```

### 모듈 목록 조회
```bash
curl http://localhost:8000/modules
```

## 다음 Task (3.3) 준비사항

### Task 3.3: 캠페인 등록 완성 (모듈 연동)

1. **모듈 시스템과 템플릿 연동**
   - 템플릿의 modules 필드를 사용하여 ModuleRegistry.execute_modules() 호출
   - 모듈 실행 결과로 변수 치환

2. **캠페인 등록 플로우 완성**
   - 템플릿 조회 → 모듈 실행 → 변수 치환 → superap 폼 입력 → 등록

3. **submit_campaign() 구현**
   - 등록 버튼 클릭 및 결과 확인

4. **extract_campaign_code() 구현**
   - 등록된 캠페인 번호 추출

## 알려진 이슈

없음

## 참고사항

- 애플리케이션 시작 시 `register_default_modules()`가 자동 호출됨
- 기존 DB가 있는 경우 `migrate_templates_add_modules()` 실행 필요
- Pydantic v2 호환을 위해 `model_config` 사용 (class Config 대신)
