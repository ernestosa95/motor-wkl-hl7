"""Equivalencias entre el texto del estudio (worklist) y su codigo en el destino."""
import csv
import io
import re
import unicodedata
from collections import Counter

from sqlalchemy import func

from core.database import SessionLocal, engine
from core.models import Base, EquivalenciaEstudio, RegistroTrazabilidad

TAG_DESCRIPCION = "00321060"  # Requested Procedure Description

_tabla_lista = False


def _asegurar_tabla():
    """Crea la tabla si falta (mismo patron que canales y mapeos)."""
    global _tabla_lista
    if not _tabla_lista:
        Base.metadata.create_all(bind=engine, tables=[EquivalenciaEstudio.__table__])
        _tabla_lista = True


def normalizar(texto) -> str:
    """Clave de comparacion: sin tildes, en minusculas y con espacios colapsados."""
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _to_dict(e: EquivalenciaEstudio) -> dict:
    return {
        "id": str(e.id),
        "descripcion_origen": e.descripcion_origen,
        "codigo_destino": e.codigo_destino,
        "descripcion_destino": e.descripcion_destino,
        "actualizado": e.updated_at.strftime("%Y-%m-%d %H:%M:%S") if e.updated_at else None,
    }


def buscar(descripcion):
    """Equivalencia de una descripcion de worklist, o None si no esta cargada."""
    clave = normalizar(descripcion)
    if not clave:
        return None
    _asegurar_tabla()
    db = SessionLocal()
    try:
        e = db.query(EquivalenciaEstudio).filter(EquivalenciaEstudio.clave == clave).first()
        return _to_dict(e) if e else None
    finally:
        db.close()


def listar() -> list:
    _asegurar_tabla()
    db = SessionLocal()
    try:
        filas = db.query(EquivalenciaEstudio).order_by(EquivalenciaEstudio.descripcion_origen).all()
        return [_to_dict(e) for e in filas]
    finally:
        db.close()


def upsert(descripcion_origen: str, codigo_destino: str, descripcion_destino: str = "") -> dict:
    origen = " ".join(str(descripcion_origen or "").split())
    codigo = str(codigo_destino or "").strip()
    if not origen or not codigo:
        raise ValueError("Hacen falta la descripcion de origen y el codigo de destino.")
    destino = " ".join(str(descripcion_destino or "").split()) or origen
    _asegurar_tabla()
    db = SessionLocal()
    try:
        clave = normalizar(origen)
        e = db.query(EquivalenciaEstudio).filter(EquivalenciaEstudio.clave == clave).first()
        if e is None:
            e = EquivalenciaEstudio(clave=clave, descripcion_origen=origen,
                                    codigo_destino=codigo, descripcion_destino=destino)
            db.add(e)
        else:
            e.descripcion_origen, e.codigo_destino, e.descripcion_destino = origen, codigo, destino
        db.commit()
        db.refresh(e)
        return _to_dict(e)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def eliminar(id_) -> bool:
    _asegurar_tabla()
    db = SessionLocal()
    try:
        n = db.query(EquivalenciaEstudio).filter(EquivalenciaEstudio.id == id_).delete()
        db.commit()
        return n > 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def parsear_csv(texto: str):
    """CSV con columnas: descripcion_origen ; codigo ; [descripcion_destino].

    Acepta separador ; , o tabulador y una fila de encabezado opcional.
    Devuelve (filas, errores): filas = [(origen, codigo, destino)].
    """
    texto = (texto or "").lstrip("\ufeff")
    try:
        dialecto = csv.Sniffer().sniff(texto.split("\n", 1)[0], delimiters=";,\t")
    except csv.Error:
        dialecto = csv.excel
        dialecto.delimiter = ";"
    filas, errores = [], []
    for n, fila in enumerate(csv.reader(io.StringIO(texto), dialecto), 1):
        celdas = [c.strip() for c in fila]
        if not any(celdas):
            continue
        if n == 1 and normalizar(celdas[0]) in ("descripcion_origen", "descripcion", "estudio", "origen"):
            continue  # encabezado
        if len(celdas) < 2 or not celdas[0] or not celdas[1]:
            errores.append("Fila %d: faltan la descripcion o el codigo." % n)
            continue
        filas.append((celdas[0], celdas[1], celdas[2] if len(celdas) > 2 else ""))
    return filas, errores


def importar_csv(texto: str) -> dict:
    filas, errores = parsear_csv(texto)
    existentes = {e["descripcion_origen"] for e in listar()}
    nuevos = actualizados = 0
    for origen, codigo, destino in filas:
        if " ".join(origen.split()) in existentes:
            actualizados += 1
        else:
            nuevos += 1
        upsert(origen, codigo, destino)
    return {"nuevos": nuevos, "actualizados": actualizados, "errores": errores}


def pendientes() -> list:
    """Descripciones que llegaron en ordenes y aun no tienen equivalencia."""
    _asegurar_tabla()
    db = SessionLocal()
    try:
        cargadas = {e.clave for e in db.query(EquivalenciaEstudio.clave).all()}
        expr = RegistroTrazabilidad.payload_dicom_raw[TAG_DESCRIPCION].astext
        filas = db.query(expr, func.count()).group_by(expr).all()
    finally:
        db.close()
    cuenta, ejemplo = Counter(), {}
    for desc, n in filas:
        clave = normalizar(desc)
        if not clave or clave in cargadas:
            continue
        cuenta[clave] += n
        ejemplo.setdefault(clave, " ".join(str(desc).split()))
    return [{"descripcion": ejemplo[c], "cantidad": n} for c, n in cuenta.most_common()]
