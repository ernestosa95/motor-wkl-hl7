<#
    MotorDICOM - Respaldo de la base de datos (pg_dump, formato custom)
    ===================================================================
      .\backup_db.ps1                  Respalda ahora en C:\ProgramData\MotorDICOM\backups
      .\backup_db.ps1 -Dias 30         Conserva 30 dias (por defecto 14)
      .\backup_db.ps1 -Programar       Crea la tarea diaria "MotorDICOM Backup" a las 02:00 (como administrador)

    Restaurar (con los servicios API/Worker/Ingesta detenidos):
      pg_restore.exe -h localhost -p 5433 -U postgres -d motor_dicom_hl7 --clean --if-exists <archivo.dump>

    Guardar tambien, en un lugar seguro, C:\ProgramData\MotorDICOM\.env y .superpw (no van en el dump).
#>
param(
    [string] $InstallDir = (Split-Path -Parent $PSScriptRoot),
    [string] $Destino    = (Join-Path $env:ProgramData "MotorDICOM\backups"),
    [int]    $Dias       = 14,
    [switch] $Programar
)

$ErrorActionPreference = "Stop"
$DataRoot = Join-Path $env:ProgramData "MotorDICOM"

if ($Programar) {
    $accion = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -InstallDir `"$InstallDir`" -Dias $Dias"
    $disparador = New-ScheduledTaskTrigger -Daily -At 2:00am
    Register-ScheduledTask -TaskName "MotorDICOM Backup" -Action $accion -Trigger $disparador `
        -User "SYSTEM" -RunLevel Highest -Force | Out-Null
    Write-Host "Tarea 'MotorDICOM Backup' creada: diaria a las 02:00, conserva $Dias dias."
    return
}

$PgDump = Join-Path $InstallDir "pgsql\bin\pg_dump.exe"
if (-not (Test-Path $PgDump)) { throw "No se encontro $PgDump" }
$SuperPw = Join-Path $DataRoot ".superpw"
if (-not (Test-Path $SuperPw)) { throw "No se encontro $SuperPw" }

New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$archivo = Join-Path $Destino ("motor_dicom_hl7_{0:yyyyMMdd_HHmm}.dump" -f (Get-Date))

$env:PGPASSWORD = (Get-Content $SuperPw -Raw).Trim()
try {
    & $PgDump -h localhost -p 5433 -U postgres -d motor_dicom_hl7 -Fc -f $archivo
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $archivo -ErrorAction SilentlyContinue
        throw "pg_dump fallo (codigo $LASTEXITCODE)"
    }
} finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

# Retencion: borra los respaldos mas viejos que $Dias
Get-ChildItem $Destino -Filter "motor_dicom_hl7_*.dump" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$Dias) } | Remove-Item

$mb = [math]::Round((Get-Item $archivo).Length / 1MB, 1)
Write-Host "Respaldo creado: $archivo ($mb MB)"
