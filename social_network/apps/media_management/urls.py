from django.urls import path
from apps.media_management import views

urlpatterns = [
    path('media_management/',views.media_management,name='media_management')
]
