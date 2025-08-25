from django.conf import settings
from pywebpush import webpush, WebPushException
import json
import logging

from .models import Notification, NotificationPreference, PushSubscription

logger = logging.getLogger(__name__)


def create_notification(recipient, sender, notification_type, title, message, content_object=None, extra_data=None):
    """
    Créer une notification et l'envoyer via push si activé
    
    Args:
        recipient: Utilisateur destinataire
        sender: Utilisateur expéditeur (peut être None)
        notification_type: Type de notification ('like', 'comment', etc.)
        title: Titre de la notification
        message: Message de la notification
        content_object: Objet lié (post, commentaire, etc.)
        extra_data: Données supplémentaires (dict)
    """
    
    # Créer la notification en base
    notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        title=title,
        message=message,
        content_object=content_object,
        extra_data=extra_data or {}
    )
    
    # Vérifier les préférences utilisateur
    preferences, _ = NotificationPreference.objects.get_or_create(user=recipient)
    
    # Envoyer push notification si activé
    if preferences.can_send_push(notification_type):
        send_push_notification(notification)
    
    return notification


def send_push_notification(notification):
    """
    Envoyer une push notification
    
    Args:
        notification: Instance de Notification
    """
    if not hasattr(settings, 'WEBPUSH_SETTINGS'):
        logger.warning("WEBPUSH_SETTINGS non configuré")
        return
    
    # Récupérer les abonnements actifs de l'utilisateur
    subscriptions = PushSubscription.objects.filter(
        user=notification.recipient,
        is_active=True
    )
    
    if not subscriptions.exists():
        logger.info(f"Aucun abonnement push pour {notification.recipient.username}")
        return
    
    # Préparer le payload
    payload = {
        'title': notification.title,
        'message': notification.message,
        'notification_id': notification.id,
        'type': notification.notification_type,
        'action_url': notification.action_url,
        'sender': notification.sender.username if notification.sender else None,
        'sender_avatar': notification.sender.get_avatar_url() if notification.sender else None,
        'timestamp': notification.created_at.isoformat()
    }
    
    # Envoyer à tous les abonnements
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': subscription.endpoint,
                    'keys': {
                        'p256dh': subscription.p256dh_key,
                        'auth': subscription.auth_key
                    }
                },
                data=json.dumps(payload),
                vapid_private_key=settings.WEBPUSH_SETTINGS.get('VAPID_PRIVATE_KEY'),
                vapid_claims={
                    'sub': settings.WEBPUSH_SETTINGS.get('VAPID_CLAIMS_EMAIL')
                }
            )
            
            logger.info(f"Push notification envoyée à {subscription.id}")
            
        except WebPushException as e:
            logger.error(f"Erreur push notification pour {subscription.id}: {e}")
            
            # Si l'abonnement est expiré/invalide, le désactiver
            if e.response and e.response.status_code in [410, 404]:
                subscription.is_active = False
                subscription.save()
                logger.info(f"Abonnement {subscription.id} désactivé")
        
        except Exception as e:
            logger.error(f"Erreur inattendue pour {subscription.id}: {e}")
    
    # Marquer comme envoyé
    notification.is_push_sent = True
    notification.save(update_fields=['is_push_sent'])


# Fonctions utilitaires pour créer des notifications spécifiques

def notify_like(post, user):
    """Notifier l'auteur d'un like sur son post"""
    if post.author != user:
        create_notification(
            recipient=post.author,
            sender=user,
            notification_type='like',
            title='Nouveau like',
            message=f'{user.display_name} a aimé votre post',
            content_object=post
        )


def notify_comment(post, comment, user):
    """Notifier l'auteur d'un commentaire sur son post"""
    if post.author != user:
        create_notification(
            recipient=post.author,
            sender=user,
            notification_type='comment',
            title='Nouveau commentaire',
            message=f'{user.display_name} a commenté votre post',
            content_object=comment
        )


def notify_retweet(post, user):
    """Notifier l'auteur d'un retweet de son post"""
    if post.author != user:
        create_notification(
            recipient=post.author,
            sender=user,
            notification_type='retweet',
            title='Nouveau retweet',
            message=f'{user.display_name} a retweeté votre post',
            content_object=post
        )


def notify_follow(followed_user, follower):
    """Notifier qu'un utilisateur a un nouveau follower"""
    create_notification(
        recipient=followed_user,
        sender=follower,
        notification_type='follow',
        title='Nouveau follower',
        message=f'{follower.display_name} vous suit maintenant'
    )


def notify_mention(mentioned_user, post, author):
    """Notifier une mention dans un post"""
    if mentioned_user != author:
        create_notification(
            recipient=mentioned_user,
            sender=author,
            notification_type='mention',
            title='Vous avez été mentionné',
            message=f'{author.display_name} vous a mentionné dans un post',
            content_object=post
        )