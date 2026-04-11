@echo off
chcp 65001 >nul 2>&1
REM add_cameras.bat — Adiciona câmeras em lote via API
REM Uso: scripts\add_cameras.bat

setlocal enabledelayedexpansion

echo ═══ Adicionar Câmeras em Lote ═══
echo.

REM Verifica se API está rodando
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ERRO: API não está respondendo em http://localhost:8000
    echo Execute: docker compose up -d
    pause
    exit /b 1
)

echo Obter token de autenticação...
echo.

REM Fazer login para obter token
for /f "tokens=*" %%i in ('curl -s -X POST http://localhost:8000/api/v1/auth/login ^
    -H "Content-Type: application/json" ^
    -d "{\"email\":\"admin@vms.com\",\"password\":\"admin123\"}" ^
    ^| python -c "import sys, json; print(json.load(sys.stdin).get('access_token',''))" 2^>nul') do set TOKEN=%%i

if "%TOKEN%"=="" (
    echo ERRO: Falha ao obter token. Verifique credenciais.
    echo Execute primeiro: scripts\seed.bat
    pause
    exit /b 1
)

echo Token obtido com sucesso!
echo.

REM Configuração das câmeras
REM Formato: NOME|PROTOCOLO|URL_RTSP_OU_RTMP|LOCALIZACAO

echo Adicionando câmeras...
echo.

set API_URL=http://localhost:8000
set AUTH_HEADER=Authorization: Bearer %TOKEN%

REM Câmeras RTSP - Intelbras
curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-01\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite123@45.236.226.70:6044/cam/realmonitor?channel=1^&subtype=0\",\"location\":\"Externo - Entrada Principal\"}" >nul

echo ✓ Intelbras-01 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-02\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite123@45.236.226.70:6045/cam/realmonitor?channel=1^&subtype=0\",\"location\":\"Externo - Estacionamento\"}" >nul

echo ✓ Intelbras-02 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-03\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite123@45.236.226.71:6046/cam/realmonitor?channel=1^&subtype=0\",\"location\":\"Externo - Portão\"}" >nul

echo ✓ Intelbras-03 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-04\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite123@45.236.226.71:6047/cam/realmonitor?channel=1^&subtype=0\",\"location\":\"Interno - Recepção\"}" >nul

echo ✓ Intelbras-04 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-05\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite123@45.236.226.72:6048/cam/realmonitor?channel=1^&subtype=0\",\"location\":\"Interno - Corredor A\"}" >nul

echo ✓ Intelbras-05 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-06\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite123@45.236.226.72:6049/cam/realmonitor?channel=1^&subtype=0\",\"location\":\"Interno - Corredor B\"}" >nul

echo ✓ Intelbras-06 adicionada

REM Câmeras RTMP - Intelbras
curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-RTMP-01\",\"stream_protocol\":\"rtmp_push\",\"rtmp_stream_key\":\"7KOM27155085F\",\"location\":\"Remoto - Filial 1\"}" >nul

echo ✓ Intelbras-RTMP-01 adicionada (RTMP push)

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-RTMP-02\",\"stream_protocol\":\"rtmp_push\",\"rtmp_stream_key\":\"7KOM2715585AK\",\"location\":\"Remoto - Filial 2\"}" >nul

echo ✓ Intelbras-RTMP-02 adicionada (RTMP push)

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Intelbras-RTMP-03\",\"stream_protocol\":\"rtmp_push\",\"rtmp_stream_key\":\"7KOM2715805PF\",\"location\":\"Remoto - Filial 3\"}" >nul

echo ✓ Intelbras-RTMP-03 adicionada (RTMP push)

REM Câmeras Hikvision
curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Hikvision-01\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite@170.84.217.71:608/h264/ch1/main/av_stream\",\"location\":\"Externo - Rua A\"}" >nul

echo ✓ Hikvision-01 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Hikvision-02\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite@170.84.217.83:608/h264/ch1/main/av_stream\",\"location\":\"Externo - Rua B\"}" >nul

echo ✓ Hikvision-02 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Hikvision-03\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite@170.84.217.84:603/h264/ch1/main/av_stream\",\"location\":\"Interno - Sala Cofre\"}" >nul

echo ✓ Hikvision-03 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Hikvision-04\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite@186.226.193.111:600/h264/ch1/main/av_stream\",\"location\":\"Externo - Entrada Norte\"}" >nul

echo ✓ Hikvision-04 adicionada

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Hikvision-05\",\"stream_protocol\":\"rtsp_pull\",\"rtsp_url\":\"rtsp://admin:Camerite@186.226.193.111:601/h264/ch1/main/av_stream\",\"location\":\"Externo - Entrada Sul\"}" >nul

echo ✓ Hikvision-05 adicionada

REM RTMP Hikvision
curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Hikvision-RTMP-01\",\"stream_protocol\":\"rtmp_push\",\"rtmp_stream_key\":\"FC2487237\",\"location\":\"Remoto - Matriz\"}" >nul

echo ✓ Hikvision-RTMP-01 adicionada (RTMP push)

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Hikvision-RTMP-02\",\"stream_protocol\":\"rtmp_push\",\"rtmp_stream_key\":\"FC2487838\",\"location\":\"Remoto - Filial Norte\"}" >nul

echo ✓ Hikvision-RTMP-02 adicionada (RTMP push)

curl -s -X POST %API_URL%/api/v1/cameras ^
    -H "%AUTH_HEADER%" ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Hikvision-RTMP-03\",\"stream_protocol\":\"rtmp_push\",\"rtmp_stream_key\":\"FC2487653\",\"location\":\"Remoto - Filial Sul\"}" >nul

echo ✓ Hikvision-RTMP-03 adicionada (RTMP push)

echo.
echo ════════════════════════════════════════════════
echo ✓ Todas as 17 câmeras foram adicionadas!
echo ════════════════════════════════════════════════
echo.
echo Acesse http://localhost:5173/cameras para visualizar
echo.
pause
