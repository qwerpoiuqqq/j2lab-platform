from django.contrib import admin
from .models import Product, PricePolicy


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'cost_price', 'base_price', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(PricePolicy)
class PricePolicyAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'price', 'created_at']
    list_filter = ['product']
