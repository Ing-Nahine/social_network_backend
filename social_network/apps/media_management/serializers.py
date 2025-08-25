from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    MediaFile, 
    MediaThumbnail, 
    MediaProcessingQueue,
    MediaAnalytics
)
from apps.posts.models import PostMedia

User = get_user_model()


class MediaThumbnailSerializer(serializers.ModelSerializer):
    """Serializer pour les miniatures"""
    
    url = serializers.SerializerMethodField()
    
    class Meta:
        model = MediaThumbnail
        fields = [
            'size', 'url', 'width', 'height', 'file_size'
        ]
    
    def get_url(self, obj):
        """Retourne l'URL de la miniature"""
        return obj.file_url


class MediaFileSerializer(serializers.ModelSerializer):
    """Serializer de base pour les fichiers médias"""
    
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    
    class Meta:
        model = MediaFile
        fields = [
            'id', 'media_type', 'usage_type', 'url', 'thumbnail_url',
            'original_filename', 'file_size', 'width', 'height', 'duration',
            'alt_text', 'is_processed', 'is_approved',
            'uploaded_by_username', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'file_size', 'width', 'height', 'duration',
            'is_processed', 'uploaded_by_username', 'created_at', 'updated_at'
        ]
    
    def get_url(self, obj):
        """Retourne l'URL du fichier média"""
        return obj.file_url
    
    def get_thumbnail_url(self, obj):
        """Retourne l'URL de la miniature"""
        return obj.thumbnail_url


class MediaFileDetailSerializer(MediaFileSerializer):
    """Serializer détaillé pour les fichiers médias"""
    
    thumbnails = MediaThumbnailSerializer(many=True, read_only=True)
    analytics = serializers.SerializerMethodField()
    processing_status = serializers.SerializerMethodField()
    
    class Meta(MediaFileSerializer.Meta):
        fields = MediaFileSerializer.Meta.fields + [
            'mime_type', 'processing_error', 'thumbnails', 
            'analytics', 'processing_status'
        ]
    
    def get_analytics(self, obj):
        """Retourne les analytics du média"""
        try:
            analytics = obj.analytics
            return {
                'total_views': analytics.total_views,
                'unique_views': analytics.unique_views,
                'total_likes': analytics.total_likes,
                'total_shares': analytics.total_shares,
                'total_downloads': analytics.total_downloads,
                'average_view_duration': analytics.average_view_duration,
                'bounce_rate': analytics.bounce_rate,
            }
        except MediaAnalytics.DoesNotExist:
            return {
                'total_views': 0,
                'unique_views': 0,
                'total_likes': 0,
                'total_shares': 0,
                'total_downloads': 0,
                'average_view_duration': 0.0,
                'bounce_rate': 0.0,
            }
    
    def get_processing_status(self, obj):
        """Retourne le statut de traitement"""
        pending_tasks = obj.processing_tasks.filter(status='pending').count()
        processing_tasks = obj.processing_tasks.filter(status='processing').count()
        failed_tasks = obj.processing_tasks.filter(status='failed').count()
        completed_tasks = obj.processing_tasks.filter(status='completed').count()
        
        return {
            'pending': pending_tasks,
            'processing': processing_tasks,
            'failed': failed_tasks,
            'completed': completed_tasks,
            'is_fully_processed': pending_tasks == 0 and processing_tasks == 0,
            'has_errors': failed_tasks > 0
        }


class PostMediaSerializer(serializers.ModelSerializer):
    """Serializer pour les relations post-média"""
    
    media_file = MediaFileSerializer(read_only=True)
    media_file_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = PostMedia
        fields = [
            'id', 'media_file', 'media_file_id', 'order', 
            'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_media_file_id(self, value):
        """Valide que le fichier média existe et appartient à l'utilisateur"""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Utilisateur requis")
        
        try:
            media_file = MediaFile.objects.get(id=value)
            if media_file.uploaded_by != request.user:
                raise serializers.ValidationError("Vous n'avez pas accès à ce fichier")
            return value
        except MediaFile.DoesNotExist:
            raise serializers.ValidationError("Fichier média introuvable")


class MediaUploadSerializer(serializers.Serializer):
    """Serializer pour l'upload de médias"""
    
    file = serializers.FileField()
    usage_type = serializers.ChoiceField(
        choices=MediaFile.USAGE_TYPES,
        default='post'
    )
    alt_text = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True
    )
    
    def validate_file(self, value):
        """Valide le fichier uploadé"""
        # Vérifier la taille
        max_size = 100 * 1024 * 1024  # 100MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Le fichier est trop volumineux. Taille maximale : {max_size // (1024*1024)}MB"
            )
        
        # Vérifier l'extension
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm', '.mov', '.avi']
        import os
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Format de fichier non supporté. Formats autorisés : {', '.join(allowed_extensions)}"
            )
        
        return value


class BulkMediaUploadSerializer(serializers.Serializer):
    """Serializer pour l'upload multiple de médias"""
    
    files = serializers.ListField(
        child=serializers.FileField(),
        min_length=1,
        max_length=10
    )
    usage_type = serializers.ChoiceField(
        choices=MediaFile.USAGE_TYPES,
        default='post'
    )
    
    def validate_files(self, value):
        """Valide la liste de fichiers"""
        total_size = sum(f.size for f in value)
        max_total_size = 200 * 1024 * 1024  # 200MB total
        
        if total_size > max_total_size:
            raise serializers.ValidationError(
                f"Taille totale trop importante. Maximum : {max_total_size // (1024*1024)}MB"
            )
        
        return value


class MediaProcessingQueueSerializer(serializers.ModelSerializer):
    """Serializer pour les tâches de traitement"""
    
    media_file = MediaFileSerializer(read_only=True)
    
    class Meta:
        model = MediaProcessingQueue
        fields = [
            'id', 'media_file', 'task_type', 'status', 'progress',
            'error_message', 'result_data', 'priority', 'attempts',
            'max_attempts', 'created_at', 'started_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'started_at', 'completed_at'
        ]


class MediaAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer pour les analytics des médias"""
    
    media_file = MediaFileSerializer(read_only=True)
    engagement_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = MediaAnalytics
        fields = [
            'media_file', 'total_views', 'unique_views', 'total_likes',
            'total_shares', 'total_downloads', 'average_view_duration',
            'bounce_rate', 'engagement_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at'
        ]
    
    def get_engagement_rate(self, obj):
        """Calcule le taux d'engagement"""
        if obj.total_views == 0:
            return 0.0
        
        total_interactions = obj.total_likes + obj.total_shares + obj.total_downloads
        return round((total_interactions / obj.total_views) * 100, 2)


class MediaLibrarySerializer(serializers.Serializer):
    """Serializer pour la bibliothèque média"""
    
    type = serializers.ChoiceField(
        choices=[choice[0] for choice in MediaFile.MEDIA_TYPES],
        required=False
    )
    usage = serializers.ChoiceField(
        choices=[choice[0] for choice in MediaFile.USAGE_TYPES],
        required=False
    )
    page = serializers.IntegerField(default=1, min_value=1)
    per_page = serializers.IntegerField(default=20, min_value=1, max_value=50)
    search = serializers.CharField(required=False, max_length=100)
    
    def validate_page(self, value):
        """Valide le numéro de page"""
        if value < 1:
            raise serializers.ValidationError("Le numéro de page doit être positif")
        return value


class AttachMediaToPostSerializer(serializers.Serializer):
    """Serializer pour attacher des médias à un post"""
    
    post_id = serializers.IntegerField()
    media_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=4
    )
    descriptions = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=True),
        required=False,
        allow_empty=True
    )
    
    def validate(self, data):
        """Validation croisée"""
        media_ids = data.get('media_ids', [])
        descriptions = data.get('descriptions', [])
        
        # Si des descriptions sont fournies, elles doivent correspondre aux médias
        if descriptions and len(descriptions) != len(media_ids):
            raise serializers.ValidationError(
                "Le nombre de descriptions doit correspondre au nombre de médias"
            )
        
        return data
    
    def validate_post_id(self, value):
        """Valide que le post existe et appartient à l'utilisateur"""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Utilisateur requis")
        
        from .models import Post
        try:
            post = Post.objects.get(id=value, author=request.user)
            return value
        except Post.DoesNotExist:
            raise serializers.ValidationError("Post introuvable ou accès refusé")
    
    def validate_media_ids(self, value):
        """Valide que tous les médias existent et appartiennent à l'utilisateur"""
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Utilisateur requis")
        
        existing_media = MediaFile.objects.filter(
            id__in=value,
            uploaded_by=request.user,
            is_approved=True
        )
        
        if len(existing_media) != len(value):
            raise serializers.ValidationError(
                "Certains médias sont introuvables ou non approuvés"
            )
        
        return value


class MediaStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques globales des médias"""
    
    total_media = serializers.IntegerField()
    total_images = serializers.IntegerField()
    total_videos = serializers.IntegerField()
    total_storage_used = serializers.IntegerField()  # en bytes
    total_views = serializers.IntegerField()
    total_likes = serializers.IntegerField()
    total_shares = serializers.IntegerField()
    most_popular_media = MediaFileSerializer(many=True)
    recent_uploads = MediaFileSerializer(many=True)
    
    def to_representation(self, instance):
        """Convertit les données pour l'affichage"""
        data = super().to_representation(instance)
        
        # Convertir la taille de stockage en format lisible
        storage_bytes = data.get('total_storage_used', 0)
        if storage_bytes > 1024**3:  # GB
            data['storage_used_formatted'] = f"{storage_bytes / (1024**3):.2f} GB"
        elif storage_bytes > 1024**2:  # MB
            data['storage_used_formatted'] = f"{storage_bytes / (1024**2):.2f} MB"
        else:  # KB
            data['storage_used_formatted'] = f"{storage_bytes / 1024:.2f} KB"
        
        return data


class MediaSearchSerializer(serializers.Serializer):
    """Serializer pour la recherche de médias"""
    
    query = serializers.CharField(max_length=100)
    media_type = serializers.ChoiceField(
        choices=[choice[0] for choice in MediaFile.MEDIA_TYPES],
        required=False
    )
    usage_type = serializers.ChoiceField(
        choices=[choice[0] for choice in MediaFile.USAGE_TYPES],
        required=False
    )
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    min_views = serializers.IntegerField(required=False, min_value=0)
    min_likes = serializers.IntegerField(required=False, min_value=0)
    
    def validate(self, data):
        """Validation croisée des dates"""
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                "La date de début doit être antérieure à la date de fin"
            )
        
        return data


class MediaModerationSerializer(serializers.ModelSerializer):
    """Serializer pour la modération des médias (admin)"""
    
    class Meta:
        model = MediaFile
        fields = [
            'id', 'is_approved', 'processing_error'
        ]
    
    def update(self, instance, validated_data):
        """Met à jour le statut de modération"""
        instance.is_approved = validated_data.get('is_approved', instance.is_approved)
        instance.processing_error = validated_data.get('processing_error', instance.processing_error)
        instance.save()
        return instance