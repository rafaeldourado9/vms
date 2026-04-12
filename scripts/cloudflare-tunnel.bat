@echo off
REM Túnel Cloudflare para desenvolvimento local VMS
REM Expõe API (8000) e Frontend (5173/dev ou 80/prod) para webhooks externos

echo ========================================
echo   VMS - Cloudflare Tunnel
echo ========================================
echo.

REM Porta da API local
set API_PORT=8000

echo [1/3] Iniciando tunel para API (porta %API_PORT%)...
echo [2/3] URLs dos webhooks:
echo   - Hikvision:  https://SEU-TUNEL.trycloudflare.com/hik_pro_connect?camera_id=UUID
echo   - Intelbras:  https://SEU-TUNEL.trycloudflare.com/intelbras_events?camera_id=UUID
echo   - Eventos:    https://SEU-TUNEL.trycloudflare.com/api/v1/webhooks/...
echo.
echo [3/3] Aguarde a URL ser gerada abaixo...
echo.

cloudflared tunnel --url http://localhost:%API_PORT% --protocol http2
