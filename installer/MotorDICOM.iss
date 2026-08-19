; =============================================================================
;  MotorDICOM - Instalador (Inno Setup 6+)
;  Compilar con:  iscc MotorDICOM.iss
;  Genera:        dist_installer\MotorDICOM-Setup.exe
;
;  Estructura esperada junto a este .iss antes de compilar:
;    ..\dist\MotorDICOM\        (salida onedir de PyInstaller)
;    ..\vendor\pgsql\           (PostgreSQL portable descomprimido: bin\, lib\, share\)
;    ..\vendor\nssm.exe         (nssm 64-bit)
;    ..\vendor\vc_redist.x64.exe (Visual C++ Redistributable x64)
;    postinstall.ps1
;    postuninstall.ps1
; =============================================================================

#define AppName "MotorDICOM"
#define AppVersion "1.0.0"
#define Publisher "Tecnoimagen SA"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist_installer
OutputBaseFilename={#AppName}-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Bundle de la aplicacion (PyInstaller onedir)
Source: "..\dist\MotorDICOM\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; PostgreSQL portable
Source: "..\vendor\pgsql\*"; DestDir: "{app}\pgsql"; Flags: recursesubdirs createallsubdirs ignoreversion
; NSSM
Source: "..\vendor\nssm.exe"; DestDir: "{app}\tools"; Flags: ignoreversion
; Visual C++ Redistributable (requerido por los binarios de PostgreSQL)
Source: "..\vendor\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
; Scripts de orquestacion
Source: "postinstall.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "postuninstall.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[Icons]
Name: "{group}\Consola MotorDICOM"; Filename: "http://localhost:8000"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

[Run]
; 1) Instalar la runtime de C++ ANTES de tocar PostgreSQL (sino initdb crashea)
Filename: "{tmp}\vc_redist.x64.exe"; \
  Parameters: "/install /quiet /norestart"; \
  StatusMsg: "Instalando Visual C++ Redistributable..."; \
  Flags: waituntilterminated

; 2) Provisiona Postgres, crea DB, migra y registra servicios
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\postinstall.ps1"" -InstallDir ""{app}"""; \
  StatusMsg: "Provisionando base de datos y servicios (puede demorar)..."; \
  Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\postuninstall.ps1"" -InstallDir ""{app}"""; \
  RunOnceId: "RemoveServices"; Flags: runhidden waituntilterminated
