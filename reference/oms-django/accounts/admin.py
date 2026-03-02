from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'company_name', 'role', 'parent', 'balance', 'is_active']
    list_filter = ['role', 'is_active']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('추가 정보', {
            'fields': ('role', 'parent', 'balance', 'company_name', 'phone'),
        }),
    )
