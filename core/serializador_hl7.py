"""Serializador HL7 v2.5 dirigido por el mapeo + valores fijos configurados."""
import os
import re
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
        "segmentos": ["MSH", "PID", "PV1", "ORC", "OBR"],
        "fijos": {
            "MSH": {5: "RIS", 6: "DESTINO", 11: "P", 12: "2.5"},
            "PID": {1: "1"},
            "PV1": {1: "1", 2: "O"},
            "ORC": {1: "NW"},
            "OBR": {1: "1"},
        },
    },
}

# Identidad del emisor (MSH-3 / MSH-4) que valida el canal de Mirth.
SENDING_APP = os.environ.get("HL7_SENDING_APP", "SISGH")
SENDING_FACILITY = os.environ.get("HL7_SENDING_FACILITY", "ARP03")


def escapar(valor) -> str:
    """Escapa los delimitadores HL7 (| ~ \\ &) y quita saltos de linea.

    El '^' se conserva a proposito: en DICOM (PN) tambien separa componentes
    (APELLIDO^NOMBRE) y se traslada tal cual al componente HL7.
    """
    s = str(valor)
    s = s.replace("\\", "\\E\\")  # primero la barra, para no re-escapar lo siguiente
    s = s.replace("|", "\\F\\").replace("~", "\\R\\").replace("&", "\\T\\")
    return s.replace("\r", " ").replace("\n", " ")


# {00100020} -> valor del tag DICOM; {00100010:apellido} / {00100010:nombres} -> parte del nombre.
# {ahora} -> fecha/hora del mensaje (la misma de MSH-7).
# {codigo_estudio} / {descripcion_estudio} -> equivalencia del estudio en el destino.
_PLANTILLA = re.compile(r"\{(?:([0-9A-Fa-f]{8})(?::([a-z]+))?|([a-z_]+))\}")


class EstudioSinCodigo(Exception):
    """El estudio del worklist no tiene equivalencia cargada en el destino."""


def _valor_derivado(payload: dict, tag: str, parte) -> str:
    v = str(payload.get(tag, "") or "")
    if parte not in ("apellido", "nombres"):
        return v
    if "^" in v:  # formato DICOM: APELLIDO^NOMBRE[^...]
        comps = v.split("^")
        apellido, nombres = comps[0], " ".join(c for c in comps[1:] if c)
    else:  # el worklist trae "APELLIDO NOMBRES": primera palabra = apellido
        palabras = v.split(None, 1)
        apellido = palabras[0] if palabras else ""
        nombres = palabras[1] if len(palabras) > 1 else ""
    return apellido if parte == "apellido" else nombres


def _marcador(nombre: str, payload: dict, ahora: str, contexto: dict) -> str:
    if nombre == "ahora":
        return ahora
    if nombre in ("codigo_estudio", "descripcion_estudio"):
        if nombre not in contexto:
            raise EstudioSinCodigo(
                "Estudio sin codigo de equivalencia: %r. Cargalo en Estudios y reprocesa."
                % (payload.get("00321060", ""),))
        return escapar(contexto[nombre])
    raise ValueError("Marcador desconocido: {%s}" % nombre)


def _renderizar_fijo(valor: str, payload: dict, ahora: str = "", contexto: dict = None) -> str:
    """Un valor fijo es HL7 literal (^ ~ & se respetan tal cual). Solo los datos
    DICOM insertados con {tag} se escapan; se quitan los saltos de linea."""
    texto = _PLANTILLA.sub(
        lambda m: _marcador(m.group(3), payload, ahora, contexto or {}) if m.group(3)
        else escapar(_valor_derivado(payload, m.group(1), m.group(2))),
        valor)
    return texto.replace("\r", " ").replace("\n", " ")


def _set_campo(segmentos, disponibles, campo, valor, crudo=False):
    """Escribe 'SEG-N' (campo completo) o 'SEG-N.M' (componente M del campo N).

    El componente se aplica sobre lo que el campo ya tenga, asi se puede agregar
    p. ej. la autoridad asignadora (PID-3.4) sin perder el ID mapeado en PID-3.
    crudo=True escribe el valor tal cual (ya es HL7); si no, se escapa.
    """
    try:
        ref, _, comp = campo.partition(".")
        seg, idx = ref.split("-")
        idx = int(idx)
        comp = int(comp) if comp else 0
    except (ValueError, AttributeError):
        return
    if seg not in disponibles:
        return
    if not crudo:
        valor = escapar(valor)
    if not comp:
        segmentos[seg][idx] = valor
        return
    partes = segmentos[seg].get(idx, "").split("^")
    partes += [""] * (comp - len(partes))
    partes[comp - 1] = valor
    segmentos[seg][idx] = "^".join(partes)


def construir_mensaje(payload_dicom: dict, mapeos: dict, valores_fijos: dict, tipo: str,
                      msg_id: str = None, contexto: dict = None) -> str:
    tipo = tipo.upper()
    if tipo not in CONFIG:
        raise ValueError(f"Tipo de mensaje no soportado: {tipo}")

    cfg = CONFIG[tipo]
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    msg_id = msg_id or uuid.uuid4().hex[:10].upper()

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
    # Primero los campos completos y luego los componentes ("PID-3.4"), para que
    # estos ultimos se apliquen sobre el valor final del campo.
    for campo, valor in sorted((valores_fijos or {}).items(), key=lambda kv: "." in kv[0]):
        if valor is not None and str(valor) != "":
            _set_campo(segmentos, disponibles, campo,
                       _renderizar_fijo(str(valor), payload_dicom, timestamp, contexto), crudo=True)

    # Serialización.
    lineas = []
    for nombre in cfg["segmentos"]:
        campos = segmentos[nombre]
        inicio = 2 if nombre == "MSH" else 1
        maximo = max(campos.keys()) if campos else inicio
        cuerpo = "|".join(campos.get(i, "") for i in range(inicio, maximo + 1))
        lineas.append(f"{nombre}|{cuerpo}")

    return "\r".join(lineas)
