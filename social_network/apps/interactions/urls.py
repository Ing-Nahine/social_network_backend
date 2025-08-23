from django.urls import path
from apps.interactions import views

urlpatterns = [
    path('interactions/',views.interactions,name='interactions')
]
