@echo off
title AI Anki Audio Generator

echo ==========================================
echo       AI Anki Audio Generator
echo ==========================================
echo.

docker info >nul 2>&1

if errorlevel 1 (
    echo ERRO: O Docker Desktop nao esta iniciado.
    echo.
    echo Abra o Docker Desktop e aguarde ele iniciar.
    echo Depois execute este arquivo novamente.
    pause
    exit
)

echo Iniciando o programa...
echo.

docker compose run --rm anki-audio-generator

echo.
echo Programa encerrado.
pause
