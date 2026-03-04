"""Campaign status synchronization service.

Checks superap.io for the current status of active campaigns
and updates the database accordingly. Handles expired/paused campaigns.

Ported from reference/quantum-campaign/backend/app/services/keyword_rotation.py
(sync functions), adapted for async PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.campaign import Campaign
from app.models.superap_account import SuperapAccount
from app.services.superap_client import SuperapClient
from app.utils.crypto import decrypt_password
from app.utils.status_map import normalize_status

logger = logging.getLogger(__name__)


async def sync_single_campaign(
    campaign_id: int,
    client: SuperapClient,
) -> dict:
    """Sync status for a single campaign from superap.io.

    Args:
        campaign_id: Campaign DB ID
        client: Logged-in SuperapClient instance

    Returns:
        Result dict
    """
    async with async_session_factory() as session:
        result = await session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            return {"success": False, "message": f"Campaign {campaign_id} not found"}
        if not campaign.campaign_code:
            return {"success": False, "message": "No campaign code"}

        account_result = await session.execute(
            select(SuperapAccount).where(
                SuperapAccount.id == campaign.superap_account_id
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            return {"success": False, "message": "Account not found"}

        account_key = str(account.id)

        try:
            info = await client.get_campaign_status_with_conversions(
                account_key, campaign.campaign_code
            )
        except Exception as e:
            return {"success": False, "message": f"Status query failed: {str(e)}"}

        if not info:
            return {"success": False, "message": "Cannot get status"}

        previous_status = campaign.status
        raw_status = info.get("status", "")
        new_status = normalize_status(raw_status) if raw_status else campaign.status

        changed = False
        if raw_status and campaign.status != new_status:
            campaign.status = new_status
            changed = True

        current_count = info.get("current_count", 0)
        if current_count is not None and campaign.current_conversions != current_count:
            campaign.current_conversions = current_count
            changed = True

        if changed:
            campaign.updated_at = datetime.now(timezone.utc)
            await session.commit()

        logger.info(
            f"Campaign {campaign.campaign_code} sync: {previous_status} -> {new_status}"
        )

        return {
            "success": True,
            "status": new_status,
            "previous_status": previous_status,
            "current_conversions": current_count,
        }


async def bulk_sync_campaigns(
    account_ids: Optional[List[int]] = None,
) -> dict:
    """Sync all active campaigns, optionally filtered by account IDs.

    For each account:
    1. Login to superap.io
    2. Query each campaign's status
    3. Update DB

    Args:
        account_ids: Optional list of account IDs to sync.
                     If None, syncs all active accounts.

    Returns:
        Result dict with total synced count
    """
    client: Optional[SuperapClient] = None

    try:
        # Load accounts
        async with async_session_factory() as session:
            if account_ids:
                accounts_result = await session.execute(
                    select(SuperapAccount).where(
                        SuperapAccount.id.in_(account_ids),
                        SuperapAccount.is_active.is_(True),
                    )
                )
            else:
                accounts_result = await session.execute(
                    select(SuperapAccount).where(
                        SuperapAccount.is_active.is_(True),
                    )
                )
            accounts = list(accounts_result.scalars().all())

        if not accounts:
            return {"success": True, "synced_count": 0, "message": "No active accounts"}

        client = SuperapClient(headless=True)
        await client.initialize()

        from app.services.keyword_rotator import sync_campaign_statuses

        total_synced = 0
        errors: list[str] = []

        for account in accounts:
            account_key = str(account.id)
            try:
                password = decrypt_password(account.password_encrypted)
                login_ok = await client.login(
                    account_key, account.user_id_superap, password
                )
                if not login_ok:
                    errors.append(f"Account {account.user_id_superap} login failed")
                    continue

                result = await sync_campaign_statuses(account.id, client)
                total_synced += result.get("synced_count", 0)
            except Exception as e:
                errors.append(f"Account {account.id} sync error: {e}")
            finally:
                try:
                    await client.close_context(account_key)
                except Exception:
                    pass

        return {
            "success": True,
            "synced_count": total_synced,
            "accounts_processed": len(accounts),
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.exception(f"Bulk sync failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if client:
            try:
                await client.close()
            except Exception:
                pass
