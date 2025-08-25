from django.urls import path
from . import views

app_name = 'interactions'

urlpatterns = [
    # API Interactions
    path('like/<int:post_id>/', views.toggle_like, name='toggle_like'),
    path('bookmark/<int:post_id>/', views.toggle_bookmark, name='toggle_bookmark'),
    
    # Comments
    path('comment/<int:post_id>/', views.create_comment, name='create_comment'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path('comment-like/<int:comment_id>/', views.toggle_comment_like, name='toggle_comment_like'),
    path('comments/<int:post_id>/', views.get_post_comments, name='post_comments'),
    
    # User interactions
    path('my-bookmarks/', views.user_bookmarks, name='user_bookmarks'),
    path('my-likes/', views.user_likes, name='user_likes'),
    
    # Post interactions summary
    path('post/<int:post_id>/', views.get_post_interactions, name='post_interactions'),
]