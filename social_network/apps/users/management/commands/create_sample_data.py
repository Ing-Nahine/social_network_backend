import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from faker import Faker
from apps.users.models import Follow, UserProfile
from apps.posts.models import Post, PostMedia, Hashtag, PostHashtag, Mention
from apps.interactions.models import Like, Comment, Bookmark, Share

User = get_user_model()
fake = Faker('fr_FR')  # Français


class Command(BaseCommand):
    help = 'Crée des données d\'exemple pour le développement'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=50,
            help='Nombre d\'utilisateurs à créer'
        )
        parser.add_argument(
            '--posts',
            type=int,
            default=200,
            help='Nombre de posts à créer'
        )
        parser.add_argument(
            '--interactions',
            type=int,
            default=1000,
            help='Nombre d\'interactions à créer (likes, comments, etc.)'
        )

    def handle(self, *args, **options):
        users_count = options['users']
        posts_count = options['posts']
        interactions_count = options['interactions']

        self.stdout.write(
            self.style.SUCCESS(
                f'Création de {users_count} utilisateurs, {posts_count} posts, '
                f'et {interactions_count} interactions...'
            )
        )

        with transaction.atomic():
            # Créer les utilisateurs
            self.create_users(users_count)
            
            # Créer les relations de suivi
            self.create_follows()
            
            # Créer les hashtags populaires
            self.create_hashtags()
            
            # Créer les posts
            self.create_posts(posts_count)
            
            # Créer les interactions
            self.create_interactions(interactions_count)

        self.stdout.write(
            self.style.SUCCESS('Données d\'exemple créées avec succès!')
        )

    def create_users(self, count):
        """Créer des utilisateurs fictifs"""
        self.stdout.write('Création des utilisateurs...')
        
        users = []
        for i in range(count):
            username = fake.user_name()
            # S'assurer de l'unicité du nom d'utilisateur
            while User.objects.filter(username=username).exists():
                username = fake.user_name()
            
            email = fake.email()
            # S'assurer de l'unicité de l'email
            while User.objects.filter(email=email).exists():
                email = fake.email()
            
            user = User(
                username=username,
                email=email,
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                bio=fake.text(max_nb_chars=200) if random.choice([True, False]) else '',
                location=fake.city() if random.choice([True, False]) else '',
                website=fake.url() if random.choice([True, False]) else '',
                birth_date=fake.date_of_birth(minimum_age=16, maximum_age=80) if random.choice([True, False]) else None,
                is_verified=random.choice([True, False]) if random.randint(1, 10) == 1 else False,
                is_private=random.choice([True, False]) if random.randint(1, 5) == 1 else False,
            )
            user.set_password('password123')
            users.append(user)
        
        User.objects.bulk_create(users, batch_size=100)
        
        # Créer les profils utilisateur
        profiles = []
        for user in User.objects.filter(username__in=[u.username for u in users]):
            profile = UserProfile(
                user=user,
                theme=random.choice(['light', 'dark', 'auto']),
                language=random.choice(['fr', 'en']),
                email_notifications=random.choice([True, False]),
                push_notifications=random.choice([True, False])
            )
            profiles.append(profile)
        
        UserProfile.objects.bulk_create(profiles, batch_size=100)
        
        self.stdout.write(f'✓ {count} utilisateurs créés')

    def create_follows(self):
        """Créer des relations de suivi aléatoires"""
        self.stdout.write('Création des relations de suivi...')
        
        users = list(User.objects.all())
        follows = []
        
        for user in users:
            # Chaque utilisateur suit entre 5 et 30 autres utilisateurs
            following_count = random.randint(5, min(30, len(users) - 1))
            potential_follows = [u for u in users if u != user]
            
            to_follow = random.sample(potential_follows, following_count)
            
            for followed_user in to_follow:
                follow = Follow(
                    follower=user,
                    followed=followed_user
                )
                follows.append(follow)
        
        # Éviter les doublons
        unique_follows = []
        seen = set()
        for follow in follows:
            key = (follow.follower.id, follow.followed.id)
            if key not in seen:
                seen.add(key)
                unique_follows.append(follow)
        
        Follow.objects.bulk_create(unique_follows, batch_size=100, ignore_conflicts=True)
        
        self.stdout.write(f'✓ {len(unique_follows)} relations de suivi créées')

    def create_hashtags(self):
        """Créer des hashtags populaires"""
        self.stdout.write('Création des hashtags...')
        
        hashtag_names = [
            'python', 'django', 'webdev', 'coding', 'tech', 'ai', 'machine_learning',
            'startup', 'entrepreneur', 'business', 'design', 'ux', 'ui', 'frontend',
            'backend', 'javascript', 'react', 'vue', 'nodejs', 'docker', 'kubernetes',
            'aws', 'cloud', 'devops', 'agile', 'scrum', 'productivity', 'motivation',
            'success', 'learning', 'career', 'remote_work', 'freelance', 'side_project'
        ]
        
        hashtags = []
        for name in hashtag_names:
            hashtag = Hashtag(
                name=name,
                posts_count=0,
                trending_score=random.uniform(0, 100)
            )
            hashtags.append(hashtag)
        
        Hashtag.objects.bulk_create(hashtags, ignore_conflicts=True)
        
        self.stdout.write(f'✓ {len(hashtag_names)} hashtags créés')

    def create_posts(self, count):
        """Créer des posts fictifs"""
        self.stdout.write('Création des posts...')
        
        users = list(User.objects.all())
        hashtags = list(Hashtag.objects.all())
        
        post_templates = [
            "Juste terminé de travailler sur un nouveau projet #webdev #coding !",
            "Excellente journée de développement avec #python #django 🚀",
            "Quelqu'un d'autre trouve que le #javascript devient de plus en plus complexe ?",
            "Nouveau tutoriel sur #react disponible sur mon blog !",
            "Les #microservices, pour ou contre ? Débat ouvert 💭",
            "Première fois avec #docker, impressionné par la simplicité !",
            "Tips du jour : toujours commenter son code #bestpractices #coding",
            "La #productivité avant tout dans le développement !",
            "Retour d'expérience sur mon dernier projet #startup #entrepreneur",
            "Le #remote_work change vraiment la donne dans la tech 🏠"
        ]
        
        posts = []
        post_hashtags = []
        mentions = []
        
        for i in range(count):
            author = random.choice(users)
            
            # Type de post
            post_type = random.choices(
                ['original', 'retweet', 'quote', 'reply'],
                weights=[70, 15, 10, 5]
            )[0]
            
            # Contenu du post
            if i < len(post_templates):
                content = post_templates[i]
            else:
                content = fake.text(max_nb_chars=200)
                # Ajouter quelques hashtags aléatoirement
                if random.choice([True, False]):
                    selected_hashtags = random.sample(hashtags, random.randint(1, 3))
                    for hashtag in selected_hashtags:
                        content += f" #{hashtag.name}"
            
            post = Post(
                author=author,
                content=content,
                post_type=post_type,
                likes_count=random.randint(0, 100),
                retweets_count=random.randint(0, 50),
                replies_count=random.randint(0, 25),
                views_count=random.randint(10, 1000),
                is_pinned=random.choice([True, False]) if random.randint(1, 20) == 1 else False,
                allow_replies=random.choice([True, False]) if random.randint(1, 10) == 1 else True,
                is_sensitive=random.choice([True, False]) if random.randint(1, 15) == 1 else False,
                created_at=fake.date_time_between(start_date='-30d', end_date='now', tzinfo=None)
            )
            posts.append(post)
        
        Post.objects.bulk_create(posts, batch_size=100)
        
        # Créer les relations post-hashtag
        created_posts = Post.objects.filter(author__in=users).order_by('-created_at')[:count]
        
        for post in created_posts:
            # Extraire les hashtags du contenu
            import re
            hashtag_matches = re.findall(r'#(\w+)', post.content.lower())
            
            for hashtag_name in hashtag_matches:
                try:
                    hashtag = Hashtag.objects.get(name=hashtag_name)
                    post_hashtag = PostHashtag(
                        post=post,
                        hashtag=hashtag
                    )
                    post_hashtags.append(post_hashtag)
                except Hashtag.DoesNotExist:
                    pass
            
            # Créer des mentions aléatoires
            if random.choice([True, False, False, False]):  # 25% de chance
                mentioned_users = random.sample(users, random.randint(1, 2))
                for mentioned_user in mentioned_users:
                    if mentioned_user != post.author:
                        mention = Mention(
                            post=post,
                            mentioned_user=mentioned_user,
                            position=random.randint(0, len(post.content))
                        )
                        mentions.append(mention)
        
        PostHashtag.objects.bulk_create(post_hashtags, batch_size=100, ignore_conflicts=True)
        Mention.objects.bulk_create(mentions, batch_size=100, ignore_conflicts=True)
        
        # Mettre à jour les compteurs de hashtags
        for hashtag in hashtags:
            hashtag.posts_count = PostHashtag.objects.filter(hashtag=hashtag).count()
            hashtag.save(update_fields=['posts_count'])
        
        self.stdout.write(f'✓ {count} posts créés')

    def create_interactions(self, count):
        """Créer des interactions fictives (likes, comments, bookmarks, shares)"""
        self.stdout.write('Création des interactions...')
        
        users = list(User.objects.all())
        posts = list(Post.objects.all())
        
        likes = []
        comments = []
        bookmarks = []
        shares = []
        
        interaction_count = 0
        
        # Créer des likes
        likes_to_create = count // 2
        for _ in range(likes_to_create):
            user = random.choice(users)
            post = random.choice(posts)
            
            # Éviter qu'un utilisateur like son propre post
            if user != post.author:
                like = Like(
                    user=user,
                    post=post
                )
                likes.append(like)
                interaction_count += 1
        
        # Créer des commentaires
        comments_to_create = count // 4
        for _ in range(comments_to_create):
            author = random.choice(users)
            post = random.choice(posts)
            
            comment = Comment(
                author=author,
                post=post,
                content=fake.text(max_nb_chars=150),
                likes_count=random.randint(0, 20)
            )
            comments.append(comment)
            interaction_count += 1
        
        # Créer des bookmarks
        bookmarks_to_create = count // 8
        for _ in range(bookmarks_to_create):
            user = random.choice(users)
            post = random.choice(posts)
            
            bookmark = Bookmark(
                user=user,
                post=post
            )
            bookmarks.append(bookmark)
            interaction_count += 1
        
        # Créer des shares
        shares_to_create = count // 8
        for _ in range(shares_to_create):
            user = random.choice(users)
            post = random.choice(posts)
            
            if user != post.author:
                share = Share(
                    user=user,
                    original_post=post,
                    share_type=random.choice(['retweet', 'quote']),
                    quote_content=fake.text(max_nb_chars=100) if random.choice([True, False]) else ''
                )
                shares.append(share)
                interaction_count += 1
        
        # Créer en lot pour éviter les doublons
        Like.objects.bulk_create(likes, batch_size=100, ignore_conflicts=True)
        Comment.objects.bulk_create(comments, batch_size=100)
        Bookmark.objects.bulk_create(bookmarks, batch_size=100, ignore_conflicts=True)
        Share.objects.bulk_create(shares, batch_size=100, ignore_conflicts=True)
        
        self.stdout.write(f'✓ {interaction_count} interactions créées')

    def create_sample_admin(self):
        """Créer un utilisateur admin pour les tests"""
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@socialnetwork.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
                'bio': 'Administrateur de la plateforme'
            }
        )
        
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            
            # Créer le profil
            UserProfile.objects.create(user=admin_user)
            
            self.stdout.write('✓ Utilisateur admin créé (admin/admin123)')
        else:
            self.stdout.write('✓ Utilisateur admin existe déjà')

    def create_test_users(self):
        """Créer des utilisateurs de test spécifiques"""
        test_users = [
            {
                'username': 'john_dev',
                'email': 'john@example.com',
                'first_name': 'John',
                'last_name': 'Developer',
                'bio': 'Développeur Python/Django passionné #webdev #python',
                'is_verified': True
            },
            {
                'username': 'marie_design',
                'email': 'marie@example.com',
                'first_name': 'Marie',
                'last_name': 'Designer',
                'bio': 'UI/UX Designer créative #design #ux',
                'is_verified': True
            },
            {
                'username': 'tech_startup',
                'email': 'contact@techstartup.com',
                'first_name': 'Tech',
                'last_name': 'Startup',
                'bio': 'Startup innovante dans la tech 🚀 #startup #innovation',
                'is_verified': True
            }
        ]
        
        for user_data in test_users:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults=user_data
            )
            
            if created:
                user.set_password('test123')
                user.save()
                UserProfile.objects.create(user=user)
                self.stdout.write(f'✓ Utilisateur test {user.username} créé')

    def handle(self, *args, **options):
        users_count = options['users']
        posts_count = options['posts']
        interactions_count = options['interactions']

        self.stdout.write(
            self.style.SUCCESS(
                f'Création de {users_count} utilisateurs, {posts_count} posts, '
                f'et {interactions_count} interactions...'
            )
        )

        with transaction.atomic():
            # Créer l'admin et les utilisateurs de test d'abord
            self.create_sample_admin()
            self.create_test_users()
            
            # Créer les utilisateurs fictifs
            self.create_users(users_count)
            
            # Créer les relations de suivi
            self.create_follows()
            
            # Créer les hashtags populaires
            self.create_hashtags()
            
            # Créer les posts
            self.create_posts(posts_count)
            
            # Créer les interactions
            self.create_interactions(interactions_count)
            
            # Mettre à jour les compteurs utilisateur
            self.update_user_counters()

        self.stdout.write(
            self.style.SUCCESS('✅ Données d\'exemple créées avec succès!')
        )
        self.stdout.write(
            self.style.WARNING(
                '\n📋 Comptes de test créés:\n'
                '- admin/admin123 (Administrateur)\n'
                '- john_dev/test123 (Développeur)\n'
                '- marie_design/test123 (Designer)\n'
                '- tech_startup/test123 (Startup)\n'
            )
        )

    def update_user_counters(self):
        """Mettre à jour les compteurs des utilisateurs"""
        self.stdout.write('Mise à jour des compteurs...')
        
        for user in User.objects.all():
            # Mettre à jour les compteurs de posts
            posts_count = Post.objects.filter(author=user, post_type='original').count()
            
            # Mettre à jour les compteurs de followers/following
            followers_count = Follow.objects.filter(followed=user).count()
            following_count = Follow.objects.filter(follower=user).count()
            
            user.posts_count = posts_count
            user.followers_count = followers_count
            user.following_count = following_count
            user.save(update_fields=['posts_count', 'followers_count', 'following_count'])
        
        self.stdout.write('✓ Compteurs mis à jour')