from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('create/', views.product_create, name='product_create'),
    path('<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('<int:pk>/schema/', views.api_product_schema, name='api_product_schema'),
    path('prices/', views.price_policy_list, name='price_policy_list'),
    path('prices/matrix/', views.price_matrix, name='price_matrix'),
    path('prices/api/save/', views.api_price_save, name='api_price_save'),
    path('prices/create/', views.price_policy_create, name='price_policy_create'),
    path('prices/<int:pk>/edit/', views.price_policy_edit, name='price_policy_edit'),
    path('prices/<int:pk>/delete/', views.price_policy_delete, name='price_policy_delete'),
    # 카테고리 관리
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('categories/reorder/', views.category_reorder, name='category_reorder'),
    path('categories/<int:pk>/products/', views.api_category_products, name='api_category_products'),
]
