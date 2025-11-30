# Script d'urgence pour arrêter tous les jobs et libérer les ressources

Write-Host "🛑 Arrêt d'urgence de tous les jobs..." -ForegroundColor Red
Write-Host ""

# Arrêter tous les processus Python
Write-Host "1. Arrêt des processus Python..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "   ✅ Processus Python arrêtés" -ForegroundColor Green

# Arrêter tous les conteneurs ensam-job
Write-Host ""
Write-Host "2. Arrêt de tous les conteneurs ensam-job..." -ForegroundColor Yellow
$containers = docker ps -a --filter "name=ensam-job" --format "{{.ID}} {{.Names}}"
if ($containers) {
    $containers | ForEach-Object {
        $id = ($_ -split ' ')[0]
        $name = ($_ -split ' ', 2)[1]
        Write-Host "   Arrêt de $name ($id)..." -ForegroundColor Gray
        docker kill $id 2>$null
        docker rm -f $id 2>$null
    }
    Write-Host "   ✅ Conteneurs arrêtés et supprimés" -ForegroundColor Green
} else {
    Write-Host "   ℹ️  Aucun conteneur ensam-job trouvé" -ForegroundColor Gray
}

# Arrêter tous les autres conteneurs en cours d'exécution
Write-Host ""
Write-Host "3. Vérification des autres conteneurs..." -ForegroundColor Yellow
$running = docker ps -q
if ($running) {
    Write-Host "   ⚠️  Conteneurs en cours d'exécution détectés" -ForegroundColor Yellow
    docker ps --format "   - {{.Names}} ({{.ID}})"
    $stop = Read-Host "   Arrêter tous les conteneurs? (o/N)"
    if ($stop -eq "o" -or $stop -eq "O") {
        docker stop $(docker ps -q) 2>$null
        Write-Host "   ✅ Tous les conteneurs arrêtés" -ForegroundColor Green
    }
} else {
    Write-Host "   ✅ Aucun conteneur en cours d'exécution" -ForegroundColor Green
}

Write-Host ""
Write-Host "✅ Nettoyage terminé" -ForegroundColor Green
Write-Host ""




