from django.db import models
from django.conf import settings
from decimal import Decimal


class Order(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', '접수완료'
        PROCESSING = 'processing', '작업중'
        COMPLETED = 'completed', '완료'
        CANCELLED = 'cancelled', '취소'

    order_number = models.CharField(
        max_length=30, unique=True, verbose_name='주문번호',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders', verbose_name='주문자',
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT,
        related_name='orders', verbose_name='상품',
    )
    status = models.CharField(
        max_length=15, choices=Status.choices,
        default=Status.SUBMITTED, verbose_name='상태',
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=0, default=Decimal('0'),
        verbose_name='총 금액',
    )
    item_count = models.PositiveIntegerField(default=0, verbose_name='건수')
    total_quantity = models.PositiveIntegerField(default=0, verbose_name='총 수량')
    deadline = models.DateField(
        null=True, blank=True, verbose_name='마감일',
        help_text='리워드 상품 만료 날짜',
    )
    memo = models.TextField(blank=True, verbose_name='메모')
    confirmed_at = models.DateTimeField(
        null=True, blank=True, verbose_name='입금확인 시각',
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='confirmed_orders',
        verbose_name='입금확인자',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_orders',
        verbose_name='승인자',
    )
    approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name='승인 시각',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='주문일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    class Meta:
        verbose_name = '주문'
        verbose_name_plural = '주문'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} ({self.get_status_display()})"


class OrderItem(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', '대기'
        PROCESSING = 'processing', '처리중'
        COMPLETED = 'completed', '완료'
        FAILED = 'failed', '실패'

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='items', verbose_name='주문',
    )
    row_number = models.PositiveIntegerField(verbose_name='행 번호')
    data = models.JSONField(default=dict, verbose_name='입력 데이터')
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name='단가',
    )
    status = models.CharField(
        max_length=15, choices=Status.choices,
        default=Status.PENDING, verbose_name='상태',
    )
    result_message = models.TextField(blank=True, verbose_name='처리 결과')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')

    class Meta:
        verbose_name = '주문 항목'
        verbose_name_plural = '주문 항목'
        ordering = ['row_number']

    def __str__(self):
        return f"#{self.row_number} - {self.order.order_number}"


class BalanceTransaction(models.Model):
    class TxType(models.TextChoices):
        DEPOSIT = 'deposit', '충전'
        WITHDRAW = 'withdraw', '차감'
        REFUND = 'refund', '환불'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='balance_transactions', verbose_name='사용자',
    )
    tx_type = models.CharField(
        max_length=10, choices=TxType.choices, verbose_name='거래 유형',
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=0, verbose_name='금액',
    )
    balance_after = models.DecimalField(
        max_digits=12, decimal_places=0, verbose_name='거래 후 잔액',
    )
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transactions', verbose_name='관련 주문',
    )
    description = models.CharField(max_length=200, blank=True, verbose_name='설명')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_transactions',
        verbose_name='처리자',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='거래일')

    class Meta:
        verbose_name = '잔액 거래'
        verbose_name_plural = '잔액 거래'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} {self.get_tx_type_display()} {self.amount}원"
