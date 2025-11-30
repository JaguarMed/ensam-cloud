# ENSAM Cloud Platform - Configuration HTTPS
# Génère un certificat SSL auto-signé pour le développement

Write-Host "🔒 Configuration HTTPS pour ENSAM Cloud Platform" -ForegroundColor Cyan
Write-Host ""

# Créer le dossier ssl s'il n'existe pas
$sslDir = "ssl"
if (-not (Test-Path $sslDir)) {
    New-Item -ItemType Directory -Path $sslDir | Out-Null
    Write-Host "✅ Dossier ssl créé" -ForegroundColor Green
}

# Vérifier si OpenSSL est disponible
$opensslAvailable = $false
try {
    $opensslVersion = openssl version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $opensslAvailable = $true
        Write-Host "✅ OpenSSL détecté" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️  OpenSSL non trouvé" -ForegroundColor Yellow
}

# Obtenir l'IP publique et locale
try {
    $publicIP = Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 5
    Write-Host "📍 IP publique: $publicIP" -ForegroundColor Cyan
} catch {
    $publicIP = "localhost"
    Write-Host "⚠️  Impossible de récupérer l'IP publique" -ForegroundColor Yellow
}

$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*"}).IPAddress | Select-Object -First 1
if ($localIP) {
    Write-Host "📍 IP locale: $localIP" -ForegroundColor Cyan
}

# Générer le certificat SSL
$certPath = "$sslDir\cert.pem"
$keyPath = "$sslDir\key.pem"

if ($opensslAvailable) {
    Write-Host ""
    Write-Host "🔐 Génération du certificat SSL auto-signé..." -ForegroundColor Yellow
    
    # Créer un fichier de configuration OpenSSL
    $opensslConfig = @"
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = MA
ST = Rabat
L = Rabat
O = ENSAM
CN = $publicIP

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
IP.1 = $publicIP
IP.2 = $localIP
IP.3 = 127.0.0.1
DNS.1 = localhost
"@
    
    $opensslConfig | Out-File -FilePath "$sslDir\openssl.conf" -Encoding ASCII
    
    # Générer la clé privée
    openssl genrsa -out $keyPath 2048 2>&1 | Out-Null
    
    # Générer le certificat
    openssl req -new -x509 -key $keyPath -out $certPath -days 365 -config "$sslDir\openssl.conf" -extensions v3_req 2>&1 | Out-Null
    
    if (Test-Path $certPath -and Test-Path $keyPath) {
        Write-Host "✅ Certificat SSL généré avec succès" -ForegroundColor Green
        Write-Host "   Certificat: $certPath" -ForegroundColor Gray
        Write-Host "   Clé: $keyPath" -ForegroundColor Gray
    } else {
        Write-Host "❌ Erreur lors de la génération du certificat" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "⚠️  OpenSSL n'est pas installé" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Cyan
    Write-Host "1. Installer OpenSSL pour Windows:" -ForegroundColor White
    Write-Host "   https://slproweb.com/products/Win32OpenSSL.html" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Utiliser un service de tunnel HTTPS (recommandé pour dev):" -ForegroundColor White
    Write-Host "   - ngrok: https://ngrok.com/" -ForegroundColor Gray
    Write-Host "   - cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Utiliser Docker avec nginx (déjà configuré)" -ForegroundColor White
    exit 0
}

Write-Host ""
Write-Host "📝 Prochaines étapes:" -ForegroundColor Yellow
Write-Host "1. Mettre à jour le fichier .env avec les chemins SSL" -ForegroundColor White
Write-Host "2. Lancer le serveur avec HTTPS" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Note: Ce certificat est auto-signé. Les navigateurs afficheront un avertissement." -ForegroundColor Yellow
Write-Host "   Pour la production, utilisez Let's Encrypt avec un nom de domaine." -ForegroundColor Yellow





