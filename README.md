# 🐦 Social Network Backend - Type Twitter

Backend complet pour un réseau social inspiré de Twitter, développé avec Django REST Framework.

## 🚀 Fonctionnalités

### 👥 Authentification & Utilisateurs
- ✅ Inscription/Connexion avec JWT
- ✅ Profils utilisateur complets (avatar, bannière, bio)
- ✅ Système de suivi (follow/unfollow)
- ✅ Comptes publics/privés
- ✅ Suggestions d'utilisateurs à suivre
- ✅ Statistiques utilisateur détaillées

### 📝 Posts & Contenu
- ✅ Création de posts (280 caractères max)
- ✅ Support médias (images/vidéos)
- ✅ Hashtags automatiques
- ✅ Mentions d'utilisateurs (@username)
- ✅ Posts programmés
- ✅ Géolocalisation optionnelle

### 💬 Interactions
- ✅ Likes sur posts et commentaires
- ✅ Commentaires et réponses
- ✅ Retweets (simple et avec citation)
- ✅ Signets/Favoris
- ✅ Vues des posts

### 🔔 Notifications
- ✅ Notifications en temps réel (WebSocket)
- ✅ Notifications push (WebPush)
- ✅ Notifications par email
- ✅ Digests quotidiens/hebdomadaires/mensuels
- ✅ Préférences de notification

### 📊 Analytics & Performance
- ✅ Statistiques détaillées par utilisateur
- ✅ Hashtags tendance
- ✅ Rate limiting
- ✅ Pagination optimisée
- ✅ Cache Redis

## 🛠️ Technologies Utilisées

- **Backend**: Django 4.2 + Django REST Framework
- **Base de données**: PostgreSQL
- **Cache**: Redis
- **Tâches asynchrones**: Celery
- **WebSockets**: Django Channels
- **Authentification**: JWT (Simple JWT)
- **Médias**: Django ImageKit
- **Documentation API**: Swagger/OpenAPI
- **Containerisation**: Docker + Docker Compose

## 📦 Installation

### Prérequis
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optionnel)

### 🐳 Installation avec Docker (Recommandée)

1. **Cloner le projet**
```bash
git clone <url-du-repo>
cd social-network-backend
```

2. **Configurer les variables d'environnement**
```bash
cp .env.example .env
# Éditer le fichier .env avec vos paramètres
```

3. **Lancer avec Docker Compose**
```bash
docker-compose up -d
```

4. **Créer un superutilisateur**
```bash
docker-compose exec web python manage.py createsuperuser
```

5. **Créer des données d'exemple** (optionnel)
```bash
docker-compose exec web python manage.py create_sample_data --users 50 --posts 200 --interactions 1000
```

### 💻 Installation Manuelle

1. **Cloner et configurer l'environnement**
```bash
git clone <url-du-repo>
cd social-network-backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

2. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

3. **Configurer la base de données**
```bash
# Créer la base PostgreSQL
createdb social_network

# Copier et configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos paramètres de DB
```

4. **Migrations et données initiales**
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py create_sample_data --users 20 --posts 100
```

5. **Lancer le serveur de développement**
```bash
# Terminal 1: Serveur Django
python manage.py runserver

# Terminal 2: Worker Celery
celery -A social_network worker --loglevel=info

# Terminal 3: Celery Beat
celery -A social_network beat --loglevel=info

# Terminal 4: Serveur WebSocket
python manage.py runserver 8001
```

## 🌐 Endpoints API

### Authentification
```
POST /api/auth/register/          # Inscription
POST /api/auth/login/             # Connexion
POST /api/auth/refresh/           # Rafraîchir token
POST /api/auth/verify/            # Vérifier token
```

### Utilisateurs
```
GET    /api/users/profile/                    # Profil actuel
PUT    /api/users/profile/                    # Modifier profil
GET    /api/users/<username>/                 # Profil public
POST   /api/users/<username>/follow/          # Suivre
DELETE /api/users/<username>/follow/          # Ne plus suivre
GET    /api/users/<username>/followers/       # Liste followers
GET    /api/users/<username>/following/       # Liste suivis
GET    /api/users/search/?q=<query>           # Rechercher users
GET    /api/users/suggestions/                # Suggestions
```

### Posts
```
GET    /api/posts/                            # Feed principal
POST   /api/posts/                            # Créer post
GET    /api/posts/<id>/                       # Détail post
PUT    /api/posts/<id>/                       # Modifier post
DELETE /api/posts/<id>/                       # Supprimer post
GET    /api/posts/trending/                   # Posts tendance
GET    /api/posts/hashtag/<name>/             # Posts par hashtag
```

### Interactions
```
POST   /api/interactions/posts/<id>/like/     # Liker
DELETE /api/interactions/posts/<id>/like/     # Unliker
POST   /api/interactions/posts/<id>/bookmark/ # Marquer
POST   /api/interactions/posts/<id>/share/    # Partager
GET    /api/interactions/posts/<id>/comments/ # Commentaires
POST   /api/interactions/posts/<id>/comments/ # Commenter
```

### Notifications
```
GET    /api/notifications/                    # Liste notifications
PUT    /api/notifications/mark-read/          # Marquer lues
GET    /api/notifications/unread-count/       # Compteur non lues
PUT    /api/notifications/preferences/        # Préférences
```

## 📚 Documentation API

Une fois le serveur lancé, accédez à :
- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/

## 🔧 Configuration

### Variables d'environnement principales

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de données
DB_NAME=social_network
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### Paramètres de production

Pour la production, ajustez ces paramètres dans `.env` :

```bash
DEBUG=False
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
USE_S3=True  # Pour le stockage des médias
SENTRY_DSN=your-sentry-dsn  # Monitoring des erreurs
```

## 🚀 Déploiement

### Avec Docker sur serveur

1. **Préparer le serveur**
```bash
# Installer Docker et Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Cloner le projet
git clone <url-du-repo>
cd social-network-backend
```

2. **Configuration production**
```bash
cp .env.example .env
# Configurer les variables pour la production
nano .env
```

3. **SSL/HTTPS avec Let's Encrypt**
```bash
# Modifier docker-compose.yml pour inclure Certbot
# Ou utiliser un reverse proxy comme Traefik
```

4. **Lancer en production**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Sur plateformes cloud

- **Heroku**: Utiliser le Procfile inclus
- **AWS/DigitalOcean**: Docker Compose + Load Balancer
- **Railway/Render**: Déploiement direct depuis Git

## 🧪 Tests

```bash
# Tests unitaires
python manage.py test

# Tests avec couverture
coverage run --source='.' manage.py test
coverage report

# Tests d'intégration API
python manage.py test apps.tests.integration
```

## 📊 Monitoring et Logs

### Flower (Monitoring Celery)
```
http://localhost:5555
```

### Logs
```bash
# Logs Docker
docker-compose logs -f web

# Logs Django
tail -f logs/django.log

# Logs Celery
tail -f logs/celery.log
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit les changements (`git commit -m 'Ajouter nouvelle fonctionnalité'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Ouvrir une Pull Request

## 📝 TODO / Roadmap

### Fonctionnalités à venir
- [ ] Messages directs
- [ ] Stories temporaires
- [ ] Sondages dans les posts
- [ ] Espaces/Communautés
- [ ] API GraphQL
- [ ] Mode sombre/clair
- [ ] Application mobile (React Native)
- [ ] Streaming en direct
- [ ] Monétisation (abonnements)

### Améliorations techniques
- [ ] Cache distributé (Redis Cluster)
- [ ] CDN pour les médias
- [ ] Recherche ElasticSearch
- [ ] Analytics avancées
- [ ] Modération automatique (IA)
- [ ] Tests automatisés (CI/CD)

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 👨‍💻 Auteur

Développé pour une série de vidéos YouTube sur la création d'un réseau social avec Django.

---

## ⚡ Quick Start pour YouTube

Si vous suivez les vidéos YouTube, voici le quick start :

```bash
# Cloner et lancer rapidement
git clone <repo>
cd social-network-backend
cp .env.example .env
docker-compose up -d
docker-compose exec web python manage.py create_sample_data

# Accéder à l'API
curl http://localhost:8000/api/users/stats/public/

# Documentation
http://localhost:8000/swagger/
```

**Comptes de test créés automatiquement :**
- `admin` / `admin123` (Administrateur)
- `john_dev` / `test123` (Développeur)
- `marie_design` / `test123` (Designer)

🎉 **C'est parti ! Vous avez maintenant un réseau social fonctionnel !**