"""Exportacion e importacion de la configuracion del motor (para replicarla en otro hospital o respaldarla).

Formato: un JSON `motordicom-configuracion` con hasta cuatro secciones:

  mensajes       mapeos y valores fijos de ADT y ORM          (reutilizable entre hospitales)
  equipos        equipo / unidad de negocio por modalidad      (reutilizable si el RIS usa los mismos codigos)
  canales        host, puerto y AET del worklist y de Mirth    (propio de cada hospital)
  equivalencias  texto del estudio -> codigo del RIS           (propio de cada hospital: cada RIS tiene su numeracion)

Importar es no destructivo salvo en `mensajes`, que REEMPLAZA por completo los mapeos y valores fijos de cada
tipo de mensaje. Antes de aplicar se valida todo (sin tocar nada) y se guarda un respaldo de la configuracion
actual, que se puede volver a importar para revertir.
"""
import datetime
import json
import os
import re

from core import config_repo, equipos_repo, equivalencias_repo, mapeo_repo
from core.catalogos import campos_hl7_por_tipo
from core.modalidad_ris import MODALIDADES_RIS

FORMATO = "motordicom-configuracion"
VERSION = 1
SECCIONES = ("mensajes", "equipos", "canales", "equivalencias")
POR_DEFECTO = ("mensajes", "equipos")  # las otras dos son propias de cada hospital
TIPOS_MENSAJE = ("ADT", "ORM")
CANALES_VALIDOS = ("worklist_scu", "destino_adt", "destino_orm")
# Valores que casi siempre cambian de un hospital a otro: se destacan en la vista previa.
CAMPOS_DEL_HOSPITAL = ("MSH-3", "MSH-4", "MSH-5", "MSH-6", "MSH-11", "PV1-2", "PV1-3", "ORC-17")

_RE_CAMPO = re.compile(r"^[A-Z][A-Z0-9]{2}-\d{1,3}(\.\d{1,2})?$")
_RE_TAG = re.compile(r"^[0-9A-Fa-f]{8}$")
_RE_MARCADOR_DICOM = re.compile(r"^[0-9A-Fa-f]{8}(:(apellido|nombres))?$")
_MARCADORES = {"ahora", "cita", "codigo_estudio", "descripcion_estudio",
               "codigo_equipo", "descripcion_equipo", "unidad_negocio"}
_MAX_DETALLE = 200


class ConfiguracionInvalida(Exception):
    def __init__(self, errores):
        super().__init__("; ".join(errores))
        self.errores = list(errores)


# ---------------------------------------------------------------------------
# Lectura de la configuracion actual / exportacion
# ---------------------------------------------------------------------------
def _elegir(secciones):
    if secciones is None:
        return list(POR_DEFECTO)
    elegidas = [s for s in SECCIONES if s in set(secciones)]
    desconocidas = [s for s in secciones if s not in SECCIONES]
    if desconocidas:
        raise ConfiguracionInvalida(["Seccion desconocida: %s. Opciones: %s" % (", ".join(desconocidas), ", ".join(SECCIONES))])
    return elegidas


def _secciones_del_archivo(config) -> list:
    d = config.get("secciones") if isinstance(config, dict) else None
    return [s for s in SECCIONES if isinstance(d, dict) and s in d]


def leer_actual(secciones) -> dict:
    """Configuracion vigente, con la misma forma que el archivo (solo las secciones pedidas)."""
    out = {}
    if "mensajes" in secciones:
        out["mensajes"] = {
            t: {"mapeos": {tag: sorted(campos) for tag, campos in sorted(mapeo_repo.obtener_mapeos(t).items())},
                "valores_fijos": dict(sorted(mapeo_repo.obtener_valores_fijos(t).items()))}
            for t in TIPOS_MENSAJE
        }
    if "equipos" in secciones:
        out["equipos"] = [{k: e[k] for k in ("modalidad", "codigo_equipo", "descripcion_equipo", "unidad_negocio")}
                          for e in equipos_repo.listar()]
    if "canales" in secciones:
        out["canales"] = [{k: c.get(k) for k in ("clave", "host", "puerto", "aet", "aet_local", "activo")}
                          for c in config_repo.listar()]
    if "equivalencias" in secciones:
        out["equivalencias"] = [{k: e.get(k) for k in ("descripcion_origen", "codigo_destino", "descripcion_destino", "modalidad_ris")}
                                for e in equivalencias_repo.listar()]
    return out


def exportar(secciones=None, hospital="", comentario="") -> dict:
    elegidas = _elegir(secciones)
    return {
        "formato": FORMATO,
        "version": VERSION,
        "exportado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "origen": {"hospital": str(hospital or "").strip(), "comentario": str(comentario or "").strip()},
        "secciones": leer_actual(elegidas),
    }


# ---------------------------------------------------------------------------
# Validacion (pura: no toca la base)
# ---------------------------------------------------------------------------
def _validar_mensajes(msj, errores, avisos):
    if not isinstance(msj, dict):
        errores.append("mensajes: debe ser un objeto con ADT y/o ORM.")
        return
    for tipo, datos in msj.items():
        if tipo not in TIPOS_MENSAJE:
            errores.append("mensajes: tipo desconocido '%s' (solo ADT y ORM)." % tipo)
            continue
        if not isinstance(datos, dict):
            errores.append("mensajes.%s: debe ser un objeto con mapeos y valores_fijos." % tipo)
            continue
        catalogo = {c["campo"] for c in campos_hl7_por_tipo(tipo)}
        mapeos = datos.get("mapeos", {})
        if not isinstance(mapeos, dict):
            errores.append("mensajes.%s.mapeos: debe ser un objeto tag -> lista de campos." % tipo)
            mapeos = {}
        for tag, campos in mapeos.items():
            if not _RE_TAG.match(str(tag)):
                errores.append("%s: el tag '%s' no es un tag DICOM de 8 digitos hexadecimales." % (tipo, tag))
            if not isinstance(campos, list) or not all(isinstance(c, str) for c in campos):
                errores.append("%s: el mapeo del tag %s debe ser una lista de campos HL7." % (tipo, tag))
                continue
            for c in campos:
                if not _RE_CAMPO.match(c):
                    errores.append("%s: campo HL7 invalido '%s' en el mapeo del tag %s." % (tipo, c, tag))
                elif c not in catalogo:
                    avisos.append("%s: el campo %s no esta en el catalogo (no aparecera en la pantalla Mapeo)." % (tipo, c))
        fijos = datos.get("valores_fijos", {})
        if not isinstance(fijos, dict):
            errores.append("mensajes.%s.valores_fijos: debe ser un objeto campo -> valor." % tipo)
            continue
        for campo, valor in fijos.items():
            if not _RE_CAMPO.match(str(campo)):
                errores.append("%s: campo HL7 invalido '%s' en los valores fijos." % (tipo, campo))
                continue
            if not isinstance(valor, str):
                errores.append("%s %s: el valor fijo debe ser texto." % (tipo, campo))
                continue
            if campo not in catalogo:
                avisos.append("%s: el campo %s no esta en el catalogo (no aparecera en la pantalla Mapeo)." % (tipo, campo))
            for m in re.findall(r"\{([^{}]*)\}", valor):
                if m not in _MARCADORES and not _RE_MARCADOR_DICOM.match(m):
                    errores.append("%s %s: marcador desconocido {%s}." % (tipo, campo, m))


def _validar_equipos(lista, errores, avisos):
    if not isinstance(lista, list):
        errores.append("equipos: debe ser una lista.")
        return
    vistas = set()
    for i, e in enumerate(lista, 1):
        if not isinstance(e, dict):
            errores.append("equipos[%d]: debe ser un objeto." % i)
            continue
        m = e.get("modalidad")
        if m not in MODALIDADES_RIS:
            errores.append("equipos[%d]: modalidad no valida '%s'. Opciones: %s." % (i, m, ", ".join(MODALIDADES_RIS)))
        elif m in vistas:
            errores.append("equipos: la modalidad %s esta repetida." % m)
        vistas.add(m)
        if not str(e.get("codigo_equipo") or "").strip():
            errores.append("equipos[%d] (%s): falta el codigo del equipo." % (i, m))


def _validar_canales(lista, errores, avisos):
    if not isinstance(lista, list):
        errores.append("canales: debe ser una lista.")
        return
    vistas = set()
    for i, c in enumerate(lista, 1):
        if not isinstance(c, dict):
            errores.append("canales[%d]: debe ser un objeto." % i)
            continue
        clave = c.get("clave")
        if clave not in CANALES_VALIDOS:
            errores.append("canales[%d]: clave desconocida '%s'. Opciones: %s." % (i, clave, ", ".join(CANALES_VALIDOS)))
        elif clave in vistas:
            errores.append("canales: la clave %s esta repetida." % clave)
        vistas.add(clave)
        if not str(c.get("host") or "").strip():
            errores.append("canales[%d] (%s): falta el host." % (i, clave))
        p = c.get("puerto")
        if isinstance(p, bool) or not isinstance(p, int) or not 1 <= p <= 65535:
            errores.append("canales[%d] (%s): el puerto debe ser un entero entre 1 y 65535." % (i, clave))
        if "activo" in c and c["activo"] is not None and not isinstance(c["activo"], bool):
            errores.append("canales[%d] (%s): 'activo' debe ser verdadero o falso." % (i, clave))


def _validar_equivalencias(lista, errores, avisos):
    if not isinstance(lista, list):
        errores.append("equivalencias: debe ser una lista.")
        return
    vistas = {}
    for i, e in enumerate(lista, 1):
        if not isinstance(e, dict):
            errores.append("equivalencias[%d]: debe ser un objeto." % i)
            continue
        origen, codigo = str(e.get("descripcion_origen") or "").strip(), str(e.get("codigo_destino") or "").strip()
        if not origen or not codigo:
            errores.append("equivalencias[%d]: faltan la descripcion de origen o el codigo." % i)
            continue
        try:
            equivalencias_repo._modalidad_valida(e.get("modalidad_ris"))
        except ValueError as ex:
            errores.append("equivalencias[%d] (%s): %s" % (i, origen[:40], ex))
        clave = equivalencias_repo.normalizar(origen)
        if clave in vistas:
            avisos.append("equivalencias: '%s' esta repetida (fila %d y %d); se usara la ultima." % (origen[:40], vistas[clave], i))
        vistas[clave] = i


_VALIDADORES = {"mensajes": _validar_mensajes, "equipos": _validar_equipos,
                "canales": _validar_canales, "equivalencias": _validar_equivalencias}


def validar(config, secciones) -> tuple:
    """(errores, avisos) del archivo para las secciones elegidas. No toca la base."""
    errores, avisos = [], []
    if not isinstance(config, dict) or config.get("formato") != FORMATO:
        return ["El archivo no es una configuracion del motor (falta 'formato': '%s')." % FORMATO], avisos
    v = config.get("version")
    if not isinstance(v, int) or v < 1:
        errores.append("Version del formato invalida.")
    elif v > VERSION:
        errores.append("El archivo es de una version mas nueva (%d) que la que entiende este motor (%d). Actualiza el motor." % (v, VERSION))
    datos = config.get("secciones")
    if not isinstance(datos, dict):
        errores.append("Falta el objeto 'secciones'.")
        return errores, avisos
    for s in secciones:
        if s not in datos:
            avisos.append("La seccion '%s' no esta en el archivo; se omite." % s)
        else:
            _VALIDADORES[s](datos[s], errores, avisos)
    return errores, avisos


# ---------------------------------------------------------------------------
# Comparacion con lo vigente (pura)
# ---------------------------------------------------------------------------
def _diff(actual: dict, nuevo: dict, con_quitar: bool) -> list:
    detalle = []
    for k in sorted(nuevo):
        if k not in actual:
            detalle.append({"clave": k, "accion": "agregar", "antes": None, "despues": nuevo[k]})
        elif actual[k] != nuevo[k]:
            detalle.append({"clave": k, "accion": "cambiar", "antes": actual[k], "despues": nuevo[k]})
    if con_quitar:
        for k in sorted(actual):
            if k not in nuevo:
                detalle.append({"clave": k, "accion": "quitar", "antes": actual[k], "despues": None})
    return detalle


def _aplanar(secciones_cfg: dict, seccion: str):
    """Pasa una seccion a {clave: valor} para compararla."""
    d = secciones_cfg.get(seccion)
    if seccion == "mensajes":
        out = {}
        for tipo in TIPOS_MENSAJE:
            m = (d or {}).get(tipo) or {}
            for tag, campos in (m.get("mapeos") or {}).items():
                out["%s mapeo %s" % (tipo, str(tag).upper())] = sorted(campos)
            for campo, valor in (m.get("valores_fijos") or {}).items():
                if valor not in (None, ""):
                    out["%s %s" % (tipo, campo)] = valor
        return out
    if seccion == "equipos":
        return {e["modalidad"]: {k: e.get(k) or "" for k in ("codigo_equipo", "descripcion_equipo", "unidad_negocio")} for e in (d or [])}
    if seccion == "canales":
        return {c["clave"]: {k: c.get(k) for k in ("host", "puerto", "aet", "aet_local", "activo") if c.get(k) is not None} for c in (d or [])}
    return {equivalencias_repo.normalizar(e["descripcion_origen"]):
            {"codigo": str(e["codigo_destino"]).strip(), "descripcion_destino": (e.get("descripcion_destino") or "").strip(),
             "modalidad_ris": e.get("modalidad_ris") or ""} for e in (d or [])}


def comparar(actual: dict, nuevo: dict, secciones) -> dict:
    """Que cambiaria al aplicar `nuevo` sobre `actual`, por seccion."""
    out = {}
    for s in secciones:
        if s not in nuevo:
            continue
        a, n = _aplanar(actual, s), _aplanar(nuevo, s)
        if s == "mensajes":  # el archivo solo reemplaza los tipos que trae (ADT y/o ORM)
            tipos = tuple(t + " " for t in (nuevo.get("mensajes") or {}))
            a = {k: v for k, v in a.items() if k.startswith(tipos)}
        # Solo `mensajes` reemplaza (quita lo que no esta en el archivo); el resto solo agrega o cambia.
        # Para equipos y canales se compara solo contra lo que el archivo menciona.
        detalle = _diff(a, n, con_quitar=(s == "mensajes"))
        out[s] = {
            "agregar": sum(d["accion"] == "agregar" for d in detalle),
            "cambiar": sum(d["accion"] == "cambiar" for d in detalle),
            "quitar": sum(d["accion"] == "quitar" for d in detalle),
            "igual": len([k for k in n if k in a and a[k] == n[k]]),
            "detalle": detalle[:_MAX_DETALLE],
            "recortado": len(detalle) > _MAX_DETALLE,
        }
    return out


def valores_del_hospital(config) -> list:
    """Valores del archivo que suelen ser propios de cada hospital (para revisarlos antes de aplicar)."""
    out = []
    for tipo, m in ((config.get("secciones") or {}).get("mensajes") or {}).items():
        for campo in CAMPOS_DEL_HOSPITAL:
            v = ((m or {}).get("valores_fijos") or {}).get(campo)
            if v:
                out.append({"mensaje": tipo, "campo": campo, "valor": v})
    return out


def analizar(config, secciones=None) -> dict:
    """Vista previa de una importacion: errores, avisos y diferencias. No modifica nada."""
    elegidas = _elegir(secciones if secciones is not None else _secciones_del_archivo(config))
    errores, avisos = validar(config, elegidas)
    resultado = {"errores": errores, "avisos": avisos, "secciones_en_archivo": [], "cambios": {}, "valores_del_hospital": []}
    if isinstance(config, dict) and isinstance(config.get("secciones"), dict):
        resultado["secciones_en_archivo"] = _secciones_del_archivo(config)
        resultado["origen"] = config.get("origen") or {}
        resultado["exportado"] = config.get("exportado")
    if not errores:
        actual = leer_actual([s for s in elegidas if s in config["secciones"]])
        resultado["cambios"] = comparar(actual, config["secciones"], elegidas)
        resultado["valores_del_hospital"] = valores_del_hospital(config)
    return resultado


# ---------------------------------------------------------------------------
# Aplicacion
# ---------------------------------------------------------------------------
def _carpeta_respaldos() -> str:
    raiz = os.environ.get("MOTORDICOM_DATA") or os.path.join(os.environ.get("ProgramData", os.getcwd()), "MotorDICOM")
    carpeta = os.path.join(raiz, "backups")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def guardar_respaldo() -> str:
    """Guarda TODA la configuracion actual antes de importar. Volver a importar ese archivo la restituye."""
    cfg = exportar(SECCIONES, comentario="Respaldo automatico antes de importar una configuracion")
    ruta = os.path.join(_carpeta_respaldos(), "configuracion_antes_de_importar_%s.json" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    return ruta


def aplicar(config, secciones=None, usuario="") -> dict:
    """Valida, respalda y aplica la configuracion. Lanza ConfiguracionInvalida si algo no es valido."""
    elegidas = _elegir(secciones if secciones is not None else _secciones_del_archivo(config))
    errores, avisos = validar(config, elegidas)
    if errores:
        raise ConfiguracionInvalida(errores)
    datos = config["secciones"]
    aplicadas = [s for s in elegidas if s in datos]
    if not aplicadas:
        raise ConfiguracionInvalida(["No hay nada que aplicar: ninguna de las secciones elegidas esta en el archivo."])

    respaldo = guardar_respaldo()
    resumen = {}
    try:
        if "mensajes" in aplicadas:
            for tipo, m in datos["mensajes"].items():
                mapeo_repo.reemplazar(tipo, {str(t).upper(): list(c) for t, c in (m.get("mapeos") or {}).items()},
                                      dict(m.get("valores_fijos") or {}))
            resumen["mensajes"] = sorted(datos["mensajes"])
        if "equipos" in aplicadas:
            for e in datos["equipos"]:
                equipos_repo.guardar(e["modalidad"], e["codigo_equipo"], e.get("descripcion_equipo") or "", e.get("unidad_negocio") or "")
            resumen["equipos"] = len(datos["equipos"])
        if "canales" in aplicadas:
            for c in datos["canales"]:
                if config_repo.upsert(c["clave"], {k: c.get(k) for k in ("host", "puerto", "aet", "aet_local", "activo")}) is None:
                    raise ConfiguracionInvalida(["El canal '%s' no existe en este motor." % c["clave"]])
            resumen["canales"] = len(datos["canales"])
        if "equivalencias" in aplicadas:
            for e in datos["equivalencias"]:
                equivalencias_repo.upsert(e["descripcion_origen"], e["codigo_destino"], e.get("descripcion_destino") or "",
                                          e.get("modalidad_ris") or None)
            resumen["equivalencias"] = len(datos["equivalencias"])
    except Exception as ex:
        raise ConfiguracionInvalida(["Se interrumpio al aplicar (%s). Ya se habian aplicado: %s. Para volver atras, importa el respaldo: %s"
                                     % (ex, ", ".join(resumen) or "nada", respaldo)])
    print(f"[*] Configuracion importada por {usuario or '?'}: {resumen}; respaldo en {respaldo}")
    return {"aplicado": True, "secciones": aplicadas, "resumen": resumen, "respaldo": respaldo, "avisos": avisos}
