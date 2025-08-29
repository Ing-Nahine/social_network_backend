import os
import uuid
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit, ResizeToFill
from PIL import Image

User = get_user_model()


def get_upload_path(instance, filename):
    """Génère un chemin d'upload unique pour les médias"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    
    if instance.media_type == 'image':
        return f'media/images/{filename}'
    elif instance.media_type == 'video':
        return f'media/videos/{filename}'
    elif instance.media_type == 'gif':
        return f'media/gifs/{filename}'
    else:
        return f'media/other/{filename}'


def validate_image_size(image):
    """Valide la taille de l'image (max 10MB)"""
    max_size = 10 * 1024 * 1024  # 10MB
    if image.size > max_size:
        raise ValidationError(_('La taille de l\'image ne peut pas dépasser 10MB.'))


def validate_video_size(video):
    """Valide la taille de la vidéo (max 100MB)"""
    max_size = 100 * 1024 * 1024  # 100MB
    if video.size > max_size:
        raise ValidationError(_('La taille de la vidéo ne peut pas dépasser 100MB.'))


class MediaFile(models.Model):
    """Modèle de base pour tous les fichiers médias"""
    
    MEDIA_TYPES = [
        ('image', _('Image')),
        ('video', _('Vidéo')),
        ('gif', _('GIF')),
        ('audio', _('Audio')),
    ]
    
    USAGE_TYPES = [
        ('post', _('Post')),
        ('profile_avatar', _('Avatar de profil')),
        ('profile_banner', _('Bannière de profil')),
        ('message', _('Message privé')),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uploaded_media',
        verbose_name=_('Uploadé par')
    )
    
    # Type et usage
    media_type = models.CharField(_('Type de média'), max_length=10, choices=MEDIA_TYPES)
    usage_type = models.CharField(_('Type d\'usage'), max_length=20, choices=USAGE_TYPES)
    
    # Fichier principal
    file = models.FileField(
        upload_to=get_upload_path,
        verbose_name=_('Fichier'),
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'webm', 'mov', 'avi', 'mp3', 'wav']
            )
        ]
    )
    
    # Métadonnées
    original_filename = models.CharField(_('Nom de fichier original'), max_length=255)
    file_size = models.PositiveIntegerField(_('Taille du fichier (bytes)'), null=True, blank=True)
    mime_type = models.CharField(_('Type MIME'), max_length=100, blank=True)
    
    # Dimensions pour images/vidéos
    width = models.PositiveIntegerField(_('Largeur'), null=True, blank=True)
    height = models.PositiveIntegerField(_('Hauteur'), null=True, blank=True)
    
    # Durée pour vidéos/audio (en secondes)
    duration = models.PositiveIntegerField(_('Durée (secondes)'), null=True, blank=True)
    
    # Accessibilité
    alt_text = models.CharField(_('Texte alternatif'), max_length=200, blank=True)
    
    # Statut
    is_processed = models.BooleanField(_('Traité'), default=False)
    is_approved = models.BooleanField(_('Approuvé'), default=True)
    processing_error = models.TextField(_('Erreur de traitement'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)

    class Meta:
        db_table = 'media_files'
        verbose_name = _('Fichier média')
        verbose_name_plural = _('Fichiers médias')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uploaded_by', '-created_at']),
            models.Index(fields=['media_type', '-created_at']),
            models.Index(fields=['usage_type', '-created_at']),
            models.Index(fields=['is_approved', '-created_at']),
        ]

    def __str__(self):
        return f"{self.media_type} - {self.original_filename}"

    def clean(self):
        """Validation personnalisée"""
        if self.file:
            # Validation de la taille selon le type
            if self.media_type == 'image':
                validate_image_size(self.file)
            elif self.media_type == 'video':
                validate_video_size(self.file)

    def save(self, *args, **kwargs):
        if self.file:
            self.original_filename = self.file.name
            self.file_size = self.file.size
            
            # Déterminer le type MIME
            if self.file.name.lower().endswith(('.jpg', '.jpeg')):
                self.mime_type = 'image/jpeg'
            elif self.file.name.lower().endswith('.png'):
                self.mime_type = 'image/png'
            elif self.file.name.lower().endswith('.gif'):
                self.mime_type = 'image/gif'
            elif self.file.name.lower().endswith('.webp'):
                self.mime_type = 'image/webp'
            elif self.file.name.lower().endswith('.mp4'):
                self.mime_type = 'video/mp4'
            elif self.file.name.lower().endswith('.webm'):
                self.mime_type = 'video/webm'
        
        super().save(*args, **kwargs)

    @property
    def file_url(self):
        """Retourne l'URL du fichier"""
        return self.file.url if self.file else None

    @property
    def thumbnail_url(self):
        """Retourne l'URL de la miniature (si disponible)"""
        thumbnail = self.thumbnails.filter(size='medium').first()
        return thumbnail.file_url if thumbnail else self.file_url

    def get_file_extension(self):
        """Retourne l'extension du fichier"""
        return os.path.splitext(self.original_filename)[1].lower()


class MediaThumbnail(models.Model):
    """Miniatures générées pour les médias"""
    
    THUMBNAIL_SIZES = [
        ('small', _('Petit (150x150)')),
        ('medium', _('Moyen (400x400)')),
        ('large', _('Grand (800x800)')),
    ]
    
    media_file = models.ForeignKey(
        MediaFile,
        on_delete=models.CASCADE,
        related_name='thumbnails',
        verbose_name=_('Fichier média')
    )
    
    size = models.CharField(_('Taille'), max_length=10, choices=THUMBNAIL_SIZES)
    
    thumbnail = ProcessedImageField(
        upload_to='media/thumbnails/',
        processors=[ResizeToFit(800, 800)],  # Sera ajusté selon la taille
        format='JPEG',
        options={'quality': 85},
        verbose_name=_('Miniature')
    )
    
    width = models.PositiveIntegerField(_('Largeur'))
    height = models.PositiveIntegerField(_('Hauteur'))
    file_size = models.PositiveIntegerField(_('Taille du fichier'))
    
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'media_thumbnails'
        verbose_name = _('Miniature')
        verbose_name_plural = _('Miniatures')
        unique_together = ('media_file', 'size')
        indexes = [
            models.Index(fields=['media_file', 'size']),
        ]

    def __str__(self):
        return f"Miniature {self.size} pour {self.media_file}"

    @property
    def file_url(self):
        return self.thumbnail.url if self.thumbnail else None


class MediaProcessingQueue(models.Model):
    """File d'attente pour le traitement des médias"""
    
    STATUS_CHOICES = [
        ('pending', _('En attente')),
        ('processing', _('En cours')),
        ('completed', _('Terminé')),
        ('failed', _('Échec')),
    ]
    
    TASK_TYPES = [
        ('thumbnail_generation', _('Génération de miniatures')),
        ('video_compression', _('Compression vidéo')),
        ('image_optimization', _('Optimisation image')),
        ('metadata_extraction', _('Extraction métadonnées')),
    ]
    
    media_file = models.ForeignKey(
        MediaFile,
        on_delete=models.CASCADE,
        related_name='processing_tasks',
        verbose_name=_('Fichier média')
    )
    
    task_type = models.CharField(_('Type de tâche'), max_length=30, choices=TASK_TYPES)
    status = models.CharField(_('Statut'), max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Progression et résultats
    progress = models.PositiveIntegerField(_('Progression (%)'), default=0)
    error_message = models.TextField(_('Message d\'erreur'), blank=True)
    result_data = models.JSONField(_('Données de résultat'), default=dict, blank=True)
    
    # Priorité (plus le nombre est élevé, plus c'est prioritaire)
    priority = models.PositiveIntegerField(_('Priorité'), default=5)
    
    # Tentatives
    attempts = models.PositiveIntegerField(_('Tentatives'), default=0)
    max_attempts = models.PositiveIntegerField(_('Tentatives max'), default=3)
    
    # Timestamps
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    started_at = models.DateTimeField(_('Démarré le'), null=True, blank=True)
    completed_at = models.DateTimeField(_('Terminé le'), null=True, blank=True)

    class Meta:
        db_table = 'media_processing_queue'
        verbose_name = _('Tâche de traitement')
        verbose_name_plural = _('Tâches de traitement')
        ordering = ['-priority', 'created_at']
        indexes = [
            models.Index(fields=['status', '-priority']),
            models.Index(fields=['media_file', 'task_type']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.task_type} - {self.media_file} ({self.status})"

    @property
    def can_retry(self):
        """Vérifie si la tâche peut être relancée"""
        return self.status == 'failed' and self.attempts < self.max_attempts


class MediaAnalytics(models.Model):
    """Statistiques d'usage des médias"""
    
    media_file = models.OneToOneField(
        MediaFile,
        on_delete=models.CASCADE,
        related_name='analytics',
        verbose_name=_('Fichier média')
    )
    
    # Statistiques de vues
    total_views = models.PositiveIntegerField(_('Vues totales'), default=0)
    unique_views = models.PositiveIntegerField(_('Vues uniques'), default=0)
    
    # Interactions
    total_likes = models.PositiveIntegerField(_('Likes totaux'), default=0)
    total_shares = models.PositiveIntegerField(_('Partages totaux'), default=0)
    total_downloads = models.PositiveIntegerField(_('Téléchargements totaux'), default=0)
    
    # Performance
    average_view_duration = models.FloatField(_('Durée moyenne de vue (%)'), default=0.0)
    bounce_rate = models.FloatField(_('Taux de rebond (%)'), default=0.0)
    
    # Timestamps
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)

    class Meta:
        db_table = 'media_analytics'
        verbose_name = _('Analytique média')
        verbose_name_plural = _('Analytiques médias')

    def __str__(self):
        return f"Analytics pour {self.media_file}"