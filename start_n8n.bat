@echo off
title n8n Local Server
cd /d "%~dp0"
cls

echo ===================================================================
echo   Starting n8n Locally (Direct Node.js Engine)
echo   Connecting to Neon Cloud PostgreSQL Database...
echo ===================================================================
echo.

:: 1. Database Configuration (Neon Cloud PostgreSQL)
set DB_TYPE=postgresdb
set DB_POSTGRESDB_HOST=ep-lucky-king-ae1cagq7-pooler.c-2.us-east-2.aws.neon.tech
set DB_POSTGRESDB_PORT=5432
set DB_POSTGRESDB_DATABASE=neondb
set DB_POSTGRESDB_USER=neondb_owner
set DB_POSTGRESDB_PASSWORD=npg_IrDieSFX6Z7Q
set DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED=false
set DB_POSTGRESDB_POOL_SIZE=10
set DB_POSTGRESDB_CONNECTION_TIMEOUT=60000

:: 2. Instance & Security Settings
set N8N_ENCRYPTION_KEY=n8n-render-secret-key-328b555-production
set N8N_PORT=5678
set N8N_HOST=localhost
set N8N_LISTEN_ADDRESS=0.0.0.0
set WEBHOOK_URL=http://localhost:5678/
set N8N_WEBHOOK_URL=http://localhost:5678/
set N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=false
set N8N_VERSION_NOTIFICATIONS_ENABLED=false
set N8N_DIAGNOSTICS_ENABLED=false

echo -------------------------------------------------------------------
echo  * Local Dashboard:  http://localhost:5678
echo  * Database:         Neon Cloud PostgreSQL (All workflows preserved)
echo -------------------------------------------------------------------
echo.
echo Launching n8n engine and opening browser...
echo.

where n8n >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    call n8n start --open
) else (
    where npx >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        call npx -y n8n start --open
    ) else (
        where pnpm >nul 2>nul
        if %ERRORLEVEL% EQU 0 (
            call pnpm dlx n8n start --open
        ) else (
            echo [ERROR] Neither n8n, npx, nor pnpm was found in PATH.
            pause
            exit /b 1
        )
    )
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] n8n exited with error code %ERRORLEVEL%.
    pause
)
