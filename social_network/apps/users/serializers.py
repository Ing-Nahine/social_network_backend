from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Follow, UserProfile

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Sérialiseur pour l'inscription d'un utilisateur"""
    
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def validate(self, attrs):
        """Validation personnalisée"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        
        # Vérifier l'unicité de l'email
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError("Un compte avec cet email existe déjà.")
        
        # Vérifier l'unicité du nom d'utilisateur
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris.")
        
        return attrs

    def create(self, validated_data):
        """Créer un nouvel utilisateur"""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        
        # Créer le profil utilisateur associé
        UserProfile.objects.create(user=user)
        
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Sérialiseur pour le profil utilisateur"""
    
    class Meta:
        model = UserProfile
        fields = [
            'theme', 'language', 'email_notifications', 'push_notifications',
            'show_email', 'show_birth_date', 'allow_direct_messages'
        ]


class UserSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les informations utilisateur publiques"""
    
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    is_followed_by = serializers.SerializerMethodField()
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'display_name', 'bio', 'location', 'website', 'birth_date',
            'avatar', 'banner', 'avatar_url', 'banner_url',
            'followers_count', 'following_count', 'posts_count',
            'is_verified', 'is_private', 'is_following', 'is_followed_by',
            'created_at', 'last_active', 'profile'
        ]
        read_only_fields = [
            'id', 'followers_count', 'following_count', 'posts_count',
            'is_verified', 'created_at', 'last_active'
        ]

    def get_avatar_url(self, obj):
        """Retourne l'URL complète de l'avatar"""
        request = self.context.get('request')
        if obj.avatar:
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_banner_url(self, obj):
        """Retourne l'URL complète de la bannière"""
        request = self.context.get('request')
        if obj.banner:
            if request:
                return request.build_absolute_uri(obj.banner.url)
            return obj.banner.url
        return None

    def get_is_following(self, obj):
        """Vérifie si l'utilisateur actuel suit cet utilisateur"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(
                follower=request.user,
                followed=obj
            ).exists()
        return False

    def get_is_followed_by(self, obj):
        """Vérifie si cet utilisateur suit l'utilisateur actuel"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(
                follower=obj,
                followed=request.user
            ).exists()
        return False


class UserUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la mise à jour du profil utilisateur"""
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'bio', 'location', 'website',
            'birth_date', 'avatar', 'banner', 'is_private'
        ]

    def validate_bio(self, value):
        """Validation de la bio"""
        if len(value) > 500:
            raise serializers.ValidationError("La bio ne peut pas dépasser 500 caractères.")
        return value

    def validate_website(self, value):
        """Validation du site web"""
        if value and not (value.startswith('http://') or value.startswith('https://')):
            value = f"https://{value}"
        return value


class FollowSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les relations de suivi"""
    
    follower = UserSerializer(read_only=True)
    followed = UserSerializer(read_only=True)
    
    class Meta:
        model = Follow
        fields = ['id', 'follower', 'followed', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserStatsSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les statistiques utilisateur"""
    
    engagement_rate = serializers.SerializerMethodField()
    avg_likes_per_post = serializers.SerializerMethodField()
    most_active_hour = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'followers_count', 'following_count', 'posts_count',
            'engagement_rate', 'avg_likes_per_post', 'most_active_hour'
        ]

    def get_engagement_rate(self, obj):
        """Calcule le taux d'engagement moyen"""
        from apps.posts.models import Post
        from django.db.models import Avg
        
        avg_engagement = Post.objects.filter(author=obj).aggregate(
            avg_likes=Avg('likes_count'),
            avg_retweets=Avg('retweets_count'),
            avg_comments=Avg('replies_count'),
            avg_views=Avg('views_count')
        )
        
        total_interactions = (
            (avg_engagement['avg_likes'] or 0) +
            (avg_engagement['avg_retweets'] or 0) +
            (avg_engagement['avg_comments'] or 0)
        )
        
        avg_views = avg_engagement['avg_views'] or 0
        
        if avg_views > 0:
            return round((total_interactions / avg_views) * 100, 2)
        return 0

    def get_avg_likes_per_post(self, obj):
        """Calcule la moyenne de likes par post"""
        from apps.posts.models import Post
        from django.db.models import Avg
        
        result = Post.objects.filter(author=obj).aggregate(
            avg_likes=Avg('likes_count')
        )
        return round(result['avg_likes'] or 0, 1)

    def get_most_active_hour(self, obj):
        """Trouve l'heure la plus active de l'utilisateur"""
        from apps.posts.models import Post
        from django.db.models import Count
        from django.db.models.functions import Extract
        
        result = Post.objects.filter(author=obj).annotate(
            hour=Extract('created_at', 'hour')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        return result['hour'] if result else None


class FollowersListSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la liste des followers"""
    
    follower = UserSerializer(read_only=True)
    mutual_followers_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Follow
        fields = ['follower', 'created_at', 'mutual_followers_count']

    def get_mutual_followers_count(self, obj):
        """Compte les followers en commun"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Followers du follower qui suivent aussi l'utilisateur actuel
            return Follow.objects.filter(
                follower__in=obj.follower.followers.values('follower'),
                followed=request.user
            ).count()
        return 0


class FollowingListSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la liste des utilisateurs suivis"""
    
    followed = UserSerializer(read_only=True)
    mutual_followers_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Follow
        fields = ['followed', 'created_at', 'mutual_followers_count']

    def get_mutual_followers_count(self, obj):
        """Compte les followers en commun"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Followers de l'utilisateur suivi qui suivent aussi l'utilisateur actuel
            return Follow.objects.filter(
                follower__in=obj.followed.followers.values('follower'),
                followed=request.user
            ).count()
        return 0


class UserSearchSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la recherche d'utilisateurs"""
    
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    mutual_followers_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'display_name', 'bio', 'avatar_url',
            'followers_count', 'is_verified', 'is_following',
            'mutual_followers_count'
        ]

    def get_avatar_url(self, obj):
        """Retourne l'URL de l'avatar"""
        request = self.context.get('request')
        if obj.avatar:
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_is_following(self, obj):
        """Vérifie si l'utilisateur actuel suit cet utilisateur"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(
                follower=request.user,
                followed=obj
            ).exists()
        return False

    def get_mutual_followers_count(self, obj):
        """Compte les followers en commun"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(
                follower__in=obj.followers.values('follower'),
                followed=request.user
            ).count()
        return 0