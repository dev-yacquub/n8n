# Start n8n locally without Docker, connecting to Neon PostgreSQL
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "  Starting n8n Locally (Direct Node.js Engine)" -ForegroundColor Green
Write-Host "  Connecting to your Neon Cloud PostgreSQL Database..." -ForegroundColor Yellow
Write-Host "===================================================================" -ForegroundColor Cyan

# Neon Cloud PostgreSQL Configuration
$env:DB_TYPE = "postgresdb"
$env:DB_POSTGRESDB_HOST = "ep-lucky-king-ae1cagq7-pooler.c-2.us-east-2.aws.neon.tech"
$env:DB_POSTGRESDB_PORT = "5432"
$env:DB_POSTGRESDB_DATABASE = "neondb"
$env:DB_POSTGRESDB_USER = "neondb_owner"
$env:DB_POSTGRESDB_PASSWORD = "npg_IrDieSFX6Z7Q"
$env:DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED = "false"
$env:DB_POSTGRESDB_POOL_SIZE = "10"
$env:DB_POSTGRESDB_CONNECTION_TIMEOUT = "60000"

# Security, Port & Permissions
$env:N8N_ENCRYPTION_KEY = "n8n-render-secret-key-328b555-production"
$env:N8N_PORT = "5678"
$env:N8N_HOST = "localhost"
$env:N8N_LISTEN_ADDRESS = "0.0.0.0"
$env:WEBHOOK_URL = "http://localhost:5678/"
$env:N8N_WEBHOOK_URL = "http://localhost:5678/"
$env:N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS = "false"
$env:N8N_VERSION_NOTIFICATIONS_ENABLED = "false"
$env:N8N_DIAGNOSTICS_ENABLED = "false"

Write-Host "`n-------------------------------------------------------------------" -ForegroundColor Gray
Write-Host " * Local Dashboard:  http://localhost:5678" -ForegroundColor Cyan
Write-Host " * Database:         Neon Cloud PostgreSQL (All workflows preserved!)" -ForegroundColor Green
Write-Host "-------------------------------------------------------------------`n" -ForegroundColor Gray

if (Get-Command n8n -ErrorAction SilentlyContinue) {
    n8n start --open
} elseif (Get-Command npx -ErrorAction SilentlyContinue) {
    npx -y n8n start --open
} elseif (Get-Command pnpm -ErrorAction SilentlyContinue) {
    pnpm dlx n8n start --open
} else {
    Write-Host "[ERROR] Neither n8n, npx, nor pnpm found." -ForegroundColor Red
}
