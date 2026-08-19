# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para MotorDICOM (modo onedir).
Compilar con:   pyinstaller MotorDICOM.spec --noconfirm

Requisitos de build (ver BUILD.md):
  - El front ya compilado en ./static  (salida de `npm run build`)
  - Las migraciones Alembic en ./core/alembic
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []

# --- Librerias que traen datos/plugins que PyInstaller NO detecta solo ---
for paquete in ("pynetdicom", "pydicom"):
    d, b, h = collect_all(paquete)
    datas += d
    binaries += b
    hiddenimports += h

# Submodulos que se importan de forma dinamica en runtime
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("huey")
# passlib carga sus algoritmos (bcrypt, pbkdf2, etc.) por nombre en runtime;
# collect_submodules los incluye a todos sin tener que enumerarlos.
hiddenimports += collect_submodules("passlib.handlers")

hiddenimports += [
    "psycopg2",
    "sqlalchemy.dialects.postgresql",
    "jinja2",
    "alembic",
    "dotenv",
    "bcrypt",
    # Los modulos de migracion se importan por ruta; se listan como datas abajo.
    "core.database",
    "core.models",
    "core.broker",
    "core.api",
]

# --- Recursos que la app lee del filesystem en runtime ---
datas += [
    ("static", "static"),                 # SPA compilada (React/Vite)
    ("core/alembic", "alembic"),          # migraciones + env.py
    # ("core/plantillas_hl7", "plantillas_hl7"),  # <- borrada: plantillas embebidas en codigo
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],  # no se usa GUI; achica el bundle
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MotorDICOM",
    console=True,          # servicios; util para ver logs si se corre a mano
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,             # UPX puede romper psycopg2/pynetdicom; dejar en False
    name="MotorDICOM",
)
