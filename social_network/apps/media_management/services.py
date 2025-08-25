import os
import mimetypes
import logging
from typing import Optional, List, Dict, Any
from PIL import Image, ImageOps
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.translation import gettext_lazy as _
from .models import MediaFile, MediaThumbnail, MediaProcessingQueue

logger = logging.getLogger(__name__)


class MediaService:
    """Service principal pour la gestion des médias"""
    
    # Configurations par défaut
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
    
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/webm', 'video/quicktime', 'video/avi']
    
    THUMBNAIL_SIZES = {
        'small': (150, 150),
        'medium': (400, 400),
        'large': (800, 800),
    }

    @classmethod
    def upload_media(cls, file, user, usage_type='post', alt_text='') -> MediaFile:
        """
        Upload et traitement initial d'un fichier média
        
        Args:
            file: Fichier uploadé
            user: Utilisateur qui uploade
            usage_type: Type d'usage ('post', 'profile_avatar', etc.)
            alt_text: Texte alternatif pour l'accessibilité
            
        Returns:
            MediaFile: Instance du média créé
            
        Raises:
            ValidationError: Si le fichier n'est pas valide
        """
        from django.core.exceptions import ValidationError
        
        # Déterminer le type de média
        media_type = cls._detect_media_type(file)
        
        # Valider le fichier
        cls._validate_file(file, media_type)
        
        # Créer l'instance MediaFile
        media_file = MediaFile.objects.create(
            uploaded_by=user,
            media_type=media_type,
            usage_type=usage_type,
            file=file,
            alt_text=alt_text,
            original_filename=file.name,
            file_size=file.size,
            mime_type=mimetypes.guess_type(file.name)[0] or '',
        )
        
        # Extraire les métadonnées de base
        cls._extract_basic_metadata(media_file)
        
        # Programmer les tâches de traitement
        cls._queue_processing_tasks(media_file)
        
        logger.info(f"Média uploadé: {media_file.id} par {user.username}")
        
        return media_file

    @classmethod
    def _detect_media_type(cls, file) -> str:
        """Détecte le type de média basé sur le MIME type"""
        mime_type = mimetypes.guess_type(file.name)[0]
        
        if mime_type in cls.ALLOWED_IMAGE_TYPES:
            return 'image'
        elif mime_type in cls.ALLOWED_VIDEO_TYPES:
            return 'video'
        elif mime_type == 'image/gif':
            return 'gif'
        else:
            return 'image'  # Par défaut

    @classmethod
    def _validate_file(cls, file, media_type):
        """Valide un fichier selon son type"""
        from django.core.exceptions import ValidationError
        
        if media_type == 'image' and file.size > cls.MAX_IMAGE_SIZE:
            raise ValidationError(_('La taille de l\'image ne peut pas dépasser 10MB.'))
        
        if media_type == 'video' and file.size > cls.MAX_VIDEO_SIZE:
            raise ValidationError(_('La taille de la vidéo ne peut pas dépasser 100MB.'))
        
        # Validation du MIME type
        mime_type = mimetypes.guess_type(file.name)[0]
        if media_type == 'image' and mime_type not in cls.ALLOWED_IMAGE_TYPES:
            raise ValidationError(_('Format d\'image non supporté.'))
        
        if media_type == 'video' and mime_type not in cls.ALLOWED_VIDEO_TYPES:
            raise ValidationError(_('Format de vidéo non supporté.'))

    @classmethod
    def _extract_basic_metadata(cls, media_file):
        """Extrait les métadonnées de base d'un fichier"""
        try:
            if media_file.media_type == 'image':
                cls._extract_image_metadata(media_file)
        except Exception as e:
            logger.error(f"Erreur optimisation image {media_file.id}: {e}")
            return False


class MediaValidator:
    """Classe pour valider les fichiers médias"""
    
    @staticmethod
    def validate_image_content(file) -> bool:
        """Valide le contenu d'une image"""
        try:
            with Image.open(file) as img:
                # Vérifier que l'image peut être ouverte
                img.verify()
                return True
        except Exception:
            return False
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """Valide l'extension d'un fichier"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in allowed_extensions
    
    @staticmethod
    def validate_dimensions(file, max_width: int = 4096, max_height: int = 4096) -> bool:
        """Valide les dimensions d'une image"""
        try:
            with Image.open(file) as img:
                return img.width <= max_width and img.height <= max_height
        except Exception:
            return False


class MediaProcessor:
    """Processeur pour les tâches de traitement des médias"""
    
    @classmethod
    def process_pending_tasks(cls, limit: int = 10):
        """Traite les tâches en attente"""
        pending_tasks = MediaProcessingQueue.objects.filter(
            status='pending'
        ).order_by('-priority', 'created_at')[:limit]
        
        for task in pending_tasks:
            cls.process_task(task)
    
    @classmethod
    def process_task(cls, task: MediaProcessingQueue):
        """Traite une tâche spécifique"""
        try:
            task.status = 'processing'
            task.started_at = timezone.now()
            task.attempts += 1
            task.save()
            
            success = False
            
            if task.task_type == 'thumbnail_generation':
                success = cls._process_thumbnail_generation(task)
            elif task.task_type == 'image_optimization':
                success = cls._process_image_optimization(task)
            elif task.task_type == 'video_compression':
                success = cls._process_video_compression(task)
            elif task.task_type == 'metadata_extraction':
                success = cls._process_metadata_extraction(task)
            
            if success:
                task.status = 'completed'
                task.completed_at = timezone.now()
                task.progress = 100
            else:
                task.status = 'failed'
                task.error_message = "Échec du traitement"
            
            task.save()
            
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
            logger.error(f"Erreur traitement tâche {task.id}: {e}")
    
    @classmethod
    def _process_thumbnail_generation(cls, task: MediaProcessingQueue) -> bool:
        """Traite la génération de miniatures"""
        try:
            thumbnails = MediaService.generate_thumbnails(task.media_file)
            task.result_data = {'thumbnails_created': len(thumbnails)}
            return len(thumbnails) > 0
        except Exception as e:
            logger.error(f"Erreur génération miniatures: {e}")
            return False
    
    @classmethod
    def _process_image_optimization(cls, task: MediaProcessingQueue) -> bool:
        """Traite l'optimisation d'image"""
        try:
            return MediaService.optimize_image(task.media_file)
        except Exception as e:
            logger.error(f"Erreur optimisation image: {e}")
            return False
    
    @classmethod
    def _process_video_compression(cls, task: MediaProcessingQueue) -> bool:
        """Traite la compression vidéo (placeholder)"""
        # TODO: Implémenter la compression vidéo avec ffmpeg
        logger.info("Compression vidéo non implémentée")
        return True
    
    @classmethod
    def _process_metadata_extraction(cls, task: MediaProcessingQueue) -> bool:
        """Traite l'extraction de métadonnées"""
        try:
            media_file = task.media_file
            
            if media_file.media_type == 'video':
                return cls._extract_video_metadata(media_file)
            
            return True
        except Exception as e:
            logger.error(f"Erreur extraction métadonnées: {e}")
            return False
    
    @classmethod
    def _extract_video_metadata(cls, media_file: MediaFile) -> bool:
        """Extrait les métadonnées d'une vidéo avec ffprobe"""
        try:
            import subprocess
            import json
            
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                media_file.file.path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Extraire les informations du premier stream vidéo
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        media_file.width = stream.get('width', 0)
                        media_file.height = stream.get('height', 0)
                        break
                
                # Durée
                format_data = data.get('format', {})
                duration = float(format_data.get('duration', 0))
                media_file.duration = int(duration) if duration else None
                
                media_file.save(update_fields=['width', 'height', 'duration'])
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur extraction métadonnées vidéo: {e}")
            return False


class MediaCleanupService:
    """Service de nettoyage des médias orphelins"""
    
    @classmethod
    def cleanup_orphaned_media(cls, days_old: int = 7):
        """Supprime les médias non utilisés depuis X jours"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # Trouver les médias orphelins
        orphaned_media = MediaFile.objects.filter(
            created_at__lt=cutoff_date,
            post_relations__isnull=True,  # Pas utilisé dans des posts
            uploaded_by__avatar__isnull=True,  # Pas utilisé comme avatar
            uploaded_by__banner__isnull=True   # Pas utilisé comme bannière
        ).distinct()
        
        deleted_count = 0
        for media in orphaned_media:
            try:
                # Supprimer les fichiers du stockage
                if media.file:
                    default_storage.delete(media.file.name)
                
                for thumbnail in media.thumbnails.all():
                    if thumbnail.thumbnail:
                        default_storage.delete(thumbnail.thumbnail.name)
                
                media.delete()
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Erreur suppression média orphelin {media.id}: {e}")
        
        logger.info(f"Nettoyage terminé: {deleted_count} médias supprimés")
        return deleted_count
    
    @classmethod
    def cleanup_failed_processing_tasks(cls, days_old: int = 3):
        """Supprime les tâches de traitement échouées anciennes"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        deleted_count = MediaProcessingQueue.objects.filter(
            status='failed',
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Tâches échouées supprimées: {deleted_count}")
        return deleted_count


class MediaAnalyticsService:
    """Service pour gérer les analytiques des médias"""
    
    @classmethod
    def track_view(cls, media_file: MediaFile, user=None, ip_address=None):
        """Enregistre une vue sur un média"""
        from .models import MediaAnalytics
        
        try:
            analytics, created = MediaAnalytics.objects.get_or_create(
                media_file=media_file
            )
            
            analytics.total_views += 1
            
            # TODO: Implémenter le tracking des vues uniques
            # (nécessite une table séparée pour les vues par utilisateur/IP)
            
            analytics.save()
            
        except Exception as e:
            logger.error(f"Erreur tracking vue média {media_file.id}: {e}")
    
    @classmethod
    def track_interaction(cls, media_file: MediaFile, interaction_type: str):
        """Enregistre une interaction (like, share, download)"""
        from .models import MediaAnalytics
        
        try:
            analytics, created = MediaAnalytics.objects.get_or_create(
                media_file=media_file
            )
            
            if interaction_type == 'like':
                analytics.total_likes += 1
            elif interaction_type == 'share':
                analytics.total_shares += 1
            elif interaction_type == 'download':
                analytics.total_downloads += 1
            
            analytics.save()
            
        except Exception as e:
            logger.error(f"Erreur tracking interaction {interaction_type} média {media_file.id}: {e}")
    
    @classmethod
    def get_popular_media(cls, limit: int = 10, days: int = 7):
        """Retourne les médias les plus populaires"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import F
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return MediaFile.objects.filter(
            created_at__gte=cutoff_date,
            analytics__isnull=False
        ).annotate(
            popularity_score=F('analytics__total_views') + 
                           F('analytics__total_likes') * 2 + 
                           F('analytics__total_shares') * 3
        ).order_by('-popularity_score')[:limit]("Erreur lors de l'extraction des métadonnées: {e}")

    @classmethod
    def _extract_image_metadata(cls, media_file):
        """Extrait les métadonnées d'une image"""
        try:
            with Image.open(media_file.file.path) as img:
                media_file.width = img.width
                media_file.height = img.height
                
                # Correction de l'orientation EXIF
                img = ImageOps.exif_transpose(img)
                
                media_file.save(update_fields=['width', 'height'])
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des métadonnées image: {e}")

    @classmethod
    def _queue_processing_tasks(cls, media_file):
        """Programme les tâches de traitement en arrière-plan"""
        tasks = []
        
        if media_file.media_type == 'image':
            tasks.append('thumbnail_generation')
            tasks.append('image_optimization')
        elif media_file.media_type == 'video':
            tasks.append('thumbnail_generation')
            tasks.append('video_compression')
            tasks.append('metadata_extraction')
        
        for task_type in tasks:
            MediaProcessingQueue.objects.create(
                media_file=media_file,
                task_type=task_type,
                priority=7 if task_type == 'thumbnail_generation' else 5
            )

    @classmethod
    def generate_thumbnails(cls, media_file: MediaFile) -> List[MediaThumbnail]:
        """Génère les miniatures pour un fichier média"""
        thumbnails = []
        
        if media_file.media_type not in ['image', 'video']:
            return thumbnails
        
        try:
            # Pour les images, utiliser PIL
            if media_file.media_type == 'image':
                thumbnails = cls._generate_image_thumbnails(media_file)
            
            # Pour les vidéos, extraire une frame (nécessite ffmpeg)
            elif media_file.media_type == 'video':
                thumbnails = cls._generate_video_thumbnails(media_file)
                
        except Exception as e:
            logger.error(f"Erreur génération miniatures pour {media_file.id}: {e}")
        
        return thumbnails

    @classmethod
    def _generate_image_thumbnails(cls, media_file: MediaFile) -> List[MediaThumbnail]:
        """Génère des miniatures pour une image"""
        thumbnails = []
        
        try:
            with Image.open(media_file.file.path) as img:
                # Correction orientation EXIF
                img = ImageOps.exif_transpose(img)
                
                for size_name, dimensions in cls.THUMBNAIL_SIZES.items():
                    # Créer la miniature
                    thumb_img = img.copy()
                    thumb_img.thumbnail(dimensions, Image.Resampling.LANCZOS)
                    
                    # Sauvegarder dans un buffer
                    from io import BytesIO
                    buffer = BytesIO()
                    thumb_img.save(buffer, format='JPEG', quality=85)
                    buffer.seek(0)
                    
                    # Créer le nom de fichier
                    filename = f"{media_file.id}_{size_name}.jpg"
                    
                    # Créer la miniature en base
                    thumbnail = MediaThumbnail.objects.create(
                        media_file=media_file,
                        size=size_name,
                        width=thumb_img.width,
                        height=thumb_img.height,
                        file_size=len(buffer.getvalue())
                    )
                    
                    # Sauvegarder le fichier
                    thumbnail.thumbnail.save(
                        filename,
                        ContentFile(buffer.getvalue()),
                        save=True
                    )
                    
                    thumbnails.append(thumbnail)
                    logger.info(f"Miniature {size_name} générée pour {media_file.id}")
        
        except Exception as e:
            logger.error(f"Erreur génération miniatures image {media_file.id}: {e}")
        
        return thumbnails

    @classmethod
    def _generate_video_thumbnails(cls, media_file: MediaFile) -> List[MediaThumbnail]:
        """Génère des miniatures pour une vidéo (nécessite ffmpeg)"""
        thumbnails = []
        
        try:
            import subprocess
            import tempfile
            
            # Créer un fichier temporaire pour l'image extraite
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Commande ffmpeg pour extraire une frame à 1 seconde
            cmd = [
                'ffmpeg',
                '-i', media_file.file.path,
                '-ss', '1',  # À 1 seconde
                '-vframes', '1',  # Une seule frame
                '-y',  # Overwrite
                temp_path
            ]
            
            # Exécuter ffmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(temp_path):
                # Utiliser l'image extraite pour générer les miniatures
                with Image.open(temp_path) as img:
                    for size_name, dimensions in cls.THUMBNAIL_SIZES.items():
                        thumb_img = img.copy()
                        thumb_img.thumbnail(dimensions, Image.Resampling.LANCZOS)
                        
                        from io import BytesIO
                        buffer = BytesIO()
                        thumb_img.save(buffer, format='JPEG', quality=85)
                        buffer.seek(0)
                        
                        filename = f"{media_file.id}_{size_name}.jpg"
                        
                        thumbnail = MediaThumbnail.objects.create(
                            media_file=media_file,
                            size=size_name,
                            width=thumb_img.width,
                            height=thumb_img.height,
                            file_size=len(buffer.getvalue())
                        )
                        
                        thumbnail.thumbnail.save(
                            filename,
                            ContentFile(buffer.getvalue()),
                            save=True
                        )
                        
                        thumbnails.append(thumbnail)
                
                # Nettoyer le fichier temporaire
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Erreur génération miniatures vidéo {media_file.id}: {e}")
        
        return thumbnails

    @classmethod
    def delete_media(cls, media_file: MediaFile, user) -> bool:
        """
        Supprime un fichier média et tous ses assets associés
        
        Args:
            media_file: Fichier à supprimer
            user: Utilisateur demandant la suppression
            
        Returns:
            bool: True si suppression réussie
        """
        # Vérifier les permissions
        if media_file.uploaded_by != user:
            return False
        
        try:
            # Supprimer les miniatures
            for thumbnail in media_file.thumbnails.all():
                if thumbnail.thumbnail:
                    default_storage.delete(thumbnail.thumbnail.name)
            
            # Supprimer le fichier principal
            if media_file.file:
                default_storage.delete(media_file.file.name)
            
            # Supprimer l'enregistrement
            media_file.delete()
            
            logger.info(f"Média {media_file.id} supprimé par {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur suppression média {media_file.id}: {e}")
            return False

    @classmethod
    def get_media_stats(cls, media_file: MediaFile) -> Dict[str, Any]:
        """Retourne les statistiques d'un fichier média"""
        try:
            analytics = media_file.analytics
            return {
                'total_views': analytics.total_views,
                'unique_views': analytics.unique_views,
                'total_likes': analytics.total_likes,
                'total_shares': analytics.total_shares,
                'total_downloads': analytics.total_downloads,
                'average_view_duration': analytics.average_view_duration,
                'bounce_rate': analytics.bounce_rate,
            }
        except:
            return {
                'total_views': 0,
                'unique_views': 0,
                'total_likes': 0,
                'total_shares': 0,
                'total_downloads': 0,
                'average_view_duration': 0.0,
                'bounce_rate': 0.0,
            }

    @classmethod
    def optimize_image(cls, media_file: MediaFile) -> bool:
        """Optimise une image (compression, format, etc.)"""
        if media_file.media_type != 'image':
            return False
        
        try:
            with Image.open(media_file.file.path) as img:
                # Conversion en RGB si nécessaire
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                    img = background
                
                # Correction orientation
                img = ImageOps.exif_transpose(img)
                
                # Sauvegarde optimisée
                img.save(
                    media_file.file.path,
                    format='JPEG',
                    quality=85,
                    optimize=True,
                    progressive=True
                )
                
                # Mettre à jour la taille du fichier
                media_file.file_size = os.path.getsize(media_file.file.path)
                media_file.save(update_fields=['file_size'])
                
                return True
                
        except Exception as e:
            return False