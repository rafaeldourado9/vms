@echo off
REM Inicia stack VMS com túnel Cloudflare para desenvolvimento
REM Uso: ./dev-tunnel.bat
REM Após iniciar, copie a URL https://xxxx.trycloudflare.com para as câmeras

echo ========================================
echo   VMS Dev Stack + Cloudflare Tunnel
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/2] Iniciando stack...
docker compose --profile dev up -d

echo [2/2] Aguardando túnel subir (15s)...
timeout /t 15 /nobreak >nul

echo.
echo ========================================
echo   URLs do túnel (veja os logs abaixo):
echo ========================================
docker compose --profile dev logs cloudflared 2>nul | findstr "trycloudflare"

echo.
echo Para ver a URL do túnel a qualquer momento:
echo   docker compose --profile dev logs cloudflared ^| findstr trycloudflare
echo.
echo Webhooks:
echo   Hikvision:  https://SEU-TUNEL.trycloudflare.com/hik_pro_connect?camera_id=UUID
echo   Intelbras:  https://SEU-TUNEL.trycloudflare.com/intelbras_events?camera_id=UUID
echo.

pause
