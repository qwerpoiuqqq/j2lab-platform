#!/usr/bin/env python3
"""Migrate quantum.db (SQLite) data → unified platform PostgreSQL.

Usage (inside api-server container):
  python /scripts/migrate-quantum-data.py /path/to/quantum.db

Maps:
  quantum accounts → superap_accounts (with company_id from user_id pattern)
  quantum campaigns → campaigns (with company_id from account mapping)
  quantum keyword_pool → campaign_keyword_pool
  quantum campaign_templates → campaign_templates
"""

import asyncio
import sqlite3
import sys
from datetime import datetime, date

# ------------------------------------------------------------------
# Company mapping: superap account user_id → company code
# ------------------------------------------------------------------
def detect_company(user_id: str) -> str:
    """Detect company from superap account user_id."""
    uid = user_id.strip()
    if "일류기획" in uid or "일류" in uid:
        return "ilryu"
    if "제이투랩" in uid or "제이투" in uid:
        return "j2lab"
    # 기본값: 제이투랩
    return "j2lab"


async def migrate(sqlite_path: str):
    from sqlalchemy import select, text
    from app.core.database import async_session_factory
    from app.core.security import hash_password
    from app.models.company import Company
    from app.models.superap_account import SuperapAccount
    from app.models.campaign import Campaign
    from app.models.campaign_keyword_pool import CampaignKeywordPool
    from app.models.campaign_template import CampaignTemplate

    # Read SQLite data
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Load quantum data
    q_accounts = [dict(r) for r in c.execute("SELECT * FROM accounts").fetchall()]
    q_campaigns = [dict(r) for r in c.execute("SELECT * FROM campaigns").fetchall()]
    q_keywords = [dict(r) for r in c.execute("SELECT * FROM keyword_pool").fetchall()]
    q_templates = [dict(r) for r in c.execute("SELECT * FROM campaign_templates").fetchall()]
    conn.close()

    print(f"Quantum data loaded: {len(q_accounts)} accounts, {len(q_campaigns)} campaigns, {len(q_keywords)} keywords, {len(q_templates)} templates")

    async with async_session_factory() as session:
        # --- Load companies ---
        companies = {}
        result = await session.execute(select(Company))
        for co in result.scalars().all():
            companies[co.code] = co
        print(f"Companies in DB: {list(companies.keys())}")

        if "ilryu" not in companies or "j2lab" not in companies:
            print("[ERROR] Companies 일류기획(ilryu) and 제이투랩(j2lab) must exist. Run seed-data.sh first.")
            return

        # --- Check if already migrated ---
        existing_count = await session.execute(
            select(Campaign).limit(1)
        )
        if existing_count.scalar_one_or_none():
            # Check if it looks like quantum data
            code_check = await session.execute(
                select(Campaign).where(Campaign.campaign_code.isnot(None)).limit(1)
            )
            if code_check.scalar_one_or_none():
                print("[SKIP] Campaign data already exists (appears to be migrated)")
                return

        # --- Migrate accounts ---
        account_map = {}  # quantum account_id → new superap_account_id
        for qa in q_accounts:
            company_code = detect_company(qa["user_id"])
            company = companies[company_code]

            # Check if account already exists
            existing = await session.execute(
                select(SuperapAccount).where(SuperapAccount.user_id == qa["user_id"])
            )
            if sa := existing.scalar_one_or_none():
                account_map[qa["id"]] = sa.id
                print(f"  [EXIST] Account {qa['user_id']} → id={sa.id}")
                continue

            new_account = SuperapAccount(
                user_id=qa["user_id"],
                password_encrypted=qa.get("password_encrypted", ""),
                agency_name=qa.get("agency_name") or company.name,
                is_active=bool(qa.get("is_active", True)),
                company_id=company.id,
            )
            session.add(new_account)
            await session.flush()
            account_map[qa["id"]] = new_account.id
            print(f"  [OK] Account {qa['user_id']} → id={new_account.id} (company={company_code})")

        # --- Migrate templates ---
        template_map = {}
        for qt in q_templates:
            existing = await session.execute(
                select(CampaignTemplate).where(CampaignTemplate.type_name == qt["type_name"])
            )
            if st := existing.scalar_one_or_none():
                template_map[qt["id"]] = st.id
                continue

            import json
            new_template = CampaignTemplate(
                type_name=qt["type_name"],
                description_template=qt.get("description_template", ""),
                hint_text=qt.get("hint_text", ""),
                campaign_type_selection=qt.get("campaign_type_selection"),
                links=json.loads(qt["links"]) if qt.get("links") else [],
                hashtag=qt.get("hashtag"),
                image_url_200x600=qt.get("image_url_200x600"),
                image_url_720x780=qt.get("image_url_720x780"),
                modules=json.loads(qt["modules"]) if qt.get("modules") else [],
                is_active=bool(qt.get("is_active", True)),
                conversion_text_template=qt.get("conversion_text_template"),
            )
            session.add(new_template)
            await session.flush()
            template_map[qt["id"]] = new_template.id
            print(f"  [OK] Template {qt['type_name']} → id={new_template.id}")

        # --- Migrate campaigns ---
        campaign_map = {}  # quantum campaign_id → new campaign_id
        campaign_type_map = {"트래픽": "traffic", "저장하기": "save", "저장": "save", "랜드마크": "landmark"}
        skipped = 0

        for qc in q_campaigns:
            # Determine company from account
            account_id = qc.get("account_id")
            new_account_id = account_map.get(account_id) if account_id else None

            # Determine company_id from account's company
            company_id = None
            if new_account_id:
                acct_result = await session.execute(
                    select(SuperapAccount).where(SuperapAccount.id == new_account_id)
                )
                acct = acct_result.scalar_one_or_none()
                if acct:
                    company_id = acct.company_id

            # If no company, default to j2lab
            if company_id is None:
                company_id = companies["j2lab"].id

            # Map campaign_type
            raw_type = qc.get("campaign_type", "traffic")
            campaign_type = campaign_type_map.get(raw_type, raw_type)

            # Parse dates
            def parse_date(val):
                if not val:
                    return date.today()
                if isinstance(val, date):
                    return val
                try:
                    return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    return date.today()

            # Parse extension_history
            import json
            ext_history = None
            if qc.get("extension_history"):
                try:
                    ext_history = json.loads(qc["extension_history"])
                except (json.JSONDecodeError, TypeError):
                    pass

            new_campaign = Campaign(
                campaign_code=qc.get("campaign_code"),
                superap_account_id=new_account_id,
                agency_name=qc.get("agency_name"),
                place_name=qc.get("place_name", ""),
                place_url=qc.get("place_url", ""),
                campaign_type=campaign_type,
                start_date=parse_date(qc.get("start_date")),
                end_date=parse_date(qc.get("end_date")),
                daily_limit=qc.get("daily_limit", 300),
                total_limit=qc.get("total_limit"),
                current_conversions=qc.get("current_conversions", 0),
                landmark_name=qc.get("landmark_name"),
                step_count=qc.get("step_count"),
                original_keywords=qc.get("original_keywords"),
                status=qc.get("status", "pending"),
                registration_step=qc.get("registration_step"),
                registration_message=qc.get("registration_message"),
                extend_target_id=qc.get("extend_target_id"),
                extension_history=ext_history,
                last_keyword_change=datetime.fromisoformat(qc["last_keyword_change"]) if qc.get("last_keyword_change") else None,
                company_id=company_id,
                # managed_by is NULL — admin can assign handlers later
            )
            session.add(new_campaign)
            await session.flush()
            campaign_map[qc["id"]] = new_campaign.id

        print(f"  [OK] Migrated {len(campaign_map)} campaigns")

        # --- Migrate keywords (batch) ---
        batch = []
        batch_size = 500
        migrated_kw = 0
        for qk in q_keywords:
            new_campaign_id = campaign_map.get(qk.get("campaign_id"))
            if not new_campaign_id:
                continue

            batch.append(CampaignKeywordPool(
                campaign_id=new_campaign_id,
                keyword=qk.get("keyword", ""),
                is_used=bool(qk.get("is_used", False)),
                used_at=datetime.fromisoformat(qk["used_at"]) if qk.get("used_at") else None,
                round_number=1,
            ))
            migrated_kw += 1

            if len(batch) >= batch_size:
                session.add_all(batch)
                await session.flush()
                batch = []

        if batch:
            session.add_all(batch)
            await session.flush()

        print(f"  [OK] Migrated {migrated_kw} keywords")

        await session.commit()
        print()
        print("=== Migration complete! ===")
        print(f"  Accounts: {len(account_map)}")
        print(f"  Templates: {len(template_map)}")
        print(f"  Campaigns: {len(campaign_map)}")
        print(f"  Keywords: {migrated_kw}")
        print()
        print("  NOTE: managed_by is NULL for all campaigns.")
        print("  Assign handlers via admin panel or:")
        print("    UPDATE campaigns SET managed_by = '<user_uuid>' WHERE agency_name = '...'")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate-quantum-data.py /path/to/quantum.db")
        sys.exit(1)
    asyncio.run(migrate(sys.argv[1]))
