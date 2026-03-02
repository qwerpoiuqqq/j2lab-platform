from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('grid/', views.order_grid, name='order_grid'),
    path('api/submit/', views.api_order_submit, name='api_order_submit'),
    path('api/excel-template/<int:product_id>/', views.api_excel_template_download, name='api_excel_template'),
    path('api/excel-upload/', views.api_excel_upload, name='api_excel_upload'),
    path('', views.order_list, name='order_list'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/cancel/', views.order_cancel, name='order_cancel'),
    path('<int:pk>/delete/', views.order_delete, name='order_delete'),
    path('<int:pk>/status/', views.order_status_update, name='order_status_update'),
    path('bulk-status/', views.order_bulk_status_update, name='order_bulk_status_update'),
    path('<int:pk>/confirm-payment/', views.order_confirm_payment, name='order_confirm_payment'),
    path('<int:pk>/approve/', views.order_approve, name='order_approve'),
    path('<int:pk>/deadline/', views.order_deadline_update, name='order_deadline_update'),
    path('<int:pk>/renew-data/', views.api_order_renew_data, name='api_order_renew_data'),
    path('<int:pk>/export-items/', views.order_items_export, name='order_items_export'),
    path('export/', views.order_export, name='order_export'),
    path('settlement/', views.settlement_list, name='settlement_list'),
    path('settlement/secret/', views.settlement_secret, name='settlement_secret'),
]
