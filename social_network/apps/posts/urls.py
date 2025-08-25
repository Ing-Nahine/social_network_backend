from django.urls import path
from . import views


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
    
    

    
]




