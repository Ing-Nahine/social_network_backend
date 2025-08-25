from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # API Notifications
    path('', views.notification_list, name='list'),
    path('<int:notification_id>/read/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
    path('count/', views.notification_count, name='count'),
    
    # Préférences
    path('preferences/', views.notification_preferences, name='preferences'),
    
    # Push notifications
    path('push/register/', views.register_push_subscription, name='push_register'),
    path('push/unregister/', views.unregister_push_subscription, name='push_unregister'),
    path('push/test/', views.test_push_notification, name='push_test'),
    path('vapid-key/', views.get_vapid_public_key, name='vapid_key'),
]