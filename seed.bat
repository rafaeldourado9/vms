@echo off
chcp 65001 >nul 2>&1
REM seed.bat — Cria tenant + admin + license key ativada.
REM
REM Uso (a partir da raiz do projeto):
REM   seed.bat
REM   seed.bat --name "Acme" --slug acme --email admin@acme.com --password senha123
REM   seed.bat --model self_hosted --cameras 10 --days 730

set "ROOT=%~dp0"
set "SEED_PY=%ROOT%api\src\vms\scripts\seed.py"

if not exist "%SEED_PY%" (
    echo ERRO: %SEED_PY% nao encontrado.
    exit /b 1
)

docker compose ps api >nul 2>&1
if errorlevel 1 (
    echo ERRO: Docker Compose nao disponivel. Execute: docker compose up -d --build
    exit /b 1
)

REM Copia o modulo pro container (caso a imagem seja mais antiga que o arquivo)
docker compose cp "%SEED_PY%" api:/app/src/vms/scripts/seed.py >nul

docker compose exec api python -m vms.scripts.seed %*
