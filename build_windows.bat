@echo off
title Build - Anki Audio Generator
cd /d "%~dp0"

echo ==========================================
echo   ANKI AUDIO GENERATOR - BUILD
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

REM ------------------------------------------------------------
REM ffmpeg: para o .exe funcionar sozinho (cards Cloze), coloque
REM ffmpeg.exe e ffprobe.exe numa pasta chamada "ffmpeg" ao lado
REM deste arquivo ANTES de rodar o build. Eles serao embutidos.
REM ------------------------------------------------------------
set "EXTRA="
if exist "ffmpeg\ffmpeg.exe" if exist "ffmpeg\ffprobe.exe" (
    echo.
    echo ffmpeg encontrado em .\ffmpeg - sera embutido no executavel.
    set "EXTRA=--add-binary "ffmpeg\ffmpeg.exe;." --add-binary "ffmpeg\ffprobe.exe;.""
)

if not defined EXTRA (
    echo.
    echo AVISO: .\ffmpeg\ffmpeg.exe e .\ffmpeg\ffprobe.exe nao encontrados.
    echo O executavel sera gerado SEM ffmpeg: os cards comuns funcionam,
    echo mas os cards Cloze exigirao o ffmpeg instalado no PATH.
)

echo.
echo Gerando executavel...
pyinstaller --clean --noconfirm --onefile --console --name Anki_Audio_Generator %EXTRA% main.py
if errorlevel 1 (
    echo.
    echo Erro ao gerar executavel.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   BUILD CONCLUIDO!
echo.
echo   Executavel:
echo   dist\Anki_Audio_Generator.exe
echo ==========================================
pause
