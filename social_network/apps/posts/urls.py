from django.urls import path
from . import views
from . import views, media_views


app_name = 'posts'

urlpatterns = [
    # API Posts
    path('', views.feed, name='feed'),
    path('create/', views.create_post, name='create'),
    path('<int:post_id>/', views.post_detail, name='detail'),
    path('<int:post_id>/delete/', views.delete_post, name='delete'),
    path('<int:post_id>/reply/', views.create_reply, name='reply'),
    path('<int:post_id>/retweet/', views.create_retweet, name='retweet'),
    
    # Hashtags
    path('hashtag/<str:hashtag_name>/', views.hashtag_posts, name='hashtag'),
    path('trending/', views.trending_hashtags, name='trending'),
    
    # Posts utilisateur
    path('user/<str:username>/', views.user_posts, name='user_posts'),
    
    
    
    
    path('media/upload/', media_views.upload_media, name='upload_media'),
    path('media/<int:media_id>/', media_views.get_media, name='get_media'),
    path('media/<int:media_id>/delete/', media_views.delete_media, name='delete_media'),
    path('media/<int:media_id>/alt-text/', media_views.update_media_alt_text, name='update_alt_text'),
    path('media/<int:media_id>/serve/', media_views.serve_media, name='serve_media'),
    path('<int:post_id>/media/', media_views.get_post_media, name='post_media'),

    
    
]




