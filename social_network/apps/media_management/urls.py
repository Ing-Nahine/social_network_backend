from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MediaFileViewSet, MediaAnalyticsViewSet, bulk_upload_media, user_media_library, popular_media, attach_media_to_post, media_proxy

router = DefaultRouter()
router.register(r'files', MediaFileViewSet, basename='mediafile')
router.register(r'analytics', MediaAnalyticsViewSet, basename='mediaanalytics')

urlpatterns = [
    path('', include(router.urls)),
    path('bulk-upload/', bulk_upload_media, name='bulk-upload-media'),
    path('library/', user_media_library, name='user-media-library'),
    path('popular/', popular_media, name='popular-media'),
    path('attach-to-post/', attach_media_to_post, name='attach-media-to-post'),
    path('proxy/<uuid:media_id>/', media_proxy, name='media-proxy'),
]
