# ENSAM Cloud Platform - Tunnel HTTPS avec ngrok
# Solution rapide pour accès HTTPS sans configuration SSL

Write-Host "🌐 Configuration du tunnel HTTPS avec ngrok..." -ForegroundColor Cyan
Write-Host ""

# Vérifier si ngrok est installé
$ngrokPath = Get-Command ngrok -ErrorAction SilentlyContinue

if (-not $ngrokPath) {
    Write-Host "❌ ngrok n'est pas installé" -ForegroundColor Red
    Write-Host ""
    Write-Host "📥 Installation:" -ForegroundColor Yellow
    Write-Host "1. Télécharger ngrok: https://ngrok.com/download" -ForegroundColor White
    Write-Host "2. Extraire ngrok.exe dans un dossier du PATH" -ForegroundColor White
    Write-Host "3. Ou placer ngrok.exe dans ce dossier (C:\Cloud)" -ForegroundColor White
    Write-Host ""
    Write-Host "Alternative: Utiliser Chocolatey" -ForegroundColor Yellow
    Write-Host "  choco install ngrok" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✅ ngrok détecté" -ForegroundColor Green

# Vérifier que le serveur tourne sur le port 8080
$serverRunning = netstat -an | findstr ":8080.*LISTENING"
if (-not $serverRunning) {
    Write-Host "⚠️  Le serveur ne semble pas tourner sur le port 8080" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Démarrez d'abord le serveur dans un autre terminal:" -ForegroundColor Yellow
    Write-Host "  python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8080" -ForegroundColor White
    Write-Host ""
    Write-Host "Ou utilisez:" -ForegroundColor Yellow
    Write-Host "  .\start-server.ps1" -ForegroundColor White
    Write-Host ""
    
    $continue = Read-Host "Continuer quand même? (o/N)"
    if ($continue -ne "o" -and $continue -ne "O") {
        exit 0
    }
}

Write-Host ""
Write-Host "🔧 Configuration ngrok:" -ForegroundColor Yellow
Write-Host "   - Port local: 8080" -ForegroundColor White
Write-Host "   - Protocole: HTTPS" -ForegroundColor White
Write-Host ""

# Vérifier si ngrok est authentifié
$ngrokConfig = "$env:USERPROFILE\.ngrok2\ngrok.yml"
if (-not (Test-Path $ngrokConfig)) {
    Write-Host "⚠️  ngrok n'est pas authentifié" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Pour obtenir une URL permanente:" -ForegroundColor Yellow
    Write-Host "1. Créer un compte sur https://ngrok.com" -ForegroundColor White
    Write-Host "2. Obtenir votre authtoken" -ForegroundColor White
    Write-Host "3. Exécuter: ngrok config add-authtoken <VOTRE_TOKEN>" -ForegroundColor White
    Write-Host ""
    Write-Host "Sans authentification, ngrok fonctionnera mais avec une URL temporaire." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "▶️  Démarrage du tunnel ngrok..." -ForegroundColor Cyan
Write-Host "   Appuyez sur Ctrl+C pour arrêter" -ForegroundColor Gray
Write-Host ""
Write-Host "📌 Une URL HTTPS sera générée (ex: https://abc123.ngrok.io)" -ForegroundColor Yellow
Write-Host "   Partagez cette URL pour accéder à la plateforme depuis Internet" -ForegroundColor Yellow
Write-Host ""

# Lancer ngrok
ngrok http 8080





