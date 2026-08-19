"""Acceso a la configuración de canales en la base de datos.

Devuelve dicts (no objetos ORM) para evitar problemas de sesión cerrada.
"""
from core.database import SessionLocal, engine
from core.models import Base, Canal

# Valores por defecto con los que se siembra la tabla la primera vez.
DEFAULTS = {
    "worklist_scu": {
        "nombre": "Origen: Worklist DICOM (C-FIND)",
        "host": "127.0.0.1", "puerto": 4243,
        "aet": "TEST_PACS", "aet_local": "MOTOR_WKL",
    },
    "destino_adt": {
        "nombre": "Destino MLLP: Demográficos (ADT)",
        "host": "127.0.0.1", "puerto": 2575,
        "aet": None, "aet_local": None,
    },
    "destino_orm": {
        "nombre": "Destino MLLP: Órdenes (ORM)",
        "host": "127.0.0.1", "puerto": 2575,
        "aet": None, "aet_local": None,
    },
}


def _to_dict(c: Canal) -> dict:
    return {
        "clave": c.clave,
        "nombre": c.nombre,
        "host": c.host,
        "puerto": c.puerto,
        "aet": c.aet,
        "aet_local": c.aet_local,
        "activo": c.activo,
        "actualizado": c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else None,
    }


def seed_canales():
    """Crea la tabla (si falta) y siembra los tres canales por defecto una sola vez."""
    Base.metadata.create_all(bind=engine)  # red de seguridad si no corrió Alembic
    db = SessionLocal()
    try:
        for clave, datos in DEFAULTS.items():
            existe = db.query(Canal).filter(Canal.clave == clave).first()
            if not existe:
                db.add(Canal(clave=clave, **datos))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[!] Error al sembrar canales: {e}")
    finally:
        db.close()


def listar() -> list:
    db = SessionLocal()
    try:
        return [_to_dict(c) for c in db.query(Canal).order_by(Canal.clave).all()]
    finally:
        db.close()


def obtener_canal(clave: str):
    db = SessionLocal()
    try:
        c = db.query(Canal).filter(Canal.clave == clave).first()
        return _to_dict(c) if c else None
    finally:
        db.close()


def upsert(clave: str, datos: dict):
    """Actualiza host/puerto/aet/aet_local/activo de un canal existente."""
    db = SessionLocal()
    try:
        c = db.query(Canal).filter(Canal.clave == clave).first()
        if not c:
            return None
        for campo in ("host", "puerto", "aet", "aet_local", "activo"):
            if campo in datos and datos[campo] is not None:
                setattr(c, campo, datos[campo])
        db.commit()
        return _to_dict(c)
    except Exception as e:
        db.rollback()
        print(f"[!] Error al actualizar canal {clave}: {e}")
        raise
    finally:
        db.close()
