"""
MotorDICOM - Entrypoint unificado (dispatcher por subcomando)
=============================================================
    MotorDICOM.exe api          -> API FastAPI + SPA React (uvicorn, :8000)
    MotorDICOM.exe worker       -> consumidor Huey (transformacion + emision)
    MotorDICOM.exe ingesta      -> loop de ingesta DICOM (C-FIND worklist)
    MotorDICOM.exe migrate      -> aplica migraciones Alembic (idempotente) y sale
    MotorDICOM.exe crear-admin  -> siembra el usuario admin inicial y sale
"""

import os
import sys
import time
import logging


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def data_dir() -> str:
    root = os.environ.get(
        "MOTORDICOM_DATA",
        os.path.join(os.environ.get("ProgramData", os.getcwd()), "MotorDICOM"),
    )
    os.makedirs(root, exist_ok=True)
    return root


def _load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = os.path.join(data_dir(), ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path, override=False)


def _setup_logging():
    logs = os.path.join(data_dir(), "logs")
    os.makedirs(logs, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(logs, "motordicom.log"), encoding="utf-8"),
        ],
    )


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------
def cmd_api():
    import uvicorn
    from core.api import app

    static_dir = resource_path("static")
    if os.path.isdir(static_dir):
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="spa")
        logging.info("SPA servida desde %s", static_dir)
    else:
        logging.warning("No se encontro carpeta 'static'; se sirve solo la API")

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    logging.info("Iniciando API en %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


def cmd_worker():
    from core.broker import huey
    from huey.consumer import Consumer

    workers = int(os.environ.get("HUEY_WORKERS", "2"))
    logging.info("Iniciando consumidor Huey (%s workers, thread)", workers)
    Consumer(huey, workers=workers, worker_type="thread").run()


def cmd_ingesta():
    intervalo = int(os.environ.get("INGESTA_INTERVALO_SEG", "30"))
    try:
        from core.ingesta import iniciar_ingesta  # type: ignore
        logging.info("Arrancando ingesta continua (core.ingesta.iniciar_ingesta)")
        iniciar_ingesta()
    except ImportError:
        logging.warning(
            "core.ingesta.iniciar_ingesta no existe. Loop en modo espera cada "
            "%ss. Cablea aqui tu C-FIND SCU real.", intervalo
        )
        while True:
            time.sleep(intervalo)


def cmd_migrate():
    """
    Aplica migraciones Alembic de forma idempotente y tolerante a bases
    preexistentes.

    Si la base ya tiene las tablas del modelo pero NO tiene el historial de
    Alembic registrado (caso tipico de reinstalar sobre una instalacion vieja),
    en vez de fallar con 'DuplicateTable' se "sella" (stamp) al head y no se
    re-ejecutan las migraciones. Asi el instalador funciona igual en maquina
    limpia (upgrade normal) que sobre una base existente (adopcion via stamp).
    """
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import inspect
    from core.database import DATABASE_URL, engine

    cfg = Config()
    cfg.set_main_option("script_location", resource_path("alembic"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

    insp = inspect(engine)
    tablas = set(insp.get_table_names())
    tiene_alembic = "alembic_version" in tablas
    # Tablas nucleo del modelo que indican una base ya inicializada por fuera de Alembic
    tablas_modelo = {"registro_trazabilidad", "usuarios", "canales", "mapeos"}
    base_preexistente = bool(tablas_modelo & tablas)

    if base_preexistente and not tiene_alembic:
        # La base ya existe pero Alembic no la conoce -> adoptarla sin recrear.
        logging.warning(
            "Base preexistente sin historial Alembic; se sella (stamp) al head "
            "en vez de recrear tablas."
        )
        command.stamp(cfg, "head")
        logging.info("Base sellada al head. No se re-ejecutaron migraciones.")
        return

    logging.info("Aplicando migraciones Alembic (upgrade head)...")
    command.upgrade(cfg, "head")
    logging.info("Migraciones aplicadas correctamente.")


def cmd_crear_admin():
    """Siembra el usuario admin inicial. Idempotente: si ya existe, no lo toca."""
    from core.database import SessionLocal
    from core.models import Usuario
    from passlib.context import CryptContext

    usuario_inicial = os.environ.get("ADMIN_USER", "admin")
    pass_inicial = os.environ.get("ADMIN_PASS", "admin123")

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    db = SessionLocal()
    try:
        existente = db.query(Usuario).filter(Usuario.username == usuario_inicial).first()
        if existente:
            logging.info("El usuario '%s' ya existe; no se modifica.", usuario_inicial)
            return
        nuevo = Usuario(
            username=usuario_inicial,
            hashed_password=pwd_context.hash(pass_inicial),
            debe_cambiar_password=True,
        )
        db.add(nuevo)
        db.commit()
        logging.info(
            "Usuario '%s' creado (contrasena inicial: '%s', cambio obligatorio).",
            usuario_inicial, pass_inicial,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
COMANDOS = {
    "api": cmd_api,
    "worker": cmd_worker,
    "ingesta": cmd_ingesta,
    "migrate": cmd_migrate,
    "crear-admin": cmd_crear_admin,
}


def main():
    _load_env()
    _setup_logging()

    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd not in COMANDOS:
        print("Uso: MotorDICOM.exe [api|worker|ingesta|migrate|crear-admin]", file=sys.stderr)
        sys.exit(2)

    try:
        COMANDOS[cmd]()
    except KeyboardInterrupt:
        logging.info("Interrupcion recibida, cerrando '%s'.", cmd)
    except Exception:
        logging.exception("Fallo fatal en el subcomando '%s'", cmd)
        sys.exit(1)


if __name__ == "__main__":
    main()