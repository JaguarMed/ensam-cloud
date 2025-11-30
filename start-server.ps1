# ENSAM Cloud Platform - Script de démarrage
# Lance le serveur avec la configuration optimale pour l'accès Internet

Write-Host "🚀 Démarrage de ENSAM Cloud Platform..." -ForegroundColor Cyan
Write-Host ""

# Vérifier que Python est installé
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python détecté: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python n'est pas installé ou pas dans le PATH" -ForegroundColor Red
    exit 1
}

# Vérifier que le fichier .env existe
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  Fichier .env non trouvé, copie depuis env.example..." -ForegroundColor Yellow
    Copy-Item env.example .env
    Write-Host "✅ Fichier .env créé" -ForegroundColor Green
}

# Vérifier la configuration CORS
$corsConfig = Get-Content .env | Select-String "CORS_ORIGINS"
if ($corsConfig -match "CORS_ORIGINS=\*") {
    Write-Host "✅ CORS configuré pour accepter toutes les origines" -ForegroundColor Green
} else {
    Write-Host "⚠️  CORS peut nécessiter une configuration supplémentaire" -ForegroundColor Yellow
}

# Obtenir l'IP locale
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*"}).IPAddress | Select-Object -First 1
if ($localIP) {
    Write-Host "📍 IP locale: $localIP" -ForegroundColor Cyan
}

# Obtenir l'IP publique
try {
    $publicIP = Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 5
    Write-Host "🌐 IP publique: $publicIP" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📌 URLs d'accès:" -ForegroundColor Yellow
    Write-Host "   - Local:      http://localhost:8080" -ForegroundColor White
    Write-Host "   - Réseau:     http://$localIP:8080" -ForegroundColor White
    Write-Host "   - Internet:   http://$publicIP:8080" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "⚠️  Impossible de récupérer l'IP publique" -ForegroundColor Yellow
}

# Vérifier le pare-feu
$firewallRule = Get-NetFirewallRule -DisplayName "ENSAM Cloud Platform" -ErrorAction SilentlyContinue
if ($firewallRule) {
    Write-Host "✅ Pare-feu Windows configuré" -ForegroundColor Green
} else {
    Write-Host "⚠️  Règle de pare-feu non trouvée, création..." -ForegroundColor Yellow
    try {
        New-NetFirewallRule -DisplayName "ENSAM Cloud Platform" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow | Out-Null
        Write-Host "✅ Règle de pare-feu créée" -ForegroundColor Green
    } catch {
        Write-Host "❌ Impossible de créer la règle de pare-feu (nécessite les droits admin)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "🔧 Configuration:" -ForegroundColor Yellow
Write-Host "   - Host: 0.0.0.0 (accepte toutes les connexions)" -ForegroundColor White
Write-Host "   - Port: 8080" -ForegroundColor White
Write-Host "   - Mode: Reload (redémarre automatiquement sur changement)" -ForegroundColor White
Write-Host ""
Write-Host "▶️  Démarrage du serveur..." -ForegroundColor Cyan
Write-Host "   Appuyez sur Ctrl+C pour arrêter" -ForegroundColor Gray
Write-Host ""

# Lancer le serveur
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8080





