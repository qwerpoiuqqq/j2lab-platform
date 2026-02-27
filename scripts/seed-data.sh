#!/usr/bin/env bash
# =============================================================================
# J2LAB Platform - Seed Initial Data
# =============================================================================
# Creates:
#   - 2 companies: 일류기획 (ilryu), 제이투랩 (j2lab)
#   - 1 system_admin user: admin@jtwolab.kr / jjlab1234!j
#   - 4 categories: 트래픽, 저장, 자동완성, 영수증
#   - 4 products: traffic_30, save_30, traffic_60, save_60
#   - Role-based price policies for distributor / sub_account
#   - 3 additional users: company_admin, order_handler, distributor
#
# Usage:
#   # From host (docker compose must be running with api-server)
#   ./scripts/seed-data.sh
#
#   # Change default admin password via env var
#   ADMIN_PASSWORD=MySecurePassword123! ./scripts/seed-data.sh
# =============================================================================

set -euo pipefail

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@jtwolab.kr}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-jjlab1234!j}"
ADMIN_NAME="${ADMIN_NAME:-시스템관리자}"

echo "=========================================="
echo "  J2LAB Platform - Seed Initial Data"
echo "=========================================="

# Run seed logic inside the api-server container
docker compose exec -T api-server python -c "
import asyncio
import sys

async def seed():
    from datetime import date
    from sqlalchemy import select, text
    from app.core.database import async_session_factory
    from app.core.security import hash_password
    from app.models.company import Company
    from app.models.user import User
    from app.models.category import Category
    from app.models.product import Product
    from app.models.price_policy import PricePolicy

    async with async_session_factory() as session:
        # --- Check if companies already exist ---
        result = await session.execute(select(Company).limit(1))
        if result.scalar_one_or_none():
            print('[SKIP] Companies already exist')
        else:
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

        # --- Create categories (skip if already exist) ---
        result = await session.execute(select(Category).limit(1))
        if result.scalar_one_or_none():
            print('[SKIP] Categories already exist')
        else:
            categories_data = [
                {'name': '트래픽', 'sort_order': 1},
                {'name': '저장', 'sort_order': 2},
                {'name': '자동완성', 'sort_order': 3},
                {'name': '영수증', 'sort_order': 4},
            ]
            for cat_data in categories_data:
                cat = Category(name=cat_data['name'], sort_order=cat_data['sort_order'], is_active=True)
                session.add(cat)
            await session.flush()
            print('[OK] Categories created: 트래픽, 저장, 자동완성, 영수증')

        # --- Create products (skip if already exist) ---
        result = await session.execute(select(Product).limit(1))
        if result.scalar_one_or_none():
            print('[SKIP] Products already exist')
        else:
            form_schema = {
                'fields': [
                    {'key': 'place_url', 'type': 'url', 'label': '플레이스 URL', 'required': True},
                    {'key': 'campaign_type', 'type': 'select', 'label': '캠페인 유형', 'required': True, 'options': ['traffic', 'save']},
                    {'key': 'duration_days', 'type': 'number', 'label': '기간(일)', 'required': True},
                    {'key': 'daily_limit', 'type': 'number', 'label': '일일 한도', 'required': True},
                    {'key': 'total_limit', 'type': 'number', 'label': '총 한도', 'required': True},
                    {'key': 'place_name', 'type': 'text', 'label': '업체명', 'required': False},
                ]
            }

            products_data = [
                {'name': '트래픽 30일', 'code': 'traffic_30', 'category': '트래픽', 'base_price': 300000},
                {'name': '저장 30일', 'code': 'save_30', 'category': '저장', 'base_price': 250000},
                {'name': '트래픽 60일', 'code': 'traffic_60', 'category': '트래픽', 'base_price': 550000},
                {'name': '저장 60일', 'code': 'save_60', 'category': '저장', 'base_price': 450000},
            ]

            product_objects = []
            for p_data in products_data:
                prod = Product(
                    name=p_data['name'],
                    code=p_data['code'],
                    category=p_data['category'],
                    base_price=p_data['base_price'],
                    form_schema=form_schema,
                    is_active=True,
                )
                session.add(prod)
                product_objects.append((prod, p_data['base_price']))
            await session.flush()

            for prod, bp in product_objects:
                print(f'[OK] Product created: {prod.name} (code={prod.code}, id={prod.id})')

            # --- Create role-based price policies ---
            today = date.today()
            for prod, base_price in product_objects:
                # distributor: 85% of base price
                dist_policy = PricePolicy(
                    product_id=prod.id,
                    role='distributor',
                    unit_price=int(base_price * 0.85),
                    effective_from=today,
                )
                # sub_account: 90% of base price
                sub_policy = PricePolicy(
                    product_id=prod.id,
                    role='sub_account',
                    unit_price=int(base_price * 0.90),
                    effective_from=today,
                )
                session.add_all([dist_policy, sub_policy])
            await session.flush()
            print('[OK] Price policies created for distributor (85%) and sub_account (90%)')

        # --- Create additional users (skip if exist by email) ---
        additional_users = [
            {
                'email': 'ilryu_accountant@jtwolab.kr',
                'password': 'ilryu1234!',
                'name': '일류기획 경리',
                'role': 'company_admin',
                'company_code': 'ilryu',
            },
            {
                'email': 'j2lab_handler@jtwolab.kr',
                'password': 'j2lab1234!',
                'name': 'j2lab 담당자',
                'role': 'order_handler',
                'company_code': 'j2lab',
            },
            {
                'email': 'j2lab_distributor@jtwolab.kr',
                'password': 'j2lab1234!',
                'name': 'j2lab 총판',
                'role': 'distributor',
                'company_code': 'j2lab',
            },
        ]

        for u_data in additional_users:
            result = await session.execute(
                select(User).where(User.email == u_data['email']).limit(1)
            )
            if result.scalar_one_or_none():
                print(f'[SKIP] User already exists: {u_data[\"email\"]}')
                continue

            # Look up company
            result = await session.execute(
                select(Company).where(Company.code == u_data['company_code']).limit(1)
            )
            company = result.scalar_one_or_none()
            if not company:
                print(f'[ERROR] Company not found: {u_data[\"company_code\"]}')
                continue

            user = User(
                email=u_data['email'],
                hashed_password=hash_password(u_data['password']),
                name=u_data['name'],
                role=u_data['role'],
                company_id=company.id,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            print(f'[OK] User created: {u_data[\"email\"]} ({u_data[\"role\"]}, id={user.id})')

        await session.commit()
        print('')
        print('[OK] Seed data created successfully!')
        print('')
        print('  Login credentials:')
        print('    Admin:       ${ADMIN_EMAIL} / ${ADMIN_PASSWORD}')
        print('    Accountant:  ilryu_accountant@jtwolab.kr / ilryu1234!')
        print('    Handler:     j2lab_handler@jtwolab.kr / j2lab1234!')
        print('    Distributor: j2lab_distributor@jtwolab.kr / j2lab1234!')
        print('')
        print('  ** IMPORTANT: Change passwords after first login! **')

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
