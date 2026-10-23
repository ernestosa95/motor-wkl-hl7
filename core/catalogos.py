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
    # Datos extra del worklist (si el servidor los entrega)
    {"tag": "00401001", "nombre": "Requested Procedure ID"},
    {"tag": "00321064", "nombre": "Requested Procedure Code Value"},
    {"tag": "00400009", "nombre": "Scheduled Procedure Step ID"},
    {"tag": "00400007", "nombre": "Scheduled Procedure Step Description"},
    {"tag": "00400003", "nombre": "Scheduled Procedure Step Start Time"},
    {"tag": "00400001", "nombre": "Scheduled Station AE Title"},
]

# Campos HL7 destino, agrupados por segmento. Sirven como destino de un tag DICOM
# y/o como "valor fijo" (constante). "SEG-N.M" es el componente M del campo N
# (ej. PID-3.4 = autoridad asignadora del ID); se aplica sobre lo que ya tenga el
# campo, asi el ID del paciente se conserva.
CATALOGO_HL7 = [
    # --- MSH: cabecera. MSH-1, 2, 7 y 10 los genera el motor ---
    {"campo": "MSH-3",  "segmento": "MSH", "descripcion": "Aplicación emisora (def. SISGH)"},
    {"campo": "MSH-4",  "segmento": "MSH", "descripcion": "Establecimiento emisor (def. ARP03)"},
    {"campo": "MSH-5",  "segmento": "MSH", "descripcion": "Aplicación receptora"},
    {"campo": "MSH-6",  "segmento": "MSH", "descripcion": "Establecimiento receptor"},
    {"campo": "MSH-9",  "segmento": "MSH", "descripcion": "Tipo de mensaje (ej. ADT^A04^ADT_A01)"},
    {"campo": "MSH-11", "segmento": "MSH", "descripcion": "Processing ID (P producción / T prueba)"},
    {"campo": "MSH-12", "segmento": "MSH", "descripcion": "Versión HL7 (def. 2.5)"},
    {"campo": "MSH-15", "segmento": "MSH", "descripcion": "Accept ack type (AL / NE)"},
    {"campo": "MSH-16", "segmento": "MSH", "descripcion": "Application ack type (AL / NE)"},
    {"campo": "MSH-17", "segmento": "MSH", "descripcion": "País (ej. ARG)"},
    {"campo": "MSH-18", "segmento": "MSH", "descripcion": "Charset (ej. UTF-8, 8859/1)"},
    {"campo": "MSH-19", "segmento": "MSH", "descripcion": "Idioma (ej. es)"},
    # --- EVN ---
    {"campo": "EVN-1",  "segmento": "EVN", "descripcion": "Código de evento (def. A04)"},
    {"campo": "EVN-4",  "segmento": "EVN", "descripcion": "Motivo del evento"},
    {"campo": "EVN-5",  "segmento": "EVN", "descripcion": "Operador"},
    {"campo": "EVN-7",  "segmento": "EVN", "descripcion": "Establecimiento del evento"},
    # --- PID ---
    {"campo": "PID-2",    "segmento": "PID", "descripcion": "ID del paciente (externo)"},
    {"campo": "PID-3",    "segmento": "PID", "descripcion": "ID del paciente"},
    {"campo": "PID-3.4",  "segmento": "PID", "descripcion": "ID paciente: autoridad asignadora"},
    {"campo": "PID-3.5",  "segmento": "PID", "descripcion": "ID paciente: tipo de ID (ej. DNI, MR)"},
    {"campo": "PID-4",    "segmento": "PID", "descripcion": "ID alternativo del paciente"},
    {"campo": "PID-5",    "segmento": "PID", "descripcion": "Nombre del paciente"},
    {"campo": "PID-5.7",  "segmento": "PID", "descripcion": "Nombre: tipo (ej. L legal)"},
    {"campo": "PID-6",    "segmento": "PID", "descripcion": "Apellido de soltera de la madre"},
    {"campo": "PID-7",    "segmento": "PID", "descripcion": "Fecha de nacimiento"},
    {"campo": "PID-8",    "segmento": "PID", "descripcion": "Sexo"},
    {"campo": "PID-10",   "segmento": "PID", "descripcion": "Raza"},
    {"campo": "PID-11",   "segmento": "PID", "descripcion": "Domicilio"},
    {"campo": "PID-13",   "segmento": "PID", "descripcion": "Teléfono"},
    {"campo": "PID-15",   "segmento": "PID", "descripcion": "Idioma principal"},
    {"campo": "PID-16",   "segmento": "PID", "descripcion": "Estado civil"},
    {"campo": "PID-18",   "segmento": "PID", "descripcion": "Nº de cuenta del paciente"},
    {"campo": "PID-19",   "segmento": "PID", "descripcion": "Documento / SSN"},
    {"campo": "PID-28",   "segmento": "PID", "descripcion": "Nacionalidad"},
    # --- PV1 ---
    {"campo": "PV1-2",  "segmento": "PV1", "descripcion": "Clase de paciente (O, I, E, N)"},
    {"campo": "PV1-3",  "segmento": "PV1", "descripcion": "Ubicación (servicio^sala^cama)"},
    {"campo": "PV1-4",  "segmento": "PV1", "descripcion": "Tipo de admisión"},
    {"campo": "PV1-7",  "segmento": "PV1", "descripcion": "Médico de atención"},
    {"campo": "PV1-8",  "segmento": "PV1", "descripcion": "Médico derivante"},
    {"campo": "PV1-10", "segmento": "PV1", "descripcion": "Servicio / modalidad"},
    {"campo": "PV1-14", "segmento": "PV1", "descripcion": "Fuente de admisión"},
    {"campo": "PV1-17", "segmento": "PV1", "descripcion": "Médico que admite"},
    {"campo": "PV1-18", "segmento": "PV1", "descripcion": "Tipo de paciente"},
    {"campo": "PV1-19", "segmento": "PV1", "descripcion": "Nº de visita / episodio"},
    {"campo": "PV1-39", "segmento": "PV1", "descripcion": "Establecimiento de servicio"},
    {"campo": "PV1-44", "segmento": "PV1", "descripcion": "Fecha/hora de admisión"},
    # --- ORC ---
    {"campo": "ORC-1",  "segmento": "ORC", "descripcion": "Control de orden (def. NW)"},
    {"campo": "ORC-2",  "segmento": "ORC", "descripcion": "Nº de orden"},
    {"campo": "ORC-3",  "segmento": "ORC", "descripcion": "Nº de orden (filler)"},
    {"campo": "ORC-4",  "segmento": "ORC", "descripcion": "Nº de grupo de orden (placer group)"},
    {"campo": "ORC-5",  "segmento": "ORC", "descripcion": "Estado de la orden"},
    {"campo": "ORC-7",  "segmento": "ORC", "descripcion": "Cantidad/tiempo; ORC-7.4 = fecha/hora de la cita (ej. 1^^^{cita}^^1)"},
    {"campo": "ORC-9",  "segmento": "ORC", "descripcion": "Fecha/hora de la transacción"},
    {"campo": "ORC-12", "segmento": "ORC", "descripcion": "Médico que ordena"},
    {"campo": "ORC-13", "segmento": "ORC", "descripcion": "Ubicación de quien ordena"},
    {"campo": "ORC-17", "segmento": "ORC", "descripcion": "Organización que ingresa la orden (ej. 02020501^O)"},
    # --- OBR ---
    {"campo": "OBR-2",  "segmento": "OBR", "descripcion": "Nº de orden (placer)"},
    {"campo": "OBR-3",  "segmento": "OBR", "descripcion": "Nº de orden (filler / accession)"},
    {"campo": "OBR-4",  "segmento": "OBR", "descripcion": "Procedimiento (ej. {codigo_estudio}^{descripcion_estudio})"},
    {"campo": "OBR-4.1", "segmento": "OBR", "descripcion": "Procedimiento: código"},
    {"campo": "OBR-4.3", "segmento": "OBR", "descripcion": "Procedimiento: sistema de codificación"},
    {"campo": "OBR-5",  "segmento": "OBR", "descripcion": "Prioridad"},
    {"campo": "OBR-7",  "segmento": "OBR", "descripcion": "Fecha/hora de observación"},
    {"campo": "OBR-16", "segmento": "OBR", "descripcion": "Médico solicitante"},
    {"campo": "OBR-18", "segmento": "OBR", "descripcion": "Unidad de negocio / centro de costo que realiza el estudio (ej. {unidad_negocio})"},
    {"campo": "OBR-19", "segmento": "OBR", "descripcion": "Campo libre (placer)"},
    {"campo": "OBR-24", "segmento": "OBR", "descripcion": "Modalidad / sección diagnóstica"},
    {"campo": "OBR-21", "segmento": "OBR", "descripcion": "Recurso / equipo donde se realiza el estudio (ej. {codigo_equipo})"},
    {"campo": "OBR-25", "segmento": "OBR", "descripcion": "(no usar: la especificacion del RIS usa OBR-27)"},
    {"campo": "OBR-27", "segmento": "OBR", "descripcion": "Cantidad/tiempo; OBR-27.4 = fecha/hora de la cita (ej. 1^^^{cita}^^1)"},
    {"campo": "OBR-31", "segmento": "OBR", "descripcion": "Motivo del estudio"},
]

# Segmentos que lleva cada tipo de mensaje (define qué campos son mapeables).
SEGMENTOS = {
    "ADT": ["MSH", "EVN", "PID", "PV1"],
    "ORM": ["MSH", "PID", "PV1", "ORC", "OBR"],
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
