<#
    MotorDICOM - Pre/Post desinstalacion
    ====================================
    Detiene y elimina los servicios. Por seguridad clinica, los DATOS
    (C:\ProgramData\MotorDICOM) NO se borran automaticamente: contienen el
    historico de trazabilidad y auditorias. Borrarlos es decision manual.
#>

param(
    [Parameter(Mandatory = $true)] [string] $InstallDir
)

$Nssm      = Join-Path $InstallDir "tools\nssm.exe"
$PgBin     = Join-Path $InstallDir "pgsql\bin"
$PgData    = Join-Path $env:ProgramData "MotorDICOM\pgdata"
$PgSvcName = "MotorDICOM Postgres"

foreach ($svc in @("MotorDICOM API", "MotorDICOM Worker", "MotorDICOM Ingesta")) {
    if (Get-Service -Name $svc -ErrorAction SilentlyContinue) {
        & $Nssm stop $svc 2>$null | Out-Null
        & $Nssm remove $svc confirm 2>$null | Out-Null
    }
}

if (Get-Service -Name $PgSvcName -ErrorAction SilentlyContinue) {
    Stop-Service -Name $PgSvcName -Force -ErrorAction SilentlyContinue
    & "$PgBin\pg_ctl.exe" unregister -N "$PgSvcName" 2>$null | Out-Null
}

Remove-NetFirewallRule -DisplayName "MotorDICOM Web (8000)"   -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "MotorDICOM DICOM (4242)" -ErrorAction SilentlyContinue

Write-Host "Servicios eliminados. Datos conservados en C:\ProgramData\MotorDICOM"
