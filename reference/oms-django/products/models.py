from django.db import models
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='카테고리명')
    icon = models.CharField(max_length=50, default='bi-grid', verbose_name='아이콘')
    display_order = models.PositiveIntegerField(default=0, verbose_name='표시 순서')
    is_active = models.BooleanField(default=True, verbose_name='활성')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')

    class Meta:
        verbose_name = '카테고리'
        verbose_name_plural = '카테고리'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products', verbose_name='카테고리',
    )
    name = models.CharField(max_length=200, verbose_name='상품명')
    description = models.TextField(blank=True, verbose_name='설명')
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=0, default=0,
        verbose_name='원가 (총 관리자 단가)',
    )
    base_price = models.DecimalField(
        max_digits=10, decimal_places=0, default=0,
        verbose_name='기본 단가 (대행사 기본 적용 단가)',
        help_text='업체별 개별 단가가 없을 때 대행사/셀러에게 적용되는 기본 단가',
    )
    schema = models.JSONField(
        default=list,
        verbose_name='입력 스키마',
        help_text='주문 시 입력할 필드 정의 [{"name":"url","label":"URL","type":"text","required":true}, ...]',
    )
    min_work_days = models.PositiveIntegerField(
        default=1,
        verbose_name='최소 작업일 수',
    )
    max_work_days = models.PositiveIntegerField(
        default=30,
        verbose_name='최대 작업일 수',
    )
    reduction_rate = models.PositiveIntegerField(
        default=0,
        verbose_name='감은 비율 (%)',
        help_text='총 타수에서 실제 투입하지 않는 비율 (예: 30 = 30% 감음)',
    )
    is_active = models.BooleanField(default=True, verbose_name='활성')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    class Meta:
        verbose_name = '상품'
        verbose_name_plural = '상품'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class PricePolicy(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='price_policies', verbose_name='상품',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='price_policies', verbose_name='적용 대상',
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=0,
        null=True, blank=True, verbose_name='적용 단가',
    )
    reduction_rate = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='감은 비율 (%)',
        help_text='null이면 상품 기본 감은 비율 사용',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')

    class Meta:
        verbose_name = '단가 정책'
        verbose_name_plural = '단가 정책'
        unique_together = ['product', 'user']

    def __str__(self):
        return f"{self.product.name} - {self.user} : {self.price}원"
