# ENSAM Cloud Platform - Démarrage avec HTTPS via cloudflared
# Démarre le serveur HTTP et le tunnel HTTPS cloudflared

Write-Host "🔒 Démarrage de ENSAM Cloud Platform avec HTTPS (cloudflared)..." -ForegroundColor Cyan
Write-Host ""

# Arrêter les processus existants
Write-Host "🛑 Arrêt des processus existants..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Vérifier que cloudflared existe
if (-not (Test-Path ".\cloudflared.exe")) {
    Write-Host "❌ cloudflared.exe non trouvé" -ForegroundColor Red
    Write-Host "   Téléchargez-le depuis: https://github.com/cloudflare/cloudflared/releases" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ cloudflared disponible" -ForegroundColor Green
Write-Host ""

# Démarrer le serveur HTTP en arrière-plan
Write-Host "▶️  Démarrage du serveur HTTP sur le port 8080..." -ForegroundColor Cyan
$serverJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
}

# Attendre que le serveur démarre
Start-Sleep -Seconds 5

# Vérifier que le serveur répond
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8080/health" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✅ Serveur HTTP démarré" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Le serveur ne répond pas encore, mais cloudflared va démarrer..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🌐 Démarrage du tunnel HTTPS cloudflared..." -ForegroundColor Cyan
Write-Host "   Une URL HTTPS sera générée automatiquement" -ForegroundColor Yellow
Write-Host ""
Write-Host "📌 L'URL HTTPS sera affichée ci-dessous" -ForegroundColor Cyan
Write-Host "   Appuyez sur Ctrl+C pour arrêter" -ForegroundColor Gray
Write-Host ""

# Démarrer cloudflared (affiche l'URL dans la sortie)
.\cloudflared.exe tunnel --url http://localhost:8080




