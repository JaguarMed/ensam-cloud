# ENSAM Cloud Platform - Démarrage avec HTTPS
# Lance le serveur avec SSL/TLS pour un accès sécurisé

Write-Host "🔒 Démarrage de ENSAM Cloud Platform avec HTTPS..." -ForegroundColor Cyan
Write-Host ""

# Vérifier que les certificats SSL existent
$certPath = "ssl\cert.pem"
$keyPath = "ssl\key.pem"

if (-not (Test-Path $certPath) -or -not (Test-Path $keyPath)) {
    Write-Host "❌ Certificats SSL non trouvés" -ForegroundColor Red
    Write-Host ""
    Write-Host "Exécutez d'abord:" -ForegroundColor Yellow
    Write-Host "  .\setup-https.ps1" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✅ Certificats SSL trouvés" -ForegroundColor Green

# Obtenir l'IP publique
try {
    $publicIP = Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 5
    Write-Host "🌐 IP publique: $publicIP" -ForegroundColor Cyan
} catch {
    $publicIP = "localhost"
}

$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*"}).IPAddress | Select-Object -First 1

Write-Host ""
Write-Host "📌 URLs d'accès HTTPS:" -ForegroundColor Yellow
Write-Host "   - Local:      https://localhost:8443" -ForegroundColor White
if ($localIP) {
    Write-Host "   - Réseau:     https://$localIP:8443" -ForegroundColor White
}
Write-Host "   - Internet:   https://$publicIP:8443" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Note: Le navigateur affichera un avertissement car le certificat est auto-signé." -ForegroundColor Yellow
Write-Host "   Cliquez sur 'Avancé' puis 'Continuer vers le site' pour accéder." -ForegroundColor Yellow
Write-Host ""

# Vérifier le pare-feu pour le port 8443
$firewallRule = Get-NetFirewallRule -DisplayName "ENSAM Cloud Platform HTTPS" -ErrorAction SilentlyContinue
if (-not $firewallRule) {
    Write-Host "🔧 Configuration du pare-feu pour le port 8443..." -ForegroundColor Yellow
    try {
        New-NetFirewallRule -DisplayName "ENSAM Cloud Platform HTTPS" -Direction Inbound -LocalPort 8443 -Protocol TCP -Action Allow | Out-Null
        Write-Host "✅ Pare-feu configuré" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Impossible de configurer le pare-feu (nécessite les droits admin)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "🔧 Configuration:" -ForegroundColor Yellow
Write-Host "   - Host: 0.0.0.0 (accepte toutes les connexions)" -ForegroundColor White
Write-Host "   - Port: 8443 (HTTPS)" -ForegroundColor White
Write-Host "   - SSL: Activé" -ForegroundColor White
Write-Host "   - Mode: Reload (redémarre automatiquement)" -ForegroundColor White
Write-Host ""
Write-Host "▶️  Démarrage du serveur HTTPS..." -ForegroundColor Cyan
Write-Host "   Appuyez sur Ctrl+C pour arrêter" -ForegroundColor Gray
Write-Host ""

# Lancer le serveur avec HTTPS
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8443 --ssl-keyfile $keyPath --ssl-certfile $certPath





