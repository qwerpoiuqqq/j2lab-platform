from django.contrib import admin
from .models import Order, OrderItem, BalanceTransaction


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['row_number', 'data', 'unit_price', 'status']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'user', 'product', 'item_count', 'total_amount', 'status', 'created_at']
    list_filter = ['status', 'product']
    search_fields = ['order_number']
    inlines = [OrderItemInline]


@admin.register(BalanceTransaction)
class BalanceTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'tx_type', 'amount', 'balance_after', 'description', 'created_at']
    list_filter = ['tx_type']
