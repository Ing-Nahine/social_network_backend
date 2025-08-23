from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit


class User(AbstractUser):
    """Modèle utilisateur personnalisé"""
    
    email = models.EmailField(_('email address'), unique=True)
    bio = models.TextField(_('Bio'), max_length=500, blank=True)
    birth_date = models.DateField(_('Date de naissance'), null=True, blank=True)
    location = models.CharField(_('Localisation'), max_length=100, blank=True)
    website = models.URLField(_('Site web'), blank=True)
    is_verified = models.BooleanField(_('Compte vérifié'), default=False)
    is_private = models.BooleanField(_('Compte privé'), default=False)
    
    # Images de profil
    avatar = ProcessedImageField(
        upload_to='avatars/',
        processors=[ResizeToFit(400, 400)],
        format='JPEG',
        options={'quality': 90},
        null=True,
        blank=True,
        verbose_name=_('Avatar')
    )
    
    banner = ProcessedImageField(
        upload_to='banners/',
        processors=[ResizeToFit(1500, 500)],
        format='JPEG',
        options={'quality': 90},
        null=True,
        blank=True,
        verbose_name=_('Bannière')
    )
    
    # Statistiques
    followers_count = models.PositiveIntegerField(_('Nombre de followers'), default=0)
    following_count = models.PositiveIntegerField(_('Nombre de suivis'), default=0)
    posts_count = models.PositiveIntegerField(_('Nombre de posts'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)
    last_active = models.DateTimeField(_('Dernière activité'), default=timezone.now)

    USERNAME_FIELD = ('email')
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'
        verbose_name = _('Utilisateur')
        verbose_name_plural = _('Utilisateurs')
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"@{self.username}"

    @property
    def display_name(self):
        """Retourne le nom d'affichage (first_name last_name ou username)"""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.username

    def get_avatar_url(self):
        """Retourne l'URL de l'avatar ou une image par défaut"""
        if self.avatar:
            return self.avatar.url
        return '/static/images/default-avatar.png'

    def get_banner_url(self):
        """Retourne l'URL de la bannière ou une image par défaut"""
        if self.banner:
            return self.banner.url
        return '/static/images/default-banner.png'


class Follow(models.Model):
    """Modèle pour les relations de suivi entre utilisateurs"""
    
    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='following',
        verbose_name=_('Follower')
    )
    followed = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='followers',
        verbose_name=_('Suivi')
    )
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'user_follows'
        verbose_name = _('Suivi')
        verbose_name_plural = _('Suivis')
        unique_together = ('follower', 'followed')
        indexes = [
            models.Index(fields=['follower', 'created_at']),
            models.Index(fields=['followed', 'created_at']),
        ]

    def __str__(self):
        return f"{self.follower} suit {self.followed}"

    def clean(self):
        """Validation personnalisée"""
        from django.core.exceptions import ValidationError
        
        if self.follower == self.followed:
            raise ValidationError(_('Un utilisateur ne peut pas se suivre lui-même'))

    def save(self, *args, **kwargs):
        """Mise à jour des compteurs lors de la sauvegarde"""
        self.clean()
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        if is_new:
            # Incrémenter les compteurs
            User.objects.filter(id=self.follower.id).update(
                following_count=models.F('following_count') + 1
            )
            User.objects.filter(id=self.followed.id).update(
                followers_count=models.F('followers_count') + 1
            )

    def delete(self, *args, **kwargs):
        """Mise à jour des compteurs lors de la suppression"""
        follower_id = self.follower.id
        followed_id = self.followed.id
        
        super().delete(*args, **kwargs)
        
        # Décrémenter les compteurs
        User.objects.filter(id=follower_id).update(
            following_count=models.F('following_count') - 1
        )
        User.objects.filter(id=followed_id).update(
            followers_count=models.F('followers_count') - 1
        )


class UserProfile(models.Model):
    """Informations supplémentaires du profil utilisateur"""
    
    THEME_CHOICES = [
        ('light', _('Clair')),
        ('dark', _('Sombre')),
        ('auto', _('Automatique')),
    ]
    
    LANGUAGE_CHOICES = [
        ('fr', _('Français')),
        ('en', _('Anglais')),
        ('es', _('Espagnol')),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('Utilisateur')
    )
    
    # Préférences
    theme = models.CharField(_('Thème'), max_length=10, choices=THEME_CHOICES, default='light')
    language = models.CharField(_('Langue'), max_length=5, choices=LANGUAGE_CHOICES, default='fr')
    email_notifications = models.BooleanField(_('Notifications par email'), default=True)
    push_notifications = models.BooleanField(_('Notifications push'), default=True)
    
    # Paramètres de confidentialité
    show_email = models.BooleanField(_('Afficher email'), default=False)
    show_birth_date = models.BooleanField(_('Afficher date de naissance'), default=False)
    allow_direct_messages = models.BooleanField(_('Autoriser messages directs'), default=True)
    
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)

    class Meta:
        db_table = 'user_profiles'
        verbose_name = _('Profil utilisateur')
        verbose_name_plural = _('Profils utilisateurs')

    def __str__(self):
        return f"Profil de {self.user.username}"