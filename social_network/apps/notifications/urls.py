from django.urls import path
from apps.notifications import views

urlpatterns = [
    path('notifications/',views.notifications,name='notifications')
]
