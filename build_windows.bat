
@echo off
title Build - Anki Audio Generator

cd /d "%~dp0"

echo ==========================================
echo     ANKI AUDIO GENERATOR - BUILD
echo ==========================================
echo.

if not exist .venv-build (
    echo Criando ambiente virtual...
    py -3 -m venv .venv-build

    if errorlevel 1 (
        echo Erro ao criar ambiente virtual.
        pause
        exit /b 1
    )
)

call .venv-build\Scripts\activate.bat

echo.
echo Instalando dependencias...
python -m pip install --upgrade pip
pip install -r requirements-build.txt

if errorlevel 1 (
    echo Erro ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo Gerando executavel...
pyinstaller --clean --noconfirm --onefile --console --name Anki_Audio_Generator main.py

if errorlevel 1 (
    echo.
    echo Erro ao gerar executavel.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo BUILD CONCLUIDO!
echo.
echo Executavel:
echo dist\Anki_Audio_Generator.exe
echo ==========================================

pause

