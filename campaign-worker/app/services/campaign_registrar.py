"""Campaign registration orchestration service.

Receives registration requests from api-server, decrypts superap credentials,
fills the campaign form via Playwright, submits it, and updates the DB.

Ported from reference/quantum-campaign/backend/app/services/campaign_registration.py
and auto_registration.py, adapted for async PostgreSQL.
"""

from __future__ import annotations

import asyncio
import logging
import re
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
from app.utils.crypto import decrypt_password
from app.utils.template_vars import apply_template_variables

logger = logging.getLogger(__name__)

# Concurrent registration lock
_registration_lock = asyncio.Lock()


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


async def _send_callback(campaign_id: int, status: str, message: str = "") -> None:
    """Send completion callback to api-server."""
    callback_url = (
        f"{settings.API_SERVER_URL}/internal/callback/campaign/{campaign_id}"
    )
    payload = {"status": status, "message": message}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(callback_url, json=payload)
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


async def register_campaign(campaign_id: int) -> dict:
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

        # Load superap account
        account_stmt = select(SuperapAccount).where(
            SuperapAccount.id == campaign.superap_account_id
        )
        account_result = await session.execute(account_stmt)
        account = account_result.scalar_one_or_none()

        if not account:
            await _update_step(
                session, campaign_id, "failed",
                f"Superap account {campaign.superap_account_id} not found",
            )
            await _send_callback(campaign_id, "failed", "Account not found")
            return {"success": False, "error": "Account not found"}

        # Load template
        template_stmt = select(CampaignTemplate).where(
            CampaignTemplate.code == campaign.campaign_type,
            CampaignTemplate.is_active.is_(True),
        )
        template_result = await session.execute(template_stmt)
        template = template_result.scalar_one_or_none()

        if not template:
            await _update_step(
                session, campaign_id, "failed",
                f"Template not found for type: {campaign.campaign_type}",
            )
            await _send_callback(campaign_id, "failed", "Template not found")
            return {"success": False, "error": "Template not found"}

    # Perform Playwright automation outside the DB session
    client: Optional[SuperapClient] = None
    try:
        client = SuperapClient(headless=settings.PLAYWRIGHT_HEADLESS)
        await client.initialize()

        account_key = str(account.id)

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
            await _send_callback(campaign_id, "failed", "Login failed")
            return {"success": False, "error": "Login failed"}

        # Step 2: Prepare form data
        async with async_session_factory() as session:
            await _update_step(session, campaign_id, "filling_form", "Preparing form data...")

        masked_place_name = _mask_place_name(campaign.place_name)
        context = {
            "place_name": masked_place_name,
            "place_url": campaign.place_url,
            "landmark_name": campaign.landmark_name or "",
            "steps": campaign.step_count or 0,
        }

        description = apply_template_variables(
            template.description_template, context
        )
        hint = apply_template_variables(template.hint_text, {
            "place_name": campaign.place_name,
            "landmark_name": campaign.landmark_name or "",
            "steps": campaign.step_count or 0,
        })

        superap_campaign_type = template.campaign_type_selection or "플레이스 퀴즈"
        campaign_name = _generate_campaign_name(
            campaign.place_name, superap_campaign_type
        )

        keywords = [
            kw.strip()
            for kw in (campaign.original_keywords or "").split(",")
            if kw.strip()
        ]

        conversion_text = None
        if template.conversion_text_template:
            conversion_text = apply_template_variables(
                template.conversion_text_template,
                {
                    "place_name": campaign.place_name,
                    "landmark_name": campaign.landmark_name or "",
                    "steps": campaign.step_count or 0,
                },
            )

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
            links=template.links or [],
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
            await _send_callback(campaign_id, "failed", error_msg)
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
            await _send_callback(campaign_id, "failed", error_msg)
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

            await session.execute(
                update(Campaign)
                .where(Campaign.id == campaign_id)
                .values(
                    campaign_code=campaign_code,
                    status="active",
                    registration_step="completed",
                    registration_message=f"Registered: code {campaign_code}",
                    registered_at=now,
                    last_keyword_change=now,
                    updated_at=now,
                )
            )
            await session.commit()

        await _send_callback(campaign_id, "completed", f"Campaign code: {campaign_code}")

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
        await _send_callback(campaign_id, "failed", error_msg)
        return {"success": False, "error": error_msg}
    except SuperapCampaignError as e:
        error_msg = f"Superap error: {str(e)}"
        async with async_session_factory() as session:
            await _update_step(session, campaign_id, "failed", error_msg)
        await _send_callback(campaign_id, "failed", error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.exception(f"Campaign {campaign_id} registration failed")
        async with async_session_factory() as session:
            await _update_step(session, campaign_id, "failed", error_msg)
        await _send_callback(campaign_id, "failed", error_msg)
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

        # Update DB
        async with async_session_factory() as session:
            await session.execute(
                update(Campaign)
                .where(Campaign.id == campaign_id)
                .values(
                    total_limit=updated_total,
                    end_date=new_end_date,
                    daily_limit=new_daily_limit or campaign.daily_limit,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        await _send_callback(
            campaign_id, "extended",
            f"Extended: total={updated_total}, end_date={new_end_date}",
        )

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
