"""캠페인 등록 서비스 - 모듈 시스템과 템플릿 연동.

Phase 3 - Task 3.3: 캠페인 등록 전체 플로우 완성
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.models.template import CampaignTemplate
from app.modules.registry import ModuleRegistry
from app.services.superap import (
    CampaignFormData,
    CampaignFormResult,
    SuperapController,
    SuperapCampaignError,
)
from app.services.campaign_extension import extract_place_id
from app.utils.template_vars import apply_template_variables


@dataclass
class CampaignRegistrationData:
    """캠페인 등록 입력 데이터."""

    # 필수 필드
    place_name: str
    place_url: str
    campaign_type: str  # '트래픽', '저장하기' 등 (템플릿 type_name)
    keywords: List[str]  # 키워드 풀
    start_date: date
    end_date: date

    # 선택 필드
    agency_name: Optional[str] = None
    daily_limit: int = 300
    total_limit: Optional[int] = None  # None이면 자동 계산

    def __post_init__(self):
        # total_limit 자동 계산
        if self.total_limit is None and self.start_date and self.end_date:
            days = (self.end_date - self.start_date).days + 1
            self.total_limit = days * self.daily_limit


@dataclass
class CampaignRegistrationResult:
    """캠페인 등록 결과."""

    success: bool
    campaign_code: Optional[str] = None
    campaign_id: Optional[int] = None
    error_message: Optional[str] = None

    # 디버깅용 정보
    module_context: Dict[str, Any] = field(default_factory=dict)
    form_result: Optional[CampaignFormResult] = None
    screenshot_path: Optional[str] = None


class CampaignRegistrationError(Exception):
    """캠페인 등록 오류."""

    pass


class CampaignRegistrationService:
    """캠페인 등록 서비스.

    모듈 시스템 + 템플릿을 활용한 캠페인 등록 전체 플로우를 처리합니다.

    플로우:
    1. 템플릿 조회
    2. 모듈 실행 (템플릿에 정의된 모듈만)
    3. 템플릿 변수 치환
    4. superap 폼 입력
    5. 등록 버튼 클릭
    6. 캠페인 번호 추출
    7. DB 저장
    """

    def __init__(
        self,
        superap_controller: SuperapController,
        db: Session,
    ):
        self.superap = superap_controller
        self.db = db

    async def register_campaign(
        self,
        account_id: str,
        data: CampaignRegistrationData,
        db_account_id: int,
        dry_run: bool = False,
    ) -> CampaignRegistrationResult:
        """캠페인 등록 전체 플로우 실행.

        Args:
            account_id: superap 계정 식별자 (로그인용)
            data: 캠페인 등록 데이터
            db_account_id: DB Account.id
            dry_run: True면 폼 입력까지만 (등록 버튼 클릭 안 함)

        Returns:
            등록 결과
        """
        result = CampaignRegistrationResult(success=False)

        try:
            # 1. 템플릿 조회
            template = self._get_template(data.campaign_type)
            if not template:
                result.error_message = f"템플릿을 찾을 수 없습니다: {data.campaign_type}"
                return result

            # 2. 모듈 실행
            module_ids = template.modules or []
            initial_context = {
                "place_url": data.place_url,
                "place_name": data.place_name,
            }

            context = await ModuleRegistry.execute_modules(
                module_ids=module_ids,
                initial_context=initial_context,
            )
            result.module_context = context

            # 플레이스 URL에서 추출한 실제 상호명 사용
            real_place_name = context.get("real_place_name")

            # 모듈에서 real_place_name을 못 얻었고 place_name도 비어있으면 별도 추출
            if not real_place_name and not data.place_name:
                try:
                    from app.services.naver_map import NaverMapScraper
                    async with NaverMapScraper(headless=True) as scraper:
                        place_info = await scraper.get_place_info(data.place_url)
                        if place_info.name:
                            real_place_name = place_info.name
                            context["real_place_name"] = real_place_name
                except Exception:
                    pass

            if real_place_name and real_place_name != data.place_name:
                data.place_name = real_place_name
                context["place_name"] = real_place_name

            # 3. 템플릿 변수 치환 (상호명 마스킹 적용)
            # 상호명 마스킹: 2글자마다 X로 교체
            masked_place_name = self._mask_place_name(data.place_name)
            context_for_template = context.copy()
            context_for_template["place_name"] = masked_place_name

            description = apply_template_variables(
                template.description_template,
                context_for_template,
            )
            hint = apply_template_variables(
                template.hint_text,
                context,
            )

            # 4. superap 폼 데이터 준비
            # 캠페인 타입: 템플릿의 campaign_type_selection 사용
            superap_campaign_type = template.campaign_type_selection or "플레이스 퀴즈"

            # 캠페인 이름 생성
            campaign_name = self._generate_campaign_name(
                data.place_name,
                superap_campaign_type,
            )

            # 전환 인식 기준: 텍스트 템플릿이 있으면 텍스트, 없으면 걸음수
            conversion_text = None
            if template.conversion_text_template:
                conversion_text = apply_template_variables(
                    template.conversion_text_template, context
                )

            form_data = CampaignFormData(
                campaign_name=campaign_name,
                place_name=data.place_name,
                landmark_name=context.get("landmark_name", ""),
                participation_guide=description,
                keywords=data.keywords,
                hint=hint,
                walking_steps=context.get("steps", 0),
                conversion_text=conversion_text,
                start_date=data.start_date,
                end_date=data.end_date,
                daily_limit=data.daily_limit,
                total_limit=data.total_limit,
                links=template.links or [],
                campaign_type=superap_campaign_type,
            )

            # 5. 폼 입력
            form_result = await self.superap.fill_campaign_form(
                account_id=account_id,
                form_data=form_data,
                take_screenshot=True,
            )
            result.form_result = form_result
            result.screenshot_path = form_result.screenshot_path

            if not form_result.success:
                result.error_message = f"폼 입력 실패: {', '.join(form_result.errors)}"
                return result

            # dry_run이면 여기서 종료
            if dry_run:
                result.success = True
                result.error_message = "dry_run 모드: 폼 입력까지만 완료"
                return result

            # 6. 등록 버튼 클릭 + 캠페인 코드 캡처
            submit_result = await self.superap.submit_campaign(
                account_id, campaign_name=campaign_name,
            )
            if not submit_result.success:
                result.error_message = f"캠페인 제출 실패: {submit_result.error_message}"
                return result

            # 7. 캠페인 번호 추출
            campaign_code = submit_result.campaign_code
            if not campaign_code:
                campaign_code = await self.superap.extract_campaign_code(
                    account_id, campaign_name=campaign_name,
                )
            result.campaign_code = campaign_code

            # 8. DB 저장
            campaign = self._save_campaign_to_db(
                data=data,
                context=context,
                campaign_code=campaign_code,
                db_account_id=db_account_id,
                processed_keywords=form_data.processed_keywords,
            )
            result.campaign_id = campaign.id

            result.success = True
            return result

        except SuperapCampaignError as e:
            result.error_message = f"Superap 오류: {str(e)}"
            return result
        except Exception as e:
            result.error_message = f"예기치 않은 오류: {str(e)}"
            return result

    def _get_template(self, campaign_type: str) -> Optional[CampaignTemplate]:
        """캠페인 타입에 해당하는 템플릿 조회."""
        return self.db.query(CampaignTemplate).filter(
            CampaignTemplate.type_name == campaign_type,
            CampaignTemplate.is_active == True,
        ).first()

    def _generate_campaign_name(
        self,
        place_name: str,
        campaign_type: str,
    ) -> str:
        """캠페인 이름 생성.

        규칙:
        - "점"으로 끝나는 지점명이 있으면: "{브랜드prefix} {지점prefix} 퀴즈 맞추기"
          - 브랜드 2글자 → 1글자, 그 외 → min(2, len)
          - 지점: "점" 제거 후 앞 2글자
        - "점"이 없으면: 기존 방식 (전체 앞 2글자)
        - 저장하기 타입: "저장 퀴즈 맞추기"
        """
        save_keywords = ["저장", "save", "place_save"]
        is_save = any(kw in campaign_type.lower() for kw in save_keywords)
        suffix = "저장 퀴즈 맞추기" if is_save else "퀴즈 맞추기"

        parts = place_name.strip().split()

        # 마지막 단어가 "점"으로 끝나고, 2개 이상의 단어가 있는 경우
        if len(parts) >= 2 and parts[-1].endswith("점"):
            brand_part = " ".join(parts[:-1])
            branch_word = parts[-1][:-1]  # "점" 제거

            brand_chars = [c for c in brand_part if c != " "]
            if len(brand_chars) == 2:
                brand_prefix = brand_chars[0]
            elif len(brand_chars) <= 1:
                brand_prefix = brand_chars[0] if brand_chars else ""
            else:
                brand_prefix = "".join(brand_chars[:2])

            branch_prefix = branch_word[:2] if branch_word else ""

            if brand_prefix and branch_prefix:
                return f"{brand_prefix} {branch_prefix} {suffix}"

        # 폴백: 공백 제외 앞 2글자
        name_chars = [c for c in place_name if c != " "]
        if len(name_chars) <= 2:
            prefix = name_chars[0] if name_chars else ""
        else:
            prefix = "".join(name_chars[:2])

        return f"{prefix} {suffix}"

    def _mask_place_name(self, name: str) -> str:
        """상호명 2글자마다 X로 마스킹.

        예: "일류곱창 마포공덕본점" → "일X곱X 마X공X본X"
        """
        if not name:
            return name
        result = []
        char_count = 0
        for char in name:
            if char == ' ':
                result.append(char)
            else:
                char_count += 1
                if char_count % 2 == 0:
                    result.append('X')
                else:
                    result.append(char)
        return ''.join(result)

    def _save_campaign_to_db(
        self,
        data: CampaignRegistrationData,
        context: Dict[str, Any],
        campaign_code: str,
        db_account_id: int,
        processed_keywords: str = "",
    ) -> Campaign:
        """캠페인 및 키워드 풀을 DB에 저장.

        processed_keywords: superap.io에 실제로 세팅된 키워드 문자열 (255자 이내)
        """
        # Campaign 저장
        place_id = extract_place_id(data.place_url)
        now = datetime.now(timezone.utc)

        # 실제 세팅된 키워드 목록 파싱
        used_keyword_set = set()
        if processed_keywords:
            used_keyword_set = {kw.strip() for kw in processed_keywords.split(",") if kw.strip()}

        campaign = Campaign(
            campaign_code=campaign_code,
            account_id=db_account_id,
            agency_name=data.agency_name,
            place_name=data.place_name,
            place_url=data.place_url,
            place_id=place_id,
            campaign_type=data.campaign_type,
            registered_at=now,
            start_date=data.start_date,
            end_date=data.end_date,
            daily_limit=data.daily_limit,
            total_limit=data.total_limit,
            landmark_name=context.get("landmark_name"),
            step_count=context.get("steps"),
            original_keywords=", ".join(data.keywords),
            status="active",
            last_keyword_change=now if used_keyword_set else None,
        )
        self.db.add(campaign)
        self.db.flush()  # campaign.id 확보

        # KeywordPool 저장 (실제 세팅된 것은 is_used=True)
        for keyword in data.keywords:
            keyword = keyword.strip()
            if keyword:
                is_used = keyword in used_keyword_set
                kw = KeywordPool(
                    campaign_id=campaign.id,
                    keyword=keyword,
                    is_used=is_used,
                    used_at=now if is_used else None,
                )
                self.db.add(kw)

        self.db.commit()
        self.db.refresh(campaign)

        return campaign


async def register_campaign(
    superap_controller: SuperapController,
    db: Session,
    account_id: str,
    data: CampaignRegistrationData,
    db_account_id: int,
    dry_run: bool = False,
) -> CampaignRegistrationResult:
    """캠페인 등록 함수 (편의 함수).

    CampaignRegistrationService를 사용하여 캠페인을 등록합니다.
    """
    service = CampaignRegistrationService(superap_controller, db)
    return await service.register_campaign(
        account_id=account_id,
        data=data,
        db_account_id=db_account_id,
        dry_run=dry_run,
    )
