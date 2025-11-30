# 🔒 Status HTTPS - ENSAM Cloud Platform

## ✅ Configuration HTTPS activée

Le serveur est configuré avec HTTPS via cloudflared.

### 📊 État actuel

- **Serveur HTTP** : `http://localhost:8080` ✅
- **Tunnel HTTPS** : cloudflared ✅
- **Image GPU** : `nvidia/cuda:12.0.0-devel-ubuntu22.04` ✅

### 🌐 Obtenir l'URL HTTPS

Pour voir l'URL HTTPS publique générée par cloudflared :

1. **Option 1 - Script automatique** :
   ```powershell
   .\start-https.ps1
   ```
   Le script affichera l'URL HTTPS dans la sortie.

2. **Option 2 - Manuel** :
   ```powershell
   # Dans un terminal séparé
   .\cloudflared.exe tunnel --url http://localhost:8080
   ```
   L'URL HTTPS s'affichera (format : `https://xxxxx.trycloudflare.com`)

### 📌 URLs d'accès

- **Local HTTP** : `http://localhost:8080`
- **HTTPS public** : Voir ci-dessus (généré par cloudflared)

### ⚠️ Notes importantes

- L'URL HTTPS cloudflared change à chaque redémarrage
- L'URL est accessible depuis Internet avec HTTPS automatique
- Aucun compte cloudflare requis pour les tests
- Pour une URL permanente, configurez un tunnel nommé cloudflare

### 🛑 Arrêter les services

```powershell
Get-Process python,cloudflared | Stop-Process -Force
```

### 🔄 Redémarrer

```powershell
.\start-https.ps1
```




