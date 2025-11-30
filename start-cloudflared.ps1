# ENSAM Cloud Platform - Tunnel HTTPS avec cloudflared
# Alternative à ngrok, gratuit et sans compte requis

Write-Host "🌐 Configuration du tunnel HTTPS avec cloudflared..." -ForegroundColor Cyan
Write-Host ""

# Vérifier si cloudflared existe
if (-not (Test-Path ".\cloudflared.exe")) {
    Write-Host "📥 Téléchargement de cloudflared..." -ForegroundColor Yellow
    
    try {
        $latestUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        Invoke-WebRequest -Uri $latestUrl -OutFile "cloudflared.exe" -UseBasicParsing
        Write-Host "✅ cloudflared téléchargé" -ForegroundColor Green
    } catch {
        Write-Host "❌ Erreur lors du téléchargement" -ForegroundColor Red
        Write-Host "   Téléchargez manuellement: https://github.com/cloudflare/cloudflared/releases" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "✅ cloudflared disponible" -ForegroundColor Green

# Vérifier que le serveur tourne
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
Write-Host "🔧 Configuration:" -ForegroundColor Yellow
Write-Host "   - Port local: 8080" -ForegroundColor White
Write-Host "   - Protocole: HTTPS" -ForegroundColor White
Write-Host "   - Compte requis: NON ✅" -ForegroundColor Green
Write-Host ""

Write-Host "▶️  Démarrage du tunnel cloudflared..." -ForegroundColor Cyan
Write-Host "   Appuyez sur Ctrl+C pour arrêter" -ForegroundColor Gray
Write-Host ""
Write-Host "📌 Une URL HTTPS sera générée automatiquement" -ForegroundColor Yellow
Write-Host "   Partagez cette URL pour accéder à la plateforme depuis Internet" -ForegroundColor Yellow
Write-Host ""

# Lancer cloudflared
.\cloudflared.exe tunnel --url http://localhost:8080





