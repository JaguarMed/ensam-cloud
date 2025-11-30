# ENSAM Cloud Platform - Démarrage complet avec HTTPS
# Démarre le serveur HTTP et le tunnel HTTPS cloudflared

Write-Host ""
Write-Host "🔒 ENSAM Cloud Platform - Configuration HTTPS" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# Arrêter les processus existants
Write-Host "🛑 Arrêt des processus existants..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Vérifier cloudflared
if (-not (Test-Path ".\cloudflared.exe")) {
    Write-Host "❌ cloudflared.exe non trouvé" -ForegroundColor Red
    Write-Host "   Téléchargez-le depuis: https://github.com/cloudflare/cloudflared/releases" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ cloudflared disponible" -ForegroundColor Green
Write-Host ""

# Démarrer le serveur HTTP
Write-Host "▶️  Démarrage du serveur HTTP (port 8080)..." -ForegroundColor Cyan
$serverProcess = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "src.main:app", "--reload", "--host", "0.0.0.0", "--port", "8080" -PassThru -WindowStyle Hidden

# Attendre que le serveur démarre
Write-Host "⏳ Attente du démarrage du serveur..." -ForegroundColor Yellow
$maxAttempts = 10
$attempt = 0
$serverReady = $false

while ($attempt -lt $maxAttempts -and -not $serverReady) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8080/health" -TimeoutSec 1 -ErrorAction Stop
        $serverReady = $true
        Write-Host "✅ Serveur HTTP démarré et prêt" -ForegroundColor Green
    } catch {
        $attempt++
        Write-Host "." -NoNewline -ForegroundColor Gray
    }
}

if (-not $serverReady) {
    Write-Host ""
    Write-Host "⚠️  Le serveur ne répond pas, mais on continue..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🌐 Démarrage du tunnel HTTPS cloudflared..." -ForegroundColor Cyan
Write-Host ""
Write-Host "📌 L'URL HTTPS sera affichée ci-dessous" -ForegroundColor Yellow
Write-Host "   Cette URL est accessible depuis Internet avec HTTPS" -ForegroundColor Yellow
Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# Démarrer cloudflared et capturer l'URL
Write-Host "🔍 Recherche de l'URL HTTPS..." -ForegroundColor Cyan
Write-Host ""

# Démarrer cloudflared en arrière-plan et capturer la sortie
$cloudflaredJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    $output = .\cloudflared.exe tunnel --url http://localhost:8080 2>&1 | Out-String
    return $output
}

# Attendre un peu pour que cloudflared génère l'URL
Start-Sleep -Seconds 8

# Essayer de récupérer l'URL depuis la sortie
$output = Receive-Job -Job $cloudflaredJob -ErrorAction SilentlyContinue
if ($output) {
    # Chercher l'URL dans la sortie
    if ($output -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
        $httpsUrl = $matches[0]
        Write-Host ""
        Write-Host "=" * 60 -ForegroundColor Green
        Write-Host "✅ URL HTTPS générée avec succès!" -ForegroundColor Green
        Write-Host ""
        Write-Host "🌐 URL HTTPS publique:" -ForegroundColor Cyan
        Write-Host "   $httpsUrl" -ForegroundColor White -BackgroundColor DarkGreen
        Write-Host ""
        Write-Host "📌 Cette URL est accessible depuis Internet" -ForegroundColor Yellow
        Write-Host "   Partagez cette URL pour accéder à la plateforme" -ForegroundColor Yellow
        Write-Host "=" * 60 -ForegroundColor Green
        Write-Host ""
    }
}

# Afficher la sortie complète de cloudflared
Write-Host "📋 Sortie de cloudflared:" -ForegroundColor Cyan
Write-Host $output
Write-Host ""
Write-Host "💡 Pour voir l'URL en temps réel, exécutez dans un autre terminal:" -ForegroundColor Yellow
Write-Host "   .\cloudflared.exe tunnel --url http://localhost:8080" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Appuyez sur Ctrl+C pour arrêter" -ForegroundColor Gray

# Attendre que cloudflared continue
Wait-Job -Job $cloudflaredJob

