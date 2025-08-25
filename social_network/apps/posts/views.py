from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Post, PostMedia, Hashtag, Mention
from .serializers import PostSerializer, PostCreateSerializer


class PostPagination(PageNumberPagination):
    """Pagination personnalisée pour les posts"""
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def feed(request):
    """
    Feed principal - Posts des utilisateurs suivis + posts populaires
    GET /api/posts/
    """
    if request.user.is_authenticated:
        # Posts des utilisateurs suivis + posts de l'utilisateur
        following_ids = request.user.following.values_list('followed_id', flat=True)
        posts = Post.objects.filter(
            Q(author__in=following_ids) | Q(author=request.user)
        ).select_related('author').prefetch_related('media')
    else:
        # Posts publics pour les non-connectés
        posts = Post.objects.filter(
            author__is_private=False
        ).select_related('author').prefetch_related('media')
    
    # Pagination
    paginator = PostPagination()
    page = paginator.paginate_queryset(posts, request)
    
    serializer = PostSerializer(page, many=True, context={'request': request})
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_post(request):
    """
    Créer un nouveau post
    POST /api/posts/create/
    Body: {"content": "text", "media_files": [files]}
    """
    serializer = PostCreateSerializer(data=request.data)
    if serializer.is_valid():
        # Créer le post
        post = serializer.save(author=request.user)
        
        # Traiter les médias si présents
        media_files = request.FILES.getlist('media_files')
        for i, file in enumerate(media_files[:4]):  # Max 4 médias
            media_type = 'image' if file.content_type.startswith('image/') else 'video'
            PostMedia.objects.create(
                post=post,
                media_type=media_type,
                image=file if media_type == 'image' else None,
                video=file if media_type == 'video' else None,
                order=i
            )
        
        return Response(
            PostSerializer(post, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def post_detail(request, post_id):
    """
    Détail d'un post avec ses réponses
    GET /api/posts/{id}/
    """
    post = get_object_or_404(Post, id=post_id)
    
    # Incrémenter le compteur de vues
    if request.user.is_authenticated:
        from apps.interactions.models import PostView
        PostView.objects.get_or_create(
            user=request.user,
            post=post,
            defaults={'ip_address': request.META.get('REMOTE_ADDR')}
        )
    
    # Récupérer les réponses
    replies = Post.objects.filter(parent_post=post)[:20]
    
    return Response({
        'post': PostSerializer(post, context={'request': request}).data,
        'replies': PostSerializer(replies, many=True, context={'request': request}).data
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_post(request, post_id):
    """
    Supprimer un post (uniquement par l'auteur)
    DELETE /api/posts/{id}/
    """
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post.delete()
    
    return Response({'message': 'Post supprimé'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_reply(request, post_id):
    """
    Créer une réponse à un post
    POST /api/posts/{id}/reply/
    Body: {"content": "text"}
    """
    parent_post = get_object_or_404(Post, id=post_id)
    content = request.data.get('content', '').strip()
    
    if not content:
        return Response(
            {'error': 'Le contenu est requis'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    reply = Post.objects.create(
        author=request.user,
        content=content,
        post_type='reply',
        parent_post=parent_post
    )
    
    return Response(
        PostSerializer(reply, context={'request': request}).data,
        status=status.HTTP_201_CREATED
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_retweet(request, post_id):
    """
    Créer un retweet ou quote tweet
    POST /api/posts/{id}/retweet/
    Body: {"quote_content": "text"} (optionnel pour quote tweet)
    """
    original_post = get_object_or_404(Post, id=post_id)
    quote_content = request.data.get('quote_content', '').strip()
    
    # Vérifier si déjà retweeté
    from apps.interactions.models import Share
    if Share.objects.filter(user=request.user, original_post=original_post).exists():
        return Response(
            {'error': 'Post déjà retweeté'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if quote_content:
        # Quote tweet
        retweet_post = Post.objects.create(
            author=request.user,
            content=quote_content,
            post_type='quote',
            original_post=original_post
        )
        share_type = 'quote'
    else:
        # Retweet simple
        retweet_post = Post.objects.create(
            author=request.user,
            content=original_post.content,
            post_type='retweet',
            original_post=original_post
        )
        share_type = 'retweet'
    
    # Créer la relation de partage
    Share.objects.create(
        user=request.user,
        original_post=original_post,
        shared_post=retweet_post,
        share_type=share_type,
        quote_content=quote_content
    )
    
    return Response(
        PostSerializer(retweet_post, context={'request': request}).data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET'])
def hashtag_posts(request, hashtag_name):
    """
    Posts contenant un hashtag
    GET /api/posts/hashtag/{name}/
    """
    hashtag = get_object_or_404(Hashtag, name=hashtag_name)
    posts = Post.objects.filter(hashtag_relations__hashtag=hashtag)
    
    paginator = PostPagination()
    page = paginator.paginate_queryset(posts, request)
    
    serializer = PostSerializer(page, many=True, context={'request': request})
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
def trending_hashtags(request):
    """
    Hashtags tendance
    GET /api/posts/trending/
    """
    hashtags = Hashtag.objects.order_by('-trending_score', '-posts_count')[:20]
    
    data = [{
        'name': h.name,
        'posts_count': h.posts_count,
        'trending_score': h.trending_score
    } for h in hashtags]
    
    return Response({'hashtags': data})


@api_view(['GET'])
def user_posts(request, username):
    """
    Posts d'un utilisateur
    GET /api/posts/user/{username}/
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    user = get_object_or_404(User, username=username)
    posts = Post.objects.filter(author=user)
    
    paginator = PostPagination()
    page = paginator.paginate_queryset(posts, request)
    
    serializer = PostSerializer(page, many=True, context={'request': request})
    return paginator.get_paginated_response(serializer.data)