from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import logging
import json
import requests

from .models import (
    Notification, NotificationPreference, PushSubscription, 
    NotificationBatch
)

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_notification(self, recipient_id, sender_id, notification_type, 
                     title, message, content_type_id=None, object_id=None, 
                     extra_data=None):
    """Tâche pour créer et envoyer une notification"""
    try:
        recipient = User.objects.get(id=recipient_id)
        sender = User.objects.get(id=sender_id) if sender_id else None
        
        # Créer la notification
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type=notification_type,
            title=title,
            message=message,
            content_type_id=content_type_id,
            object_id=object_id,
            extra_data=extra_data or {}
        )
        
        # Récupérer les préférences de notification
        preferences, created = NotificationPreference.objects.get_or_create(
            user=recipient
        )
        
        # Envoyer email si activé
        if preferences.can_send_email(notification_type):
            send_email_notification.delay(notification.id)
        
        # Envoyer push si activé
        if preferences.can_send_push(notification_type):
            send_push_notification.delay(notification.id)
        
        return notification.id
        
    except Exception as exc:
        logger.error(f"Erreur lors de l'envoi de notification: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_email_notification(self, notification_id):
    """Envoyer une notification par email"""
    try:
        notification = Notification.objects.select_related(
            'recipient', 'sender'
        ).get(id=notification_id)
        
        if notification.is_email_sent:
            return f"Email déjà envoyé pour la notification {notification_id}"
        
        # Préparer le contexte pour le template
        context = {
            'notification': notification,
            'recipient': notification.recipient,
            'sender': notification.sender,
            'action_url': notification.action_url,
        }
        
        # Générer le contenu HTML
        html_message = render_to_string(
            f'notifications/email/{notification.notification_type}.html',
            context
        )
        
        # Générer le contenu texte
        plain_message = render_to_string(
            f'notifications/email/{notification.notification_type}.txt',
            context
        )
        
        # Envoyer l'email
        success = send_mail(
            subject=notification.title,
            message=plain_message,
            html_message=html_message,
            from_email='noreply@socialnetwork.com',
            recipient_list=[notification.recipient.email],
            fail_silently=False
        )
        
        if success:
            notification.is_email_sent = True
            notification.save(update_fields=['is_email_sent'])
            
        return f"Email envoyé pour la notification {notification_id}"
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} non trouvée")
        return f"Notification {notification_id} non trouvée"
    except Exception as exc:
        logger.error(f"Erreur lors de l'envoi d'email: {exc}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def send_push_notification(self, notification_id):
    """Envoyer une notification push"""
    try:
        notification = Notification.objects.select_related(
            'recipient'
        ).get(id=notification_id)
        
        if notification.is_push_sent:
            return f"Push déjà envoyé pour la notification {notification_id}"
        
        # Récupérer tous les abonnements push actifs de l'utilisateur
        subscriptions = PushSubscription.objects.filter(
            user=notification.recipient,
            is_active=True
        )
        
        if not subscriptions.exists():
            return f"Aucun abonnement push pour l'utilisateur {notification.recipient.username}"
        
        # Préparer le payload de la notification push
        payload = {
            'title': notification.title,
            'body': notification.message,
            'icon': '/static/images/icon-192.png',
            'badge': '/static/images/badge.png',
            'data': {
                'notification_id': notification.id,
                'action_url': notification.action_url,
                'type': notification.notification_type
            }
        }
        
        sent_count = 0
        failed_subscriptions = []
        
        for subscription in subscriptions:
            try:
                # Ici, vous devriez utiliser une bibliothèque comme pywebpush
                # pour envoyer la notification push réelle
                # Pour cet exemple, nous simulons l'envoi
                
                response = send_webpush_notification(
                    subscription.endpoint,
                    subscription.p256dh_key,
                    subscription.auth_key,
                    json.dumps(payload)
                )
                
                if response.status_code == 200:
                    sent_count += 1
                    subscription.last_used_at = timezone.now()
                    subscription.save(update_fields=['last_used_at'])
                else:
                    failed_subscriptions.append(subscription.id)
                    
            except Exception as e:
                logger.error(f"Erreur envoi push pour subscription {subscription.id}: {e}")
                failed_subscriptions.append(subscription.id)
        
        # Désactiver les abonnements défaillants
        if failed_subscriptions:
            PushSubscription.objects.filter(
                id__in=failed_subscriptions
            ).update(is_active=False)
        
        if sent_count > 0:
            notification.is_push_sent = True
            notification.save(update_fields=['is_push_sent'])
        
        return f"Push envoyé à {sent_count} appareils pour la notification {notification_id}"
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} non trouvée")
        return f"Notification {notification_id} non trouvée"
    except Exception as exc:
        logger.error(f"Erreur lors de l'envoi push: {exc}")
        raise self.retry(exc=exc, countdown=300)


def send_webpush_notification(endpoint, p256dh_key, auth_key, payload):
    """Simuler l'envoi d'une notification WebPush"""
    # Dans un vrai projet, utilisez pywebpush ou une autre bibliothèque
    # Ici on simule une réponse réussie
    class MockResponse:
        status_code = 200
    
    return MockResponse()


@shared_task
def send_follow_notification(follower_id, followed_id):
    """Envoyer une notification de nouveau follower"""
    try:
        follower = User.objects.get(id=follower_id)
        followed = User.objects.get(id=followed_id)
        
        send_notification.delay(
            recipient_id=followed_id,
            sender_id=follower_id,
            notification_type='follow',
            title='Nouveau follower',
            message=f'@{follower.username} a commencé à vous suivre'
        )
        
    except User.DoesNotExist:
        logger.error("Utilisateur non trouvé lors de l'envoi de notification de suivi")


@shared_task
def send_like_notification(liker_id, post_id):
    """Envoyer une notification de like"""
    try:
        from apps.posts.models import Post
        from django.contrib.contenttypes.models import ContentType
        
        liker = User.objects.get(id=liker_id)
        post = Post.objects.select_related('author').get(id=post_id)
        
        # Ne pas envoyer de notification si l'utilisateur like son propre post
        if liker == post.author:
            return
        
        content_type = ContentType.objects.get_for_model(Post)
        
        send_notification.delay(
            recipient_id=post.author.id,
            sender_id=liker_id,
            notification_type='like',
            title='Nouveau like',
            message=f'@{liker.username} a aimé votre post',
            content_type_id=content_type.id,
            object_id=post.id
        )
        
    except (User.DoesNotExist, Post.DoesNotExist):
        logger.error("Utilisateur ou post non trouvé lors de l'envoi de notification de like")


@shared_task
def send_comment_notification(commenter_id, post_id):
    """Envoyer une notification de commentaire"""
    try:
        from apps.posts.models import Post
        from django.contrib.contenttypes.models import ContentType
        
        commenter = User.objects.get(id=commenter_id)
        post = Post.objects.select_related('author').get(id=post_id)
        
        # Ne pas envoyer de notification si l'utilisateur commente son propre post
        if commenter == post.author:
            return
        
        content_type = ContentType.objects.get_for_model(Post)
        
        send_notification.delay(
            recipient_id=post.author.id,
            sender_id=commenter_id,
            notification_type='comment',
            title='Nouveau commentaire',
            message=f'@{commenter.username} a commenté votre post',
            content_type_id=content_type.id,
            object_id=post.id
        )
        
    except (User.DoesNotExist, Post.DoesNotExist):
        logger.error("Utilisateur ou post non trouvé lors de l'envoi de notification de commentaire")


@shared_task
def send_mention_notification(mentioner_id, mentioned_id, post_id):
    """Envoyer une notification de mention"""
    try:
        from apps.posts.models import Post
        from django.contrib.contenttypes.models import ContentType
        
        mentioner = User.objects.get(id=mentioner_id)
        mentioned = User.objects.get(id=mentioned_id)
        post = Post.objects.get(id=post_id)
        
        content_type = ContentType.objects.get_for_model(Post)
        
        send_notification.delay(
            recipient_id=mentioned_id,
            sender_id=mentioner_id,
            notification_type='mention',
            title='Vous avez été mentionné',
            message=f'@{mentioner.username} vous a mentionné dans un post',
            content_type_id=content_type.id,
            object_id=post.id
        )
        
    except (User.DoesNotExist, Post.DoesNotExist):
        logger.error("Utilisateur ou post non trouvé lors de l'envoi de notification de mention")


@shared_task
def send_retweet_notification(retweeter_id, post_id):
    """Envoyer une notification de retweet"""
    try:
        from apps.posts.models import Post
        from django.contrib.contenttypes.models import ContentType
        
        retweeter = User.objects.get(id=retweeter_id)
        post = Post.objects.select_related('author').get(id=post_id)
        
        # Ne pas envoyer de notification si l'utilisateur retweet son propre post
        if retweeter == post.author:
            return
        
        content_type = ContentType.objects.get_for_model(Post)
        
        send_notification.delay(
            recipient_id=post.author.id,
            sender_id=retweeter_id,
            notification_type='retweet',
            title='Nouveau retweet',
            message=f'@{retweeter.username} a retweeté votre post',
            content_type_id=content_type.id,
            object_id=post.id
        )
        
    except (User.DoesNotExist, Post.DoesNotExist):
        logger.error("Utilisateur ou post non trouvé lors de l'envoi de notification de retweet")


@shared_task
def send_digest_notifications():
    """Envoyer les notifications digest selon les préférences utilisateur"""
    from datetime import datetime, timedelta
    
    now = timezone.now()
    
    # Digest quotidien (envoyé à 8h du matin)
    if now.hour == 8:
        send_daily_digest.delay()
    
    # Digest hebdomadaire (envoyé le lundi à 8h)
    if now.weekday() == 0 and now.hour == 8:
        send_weekly_digest.delay()
    
    # Digest mensuel (envoyé le 1er du mois à 8h)
    if now.day == 1 and now.hour == 8:
        send_monthly_digest.delay()


@shared_task
def send_daily_digest():
    """Envoyer le digest quotidien"""
    from datetime import datetime, timedelta
    
    yesterday = timezone.now() - timedelta(days=1)
    
    # Utilisateurs ayant opté pour le digest quotidien
    users_with_daily_digest = User.objects.filter(
        notification_preferences__digest_frequency='daily'
    ).select_related('notification_preferences')
    
    for user in users_with_daily_digest:
        # Récupérer les notifications non lues des dernières 24h
        notifications = Notification.objects.filter(
            recipient=user,
            created_at__gte=yesterday,
            is_read=False
        ).order_by('-created_at')
        
        if notifications.exists():
            create_digest_batch.delay(user.id, 'daily', list(notifications.values_list('id', flat=True)))


@shared_task
def send_weekly_digest():
    """Envoyer le digest hebdomadaire"""
    from datetime import datetime, timedelta
    
    last_week = timezone.now() - timedelta(days=7)
    
    users_with_weekly_digest = User.objects.filter(
        notification_preferences__digest_frequency='weekly'
    ).select_related('notification_preferences')
    
    for user in users_with_weekly_digest:
        notifications = Notification.objects.filter(
            recipient=user,
            created_at__gte=last_week,
            is_read=False
        ).order_by('-created_at')
        
        if notifications.exists():
            create_digest_batch.delay(user.id, 'weekly', list(notifications.values_list('id', flat=True)))


@shared_task
def send_monthly_digest():
    """Envoyer le digest mensuel"""
    from datetime import datetime, timedelta
    
    last_month = timezone.now() - timedelta(days=30)
    
    users_with_monthly_digest = User.objects.filter(
        notification_preferences__digest_frequency='monthly'
    ).select_related('notification_preferences')
    
    for user in users_with_monthly_digest:
        notifications = Notification.objects.filter(
            recipient=user,
            created_at__gte=last_month,
            is_read=False
        ).order_by('-created_at')
        
        if notifications.exists():
            create_digest_batch.delay(user.id, 'monthly', list(notifications.values_list('id', flat=True)))


@shared_task
def create_digest_batch(user_id, batch_type, notification_ids):
    """Créer et envoyer un lot de notifications digest"""
    try:
        user = User.objects.get(id=user_id)
        notifications = Notification.objects.filter(id__in=notification_ids)
        
        if not notifications.exists():
            return
        
        # Grouper les notifications par type
        notification_groups = {}
        for notif in notifications:
            if notif.notification_type not in notification_groups:
                notification_groups[notif.notification_type] = []
            notification_groups[notif.notification_type].append(notif)
        
        # Générer le sujet et le contenu du digest
        if batch_type == 'daily':
            subject = f"Votre résumé quotidien - {notifications.count()} nouvelles notifications"
        elif batch_type == 'weekly':
            subject = f"Votre résumé hebdomadaire - {notifications.count()} nouvelles notifications"
        else:
            subject = f"Votre résumé mensuel - {notifications.count()} nouvelles notifications"
        
        # Générer le contenu HTML
        context = {
            'user': user,
            'notification_groups': notification_groups,
            'batch_type': batch_type,
            'total_count': notifications.count()
        }
        
        content = render_to_string('notifications/digest/email_digest.html', context)
        
        # Créer le lot de notifications
        batch = NotificationBatch.objects.create(
            user=user,
            batch_type=batch_type,
            subject=subject,
            content=content
        )
        
        # Associer les notifications au lot
        batch.notifications.set(notifications)
        
        # Envoyer le digest par email
        success = send_mail(
            subject=subject,
            message=content,
            html_message=content,
            from_email='digest@socialnetwork.com',
            recipient_list=[user.email],
            fail_silently=False
        )
        
        if success:
            batch.mark_as_sent()
        
        return f"Digest {batch_type} envoyé à {user.username}"
        
    except User.DoesNotExist:
        logger.error(f"Utilisateur {user_id} non trouvé pour le digest")
    except Exception as e:
        logger.error(f"Erreur lors de la création du digest: {e}")


@shared_task
def cleanup_old_notifications():
    """Nettoyer les anciennes notifications"""
    from datetime import datetime, timedelta
    
    # Supprimer les notifications lues de plus de 30 jours
    old_read_notifications = timezone.now() - timedelta(days=30)
    deleted_read = Notification.objects.filter(
        is_read=True,
        read_at__lt=old_read_notifications
    ).delete()
    
    # Supprimer les notifications non lues de plus de 90 jours
    old_unread_notifications = timezone.now() - timedelta(days=90)
    deleted_unread = Notification.objects.filter(
        is_read=False,
        created_at__lt=old_unread_notifications
    ).delete()
    
    # Supprimer les lots de digest envoyés de plus de 60 jours
    old_batches = timezone.now() - timedelta(days=60)
    deleted_batches = NotificationBatch.objects.filter(
        is_sent=True,
        sent_at__lt=old_batches
    ).delete()
    
    logger.info(f"Nettoyage notifications: {deleted_read[0]} lues, {deleted_unread[0]} non lues, {deleted_batches[0]} lots supprimés")
    
    return {
        'deleted_read': deleted_read[0],
        'deleted_unread': deleted_unread[0],
        'deleted_batches': deleted_batches[0]
    }


@shared_task
def mark_notifications_as_read(user_id, notification_ids=None):
    """Marquer les notifications comme lues"""
    try:
        user = User.objects.get(id=user_id)
        
        queryset = Notification.objects.filter(recipient=user, is_read=False)
        
        if notification_ids:
            queryset = queryset.filter(id__in=notification_ids)
        
        updated = queryset.update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return f"{updated} notifications marquées comme lues pour {user.username}"
        
    except User.DoesNotExist:
        logger.error(f"Utilisateur {user_id} non trouvé")
        return f"Utilisateur {user_id} non trouvé"


@shared_task
def send_bulk_notification(user_ids, notification_type, title, message, extra_data=None):
    """Envoyer une notification en masse à plusieurs utilisateurs"""
    sent_count = 0
    
    for user_id in user_ids:
        try:
            send_notification.delay(
                recipient_id=user_id,
                sender_id=None,
                notification_type=notification_type,
                title=title,
                message=message,
                extra_data=extra_data
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Erreur envoi notification bulk à l'utilisateur {user_id}: {e}")
    
    return f"Notification envoyée à {sent_count} utilisateurs"