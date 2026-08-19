<#
    MotorDICOM - Post-instalacion
    =============================
    Provisiona PostgreSQL portable embebido y registra los servicios de Windows.
    Lo invoca Inno Setup con privilegios de administrador:

        powershell -ExecutionPolicy Bypass -File postinstall.ps1 -InstallDir "C:\Program Files\MotorDICOM"

    Idempotente: se puede re-ejecutar sin destruir datos existentes.
#>

param(
    [Parameter(Mandatory = $true)] [string] $InstallDir
)

$ErrorActionPreference = "Stop"

# --- Rutas ---
$DataRoot   = Join-Path $env:ProgramData "MotorDICOM"
$PgData     = Join-Path $DataRoot "pgdata"
$Logs       = Join-Path $DataRoot "logs"
$PgBin      = Join-Path $InstallDir "pgsql\bin"
$Nssm       = Join-Path $InstallDir "tools\nssm.exe"
$Exe        = Join-Path $InstallDir "MotorDICOM.exe"
$EnvFile    = Join-Path $DataRoot ".env"

# --- Parametros de base de datos ---
$PgPort     = "5433"
$PgSvcName  = "MotorDICOM Postgres"
$DbName     = "motor_dicom_hl7"
$DbUser     = "motor"

New-Item -ItemType Directory -Force -Path $DataRoot, $Logs | Out-Null

function New-Secret([int]$len = 24) {
    -join ((48..57) + (65..90) + (97..122) | Get-Random -Count $len | ForEach-Object { [char]$_ })
}

# ===========================================================================
# 1. initdb (solo la primera vez)
# ===========================================================================
if (-not (Test-Path (Join-Path $PgData "PG_VERSION"))) {
    Write-Host "[1/7] Inicializando cluster PostgreSQL..."
    $SuperPw = New-Secret 28
    $pwFile  = Join-Path $env:TEMP "md_pgpw.txt"
    Set-Content -Path $pwFile -Value $SuperPw -NoNewline -Encoding ascii

    & "$PgBin\initdb.exe" -U postgres --pwfile="$pwFile" `
        --encoding=UTF8 --auth=scram-sha-256 -D "$PgData" | Out-Null
    Remove-Item $pwFile -Force

    # Bind a localhost y puerto propio para no chocar con un Postgres existente
    Add-Content (Join-Path $PgData "postgresql.conf") "`nport = $PgPort`nlisten_addresses = 'localhost'"

    # Guardamos la pw superusuario para el paso de creacion de rol/DB
    $SuperPw | Set-Content (Join-Path $DataRoot ".superpw") -NoNewline -Encoding ascii
} else {
    Write-Host "[1/7] Cluster ya inicializado, se omite initdb."
}

# ===========================================================================
# 2. Registrar y arrancar el servicio de Postgres
# ===========================================================================
Write-Host "[2/7] Registrando servicio Postgres..."
if (-not (Get-Service -Name $PgSvcName -ErrorAction SilentlyContinue)) {
    & "$PgBin\pg_ctl.exe" register -N "$PgSvcName" -D "$PgData" -w | Out-Null
}
Start-Service -Name $PgSvcName

# Esperar readiness
Write-Host "[3/7] Esperando a que Postgres acepte conexiones..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    & "$PgBin\pg_isready.exe" -h localhost -p $PgPort -q
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw "Postgres no respondio a tiempo." }

# ===========================================================================
# 3. Crear rol y base de datos (idempotente)
# ===========================================================================
Write-Host "[4/7] Creando rol y base de datos..."
$SuperPw = Get-Content (Join-Path $DataRoot ".superpw") -Raw
$env:PGPASSWORD = $SuperPw

# Reusar la pw ya existente para no invalidar la conexion en re-runs.
# Guardas: si el .env no existe o no trae la linea, se genera una nueva.
$DbPw = $null
if (Test-Path $EnvFile) {
    $linea = Get-Content $EnvFile | Where-Object { $_ -match "^DB_PASSWORD=" } | Select-Object -First 1
    if ($linea) { $DbPw = ($linea -replace "^DB_PASSWORD=", "").Trim() }
}
if ([string]::IsNullOrWhiteSpace($DbPw)) { $DbPw = New-Secret 24 }

$sql = @"
DO `$`$ BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DbUser') THEN
      CREATE ROLE $DbUser LOGIN PASSWORD '$DbPw';
   END IF;
END `$`$;
"@
$sql | & "$PgBin\psql.exe" -h localhost -p $PgPort -U postgres -d postgres -v ON_ERROR_STOP=1 | Out-Null

# FIX: envolver $exists en comillas para que .Trim() no falle cuando psql
# no devuelve filas (la base todavia no existe -> $exists es $null).
$exists = & "$PgBin\psql.exe" -h localhost -p $PgPort -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'"
if ("$exists".Trim() -ne "1") {
    & "$PgBin\psql.exe" -h localhost -p $PgPort -U postgres -c "CREATE DATABASE $DbName OWNER $DbUser" | Out-Null
}
Remove-Item Env:\PGPASSWORD

# ===========================================================================
# 4. Escribir .env (consumido por MotorDICOM.exe)
# ===========================================================================
Write-Host "[5/7] Escribiendo configuracion (.env)..."
$jwt = New-Secret 40
@"
DB_HOST=localhost
DB_PORT=$PgPort
DB_NAME=$DbName
DB_USER=$DbUser
DB_PASSWORD=$DbPw
API_HOST=0.0.0.0
API_PORT=8000
JWT_SECRET=$jwt
"@ | Set-Content -Path $EnvFile -Encoding ascii

# ===========================================================================
# 5. Migraciones Alembic
# ===========================================================================
Write-Host "[6/7] Aplicando migraciones y sembrando admin inicial..."
& "$Exe" migrate
if ($LASTEXITCODE -ne 0) { throw "Fallaron las migraciones Alembic." }
& "$Exe" crear-admin
if ($LASTEXITCODE -ne 0) { throw "Fallo la creacion del usuario admin inicial." }

# ===========================================================================
# 6. Registrar servicios de aplicacion con NSSM + firewall
# ===========================================================================
Write-Host "[7/7] Registrando servicios de aplicacion..."

function Register-Svc([string]$name, [string]$arg) {
    if (Get-Service -Name $name -ErrorAction SilentlyContinue) {
        & $Nssm stop $name | Out-Null
        & $Nssm remove $name confirm | Out-Null
    }
    & $Nssm install $name "$Exe" $arg | Out-Null
    & $Nssm set $name AppDirectory "$InstallDir" | Out-Null
    & $Nssm set $name AppStdout (Join-Path $Logs "$arg.log") | Out-Null
    & $Nssm set $name AppStderr (Join-Path $Logs "$arg.log") | Out-Null
    & $Nssm set $name Start SERVICE_AUTO_START | Out-Null
    & $Nssm set $name DependOnService "$PgSvcName" | Out-Null
    & $Nssm set $name AppEnvironmentExtra "MOTORDICOM_DATA=$DataRoot" | Out-Null
}

Register-Svc "MotorDICOM API"     "api"
Register-Svc "MotorDICOM Worker"  "worker"
Register-Svc "MotorDICOM Ingesta" "ingesta"

# Reglas de firewall: 8000 (consola web) y 4242 (DICOM C-FIND) entrantes.
# El emisor MLLP conecta SALIENTE al HIS, no requiere regla de entrada.
New-NetFirewallRule -DisplayName "MotorDICOM Web (8000)" -Direction Inbound `
    -Action Allow -Protocol TCP -LocalPort 8000 -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "MotorDICOM DICOM (4242)" -Direction Inbound `
    -Action Allow -Protocol TCP -LocalPort 4242 -ErrorAction SilentlyContinue | Out-Null

Start-Service "MotorDICOM API", "MotorDICOM Worker", "MotorDICOM Ingesta"

Write-Host "`nMotorDICOM instalado. Consola: http://localhost:8000"
