from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from apps.posts.models import Post

User = get_user_model()


class Like(models.Model):
    """Modèle pour les likes sur les posts"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('Utilisateur')
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('Post')
    )
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'post_likes'
        verbose_name = _('Like')
        verbose_name_plural = _('Likes')
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['post', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} aime le post {self.post.id}"

    def save(self, *args, **kwargs):
        """Mise à jour du compteur de likes lors de la sauvegarde"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            Post.objects.filter(id=self.post.id).update(
                likes_count=models.F('likes_count') + 1
            )

    def delete(self, *args, **kwargs):
        """Mise à jour du compteur de likes lors de la suppression"""
        post_id = self.post.id
        super().delete(*args, **kwargs)
        
        Post.objects.filter(id=post_id).update(
            likes_count=models.F('likes_count') - 1
        )


class Comment(models.Model):
    """Modèle pour les commentaires sur les posts"""
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Auteur')
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Post')
    )
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name=_('Commentaire parent')
    )
    
    content = models.TextField(_('Contenu'), max_length=280)
    likes_count = models.PositiveIntegerField(_('Nombre de likes'), default=0)
    replies_count = models.PositiveIntegerField(_('Nombre de réponses'), default=0)
    
    is_edited = models.BooleanField(_('Modifié'), default=False)
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Modifié le'), auto_now=True)

    class Meta:
        db_table = 'post_comments'
        verbose_name = _('Commentaire')
        verbose_name_plural = _('Commentaires')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', '-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['parent_comment', '-created_at']),
        ]

    def __str__(self):
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Commentaire de {self.author.username}: {content_preview}"

    def save(self, *args, **kwargs):
        """Mise à jour des compteurs lors de la sauvegarde"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Incrémenter le compteur de commentaires du post
            Post.objects.filter(id=self.post.id).update(
                replies_count=models.F('replies_count') + 1
            )
            
            # Si c'est une réponse à un commentaire, incrémenter son compteur
            if self.parent_comment:
                Comment.objects.filter(id=self.parent_comment.id).update(
                    replies_count=models.F('replies_count') + 1
                )

    def delete(self, *args, **kwargs):
        """Mise à jour des compteurs lors de la suppression"""
        post_id = self.post.id
        parent_comment_id = self.parent_comment.id if self.parent_comment else None
        
        super().delete(*args, **kwargs)
        
        # Décrémenter le compteur de commentaires du post
        Post.objects.filter(id=post_id).update(
            replies_count=models.F('replies_count') - 1
        )
        
        # Si c'était une réponse à un commentaire, décrémenter son compteur
        if parent_comment_id:
            Comment.objects.filter(id=parent_comment_id).update(
                replies_count=models.F('replies_count') - 1
            )

    @property
    def is_reply(self):
        """Vérifie si c'est une réponse à un autre commentaire"""
        return self.parent_comment is not None


class CommentLike(models.Model):
    """Modèle pour les likes sur les commentaires"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comment_likes',
        verbose_name=_('Utilisateur')
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name=_('Commentaire')
    )
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'comment_likes'
        verbose_name = _('Like de commentaire')
        verbose_name_plural = _('Likes de commentaires')
        unique_together = ('user', 'comment')
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['comment', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} aime le commentaire {self.comment.id}"

    def save(self, *args, **kwargs):
        """Mise à jour du compteur de likes lors de la sauvegarde"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            Comment.objects.filter(id=self.comment.id).update(
                likes_count=models.F('likes_count') + 1
            )

    def delete(self, *args, **kwargs):
        """Mise à jour du compteur de likes lors de la suppression"""
        comment_id = self.comment.id
        super().delete(*args, **kwargs)
        
        Comment.objects.filter(id=comment_id).update(
            likes_count=models.F('likes_count') - 1
        )


class Bookmark(models.Model):
    """Modèle pour les signets/favoris"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookmarks',
        verbose_name=_('Utilisateur')
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='bookmarks',
        verbose_name=_('Post')
    )
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'post_bookmarks'
        verbose_name = _('Signet')
        verbose_name_plural = _('Signets')
        unique_together = ('user', 'post')
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['post', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} a mis en signet le post {self.post.id}"


class Share(models.Model):
    """Modèle pour le partage de posts (retweets)"""
    
    SHARE_TYPES = [
        ('retweet', _('Retweet simple')),
        ('quote', _('Quote tweet')),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shares',
        verbose_name=_('Utilisateur')
    )
    original_post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='shares',
        verbose_name=_('Post original')
    )
    shared_post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='share_of',
        verbose_name=_('Post de partage')
    )
    
    share_type = models.CharField(_('Type de partage'), max_length=10, choices=SHARE_TYPES)
    quote_content = models.TextField(_('Contenu du quote'), max_length=280, blank=True)
    
    created_at = models.DateTimeField(_('Créé le'), auto_now_add=True)

    class Meta:
        db_table = 'post_shares'
        verbose_name = _('Partage')
        verbose_name_plural = _('Partages')
        unique_together = ('user', 'original_post')
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['original_post', '-created_at']),
            models.Index(fields=['share_type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} a partagé le post {self.original_post.id}"

    def save(self, *args, **kwargs):
        """Mise à jour du compteur de retweets lors de la sauvegarde"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            Post.objects.filter(id=self.original_post.id).update(
                retweets_count=models.F('retweets_count') + 1
            )

    def delete(self, *args, **kwargs):
        """Mise à jour du compteur de retweets lors de la suppression"""
        original_post_id = self.original_post.id
        super().delete(*args, **kwargs)
        
        Post.objects.filter(id=original_post_id).update(
            retweets_count=models.F('retweets_count') - 1
        )


class PostView(models.Model):
    """Modèle pour tracker les vues des posts"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='post_views',
        verbose_name=_('Utilisateur')
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='views',
        verbose_name=_('Post')
    )
    ip_address = models.GenericIPAddressField(_('Adresse IP'), null=True, blank=True)
    user_agent = models.TextField(_('User Agent'), blank=True)
    viewed_at = models.DateTimeField(_('Vu le'), auto_now_add=True)

    class Meta:
        db_table = 'post_views'
        verbose_name = _('Vue de post')
        verbose_name_plural = _('Vues de posts')
        indexes = [
            models.Index(fields=['post', '-viewed_at']),
            models.Index(fields=['user', '-viewed_at']),
            models.Index(fields=['ip_address', '-viewed_at']),
        ]

    def __str__(self):
        user_info = self.user.username if self.user else self.ip_address
        return f"Vue du post {self.post.id} par {user_info}"

    def save(self, *args, **kwargs):
        """Mise à jour du compteur de vues lors de la sauvegarde"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            Post.objects.filter(id=self.post.id).update(
                views_count=models.F('views_count') + 1
            )