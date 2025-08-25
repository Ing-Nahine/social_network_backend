from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
import json
import os
from PIL import Image

from .models import PostMedia, Post


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def upload_media(request):
    """Upload de médias via AJAX"""
    if 'file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'message': 'Aucun fichier fourni'
        })
    
    file = request.FILES['file']
    post_id = request.POST.get('post_id')
    
    # Validation du type de fichier
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'video/mp4', 'video/webm']
    if file.content_type not in allowed_types:
        return JsonResponse({
            'success': False,
            'message': 'Type de fichier non autorisé'
        })
    
    # Validation de la taille (10MB max)
    if file.size > 10 * 1024 * 1024:
        return JsonResponse({
            'success': False,
            'message': 'Fichier trop volumineux (10MB max)'
        })
    
    try:
        media_type = 'image' if file.content_type.startswith('image/') else 'video'
        
        # Créer l'objet média
        media = PostMedia.objects.create(
            post_id=post_id if post_id else None,
            media_type=media_type,
            image=file if media_type == 'image' else None,
            video=file if media_type == 'video' else None,
            file_size=file.size
        )
        
        # Extraire les dimensions pour les images
        if media_type == 'image' and media.image:
            try:
                with Image.open(media.image.path) as img:
                    media.width, media.height = img.size
                    media.save()
            except Exception:
                pass
        
        return JsonResponse({
            'success': True,
            'media': {
                'id': media.id,
                'url': media.file_url,
                'type': media.media_type,
                'width': media.width,
                'height': media.height
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erreur lors de l\'upload: {str(e)}'
        })


@login_required
@require_http_methods(["DELETE"])
def delete_media(request, media_id):
    """Supprimer un média"""
    media = get_object_or_404(PostMedia, id=media_id)
    
    # Vérifier que l'utilisateur peut supprimer ce média
    if media.post and media.post.author != request.user:
        return JsonResponse({
            'success': False,
            'message': 'Non autorisé'
        }, status=403)
    
    # Supprimer le fichier physique
    if media.image:
        if default_storage.exists(media.image.name):
            default_storage.delete(media.image.name)
    elif media.video:
        if default_storage.exists(media.video.name):
            default_storage.delete(media.video.name)
    
    media.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Média supprimé'
    })


def get_media(request, media_id):
    """Récupérer les infos d'un média"""
    media = get_object_or_404(PostMedia, id=media_id)
    
    return JsonResponse({
        'id': media.id,
        'type': media.media_type,
        'url': media.file_url,
        'alt_text': media.alt_text,
        'width': media.width,
        'height': media.height,
        'file_size': media.file_size,
        'duration': media.duration,
        'created_at': media.created_at.isoformat()
    })


@login_required
@require_http_methods(["PATCH"])
def update_media_alt_text(request, media_id):
    """Mettre à jour le texte alternatif d'un média"""
    media = get_object_or_404(PostMedia, id=media_id)
    
    # Vérifier les permissions
    if media.post and media.post.author != request.user:
        return JsonResponse({
            'success': False,
            'message': 'Non autorisé'
        }, status=403)
    
    data = json.loads(request.body)
    alt_text = data.get('alt_text', '').strip()
    
    media.alt_text = alt_text[:200]  # Limiter à 200 caractères
    media.save()
    
    return JsonResponse({
        'success': True,
        'alt_text': media.alt_text
    })


def serve_media(request, media_id):
    """Servir un fichier média (pour développement uniquement)"""
    if not settings.DEBUG:
        return HttpResponse(status=404)
    
    media = get_object_or_404(PostMedia, id=media_id)
    
    file_path = None
    if media.image:
        file_path = media.image.path
    elif media.video:
        file_path = media.video.path
    
    if file_path and os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read())
            response['Content-Type'] = f'image/jpeg' if media.media_type == 'image' else 'video/mp4'
            return response
    
    return HttpResponse(status=404)


def get_post_media(request, post_id):
    """Récupérer tous les médias d'un post"""
    post = get_object_or_404(Post, id=post_id)
    media_list = PostMedia.objects.filter(post=post).order_by('order')
    
    media_data = []
    for media in media_list:
        media_data.append({
            'id': media.id,
            'type': media.media_type,
            'url': media.file_url,
            'alt_text': media.alt_text,
            'width': media.width,
            'height': media.height,
            'order': media.order
        })
    
    return JsonResponse({'media': media_data})