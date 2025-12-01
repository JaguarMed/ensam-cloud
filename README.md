# Plateforme Cloud Privée pour l'Exécution Distante de Scripts Python avec Support GPU

**ENSAM Rabat - Cloud Computing 2025**

## 📋 Description

Cette plateforme permet aux étudiants d'exécuter des scripts Python à distance sur un serveur équipé d'un CPU/GPU via une interface web sécurisée. Elle implémente les 8 exigences fonctionnelles (EF1-EF8) du cahier des charges.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Client (Navigateur Web)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │    Login    │  │   Éditeur   │  │      Historique         │ │
│  │   (EF1)     │  │   (EF2)     │  │   (EF6, EF7, EF8)       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Nginx Reverse Proxy                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │    HTTPS    │  │ Rate Limit  │  │   Load Balancing        │ │
│  │   (TLS)     │  │  (ufw)      │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Auth JWT   │  │  Jobs API   │  │   WebSocket Logs        │ │
│  │   (EF1)     │  │  (EF2,EF8)  │  │      (EF5)              │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Prometheus Metrics (EF7)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Compute Core (Docker)                       │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              Docker Containers (EF3, EF4)                  │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │ │
│  │  │  CPU Job    │  │  GPU Job    │  │   Resource      │   │ │
│  │  │  Container  │  │  Container  │  │   Limits        │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Monitoring Stack                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Prometheus  │  │  Grafana    │  │   Node Exporter         │ │
│  │             │  │             │  │   cAdvisor              │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## ✅ Exigences Fonctionnelles

| EF | Description | Statut |
|----|-------------|--------|
| **EF1** | Authentification utilisateur avec JWT | ✅ Implémenté |
| **EF2** | Upload/édition de scripts et soumission | ✅ Implémenté |
| **EF3** | Exécution isolée avec limites de ressources | ✅ Implémenté |
| **EF4** | Accélération GPU (NVIDIA) | ✅ Implémenté |
| **EF5** | Streaming temps réel des logs (WebSocket) | ✅ Implémenté |
| **EF6** | Historique des jobs et visualisation | ✅ Implémenté |
| **EF7** | Service mesuré / métriques Prometheus | ✅ Implémenté |
| **EF8** | Annulation manuelle des jobs | ✅ Implémenté |

## 🚀 Installation et Démarrage

### Prérequis

- Python 3.10+
- Docker Desktop (pour l'exécution isolée)
- NVIDIA Container Toolkit (optionnel, pour GPU)

### Installation locale (Développement)

```bash
# 1. Cloner le projet
git clone <repository-url>
cd Cloud

# 2. Créer un environnement virtuel
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer l'environnement
copy env.example .env
# Modifier .env selon vos besoins

# 5. Lancer l'application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Accès à l'application

| Service | URL | Description |
|---------|-----|-------------|
| Interface Web | http://localhost:8080 | Application principale (HTTP) |
| Interface Web | https://localhost:8443 | Application principale (HTTPS) |
| Admin Panel | http://localhost:8080/admin | Interface administrateur |
| API Docs | http://localhost:8080/api/docs | Documentation Swagger |
| Métriques | http://localhost:8080/api/metrics/ | Prometheus metrics |

**⚠️ Pour l'accès Internet, HTTPS est obligatoire.** Voir `ACCES-INTERNET.md` pour la configuration.

### Comptes de démonstration

| Email | Mot de passe | Rôle |
|-------|--------------|------|
| admin@ensam.ma | admin123 | Administrateur |
| demo@ensam.ma | demo123 | Utilisateur |

### Accès depuis un autre appareil

Pour accéder à la plateforme depuis un autre appareil sur le même réseau :

1. Trouver l'IP du serveur : `ipconfig` (Windows) ou `ip addr` (Linux)
2. Accéder via : `http://<IP_SERVEUR>:8000`

Exemple : `http://192.168.128.43:8000`

## 🐳 Déploiement avec Docker

### Déploiement simple (développement)

```bash
cd docker
docker-compose up -d app
```

### Déploiement complet avec monitoring

```bash
cd docker
docker-compose up -d
```

Services démarrés :
| Service | Port | Description |
|---------|------|-------------|
| **nginx** | 80, 443 | Reverse proxy avec HTTPS |
| **app** | 8000 | Application FastAPI |
| **prometheus** | 9090 | Collecte des métriques |
| **grafana** | 3000 | Tableaux de bord (admin/admin) |
| **node-exporter** | 9100 | Métriques système |
| **cadvisor** | 8081 | Métriques containers |

### Déploiement avec Ansible (Production)

```bash
cd ansible

# Éditer l'inventaire
nano inventory.ini

# Lancer le déploiement
ansible-playbook -i inventory.ini playbook.yml
```

## 📊 Monitoring & Métriques

### Métriques Prometheus

L'endpoint `/api/metrics/` expose :

```
# Jobs
ensam_cloud_jobs_total{status="success|failed|running|..."}
ensam_cloud_jobs_running
ensam_cloud_jobs_queued
ensam_cloud_jobs_submitted_total{user_id, execution_mode}

# Durées
ensam_cloud_job_duration_seconds{execution_mode, resource_profile}
ensam_cloud_job_queue_time_seconds

# GPU vs CPU
ensam_cloud_gpu_jobs_total
ensam_cloud_cpu_jobs_total

# Utilisateurs
ensam_cloud_active_users
```

### Dashboard Grafana

Un dashboard pré-configuré est disponible avec :
- Vue d'ensemble (jobs, utilisateurs, taux de succès)
- Utilisation CPU/RAM système
- Métriques par container Docker
- Performance des jobs (durée, statuts)

Accès : http://localhost:3000 (admin/admin)

## 🔒 Sécurité

### Authentification JWT
- Tokens avec expiration configurable
- Refresh automatique côté client
- Routes protégées par middleware

### Isolation Docker
- Chaque job dans un container séparé
- Réseau isolé (`network_mode: none`)
- Limites CPU/RAM/timeout

### HTTPS (Production)
Configuration nginx avec :
- TLS 1.2/1.3
- Headers de sécurité (HSTS, CSP, X-Frame-Options)
- Certificat Let's Encrypt

### Rate Limiting

```nginx
# Login: 5 requêtes/minute
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

# API: 60 requêtes/minute
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=60r/m;
```

### Pare-feu (ufw)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8000/tcp  # App (dev)
sudo ufw enable
```

## 🖥️ Profils de Ressources

| Profil | CPU | RAM | Timeout |
|--------|-----|-----|---------|
| small | 512 shares | 512 MB | 60s |
| medium | 1024 shares | 2 GB | 5 min |
| large | 2048 shares | 4 GB | 15 min |
| gpu | 2048 shares | 8 GB | 30 min |

## 📁 Structure du Projet

```
Cloud/
├── src/                    # Code source principal
│   ├── main.py            # Point d'entrée FastAPI
│   ├── models.py          # Modèles SQLAlchemy
│   ├── schemas.py         # Schémas Pydantic
│   ├── core/              # Configuration et sécurité
│   │   ├── config.py      # Settings (pydantic-settings)
│   │   ├── database.py    # Connexion DB
│   │   └── security.py    # JWT et auth
│   ├── api/routes/        # Routes API
│   │   ├── auth.py        # Authentification
│   │   ├── jobs.py        # Gestion des jobs
│   │   ├── admin.py       # Administration
│   │   ├── metrics.py     # Métriques Prometheus
│   │   └── websocket.py   # Streaming logs
│   ├── services/          # Services métier
│   │   ├── executor.py    # Exécution Docker
│   │   └── metrics.py     # Prometheus client
│   └── templates/         # Templates HTML (Jinja2)
├── docker/                # Configuration Docker
│   ├── Dockerfile         # Image de l'application
│   ├── docker-compose.yml # Orchestration complète
│   ├── prometheus.yml     # Config Prometheus
│   ├── nginx/             # Reverse proxy
│   │   ├── nginx.conf
│   │   └── Dockerfile
│   └── grafana/           # Dashboards
│       └── provisioning/
├── ansible/               # Déploiement automatisé
│   ├── playbook.yml       # Playbook principal
│   ├── inventory.ini      # Serveurs cibles
│   └── templates/         # Templates Jinja2
├── data/                  # Données runtime
│   ├── scripts/           # Scripts utilisateurs
│   ├── logs/              # Logs d'exécution
│   └── results/           # Résultats
├── requirements.txt       # Dépendances Python
├── env.example           # Variables d'environnement
└── README.md
```

## 📝 API Endpoints

### Authentification
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/login` | Connexion |
| POST | `/api/auth/register` | Inscription |
| GET | `/api/auth/me` | Utilisateur courant |

### Jobs
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/jobs/run` | Soumettre un job |
| POST | `/api/jobs/upload` | Upload et exécuter |
| GET | `/api/jobs/history` | Historique |
| GET | `/api/jobs/{id}` | Détails d'un job |
| GET | `/api/jobs/{id}/logs` | Logs |
| POST | `/api/jobs/{id}/cancel` | Annuler |

### Admin
| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/admin/stats` | Statistiques globales |
| GET | `/api/admin/users` | Liste utilisateurs |
| PUT | `/api/admin/users/{id}` | Modifier utilisateur |
| DELETE | `/api/admin/users/{id}` | Supprimer utilisateur |
| GET | `/api/admin/jobs` | Tous les jobs |
| GET | `/api/admin/monitoring/charts` | Données graphiques |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `WS /ws/jobs/{id}/logs?token=...` | Streaming logs temps réel |

## 🔧 Configuration

Variables d'environnement (`.env`) :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `SECRET_KEY` | Clé secrète JWT | ⚠️ À changer |
| `DATABASE_URL` | URL base de données | SQLite local |
| `DOCKER_IMAGE_CPU` | Image Docker CPU | python:3.11-slim |
| `DOCKER_IMAGE_GPU` | Image Docker GPU | nvidia/cuda:12.0 |
| `GPU_ENABLED` | Activer GPU | true |
| `RATE_LIMIT_PER_MINUTE` | Limite requêtes | 60 |

## 📄 Licence

Projet universitaire - ENSAM Rabat
