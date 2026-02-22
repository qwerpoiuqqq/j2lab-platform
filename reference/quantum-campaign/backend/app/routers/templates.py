"""템플릿 관리 API 라우터."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.campaign import Campaign
from app.models.template import CampaignTemplate
from app.modules.registry import ModuleRegistry


router = APIRouter(prefix="/templates", tags=["templates"])


# Pydantic 스키마 정의
class ModuleInfo(BaseModel):
    """모듈 정보."""

    module_id: str
    description: str
    output_variables: List[str]
    dependencies: List[str]


class TemplateListItem(BaseModel):
    """템플릿 목록 아이템."""

    id: int
    type_name: str
    campaign_type_selection: Optional[str]
    modules: List[str]
    module_descriptions: List[str]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TemplateDetail(BaseModel):
    """템플릿 상세 정보."""

    id: int
    type_name: str
    description_template: str
    hint_text: str
    campaign_type_selection: Optional[str]
    links: List[str]
    hashtag: Optional[str]
    image_url_200x600: Optional[str]
    image_url_720x780: Optional[str]
    conversion_text_template: Optional[str]
    steps_start: Optional[str]
    modules: List[str]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TemplateCreate(BaseModel):
    """템플릿 생성 요청."""

    type_name: str = Field(..., min_length=1, max_length=50)
    description_template: str
    hint_text: str
    campaign_type_selection: Optional[str] = None
    links: List[str] = Field(default_factory=list)
    hashtag: Optional[str] = None
    image_url_200x600: Optional[str] = None
    image_url_720x780: Optional[str] = None
    conversion_text_template: Optional[str] = None
    steps_start: Optional[str] = None
    modules: List[str] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    """템플릿 수정 요청."""

    type_name: Optional[str] = Field(None, min_length=1, max_length=50)
    description_template: Optional[str] = None
    hint_text: Optional[str] = None
    campaign_type_selection: Optional[str] = None
    links: Optional[List[str]] = None
    hashtag: Optional[str] = None
    image_url_200x600: Optional[str] = None
    image_url_720x780: Optional[str] = None
    conversion_text_template: Optional[str] = None
    steps_start: Optional[str] = None
    modules: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TemplateListResponse(BaseModel):
    """템플릿 목록 응답."""

    templates: List[TemplateListItem]
    total: int


class TemplateDeleteResponse(BaseModel):
    """템플릿 삭제 응답."""

    message: str


class ModuleListResponse(BaseModel):
    """모듈 목록 응답."""

    modules: List[ModuleInfo]
    total: int


def _get_module_descriptions(module_ids: List[str]) -> List[str]:
    """모듈 ID 목록에서 설명 목록 반환."""
    descriptions = []
    for module_id in module_ids:
        module = ModuleRegistry.get(module_id)
        if module:
            descriptions.append(module.description)
        else:
            descriptions.append(f"Unknown module: {module_id}")
    return descriptions


def _to_detail(template: CampaignTemplate) -> TemplateDetail:
    """CampaignTemplate DB 모델을 TemplateDetail 응답으로 변환."""
    return TemplateDetail(
        id=template.id,
        type_name=template.type_name,
        description_template=template.description_template,
        hint_text=template.hint_text,
        campaign_type_selection=template.campaign_type_selection,
        links=template.links or [],
        hashtag=template.hashtag,
        image_url_200x600=template.image_url_200x600,
        image_url_720x780=template.image_url_720x780,
        conversion_text_template=template.conversion_text_template,
        steps_start=template.steps_start,
        modules=template.modules or [],
        is_active=template.is_active if template.is_active is not None else True,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """템플릿 목록 조회."""
    query = db.query(CampaignTemplate)

    if is_active is not None:
        query = query.filter(CampaignTemplate.is_active == is_active)

    templates = query.order_by(CampaignTemplate.id).all()

    items = []
    for template in templates:
        modules = template.modules or []
        items.append(
            TemplateListItem(
                id=template.id,
                type_name=template.type_name,
                campaign_type_selection=template.campaign_type_selection,
                modules=modules,
                module_descriptions=_get_module_descriptions(modules),
                is_active=template.is_active if template.is_active is not None else True,
                created_at=template.created_at,
                updated_at=template.updated_at,
            )
        )

    return TemplateListResponse(templates=items, total=len(items))


@router.get("/{template_id}", response_model=TemplateDetail)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
):
    """템플릿 상세 조회."""
    template = db.query(CampaignTemplate).filter(
        CampaignTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    return _to_detail(template)


@router.post("", response_model=TemplateDetail, status_code=201)
async def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
):
    """템플릿 생성."""
    existing = db.query(CampaignTemplate).filter(
        CampaignTemplate.type_name == data.type_name
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"'{data.type_name}' 이름의 템플릿이 이미 존재합니다"
        )

    for module_id in data.modules:
        if not ModuleRegistry.get(module_id):
            raise HTTPException(
                status_code=400,
                detail=f"등록되지 않은 모듈입니다: {module_id}"
            )

    template = CampaignTemplate(
        type_name=data.type_name,
        description_template=data.description_template,
        hint_text=data.hint_text,
        campaign_type_selection=data.campaign_type_selection,
        links=data.links,
        hashtag=data.hashtag,
        image_url_200x600=data.image_url_200x600,
        image_url_720x780=data.image_url_720x780,
        conversion_text_template=data.conversion_text_template,
        steps_start=data.steps_start,
        modules=data.modules,
        is_active=True,
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return _to_detail(template)


@router.put("/{template_id}", response_model=TemplateDetail)
async def update_template(
    template_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
):
    """템플릿 수정."""
    template = db.query(CampaignTemplate).filter(
        CampaignTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    if data.type_name and data.type_name != template.type_name:
        existing = db.query(CampaignTemplate).filter(
            CampaignTemplate.type_name == data.type_name,
            CampaignTemplate.id != template_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"'{data.type_name}' 이름의 템플릿이 이미 존재합니다"
            )

    if data.modules is not None:
        for module_id in data.modules:
            if not ModuleRegistry.get(module_id):
                raise HTTPException(
                    status_code=400,
                    detail=f"등록되지 않은 모듈입니다: {module_id}"
                )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)

    return _to_detail(template)


@router.delete("/{template_id}", response_model=TemplateDeleteResponse)
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
):
    """템플릿 삭제."""
    template = db.query(CampaignTemplate).filter(
        CampaignTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    # 해당 템플릿을 사용 중인 활성 캠페인 확인
    active_count = db.query(Campaign).filter(
        Campaign.campaign_type == template.type_name,
        Campaign.status.in_(["active", "pending"]),
    ).count()

    if active_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"이 템플릿을 사용 중인 활성 캠페인이 {active_count}개 있습니다. "
                   f"먼저 해당 캠페인을 비활성화하거나 삭제해주세요."
        )

    name = template.type_name
    db.delete(template)
    db.commit()

    return TemplateDeleteResponse(message=f"템플릿 '{name}'이(가) 삭제되었습니다.")


# 모듈 API는 별도 prefix로 분리
modules_router = APIRouter(prefix="/modules", tags=["modules"])


@modules_router.get("", response_model=ModuleListResponse)
async def list_modules():
    """사용 가능한 모듈 목록 조회."""
    modules_info = ModuleRegistry.get_all_info()

    modules = [
        ModuleInfo(
            module_id=info["module_id"],
            description=info["description"],
            output_variables=info["output_variables"],
            dependencies=info["dependencies"],
        )
        for info in modules_info
    ]

    return ModuleListResponse(modules=modules, total=len(modules))
