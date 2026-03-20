from __future__ import annotations

from datetime import date, time

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.user import User
from tests.conftest import get_auth_header


async def create_test_product(db: AsyncSession) -> Product:
    product = Product(
        name="Traffic Campaign",
        code="traffic",
        base_price=10000,
        daily_deadline=time(18, 0),
        is_active=True,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


@pytest.mark.asyncio
class TestSettlementDailyCheck:
    async def test_company_admin_sees_distributor_total_quantity(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        company_admin: User,
        distributor: User,
        sub_account: User,
    ):
        from app.services import balance_service

        product = await create_test_product(db_session)
        await balance_service.deposit(
            db_session, distributor.id, 50000, "Initial deposit"
        )
        await db_session.commit()

        sub_headers = get_auth_header(sub_account)
        create_resp = await client.post(
            "/api/v1/orders/",
            json={
                "items": [{"product_id": product.id, "quantity": 3}],
            },
            headers=sub_headers,
        )
        assert create_resp.status_code == 201
        order_id = create_resp.json()["id"]

        submit_resp = await client.post(
            f"/api/v1/orders/{order_id}/submit",
            headers=sub_headers,
        )
        assert submit_resp.status_code == 200

        admin_headers = get_auth_header(company_admin)
        resp = await client.get(
            f"/api/v1/settlements/daily-check?date={date.today().isoformat()}",
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_quantity"] == 3
        distributor_row = next(
            row for row in data["distributors"]
            if row["distributor_id"] == str(distributor.id)
        )
        assert distributor_row["total_quantity"] == 3
        assert distributor_row["orders"][0]["total_quantity"] == 3
