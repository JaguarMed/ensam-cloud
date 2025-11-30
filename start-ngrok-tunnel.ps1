# Démarrer ngrok dans une nouvelle fenêtre PowerShell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Cloud; Write-Host '🌐 Tunnel ngrok HTTPS' -ForegroundColor Cyan; Write-Host ''; Write-Host 'URL sera disponible sur: http://localhost:4040' -ForegroundColor Yellow; Write-Host ''; .\ngrok.exe http 8080"





