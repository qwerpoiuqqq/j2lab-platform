#!/usr/bin/env bash
# =============================================================================
# J2LAB Platform - Seed Initial Data
# =============================================================================
# Creates:
#   - 2 companies: 일류기획 (ilryu), 제이투랩 (j2lab)
#   - 1 system_admin user: admin@j2lab.com / admin123!
#
# Usage:
#   # From host (docker compose must be running with api-server)
#   ./scripts/seed-data.sh
#
#   # Change default admin password via env var
#   ADMIN_PASSWORD=MySecurePassword123! ./scripts/seed-data.sh
# =============================================================================

set -euo pipefail

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@j2lab.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123!}"
ADMIN_NAME="${ADMIN_NAME:-시스템관리자}"

echo "=========================================="
echo "  J2LAB Platform - Seed Initial Data"
echo "=========================================="

# Run seed logic inside the api-server container
docker compose exec -T api-server python -c "
import asyncio
import sys

async def seed():
    from sqlalchemy import select, text
    from app.core.database import async_session_factory
    from app.core.security import hash_password
    from app.models.company import Company
    from app.models.user import User

    async with async_session_factory() as session:
        # --- Check if data already exists ---
        result = await session.execute(select(Company).limit(1))
        if result.scalar_one_or_none():
            print('[SKIP] Seed data already exists')
            return

        # --- Create companies ---
        company_ilryu = Company(
            name='일류기획',
            code='ilryu',
            is_active=True,
        )
        company_j2lab = Company(
            name='제이투랩',
            code='j2lab',
            is_active=True,
        )
        session.add_all([company_ilryu, company_j2lab])
        await session.flush()

        print(f'[OK] Company created: 일류기획 (id={company_ilryu.id})')
        print(f'[OK] Company created: 제이투랩 (id={company_j2lab.id})')

        # --- Create system_admin user ---
        admin_user = User(
            email='${ADMIN_EMAIL}',
            hashed_password=hash_password('${ADMIN_PASSWORD}'),
            name='${ADMIN_NAME}',
            role='system_admin',
            company_id=company_j2lab.id,
            is_active=True,
        )
        session.add(admin_user)
        await session.flush()

        print(f'[OK] User created: ${ADMIN_EMAIL} (system_admin, id={admin_user.id})')

        await session.commit()
        print('')
        print('[OK] Seed data created successfully!')
        print('')
        print('  Login credentials:')
        print('    Email:    ${ADMIN_EMAIL}')
        print('    Password: ${ADMIN_PASSWORD}')
        print('')
        print('  ** IMPORTANT: Change the admin password after first login! **')

asyncio.run(seed())
"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "  Seed Complete!"
    echo "=========================================="
else
    echo ""
    echo "[ERROR] Seed data creation failed"
    exit 1
fi
