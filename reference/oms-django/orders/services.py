import os
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from products.models import PricePolicy

from .models import Order, OrderItem

ORDER_MAX_ITEMS = int(os.getenv('ORDER_MAX_ITEMS', '5000'))


def get_user_price(product, user):
    default_price = product.cost_price if user.is_admin else product.base_price
    try:
        policy = PricePolicy.objects.get(product=product, user=user)
        return policy.price if policy.price is not None else default_price
    except PricePolicy.DoesNotExist:
        return default_price


def _parse_positive_int(raw_value, field_name):
    try:
        parsed = int(float(raw_value or 0))
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} 값이 올바르지 않습니다.')
    if parsed <= 0:
        raise ValueError(f'{field_name} 값은 1 이상이어야 합니다.')
    return parsed


@transaction.atomic
def create_order(user, product, items_data, memo=''):
    """주문 접수: 수량 * 단가 + 부가세 10%."""
    if not items_data:
        raise ValueError('주문 데이터가 비어 있습니다.')
    if len(items_data) > ORDER_MAX_ITEMS:
        raise ValueError(f'한 번에 최대 {ORDER_MAX_ITEMS}건까지 접수할 수 있습니다.')

    unit_price = get_user_price(product, user)

    qty_field = None
    for field in product.schema:
        if field.get('is_quantity'):
            qty_field = field['name']
            break

    if qty_field:
        total_qty = 0
        for idx, item in enumerate(items_data, start=1):
            qty = _parse_positive_int(item.get(qty_field), f'{idx}행 수량')
            total_qty += qty
    else:
        total_qty = len(items_data)

    if total_qty <= 0:
        raise ValueError('총 수량이 0보다 커야 합니다.')

    supply_amount = unit_price * total_qty
    vat_amount = (supply_amount * Decimal('0.1')).quantize(Decimal('1'))
    total_amount = supply_amount + vat_amount

    deadline_date = timezone.now().date() + timedelta(days=product.max_work_days)

    order = Order.objects.create(
        order_number='TEMP',
        user=user,
        product=product,
        total_amount=total_amount,
        item_count=len(items_data),
        total_quantity=total_qty,
        deadline=deadline_date,
        memo=memo,
        status=Order.Status.SUBMITTED,
    )
    order.order_number = str(order.pk)
    order.save(update_fields=['order_number'])

    order_items = [
        OrderItem(
            order=order,
            row_number=idx,
            data=data,
            unit_price=unit_price,
        )
        for idx, data in enumerate(items_data, start=1)
    ]
    OrderItem.objects.bulk_create(order_items)

    return order


@transaction.atomic
def confirm_payment(order, confirmed_by):
    """관리자의 입금 확인 처리."""
    if order.status != Order.Status.SUBMITTED:
        raise ValueError('접수완료 상태의 주문만 입금확인 처리할 수 있습니다.')

    order.status = Order.Status.PAID
    order.confirmed_at = timezone.now()
    order.confirmed_by = confirmed_by
    order.save(update_fields=['status', 'confirmed_at', 'confirmed_by', 'updated_at'])
    return order


@transaction.atomic
def cancel_order(order, cancelled_by):
    if order.status == Order.Status.CANCELLED:
        raise ValueError('이미 취소된 주문입니다.')

    order.status = Order.Status.CANCELLED
    order.save(update_fields=['status', 'updated_at'])
    return order
