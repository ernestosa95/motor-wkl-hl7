"""Acceso al mapeo DICOM -> HL7 y valores fijos, separados por tipo de mensaje."""
from collections import defaultdict

from core.database import SessionLocal, engine
from core.models import Base, Mapeo, ValorFijo
from core.catalogos import (
    CATALOGO_DICOM, DEFAULT_MAPEOS, DEFAULT_VALORES_FIJOS,
    display_tag, campos_hl7_por_tipo,
)

TIPOS = ("ADT", "ORM")


def seed_mapeos():
    """Crea tablas (si faltan) y siembra el mapeo por defecto si están vacías."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Mapeo).first() is None:
            for tipo in TIPOS:
                for tag, campos in DEFAULT_MAPEOS[tipo].items():
                    for campo in campos:
                        db.add(Mapeo(tipo_mensaje=tipo, dicom_tag=tag, hl7_field=campo))
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[!] Error al sembrar mapeos: {e}")
    finally:
        db.close()


def obtener_mapeos(tipo: str) -> dict:
    db = SessionLocal()
    try:
        resultado = defaultdict(list)
        for m in db.query(Mapeo).filter(Mapeo.tipo_mensaje == tipo).all():
            resultado[m.dicom_tag].append(m.hl7_field)
        return dict(resultado)
    finally:
        db.close()


def obtener_valores_fijos(tipo: str) -> dict:
    db = SessionLocal()
    try:
        return {v.hl7_field: v.valor for v in db.query(ValorFijo).filter(ValorFijo.tipo_mensaje == tipo).all()}
    finally:
        db.close()


def obtener_todo(tipo: str) -> dict:
    """Catálogos filtrados + mapeo + valores fijos, para el editor visual."""
    catalogo_dicom = [{**t, "display": display_tag(t["tag"])} for t in CATALOGO_DICOM]
    return {
        "tipo": tipo,
        "catalogo_dicom": catalogo_dicom,
        "catalogo_hl7": campos_hl7_por_tipo(tipo),
        "mapeos": obtener_mapeos(tipo),
        "valores_fijos": obtener_valores_fijos(tipo),
    }


def reemplazar(tipo: str, mapeos: dict, valores_fijos: dict):
    """Reemplaza mapeo y valores fijos de un tipo de mensaje."""
    db = SessionLocal()
    try:
        db.query(Mapeo).filter(Mapeo.tipo_mensaje == tipo).delete()
        db.query(ValorFijo).filter(ValorFijo.tipo_mensaje == tipo).delete()
        for tag, campos in (mapeos or {}).items():
            for campo in campos:
                db.add(Mapeo(tipo_mensaje=tipo, dicom_tag=tag, hl7_field=campo))
        for campo, valor in (valores_fijos or {}).items():
            if valor is not None and str(valor) != "":
                db.add(ValorFijo(tipo_mensaje=tipo, hl7_field=campo, valor=str(valor)))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[!] Error al reemplazar mapeo de {tipo}: {e}")
        raise
    finally:
        db.close()
    return obtener_todo(tipo)
