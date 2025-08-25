from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Like, Comment, CommentLike, Bookmark, Share
from .serializers import CommentSerializer, CommentCreateSerializer
from apps.posts.models import Post


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_like(request, post_id):
    """
    Toggle like sur un post
    POST /api/interactions/like/{post_id}/
    """
    post = get_object_or_404(Post, id=post_id)
    
    try:
        # Si le like existe, le supprimer
        like = Like.objects.get(user=request.user, post=post)
        like.delete()
        liked = False
        message = "Like supprimé"
    except Like.DoesNotExist:
        # Sinon, créer le like
        Like.objects.create(user=request.user, post=post)
        liked = True
        message = "Post liké"
    
    # Rafraîchir le post pour obtenir le nouveau compteur
    post.refresh_from_db()
    
    return Response({
        'success': True,
        'liked': liked,
        'likes_count': post.likes_count,
        'message': message
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_bookmark(request, post_id):
    """
    Toggle bookmark sur un post
    POST /api/interactions/bookmark/{post_id}/
    """
    post = get_object_or_404(Post, id=post_id)
    
    try:
        bookmark = Bookmark.objects.get(user=request.user, post=post)
        bookmark.delete()
        bookmarked = False
        message = "Signet supprimé"
    except Bookmark.DoesNotExist:
        Bookmark.objects.create(user=request.user, post=post)
        bookmarked = True
        message = "Post mis en signet"
    
    return Response({
        'success': True,
        'bookmarked': bookmarked,
        'message': message
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_comment(request, post_id):
    """
    Créer un commentaire sur un post
    POST /api/interactions/comment/{post_id}/
    Body: {"content": "text", "parent_comment_id": 123}
    """
    post = get_object_or_404(Post, id=post_id)
    
    serializer = CommentCreateSerializer(data=request.data)
    if serializer.is_valid():
        comment = serializer.save(
            author=request.user,
            post=post
        )
        
        return Response(
            CommentSerializer(comment, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_comment(request, comment_id):
    """
    Supprimer un commentaire
    DELETE /api/interactions/comment/{comment_id}/
    """
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    comment.delete()
    
    return Response({'message': 'Commentaire supprimé'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_comment_like(request, comment_id):
    """
    Toggle like sur un commentaire
    POST /api/interactions/comment-like/{comment_id}/
    """
    comment = get_object_or_404(Comment, id=comment_id)
    
    try:
        like = CommentLike.objects.get(user=request.user, comment=comment)
        like.delete()
        liked = False
        message = "Like supprimé"
    except CommentLike.DoesNotExist:
        CommentLike.objects.create(user=request.user, comment=comment)
        liked = True
        message = "Commentaire liké"
    
    comment.refresh_from_db()
    
    return Response({
        'success': True,
        'liked': liked,
        'likes_count': comment.likes_count,
        'message': message
    })


@api_view(['GET'])
def get_post_comments(request, post_id):
    """
    Récupérer les commentaires d'un post
    GET /api/interactions/comments/{post_id}/
    """
    post = get_object_or_404(Post, id=post_id)
    
    # Commentaires principaux uniquement (pas les réponses)
    comments = Comment.objects.filter(
        post=post,
        parent_comment=None
    ).select_related('author').prefetch_related('replies__author')[:20]
    
    serializer = CommentSerializer(
        comments, 
        many=True, 
        context={'request': request}
    )
    
    return Response({
        'comments': serializer.data,
        'total_comments': post.replies_count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_bookmarks(request):
    """
    Signets de l'utilisateur connecté
    GET /api/interactions/my-bookmarks/
    """
    bookmarks = Bookmark.objects.filter(
        user=request.user
    ).select_related('post__author').prefetch_related('post__media')
    
    # Sérialiser les posts des signets
    from apps.posts.serializers import PostSerializer
    posts = [bookmark.post for bookmark in bookmarks]
    serializer = PostSerializer(posts, many=True, context={'request': request})
    
    return Response({'bookmarks': serializer.data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_likes(request):
    """
    Posts likés par l'utilisateur connecté
    GET /api/interactions/my-likes/
    """
    likes = Like.objects.filter(
        user=request.user
    ).select_related('post__author').prefetch_related('post__media')
    
    # Sérialiser les posts likés
    from apps.posts.serializers import PostSerializer
    posts = [like.post for like in likes]
    serializer = PostSerializer(posts, many=True, context={'request': request})
    
    return Response({'liked_posts': serializer.data})


@api_view(['GET'])
def get_post_interactions(request, post_id):
    """
    Récupérer toutes les interactions d'un post
    GET /api/interactions/post/{post_id}/
    """
    post = get_object_or_404(Post, id=post_id)
    
    interactions = {
        'is_liked': False,
        'is_bookmarked': False,
        'is_retweeted': False,
        'likes_count': post.likes_count,
        'retweets_count': post.retweets_count,
        'replies_count': post.replies_count,
        'views_count': post.views_count
    }
    
    # Si utilisateur connecté, vérifier ses interactions
    if request.user.is_authenticated:
        interactions['is_liked'] = Like.objects.filter(
            user=request.user, post=post
        ).exists()
        interactions['is_bookmarked'] = Bookmark.objects.filter(
            user=request.user, post=post
        ).exists()
        interactions['is_retweeted'] = Share.objects.filter(
            user=request.user, original_post=post
        ).exists()
    
    return Response(interactions)