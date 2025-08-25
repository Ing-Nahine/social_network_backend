from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Comment, CommentLike

User = get_user_model()


class CommentAuthorSerializer(serializers.ModelSerializer):
    """Sérialiseur utilisateur simple pour les commentaires"""
    avatar_url = serializers.CharField(source='get_avatar_url', read_only=True)
    display_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'avatar_url', 'is_verified']


class CommentSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les commentaires"""
    author = CommentAuthorSerializer(read_only=True)
    is_liked = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'author', 'content', 'likes_count', 'replies_count',
            'is_liked', 'replies', 'is_reply', 'created_at', 'updated_at'
        ]
    
    def get_is_liked(self, obj):
        """Vérifier si l'utilisateur a liké ce commentaire"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return CommentLike.objects.filter(
                user=request.user, comment=obj
            ).exists()
        return False
    
    def get_replies(self, obj):
        """Récupérer les réponses au commentaire (limitées à 5)"""
        if obj.parent_comment is None:  # Seulement pour les commentaires principaux
            replies = obj.replies.select_related('author')[:5]
            return CommentSerializer(
                replies, 
                many=True, 
                context=self.context
            ).data
        return []


class CommentCreateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la création de commentaires"""
    parent_comment_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Comment
        fields = ['content', 'parent_comment_id']
    
    def validate_content(self, value):
        """Valider le contenu du commentaire"""
        if len(value.strip()) == 0:
            raise serializers.ValidationError("Le contenu ne peut pas être vide")
        if len(value) > 280:
            raise serializers.ValidationError("Le contenu ne peut pas dépasser 280 caractères")
        return value.strip()
    
    def validate_parent_comment_id(self, value):
        """Valider l'ID du commentaire parent"""
        if value:
            try:
                parent_comment = Comment.objects.get(id=value)
                # Vérifier que le commentaire parent est sur le même post
                post_id = self.context.get('post_id')
                if parent_comment.post.id != post_id:
                    raise serializers.ValidationError("Le commentaire parent n'appartient pas au même post")
                return parent_comment
            except Comment.DoesNotExist:
                raise serializers.ValidationError("Commentaire parent introuvable")
        return None
    
    def create(self, validated_data):
        """Créer le commentaire"""
        parent_comment_id = validated_data.pop('parent_comment_id', None)
        parent_comment = self.validate_parent_comment_id(parent_comment_id)
        
        comment = Comment.objects.create(
            parent_comment=parent_comment,
            **validated_data
        )
        
        return comment