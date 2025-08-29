from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.db import models

from .models import Follow, UserProfile
from .serializers import (
    UserRegistrationSerializer, UserSerializer, UserUpdateSerializer,
    FollowSerializer, UserStatsSerializer, FollowersListSerializer,
    FollowingListSerializer, UserSearchSerializer, UserProfileSerializer
)
from apps.posts.models import Post
from apps.notifications.tasks import send_follow_notification

User = get_user_model()


class UserRegistrationView(generics.CreateAPIView):
    """Vue pour l'inscription des utilisateurs"""
    
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST'))
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            'message': 'Compte créé avec succès',
            'user': UserSerializer(user, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Vue pour récupérer et modifier le profil utilisateur"""
    
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer


class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'username'

    def get_object(self):
        username = self.kwargs.get(self.lookup_field)
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Utilisateur non trouvé")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Ajouter des statistiques supplémentaires
        data = serializer.data
        data['recent_posts'] = list(instance.posts.all()[:5].values(
            'id', 'content', 'likes_count', 'created_at'
        ))
        return Response(data)


class UserStatsView(generics.RetrieveAPIView):
    """Vue pour récupérer les statistiques détaillées d'un utilisateur"""
    
    serializer_class = UserStatsSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'username'

    def get_queryset(self):
        return User.objects.all()

    def get_object(self):
        username = self.kwargs.get('username')
        if username:
            return get_object_or_404(User, username=username)
        return self.request.user


class FollowUserView(APIView):
    """Vue pour suivre/ne plus suivre un utilisateur"""
    
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(ratelimit(key='user', rate='30/m', method='POST'))
    def post(self, request, username):
        try:
            user_to_follow = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )

        if user_to_follow == request.user:
            return Response(
                {'error': 'Vous ne pouvez pas vous suivre vous-même'},
                status=status.HTTP_400_BAD_REQUEST
            )

        follow, created = Follow.objects.get_or_create(
            follower=request.user,
            followed=user_to_follow
        )

        if created:
            # Envoyer notification de suivi
            send_follow_notification.delay(request.user.id, user_to_follow.id)
            
            return Response({
                'message': f'Vous suivez maintenant @{username}',
                'following': True
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'message': f'Vous suivez déjà @{username}',
                'following': True
            }, status=status.HTTP_200_OK)

    @method_decorator(ratelimit(key='user', rate='30/m', method='DELETE'))
    def delete(self, request, username):
        try:
            user_to_unfollow = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            follow = Follow.objects.get(
                follower=request.user,
                followed=user_to_unfollow
            )
            follow.delete()
            
            return Response({
                'message': f'Vous ne suivez plus @{username}',
                'following': False
            }, status=status.HTTP_200_OK)
        except Follow.DoesNotExist:
            return Response({
                'message': f'Vous ne suivez pas @{username}',
                'following': False
            }, status=status.HTTP_200_OK)


class FollowersListView(generics.ListAPIView):
    """Vue pour lister les followers d'un utilisateur"""
    
    serializer_class = FollowersListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['follower__username', 'follower__first_name', 'follower__last_name']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        username = self.kwargs.get('username')
        user = get_object_or_404(User, username=username)
        
        return Follow.objects.filter(followed=user).select_related(
            'follower'
        ).prefetch_related(
            'follower__profile'
        )


class FollowingListView(generics.ListAPIView):
    """Vue pour lister les utilisateurs suivis"""
    
    serializer_class = FollowingListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['followed__username', 'followed__first_name', 'followed__last_name']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        username = self.kwargs.get('username')
        user = get_object_or_404(User, username=username)
        
        return Follow.objects.filter(follower=user).select_related(
            'followed'
        ).prefetch_related(
            'followed__profile'
        )


class UserSearchView(generics.ListAPIView):
    """Vue pour rechercher des utilisateurs"""
    
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['username', 'first_name', 'last_name', 'bio']
    ordering_fields = ['followers_count', 'created_at']
    ordering = ['-followers_count']

    def get_queryset(self):
        queryset = User.objects.select_related('profile')
        
        # Filtrer les comptes privés si l'utilisateur n'est pas connecté
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_private=False)
        
        return queryset

    def list(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        
        if len(query) < 2:
            return Response({
                'error': 'La recherche doit contenir au moins 2 caractères'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return super().list(request, *args, **kwargs)


class SuggestedUsersView(generics.ListAPIView):
    """Vue pour suggérer des utilisateurs à suivre"""
    
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Utilisateurs que l'utilisateur actuel ne suit pas
        following_ids = Follow.objects.filter(follower=user).values_list('followed_id', flat=True)
        
        # Suggestions basées sur les followers en commun
        suggested_users = User.objects.filter(
            followers__follower__in=following_ids
        ).exclude(
            id__in=list(following_ids) + [user.id]
        ).annotate(
            mutual_count=Count('followers__follower', filter=models.Q(
                followers__follower__in=following_ids
            ))
        ).filter(
            mutual_count__gt=0,
            is_private=False
        ).order_by('-mutual_count', '-followers_count')[:10]
        
        return suggested_users


class MutualFollowersView(generics.ListAPIView):
    """Vue pour lister les followers en commun avec un utilisateur"""
    
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        username = self.kwargs.get('username')
        other_user = get_object_or_404(User, username=username)
        current_user = self.request.user
        
        # Followers de l'autre utilisateur qui suivent aussi l'utilisateur actuel
        mutual_followers = User.objects.filter(
            following__followed=other_user,
            following__follower__following__followed=current_user
        ).distinct()
        
        return mutual_followers


class UserProfileSettingsView(generics.RetrieveUpdateAPIView):
    """Vue pour gérer les paramètres de profil utilisateur"""
    
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(key='user', rate='10/m', method='POST')
def toggle_private_account(request):
    """Basculer entre compte public et privé"""
    user = request.user
    user.is_private = not user.is_private
    user.save(update_fields=['is_private'])
    
    return Response({
        'message': f'Compte maintenant {"privé" if user.is_private else "public"}',
        'is_private': user.is_private
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_activity_stats(request, username=None):
    """Statistiques d'activité détaillées d'un utilisateur"""
    if username:
        user = get_object_or_404(User, username=username)
    else:
        user = request.user
    
    # Vérifier les permissions pour voir les stats privées
    can_view_private = (
        user == request.user or 
        not user.is_private or 
        Follow.objects.filter(follower=request.user, followed=user).exists()
    )
    
    if not can_view_private:
        return Response(
            {'error': 'Vous n\'avez pas accès aux statistiques de cet utilisateur'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    from django.db.models import Count, Avg
    from django.db.models.functions import TruncDate, TruncHour
    from datetime import datetime, timedelta
    
    now = datetime.now()
    last_30_days = now - timedelta(days=30)
    
    # Posts par jour sur les 30 derniers jours
    posts_per_day = Post.objects.filter(
        author=user,
        created_at__gte=last_30_days
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Heures d'activité
    activity_by_hour = Post.objects.filter(
        author=user,
        created_at__gte=last_30_days
    ).annotate(
        hour=TruncHour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Engagement moyen
    avg_engagement = Post.objects.filter(author=user).aggregate(
        avg_likes=Avg('likes_count'),
        avg_retweets=Avg('retweets_count'),
        avg_replies=Avg('replies_count'),
        avg_views=Avg('views_count')
    )
    
    # Top hashtags utilisés
    from apps.posts.models import PostHashtag
    top_hashtags = PostHashtag.objects.filter(
        post__author=user,
        post__created_at__gte=last_30_days
    ).values(
        'hashtag__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    return Response({
        'user': UserSerializer(user, context={'request': request}).data,
        'stats': {
            'posts_per_day': list(posts_per_day),
            'activity_by_hour': list(activity_by_hour),
            'avg_engagement': avg_engagement,
            'top_hashtags': list(top_hashtags)
        }
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_feed_preferences(request):
    """Récupérer les préférences de feed de l'utilisateur"""
    # Ici on peut ajouter des préférences comme :
    # - Afficher les retweets
    # - Filtrer par type de contenu
    # - Algorithme de tri préféré
    
    preferences = {
        'show_retweets': True,
        'show_replies': True,
        'content_filters': [],
        'algorithm': 'chronological'  # ou 'algorithmic'
    }
    
    return Response(preferences)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(key='user', rate='10/m', method='POST')
def update_feed_preferences(request):
    """Mettre à jour les préférences de feed"""
    # Validation et sauvegarde des préférences
    # Pour l'instant, on retourne juste les données reçues
    
    return Response({
        'message': 'Préférences mises à jour',
        'preferences': request.data
    })


class UserBlockListView(generics.ListAPIView):
    """Vue pour lister les utilisateurs bloqués (fonctionnalité future)"""
    
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Pour l'instant, retourne une liste vide
        # À implémenter avec un modèle Block
        return User.objects.none()


@api_view(['POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(key='user', rate='20/m')
def block_user(request, username):
    """Bloquer/débloquer un utilisateur (fonctionnalité future)"""
    
    try:
        user_to_block = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non trouvé'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'POST':
        # Logique de blocage à implémenter
        return Response({
            'message': f'@{username} a été bloqué',
            'blocked': True
        })
    
    elif request.method == 'DELETE':
        # Logique de déblocage à implémenter
        return Response({
            'message': f'@{username} a été débloqué',
            'blocked': False
        })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_user_stats(request):
    """Statistiques publiques de la plateforme"""
    from django.db.models import Count
    from datetime import datetime, timedelta
    
    now = datetime.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    
    stats = {
        'total_users': User.objects.count(),
        'new_users_today': User.objects.filter(created_at__gte=last_24h).count(),
        'new_users_this_week': User.objects.filter(created_at__gte=last_7d).count(),
        'verified_users': User.objects.filter(is_verified=True).count(),
        'active_users_today': User.objects.filter(last_active__gte=last_24h).count(),
    }
    
    return Response(stats)