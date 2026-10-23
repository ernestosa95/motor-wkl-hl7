"""Equivalencias entre el texto del estudio (worklist) y su codigo en el destino."""
import csv
import io
import re
import unicodedata
from collections import Counter

from sqlalchemy import func, text

from core.database import SessionLocal, engine
from core.models import Base, EquivalenciaEstudio, RegistroTrazabilidad
from core.modalidad_ris import MODALIDADES_RIS, clasificar
from core import equipos_repo

TAG_DESCRIPCION = "00321060"  # Requested Procedure Description

_tabla_lista = False


def _asegurar_tabla():
    """Crea la tabla si falta (mismo patron que canales y mapeos)."""
    global _tabla_lista
    if not _tabla_lista:
        Base.metadata.create_all(bind=engine, tables=[EquivalenciaEstudio.__table__])
        # create_all no agrega columnas a una tabla existente (instalaciones anteriores)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE equivalencias_estudio "
                              "ADD COLUMN IF NOT EXISTS modalidad_ris VARCHAR(32)"))
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
        "modalidad_ris": e.modalidad_ris,
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


def _modalidad_valida(modalidad):
    """Normaliza una modalidad del RIS ('' / None = sin indicar). Lanza ValueError si no es valida."""
    m = " ".join(str(modalidad or "").split()).upper()
    if not m:
        return None
    if m not in MODALIDADES_RIS:
        raise ValueError("Modalidad del RIS no valida: %r. Opciones: %s" % (m, ", ".join(MODALIDADES_RIS)))
    return m


def upsert(descripcion_origen: str, codigo_destino: str, descripcion_destino: str = "",
           modalidad_ris: str = None) -> dict:
    """Crea o actualiza una equivalencia. Si no se indica modalidad, conserva la existente."""
    origen = " ".join(str(descripcion_origen or "").split())
    codigo = str(codigo_destino or "").strip()
    if not origen or not codigo:
        raise ValueError("Hacen falta la descripcion de origen y el codigo de destino.")
    modalidad = _modalidad_valida(modalidad_ris)
    destino = " ".join(str(descripcion_destino or "").split()) or origen
    _asegurar_tabla()
    db = SessionLocal()
    try:
        clave = normalizar(origen)
        e = db.query(EquivalenciaEstudio).filter(EquivalenciaEstudio.clave == clave).first()
        if e is None:
            e = EquivalenciaEstudio(clave=clave, descripcion_origen=origen,
                                    codigo_destino=codigo, descripcion_destino=destino,
                                    modalidad_ris=modalidad)
            db.add(e)
        else:
            e.descripcion_origen, e.codigo_destino, e.descripcion_destino = origen, codigo, destino
            if modalidad:
                e.modalidad_ris = modalidad
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
    """CSV con columnas: descripcion_origen ; codigo ; [descripcion_destino] ; ...

    Acepta separador ; , o tabulador y una fila de encabezado opcional. Si el encabezado
    tiene una columna `modalidad_ris` se lee por nombre (las demas columnas extra se ignoran).
    Las filas con descripcion pero sin codigo (aun no completadas, como las que trae la
    exportacion de pendientes) se omiten sin ser un error.
    Devuelve (filas, errores, omitidas): filas = [(origen, codigo, destino, modalidad_ris)].
    """
    texto = (texto or "").lstrip("\ufeff")
    # Solo se detecta el separador; las comillas siguen el formato estandar (""
    # escapa una comilla). El Sniffer deduce mal las comillas desde la 1a linea.
    primera = texto.split("\n", 1)[0]
    separador = max(";,\t", key=primera.count) if any(c in primera for c in ";,\t") else ";"
    filas, errores, omitidas = [], [], 0
    col_mod = None
    for n, fila in enumerate(csv.reader(io.StringIO(texto), delimiter=separador), 1):
        celdas = [c.strip() for c in fila]
        if not any(celdas):
            continue
        if n == 1 and normalizar(celdas[0]) in ("descripcion_origen", "descripcion", "estudio", "origen"):
            nombres = [normalizar(c) for c in celdas]
            col_mod = nombres.index("modalidad_ris") if "modalidad_ris" in nombres else None
            continue  # encabezado
        if not celdas[0]:
            errores.append("Fila %d: falta la descripcion de origen." % n)
        elif len(celdas) < 2 or not celdas[1]:
            omitidas += 1  # todavia sin codigo
        else:
            modalidad = celdas[col_mod] if col_mod is not None and col_mod < len(celdas) else ""
            try:
                modalidad = _modalidad_valida(modalidad) or ""
            except ValueError as e:
                errores.append("Fila %d: %s" % (n, e))
                continue
            filas.append((celdas[0], celdas[1], celdas[2] if len(celdas) > 2 else "", modalidad))
    return filas, errores, omitidas


def importar_csv(texto: str) -> dict:
    filas, errores, omitidas = parsear_csv(texto)
    existentes = {e["descripcion_origen"] for e in listar()}
    nuevos = actualizados = 0
    for origen, codigo, destino, modalidad in filas:
        if " ".join(origen.split()) in existentes:
            actualizados += 1
        else:
            nuevos += 1
        upsert(origen, codigo, destino, modalidad or None)
    return {"nuevos": nuevos, "actualizados": actualizados, "omitidas": omitidas, "errores": errores}


TAG_MODALIDAD = "00080060"  # Modality


def _uso_por_estudio(db):
    """Por cada texto de estudio (clave normalizada): ejemplo, total de ordenes y
    modalidades DICOM con que llego, segun el historial de ordenes."""
    desc = RegistroTrazabilidad.payload_dicom_raw[TAG_DESCRIPCION].astext
    mod = RegistroTrazabilidad.payload_dicom_raw[TAG_MODALIDAD].astext
    filas = db.query(desc, mod, func.count()).group_by(desc, mod).all()
    uso = {}
    for d, m, n in filas:
        clave = normalizar(d)
        if not clave:
            continue
        u = uso.setdefault(clave, {"descripcion": " ".join(str(d).split()),
                                   "cantidad": 0, "mods": Counter()})
        u["cantidad"] += n
        if m:
            u["mods"][m.strip().upper()] += n
    return uso


def _txt_modalidades(mods: Counter) -> str:
    return "/".join(m for m, _ in mods.most_common())


def panel() -> dict:
    """Equivalencias cargadas y estudios pendientes, ambos con su modalidad DICOM."""
    _asegurar_tabla()
    db = SessionLocal()
    try:
        equivalencias = db.query(EquivalenciaEstudio).order_by(
            EquivalenciaEstudio.descripcion_origen).all()
        cargadas = {e.clave for e in equivalencias}
        uso = _uso_por_estudio(db)
        eqs = []
        for e in equivalencias:
            d = _to_dict(e)
            d["modalidad"] = _txt_modalidades(uso.get(e.clave, {}).get("mods", Counter()))
            d["modalidad_sugerida"] = clasificar(e.descripcion_origen, d["modalidad"])[0]
            eqs.append(d)
    finally:
        db.close()
    pend = []
    for c, u in sorted(uso.items(), key=lambda kv: -kv[1]["cantidad"]):
        if c in cargadas:
            continue
        dicom = _txt_modalidades(u["mods"])
        sugerida, _, obs = clasificar(u["descripcion"], dicom)
        pend.append({"descripcion": u["descripcion"], "cantidad": u["cantidad"], "modalidad": dicom,
                     "modalidad_sugerida": sugerida})
    return {"equivalencias": eqs, "pendientes": pend,
            "modalidades_ris": list(MODALIDADES_RIS), "equipos": equipos_repo.listar()}


def pendientes() -> list:
    """Descripciones que llegaron en ordenes y aun no tienen equivalencia."""
    return panel()["pendientes"]
