# 🌐 Guide d'accès Internet avec HTTPS - ENSAM Cloud Platform

## 🔒 HTTPS - Obligatoire pour l'accès Internet

Pour un accès sécurisé depuis Internet, **HTTPS est requis**. Trois options sont disponibles :

---

## Option 1 : HTTPS avec certificat SSL auto-signé (Développement)

### Étape 1 : Générer le certificat SSL

```powershell
.\setup-https.ps1
```

**Prérequis** : OpenSSL doit être installé
- Télécharger : https://slproweb.com/products/Win32OpenSSL.html
- Ou installer via Chocolatey : `choco install openssl`

### Étape 2 : Démarrer le serveur avec HTTPS

```powershell
.\start-server-https.ps1
```

Le serveur sera accessible sur le **port 8443** avec HTTPS.

### Étape 3 : Configurer le port forwarding

Sur le routeur, rediriger :
- **Port externe** : `8443` (HTTPS)
- **IP interne** : `192.168.128.43`
- **Port interne** : `8443`

### Accès

- Local : `https://localhost:8443`
- Réseau : `https://192.168.128.43:8443`
- Internet : `https://196.75.17.34:8443`

⚠️ **Note** : Les navigateurs afficheront un avertissement car le certificat est auto-signé. Cliquez sur "Avancé" puis "Continuer vers le site".

---

## Option 2 : Tunnel HTTPS avec ngrok (Recommandé pour tests)

### Avantages
- ✅ Configuration rapide (pas de certificat à gérer)
- ✅ URL HTTPS publique immédiate
- ✅ Pas besoin de configurer le routeur

### Étape 1 : Installer ngrok

1. Télécharger : https://ngrok.com/download
2. Extraire `ngrok.exe` dans `C:\Cloud` ou dans le PATH

### Étape 2 : Démarrer le serveur HTTP (port 8080)

Dans un terminal :
```powershell
.\start-server.ps1
```

### Étape 3 : Démarrer ngrok

Dans un autre terminal :
```powershell
.\start-ngrok.ps1
```

Ou directement :
```powershell
ngrok http 8080
```

### Résultat

ngrok génère une URL HTTPS comme : `https://abc123.ngrok.io`

Cette URL est accessible depuis n'importe où sur Internet.

### Pour une URL permanente

1. Créer un compte sur https://ngrok.com
2. Obtenir votre authtoken
3. Exécuter : `ngrok config add-authtoken <VOTRE_TOKEN>`
4. Utiliser : `ngrok http 8080 --domain=votre-domaine.ngrok.io`

---

## Option 3 : Docker avec nginx (Production)

### Configuration complète avec HTTPS

```powershell
cd docker
docker-compose up -d
```

Nginx est déjà configuré pour :
- ✅ Rediriger HTTP (port 80) vers HTTPS (port 443)
- ✅ Certificat SSL auto-signé (développement)
- ✅ Support Let's Encrypt (production)

### Pour Let's Encrypt (production)

1. Avoir un nom de domaine pointant vers ton IP publique
2. Modifier `docker-compose.yml` pour activer certbot
3. Le certificat sera généré automatiquement

---

## 📋 Checklist HTTPS

### ✅ Configuration actuelle
- [x] Pare-feu Windows configuré (ports 8080, 8443)
- [x] CORS configuré pour accepter toutes les origines
- [x] Serveur configuré pour écouter sur 0.0.0.0

### ⚠️ À faire selon l'option choisie

**Option 1 (SSL auto-signé)** :
- [ ] Installer OpenSSL
- [ ] Générer le certificat (`.\setup-https.ps1`)
- [ ] Configurer port forwarding (port 8443)
- [ ] Démarrer avec HTTPS (`.\start-server-https.ps1`)

**Option 2 (ngrok)** :
- [ ] Installer ngrok
- [ ] Démarrer le serveur HTTP (`.\start-server.ps1`)
- [ ] Démarrer ngrok (`.\start-ngrok.ps1`)

**Option 3 (Docker)** :
- [ ] Installer Docker Desktop
- [ ] Lancer `docker-compose up -d`
- [ ] Configurer port forwarding (ports 80, 443)

---

## 🔧 Configuration du routeur (Option 1 et 3)

### Ports à rediriger

| Option | Port externe | Port interne | Protocole |
|--------|--------------|--------------|-----------|
| Option 1 | 8443 | 8443 | HTTPS |
| Option 3 | 443 | 443 | HTTPS |
| Option 3 | 80 | 80 | HTTP (redirige vers HTTPS) |

### Étapes générales :
1. Accéder au routeur : `http://192.168.128.1`
2. Se connecter
3. Trouver "Port Forwarding" / "Virtual Server" / "NAT"
4. Ajouter les règles ci-dessus
5. Sauvegarder

---

## 🧪 Test de connexion

### Option 1 (SSL auto-signé)
```
https://196.75.17.34:8443
```

### Option 2 (ngrok)
```
https://abc123.ngrok.io
```

### Option 3 (Docker)
```
https://196.75.17.34
```

---

## ⚠️ Notes importantes

1. **Certificat auto-signé** : Les navigateurs afficheront un avertissement. C'est normal pour le développement.

2. **Production** : Utilisez Let's Encrypt avec un nom de domaine pour un certificat valide.

3. **IP dynamique** : L'IP publique peut changer. Vérifiez-la régulièrement :
   ```powershell
   Invoke-RestMethod -Uri "https://api.ipify.org"
   ```

4. **Sécurité** : HTTPS est obligatoire pour l'accès Internet. Ne pas exposer HTTP directement.

---

## 🚀 Recommandation

- **Tests/Développement** : Utiliser **ngrok** (Option 2) - le plus simple
- **Production** : Utiliser **Docker + nginx + Let's Encrypt** (Option 3) - le plus sécurisé

---

## 📞 Support

Pour toute question :
- Vérifier les logs du serveur
- Vérifier la configuration du routeur
- Vérifier le pare-feu Windows
- Consulter la documentation ngrok : https://ngrok.com/docs
