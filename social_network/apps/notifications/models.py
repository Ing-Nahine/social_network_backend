from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone

User = get_user_model()

class Notification(models.Model):
    """Modèle pour les notifications"""
    
    NOTIFICATION_TYPES = [
        ('like', _('Like')),
        ('comment', _('Commentaire')),
        ('retweet', _('Retweet')),
        ('follow', _('Nouveau follower')),
        ('mention', _('Mention')),
        ('quote', _('Quote tweet')),
        ('reply', _('Réponse')),
        ('system', _('Notification système')),
    ]
    
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Destinataire')
    )
    
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sent_notifications',
        verbose_name=_('Expéditeur')
    )
    
    notification_type = models.CharField(
        _('Type de notification'),
        max_length=20,
        choices=NOTIFICATION_TYPES
    )
    
    title = models.CharField(_('Titre'), max_length=100)
    message = models.TextField(_('Message'), max_length=500)
    
    # Lien générique vers l'objet concerné (post, commentaire, etc.)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Métadonnées
    is_read = models.BooleanField(_('Lu'), default=False)
    is_email_sent = models.BooleanField(_('Email envoyé'), default=False)
    is_push_sent = models.BooleanField(_('Push envoyé'), default=False)
    
    # Données additionnelles (JSON)
    extra_data = models.JSONField(_('Données supplémentaires'), default=dict, blank=True)
    
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    read_at = models.DateTimeField(_('Lu le'), null=True, blank=True)

    class Meta:
        db_table = 'notifications'
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"Notification {self.notification_type} pour {self.recipient.username}"

    def mark_as_read(self):
        """Marquer la notification comme lue"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    @property
    def action_url(self):
        """Génère l'URL d'action pour la notification"""
        if self.notification_type in ['like', 'comment', 'retweet', 'quote', 'reply']:
            if hasattr(self.content_object, 'id'):
                return f"/posts/{self.content_object.id}/"
        elif self.notification_type == 'follow':
            if self.sender:
                return f"/profile/{self.sender.username}/"
        elif self.notification_type == 'mention':
            if hasattr(self.content_object, 'post'):
                return f"/posts/{self.content_object.post.id}/"
        return "/"


class NotificationPreference(models.Model):
    """Modèle pour les préférences de notifications utilisateur"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name=_('Utilisateur')
    )
    
    # Préférences par type de notification
    likes_email = models.BooleanField(_('Likes par email'), default=True)
    likes_push = models.BooleanField(_('Likes push'), default=True)
    
    comments_email = models.BooleanField(_('Commentaires par email'), default=True)
    comments_push = models.BooleanField(_('Commentaires push'), default=True)
    
    retweets_email = models.BooleanField(_('Retweets par email'), default=True)
    retweets_push = models.BooleanField(_('Retweets push'), default=True)
    
    follows_email = models.BooleanField(_('Nouveaux followers par email'), default=True)
    follows_push = models.BooleanField(_('Nouveaux followers push'), default=True)
    
    mentions_email = models.BooleanField(_('Mentions par email'), default=True)
    mentions_push = models.BooleanField(_('Mentions push'), default=True)
    
    quotes_email = models.BooleanField(_('Quote tweets par email'), default=True)
    quotes_push = models.BooleanField(_('Quote tweets push'), default=True)
    
    replies_email = models.BooleanField(_('Réponses par email'), default=True)
    replies_push = models.BooleanField(_('Réponses push'), default=True)
    
    system_email = models.BooleanField(_('Notifications système par email'), default=True)
    system_push = models.BooleanField(_('Notifications système push'), default=False)
    
    # Paramètres généraux
    digest_frequency = models.CharField(
        _('Fréquence du digest'),
        max_length=20,
        choices=[
            ('never', _('Jamais')),
            ('daily', _('Quotidien')),
            ('weekly', _('Hebdomadaire')),
            ('monthly', _('Mensuel')),
        ],
        default='weekly'
    )
    
    quiet_hours_start = models.TimeField(_('Début heures silencieuses'), null=True, blank=True)
    quiet_hours_end = models.TimeField(_('Fin heures silencieuses'), null=True, blank=True)
    
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)

    class Meta:
        db_table = 'notification_preferences'
        verbose_name = _('Préférence de notification')
        verbose_name_plural = _('Préférences de notifications')

    def __str__(self):
        return f"Préférences de notification pour {self.user.username}"

    def can_send_email(self, notification_type):
        """Vérifie si on peut envoyer un email pour ce type de notification"""
        field_name = f"{notification_type}_email"
        return getattr(self, field_name, False)

    def can_send_push(self, notification_type):
        """Vérifie si on peut envoyer une notification push pour ce type"""
        field_name = f"{notification_type}_push"
        return getattr(self, field_name, False)


class PushSubscription(models.Model):
    """Modèle pour les abonnements push notification (WebPush)"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
        verbose_name=_('Utilisateur')
    )
    
    endpoint = models.URLField(_('Endpoint'), max_length=500)
    p256dh_key = models.CharField(_('Clé P256DH'), max_length=100)
    auth_key = models.CharField(_('Clé Auth'), max_length=50)
    
    # Métadonnées du navigateur/appareil
    user_agent = models.TextField(_('User Agent'), blank=True)
    device_name = models.CharField(_('Nom de l\'appareil'), max_length=100, blank=True)
    
    is_active = models.BooleanField(_('Actif'), default=True)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    last_used_at = models.DateTimeField(_('Dernière utilisation'), auto_now=True)

    class Meta:
        db_table = 'push_subscriptions'
        verbose_name = _('Abonnement Push')
        verbose_name_plural = _('Abonnements Push')
        unique_together = ('user', 'endpoint')
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['endpoint']),
        ]

    def __str__(self):
        return f"Abonnement push pour {self.user.username}"


class NotificationBatch(models.Model):
    """Modèle pour les lots de notifications (digest)"""
    
    BATCH_TYPES = [
        ('daily', _('Digest quotidien')),
        ('weekly', _('Digest hebdomadaire')),
        ('monthly', _('Digest mensuel')),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notification_batches',
        verbose_name=_('Utilisateur')
    )
    
    batch_type = models.CharField(_('Type de lot'), max_length=20, choices=BATCH_TYPES)
    notifications = models.ManyToManyField(
        Notification,
        related_name='batches',
        verbose_name=_('Notifications')
    )
    
    subject = models.CharField(_('Sujet'), max_length=200)
    content = models.TextField(_('Contenu'))
    
    is_sent = models.BooleanField(_('Envoyé'), default=False)
    sent_at = models.DateTimeField(_('Envoyé le'), null=True, blank=True)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'notification_batches'
        verbose_name = _('Lot de notifications')
        verbose_name_plural = _('Lots de notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'batch_type']),
            models.Index(fields=['is_sent', 'created_at']),
        ]

    def __str__(self):
        return f"Lot {self.batch_type} pour {self.user.username}"

    def mark_as_sent(self):
        """Marquer le lot comme envoyé"""
        self.is_sent = True
        self.sent_at = models.timezone.now()
        self.save(update_fields=['is_sent', 'sent_at'])