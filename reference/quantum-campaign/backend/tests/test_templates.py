"""템플릿 API 및 변수 치환 테스트."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.template import CampaignTemplate
from app.modules.registry import ModuleRegistry, register_default_modules
from app.utils.template_vars import (
    apply_template_variables,
    extract_variables,
    validate_template_variables,
    get_available_variables_for_modules,
    VARIABLE_MAP,
)


# 테스트용 인메모리 DB 설정
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """테스트용 DB 세션."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    # 모듈 등록
    ModuleRegistry.clear()
    register_default_modules()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """테스트 클라이언트 생성."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_template(db_session):
    """샘플 템플릿 생성."""
    template = CampaignTemplate(
        type_name="테스트",
        description_template="&명소명&에서 &상호명&까지 &걸음수& 걸음",
        hint_text="걸음수 맞추기",
        campaign_type_selection="플레이스 퀴즈",
        links=["https://example.com"],
        hashtag="#test",
        modules=["landmark", "steps"],
        is_active=True,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


# ============================================================
# 변수 치환 함수 테스트
# ============================================================


class TestApplyTemplateVariables:
    """apply_template_variables 함수 테스트."""

    def test_basic_substitution(self):
        """기본 변수 치환 테스트."""
        context = {
            "landmark_name": "마포역 2번출구",
            "place_name": "일류곱창 마포공덕본점",
            "steps": 863,
        }
        template = "&명소명&에서 &상호명&까지 &걸음수& 걸음"

        result = apply_template_variables(template, context)

        assert result == "마포역 2번출구에서 일류곱창 마포공덕본점까지 863 걸음"

    def test_partial_substitution(self):
        """일부 변수만 있는 경우 테스트."""
        context = {
            "landmark_name": "마포역",
        }
        template = "&명소명&에서 &상호명&까지"

        result = apply_template_variables(template, context)

        assert result == "마포역에서 &상호명&까지"

    def test_empty_template(self):
        """빈 템플릿 테스트."""
        result = apply_template_variables("", {"key": "value"})
        assert result == ""

    def test_no_variables(self):
        """변수가 없는 템플릿 테스트."""
        template = "변수가 없는 텍스트"
        result = apply_template_variables(template, {"key": "value"})
        assert result == "변수가 없는 텍스트"

    def test_strict_mode_raises_error(self):
        """strict 모드에서 미치환 변수 에러 테스트."""
        context = {"landmark_name": "마포역"}
        template = "&명소명&에서 &상호명&까지"

        with pytest.raises(ValueError) as exc_info:
            apply_template_variables(template, context, strict=True)

        assert "상호명" in str(exc_info.value)

    def test_integer_value_conversion(self):
        """정수 값 문자열 변환 테스트."""
        context = {"steps": 1000}
        template = "&걸음수& 걸음"

        result = apply_template_variables(template, context)

        assert result == "1000 걸음"

    def test_none_template(self):
        """None 템플릿 테스트."""
        result = apply_template_variables(None, {"key": "value"})
        assert result is None


class TestExtractVariables:
    """extract_variables 함수 테스트."""

    def test_basic_extraction(self):
        """기본 변수 추출 테스트."""
        template = "&명소명&에서 &상호명&까지 &걸음수& 걸음"

        result = extract_variables(template)

        assert result == ["명소명", "상호명", "걸음수"]

    def test_duplicate_variables(self):
        """중복 변수 제거 테스트."""
        template = "&명소명&에서 &명소명&까지"

        result = extract_variables(template)

        assert result == ["명소명"]

    def test_empty_template(self):
        """빈 템플릿 테스트."""
        result = extract_variables("")
        assert result == []

    def test_no_variables(self):
        """변수가 없는 템플릿 테스트."""
        result = extract_variables("변수가 없는 텍스트")
        assert result == []


class TestValidateTemplateVariables:
    """validate_template_variables 함수 테스트."""

    def test_valid_variables(self):
        """유효한 변수 검증 테스트."""
        template = "&명소명&에서 &상호명&까지"
        available = ["명소명", "상호명"]

        is_valid, invalid = validate_template_variables(template, available)

        assert is_valid is True
        assert invalid == []

    def test_invalid_variables(self):
        """유효하지 않은 변수 검증 테스트."""
        template = "&명소명&에서 &알수없음&까지"
        available = ["명소명", "상호명"]

        is_valid, invalid = validate_template_variables(template, available)

        assert is_valid is False
        assert "알수없음" in invalid

    def test_english_key_mapping(self):
        """영문 키 매핑 테스트."""
        template = "&명소명&에서"
        available = ["landmark_name"]  # 영문 키

        is_valid, invalid = validate_template_variables(template, available)

        assert is_valid is True
        assert invalid == []


class TestGetAvailableVariablesForModules:
    """get_available_variables_for_modules 함수 테스트."""

    def test_landmark_module_variables(self):
        """landmark 모듈 변수 테스트."""
        ModuleRegistry.clear()
        register_default_modules()

        result = get_available_variables_for_modules(["landmark"])

        assert "명소명" in result

    def test_steps_module_variables(self):
        """steps 모듈 변수 테스트."""
        ModuleRegistry.clear()
        register_default_modules()

        result = get_available_variables_for_modules(["steps"])

        assert "걸음수" in result

    def test_both_modules_variables(self):
        """landmark + steps 모듈 변수 테스트."""
        ModuleRegistry.clear()
        register_default_modules()

        result = get_available_variables_for_modules(["landmark", "steps"])

        assert "명소명" in result
        assert "걸음수" in result

    def test_always_includes_place_name(self):
        """상호명은 항상 포함 테스트."""
        ModuleRegistry.clear()
        register_default_modules()

        result = get_available_variables_for_modules([])

        assert "상호명" in result


# ============================================================
# 템플릿 API 테스트
# ============================================================


class TestTemplateListAPI:
    """GET /templates API 테스트."""

    def test_list_templates_empty(self, client):
        """빈 목록 조회 테스트."""
        response = client.get("/templates")

        assert response.status_code == 200
        data = response.json()
        assert data["templates"] == []
        assert data["total"] == 0

    def test_list_templates_with_data(self, client, sample_template):
        """데이터가 있는 목록 조회 테스트."""
        response = client.get("/templates")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["templates"][0]["type_name"] == "테스트"
        assert data["templates"][0]["modules"] == ["landmark", "steps"]

    def test_list_templates_filter_active(self, client, db_session):
        """활성화 상태 필터 테스트."""
        # 활성 템플릿
        active = CampaignTemplate(
            type_name="활성",
            description_template="test",
            hint_text="hint",
            links=[],
            is_active=True,
        )
        # 비활성 템플릿
        inactive = CampaignTemplate(
            type_name="비활성",
            description_template="test",
            hint_text="hint",
            links=[],
            is_active=False,
        )
        db_session.add_all([active, inactive])
        db_session.commit()

        # 활성만 조회
        response = client.get("/templates?is_active=true")
        data = response.json()
        assert data["total"] == 1
        assert data["templates"][0]["type_name"] == "활성"

        # 비활성만 조회
        response = client.get("/templates?is_active=false")
        data = response.json()
        assert data["total"] == 1
        assert data["templates"][0]["type_name"] == "비활성"


class TestTemplateDetailAPI:
    """GET /templates/{id} API 테스트."""

    def test_get_template_success(self, client, sample_template):
        """템플릿 상세 조회 성공 테스트."""
        response = client.get(f"/templates/{sample_template.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_template.id
        assert data["type_name"] == "테스트"
        assert data["modules"] == ["landmark", "steps"]

    def test_get_template_not_found(self, client):
        """존재하지 않는 템플릿 조회 테스트."""
        response = client.get("/templates/9999")

        assert response.status_code == 404
        assert "찾을 수 없습니다" in response.json()["detail"]


class TestTemplateCreateAPI:
    """POST /templates API 테스트."""

    def test_create_template_success(self, client):
        """템플릿 생성 성공 테스트."""
        data = {
            "type_name": "새템플릿",
            "description_template": "&명소명& 테스트",
            "hint_text": "힌트",
            "campaign_type_selection": "퀴즈",
            "links": ["https://example.com"],
            "hashtag": "#test",
            "modules": ["landmark"],
        }

        response = client.post("/templates", json=data)

        assert response.status_code == 201
        result = response.json()
        assert result["type_name"] == "새템플릿"
        assert result["modules"] == ["landmark"]
        assert result["is_active"] is True

    def test_create_template_duplicate_name(self, client, sample_template):
        """중복 이름 템플릿 생성 실패 테스트."""
        data = {
            "type_name": "테스트",  # 이미 존재하는 이름
            "description_template": "test",
            "hint_text": "hint",
            "links": [],
        }

        response = client.post("/templates", json=data)

        assert response.status_code == 400
        assert "이미 존재합니다" in response.json()["detail"]

    def test_create_template_invalid_module(self, client):
        """유효하지 않은 모듈로 생성 실패 테스트."""
        data = {
            "type_name": "새템플릿",
            "description_template": "test",
            "hint_text": "hint",
            "links": [],
            "modules": ["invalid_module"],
        }

        response = client.post("/templates", json=data)

        assert response.status_code == 400
        assert "등록되지 않은 모듈" in response.json()["detail"]


class TestTemplateUpdateAPI:
    """PUT /templates/{id} API 테스트."""

    def test_update_template_success(self, client, sample_template):
        """템플릿 수정 성공 테스트."""
        data = {
            "type_name": "수정된템플릿",
            "modules": ["landmark"],
        }

        response = client.put(f"/templates/{sample_template.id}", json=data)

        assert response.status_code == 200
        result = response.json()
        assert result["type_name"] == "수정된템플릿"
        assert result["modules"] == ["landmark"]

    def test_update_template_not_found(self, client):
        """존재하지 않는 템플릿 수정 테스트."""
        response = client.put("/templates/9999", json={"type_name": "test"})

        assert response.status_code == 404

    def test_update_template_duplicate_name(self, client, db_session):
        """중복 이름으로 수정 실패 테스트."""
        # 두 개의 템플릿 생성
        t1 = CampaignTemplate(
            type_name="템플릿1",
            description_template="test",
            hint_text="hint",
            links=[],
        )
        t2 = CampaignTemplate(
            type_name="템플릿2",
            description_template="test",
            hint_text="hint",
            links=[],
        )
        db_session.add_all([t1, t2])
        db_session.commit()

        # t2의 이름을 t1과 같게 변경 시도
        response = client.put(f"/templates/{t2.id}", json={"type_name": "템플릿1"})

        assert response.status_code == 400
        assert "이미 존재합니다" in response.json()["detail"]

    def test_update_template_partial(self, client, sample_template):
        """부분 수정 테스트."""
        data = {"is_active": False}

        response = client.put(f"/templates/{sample_template.id}", json=data)

        assert response.status_code == 200
        result = response.json()
        assert result["is_active"] is False
        assert result["type_name"] == "테스트"  # 변경 안됨


# ============================================================
# 모듈 API 테스트
# ============================================================


class TestModulesAPI:
    """GET /modules API 테스트."""

    def test_list_modules(self, client):
        """모듈 목록 조회 테스트."""
        response = client.get("/modules")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2  # landmark, steps

        module_ids = [m["module_id"] for m in data["modules"]]
        assert "landmark" in module_ids
        assert "steps" in module_ids

    def test_modules_have_required_fields(self, client):
        """모듈 정보 필수 필드 테스트."""
        response = client.get("/modules")
        data = response.json()

        for module in data["modules"]:
            assert "module_id" in module
            assert "description" in module
            assert "output_variables" in module
            assert "dependencies" in module


# ============================================================
# 통합 테스트
# ============================================================


class TestTemplateModuleIntegration:
    """템플릿과 모듈 통합 테스트."""

    def test_template_with_module_execution(self, client, db_session):
        """템플릿 모듈 정보와 변수 치환 통합 테스트."""
        # 템플릿 생성
        template = CampaignTemplate(
            type_name="통합테스트",
            description_template="&명소명&에서 &상호명&까지 &걸음수& 걸음",
            hint_text="걸음수 맞추기",
            links=[],
            modules=["landmark", "steps"],
        )
        db_session.add(template)
        db_session.commit()

        # 템플릿 조회
        response = client.get(f"/templates/{template.id}")
        assert response.status_code == 200
        data = response.json()

        # 모듈 정보 확인
        assert data["modules"] == ["landmark", "steps"]

        # 변수 치환 테스트
        context = {
            "landmark_name": "강남역",
            "place_name": "카페",
            "steps": 500,
        }
        result = apply_template_variables(data["description_template"], context)
        assert result == "강남역에서 카페까지 500 걸음"

    def test_create_and_validate_template(self, client):
        """템플릿 생성 후 변수 검증 통합 테스트."""
        # 템플릿 생성
        data = {
            "type_name": "검증테스트",
            "description_template": "&명소명&에서 &상호명&까지",
            "hint_text": "힌트",
            "links": [],
            "modules": ["landmark"],
        }
        response = client.post("/templates", json=data)
        assert response.status_code == 201

        template_data = response.json()

        # 해당 모듈로 사용 가능한 변수 확인
        available = get_available_variables_for_modules(template_data["modules"])
        assert "명소명" in available
        assert "상호명" in available  # 기본 제공

        # 템플릿 변수 검증
        is_valid, invalid = validate_template_variables(
            template_data["description_template"],
            available,
        )
        assert is_valid is True
