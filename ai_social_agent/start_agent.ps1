# Launch script for SocialCommander AI Bot
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting SocialCommander AI (Telegram Control Center)  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$env:PYTHONIOENCODING = "utf-8"
Set-Location "d:\zdiiv\N8N\ai_social_agent"

python main.py
