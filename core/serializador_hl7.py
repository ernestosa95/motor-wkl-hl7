"""Serializador HL7 v2.5 dirigido por el mapeo + valores fijos configurados."""
import uuid
import datetime

CONFIG = {
    "ADT": {
        "tipo_mensaje": "ADT^A04",
        "segmentos": ["MSH", "EVN", "PID", "PV1"],
        "fijos": {
            "MSH": {5: "HIS", 6: "DESTINO", 11: "P", 12: "2.5"},
            "EVN": {1: "A04"},
            "PID": {1: "1"},
            "PV1": {1: "1", 2: "N"},
        },
    },
    "ORM": {
        "tipo_mensaje": "ORM^O01",
        "segmentos": ["MSH", "PID", "ORC", "OBR"],
        "fijos": {
            "MSH": {5: "RIS", 6: "DESTINO", 11: "P", 12: "2.5"},
            "PID": {1: "1"},
            "ORC": {1: "NW"},
            "OBR": {1: "1"},
        },
    },
}

SENDING_APP = "MOTOR_DICOM"
SENDING_FACILITY = "TECNOIMAGEN"


def _set_campo(segmentos, disponibles, campo, valor):
    try:
        seg, idx = campo.split("-")
        idx = int(idx)
    except (ValueError, AttributeError):
        return
    if seg in disponibles:
        segmentos[seg][idx] = valor


def construir_mensaje(payload_dicom: dict, mapeos: dict, valores_fijos: dict, tipo: str) -> str:
    tipo = tipo.upper()
    if tipo not in CONFIG:
        raise ValueError(f"Tipo de mensaje no soportado: {tipo}")

    cfg = CONFIG[tipo]
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    msg_id = uuid.uuid4().hex[:10].upper()

    segmentos = {nombre: dict(cfg["fijos"].get(nombre, {})) for nombre in cfg["segmentos"]}
    disponibles = set(cfg["segmentos"])

    # MSH automático.
    segmentos["MSH"].update({
        2: "^~\\&", 3: SENDING_APP, 4: SENDING_FACILITY,
        7: timestamp, 9: cfg["tipo_mensaje"], 10: msg_id,
    })
    if "EVN" in segmentos:
        segmentos["EVN"][2] = timestamp

    # 1) Mapeo de valores DICOM.
    for tag, campos in (mapeos or {}).items():
        valor = payload_dicom.get(tag, "")
        if valor == "" or valor is None:
            continue
        for campo in campos:
            _set_campo(segmentos, disponibles, campo, valor)

    # 2) Valores fijos definidos por el usuario (sobrescriben).
    for campo, valor in (valores_fijos or {}).items():
        if valor is not None and str(valor) != "":
            _set_campo(segmentos, disponibles, campo, str(valor))

    # Serialización.
    lineas = []
    for nombre in cfg["segmentos"]:
        campos = segmentos[nombre]
        inicio = 2 if nombre == "MSH" else 1
        maximo = max(campos.keys()) if campos else inicio
        cuerpo = "|".join(campos.get(i, "") for i in range(inicio, maximo + 1))
        lineas.append(f"{nombre}|{cuerpo}")

    return "\r".join(lineas)
