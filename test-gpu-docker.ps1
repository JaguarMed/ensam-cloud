# Script de test pour vérifier l'accès GPU dans Docker

Write-Host "🔍 Test d'accès GPU dans Docker" -ForegroundColor Cyan
Write-Host ""

# Test 1: Vérifier nvidia-smi sur l'hôte
Write-Host "1. Vérification nvidia-smi sur l'hôte..." -ForegroundColor Yellow
try {
    $nvidiaSmi = nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ GPU détecté sur l'hôte:" -ForegroundColor Green
        Write-Host "   $nvidiaSmi" -ForegroundColor White
    } else {
        Write-Host "   ❌ nvidia-smi non disponible" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Erreur: $_" -ForegroundColor Red
}

Write-Host ""

# Test 2: Vérifier Docker avec GPU
Write-Host "2. Test Docker avec GPU..." -ForegroundColor Yellow
try {
    $dockerTest = docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi --query-gpu=name --format=csv,noheader 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Docker a accès au GPU:" -ForegroundColor Green
        Write-Host "   $dockerTest" -ForegroundColor White
    } else {
        Write-Host "   ❌ Docker n'a pas accès au GPU" -ForegroundColor Red
        Write-Host "   Erreur: $dockerTest" -ForegroundColor Red
        Write-Host ""
        Write-Host "   💡 Solution: Installez NVIDIA Container Toolkit" -ForegroundColor Yellow
        Write-Host "   https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ❌ Erreur: $_" -ForegroundColor Red
}

Write-Host ""

# Test 3: Vérifier les runtimes Docker
Write-Host "3. Vérification des runtimes Docker..." -ForegroundColor Yellow
try {
    $dockerInfo = docker info --format '{{json .}}' | ConvertFrom-Json
    $runtimes = $dockerInfo.Runtimes
    if ($runtimes.nvidia) {
        Write-Host "   ✅ Runtime NVIDIA disponible" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Runtime NVIDIA non disponible" -ForegroundColor Red
        Write-Host "   Runtimes disponibles: $($runtimes.PSObject.Properties.Name -join ', ')" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ⚠️  Impossible de vérifier les runtimes" -ForegroundColor Yellow
}

Write-Host ""




