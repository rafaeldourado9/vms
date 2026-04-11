@echo off
REM Testa conectividade com URLs de cameras RTSP/RTMP
REM Uso: scripts\test_cameras.bat

echo ============================================================
echo Testando conexao com cameras RTSP/RTMP...
echo ============================================================
echo.

python scripts\test_camera_urls.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Teste concluido com sucesso!
) else (
    echo.
    echo Alguns testes falharam. Verifique as cameras offline.
)

echo.
pause
