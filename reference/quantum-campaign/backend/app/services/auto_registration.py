"""자동 등록 서비스 - 업로드 확정 후 superap.io에 자동 등록.

엑셀 업로드 confirm 후 pending 상태 캠페인을 superap.io에 실제 등록하는
백그라운드 태스크. 각 단계마다 registration_step을 DB에 업데이트하여
프론트엔드에서 실시간 진행 현황을 폴링할 수 있도록 합니다.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError

from app.database import SessionLocal
from app.models.account import Account
from app.models.campaign import Campaign
from app.models.keyword import KeywordPool
from app.models.template import CampaignTemplate
from app.modules.registry import ModuleRegistry
from app.services.superap import (
    CampaignFormData,
    SuperapController,
    SuperapCampaignError,
    SuperapLoginError,
)
from app.utils.encryption import decrypt_password
from app.utils.template_vars import apply_template_variables

logger = logging.getLogger(__name__)

# 동시 실행 방지 락
_registration_lock = asyncio.Lock()


def _safe_update_step(
    db: Session,
    campaign: Campaign,
    step: str,
    message: str = "",
) -> bool:
    """등록 단계 업데이트 후 즉시 커밋 (프론트 폴링용).

    삭제된 캠페인이나 세션 오류 시 False를 반환합니다.
    """
    try:
        # 세션에 pending rollback이 있으면 롤백 먼저
        if not db.is_active:
            db.rollback()
        campaign.registration_step = step
        campaign.registration_message = message
        campaign.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except (ObjectDeletedError, InvalidRequestError) as e:
        logger.warning(f"[자동등록] DB 업데이트 실패 (캠페인 삭제됨?): {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False
    except Exception as e:
        logger.warning(f"[자동등록] DB 업데이트 실패: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False



def _mask_place_name(name: str) -> str:
    """상호명 2글자마다 X로 마스킹."""
    if not name:
        return name
    result = []
    char_count = 0
    for char in name:
        if char == " ":
            result.append(char)
        else:
            char_count += 1
            if char_count % 2 == 0:
                result.append("X")
            else:
                result.append(char)
    return "".join(result)


def _generate_campaign_name(place_name: str, campaign_type: str) -> str:
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


async def register_single_campaign(
    controller: SuperapController,
    db: Session,
    campaign: Campaign,
    account: Account,
) -> bool:
    """단일 캠페인을 superap.io에 등록.

    기존 DB 레코드를 업데이트하며, 각 단계마다 registration_step을 갱신합니다.

    Returns:
        True: 등록 성공, False: 실패
    """
    account_key = str(account.id)

    try:
        # Step 1: 로그인
        if not _safe_update_step(db, campaign, "logging_in", "superap.io 로그인 중..."):
            return False

        password = decrypt_password(account.password_encrypted)
        login_ok = await controller.login(account_key, account.user_id, password)
        if not login_ok:
            _safe_update_step(db, campaign, "failed", f"로그인 실패: 계정 {account.user_id}")
            return False

        # Step 2: 모듈 실행 (명소/걸음수 추출)
        if not _safe_update_step(db, campaign, "running_modules", "모듈 실행 중 (명소/걸음수 추출)..."):
            return False

        template = (
            db.query(CampaignTemplate)
            .filter(
                CampaignTemplate.type_name == campaign.campaign_type,
                CampaignTemplate.is_active == True,
            )
            .first()
        )
        if not template:
            _safe_update_step(
                db, campaign, "failed",
                f"템플릿을 찾을 수 없습니다: {campaign.campaign_type}",
            )
            return False

        # 모듈 개별 실행 (한 모듈 실패 시에도 나머지 진행)
        module_ids = template.modules or []
        context = {
            "place_url": campaign.place_url,
            "place_name": campaign.place_name,
        }

        # 명소 선택 전략: steps 모듈이 있으면 100m 이상, 없으면 랜덤
        if "steps" in module_ids:
            context["landmark_strategy"] = "min_distance"
            context["landmark_min_distance"] = 100
        else:
            context["landmark_strategy"] = "random"
        module_warnings = []

        for module_id in module_ids:
            # steps 모듈 실행 직전: 출발지 템플릿에 변수 치환 적용
            if module_id == "steps" and template.steps_start:
                resolved_start = apply_template_variables(
                    template.steps_start, context
                )
                if resolved_start.strip():
                    context["steps_start"] = resolved_start.strip()

            module = ModuleRegistry.get(module_id)
            if module is None:
                module_warnings.append(f"{module_id}: 등록되지 않은 모듈")
                continue
            try:
                result = await module.execute(context)
                context.update(result)
            except Exception as e:
                module_warnings.append(f"{module_id}: {str(e)}")
                logger.warning(
                    f"[자동등록] 캠페인 '{campaign.place_name}' "
                    f"모듈 '{module_id}' 실패 (계속 진행): {e}"
                )

        # landmark 모듈이 필수인데 실패한 경우 → 진행 불가
        if "landmark" in module_ids and not context.get("landmark_name"):
            _safe_update_step(
                db, campaign, "failed",
                f"명소 추출 실패: {'; '.join(module_warnings)}",
            )
            return False

        # 플레이스 URL에서 추출한 실제 상호명 사용
        real_place_name = context.get("real_place_name")

        # 모듈에서 real_place_name을 못 얻었고 campaign.place_name도 비어있으면 별도 추출
        if not real_place_name and not campaign.place_name:
            logger.info("[자동등록] 상호명 미확보 → 플레이스 URL에서 별도 추출 시도")
            try:
                from app.services.naver_map import NaverMapScraper
                async with NaverMapScraper(headless=True) as scraper:
                    place_info = await scraper.get_place_info(campaign.place_url)
                    if place_info.name:
                        real_place_name = place_info.name
                        context["real_place_name"] = real_place_name
                        logger.info(f"[자동등록] 상호명 추출 성공: '{real_place_name}'")
            except Exception as e:
                logger.warning(f"[자동등록] 상호명 별도 추출 실패: {e}")

        if real_place_name and real_place_name != campaign.place_name:
            logger.info(
                f"[자동등록] 상호명 변경: '{campaign.place_name}' → "
                f"'{real_place_name}' (플레이스 URL 기준)"
            )
            campaign.place_name = real_place_name
            context["place_name"] = real_place_name

        # 모듈 결과 DB 저장
        campaign.landmark_name = context.get("landmark_name")
        campaign.step_count = context.get("steps")
        db.commit()

        warning_suffix = ""
        if module_warnings:
            warning_suffix = f" (경고: {'; '.join(module_warnings)})"

        _safe_update_step(
            db, campaign, "running_modules",
            f"모듈 완료: 명소={context.get('landmark_name', 'N/A')}, "
            f"걸음수={context.get('steps', 'N/A')}{warning_suffix}",
        )

        # Step 3: 폼 입력 (실제 상호명 사용)
        if not _safe_update_step(db, campaign, "filling_form", "superap.io 폼 입력 중..."):
            return False

        place_name_for_form = campaign.place_name  # 실제 상호명
        masked_place_name = _mask_place_name(place_name_for_form)
        context_for_template = context.copy()
        context_for_template["place_name"] = masked_place_name

        description = apply_template_variables(
            template.description_template, context_for_template
        )
        hint = apply_template_variables(template.hint_text, context)

        # 캠페인 타입: 템플릿의 campaign_type_selection 사용
        superap_campaign_type = template.campaign_type_selection or "플레이스 퀴즈"
        campaign_name = _generate_campaign_name(
            place_name_for_form, superap_campaign_type
        )

        keywords = [
            kw.strip()
            for kw in (campaign.original_keywords or "").split(",")
            if kw.strip()
        ]

        # 전환 인식 기준: 텍스트 템플릿이 있으면 텍스트, 없으면 걸음수
        conversion_text = None
        if template.conversion_text_template:
            conversion_text = apply_template_variables(
                template.conversion_text_template, context
            )

        form_data = CampaignFormData(
            campaign_name=campaign_name,
            place_name=campaign.place_name,
            landmark_name=context.get("landmark_name", ""),
            participation_guide=description,
            keywords=keywords,
            hint=hint,
            walking_steps=context.get("steps", 0),
            conversion_text=conversion_text,
            start_date=campaign.start_date,
            end_date=campaign.end_date,
            daily_limit=campaign.daily_limit,
            total_limit=campaign.total_limit,
            links=template.links or [],
            campaign_type=superap_campaign_type,
        )

        form_result = await controller.fill_campaign_form(
            account_id=account_key,
            form_data=form_data,
            take_screenshot=True,
        )

        if not form_result.success:
            _safe_update_step(
                db, campaign, "failed",
                f"폼 입력 실패: {', '.join(form_result.errors)}",
            )
            return False

        # Step 4: 제출
        if not _safe_update_step(db, campaign, "submitting", "캠페인 제출 중..."):
            return False

        submit_result = await controller.submit_campaign(
            account_key, campaign_name=campaign_name,
        )
        if not submit_result.success:
            _safe_update_step(
                db, campaign, "failed",
                f"제출 실패: {submit_result.error_message}",
            )
            return False

        # Step 5: 캠페인 번호 추출
        if not _safe_update_step(db, campaign, "extracting_code", "캠페인 번호 추출 중..."):
            return False

        campaign_code = submit_result.campaign_code
        if not campaign_code:
            campaign_code = await controller.extract_campaign_code(
                account_key, campaign_name=campaign_name,
            )

        # Step 6: 완료 — 캠페인 레코드 업데이트
        campaign.campaign_code = campaign_code
        campaign.status = "active"
        campaign.registered_at = datetime.now(timezone.utc)

        # 초기 등록 시 실제로 superap.io에 세팅된 키워드를 사용 처리
        now = datetime.now(timezone.utc)
        initial_kw_str = form_data.processed_keywords
        if initial_kw_str:
            initial_keywords = [kw.strip() for kw in initial_kw_str.split(",") if kw.strip()]
            if initial_keywords:
                kw_records = db.query(KeywordPool).filter(
                    KeywordPool.campaign_id == campaign.id,
                    KeywordPool.keyword.in_(initial_keywords),
                    KeywordPool.is_used == False,
                ).all()
                for kw in kw_records:
                    kw.is_used = True
                    kw.used_at = now
                campaign.last_keyword_change = now
                logger.info(
                    f"[자동등록] 캠페인 '{campaign.place_name}' 초기 키워드 "
                    f"{len(kw_records)}개 사용 처리"
                )

        _safe_update_step(
            db, campaign, "completed",
            f"등록 완료: 캠페인 코드 {campaign_code}",
        )

        logger.info(
            f"[자동등록] 캠페인 '{campaign.place_name}' 등록 완료: "
            f"code={campaign_code}"
        )
        return True

    except SuperapLoginError as e:
        _safe_update_step(db, campaign, "failed", f"로그인 오류: {str(e)}")
        return False
    except SuperapCampaignError as e:
        _safe_update_step(db, campaign, "failed", f"Superap 오류: {str(e)}")
        return False
    except (ObjectDeletedError, InvalidRequestError) as e:
        logger.warning(f"[자동등록] 캠페인 삭제됨/세션 오류 (건너뜀): {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False
    except Exception as e:
        _safe_update_step(db, campaign, "failed", f"예기치 않은 오류: {str(e)}")
        logger.exception(f"[자동등록] 캠페인 ID={campaign.id} 등록 실패")
        return False


async def process_pending_campaigns(
    campaign_ids: Optional[List[int]] = None,
) -> None:
    """대기 중인 캠페인을 계정별로 그룹화하여 순차 등록.

    Args:
        campaign_ids: 지정 시 해당 ID만 처리. None이면 모든 queued 캠페인 처리.
    """
    async with _registration_lock:
        db = SessionLocal()
        controller = None

        try:
            query = db.query(Campaign).filter(
                Campaign.status == "pending",
                Campaign.registration_step == "queued",
                Campaign.campaign_code.is_(None),
            )
            if campaign_ids:
                query = query.filter(Campaign.id.in_(campaign_ids))

            campaigns = query.order_by(Campaign.id).all()

            if not campaigns:
                logger.info("[자동등록] 대기 중인 캠페인 없음")
                return

            logger.info(f"[자동등록] {len(campaigns)}개 캠페인 등록 시작")

            # 계정별 그룹화
            account_groups: Dict[int, List[Campaign]] = {}
            for c in campaigns:
                account_groups.setdefault(c.account_id, []).append(c)

            # 브라우저 초기화
            controller = SuperapController(headless=True)
            await controller.initialize()

            for account_id, group in account_groups.items():
                account = db.query(Account).filter(
                    Account.id == account_id,
                    Account.is_active == True,
                ).first()

                if not account:
                    for c in group:
                        _safe_update_step(
                            db, c, "failed",
                            f"계정을 찾을 수 없습니다: ID {account_id}",
                        )
                    continue

                login_failed = False
                for campaign in group:
                    # 로그인 실패 시 같은 계정의 나머지 캠페인도 실패 처리
                    if login_failed:
                        _safe_update_step(
                            db, campaign, "failed",
                            f"계정 {account.user_id} 로그인 실패로 건너뜀",
                        )
                        continue

                    # 캠페인이 삭제되었을 수 있으므로 refresh를 안전하게 처리
                    try:
                        db.refresh(campaign)
                    except (ObjectDeletedError, InvalidRequestError) as e:
                        logger.warning(
                            f"[자동등록] 캠페인 ID={campaign.id} "
                            f"삭제됨/접근 불가 (건너뜀): {e}"
                        )
                        try:
                            db.rollback()
                        except Exception:
                            pass
                        continue

                    # 이미 처리된 캠페인 건너뛰기
                    if campaign.registration_step != "queued":
                        logger.info(
                            f"[자동등록] 캠페인 ID={campaign.id} "
                            f"이미 처리됨 (step={campaign.registration_step})"
                        )
                        continue

                    success = await register_single_campaign(
                        controller, db, campaign, account
                    )

                    # 로그인 단계에서 실패한 경우 같은 계정 나머지도 건너뜀
                    try:
                        if not success and campaign.registration_step == "failed":
                            msg = campaign.registration_message or ""
                            if "로그인" in msg:
                                login_failed = True
                    except (ObjectDeletedError, InvalidRequestError):
                        pass

                    # 등록 간 대기
                    await asyncio.sleep(2)

                # 계정 컨텍스트 정리
                try:
                    await controller.close_context(str(account_id))
                except Exception:
                    pass

            logger.info("[자동등록] 전체 처리 완료")

        except Exception as e:
            logger.exception(f"[자동등록] 전체 처리 오류: {e}")
        finally:
            db.close()
            if controller:
                try:
                    await controller.close()
                except Exception:
                    pass


def trigger_auto_registration(campaign_ids: List[int]) -> None:
    """업로드 confirm에서 호출하는 fire-and-forget 트리거."""
    loop = asyncio.get_running_loop()
    loop.create_task(process_pending_campaigns(campaign_ids))
    logger.info(
        f"[자동등록] 백그라운드 태스크 시작: {len(campaign_ids)}개 캠페인"
    )


async def process_pending_extensions(
    campaign_ids: Optional[List[int]] = None,
) -> None:
    """pending_extend 상태 캠페인의 연장 처리.

    1. pending_extend 캠페인 조회
    2. 계정별 그룹화 → 로그인
    3. 연장 키워드를 기존 캠페인 KeywordPool에 먼저 병합
    4. 미사용 키워드 255자 이내로 조합
    5. superap.io에서 edit_campaign() 호출 (총타수 + 일타수 + 만료일 + 키워드)
    6. 성공 시 extend 레코드 삭제, 실패 시 status="failed"
    """
    import random as _random

    db = SessionLocal()
    controller = None

    try:
        query = db.query(Campaign).filter(
            Campaign.status == "pending_extend",
            Campaign.extend_target_id.isnot(None),
        )
        if campaign_ids:
            query = query.filter(Campaign.id.in_(campaign_ids))

        extend_campaigns = query.order_by(Campaign.id).all()

        if not extend_campaigns:
            logger.info("[연장처리] 대기 중인 연장 캠페인 없음")
            return

        logger.info(f"[연장처리] {len(extend_campaigns)}개 연장 캠페인 처리 시작")

        # 계정별 그룹화
        account_groups: Dict[int, List[Campaign]] = {}
        for c in extend_campaigns:
            account_groups.setdefault(c.account_id, []).append(c)

        # 브라우저 초기화
        controller = SuperapController(headless=True)
        await controller.initialize()

        for account_id, group in account_groups.items():
            account = db.query(Account).filter(
                Account.id == account_id,
                Account.is_active == True,
            ).first()

            if not account:
                for c in group:
                    c.status = "failed"
                    c.registration_message = f"계정을 찾을 수 없습니다: ID {account_id}"
                db.commit()
                continue

            # 로그인
            account_key = str(account.id)
            try:
                password = decrypt_password(account.password_encrypted)
                login_ok = await controller.login(account_key, account.user_id, password)
                if not login_ok:
                    for c in group:
                        c.status = "failed"
                        c.registration_message = f"계정 {account.user_id} 로그인 실패"
                    db.commit()
                    continue
            except Exception as e:
                for c in group:
                    c.status = "failed"
                    c.registration_message = f"로그인 오류: {str(e)}"
                db.commit()
                continue

            # 각 연장 캠페인 처리
            for ext_campaign in group:
                try:
                    # 기존 대상 캠페인 조회
                    target = db.query(Campaign).filter(
                        Campaign.id == ext_campaign.extend_target_id,
                    ).first()

                    if not target:
                        ext_campaign.status = "failed"
                        ext_campaign.registration_message = (
                            f"연장 대상 캠페인(ID:{ext_campaign.extend_target_id})을 찾을 수 없습니다"
                        )
                        db.commit()
                        continue

                    if not target.campaign_code:
                        ext_campaign.status = "failed"
                        ext_campaign.registration_message = "대상 캠페인에 campaign_code가 없습니다"
                        db.commit()
                        continue

                    # 중복 연장 방지: 동일 날짜/값의 연장이 이미 처리된 경우 건너뛰기
                    existing_history = []
                    if target.extension_history:
                        try:
                            existing_history = json.loads(target.extension_history)
                        except (json.JSONDecodeError, TypeError):
                            existing_history = []

                    is_duplicate = any(
                        h.get("start_date") == str(ext_campaign.start_date)
                        and h.get("end_date") == str(ext_campaign.end_date)
                        and h.get("daily_limit") == ext_campaign.daily_limit
                        and h.get("total_limit_added") == (ext_campaign.total_limit or 0)
                        for h in existing_history
                    )
                    if is_duplicate:
                        logger.warning(
                            f"[연장처리] 캠페인 {target.campaign_code} 중복 연장 감지 "
                            f"({ext_campaign.start_date}~{ext_campaign.end_date}), 건너뜀"
                        )
                        # 중복 연장 레코드 삭제
                        db.query(KeywordPool).filter(
                            KeywordPool.campaign_id == ext_campaign.id,
                        ).delete()
                        db.delete(ext_campaign)
                        db.commit()
                        continue

                    # 1) 연장 키워드를 기존 캠페인 KeywordPool에 먼저 병합
                    ext_keywords = [
                        kw.strip()
                        for kw in (ext_campaign.original_keywords or "").split(",")
                        if kw.strip()
                    ]
                    keywords_added = 0
                    if ext_keywords:
                        existing_kws = {
                            kw.keyword
                            for kw in db.query(KeywordPool).filter(
                                KeywordPool.campaign_id == target.id,
                            ).all()
                        }
                        for keyword in ext_keywords:
                            if keyword not in existing_kws:
                                db.add(KeywordPool(
                                    campaign_id=target.id,
                                    keyword=keyword,
                                    is_used=False,
                                ))
                                existing_kws.add(keyword)
                                keywords_added += 1
                        db.flush()
                        logger.info(
                            f"[연장처리] 캠페인 {target.campaign_code}에 키워드 {keywords_added}개 추가"
                        )

                    # 2) 미사용 키워드에서 255자 이내로 조합 (키워드 로테이션과 동일 로직)
                    unused_keywords = db.query(KeywordPool).filter(
                        KeywordPool.campaign_id == target.id,
                        KeywordPool.is_used == False,
                    ).all()

                    keywords_str = ""
                    if unused_keywords:
                        _random.shuffle(unused_keywords)
                        selected = []
                        cur_len = 0
                        for kw_pool in unused_keywords:
                            kw = kw_pool.keyword.strip()
                            if not kw:
                                continue
                            sep_len = 1 if selected else 0
                            if cur_len + sep_len + len(kw) <= 255:
                                selected.append(kw)
                                cur_len += sep_len + len(kw)
                        keywords_str = ",".join(selected)

                    # 3) 새 값 계산
                    new_total_limit = (target.total_limit or 0) + (ext_campaign.total_limit or 0)
                    new_daily_limit = ext_campaign.daily_limit
                    new_end_date = max(target.end_date, ext_campaign.end_date)

                    logger.info(
                        f"[연장처리] 캠페인 {target.campaign_code} 수정 시작: "
                        f"total_limit={target.total_limit}→{new_total_limit}, "
                        f"daily_limit={target.daily_limit}→{new_daily_limit}, "
                        f"end_date={target.end_date}→{new_end_date}, "
                        f"keywords={len(keywords_str)}자"
                    )

                    # 4) superap.io에서 캠페인 수정 (총타수 + 일타수 + 만료일 + 키워드)
                    edit_kwargs = {
                        "account_id": account_key,
                        "campaign_code": target.campaign_code,
                        "new_total_limit": new_total_limit,
                        "new_daily_limit": new_daily_limit,
                        "new_end_date": new_end_date,
                    }
                    if keywords_str:
                        edit_kwargs["new_keywords"] = keywords_str

                    edit_success = await controller.edit_campaign(**edit_kwargs)

                    if not edit_success:
                        db.rollback()  # 키워드 병합 롤백
                        ext_campaign.status = "failed"
                        ext_campaign.registration_message = "superap.io 캠페인 수정 실패"
                        db.commit()
                        continue

                    # 5) 연장 이력 기록
                    history = []
                    if target.extension_history:
                        try:
                            history = json.loads(target.extension_history)
                        except (json.JSONDecodeError, TypeError):
                            history = []
                    round_num = len(history) + 1
                    history.append({
                        "round": round_num,
                        "start_date": str(ext_campaign.start_date),
                        "end_date": str(ext_campaign.end_date),
                        "daily_limit": ext_campaign.daily_limit,
                        "total_limit_added": ext_campaign.total_limit or 0,
                        "keywords_added": keywords_added,
                        "extended_at": datetime.now(timezone.utc).isoformat(),
                    })
                    target.extension_history = json.dumps(history, ensure_ascii=False)

                    # 6) DB 업데이트: 기존 캠페인에 변경 적용
                    target.total_limit = new_total_limit
                    target.daily_limit = new_daily_limit
                    target.end_date = new_end_date
                    target.updated_at = datetime.now(timezone.utc)

                    # 전체소진 상태였으면 active로 복구
                    if target.status in ("campaign_exhausted", "전체소진", "캠페인소진"):
                        target.status = "active"

                    # 7) 연장 레코드의 키워드 먼저 삭제 (FK 제약 때문)
                    db.query(KeywordPool).filter(
                        KeywordPool.campaign_id == ext_campaign.id,
                    ).delete()

                    # 연장 레코드 삭제
                    db.delete(ext_campaign)
                    db.commit()

                    logger.info(
                        f"[연장처리] 캠페인 {target.campaign_code} 연장 성공: "
                        f"total_limit={new_total_limit}, daily_limit={new_daily_limit}, "
                        f"end_date={new_end_date} (연장 레코드 삭제됨)"
                    )

                except Exception as e:
                    ext_campaign.status = "failed"
                    ext_campaign.registration_message = f"연장 처리 오류: {str(e)}"
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
                    logger.error(f"[연장처리] 캠페인 ID={ext_campaign.id} 오류: {e}")

            # 계정 컨텍스트 정리
            try:
                await controller.close_context(account_key)
            except Exception:
                pass

        logger.info("[연장처리] 전체 처리 완료")

    except Exception as e:
        logger.exception(f"[연장처리] 전체 처리 오류: {e}")
    finally:
        db.close()
        if controller:
            try:
                await controller.close()
            except Exception:
                pass


def trigger_auto_extension(campaign_ids: Optional[List[int]] = None) -> None:
    """연장 처리 fire-and-forget 트리거."""
    loop = asyncio.get_running_loop()
    loop.create_task(process_pending_extensions(campaign_ids))
    logger.info("[연장처리] 백그라운드 태스크 시작")
