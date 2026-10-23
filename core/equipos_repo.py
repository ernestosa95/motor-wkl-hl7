"""Equipo generico (y unidad de negocio) por modalidad del RIS."""

from core.database import SessionLocal, engine
from core.models import Base, EquipoModalidad
from core.modalidad_ris import (
    MODALIDADES_RIS, RADIOLOGIA, CONTRASTADA, TOMOGRAFIA, RESONANCIA, MAMOGRAFIA,
    ECOGRAFIA, DENSITOMETRIA, MEDICINA_NUCLEAR,
)

# Valores por defecto: un equipo generico por modalidad, con codigo tipo DICOM.
# Editables desde la pantalla Estudios (y restaurables).
DEFAULTS = {
    RADIOLOGIA: "DX",
    CONTRASTADA: "DX",
    TOMOGRAFIA: "CT",
    RESONANCIA: "MR",
    MAMOGRAFIA: "MG",
    ECOGRAFIA: "US",
    DENSITOMETRIA: "BMD",
    MEDICINA_NUCLEAR: "NM",
}

_lista = False


def _defaults(modalidad: str) -> dict:
    codigo = DEFAULTS[modalidad]
    return {"codigo_equipo": codigo, "descripcion_equipo": "EQUIPO GENERICO " + codigo, "unidad_negocio": ""}


def _asegurar():
    """Crea la tabla si falta y siembra las modalidades que aun no tienen equipo."""
    global _lista
    if _lista:
        return
    Base.metadata.create_all(bind=engine, tables=[EquipoModalidad.__table__])
    db = SessionLocal()
    try:
        existentes = {m for (m,) in db.query(EquipoModalidad.modalidad).all()}
        for m in MODALIDADES_RIS:
            if m not in existentes:
                db.add(EquipoModalidad(modalidad=m, **_defaults(m)))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    _lista = True


def _to_dict(e: EquipoModalidad) -> dict:
    return {
        "modalidad": e.modalidad,
        "codigo_equipo": e.codigo_equipo,
        "descripcion_equipo": e.descripcion_equipo,
        "unidad_negocio": e.unidad_negocio,
        "es_defecto": (e.codigo_equipo == DEFAULTS[e.modalidad]
                       and e.descripcion_equipo == _defaults(e.modalidad)["descripcion_equipo"]
                       and not e.unidad_negocio),
    }


def listar() -> list:
    _asegurar()
    db = SessionLocal()
    try:
        filas = {e.modalidad: e for e in db.query(EquipoModalidad).all()}
        return [_to_dict(filas[m]) for m in MODALIDADES_RIS if m in filas]
    finally:
        db.close()


def obtener(modalidad: str):
    """Equipo de una modalidad, o None si la modalidad no es valida o no tiene codigo."""
    _asegurar()
    db = SessionLocal()
    try:
        e = db.query(EquipoModalidad).filter(EquipoModalidad.modalidad == modalidad).first()
        return _to_dict(e) if e and e.codigo_equipo else None
    finally:
        db.close()


def guardar(modalidad: str, codigo_equipo: str, descripcion_equipo: str = "", unidad_negocio: str = "") -> dict:
    if modalidad not in MODALIDADES_RIS:
        raise ValueError("Modalidad no valida: %r" % (modalidad,))
    codigo = " ".join(str(codigo_equipo or "").split())
    if not codigo:
        raise ValueError("Falta el codigo del equipo.")
    _asegurar()
    db = SessionLocal()
    try:
        e = db.query(EquipoModalidad).filter(EquipoModalidad.modalidad == modalidad).first()
        if e is None:
            e = EquipoModalidad(modalidad=modalidad, codigo_equipo=codigo)
            db.add(e)
        e.codigo_equipo = codigo
        e.descripcion_equipo = " ".join(str(descripcion_equipo or "").split())
        e.unidad_negocio = " ".join(str(unidad_negocio or "").split())
        db.commit()
        db.refresh(e)
        return _to_dict(e)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def restaurar() -> list:
    """Vuelve todas las modalidades a sus valores por defecto."""
    _asegurar()
    for m in MODALIDADES_RIS:
        d = _defaults(m)
        guardar(m, d["codigo_equipo"], d["descripcion_equipo"], d["unidad_negocio"])
    return listar()
