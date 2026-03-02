from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from orders.services import create_order
from products.models import Product


class OrderServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller1', password='pw', role=User.Role.SELLER)
        self.product = Product.objects.create(
            name='테스트 상품',
            base_price=Decimal('1000'),
            cost_price=Decimal('800'),
            schema=[
                {'name': 'url', 'type': 'url', 'required': True},
                {'name': 'qty', 'type': 'number', 'required': True, 'is_quantity': True},
            ],
            max_work_days=3,
        )

    def test_create_order_calculates_supply_and_vat(self):
        order = create_order(
            self.user,
            self.product,
            [
                {'url': 'https://a.test', 'qty': '2'},
                {'url': 'https://b.test', 'qty': '3'},
            ],
        )
        self.assertEqual(order.total_quantity, 5)
        self.assertEqual(order.item_count, 2)
        self.assertEqual(int(order.total_amount), 5500)

    def test_create_order_rejects_non_positive_quantity(self):
        with self.assertRaisesMessage(ValueError, '1행 수량 값은 1 이상이어야 합니다.'):
            create_order(self.user, self.product, [{'url': 'https://a.test', 'qty': '0'}])

    def test_create_order_rejects_oversized_batch(self):
        with patch('orders.services.ORDER_MAX_ITEMS', 1):
            with self.assertRaisesMessage(ValueError, '한 번에 최대 1건까지 접수할 수 있습니다.'):
                create_order(
                    self.user,
                    self.product,
                    [
                        {'url': 'https://a.test', 'qty': '1'},
                        {'url': 'https://b.test', 'qty': '1'},
                    ],
                )


class SettlementSecretTests(TestCase):
    def test_settlement_secret_is_blocked_when_password_not_configured(self):
        admin = User.objects.create_user(username='admin1', password='pw', role=User.Role.ADMIN)
        self.client.login(username='admin1', password='pw')
        response = self.client.get(reverse('orders:settlement_secret'))
        self.assertRedirects(response, reverse('orders:settlement_list'))
