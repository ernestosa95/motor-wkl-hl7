@echo off
rem ==========================================================================
rem  MotorDICOM - Build completo para Windows
rem
rem    build.bat [version] [opciones]
rem
rem    version        Version del instalador (ej. 1.0.1). Por defecto: 1.0.0
rem    /deps          Instala/actualiza dependencias Python (requirements-build.txt)
rem    /nofront       No recompila el frontend (usa static\ tal como esta)
rem    /noinstaller   Solo genera dist\MotorDICOM (sin Inno Setup)
rem
rem  Pasos:
rem    1. Verifica requisitos (Python, PyInstaller, Node, Inno Setup, vendor\)
rem    2. Compila el frontend (frontend-motor) y lo copia a static\
rem    3. Compila el backend con PyInstaller (MotorDICOM.spec)
rem    4. Verifica el bundle (static, alembic, ejecutable)
rem    5. Genera el instalador con Inno Setup -> dist_installer\
rem
rem  El detalle de cada paso queda en build.log
rem ==========================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "VERSION=1.0.0"
set "DO_DEPS=0"
set "DO_FRONT=1"
set "DO_INSTALLER=1"
set "LOG=%~dp0build.log"

:parse_args
if "%~1"=="" goto args_ok
if /i "%~1"=="/deps"        (set "DO_DEPS=1"      & shift & goto parse_args)
if /i "%~1"=="/nofront"     (set "DO_FRONT=0"     & shift & goto parse_args)
if /i "%~1"=="/noinstaller" (set "DO_INSTALLER=0" & shift & goto parse_args)
if /i "%~1"=="/?"           goto ayuda
if /i "%~1"=="-h"           goto ayuda
set "ARG=%~1"
if "%ARG:~0,1%"=="/" (echo [ERROR] Opcion desconocida: %~1 & goto ayuda)
set "VERSION=%~1"
shift
goto parse_args

:args_ok
set "COMMIT=sin-git"
for /f %%h in ('git rev-parse --short HEAD 2^>nul') do set "COMMIT=%%h"

echo ==================================================== > "%LOG%"
echo  Build MotorDICOM %VERSION% (commit %COMMIT%) >> "%LOG%"
echo  %DATE% %TIME% >> "%LOG%"
echo ==================================================== >> "%LOG%"

echo ====================================================
echo   MotorDICOM - Build %VERSION%  (commit %COMMIT%)
echo ====================================================

rem --------------------------------------------------------------------------
rem 1. Requisitos
rem --------------------------------------------------------------------------
echo.
echo [1/5] Verificando requisitos...

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo   - Entorno virtual: .venv
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
    echo   - Entorno virtual: venv
) else (
    echo   - [AVISO] No hay .venv ni venv; se usa el Python global.
)

where python >nul 2>&1
if errorlevel 1 (echo [ERROR] No se encontro Python en el PATH. & goto fallo)

if "%DO_DEPS%"=="0" goto deps_ok
echo   - Instalando dependencias Python...
python -m pip install -r requirements-build.txt >> "%LOG%" 2>&1
if errorlevel 1 (echo [ERROR] Fallo pip install. Ver build.log & goto fallo)
:deps_ok

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (echo [ERROR] Falta PyInstaller. Ejecuta: build.bat /deps & goto fallo)
rem Sin python-dotenv el exe NO lee el .env del instalador y no conecta a la base.
python -c "import dotenv, psycopg2, pynetdicom, huey, fastapi, passlib, jwt" >nul 2>&1
if errorlevel 1 (echo [ERROR] Faltan dependencias Python. Ejecuta: build.bat /deps & goto fallo)
echo   - Python y dependencias OK

if "%DO_FRONT%"=="0" goto req_instalador
where npm >nul 2>&1
if errorlevel 1 (echo [ERROR] No se encontro npm. Instala Node.js o usa /nofront & goto fallo)
echo   - Node/npm OK

:req_instalador
if "%DO_INSTALLER%"=="0" goto req_ok
set "ISCC="
for /f "delims=" %%i in ('where iscc 2^>nul') do if "!ISCC!"=="" set "ISCC=%%i"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
rem Instalacion "solo para mi usuario" (sin admin)
if "%ISCC%"=="" if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" (echo [ERROR] No se encontro Inno Setup 6 ^(ISCC.exe^). Instalalo o usa /noinstaller & goto fallo)
echo   - Inno Setup: %ISCC%

set "FALTA="
if not exist "vendor\pgsql\bin\initdb.exe" set "FALTA=%FALTA% vendor\pgsql\bin\initdb.exe"
if not exist "vendor\pgsql\bin\pg_ctl.exe" set "FALTA=%FALTA% vendor\pgsql\bin\pg_ctl.exe"
if not exist "vendor\pgsql\bin\psql.exe"   set "FALTA=%FALTA% vendor\pgsql\bin\psql.exe"
if not exist "vendor\nssm.exe"             set "FALTA=%FALTA% vendor\nssm.exe"
if not exist "vendor\vc_redist.x64.exe"    set "FALTA=%FALTA% vendor\vc_redist.x64.exe"
if not "%FALTA%"=="" (echo [ERROR] Faltan binarios en vendor\:%FALTA% & goto fallo)
echo   - vendor\ completo (pgsql, nssm, vc_redist)

:req_ok
rem --------------------------------------------------------------------------
rem 2. Frontend
rem --------------------------------------------------------------------------
echo.
if "%DO_FRONT%"=="1" goto front
echo [2/5] Frontend omitido (/nofront), se usa static\ actual.
goto front_ok

:front
echo [2/5] Compilando frontend...
pushd frontend-motor
if exist node_modules goto front_build
echo   - npm ci
call npm ci --no-audit --no-fund >> "%LOG%" 2>&1
if errorlevel 1 (popd & echo [ERROR] Fallo npm ci. Ver build.log & goto fallo)
:front_build
call npm run build >> "%LOG%" 2>&1
if errorlevel 1 (popd & echo [ERROR] Fallo npm run build. Ver build.log & goto fallo)
popd
rem Espeja dist\ en static\ (borra bundles viejos). robocopy: codigos < 8 son OK.
robocopy "frontend-motor\dist" "static" /MIR /NFL /NDL /NJH /NJS /NP >> "%LOG%" 2>&1
if errorlevel 8 (echo [ERROR] No se pudo copiar el frontend a static\ & goto fallo)
echo   - static\ actualizado

:front_ok
if not exist "static\index.html" (echo [ERROR] Falta static\index.html & goto fallo)

rem --------------------------------------------------------------------------
rem 3. PyInstaller
rem --------------------------------------------------------------------------
echo.
echo [3/5] Compilando backend con PyInstaller (puede tardar)...
if exist "build\MotorDICOM" rmdir /s /q "build\MotorDICOM"
if exist "dist\MotorDICOM"  rmdir /s /q "dist\MotorDICOM"
python -m PyInstaller MotorDICOM.spec --noconfirm --clean >> "%LOG%" 2>&1
if errorlevel 1 (echo [ERROR] Fallo PyInstaller. Ver build.log & goto fallo)

rem --------------------------------------------------------------------------
rem 4. Verificacion del bundle
rem --------------------------------------------------------------------------
echo.
echo [4/5] Verificando bundle...
set "BUNDLE=dist\MotorDICOM"
if not exist "%BUNDLE%\MotorDICOM.exe" (echo [ERROR] No se genero %BUNDLE%\MotorDICOM.exe & goto fallo)
rem PyInstaller 6 deja los datos en _internal\; versiones anteriores, junto al exe.
set "DATOS=%BUNDLE%\_internal"
if not exist "%DATOS%" set "DATOS=%BUNDLE%"
if not exist "%DATOS%\static\index.html" (echo [ERROR] El bundle no incluye static\ & goto fallo)
if not exist "%DATOS%\alembic\env.py"    (echo [ERROR] El bundle no incluye alembic\ & goto fallo)
rem Sin subcomando el exe muestra el uso y sale con codigo 2: confirma que arranca.
rem MOTORDICOM_DATA apunta a build\ para no crear C:\ProgramData\MotorDICOM en esta PC.
set "MOTORDICOM_DATA=%~dp0build\smoke"
"%BUNDLE%\MotorDICOM.exe" >> "%LOG%" 2>&1
set "SMOKE_RC=%ERRORLEVEL%"
set "MOTORDICOM_DATA="
if not "%SMOKE_RC%"=="2" (echo [ERROR] MotorDICOM.exe no arranca ^(codigo %SMOKE_RC%^). Ver build.log & goto fallo)
echo   - MotorDICOM.exe, static\ y alembic\ OK

rem --------------------------------------------------------------------------
rem 5. Instalador
rem --------------------------------------------------------------------------
echo.
set "SETUP="
if "%DO_INSTALLER%"=="1" goto instalador
echo [5/5] Instalador omitido (/noinstaller).
goto instalador_ok

:instalador
echo [5/5] Generando instalador con Inno Setup...
"%ISCC%" /Q /DAppVersion=%VERSION% "installer\MotorDICOM.iss" >> "%LOG%" 2>&1
if errorlevel 1 (echo [ERROR] Fallo Inno Setup. Ver build.log & goto fallo)
set "SETUP=dist_installer\MotorDICOM-Setup-%VERSION%.exe"
if not exist "%SETUP%" (echo [ERROR] No se encontro %SETUP% & goto fallo)

:instalador_ok
echo.
echo ====================================================
echo   BUILD OK - MotorDICOM %VERSION% (commit %COMMIT%)
echo   Bundle:     %BUNDLE%
if not "%SETUP%"=="" echo   Instalador: %SETUP%
echo   Log:        build.log
echo ====================================================
echo BUILD OK >> "%LOG%"
endlocal
exit /b 0

:fallo
echo.
echo ====================================================
echo   BUILD FALLIDO - revisar build.log
echo ====================================================
echo BUILD FALLIDO >> "%LOG%"
endlocal
exit /b 1

:ayuda
echo.
echo Uso: build.bat [version] [/deps] [/nofront] [/noinstaller]
echo.
echo   build.bat                 Build completo, version 1.0.0
echo   build.bat 1.0.1           Build completo, version 1.0.1
echo   build.bat 1.0.1 /deps     Instala dependencias Python y compila
echo   build.bat /noinstaller    Solo dist\MotorDICOM (sin instalador)
endlocal
exit /b 1
