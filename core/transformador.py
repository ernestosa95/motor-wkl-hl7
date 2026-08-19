"""Transformación DICOM -> HL7 dirigida por el mapeo y valores fijos de la base."""
from core.serializador_hl7 import construir_mensaje
from core.mapeo_repo import obtener_mapeos, obtener_valores_fijos
from core.catalogos import DEFAULT_MAPEOS


def procesar_transformacion(payload_dicom: dict, tipo_mensaje: str = "ORM") -> str:
    tipo = tipo_mensaje.upper()
    mapeos = obtener_mapeos(tipo) or DEFAULT_MAPEOS.get(tipo, {})
    valores_fijos = obtener_valores_fijos(tipo)
    return construir_mensaje(payload_dicom, mapeos, valores_fijos, tipo)
