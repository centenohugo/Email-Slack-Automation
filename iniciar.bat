@echo off
setlocal EnableDelayedExpansion
title RME ZAZ1 · Training Reminder
chcp 65001 >nul

echo.
echo  ============================================
echo   RME ZAZ1 · Training Reminder
echo  ============================================
echo.

:: ── 1. Comprobar Python ───────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
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
    echo [OK] Python instalado. Reiniciando sesion de PATH...
    :: Refrescar PATH sin cerrar la ventana
    for /f "tokens=*" %%i in ('where python 2^>nul') do set PYTHON_EXE=%%i
    if "!PYTHON_EXE!"=="" (
        echo [!] Python instalado pero no encontrado en PATH todavia.
        echo     Cierra esta ventana y vuelve a ejecutar iniciar.bat.
        pause
        exit /b 1
    )
) else (
    for /f "tokens=*" %%i in ('where python') do set PYTHON_EXE=%%i
)

echo [OK] Python encontrado: !PYTHON_EXE!
echo.

:: ── 2. Crear entorno virtual si no existe ─────────────────────────
if not exist "venv\" (
    echo [..] Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
    echo.
)

:: ── 3. Instalar/actualizar dependencias ───────────────────────────
echo [..] Instalando dependencias...
call venv\Scripts\pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo al instalar dependencias. Revisa requirements.txt.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.
echo.

:: ── 4. Comprobar .env ─────────────────────────────────────────────
if not exist ".env" (
    echo [!] No se encontro el archivo .env.
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo     Se ha creado .env desde .env.example.
    ) else (
        echo SECRET_KEY=cambiar-esta-clave-aleatoria> .env
        echo TEST_EMAIL=tu_correo@amazon.es>> .env
        echo     Se ha creado .env con valores de ejemplo.
    )
    echo.
    echo  ┌─────────────────────────────────────────────────────────┐
    echo  │  ACCION REQUERIDA                                       │
    echo  │                                                         │
    echo  │  Edita el archivo .env con tu correo:                   │
    echo  │    TEST_EMAIL=tu_correo@amazon.es                       │
    echo  │                                                         │
    echo  │  Guarda el archivo y pulsa cualquier tecla para         │
    echo  │  continuar.                                             │
    echo  └─────────────────────────────────────────────────────────┘
    echo.
    start notepad .env
    pause
)

:: ── 5. Lanzar app ─────────────────────────────────────────────────
echo [..] Abriendo navegador en http://localhost:5000 ...
timeout /t 2 /nobreak >nul
start http://localhost:5000

echo [OK] Iniciando servidor. Cierra esta ventana para detenerlo.
echo.
call venv\Scripts\python app.py

echo.
echo  Servidor detenido. Pulsa cualquier tecla para cerrar.
pause >nul
