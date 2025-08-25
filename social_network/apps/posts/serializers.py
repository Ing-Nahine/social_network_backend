from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Post, PostMedia, Hashtag

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Sérialiseur utilisateur simple pour les posts"""
    avatar_url = serializers.CharField(source='get_avatar_url', read_only=True)
    display_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'avatar_url', 'is_verified']


class PostMediaSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les médias de posts"""
    file_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = PostMedia
        fields = [
            'id', 'media_type', 'file_url', 'alt_text', 
            'width', 'height', 'order'
        ]


class PostSerializer(serializers.ModelSerializer):
    """Sérialiseur principal pour les posts"""
    author = UserSerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    
    # Interactions de l'utilisateur actuel
    is_liked = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    is_retweeted = serializers.SerializerMethodField()
    
    # Post original pour les retweets
    original_post = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'author', 'content', 'post_type', 'media',
            'likes_count', 'retweets_count', 'replies_count', 'views_count',
            'is_liked', 'is_bookmarked', 'is_retweeted',
            'original_post', 'created_at', 'updated_at'
        ]
    
    def get_is_liked(self, obj):
        """Vérifier si l'utilisateur a liké ce post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.interactions.models import Like
            return Like.objects.filter(user=request.user, post=obj).exists()
        return False
    
    def get_is_bookmarked(self, obj):
        """Vérifier si l'utilisateur a mis ce post en signet"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.interactions.models import Bookmark
            return Bookmark.objects.filter(user=request.user, post=obj).exists()
        return False
    
    def get_is_retweeted(self, obj):
        """Vérifier si l'utilisateur a retweeté ce post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.interactions.models import Share
            return Share.objects.filter(user=request.user, original_post=obj).exists()
        return False
    
    def get_original_post(self, obj):
        """Récupérer le post original pour les retweets"""
        if obj.original_post:
            return PostSerializer(obj.original_post, context=self.context).data
        return None


class PostCreateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la création de posts"""
    
    class Meta:
        model = Post
        fields = ['content', 'post_type', 'parent_post', 'original_post']
    
    def validate_content(self, value):
        """Valider le contenu du post"""
        if len(value.strip()) == 0:
            raise serializers.ValidationError("Le contenu ne peut pas être vide")
        if len(value) > 280:
            raise serializers.ValidationError("Le contenu ne peut pas dépasser 280 caractères")
        return value.strip()