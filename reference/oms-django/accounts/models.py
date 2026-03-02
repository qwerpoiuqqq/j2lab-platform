from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', '총관리자'
        ACCOUNTANT = 'accountant', '경리'
        MANAGER = 'manager', '책임자'
        AGENCY = 'agency', '대행사'
        SELLER = 'seller', '셀러'

    role = models.CharField(
        max_length=12,
        choices=Role.choices,
        default=Role.SELLER,
        verbose_name='역할',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='상위 계정',
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal('0'),
        verbose_name='예치금 잔액',
    )
    company_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='회사명',
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='연락처',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='가입일')

    class Meta:
        verbose_name = '사용자'
        verbose_name_plural = '사용자'

    def __str__(self):
        return f'[{self.get_role_display()}] {self.company_name or self.username}'

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_accountant(self):
        return self.role == self.Role.ACCOUNTANT

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER

    @property
    def is_agency(self):
        return self.role == self.Role.AGENCY

    @property
    def is_seller(self):
        return self.role == self.Role.SELLER

    def get_descendant_ids(self):
        """Return all descendant user ids using iterative BFS."""
        visited = {self.id}
        frontier = [self.id]
        descendants = []

        while frontier:
            child_ids = list(
                User.objects.filter(parent_id__in=frontier).values_list('id', flat=True)
            )
            next_frontier = []
            for child_id in child_ids:
                if child_id in visited:
                    continue
                visited.add(child_id)
                descendants.append(child_id)
                next_frontier.append(child_id)
            frontier = next_frontier

        return descendants

    def get_all_order_user_ids(self):
        """주문 조회에 포함할 전체 사용자 ID(자기 자신 포함).
        경리는 상위 총관리자의 범위를 상속받는다."""
        if self.is_accountant and self.parent:
            return self.parent.get_all_order_user_ids()
        return [self.id] + self.get_descendant_ids()
