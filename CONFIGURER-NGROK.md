# 🔐 Configuration ngrok - Guide rapide

## ⚠️ ngrok nécessite maintenant un compte gratuit

Depuis 2023, ngrok nécessite un compte (gratuit) pour fonctionner.

## 📝 Étapes pour configurer ngrok

### Étape 1 : Créer un compte ngrok

1. Aller sur : https://dashboard.ngrok.com/signup
2. Créer un compte gratuit (email + mot de passe)
3. Vérifier ton email

### Étape 2 : Obtenir ton authtoken

1. Se connecter sur : https://dashboard.ngrok.com/get-started/your-authtoken
2. Copier ton authtoken (ressemble à : `2abc123def456ghi789jkl012mno345pq_6rStUvWxYz7AbCdEfGhIjKl`)

### Étape 3 : Configurer ngrok

Dans PowerShell (dans le dossier C:\Cloud) :

```powershell
.\ngrok.exe config add-authtoken <TON_AUTHTOKEN>
```

Remplace `<TON_AUTHTOKEN>` par le token que tu as copié.

### Étape 4 : Démarrer le tunnel

```powershell
.\ngrok.exe http 8080
```

## ✅ Vérification

Une fois configuré, ngrok affichera :
- L'URL HTTPS publique (ex: `https://abc123.ngrok.io`)
- L'interface web sur http://localhost:4040

## 🎁 Avantages du compte ngrok gratuit

- ✅ URL HTTPS permanente (avec domaine personnalisé)
- ✅ Jusqu'à 1 tunnel simultané
- ✅ 40 connexions/minute
- ✅ Interface web de monitoring

---

## 🔄 Alternative : Utiliser cloudflared (gratuit, sans compte)

Si tu ne veux pas créer de compte, utilise **cloudflared** (Cloudflare Tunnel) :

### Installation cloudflared

```powershell
# Télécharger cloudflared
Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile "cloudflared.exe"
```

### Utilisation

```powershell
.\cloudflared.exe tunnel --url http://localhost:8080
```

cloudflared génère automatiquement une URL HTTPS sans compte requis !





