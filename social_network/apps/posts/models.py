from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit

User = get_user_model()


class Post(models.Model):
    """Modèle pour les posts/tweets"""
    
    POST_TYPES = [
        ('original', _('Post original')),
        ('retweet', _('Retweet')),
        ('quote', _('Quote tweet')),
        ('reply', _('Réponse')),
    ]
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name=_('Auteur')
    )
    
    content = models.TextField(_('Contenu'), max_length=280)
    post_type = models.CharField(_('Type de post'), max_length=10, choices=POST_TYPES, default='original')
    
    # Relations pour retweets et réponses
    parent_post = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_('Post parent')
    )
    
    original_post = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='retweets',
        verbose_name=_('Post original')
    )
    
    # Statistiques
    likes_count = models.PositiveIntegerField(_('Nombre de likes'), default=0)
    retweets_count = models.PositiveIntegerField(_('Nombre de retweets'), default=0)
    replies_count = models.PositiveIntegerField(_('Nombre de réponses'), default=0)
    views_count = models.PositiveIntegerField(_('Nombre de vues'), default=0)
    
    # Paramètres
    is_pinned = models.BooleanField(_('Post épinglé'), default=False)
    allow_replies = models.BooleanField(_('Autoriser les réponses'), default=True)
    is_sensitive = models.BooleanField(_('Contenu sensible'), default=False)
    
    # Géolocalisation
    latitude = models.FloatField(_('Latitude'), null=True, blank=True)
    longitude = models.FloatField(_('Longitude'), null=True, blank=True)
    location_name = models.CharField(_('Nom du lieu'), max_length=100, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)
    scheduled_at = models.DateTimeField(_('Programmé pour'), null=True, blank=True)
    
    class Meta:
        db_table = 'posts'
        verbose_name = _('Post')
        verbose_name_plural = _('Posts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['post_type', '-created_at']),
            models.Index(fields=['parent_post', '-created_at']),
            models.Index(fields=['is_pinned', '-created_at']),
            models.Index(fields=['-likes_count']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"@{self.author.username}: {content_preview}"

    def save(self, *args, **kwargs):
        """Mise à jour du compteur de posts de l'utilisateur"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new and self.post_type == 'original':
            User.objects.filter(id=self.author.id).update(
                posts_count=models.F('posts_count') + 1
            )

    def delete(self, *args, **kwargs):
        """Mise à jour du compteur de posts lors de la suppression"""
        if self.post_type == 'original':
            User.objects.filter(id=self.author.id).update(
                posts_count=models.F('posts_count') - 1
            )
        super().delete(*args, **kwargs)

    @property
    def is_retweet(self):
        """Vérifie si le post est un retweet"""
        return self.post_type == 'retweet'

    @property
    def is_reply(self):
        """Vérifie si le post est une réponse"""
        return self.post_type == 'reply'

    @property
    def engagement_rate(self):
        """Calcule le taux d'engagement du post"""
        if self.views_count == 0:
            return 0
        total_interactions = self.likes_count + self.retweets_count + self.replies_count
        return (total_interactions / self.views_count) * 100


class PostMedia(models.Model):
    """Modèle pour les médias attachés aux posts"""
    
    MEDIA_TYPES = [
        ('image', _('Image')),
        ('video', _('Vidéo')),
        ('gif', _('GIF')),
    ]
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='media',
        verbose_name=_('Post')
    )
    
    media_type = models.CharField(_('Type de média'), max_length=10, choices=MEDIA_TYPES)
    
    media_file = models.ForeignKey(
        'media_management.MediaFile',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Fichier média')
    )
    
    # Fichiers
    image = ProcessedImageField(
        upload_to='posts/images/',
        processors=[ResizeToFit(2048, 2048)],
        format='JPEG',
        options={'quality': 85},
        null=True,
        blank=True,
        verbose_name=_('Image')
    )
    
    video = models.FileField(
        upload_to='posts/videos/',
        null=True,
        blank=True,
        verbose_name=_('Vidéo')
    )
    
    # Métadonnées
    alt_text = models.CharField(_('Texte alternatif'), max_length=200, blank=True)
    width = models.PositiveIntegerField(_('Largeur'), null=True, blank=True)
    height = models.PositiveIntegerField(_('Hauteur'), null=True, blank=True)
    file_size = models.PositiveIntegerField(_('Taille du fichier'), null=True, blank=True)
    duration = models.PositiveIntegerField(_('Durée (secondes)'), null=True, blank=True)
    
    # Position dans le post (pour l'ordre d'affichage)
    order = models.PositiveIntegerField(_('Ordre'), default=0)
    
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'post_media'
        verbose_name = _('Média de post')
        verbose_name_plural = _('Médias de posts')
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['post', 'order']),
            models.Index(fields=['media_type']),
        ]

    def __str__(self):
        return f"Média {self.media_type} pour post {self.post.id}"

    @property
    def file_url(self):
        """Retourne l'URL du fichier média"""
        if self.media_type == 'image' and self.image:
            return self.image.url
        elif self.media_type in ['video', 'gif'] and self.video:
            return self.video.url
        return None


class Hashtag(models.Model):
    """Modèle pour les hashtags"""
    
    name = models.CharField(_('Nom'), max_length=100, unique=True)
    posts_count = models.PositiveIntegerField(_('Nombre de posts'), default=0)
    trending_score = models.FloatField(_('Score de tendance'), default=0.0)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)

    class Meta:
        db_table = 'hashtags'
        verbose_name = _('Hashtag')
        verbose_name_plural = _('Hashtags')
        ordering = ['-posts_count']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['-posts_count']),
            models.Index(fields=['-trending_score']),
        ]

    def __str__(self):
        return f"#{self.name}"


class PostHashtag(models.Model):
    """Relation many-to-many entre posts et hashtags"""
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='hashtag_relations',
        verbose_name=_('Post')
    )
    hashtag = models.ForeignKey(
        Hashtag,
        on_delete=models.CASCADE,
        related_name='post_relations',
        verbose_name=_('Hashtag')
    )
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'post_hashtags'
        verbose_name = _('Post Hashtag')
        verbose_name_plural = _('Posts Hashtags')
        unique_together = ('post', 'hashtag')
        indexes = [
            models.Index(fields=['post']),
            models.Index(fields=['hashtag']),
        ]

    def __str__(self):
        return f"{self.post} - #{self.hashtag.name}"


class Mention(models.Model):
    """Modèle pour les mentions d'utilisateurs dans les posts"""
    
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='mentions',
        verbose_name=_('Post')
    )
    mentioned_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='mentions_received',
        verbose_name=_('Utilisateur mentionné')
    )
    position = models.PositiveIntegerField(_('Position dans le texte'), default=0)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'post_mentions'
        verbose_name = _('Mention')
        verbose_name_plural = _('Mentions')
        unique_together = ('post', 'mentioned_user')
        indexes = [
            models.Index(fields=['post']),
            models.Index(fields=['mentioned_user', '-created_at']),
        ]

    def __str__(self):
        return f"@{self.mentioned_user.username} dans post {self.post.id}"