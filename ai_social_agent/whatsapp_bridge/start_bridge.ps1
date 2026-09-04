# Start WhatsApp Linked Device Bridge Service
$BridgeDir = "d:\zdiiv\N8N\ai_social_agent\whatsapp_bridge"
Set-Location $BridgeDir

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing WhatsApp bridge dependencies..." -ForegroundColor Cyan
    npm install
}

Write-Host "Starting WhatsApp Linked Device Bridge on port 3001..." -ForegroundColor Green
node index.js
