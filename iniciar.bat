@echo off
setlocal EnableDelayedExpansion
title Training Reminder
chcp 65001 >nul

:: Arranca la app con doble clic. Instala Python y las dependencias si faltan.
cd /d "%~dp0"

echo.
echo  ============================================
echo   Training Reminder
echo  ============================================
echo.

:: -- 1. Localizar Python ---------------------------------------------
set "PYTHON_EXE="
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
)
if not defined PYTHON_EXE (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py -3"
)

if not defined PYTHON_EXE (
    echo [AVISO] Python no encontrado. Instalando con winget...
    echo         Esto puede tardar unos minutos, no cierres esta ventana.
    winget install Python.Python.3.11 -e --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar Python automaticamente.
        echo         Descargalo de https://www.python.org/downloads/ y vuelve a ejecutar este archivo.
        pause
        exit /b 1
    )
    echo [AVISO] Python instalado. Cierra esta ventana y vuelve a ejecutar iniciar.bat.
    pause
    exit /b 0
)
echo [OK] Python encontrado: !PYTHON_EXE!

:: -- 2. Entorno virtual ----------------------------------------------
if not exist "%~dp0venv\Scripts\python.exe" (
    echo [..] Creando entorno virtual...
    !PYTHON_EXE! -m venv "%~dp0venv"
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)
set "VENV_PYTHON=%~dp0venv\Scripts\python.exe"

:: -- 3. Dependencias --------------------------------------------------
echo [..] Instalando dependencias...
"%VENV_PYTHON%" -m pip install -q -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [ERROR] Fallo al instalar dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

:: -- 4. Archivo .env --------------------------------------------------
::     Guarda las claves privadas. No se sube nunca al repositorio, asi que
::     hay que crearlo en cada equipo donde se instale la app.
if not exist "%~dp0.env" (
    echo [..] No hay archivo .env. Creandolo a partir de .env.example...
    copy /y "%~dp0.env.example" "%~dp0.env" >nul
    "%VENV_PYTHON%" -c "import os,io,re; p=r'%~dp0.env'; t=io.open(p,encoding='utf-8').read(); t=re.sub(r'(?m)^SECRET_KEY=.*$','SECRET_KEY='+os.urandom(24).hex(),t); io.open(p,'w',encoding='utf-8').write(t)"
    echo.
    echo [AVISO] Abre el archivo .env con el Bloc de notas y rellena tus datos
    echo         ^(EMAIL_DOMAIN, SITE_NAME, REPORT_URL...^) antes de usar la app.
    echo.
    pause
)

:: -- 5. Arrancar -------------------------------------------------------
::     El puerto se lee de PORT en el .env; por defecto 5005.
set "PORT=5005"
for /f "tokens=2 delims==" %%p in ('findstr /b /c:"PORT=" "%~dp0.env" 2^>nul') do set "PORT=%%p"

echo [..] Abriendo el navegador en http://localhost:!PORT!
timeout /t 2 /nobreak >nul
start "" "http://localhost:!PORT!"

echo [OK] Servidor arrancado. Cierra esta ventana para detenerlo.
echo.
"%VENV_PYTHON%" "%~dp0app.py"

echo.
echo  Servidor detenido. Pulsa cualquier tecla para cerrar.
pause >nul
