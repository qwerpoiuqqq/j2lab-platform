"""Campaign registration orchestration service.

Receives registration requests from api-server, decrypts superap credentials,
fills the campaign form via Playwright, submits it, and updates the DB.

Ported from reference/quantum-campaign/backend/app/services/campaign_registration.py
and auto_registration.py, adapted for async PostgreSQL.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import re
import secrets
import string
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.campaign import Campaign
from app.models.campaign_keyword_pool import CampaignKeywordPool
from app.models.campaign_template import CampaignTemplate
from app.models.superap_account import SuperapAccount
from app.services.superap_client import (
    CampaignFormData,
    CampaignFormResult,
    SuperapCampaignError,
    SuperapClient,
    SuperapLoginError,
)
from app.modules.base import ModuleError
from app.modules.registry import ModuleRegistry
from app.utils.crypto import decrypt_password

# campaign_type -> active template lookup candidates.
# Prefer english `code`, but keep legacy Korean names as fallback.
_CAMPAIGN_TEMPLATE_CANDIDATES = {
    "smart_traffic": ("smart_traffic", "스마트 트래픽"),
    "smart_save": ("smart_save", "스마트 저장하기"),
    # 레거시 호환
    "traffic": ("smart_traffic", "스마트 트래픽"),
    "save": ("smart_save", "스마트 저장하기"),
}
from app.utils.template_vars import apply_template_variables

logger = logging.getLogger(__name__)

# Per-account locks to prevent concurrent registrations on the same account
_account_locks: dict[int, asyncio.Lock] = {}


def _get_account_lock(account_id: int) -> asyncio.Lock:
    """Get or create a lock for a specific superap account."""
    if account_id not in _account_locks:
        _account_locks[account_id] = asyncio.Lock()
    return _account_locks[account_id]


def _get_template_candidates(campaign_type: str) -> tuple[str, ...]:
    candidates = list(_CAMPAIGN_TEMPLATE_CANDIDATES.get(campaign_type, (campaign_type,)))
    if campaign_type not in candidates:
        candidates.insert(0, campaign_type)

    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return tuple(unique_candidates)


async def _get_active_template(
    session: AsyncSession,
    campaign_type: str,
    template_id: int | None = None,
) -> CampaignTemplate | None:
    if template_id is not None:
        result = await session.execute(
            select(CampaignTemplate).where(
                CampaignTemplate.id == template_id,
                CampaignTemplate.is_active.is_(True),
            )
        )
        template = result.scalar_one_or_none()
        if template is not None:
            return template

    for candidate in _get_template_candidates(campaign_type):
        result = await session.execute(
            select(CampaignTemplate).where(
                CampaignTemplate.code == candidate,
                CampaignTemplate.is_active.is_(True),
            )
        )
        template = result.scalar_one_or_none()
        if template is not None:
            return template

    for candidate in _get_template_candidates(campaign_type):
        result = await session.execute(
            select(CampaignTemplate).where(
                CampaignTemplate.type_name == candidate,
                CampaignTemplate.is_active.is_(True),
            )
        )
        template = result.scalar_one_or_none()
        if template is not None:
            return template

    return None


async def _load_registration_keywords(
    session: AsyncSession,
    campaign: Campaign,
) -> list[str]:
    keywords = [
        kw.strip()
        for kw in (campaign.original_keywords or "").split(",")
        if kw.strip()
    ]
    if keywords:
        return keywords

    result = await session.execute(
        select(CampaignKeywordPool.keyword)
        .where(CampaignKeywordPool.campaign_id == campaign.id)
        .order_by(CampaignKeywordPool.is_used.asc(), CampaignKeywordPool.id.asc())
    )
    return [str(row[0]).strip() for row in result.all() if str(row[0]).strip()]


def extract_place_id(url: str) -> Optional[str]:
    """Extract place ID from a Naver Place URL."""
    if not url:
        return None
    match = re.search(
        r"/(?:place|restaurant|cafe|hospital|beauty|accommodation|shopping)/(\d+)",
        url,
    )
    if match:
        return match.group(1)
    parsed = urlparse(url)
    path_match = re.search(r"/(\d{5,})", parsed.path)
    if path_match:
        return path_match.group(1)
    return None


def _mask_place_name(name: str) -> str:
    """Mask every 2nd character with X."""
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
    """Generate campaign name from place name and type.

    Rules:
    - If place name ends with "점" (branch): "{brand_prefix} {branch_prefix} 퀴즈 맞추기"
    - Otherwise: "{first_2_chars} 퀴즈 맞추기"
    - Save type: "저장 퀴즈 맞추기"
    """
    save_keywords = ["저장", "save", "place_save"]
    is_save = any(kw in campaign_type.lower() for kw in save_keywords)
    suffix = "저장 퀴즈 맞추기" if is_save else "퀴즈 맞추기"

    parts = place_name.strip().split()
    if len(parts) >= 2 and parts[-1].endswith("점"):
        brand_part = " ".join(parts[:-1])
        branch_word = parts[-1][:-1]
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

    name_chars = [c for c in place_name if c != " "]
    if len(name_chars) <= 2:
        prefix = name_chars[0] if name_chars else ""
    else:
        prefix = "".join(name_chars[:2])
    return f"{prefix} {suffix}"


_DEFAULT_REDIRECT_CONFIG = {
    "channels": {
        "naver_app": {
            "weight": 40,
            "sub": {
                "home": {"weight": 85},
                "blog": {"weight": 15},
            },
        },
        "map_app": {
            "weight": 30,
            "tabs": {
                "map": {"weight": 25},
                "map?tab=discovery": {"weight": 30},
                "map?tab=navi": {"weight": 20},
                "map?tab=pubtrans": {"weight": 15},
                "map?tab=bookmark": {"weight": 10},
            },
        },
        "browser": {
            "weight": 30,
            "sub": {
                "home": {"weight": 85},
                "blog": {"weight": 15},
            },
        },
    },
    "place_id": "",
    "blog_url": "",
}


def _generate_landing_slug(length: int = 10) -> str:
    """Generate a random landing slug for redirect URLs."""
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def _build_redirect_config(
    template_config: dict | None,
    place_id: int | None = None,
    blog_url: str = "",
    share_url: str = "",
) -> dict:
    """Build redirect config from template defaults + place data."""
    if template_config:
        config = copy.deepcopy(template_config)
    else:
        config = copy.deepcopy(_DEFAULT_REDIRECT_CONFIG)

    if place_id:
        config["place_id"] = str(place_id)
    if blog_url:
        config["blog_url"] = blog_url
    if share_url:
        config["share_url"] = share_url

    return config


async def _update_step(
    session: AsyncSession,
    campaign_id: int,
    step: str,
    message: str = "",
) -> None:
    """Update registration step in DB (for frontend polling)."""
    try:
        await session.execute(
            update(Campaign)
            .where(Campaign.id == campaign_id)
            .values(
                registration_step=step,
                registration_message=message,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
    except Exception as e:
        logger.warning(f"Failed to update step for campaign {campaign_id}: {e}")
        await session.rollback()


async def _send_callback(
    campaign_id: int,
    status: str,
    campaign_code: Optional[str] = None,
    error_message: Optional[str] = None,
    registration_step: Optional[str] = None,
) -> None:
    """Send completion callback to api-server.

    Payload matches api-server's CampaignCallbackRequest schema:
    - status: "active", "completed", or "failed"
    - campaign_code: superap campaign code (on success)
    - error_message: error details (on failure)
    - registration_step: current step (on failure)
    """
    callback_url = (
        f"{settings.API_SERVER_URL}/internal/callback/campaign/{campaign_id}"
    )
    payload: Dict[str, Any] = {"status": status}
    if campaign_code is not None:
        payload["campaign_code"] = campaign_code
    if error_message is not None:
        payload["error_message"] = error_message
    if registration_step is not None:
        payload["registration_step"] = registration_step
    headers = {"X-Internal-Secret": settings.INTERNAL_API_SECRET}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(callback_url, json=payload, headers=headers)
            if resp.status_code < 300:
                logger.info(
                    f"Callback sent for campaign {campaign_id}: {status}"
                )
            else:
                logger.warning(
                    f"Callback failed for campaign {campaign_id}: "
                    f"{resp.status_code} {resp.text}"
                )
    except Exception as e:
        logger.warning(f"Callback error for campaign {campaign_id}: {e}")


async def register_campaign(
    campaign_id: int,
    account_id: int | None = None,
    template_id: int | None = None,
) -> dict:
    """Register a single campaign on superap.io.

    Full flow:
    1. Load campaign, account, and template from DB
    2. Decrypt superap password
    3. Login to superap.io
    4. Fill campaign form
    5. Submit and capture campaign code
    6. Update DB with campaign_code and active status
    7. Send callback to api-server

    Args:
        campaign_id: Campaign DB ID

    Returns:
        Result dict with success/error info
    """
    async with async_session_factory() as session:
        # Load campaign
        result_stmt = select(Campaign).where(Campaign.id == campaign_id)
        result = await session.execute(result_stmt)
        campaign = result.scalar_one_or_none()

        if not campaign:
            return {"success": False, "error": f"Campaign {campaign_id} not found"}

        # Mark as registering
        await session.execute(
            update(Campaign)
            .where(Campaign.id == campaign_id)
            .values(
                status="registering",
                registration_step="queued",
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

        # Load superap account
        effective_account_id = account_id or campaign.superap_account_id
        account_stmt = select(SuperapAccount).where(
            SuperapAccount.id == effective_account_id
        )
        account_result = await session.execute(account_stmt)
        account = account_result.scalar_one_or_none()

        if not account:
            await _update_step(
                session, campaign_id, "failed",
                f"Superap account {effective_account_id} not found",
            )
            await _send_callback(campaign_id, "failed", error_message="Account not found")
            return {"success": False, "error": "Account not found"}

        template = await _get_active_template(
            session,
            campaign.campaign_type,
            template_id=template_id,
        )

        if not template:
            await _update_step(
                session, campaign_id, "failed",
                f"Template not found for type: {campaign.campaign_type}",
            )
            await _send_callback(campaign_id, "failed", error_message="Template not found")
            return {"success": False, "error": "Template not found"}

    # Perform Playwright automation outside the DB session
    # Use per-account lock to prevent concurrent browser operations on same account
    async with _get_account_lock(account.id):
        client: Optional[SuperapClient] = None
        try:
            client = SuperapClient(headless=settings.PLAYWRIGHT_HEADLESS)
            await client.initialize()

            account_key = str(account.id)

            # Step 0: Execute modules if template defines them
            template_modules: list = list(template.modules or [])
            module_context: Dict[str, Any] = {}

            if template_modules:
                # Auto-add missing module dependencies without changing registry ordering.
                all_modules = list(template_modules)
                to_scan = list(template_modules)
                while to_scan:
                    mod_id = to_scan.pop(0)
                    mod = ModuleRegistry.get(mod_id)
                    if mod:
                        for dep in mod.dependencies:
                            if dep not in all_modules:
                                all_modules.insert(0, dep)
                                to_scan.append(dep)
                                logger.info(
                                    f"Auto-added dependency {dep} for module {mod_id}"
                                )
                template_modules = all_modules

            if template_modules:
                async with async_session_factory() as session:
                    await _update_step(
                        session, campaign_id, "running_modules",
                        f"Running modules: {template_modules}",
                    )
                try:
                    initial_ctx: Dict[str, Any] = {
                        "place_url": campaign.place_url,
                        "place_name": campaign.place_name,
                    }
                    # Set landmark selection strategy based on whether steps module is used
                    if "steps" in template_modules:
                        initial_ctx["landmark_strategy"] = "min_distance"
                        initial_ctx["landmark_min_distance"] = 100
                    else:
                        initial_ctx["landmark_strategy"] = "random"

                    # Execute modules in dependency order with per-module hooks
                    sorted_modules = ModuleRegistry._sort_by_dependencies(template_modules)
                    module_context = dict(initial_ctx)
                    module_warnings = []

                    for module_id in sorted_modules:
                        # steps 모듈 실행 직전: 출발지 템플릿에 변수 치환 적용
                        if module_id == "steps" and template.steps_start:
                            resolved_start = apply_template_variables(
                                template.steps_start, module_context
                            )
                            if resolved_start.strip():
                                module_context["steps_start"] = resolved_start.strip()

                        module = ModuleRegistry.get(module_id)
                        if module is None:
                            module_warnings.append(f"{module_id}: 등록되지 않은 모듈")
                            continue
                        try:
                            result = await module.execute(module_context)
                            module_context.update(result)
                            logger.info(
                                f"Campaign {campaign_id} module {module_id} completed: "
                                f"{list(result.keys())}"
                            )
                        except Exception as e:
                            module_warnings.append(f"{module_id}: {str(e)}")
                            logger.warning(
                                f"Campaign {campaign_id} module '{module_id}' 실패 (계속 진행): {e}"
                            )

                    if module_warnings:
                        logger.warning(
                            f"Campaign {campaign_id} module warnings: {module_warnings}"
                        )

                    # NaverMap fallback: extract place_name separately if still missing.
                    if not module_context.get("real_place_name") and not campaign.place_name:
                        logger.info(
                            f"Campaign {campaign_id}: place_name missing - trying NaverMap extraction"
                        )
                        try:
                            from app.services.naver_map import NaverMapScraper

                            async with NaverMapScraper(headless=True) as scraper:
                                place_info = await scraper.get_place_info(campaign.place_url)
                                if place_info.name:
                                    module_context["real_place_name"] = place_info.name
                                    logger.info(
                                        f"Campaign {campaign_id}: NaverMap extraction success: '{place_info.name}'"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Campaign {campaign_id}: NaverMap extraction failed: {e}"
                            )

                    logger.info(
                        f"Campaign {campaign_id} modules completed: "
                        f"{list(module_context.keys())}"
                    )

                    # Save module results to DB
                    real_place_name = module_context.get("real_place_name")
                    update_values: Dict[str, Any] = {
                        "module_context": module_context,
                        "updated_at": datetime.now(timezone.utc),
                    }
                    if "landmark_name" in module_context:
                        update_values["landmark_name"] = module_context["landmark_name"]
                    if "steps" in module_context:
                        update_values["step_count"] = module_context["steps"]
                    # Update place_name from module if different from current.
                    if real_place_name and real_place_name != campaign.place_name:
                        update_values["place_name"] = real_place_name

                    async with async_session_factory() as session:
                        await session.execute(
                            update(Campaign)
                            .where(Campaign.id == campaign_id)
                            .values(**update_values)
                        )
                        await session.commit()

                    # Update local campaign values for form data
                    if "landmark_name" in module_context:
                        campaign.landmark_name = module_context["landmark_name"]
                    if "steps" in module_context:
                        campaign.step_count = module_context["steps"]
                    if real_place_name and real_place_name != campaign.place_name:
                        campaign.place_name = real_place_name
                        module_context["place_name"] = real_place_name

                except ModuleError as e:
                    logger.warning(
                        f"Campaign {campaign_id} module error (continuing): {e}"
                    )
                    async with async_session_factory() as session:
                        await _update_step(
                            session, campaign_id, "module_warning",
                            f"Module warning: {str(e)}",
                        )

            # --- DRY_RUN: skip entire Playwright flow (login, form, submit) ---
            if settings.DRY_RUN:
                import secrets as _secrets
                fake_code = f"DRY{_secrets.token_hex(3).upper()}"
                logger.info(
                    f"[DRY_RUN] Skipping registration for campaign {campaign_id}, "
                    f"fake code: {fake_code}"
                )
                async with async_session_factory() as session:
                    await _update_step(
                        session, campaign_id, "completed",
                        f"[DRY_RUN] Registration skipped — code: {fake_code}",
                    )
                now = datetime.now(timezone.utc)

                # Generate smart redirect data even in DRY_RUN
                dry_landing_slug = None
                dry_redirect_config = None
                try:
                    dry_landing_slug = _generate_landing_slug()
                    dry_redirect_config = _build_redirect_config(
                        template_config=getattr(template, 'default_redirect_config', None),
                        place_id=campaign.place_id,
                    )
                except Exception as e:
                    logger.warning(f"[DRY_RUN] redirect setup failed: {e}")

                dry_update_values = {
                    "campaign_code": fake_code,
                    "status": "active",
                    "registration_step": "completed",
                    "registration_message": f"[DRY_RUN] code {fake_code}",
                    "registered_at": now,
                    "last_keyword_change": now,
                    "updated_at": now,
                }
                if dry_landing_slug:
                    dry_update_values["landing_slug"] = dry_landing_slug
                if dry_redirect_config:
                    dry_update_values["redirect_config"] = dry_redirect_config

                async with async_session_factory() as session:
                    await session.execute(
                        update(Campaign)
                        .where(Campaign.id == campaign_id)
                        .values(**dry_update_values)
                    )
                    await session.commit()
                await _send_callback(campaign_id, "active", campaign_code=fake_code)
                return {
                    "success": True,
                    "campaign_code": fake_code,
                    "campaign_id": campaign_id,
                    "dry_run": True,
                }

            # Step 1: Login
            async with async_session_factory() as session:
                await _update_step(session, campaign_id, "logging_in", "Logging in to superap.io...")

            password = decrypt_password(account.password_encrypted)
            login_ok = await client.login(account_key, account.user_id_superap, password)
            if not login_ok:
                async with async_session_factory() as session:
                    await _update_step(
                        session, campaign_id, "failed",
                        f"Login failed: {account.user_id_superap}",
                    )
                await _send_callback(campaign_id, "failed", error_message="Login failed")
                return {"success": False, "error": "Login failed"}

            # Step 2: Prepare form data
            async with async_session_factory() as session:
                await _update_step(session, campaign_id, "filling_form", "Preparing form data...")

            masked_place_name = _mask_place_name(campaign.place_name)
            context = dict(module_context) if module_context else {}
            context["place_name"] = masked_place_name
            context["place_url"] = campaign.place_url
            if "landmark_name" not in context:
                context["landmark_name"] = campaign.landmark_name or ""
            if "steps" not in context:
                context["steps"] = campaign.step_count or 0

            description = apply_template_variables(
                template.description_template, context
            )
            hint_context = dict(module_context) if module_context else {}
            hint_context["place_name"] = campaign.place_name
            hint_context["landmark_name"] = campaign.landmark_name or ""
            hint_context["steps"] = campaign.step_count or 0
            hint = apply_template_variables(template.hint_text, hint_context)

            superap_campaign_type = template.campaign_type_selection or "플레이스 퀴즈"
            campaign_name = _generate_campaign_name(
                campaign.place_name, superap_campaign_type
            )

            async with async_session_factory() as session:
                keywords = await _load_registration_keywords(session, campaign)

            conversion_text = None
            if template.conversion_text_template:
                conversion_context = dict(module_context) if module_context else {}
                conversion_context["place_name"] = campaign.place_name
                conversion_context["landmark_name"] = campaign.landmark_name or ""
                conversion_context["steps"] = campaign.step_count or 0
                conversion_text = apply_template_variables(
                    template.conversion_text_template,
                    conversion_context,
                )

            # === Smart redirect: generate slug + redirect config ===
            landing_slug = None
            redirect_config = None
            form_links = template.links or []

            try:
                from app.services.place_data_collector import collect_place_data

                # Collect place data (blog URL, coordinates)
                place_data = {}
                if campaign.place_id:
                    try:
                        place_data = await collect_place_data(
                            str(campaign.place_id), campaign.place_url
                        )
                        logger.info(
                            f"[PlaceData] campaign={campaign_id} "
                            f"blog={'있음' if place_data.get('blog_url') else '없음'}"
                        )
                    except Exception as e:
                        logger.warning(f"[PlaceData] collection failed: {e}")

                # Generate slug and build redirect config
                landing_slug = _generate_landing_slug()
                redirect_config = _build_redirect_config(
                    template_config=getattr(template, 'default_redirect_config', None),
                    place_id=campaign.place_id,
                    blog_url=place_data.get("blog_url", ""),
                    share_url=place_data.get("share_url", ""),
                )

                # Build mission link: /r/{slug}#{hashtag}
                base_url = getattr(settings, 'LANDING_BASE_URL', 'https://logic-lab.kr')
                hashtag = template.hashtag or ""
                if hashtag and not hashtag.startswith("#"):
                    hashtag = f"#{hashtag}"
                redirect_url = f"{base_url.rstrip('/')}/r/{landing_slug}"
                form_links = [f"{redirect_url}{hashtag}"]

                logger.info(
                    f"[SmartRedirect] campaign={campaign_id} "
                    f"slug={landing_slug} link={form_links[0]}"
                )
            except ImportError:
                logger.warning("place_data_collector not available, using template links")
            except Exception as e:
                logger.warning(f"[SmartRedirect] setup failed, using template links: {e}")

            form_data = CampaignFormData(
                campaign_name=campaign_name,
                place_name=campaign.place_name,
                landmark_name=campaign.landmark_name or "",
                participation_guide=description,
                keywords=keywords,
                hint=hint,
                walking_steps=campaign.step_count or 0,
                conversion_text=conversion_text,
                start_date=campaign.start_date,
                end_date=campaign.end_date,
                daily_limit=campaign.daily_limit,
                total_limit=campaign.total_limit,
                links=form_links,
                campaign_type=superap_campaign_type,
            )

            # Step 3: Fill form
            form_result = await client.fill_campaign_form(
                account_id=account_key,
                form_data=form_data,
                take_screenshot=True,
            )

            if not form_result.success:
                error_msg = f"Form fill failed: {', '.join(form_result.errors)}"
                async with async_session_factory() as session:
                    await _update_step(session, campaign_id, "failed", error_msg)
                await _send_callback(campaign_id, "failed", error_message=error_msg)
                return {"success": False, "error": error_msg}

            # Step 4: Submit
            async with async_session_factory() as session:
                await _update_step(session, campaign_id, "submitting", "Submitting campaign...")

            submit_result = await client.submit_campaign(
                account_key, campaign_name=campaign_name
            )

            if not submit_result.success:
                error_msg = f"Submit failed: {submit_result.error_message}"
                async with async_session_factory() as session:
                    await _update_step(session, campaign_id, "failed", error_msg)
                await _send_callback(campaign_id, "failed", error_message=error_msg)
                return {"success": False, "error": error_msg}

            # Step 5: Extract campaign code
            async with async_session_factory() as session:
                await _update_step(
                    session, campaign_id, "extracting_code",
                    "Extracting campaign code...",
                )

            campaign_code = submit_result.campaign_code
            if not campaign_code:
                campaign_code = await client.extract_campaign_code(
                    account_key, campaign_name=campaign_name
                )

            # Step 6: Update DB
            now = datetime.now(timezone.utc)
            async with async_session_factory() as session:
                # Mark initial keywords as used
                initial_kw_str = form_data.processed_keywords
                if initial_kw_str:
                    initial_keywords = [
                        kw.strip() for kw in initial_kw_str.split(",") if kw.strip()
                    ]
                    if initial_keywords:
                        kw_stmt = select(CampaignKeywordPool).where(
                            CampaignKeywordPool.campaign_id == campaign_id,
                            CampaignKeywordPool.keyword.in_(initial_keywords),
                            CampaignKeywordPool.is_used.is_(False),
                        )
                        kw_result = await session.execute(kw_stmt)
                        kw_records = kw_result.scalars().all()
                        for kw in kw_records:
                            kw.is_used = True
                            kw.used_at = now

                update_values = {
                    "campaign_code": campaign_code,
                    "status": "active",
                    "registration_step": "completed",
                    "registration_message": f"Registered: code {campaign_code}",
                    "registered_at": now,
                    "last_keyword_change": now,
                    "updated_at": now,
                }
                if landing_slug:
                    update_values["landing_slug"] = landing_slug
                if redirect_config:
                    update_values["redirect_config"] = redirect_config

                await session.execute(
                    update(Campaign)
                    .where(Campaign.id == campaign_id)
                    .values(**update_values)
                )
                await session.commit()

            await _send_callback(campaign_id, "active", campaign_code=campaign_code)

            logger.info(
                f"Campaign {campaign_id} registered successfully: code={campaign_code}"
            )
            return {
                "success": True,
                "campaign_code": campaign_code,
                "campaign_id": campaign_id,
            }

        except SuperapLoginError as e:
            error_msg = f"Login error: {str(e)}"
            async with async_session_factory() as session:
                await _update_step(session, campaign_id, "failed", error_msg)
            await _send_callback(campaign_id, "failed", error_message=error_msg)
            return {"success": False, "error": error_msg}
        except SuperapCampaignError as e:
            error_msg = f"Superap error: {str(e)}"
            async with async_session_factory() as session:
                await _update_step(session, campaign_id, "failed", error_msg)
            await _send_callback(campaign_id, "failed", error_message=error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(f"Campaign {campaign_id} registration failed")
            async with async_session_factory() as session:
                await _update_step(session, campaign_id, "failed", error_msg)
            await _send_callback(campaign_id, "failed", error_message=error_msg)
            return {"success": False, "error": error_msg}
        finally:
            if client:
                try:
                    await client.close()
                except Exception:
                    pass


async def extend_campaign(
    campaign_id: int,
    new_end_date: date,
    additional_total: int,
    new_daily_limit: Optional[int] = None,
) -> dict:
    """Extend an existing campaign on superap.io.

    Updates total limit, end date, and optionally daily limit.

    Args:
        campaign_id: Campaign DB ID
        new_end_date: New end date
        additional_total: Additional total limit to add
        new_daily_limit: New daily limit (optional)

    Returns:
        Result dict with success/error info
    """
    async with async_session_factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            return {"success": False, "error": f"Campaign {campaign_id} not found"}
        if not campaign.campaign_code:
            return {"success": False, "error": "Campaign has no code"}

        # Fix 6: Duplicate extension prevention
        if campaign.extension_history:
            try:
                history = (
                    json.loads(campaign.extension_history)
                    if isinstance(campaign.extension_history, str)
                    else campaign.extension_history
                )
            except (json.JSONDecodeError, TypeError):
                history = []
            if history:
                last = history[-1]
                last_time_str = last.get("extended_at", "")
                if last_time_str:
                    try:
                        last_time = datetime.fromisoformat(last_time_str)
                        if last_time.tzinfo is None:
                            last_time = last_time.replace(tzinfo=timezone.utc)
                        elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
                        if elapsed < 300 and last.get("added_quantity") == additional_total:
                            logger.warning(
                                f"Duplicate extension detected for campaign {campaign_id}"
                            )
                            return {"status": "skipped", "reason": "duplicate_extension"}
                    except (ValueError, TypeError):
                        pass

        account_result = await session.execute(
            select(SuperapAccount).where(
                SuperapAccount.id == campaign.superap_account_id
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            return {"success": False, "error": "Account not found"}

    client: Optional[SuperapClient] = None
    try:
        client = SuperapClient(headless=settings.PLAYWRIGHT_HEADLESS)
        await client.initialize()

        account_key = str(account.id)
        password = decrypt_password(account.password_encrypted)
        login_ok = await client.login(account_key, account.user_id_superap, password)
        if not login_ok:
            return {"success": False, "error": "Login failed"}

        updated_total = (campaign.total_limit or 0) + additional_total
        edit_success = await client.edit_campaign(
            account_id=account_key,
            campaign_code=campaign.campaign_code,
            new_total_limit=updated_total,
            new_daily_limit=new_daily_limit,
            new_end_date=new_end_date,
        )

        if not edit_success:
            return {"success": False, "error": "superap.io campaign edit failed"}

        # Fix 1: Build extension history entry
        history_entry = {
            "extended_at": datetime.now(timezone.utc).isoformat(),
            "previous_total_limit": campaign.total_limit,
            "new_total_limit": updated_total,
            "previous_end_date": str(campaign.end_date),
            "new_end_date": str(new_end_date),
            "added_quantity": additional_total,
        }

        # Load existing history
        existing_history: list = []
        if campaign.extension_history:
            try:
                existing_history = (
                    json.loads(campaign.extension_history)
                    if isinstance(campaign.extension_history, str)
                    else campaign.extension_history
                )
            except (json.JSONDecodeError, TypeError):
                existing_history = []
        existing_history.append(history_entry)

        # Update DB with extension_history
        async with async_session_factory() as session:
            await session.execute(
                update(Campaign)
                .where(Campaign.id == campaign_id)
                .values(
                    total_limit=updated_total,
                    end_date=new_end_date,
                    daily_limit=new_daily_limit or campaign.daily_limit,
                    extension_history=json.dumps(existing_history, ensure_ascii=False),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        await _send_callback(campaign_id, "extended")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "new_total_limit": updated_total,
            "new_end_date": str(new_end_date),
        }

    except Exception as e:
        logger.exception(f"Campaign {campaign_id} extension failed")
        return {"success": False, "error": str(e)}
    finally:
        if client:
            try:
                await client.close()
            except Exception:
                pass
