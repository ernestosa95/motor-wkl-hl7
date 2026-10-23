"""Transformación DICOM -> HL7 dirigida por el mapeo y valores fijos de la base."""
from core.serializador_hl7 import construir_mensaje
from core.mapeo_repo import obtener_mapeos, obtener_valores_fijos
from core.catalogos import DEFAULT_MAPEOS
from core import equivalencias_repo


def procesar_transformacion(payload_dicom: dict, tipo_mensaje: str = "ORM", msg_id: str = None) -> str:
    tipo = tipo_mensaje.upper()
    mapeos = obtener_mapeos(tipo) or DEFAULT_MAPEOS.get(tipo, {})
    valores_fijos = obtener_valores_fijos(tipo)

    # Solo se consulta la equivalencia del estudio si algun valor fijo la usa.
    contexto = {}
    if any("{codigo_estudio}" in v or "{descripcion_estudio}" in v for v in valores_fijos.values()):
        eq = equivalencias_repo.buscar(payload_dicom.get("00321060"))
        if eq:
            contexto = {"codigo_estudio": eq["codigo_destino"],
                        "descripcion_estudio": eq["descripcion_destino"]}

    return construir_mensaje(payload_dicom, mapeos, valores_fijos, tipo,
                             msg_id=msg_id, contexto=contexto)
