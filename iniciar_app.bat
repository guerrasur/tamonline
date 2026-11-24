@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Tamo online?

rem Si el actualizador dejó un .bat nuevo, se aplica y se relanza (todo se lee antes de ejecutar)
if exist "%~dp0iniciar_app.bat.new" (move /y "%~dp0iniciar_app.bat.new" "%~dp0iniciar_app.bat" >nul & call "%~dp0iniciar_app.bat" & exit /b)

rem ---- 1) Python 3.10+ ----
set "PY="
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo.
  echo  No se encontro Python 3.10 o superior.
  echo  Instalalo desde https://www.python.org/downloads/ y marca la casilla
  echo  "Add python.exe to PATH" durante la instalacion. Luego abri este programa de nuevo.
  echo.
  pause
  exit /b 1
)

rem ---- 2) Primera ejecucion: entorno virtual, dependencias y Chromium ----
if not exist "venv\Scripts\python.exe" (
  echo Creando entorno virtual...
  %PY% -m venv venv
  if errorlevel 1 ( echo No se pudo crear el entorno virtual. & pause & exit /b 1 )
)
if not exist "venv\.deps_ok" (
  echo Instalando dependencias, puede tardar unos minutos...
  "venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
  "venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 ( echo No se pudieron instalar las dependencias. Revisa tu conexion. & pause & exit /b 1 )
  echo ok> "venv\.deps_ok"
)
if not exist "venv\.chromium_ok" (
  echo Instalando Chromium para Playwright...
  "venv\Scripts\python.exe" -m playwright install chromium
  if errorlevel 1 (echo Aviso: no se pudo instalar Chromium; se usara solo lectura HTTP.) else (echo ok> "venv\.chromium_ok")
)

rem ---- 3) Acceso directo en el Escritorio (solo la primera vez) ----
if not exist ".acceso_creado" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crear_acceso.ps1" && echo ok> ".acceso_creado"
)

rem ---- 4) Actualizacion automatica ----
"venv\Scripts\python.exe" updater.py
if errorlevel 10 (
  echo Actualizando dependencias...
  "venv\Scripts\python.exe" -m pip install -q -r requirements.txt
)

rem ---- 5) Servidor local (si el puerto 8765 esta ocupado, solo abre el navegador) ----
"venv\Scripts\python.exe" -m server.main
if errorlevel 1 ( echo El programa se cerro con un error. Revisa la carpeta logs. & pause )
exit /b 0
