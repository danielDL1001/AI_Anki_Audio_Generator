@echo off
title Instalando AI Anki Audio Generator

echo ==========================================
echo       Instalando o programa
echo ==========================================
echo.

docker info >nul 2>&1

if errorlevel 1 (
    echo O Docker Desktop nao esta instalado
    echo ou ainda nao foi iniciado.
    echo.
    echo Instale-o pelo site oficial:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit
)

echo Construindo o programa...
echo Isso pode demorar alguns minutos na primeira vez.
echo.

docker compose build

if errorlevel 1 (
    echo.
    echo Ocorreu um erro durante a instalacao.
    pause
    exit
)

echo.
echo Instalacao concluida!
echo Agora voce pode executar Iniciar.bat.
pause
