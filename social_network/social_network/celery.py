import os
from celery import Celery
from django.conf import settings

# Définir le module de paramètres Django par défaut pour le programme 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_network.settings')

app = Celery('social_network')

# Utiliser une chaîne ici signifie que le worker n'a pas à sérialiser
# l'objet de configuration vers les processus enfants.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Charger les modules de tâches de toutes les applications Django enregistrées.
app.autodiscover_tasks()

# Configuration des tâches
app.conf.update(
    # Timezone
    timezone='Africa/Porto-Novo',
    enable_utc=True,
    
    # Tâches périodiques
    beat_schedule={
        'cleanup-expired-notifications': {
            'task': 'apps.notifications.tasks.cleanup_old_notifications',
            'schedule': 24 * 60 * 60,  # Tous les jours
        },
        'update-trending-hashtags': {
            'task': 'apps.posts.tasks.update_trending_hashtags',
            'schedule': 60 * 60,  # Toutes les heures
        },
        'send-digest-notifications': {
            'task': 'apps.notifications.tasks.send_digest_notifications',
            'schedule': 60 * 60,  # Toutes les heures
        },
        'cleanup-old-post-views': {
            'task': 'apps.interactions.tasks.cleanup_old_views',
            'schedule': 7 * 24 * 60 * 60,  # Toutes les semaines
        }
    },
    
    # Configuration des queues
    task_routes={
        'apps.notifications.tasks.*': {'queue': 'notifications'},
        'apps.media_management.tasks.*': {'queue': 'media'},
        'apps.posts.tasks.*': {'queue': 'posts'},
    },
    
    # Retry configuration
    task_annotations={
        '*': {'rate_limit': '100/m'},
        'apps.notifications.tasks.send_email_notification': {'rate_limit': '50/m'},
        'apps.notifications.tasks.send_push_notification': {'rate_limit': '100/m'},
    },
    
    # Worker configuration
    worker_prefetch_multiplier=4,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    
    # Monitoring
    task_send_sent_event=True,
    worker_send_task_events=True,
    
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Results
    result_expires=60 * 60 * 24,  # 24 heures
    result_persistent=True,
)


@app.task(bind=True)
def debug_task(self):
    """Tâche de debug pour tester Celery"""
    print(f'Request: {self.request!r}')