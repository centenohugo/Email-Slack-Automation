@echo off
setlocal EnableDelayedExpansion
title RME ZAZ1 - Training Reminder
chcp 65001 >nul

:: -- 0. Anclar al directorio del script (funciona con doble-click, --
::     accesos directos con "Iniciar en" distinto, rutas con espacios, etc.)
cd /d "%~dp0"

echo.
echo  ============================================
echo   RME ZAZ1 - Training Reminder
echo  ============================================
echo.

:: -- 1. Localizar Python --------------------------------------------
set "PYTHON_EXE="
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
)
if not defined PYTHON_EXE (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py -3"
)

if not defined PYTHON_EXE (
    echo [!] Python no encontrado. Instalando con winget...
    echo     Esto puede tardar unos minutos, no cierres esta ventana.
    echo.
    winget install Python.Python.3.11 -e --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo.
        echo [ERROR] No se pudo instalar Python automaticamente.
        echo         Descargalo manualmente desde https://www.python.org/downloads/
        echo         y vuelve a ejecutar este archivo.
        pause
        exit /b 1
    )
    echo.
    echo [OK] Python instalado. Buscando ejecutable...
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
    if not defined PYTHON_EXE (
        py -3 --version >nul 2>&1
        if not errorlevel 1 set "PYTHON_EXE=py -3"
    )
    if not defined PYTHON_EXE (
        echo [!] Python instalado pero no encontrado en PATH todavia.
        echo     Cierra esta ventana y vuelve a ejecutar iniciar.bat.
        pause
        exit /b 1
    )
)

echo [OK] Python encontrado: !PYTHON_EXE!
echo.

:: -- 2. Crear entorno virtual si no existe ---------------------------
if not exist "%~dp0venv\Scripts\python.exe" (
    echo [..] Creando entorno virtual...
    !PYTHON_EXE! -m venv "%~dp0venv"
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
    echo.
)

set "VENV_PYTHON=%~dp0venv\Scripts\python.exe"

:: -- 3. Instalar/actualizar dependencias ------------------------------
echo [..] Instalando dependencias...
"%VENV_PYTHON%" -m pip install -q -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [ERROR] Fallo al instalar dependencias. Revisa requirements.txt.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.
echo.

:: -- 4. Comprobar .env -------------------------------------------------
if not exist "%~dp0.env" (
    echo [!] No se encontro el archivo .env.
    if exist "%~dp0.env.example" (
        copy "%~dp0.env.example" "%~dp0.env" >nul
        echo     Se ha creado .env desde .env.example.
    ) else (
        echo SECRET_KEY=cambiar-esta-clave-aleatoria> "%~dp0.env"
        echo     Se ha creado .env con valores de ejemplo.
    )
    echo.
)

:: -- 5. Lanzar app -----------------------------------------------------
echo [..] Abriendo navegador en http://localhost:5000 ...
timeout /t 2 /nobreak >nul
start "" http://localhost:5000

echo [OK] Iniciando servidor. Cierra esta ventana para detenerlo.
echo.
"%VENV_PYTHON%" "%~dp0app.py"

echo.
echo  Servidor detenido. Pulsa cualquier tecla para cerrar.
pause >nul
