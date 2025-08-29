from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.http import JsonResponse
import logging
from apps.posts.models import PostMedia
from .models import MediaFile, MediaThumbnail, MediaAnalytics
from .serializers import (
    MediaFileSerializer, 
    MediaFileDetailSerializer,
    PostMediaSerializer,
    MediaAnalyticsSerializer
)
import traceback

from django.shortcuts import get_object_or_404
from apps.posts.models import Post, PostMedia
from .services import MediaService, MediaAnalyticsService

logger = logging.getLogger(__name__)


class MediaFileViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des fichiers médias"""
    
    queryset = MediaFile.objects.all()
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MediaFileDetailSerializer
        return MediaFileSerializer
    
    def get_queryset(self):
        """Filtre les médias selon l'utilisateur"""
        # Évite les erreurs lors de la génération Swagger/OpenAPI
        if getattr(self, 'swagger_fake_view', False):
            return MediaFile.objects.none()
        
        # Admin voit tout, utilisateur normal ne voit que ses fichiers
        if self.request.user.is_staff:
            return MediaFile.objects.all()
        return MediaFile.objects.filter(uploaded_by=self.request.user)

    def perform_create(self, serializer):
        """Upload d'un nouveau média"""
        try:
            file = self.request.FILES.get('file')
            usage_type = self.request.data.get('usage_type', 'post')
            alt_text = self.request.data.get('alt_text', '')
            
            if not file:
                raise ValidationError(_('Aucun fichier fourni'))
            
            # Utiliser le service pour créer le média
            media_file = MediaService.upload_media(
                file=file,
                user=self.request.user,
                usage_type=usage_type,
                alt_text=alt_text
            )
            
            serializer.instance = media_file
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Erreur upload média: {e}")
            return Response(
                {'error': _('Erreur lors de l\'upload du fichier')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        """Suppression d'un média"""
        media_file = self.get_object()
        
        # Vérifier les permissions
        if media_file.uploaded_by != request.user and not request.user.is_staff:
            return Response(
                {'error': _('Permission refusée')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Vérifier si le média est utilisé
        if self._is_media_in_use(media_file):
            return Response(
                {'error': _('Ce média est utilisé et ne peut pas être supprimé')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Supprimer avec le service
        success = MediaService.delete_media(media_file, request.user)
        
        if success:
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(
                {'error': _('Erreur lors de la suppression')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _is_media_in_use(self, media_file):
        """Vérifie si un média est utilisé"""
        return (
            media_file.post_relations.exists() or
            hasattr(media_file.uploaded_by, 'avatar') and media_file.uploaded_by.avatar == media_file.file or
            hasattr(media_file.uploaded_by, 'banner') and media_file.uploaded_by.banner == media_file.file
        )
    
    @action(detail=True, methods=['get'])
    def thumbnails(self, request, pk=None):
        """Récupère les miniatures d'un média"""
        media_file = self.get_object()
        thumbnails = media_file.thumbnails.all()
        
        thumbnail_data = []
        for thumb in thumbnails:
            thumbnail_data.append({
                'size': thumb.size,
                'url': thumb.file_url,
                'width': thumb.width,
                'height': thumb.height,
                'file_size': thumb.file_size
            })
        
        return Response(thumbnail_data)
    
    @action(detail=True, methods=['post'])
    def regenerate_thumbnails(self, request, pk=None):
        """Régénère les miniatures d'un média"""
        media_file = self.get_object()
        
        # Vérifier les permissions
        if media_file.uploaded_by != request.user and not request.user.is_staff:
            return Response(
                {'error': _('Permission refusée')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Supprimer les anciennes miniatures
            for thumbnail in media_file.thumbnails.all():
                thumbnail.delete()
            
            # Générer de nouvelles miniatures
            thumbnails = MediaService.generate_thumbnails(media_file)
            
            return Response({
                'message': _('Miniatures régénérées avec succès'),
                'thumbnails_count': len(thumbnails)
            })
            
        except Exception as e:
            logger.error(f"Erreur régénération miniatures: {e}")
            return Response(
                {'error': _('Erreur lors de la régénération')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Récupère les analytics d'un média"""
        media_file = self.get_object()
        
        # Vérifier les permissions
        if media_file.uploaded_by != request.user and not request.user.is_staff:
            return Response(
                {'error': _('Permission refusée')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        stats = MediaService.get_media_stats(media_file)
        return Response(stats)
    
    @action(detail=True, methods=['post'])
    def track_view(self, request, pk=None):
        """Enregistre une vue sur un média"""
        media_file = self.get_object()
        
        # Tracker la vue
        MediaAnalyticsService.track_view(
            media_file=media_file,
            user=request.user if request.user.is_authenticated else None,
            ip_address=self._get_client_ip(request)
        )
        
        return Response({'message': _('Vue enregistrée')})
    
    def _get_client_ip(self, request):
        """Récupère l'IP du client"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        else:
            return request.META.get('REMOTE_ADDR')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_upload_media(request):
    """Upload multiple de médias"""
    
    files = request.FILES.getlist('files')
    usage_type = request.data.get('usage_type', 'post')
    
    if not files:
        return Response(
            {'error': _('Aucun fichier fourni')},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(files) > 10:  # Limite à 10 fichiers
        return Response(
            {'error': _('Maximum 10 fichiers autorisés')},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    results = []
    errors = []
    
    with transaction.atomic():
        for i, file in enumerate(files):
            try:
                media_file = MediaService.upload_media(
                    file=file,
                    user=request.user,
                    usage_type=usage_type
                )
                
                serializer = MediaFileSerializer(media_file, context={'request': request})
                results.append(serializer.data)
                
            except ValidationError as e:
                errors.append({
                    'file_index': i,
                    'filename': file.name,
                    'error': str(e)
                })
            except Exception as e:
                logger.error(f"Erreur upload fichier {file.name}: {e}")
                errors.append({
                    'file_index': i,
                    'filename': file.name,
                    'error': _('Erreur lors de l\'upload')
                })
    
    response_data = {
        'uploaded': results,
        'errors': errors,
        'summary': {
            'total_files': len(files),
            'successful_uploads': len(results),
            'failed_uploads': len(errors)
        }
    }
    
    status_code = status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST
    return Response(response_data, status=status_code)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_media_library(request):
    """Récupère la bibliothèque média de l'utilisateur"""
    
    media_type = request.GET.get('type')  # image, video, gif
    usage_type = request.GET.get('usage')  # post, profile_avatar, profile_banner
    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 20)), 50)  # Max 50 par page
    
    queryset = MediaFile.objects.filter(
        uploaded_by=request.user,
        is_approved=True
    ).order_by('-created_at')
    
    # Filtres
    if media_type:
        queryset = queryset.filter(media_type=media_type)
    
    if usage_type:
        queryset = queryset.filter(usage_type=usage_type)
    
    # Pagination
    offset = (page - 1) * per_page
    media_files = queryset[offset:offset + per_page]
    
    serializer = MediaFileSerializer(
        media_files, 
        many=True, 
        context={'request': request}
    )
    
    return Response({
        'media': serializer.data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': queryset.count(),
            'has_next': queryset.count() > offset + per_page
        }
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def popular_media(request):
    """Récupère les médias populaires"""
    
    days = int(request.GET.get('days', 7))
    limit = min(int(request.GET.get('limit', 10)), 50)
    
    from .services import MediaAnalyticsService
    popular = MediaAnalyticsService.get_popular_media(limit=limit, days=days)
    
    serializer = MediaFileSerializer(
        popular, 
        many=True, 
        context={'request': request}
    )
    
    return Response({
        'media': serializer.data,
        'period_days': days
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def attach_media_to_post(request):
    """Attache des médias à un post"""
    post_id = request.data.get('post_id')
    media_ids = request.data.get('media_ids', [])
    
    if not post_id:
        return Response({'error': 'ID du post requis'}, status=400)
    
    if not media_ids or len(media_ids) > 4:
        return Response({'error': '1 à 4 médias requis'}, status=400)
    
    try:
        # Vérifier que le post existe
        post = get_object_or_404(Post, id=post_id, author=request.user)
        
        # Vérifier que les médias existent
        media_files = MediaFile.objects.filter(
            id__in=media_ids,
            uploaded_by=request.user
        )
        
        if len(media_files) != len(media_ids):
            return Response({'error': 'Médias introuvables'}, status=404)
        
        # Supprimer anciennes associations
        PostMedia.objects.filter(post=post).delete()
        
        # Créer nouvelles associations
        for order, media_file in enumerate(media_files):
            # Déterminer le type de média basé sur mime_type
            if media_file.mime_type.startswith('image/'):
                media_type = 'gif' if 'gif' in media_file.mime_type else 'image'
                PostMedia.objects.create(
                    post=post,
                    media_type=media_type,
                    image=media_file.file,
                    alt_text=getattr(media_file, 'alt_text', ''),
                    width=getattr(media_file, 'width', None),
                    height=getattr(media_file, 'height', None),
                    file_size=getattr(media_file, 'file_size', None),
                    order=order
                )
            elif media_file.mime_type.startswith('video/'):
                PostMedia.objects.create(
                    post=post,
                    media_type='video',
                    video=media_file.file,
                    width=getattr(media_file, 'width', None),
                    height=getattr(media_file, 'height', None),
                    file_size=getattr(media_file, 'file_size', None),
                    duration=getattr(media_file, 'duration', None),
                    order=order
                )
        
        return Response({'message': 'Médias attachés avec succès'}, status=200)
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"ERREUR COMPLÈTE: {error_details}")
        return Response({'error': 'Erreur serveur'}, status=500)
    
@api_view(['GET'])
def media_proxy(request, media_id):
    """Proxy pour servir les médias avec analytics"""
    
    try:
        media_file = get_object_or_404(MediaFile, id=media_id, is_approved=True)
        
        # Tracker la vue si l'utilisateur est authentifié
        if request.user.is_authenticated:
            MediaAnalyticsService.track_view(
                media_file=media_file,
                user=request.user
            )
        
        # Rediriger vers l'URL réelle du fichier
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(media_file.file_url)
        
    except Exception as e:
        logger.error(f"Erreur proxy média {media_id}: {e}")
        return JsonResponse(
            {'error': _('Média introuvable')},
            status=404
        )


class MediaAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les analytics des médias (admin seulement)"""
    
    queryset = MediaAnalytics.objects.all()
    serializer_class = MediaAnalyticsSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = 'media_file_id'
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Vue d'ensemble des analytics"""
        from django.db.models import Sum, Avg
        
        stats = MediaAnalytics.objects.aggregate(
            total_views=Sum('total_views'),
            total_likes=Sum('total_likes'),
            total_shares=Sum('total_shares'),
            total_downloads=Sum('total_downloads'),
            avg_view_duration=Avg('average_view_duration'),
            avg_bounce_rate=Avg('bounce_rate')
        )
        
        return Response({
            'overview': stats,
            'total_media_files': MediaFile.objects.count(),
            'approved_media_files': MediaFile.objects.filter(is_approved=True).count(),
        })