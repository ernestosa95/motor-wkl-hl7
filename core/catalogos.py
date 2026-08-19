"""Catálogos DICOM/HL7 y mapeos por defecto (separados por tipo de mensaje)."""

# Tags DICOM que el motor captura desde la Worklist.
CATALOGO_DICOM = [
    {"tag": "00100020", "nombre": "Patient ID"},
    {"tag": "00100010", "nombre": "Patient's Name"},
    {"tag": "00100030", "nombre": "Patient's Birth Date"},
    {"tag": "00100040", "nombre": "Patient's Sex"},
    {"tag": "00080050", "nombre": "Accession Number"},
    {"tag": "00321060", "nombre": "Requested Procedure Description"},
    {"tag": "00080090", "nombre": "Referring Physician's Name"},
    {"tag": "00080060", "nombre": "Modality"},
    {"tag": "00400002", "nombre": "Scheduled Procedure Step Start Date"},
]

# Campos HL7 destino, agrupados por segmento.
CATALOGO_HL7 = [
    {"campo": "PID-3",  "segmento": "PID", "descripcion": "ID del paciente"},
    {"campo": "PID-5",  "segmento": "PID", "descripcion": "Nombre del paciente"},
    {"campo": "PID-7",  "segmento": "PID", "descripcion": "Fecha de nacimiento"},
    {"campo": "PID-8",  "segmento": "PID", "descripcion": "Sexo"},
    {"campo": "PV1-7",  "segmento": "PV1", "descripcion": "Médico de atención"},
    {"campo": "PV1-10", "segmento": "PV1", "descripcion": "Servicio / modalidad"},
    {"campo": "ORC-2",  "segmento": "ORC", "descripcion": "Nº de orden"},
    {"campo": "OBR-2",  "segmento": "OBR", "descripcion": "Nº de orden (placer)"},
    {"campo": "OBR-3",  "segmento": "OBR", "descripcion": "Nº de orden (filler / accession)"},
    {"campo": "OBR-4",  "segmento": "OBR", "descripcion": "Descripción del procedimiento"},
    {"campo": "OBR-16", "segmento": "OBR", "descripcion": "Médico solicitante"},
    {"campo": "OBR-24", "segmento": "OBR", "descripcion": "Modalidad / sección diagnóstica"},
    {"campo": "OBR-27", "segmento": "OBR", "descripcion": "Fecha/hora programada"},
]

# Segmentos que lleva cada tipo de mensaje (define qué campos son mapeables).
SEGMENTOS = {
    "ADT": ["MSH", "EVN", "PID", "PV1"],
    "ORM": ["MSH", "PID", "ORC", "OBR"],
}

# Mapeos por defecto (plantillas precargadas), uno por tipo de mensaje.
DEFAULT_MAPEOS = {
    "ADT": {
        "00100020": ["PID-3"],
        "00100010": ["PID-5"],
        "00100030": ["PID-7"],
        "00100040": ["PID-8"],
        "00080090": ["PV1-7"],
        "00080060": ["PV1-10"],
    },
    "ORM": {
        "00100020": ["PID-3"],
        "00100010": ["PID-5"],
        "00100030": ["PID-7"],
        "00100040": ["PID-8"],
        "00080050": ["ORC-2", "OBR-2", "OBR-3"],
        "00321060": ["OBR-4"],
        "00080090": ["OBR-16"],
        "00080060": ["OBR-24"],
        "00400002": ["OBR-27"],
    },
}

# Valores fijos por defecto (vacío; el usuario los agrega en Opciones avanzadas).
DEFAULT_VALORES_FIJOS = {"ADT": {}, "ORM": {}}


def display_tag(tag: str) -> str:
    return f"({tag[:4]},{tag[4:]})" if len(tag) == 8 else tag


def campos_hl7_por_tipo(tipo: str):
    """Campos HL7 mapeables para un tipo de mensaje (según sus segmentos)."""
    segs = set(SEGMENTOS.get(tipo, []))
    return [c for c in CATALOGO_HL7 if c["segmento"] in segs]
