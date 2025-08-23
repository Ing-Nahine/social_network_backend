from django.urls import path
from apps.authentication import views

urlpatterns = [
    path('authentification/',views.authentification,name='authentification')
]
