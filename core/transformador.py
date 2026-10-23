"""Transformación DICOM -> HL7 dirigida por el mapeo y valores fijos de la base."""
from core.serializador_hl7 import construir_mensaje
from core.mapeo_repo import obtener_mapeos, obtener_valores_fijos
from core.catalogos import DEFAULT_MAPEOS
from core.modalidad_ris import clasificar
from core import equivalencias_repo, equipos_repo

_USA_ESTUDIO = ("{codigo_estudio}", "{descripcion_estudio}")
_USA_EQUIPO = ("{codigo_equipo}", "{descripcion_equipo}", "{unidad_negocio}")


def _usa(valores_fijos: dict, marcadores) -> bool:
    return any(m in v for v in valores_fijos.values() for m in marcadores)


def procesar_transformacion(payload_dicom: dict, tipo_mensaje: str = "ORM", msg_id: str = None) -> str:
    tipo = tipo_mensaje.upper()
    mapeos = obtener_mapeos(tipo) or DEFAULT_MAPEOS.get(tipo, {})
    valores_fijos = obtener_valores_fijos(tipo)

    # Solo se consulta lo que algun valor fijo usa.
    contexto = {}
    usa_estudio, usa_equipo = _usa(valores_fijos, _USA_ESTUDIO), _usa(valores_fijos, _USA_EQUIPO)
    eq = equivalencias_repo.buscar(payload_dicom.get("00321060")) if (usa_estudio or usa_equipo) else None

    if usa_estudio and eq:
        contexto["codigo_estudio"] = eq["codigo_destino"]
        contexto["descripcion_estudio"] = eq["descripcion_destino"]

    if usa_equipo:
        # Modalidad del RIS: la de la equivalencia; si no tiene, se deduce del texto del estudio.
        modalidad = (eq or {}).get("modalidad_ris") or clasificar(
            payload_dicom.get("00321060", ""), payload_dicom.get("00080060", ""))[0]
        contexto["_modalidad"] = modalidad
        equipo = equipos_repo.obtener(modalidad)
        if equipo:
            contexto["codigo_equipo"] = equipo["codigo_equipo"]
            contexto["descripcion_equipo"] = equipo["descripcion_equipo"]
            contexto["unidad_negocio"] = equipo["unidad_negocio"]

    return construir_mensaje(payload_dicom, mapeos, valores_fijos, tipo,
                             msg_id=msg_id, contexto=contexto)
