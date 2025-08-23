from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

# Documentation API
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Social Network API",
        default_version='v1',
        description="API pour un réseau social type Twitter",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@socialnetwork.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Administration
    path('admin/', admin.site.urls),
    
    # Documentation API
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/schema/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    # Authentification JWT
    path('api/auth/', include([
        path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
        path('verify/', TokenVerifyView.as_view(), name='token_verify'),
    ])),
    
    # Applications
    path('api/auth/', include('apps.authentication.urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/posts/', include('apps.posts.urls')),
    path('api/interactions/', include('apps.interactions.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/media/', include('apps.media_management.urls')),
    
    # Health check
    path('health/', include([
        path('', lambda request: HttpResponse('OK'), name='health_check'),
        path('db/', lambda request: HttpResponse('DB OK') if connection.ensure_connection() else HttpResponse('DB Error', status=500), name='health_db'),
    ])),
]

# Servir les fichiers média en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Import pour health check
from django.http import HttpResponse
from django.db import connection