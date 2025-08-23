from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Post, PostMedia, Hashtag, PostHashtag, Mention
from apps.users.serializers import UserSerializer
from apps.interactions.models import Like, Bookmark, Share
import re

User = get_user_model()


class PostMediaSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les médias de posts"""
    
    file_url = serializers.ReadOnlyField()
    
    class Meta:
        model = PostMedia
        fields = [
            'id', 'media_type', 'image', 'video', 'file_url',
            'alt_text', 'width', 'height', 'file_size', 'duration', 'order'
        ]
        read_only_fields = ['id', 'width', 'height', 'file_size', 'duration']

    def validate(self, attrs):
        """Validation des médias"""
        media_type = attrs.get('media_type')
        
        if media_type == 'image' and not attrs.get('image'):
            raise serializers.ValidationError("Une image est requise pour le type 'image'.")
        
        if media_type in ['video', 'gif'] and not attrs.get('video'):
            raise serializers.ValidationError("Un fichier vidéo est requis pour ce type de média.")
        
        return attrs


class HashtagSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les hashtags"""
    
    class Meta:
        model = Hashtag
        fields = ['id', 'name', 'posts_count', 'trending_score']
        read_only_fields = ['id', 'posts_count', 'trending_score']


class MentionSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les mentions"""
    
    mentioned_user = UserSerializer(read_only=True)
    
    class Meta:
        model = Mention
        fields = ['id', 'mentioned_user', 'position']
        read_only_fields = ['id']


class PostSerializer(serializers.ModelSerializer):
    """Sérialiseur principal pour les posts"""
    
    author = UserSerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    hashtags = HashtagSerializer(many=True, read_only=True, source='hashtag_relations.hashtag')
    mentions = MentionSerializer(many=True, read_only=True)
    
    # Champs calculés
    is_liked = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()
    engagement_rate = serializers.ReadOnlyField()
    
    # Posts liés (pour retweets et réponses)
    parent_post = serializers.SerializerMethodField()
    original_post = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'author', 'content', 'post_type', 'media', 'hashtags', 'mentions',
            'likes_count', 'retweets_count', 'replies_count', 'views_count',
            'is_liked', 'is_bookmarked', 'is_shared', 'engagement_rate',
            'parent_post', 'original_post', 'is_pinned', 'allow_replies',
            'is_sensitive', 'latitude', 'longitude', 'location_name',
            'created_at', 'updated_at', 'scheduled_at'
        ]
        read_only_fields = [
            'id', 'author', 'likes_count', 'retweets_count', 'replies_count',
            'views_count', 'created_at', 'updated_at'
        ]

    def get_is_liked(self, obj):
        """Vérifie si l'utilisateur actuel a liké ce post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Like.objects.filter(user=request.user, post=obj).exists()
        return False

    def get_is_bookmarked(self, obj):
        """Vérifie si l'utilisateur actuel a mis ce post en signet"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Bookmark.objects.filter(user=request.user, post=obj).exists()
        return False

    def get_is_shared(self, obj):
        """Vérifie si l'utilisateur actuel a partagé ce post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Share.objects.filter(user=request.user, original_post=obj).exists()
        return False

    def get_parent_post(self, obj):
        """Retourne le post parent (pour les réponses)"""
        if obj.parent_post:
            return PostSerializer(obj.parent_post, context=self.context).data
        return None

    def get_original_post(self, obj):
        """Retourne le post original (pour les retweets)"""
        if obj.original_post:
            return PostSerializer(obj.original_post, context=self.context).data
        return None


class PostCreateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la création de posts"""
    
    media_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False,
        allow_empty=True,
        max_length=4  # Maximum 4 médias par post
    )
    
    class Meta:
        model = Post
        fields = [
            'content', 'post_type', 'parent_post', 'original_post',
            'allow_replies', 'is_sensitive', 'latitude', 'longitude',
            'location_name', 'scheduled_at', 'media_files'
        ]

    def validate_content(self, value):
        """Validation du contenu"""
        if len(value.strip()) == 0:
            raise serializers.ValidationError("Le contenu ne peut pas être vide.")
        
        if len(value) > 280:
            raise serializers.ValidationError("Le contenu ne peut pas dépasser 280 caractères.")
        
        return value.strip()

    def validate(self, attrs):
        """Validation globale"""
        post_type = attrs.get('post_type', 'original')
        
        if post_type == 'reply' and not attrs.get('parent_post'):
            raise serializers.ValidationError("Un post parent est requis pour une réponse.")
        
        if post_type in ['retweet', 'quote'] and not attrs.get('original_post'):
            raise serializers.ValidationError("Un post original est requis pour un retweet.")
        
        return attrs

    def create(self, validated_data):
        """Création du post avec traitement des médias, hashtags et mentions"""
        media_files = validated_data.pop('media_files', [])
        request = self.context.get('request')
        
        # Créer le post
        post = Post.objects.create(
            author=request.user,
            **validated_data
        )
        
        # Traiter les médias
        self._create_media(post, media_files)
        
        # Traiter les hashtags et mentions
        self._process_hashtags_and_mentions(post, validated_data['content'])
        
        return post

    def _create_media(self, post, media_files):
        """Créer les objets média associés au post"""
        for index, media_file in enumerate(media_files):
            # Déterminer le type de média
            content_type = media_file.content_type
            if content_type.startswith('image/'):
                media_type = 'gif' if 'gif' in content_type else 'image'
                PostMedia.objects.create(
                    post=post,
                    media_type=media_type,
                    image=media_file,
                    order=index
                )
            elif content_type.startswith('video/'):
                PostMedia.objects.create(
                    post=post,
                    media_type='video',
                    video=media_file,
                    order=index
                )

    def _process_hashtags_and_mentions(self, post, content):
        """Traiter les hashtags et mentions dans le contenu"""
        # Traitement des hashtags
        hashtag_pattern = r'#(\w+)'
        hashtags = re.findall(hashtag_pattern, content, re.IGNORECASE)
        
        for hashtag_name in set(hashtags):  # Éviter les doublons
            hashtag, created = Hashtag.objects.get_or_create(
                name=hashtag_name.lower()
            )
            PostHashtag.objects.create(post=post, hashtag=hashtag)
            
            # Mettre à jour le compteur de posts du hashtag
            if created:
                hashtag.posts_count = 1
            else:
                hashtag.posts_count += 1
            hashtag.save()

        # Traitement des mentions
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, content, re.IGNORECASE)
        
        for username in set(mentions):  # Éviter les doublons
            try:
                mentioned_user = User.objects.get(username__iexact=username)
                position = content.lower().find(f'@{username.lower()}')
                Mention.objects.create(
                    post=post,
                    mentioned_user=mentioned_user,
                    position=position
                )
            except User.DoesNotExist:
                continue


class PostUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la mise à jour de posts"""
    
    class Meta:
        model = Post
        fields = [
            'content', 'allow_replies', 'is_sensitive',
            'latitude', 'longitude', 'location_name'
        ]

    def validate_content(self, value):
        """Validation du contenu"""
        if len(value.strip()) == 0:
            raise serializers.ValidationError("Le contenu ne peut pas être vide.")
        
        if len(value) > 280:
            raise serializers.ValidationError("Le contenu ne peut pas dépasser 280 caractères.")
        
        return value.strip()

    def update(self, instance, validated_data):
        """Mise à jour avec retraitement des hashtags et mentions si nécessaire"""
        old_content = instance.content
        new_content = validated_data.get('content', old_content)
        
        instance = super().update(instance, validated_data)
        
        # Si le contenu a changé, retraiter hashtags et mentions
        if old_content != new_content:
            # Supprimer les anciennes relations
            PostHashtag.objects.filter(post=instance).delete()
            Mention.objects.filter(post=instance).delete()
            
            # Recreer avec le nouveau contenu
            self._process_hashtags_and_mentions(instance, new_content)
        
        return instance

    def _process_hashtags_and_mentions(self, post, content):
        """Même logique que dans PostCreateSerializer"""
        # Traitement des hashtags
        hashtag_pattern = r'#(\w+)'
        hashtags = re.findall(hashtag_pattern, content, re.IGNORECASE)
        
        for hashtag_name in set(hashtags):
            hashtag, created = Hashtag.objects.get_or_create(
                name=hashtag_name.lower()
            )
            PostHashtag.objects.create(post=post, hashtag=hashtag)

        # Traitement des mentions
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, content, re.IGNORECASE)
        
        for username in set(mentions):
            try:
                mentioned_user = User.objects.get(username__iexact=username)
                position = content.lower().find(f'@{username.lower()}')
                Mention.objects.create(
                    post=post,
                    mentioned_user=mentioned_user,
                    position=position
                )
            except User.DoesNotExist:
                continue


class PostListSerializer(serializers.ModelSerializer):
    """Sérialiseur optimisé pour les listes de posts (feed)"""
    
    author = UserSerializer(read_only=True)
    media_preview = serializers.SerializerMethodField()
    hashtags_preview = serializers.SerializerMethodField()
    
    is_liked = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'author', 'content', 'post_type', 'media_preview',
            'hashtags_preview', 'likes_count', 'retweets_count',
            'replies_count', 'views_count', 'is_liked', 'is_bookmarked',
            'is_pinned', 'is_sensitive', 'created_at'
        ]

    def get_media_preview(self, obj):
        """Retourne un aperçu des médias (seulement le premier)"""
        first_media = obj.media.first()
        if first_media:
            return PostMediaSerializer(first_media).data
        return None

    def get_hashtags_preview(self, obj):
        """Retourne les premiers hashtags"""
        hashtags = obj.hashtag_relations.select_related('hashtag')[:3]
        return [relation.hashtag.name for relation in hashtags]

    def get_is_liked(self, obj):
        """Vérifie si l'utilisateur actuel a liké ce post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Utiliser les données préchargées si disponibles
            liked_posts = getattr(request, '_liked_posts', set())
            return obj.id in liked_posts
        return False

    def get_is_bookmarked(self, obj):
        """Vérifie si l'utilisateur actuel a mis ce post en signet"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Utiliser les données préchargées si disponibles
            bookmarked_posts = getattr(request, '_bookmarked_posts', set())
            return obj.id in bookmarked_posts
        return False