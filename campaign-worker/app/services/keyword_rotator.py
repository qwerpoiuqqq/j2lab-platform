"""Keyword rotation service with APScheduler.

Runs every 10 minutes to rotate keywords for active campaigns.
Each cycle:
1. Query active superap accounts
2. Login to each account
3. Check each campaign's keyword usage
4. Rotate keywords that haven't been changed today
5. Sync campaign statuses from superap.io

Ported from reference/quantum-campaign/backend/app/services/scheduler.py
and keyword_rotation.py, adapted for async PostgreSQL.
"""

from __future__ import annotations

import logging
import random
import re
import traceback
from collections import deque
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.campaign import Campaign
from app.models.campaign_keyword_pool import CampaignKeywordPool
from app.models.superap_account import SuperapAccount
from app.services.superap_client import SuperapClient
from app.utils.crypto import decrypt_password
from app.utils.status_map import normalize_status

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

scheduler = AsyncIOScheduler(timezone=KST)

# ============================================================
# Scheduler state tracking (diagnostics)
# ============================================================
MAX_LOG_ENTRIES = 50

scheduler_state: Dict[str, Any] = {
    "last_run": None,
    "last_result": None,
    "last_error": None,
    "run_count": 0,
    "is_running": False,
    "recent_logs": deque(maxlen=MAX_LOG_ENTRIES),
}


def _log(level: str, msg: str) -> None:
    """Internal scheduler log."""
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] [{level}] {msg}"
    scheduler_state["recent_logs"].append(entry)
    getattr(logger, level.lower(), logger.info)(f"[Scheduler] {msg}")


def get_scheduler_state() -> Dict[str, Any]:
    """Return current scheduler state."""
    return {
        "is_running": scheduler_state["is_running"],
        "scheduler_active": scheduler.running if scheduler else False,
        "last_run": scheduler_state["last_run"],
        "last_result": scheduler_state["last_result"],
        "last_error": scheduler_state["last_error"],
        "run_count": scheduler_state["run_count"],
        "recent_logs": list(scheduler_state["recent_logs"]),
    }


def _was_rotated_today(
    last_keyword_change: Optional[datetime], today_kst: date
) -> bool:
    """Check if keywords were already rotated today (KST)."""
    if last_keyword_change is None:
        return False
    last_change = last_keyword_change
    if last_change.tzinfo is None:
        last_change = last_change.replace(tzinfo=timezone.utc)
    last_change_date = last_change.astimezone(KST).date()
    return last_change_date >= today_kst


# ============================================================
# Keyword rotation logic
# ============================================================


async def rotate_keywords_for_campaign(
    campaign_id: int,
    client: SuperapClient,
    trigger_type: str = "daily",
) -> dict:
    """Rotate keywords for a single campaign.

    1. Query unused keywords from pool
    2. Shuffle and select up to 255 chars
    3. Edit keywords on superap.io
    4. Mark selected keywords as used
    5. Update last_keyword_change

    Args:
        campaign_id: Campaign DB ID
        client: Logged-in SuperapClient instance
        trigger_type: "daily" or "time_2350"

    Returns:
        Result dict
    """
    async with async_session_factory() as session:
        # Load campaign
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            return {"success": False, "message": f"Campaign {campaign_id} not found"}
        if not campaign.campaign_code:
            return {"success": False, "message": "No campaign code"}

        # Check expiration
        today_kst = datetime.now(KST).date()
        if campaign.end_date and campaign.end_date < today_kst:
            return {"success": False, "message": "Campaign expired"}

        # Load account
        account_result = await session.execute(
            select(SuperapAccount).where(
                SuperapAccount.id == campaign.superap_account_id
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            return {"success": False, "message": "Account not found"}

        account_key = str(account.id)

        # Get unused keywords
        unused_result = await session.execute(
            select(CampaignKeywordPool).where(
                CampaignKeywordPool.campaign_id == campaign_id,
                CampaignKeywordPool.is_used.is_(False),
            )
        )
        unused_keywords = list(unused_result.scalars().all())

        recycled = False
        if not unused_keywords:
            # Check total pool
            total_result = await session.execute(
                select(CampaignKeywordPool).where(
                    CampaignKeywordPool.campaign_id == campaign_id,
                )
            )
            all_keywords = list(total_result.scalars().all())

            if not all_keywords:
                return {
                    "success": False,
                    "message": "Keyword pool is empty",
                    "remaining": 0,
                }

            # Reset all keywords for recycling
            _log(
                "INFO",
                f"Campaign {campaign.campaign_code}: recycling {len(all_keywords)} keywords",
            )
            for kw in all_keywords:
                kw.is_used = False
                kw.used_at = None
            await session.flush()
            recycled = True

            # Re-query unused
            unused_result2 = await session.execute(
                select(CampaignKeywordPool).where(
                    CampaignKeywordPool.campaign_id == campaign_id,
                    CampaignKeywordPool.is_used.is_(False),
                )
            )
            unused_keywords = list(unused_result2.scalars().all())

            if not unused_keywords:
                return {
                    "success": False,
                    "message": "No keywords available after recycling",
                    "remaining": 0,
                }

        # Shuffle and select within 255 chars
        random.shuffle(unused_keywords)
        selected: list[CampaignKeywordPool] = []
        current_length = 0
        for kw_pool in unused_keywords:
            keyword = kw_pool.keyword.strip()
            if not keyword:
                continue
            separator_len = 1 if selected else 0
            new_length = current_length + separator_len + len(keyword)
            if new_length <= 255:
                selected.append(kw_pool)
                current_length = new_length

        if not selected:
            return {"success": False, "message": "No selectable keywords"}

        keywords_str = ",".join([kw.keyword.strip() for kw in selected])

        # Edit on superap.io
        try:
            edit_success = await client.edit_campaign_keywords(
                account_id=account_key,
                campaign_code=campaign.campaign_code,
                new_keywords=keywords_str,
            )
        except Exception as e:
            logger.error(
                f"Campaign {campaign.campaign_code} superap keyword edit failed: {e}"
            )
            return {"success": False, "message": f"superap edit failed: {str(e)}"}

        if not edit_success:
            return {"success": False, "message": "superap keyword edit failed"}

        # Update keyword pool
        now = datetime.now(timezone.utc)
        for kw_pool in selected:
            kw_pool.is_used = True
            kw_pool.used_at = now

        # Update campaign last_keyword_change
        if trigger_type == "time_2350":
            today_kst_dt = datetime.now(KST)
            fixed_time = today_kst_dt.replace(
                hour=23, minute=50, second=0, microsecond=0
            )
            campaign.last_keyword_change = fixed_time.astimezone(timezone.utc)
        else:
            campaign.last_keyword_change = now

        await session.commit()

        # Count remaining
        remaining_result = await session.execute(
            select(CampaignKeywordPool).where(
                CampaignKeywordPool.campaign_id == campaign_id,
                CampaignKeywordPool.is_used.is_(False),
            )
        )
        remaining = len(list(remaining_result.scalars().all()))

        recycle_msg = " (recycled)" if recycled else ""
        _log(
            "INFO",
            f"Campaign {campaign.campaign_code} keyword rotation complete{recycle_msg}: "
            f"{len(selected)} used, {remaining} remaining",
        )

        return {
            "success": True,
            "message": f"Rotated {len(selected)} keywords{recycle_msg}",
            "keywords_used": len(selected),
            "keywords_str": keywords_str,
            "remaining": remaining,
            "recycled": recycled,
        }


# ============================================================
# Conversion threshold handling
# ============================================================

CONVERSION_THRESHOLD = 10000


async def _send_threshold_callback(
    campaign_id: int,
    event_type: str,
    message: str,
    new_campaign_id: Optional[int] = None,
) -> None:
    """Send conversion threshold event callback to api-server."""
    callback_url = (
        f"{settings.API_SERVER_URL}/internal/callback"
        f"/conversion-threshold/{campaign_id}"
    )
    payload: Dict[str, Any] = {
        "event_type": event_type,
        "message": message,
    }
    if new_campaign_id is not None:
        payload["new_campaign_id"] = new_campaign_id

    headers = {"X-Internal-Secret": settings.INTERNAL_API_SECRET}
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.post(
                callback_url, json=payload, headers=headers
            )
            if resp.status_code < 300:
                _log("INFO", f"Threshold callback sent for campaign {campaign_id}: {event_type}")
            else:
                _log(
                    "WARNING",
                    f"Threshold callback failed for campaign {campaign_id}: "
                    f"{resp.status_code} {resp.text}",
                )
    except Exception as e:
        _log("WARNING", f"Threshold callback error for campaign {campaign_id}: {e}")


async def _handle_conversion_threshold(
    session: AsyncSession,
    campaign: Campaign,
    client: SuperapClient,
) -> None:
    """Handle a campaign exceeding the conversion threshold.

    1. Find the next tier network preset (same company_id + campaign_type, higher tier_order).
    2. If a next network exists:
       - Mark current campaign as completed
       - Create a new campaign record with the next network + account
       - Trigger registration via campaign_registrar
       - Notify api-server
    3. If no next network:
       - Send warning notification (all networks exhausted)
    4. Set conversion_threshold_handled = True
    """
    _log(
        "INFO",
        f"Campaign {campaign.campaign_code} (id={campaign.id}) reached "
        f"{campaign.current_conversions} conversions, checking next network...",
    )

    try:
        # Query network_presets for next tier
        current_preset_row = await session.execute(
            text(
                "SELECT tier_order, company_id, campaign_type "
                "FROM network_presets WHERE id = :preset_id"
            ),
            {"preset_id": campaign.network_preset_id},
        )
        current_preset = current_preset_row.mappings().first()

        if not current_preset:
            _log(
                "WARNING",
                f"Campaign {campaign.id}: network_preset_id={campaign.network_preset_id} not found",
            )
            campaign.conversion_threshold_handled = True
            await _send_threshold_callback(
                campaign.id,
                "error",
                f"네트워크 프리셋(id={campaign.network_preset_id})을 찾을 수 없습니다.",
            )
            return

        current_tier = current_preset["tier_order"]
        company_id = current_preset["company_id"]
        c_type = current_preset["campaign_type"]

        # Find next tier network
        next_preset_row = await session.execute(
            text(
                "SELECT np.id as preset_id, np.name as preset_name, np.tier_order, "
                "sa.id as account_id, sa.user_id_superap "
                "FROM network_presets np "
                "JOIN superap_accounts sa ON sa.network_preset_id = np.id AND sa.is_active = true "
                "WHERE np.company_id = :company_id "
                "AND np.campaign_type = :campaign_type "
                "AND np.tier_order > :current_tier "
                "AND np.is_active = true "
                "ORDER BY np.tier_order ASC, sa.assignment_order ASC "
                "LIMIT 1"
            ),
            {
                "company_id": company_id,
                "campaign_type": c_type,
                "current_tier": current_tier,
            },
        )
        next_preset = next_preset_row.mappings().first()

        if not next_preset:
            # No more networks available
            _log(
                "WARNING",
                f"Campaign {campaign.id}: no next network after tier {current_tier} "
                f"(company={company_id}, type={c_type})",
            )
            campaign.conversion_threshold_handled = True
            await _send_threshold_callback(
                campaign.id,
                "exhausted",
                f"캠페인 '{campaign.place_name}'의 전환수가 {campaign.current_conversions}건을 "
                f"초과했으나 사용 가능한 다음 네트워크가 없습니다. (현재 tier: {current_tier})",
            )
            return

        # Create new campaign with next network
        _log(
            "INFO",
            f"Campaign {campaign.id}: switching to network '{next_preset['preset_name']}' "
            f"(tier {next_preset['tier_order']}, account {next_preset['user_id_superap']})",
        )

        new_campaign = Campaign(
            superap_account_id=next_preset["account_id"],
            order_item_id=campaign.order_item_id,
            place_id=campaign.place_id,
            extraction_job_id=campaign.extraction_job_id,
            agency_name=campaign.agency_name,
            place_name=campaign.place_name,
            place_url=campaign.place_url,
            campaign_type=campaign.campaign_type,
            start_date=datetime.now(KST).date(),
            end_date=campaign.end_date,
            daily_limit=campaign.daily_limit,
            total_limit=campaign.total_limit,
            current_conversions=0,
            landmark_name=campaign.landmark_name,
            step_count=campaign.step_count,
            module_context=campaign.module_context,
            original_keywords=campaign.original_keywords,
            status="pending",
            network_preset_id=next_preset["preset_id"],
            company_id=campaign.company_id,
        )
        session.add(new_campaign)
        await session.flush()  # get new_campaign.id

        # Copy keyword pool from original campaign
        kw_result = await session.execute(
            select(CampaignKeywordPool).where(
                CampaignKeywordPool.campaign_id == campaign.id
            )
        )
        original_keywords = kw_result.scalars().all()
        for kw in original_keywords:
            new_kw = CampaignKeywordPool(
                campaign_id=new_campaign.id,
                keyword=kw.keyword,
                is_used=False,
                used_at=None,
            )
            session.add(new_kw)

        # Mark current campaign as completed
        campaign.status = "completed"
        campaign.conversion_threshold_handled = True
        campaign.registration_message = (
            f"전환수 {campaign.current_conversions}건 초과 → "
            f"네트워크 '{next_preset['preset_name']}' (tier {next_preset['tier_order']})로 이관"
        )

        await session.flush()

        new_campaign_id = new_campaign.id
        _log(
            "INFO",
            f"New campaign {new_campaign_id} created for network "
            f"'{next_preset['preset_name']}'. Triggering registration...",
        )

        # Trigger registration for the new campaign
        try:
            from app.services.campaign_registrar import register_campaign
            reg_result = await register_campaign(new_campaign_id)
            if reg_result.get("success"):
                _log(
                    "INFO",
                    f"New campaign {new_campaign_id} registered: "
                    f"code={reg_result.get('campaign_code')}",
                )
            else:
                _log(
                    "WARNING",
                    f"New campaign {new_campaign_id} registration failed: "
                    f"{reg_result.get('error')}. Campaign remains in pending for retry.",
                )
        except Exception as reg_err:
            _log(
                "ERROR",
                f"New campaign {new_campaign_id} registration error: {reg_err}. "
                f"Campaign remains in pending for retry.",
            )

        # Send callback to api-server for notification
        await _send_threshold_callback(
            campaign.id,
            "switched",
            f"캠페인 '{campaign.place_name}'의 전환수가 {campaign.current_conversions}건을 초과하여 "
            f"네트워크 '{next_preset['preset_name']}' (tier {next_preset['tier_order']})로 자동 이관했습니다.",
            new_campaign_id=new_campaign_id,
        )

    except Exception as e:
        _log(
            "ERROR",
            f"Conversion threshold handling failed for campaign {campaign.id}: {e}\n"
            f"{traceback.format_exc()}",
        )
        # Don't set conversion_threshold_handled so it can be retried
        # But prevent infinite error loops by setting it if it's a data issue
        campaign.conversion_threshold_handled = True
        await _send_threshold_callback(
            campaign.id,
            "error",
            f"전환수 초과 네트워크 변경 처리 중 오류 발생: {str(e)[:200]}",
        )


# ============================================================
# Campaign status sync
# ============================================================


async def sync_campaign_statuses(
    account_id: int,
    client: SuperapClient,
) -> dict:
    """Sync campaign statuses and conversions from superap.io.

    Args:
        account_id: SuperapAccount DB ID
        client: Logged-in SuperapClient instance

    Returns:
        Result dict
    """
    account_key = str(account_id)

    async with async_session_factory() as session:
        result = await session.execute(
            select(Campaign).where(
                Campaign.superap_account_id == account_id,
                Campaign.campaign_code.isnot(None),
            )
        )
        campaigns = list(result.scalars().all())

        if not campaigns:
            return {"success": True, "synced_count": 0}

        synced_count = 0
        for campaign in campaigns:
            try:
                info = await client.get_campaign_status_with_conversions(
                    account_key, campaign.campaign_code
                )
                if not info:
                    continue

                changed = False
                raw_status = info.get("status", "")
                if raw_status:
                    new_status = normalize_status(raw_status)
                    if campaign.status != new_status:
                        _log(
                            "INFO",
                            f"Campaign {campaign.campaign_code} status: "
                            f"{campaign.status} -> {new_status}",
                        )
                        campaign.status = new_status
                        changed = True

                current_count = info.get("current_count", 0)
                if current_count is not None and campaign.current_conversions != current_count:
                    campaign.current_conversions = current_count
                    changed = True

                # Check conversion threshold (10,000)
                if (
                    campaign.current_conversions >= CONVERSION_THRESHOLD
                    and campaign.status == "active"
                    and not campaign.conversion_threshold_handled
                    and campaign.network_preset_id is not None
                ):
                    try:
                        await _handle_conversion_threshold(session, campaign, client)
                    except Exception as threshold_err:
                        logger.error(
                            f"Campaign {campaign.campaign_code} threshold handling error: "
                            f"{threshold_err}"
                        )
                    changed = True

                if changed:
                    synced_count += 1

            except Exception as e:
                logger.warning(
                    f"Campaign {campaign.campaign_code} status sync error: {e}"
                )

        if synced_count > 0:
            await session.commit()

        return {"success": True, "synced_count": synced_count}


# ============================================================
# Main scheduler job
# ============================================================


async def check_and_rotate_keywords() -> Dict[str, Any]:
    """Main scheduler job: rotate keywords for all active campaigns.

    Runs every 10 minutes:
    1. Query active superap accounts
    2. For each account, login and process campaigns
    3. Skip campaigns already rotated today or expired
    4. Sync statuses before rotating
    """
    scheduler_state["is_running"] = True
    scheduler_state["run_count"] += 1

    result_summary: Dict[str, Any] = {
        "accounts_processed": 0,
        "logins_ok": 0,
        "logins_failed": 0,
        "rotated": 0,
        "rotation_failed": 0,
        "skipped": 0,
        "errors": [],
    }

    client: Optional[SuperapClient] = None

    try:
        now_kst = datetime.now(KST)
        today_kst = now_kst.date()
        _log("INFO", f"Keyword check started: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} KST")

        # Load active accounts
        async with async_session_factory() as session:
            accounts_result = await session.execute(
                select(SuperapAccount).where(SuperapAccount.is_active.is_(True))
            )
            active_accounts = list(accounts_result.scalars().all())

        if not active_accounts:
            _log("INFO", "No active accounts")
            scheduler_state["last_result"] = result_summary
            return result_summary

        _log("INFO", f"Found {len(active_accounts)} active accounts")

        # Initialize browser
        client = SuperapClient(headless=settings.PLAYWRIGHT_HEADLESS)
        await client.initialize()
        _log("INFO", "Browser initialized")

        for account in active_accounts:
            account_key = str(account.id)

            # Load campaigns for this account (only active/pending_keyword_change)
            async with async_session_factory() as session:
                campaigns_result = await session.execute(
                    select(Campaign).where(
                        Campaign.superap_account_id == account.id,
                        Campaign.campaign_code.isnot(None),
                        Campaign.status.in_(["active", "pending_keyword_change"]),
                    )
                )
                account_campaigns = list(campaigns_result.scalars().all())

            if not account_campaigns:
                continue

            # Filter campaigns needing rotation
            campaigns_to_rotate = []
            for c in account_campaigns:
                if c.end_date and c.end_date < today_kst:
                    result_summary["skipped"] += 1
                    continue
                if _was_rotated_today(c.last_keyword_change, today_kst):
                    result_summary["skipped"] += 1
                    continue
                campaigns_to_rotate.append(c)

            if not campaigns_to_rotate:
                _log(
                    "INFO",
                    f"Account {account.user_id_superap}: "
                    f"all {len(account_campaigns)} campaigns already rotated today",
                )
                continue

            _log(
                "INFO",
                f"Account {account.user_id_superap}: "
                f"{len(campaigns_to_rotate)}/{len(account_campaigns)} campaigns to rotate",
            )
            result_summary["accounts_processed"] += 1

            # Login
            try:
                password = decrypt_password(account.password_encrypted)
                login_ok = await client.login(
                    account_key, account.user_id_superap, password
                )
                if not login_ok:
                    msg = f"Account {account.user_id_superap} login failed"
                    _log("ERROR", msg)
                    result_summary["logins_failed"] += 1
                    result_summary["errors"].append(msg)
                    continue
                _log("INFO", f"Account {account.user_id_superap} logged in")
                result_summary["logins_ok"] += 1
            except Exception as e:
                msg = f"Account {account.user_id_superap} login error: {e}"
                _log("ERROR", msg)
                result_summary["logins_failed"] += 1
                result_summary["errors"].append(msg)
                continue

            # Sync statuses first
            try:
                sync_result = await sync_campaign_statuses(account.id, client)
                if sync_result.get("success"):
                    _log(
                        "INFO",
                        f"Account {account.user_id_superap} status sync: "
                        f"{sync_result.get('synced_count', 0)} updated",
                    )
            except Exception as e:
                _log("WARNING", f"Account {account.user_id_superap} status sync error: {e}")

            # Reload campaigns after sync (statuses may have changed)
            async with async_session_factory() as session:
                refreshed_result = await session.execute(
                    select(Campaign).where(
                        Campaign.superap_account_id == account.id,
                        Campaign.campaign_code.isnot(None),
                        Campaign.status.in_(["active", "pending_keyword_change"]),
                    )
                )
                refreshed_campaigns = list(refreshed_result.scalars().all())

            # Re-filter for rotation eligibility
            campaigns_to_rotate = []
            for c in refreshed_campaigns:
                if c.end_date and c.end_date < today_kst:
                    continue
                if _was_rotated_today(c.last_keyword_change, today_kst):
                    continue
                campaigns_to_rotate.append(c)

            # Rotate keywords for each campaign
            for campaign in campaigns_to_rotate:
                try:
                    rot_result = await rotate_keywords_for_campaign(
                        campaign_id=campaign.id,
                        client=client,
                        trigger_type="daily",
                    )
                    if rot_result["success"]:
                        result_summary["rotated"] += 1
                        _log(
                            "INFO",
                            f"Campaign {campaign.campaign_code} ({campaign.place_name}) "
                            f"rotation OK: {rot_result['message']}",
                        )
                    else:
                        result_summary["rotation_failed"] += 1
                        msg = (
                            f"Campaign {campaign.campaign_code} ({campaign.place_name}) "
                            f"rotation failed: {rot_result['message']}"
                        )
                        _log("WARNING", msg)
                        result_summary["errors"].append(msg)
                except Exception as e:
                    result_summary["rotation_failed"] += 1
                    msg = (
                        f"Campaign {campaign.campaign_code} ({campaign.place_name}) "
                        f"error: {e}"
                    )
                    _log("ERROR", msg)
                    result_summary["errors"].append(msg)

            # Clean up account context
            try:
                await client.close_context(account_key)
            except Exception:
                pass

        _log("INFO", f"Keyword check complete: {result_summary}")
        scheduler_state["last_result"] = result_summary
        scheduler_state["last_error"] = None

    except Exception as e:
        err_msg = f"Global error: {e}\n{traceback.format_exc()}"
        _log("ERROR", err_msg)
        scheduler_state["last_error"] = err_msg
        result_summary["errors"].append(str(e))
    finally:
        scheduler_state["is_running"] = False
        scheduler_state["last_run"] = datetime.now(KST).isoformat()
        if client:
            try:
                await client.close()
            except Exception:
                pass

    return result_summary


# ============================================================
# Scheduler lifecycle
# ============================================================


async def retry_stuck_registrations() -> None:
    """Retry campaigns stuck in pending/queued state for >5 minutes.

    Runs every 5 minutes. Max 3 retries per campaign.
    Ported from reference/quantum-campaign scheduler.retry_stuck_registrations.
    """
    from app.services.campaign_registrar import register_campaign

    _log("INFO", "Checking for stuck registrations...")
    try:
        async with async_session_factory() as session:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=5)

            # Find stuck campaigns: pending, no campaign_code, not updated in 5+ min
            result = await session.execute(
                select(Campaign).where(
                    Campaign.status.in_(["pending", "queued"]),
                    Campaign.campaign_code.is_(None),
                    Campaign.updated_at < cutoff,
                )
            )
            stuck = list(result.scalars().all())

            if not stuck:
                _log("INFO", "No stuck registrations found")
                return

            _log("INFO", f"Found {len(stuck)} stuck registrations")
            retried = 0

            for campaign in stuck:
                # Check retry count from registration_message using regex
                retry_count = 0
                msg = campaign.registration_message or ""
                retry_matches = re.findall(r"\[retry:(\d+)]", msg)
                if retry_matches:
                    retry_count = max(int(m) for m in retry_matches)

                if retry_count >= 3:
                    _log("WARNING", f"Campaign {campaign.id} exceeded max retries (3), skipping")
                    continue

                next_attempt = retry_count + 1
                _log("INFO", f"Retrying stuck campaign {campaign.id} (attempt {next_attempt})")

                # Mark retry attempt before calling register
                async with async_session_factory() as update_session:
                    await update_session.execute(
                        update(Campaign)
                        .where(Campaign.id == campaign.id)
                        .values(
                            registration_message=f"{msg} [retry:{next_attempt}] attempting...",
                            updated_at=now,
                        )
                    )
                    await update_session.commit()

                try:
                    await register_campaign(campaign.id)
                    retried += 1
                except Exception as e:
                    _log("ERROR", f"Retry failed for campaign {campaign.id}: {e}")
                    async with async_session_factory() as update_session:
                        await update_session.execute(
                            update(Campaign)
                            .where(Campaign.id == campaign.id)
                            .values(
                                registration_message=f"{msg} [retry:{next_attempt}] {str(e)[:100]}",
                                updated_at=now,
                            )
                        )
                        await update_session.commit()

            _log("INFO", f"Stuck registration retry complete: {retried} retried")
    except Exception as e:
        _log("ERROR", f"retry_stuck_registrations error: {e}")


def start_scheduler() -> None:
    """Start the APScheduler with keyword rotation + registration retry jobs."""
    scheduler.add_job(
        check_and_rotate_keywords,
        trigger=IntervalTrigger(minutes=settings.ROTATION_INTERVAL_MINUTES),
        id="keyword_rotation",
        name="Keyword auto-rotation",
        replace_existing=True,
    )
    scheduler.add_job(
        retry_stuck_registrations,
        trigger=IntervalTrigger(minutes=5),
        id="retry_stuck",
        name="Retry stuck registrations",
        replace_existing=True,
    )
    from app.services.campaign_expiry_checker import check_expired_campaigns

    scheduler.add_job(
        check_expired_campaigns,
        trigger=CronTrigger(hour=0, minute=30, timezone=KST),
        id="campaign_expiry_check",
        name="Campaign expiry auto-complete",
        replace_existing=True,
    )
    scheduler.start()
    _log(
        "INFO",
        f"APScheduler started (keyword rotation every {settings.ROTATION_INTERVAL_MINUTES} min, retry every 5 min)",
    )


def stop_scheduler() -> None:
    """Stop the APScheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        _log("INFO", "APScheduler stopped")
