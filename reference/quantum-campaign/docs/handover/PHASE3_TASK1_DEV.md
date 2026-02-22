# Phase 3 - Task 3.1: 모듈 시스템 구현

## 완료 일자
2026-02-04

## 구현 내용

### 1. 모듈 시스템 구조

```
backend/app/modules/
├── __init__.py      # 패키지 초기화 및 exports
├── base.py          # BaseModule 추상 클래스
├── landmark.py      # LandmarkModule - 명소 추출
├── steps.py         # StepsModule - 걸음수 계산
└── registry.py      # ModuleRegistry - 모듈 등록/실행 관리
```

### 2. BaseModule 추상 클래스 (`base.py`)

```python
class BaseModule(ABC):
    module_id: str        # 모듈 고유 ID
    description: str      # 모듈 설명 (UI 표시용)
    output_variables: List[str]  # 반환하는 변수명 목록
    dependencies: List[str]      # 의존하는 다른 모듈 ID

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def get_info(self) -> Dict[str, Any]:
        # 모듈 메타데이터 반환

    def validate_context(self, context, required_keys):
        # 필수 키 검증
```

### 3. LandmarkModule (`landmark.py`)

- **module_id**: `landmark`
- **description**: "플레이스 주변 명소 1~3위 중 랜덤 추출"
- **output_variables**: `["landmark_name", "landmark_id"]`
- **dependencies**: `[]` (없음)

**Input**:
- `place_url`: 플레이스 URL (필수)

**Output**:
- `landmark_name`: 선택된 명소 이름
- `landmark_id`: 선택된 명소의 place_id

### 4. StepsModule (`steps.py`)

- **module_id**: `steps`
- **description**: "명소→업체 도보 걸음수 계산"
- **output_variables**: `["steps"]`
- **dependencies**: `["landmark"]` (landmark 모듈에 의존)

**Input**:
- `landmark_name`: 출발지 명소 이름 (landmark 모듈에서 제공)
- `place_name`: 도착지 플레이스 상호명

**Output**:
- `steps`: 도보 걸음수 (정수)

### 5. ModuleRegistry (`registry.py`)

```python
class ModuleRegistry:
    @classmethod
    def register(cls, module: BaseModule) -> None

    @classmethod
    def unregister(cls, module_id: str) -> None

    @classmethod
    def get(cls, module_id: str) -> Optional[BaseModule]

    @classmethod
    def get_all(cls) -> List[BaseModule]

    @classmethod
    def get_all_info(cls) -> List[Dict[str, Any]]

    @classmethod
    async def execute_modules(
        cls,
        module_ids: List[str],
        initial_context: Dict[str, Any]
    ) -> Dict[str, Any]
```

**주요 기능**:
- 의존성 순서대로 모듈 자동 정렬 (위상 정렬)
- 순환 의존성 감지
- 컨텍스트 누적 전달

### 6. 사용 예시

```python
from app.modules import ModuleRegistry
from app.modules.registry import register_default_modules

# 기본 모듈 등록
register_default_modules()

# 트래픽 템플릿: landmark + steps 모듈 사용
context = await ModuleRegistry.execute_modules(
    module_ids=["landmark", "steps"],
    initial_context={
        "place_url": "https://m.place.naver.com/restaurant/1724563569",
        "place_name": "일류곱창 마포공덕본점",
    }
)

# 결과:
# {
#     "place_url": "...",
#     "place_name": "일류곱창 마포공덕본점",
#     "landmark_name": "마포역 2번출구",
#     "landmark_id": "12345",
#     "steps": 863,
# }

# 블로그 템플릿: 모듈 없음
context = await ModuleRegistry.execute_modules(
    module_ids=[],
    initial_context={...}
)
```

## 테스트 결과

### 모듈 테스트 (3회 연속 성공)

```
tests/test_modules.py - 31 passed
- TestBaseModule: 5 tests
- TestLandmarkModule: 5 tests
- TestStepsModule: 5 tests
- TestModuleRegistry: 12 tests
- TestRegisterDefaultModules: 2 tests
- TestModulesIntegration: 2 tests
```

### 테스트 커버리지

- BaseModule 추상 클래스 및 유틸리티 메서드
- LandmarkModule 실행 (성공/실패 케이스)
- StepsModule 실행 (성공/실패 케이스)
- ModuleRegistry 등록/조회/실행
- 의존성 정렬 알고리즘
- 통합 테스트 (모킹 기반)

## 파일 목록

### 새로 생성된 파일
- `backend/app/modules/__init__.py`
- `backend/app/modules/base.py`
- `backend/app/modules/landmark.py`
- `backend/app/modules/steps.py`
- `backend/app/modules/registry.py`
- `backend/tests/test_modules.py`
- `docs/handover/PHASE3_TASK1_DEV.md`

### 수정된 파일
- 없음 (기존 NaverMapScraper 유지)

## 다음 Task (3.2) 준비사항

### Task 3.2: 템플릿 관리 기능

1. **DB 스키마 수정**
   - `campaign_templates` 테이블에 `modules` JSON 필드 추가
   - 활성화 여부 `is_active` 필드 추가

2. **API 엔드포인트 구현**
   - `GET /templates` - 템플릿 목록
   - `GET /templates/{id}` - 템플릿 상세
   - `POST /templates` - 템플릿 추가
   - `PUT /templates/{id}` - 템플릿 수정
   - `GET /modules` - 사용 가능한 모듈 목록

3. **변수 치환 로직**
   - `&명소명&`, `&상호명&`, `&걸음수&` 등 변수 치환 함수

## 알려진 이슈

### 기존 naver_map 테스트 실패 (4건)
- `test_get_nearby_landmarks_no_list`
- `test_filter_ad_links`
- `test_get_walking_steps_success`
- `test_get_walking_steps_with_comma`

**원인**: 모킹 관련 문제 (MagicMock/AsyncMock 호환성)
**영향**: 새로운 모듈 시스템과 무관, 기존 Phase 2에서 발생한 문제
**권장**: Phase 3.2 이후 별도 세션에서 수정

## 참고사항

- 기존 `NaverMapScraper`는 변경 없이 유지
- 모듈에서 `NaverMapScraper`를 호출하는 방식으로 구현
- 모듈 시스템은 확장 가능하도록 설계됨 (새 모듈 추가 용이)
