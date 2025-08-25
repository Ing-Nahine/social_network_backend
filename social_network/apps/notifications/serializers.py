from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification, NotificationPreference

User = get_user_model()


class NotificationSenderSerializer(serializers.ModelSerializer):
    """Sérialiseur pour l'expéditeur d'une notification"""
    avatar_url = serializers.CharField(source='get_avatar_url', read_only=True)
    display_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'avatar_url', 'is_verified']


class NotificationSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les notifications"""
    sender = NotificationSenderSerializer(read_only=True)
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', 
        read_only=True
    )
    action_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'sender', 'notification_type', 'notification_type_display',
            'title', 'message', 'action_url', 'is_read', 'read_at',
            'created_at', 'extra_data'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les préférences de notifications"""
    
    class Meta:
        model = NotificationPreference
        exclude = ['id', 'user', 'created_at', 'updated_at']
    
    def validate_digest_frequency(self, value):
        """Valider la fréquence du digest"""
        valid_choices = ['never', 'daily', 'weekly', 'monthly']
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"Choix invalide. Options valides: {', '.join(valid_choices)}"
            )
        return value