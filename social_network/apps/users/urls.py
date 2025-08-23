from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Inscription
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    
    # Profil utilisateur
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('profile/settings/', views.UserProfileSettingsView.as_view(), name='profile_settings'),
    path('profile/toggle-private/', views.toggle_private_account, name='toggle_private'),
    
    # Détails utilisateur public
    path('<str:username>/', views.UserDetailView.as_view(), name='user_detail'),
    path('<str:username>/stats/', views.UserStatsView.as_view(), name='user_stats'),
    path('<str:username>/activity/', views.user_activity_stats, name='user_activity'),
    
    # Relations de suivi
    path('<str:username>/follow/', views.FollowUserView.as_view(), name='follow_user'),
    path('<str:username>/followers/', views.FollowersListView.as_view(), name='followers_list'),
    path('<str:username>/following/', views.FollowingListView.as_view(), name='following_list'),
    path('<str:username>/mutual/', views.MutualFollowersView.as_view(), name='mutual_followers'),
    
    # Blocage (fonctionnalité future)
    path('<str:username>/block/', views.block_user, name='block_user'),
    path('blocked/', views.UserBlockListView.as_view(), name='blocked_users'),
    
    # Recherche et suggestions
    path('search/', views.UserSearchView.as_view(), name='user_search'),
    path('suggestions/', views.SuggestedUsersView.as_view(), name='suggested_users'),
    
    # Préférences
    path('feed/preferences/', views.user_feed_preferences, name='feed_preferences'),
    path('feed/preferences/update/', views.update_feed_preferences, name='update_feed_preferences'),
    
    # Statistiques publiques
    path('stats/public/', views.public_user_stats, name='public_stats'),
]