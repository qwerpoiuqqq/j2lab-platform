from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('calendar/', views.deadline_calendar, name='deadline_calendar'),
    path('api/deadlines/', views.api_deadline_events, name='api_deadline_events'),
    path('notifications/read/<int:pk>/', views.notification_read, name='notification_read'),
    path('notifications/read-all/', views.notification_read_all, name='notification_read_all'),
    path('notices/', views.notice_list, name='notice_list'),
    path('notices/create/', views.notice_create, name='notice_create'),
    path('notices/<int:pk>/edit/', views.notice_edit, name='notice_edit'),
    path('notices/<int:pk>/delete/', views.notice_delete, name='notice_delete'),
]
