@echo off
chcp 65001 >nul 2>&1
REM seed.bat — Cria tenant inicial e usuário admin no Windows
REM Uso: scripts\seed.bat
REM    ou: scripts\seed.bat "Nome da Empresa" "slug-unico" "admin@email.com" "senha-forte"

setlocal enabledelayedexpansion

echo ═══ Seed Inicial — VMS MVP ═══
echo.

REM Verifica se Docker está rodando
docker compose ps api >nul 2>&1
if errorlevel 1 (
    echo ERRO: Docker Compose não disponível.
    echo Execute: docker compose up -d --build
    pause
    exit /b 1
)

REM Parâmetros com defaults
set "TENANT_NAME=%~1"
set "TENANT_SLUG=%~2"
set "ADMIN_EMAIL=%~3"
set "ADMIN_PASSWORD=%~4"

if "%TENANT_NAME%"=="" set "TENANT_NAME=Ops Solutions"
if "%TENANT_SLUG%"=="" set "TENANT_SLUG=ops-solutions"
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@vms.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

echo Tenant:     %TENANT_NAME% (%TENANT_SLUG%)
echo Admin:      %ADMIN_EMAIL%
echo Senha:      %ADMIN_PASSWORD%
echo.

REM Executa dentro do container
docker compose exec api python -m vms.scripts.create_tenant ^
    --name "%TENANT_NAME%" ^
    --slug "%TENANT_SLUG%" ^
    --admin-email "%ADMIN_EMAIL%" ^
    --admin-password "%ADMIN_PASSWORD%"

if errorlevel 1 (
    echo.
    echo ═══ Seed falhou ═══
    echo Possível causa: tenant já existe ^(slug duplicado^).
    pause
    exit /b 1
)

echo.
echo ═══ Seed concluído com sucesso! ═══
echo.
echo Faça login com:
echo   Email: %ADMIN_EMAIL%
echo   Senha: %ADMIN_PASSWORD%
echo.
pause
