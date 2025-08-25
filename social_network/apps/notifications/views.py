from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404

from .models import Notification, NotificationPreference, PushSubscription
from .serializers import NotificationSerializer, NotificationPreferenceSerializer


class NotificationPagination(PageNumberPagination):
    """Pagination pour les notifications"""
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    """
    Liste des notifications de l'utilisateur
    GET /api/notifications/
    Query params: ?type=like&unread=true
    """
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender')
    
    # Filtres
    notification_type = request.GET.get('type')
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    if request.GET.get('unread') == 'true':
        notifications = notifications.filter(is_read=False)
    
    # Pagination
    paginator = NotificationPagination()
    page = paginator.paginate_queryset(notifications, request)
    
    serializer = NotificationSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """
    Marquer une notification comme lue
    POST /api/notifications/{id}/read/
    """
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user
    )
    
    notification.mark_as_read()
    
    return Response({
        'success': True,
        'message': 'Notification marquée comme lue'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """
    Marquer toutes les notifications comme lues
    POST /api/notifications/mark-all-read/
    """
    from django.utils import timezone
    
    updated = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(
        is_read=True,
        read_at=timezone.now()
    )
    
    return Response({
        'success': True,
        'message': f'{updated} notifications marquées comme lues'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_count(request):
    """
    Compteur de notifications non lues
    GET /api/notifications/count/
    """
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    return Response({'unread_count': count})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def notification_preferences(request):
    """
    Gérer les préférences de notifications
    GET /api/notifications/preferences/
    PUT /api/notifications/preferences/
    """
    preferences, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'GET':
        serializer = NotificationPreferenceSerializer(preferences)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = NotificationPreferenceSerializer(
            preferences, 
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_push_subscription(request):
    """
    Enregistrer un abonnement push
    POST /api/notifications/push/register/
    Body: {
        "endpoint": "...",
        "keys": {"p256dh": "...", "auth": "..."}
    }
    """
    try:
        data = request.data
        
        subscription, created = PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=data['endpoint'],
            defaults={
                'p256dh_key': data['keys']['p256dh'],
                'auth_key': data['keys']['auth'],
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'is_active': True
            }
        )
        
        return Response({
            'success': True,
            'message': 'Abonnement push enregistré' if created else 'Abonnement push mis à jour'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unregister_push_subscription(request):
    """
    Désinscrire un abonnement push
    POST /api/notifications/push/unregister/
    Body: {"endpoint": "..."}
    """
    try:
        endpoint = request.data.get('endpoint')
        
        deleted_count, _ = PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint
        ).delete()
        
        if deleted_count > 0:
            return Response({
                'success': True,
                'message': 'Abonnement push supprimé'
            })
        else:
            return Response({
                'success': False,
                'message': 'Abonnement introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_vapid_public_key(request):
    """
    Récupérer la clé publique VAPID
    GET /api/notifications/vapid-key/
    """
    from django.conf import settings
    
    if hasattr(settings, 'WEBPUSH_SETTINGS'):
        return Response({
            'vapid_public_key': settings.WEBPUSH_SETTINGS.get('VAPID_PUBLIC_KEY', '')
        })
    
    return Response({
        'vapid_public_key': ''
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_push_notification(request):
    """
    Envoyer une notification push de test
    POST /api/notifications/push/test/
    """
    try:
        from .push_utils import create_notification
        
        create_notification(
            recipient=request.user,
            sender=None,
            notification_type='system',
            title='Test de notification',
            message='Ceci est une notification push de test',
            extra_data={'is_test': True}
        )
        
        return Response({
            'success': True,
            'message': 'Notification de test envoyée'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)