"""Emisión HL7 sobre MLLP con validación del ACK.

Este módulo solo envía y valida: no toca la base. El estado del registro
(COMPLETADO / ERROR_EMISION / ERROR_PERMANENTE) lo decide el broker, que es
quien conoce cuántos reintentos quedan.
"""
import socket
import logging

log = logging.getLogger(__name__)

# Envoltorios estándar MLLP
VT = b'\x0b'
FS = b'\x1c'
CR = b'\x0d'

MAX_ACK_BYTES = 1024 * 1024


class ErrorEmision(Exception):
    """Falla de conexión, ACK negativo o ACK que no corresponde al mensaje."""


def control_id(payload_hl7: str) -> str:
    """MSH-10 (Message Control ID) del mensaje."""
    msh = payload_hl7.split("\r", 1)[0].split("|")
    return msh[9] if len(msh) > 9 else ""


def _leer_trama(sock: socket.socket) -> bytes:
    """Lee una trama MLLP completa (VT ... FS CR), aunque llegue en varios paquetes."""
    buffer = b""
    while FS not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            raise ErrorEmision("El destino cerró la conexión sin enviar un ACK completo.")
        buffer += chunk
        if len(buffer) > MAX_ACK_BYTES:
            raise ErrorEmision("ACK demasiado grande o sin delimitador MLLP.")
    inicio = buffer.find(VT)
    return buffer[inicio + 1 if inicio >= 0 else 0:buffer.find(FS)]


def _segmento_msa(ack: str):
    for linea in ack.replace("\n", "\r").split("\r"):
        if linea.startswith("MSA"):
            return linea.split("|")
    return None


def enviar_mensaje_mllp(payload_hl7: str, host: str, puerto: int, timeout: float = 15.0) -> str:
    """Envía el mensaje y valida el ACK. Devuelve el ACK como texto.

    Lanza ErrorEmision si no hay conexión, si el ACK es negativo (AE/AR/CE/CR)
    o si no corresponde al mensaje enviado (MSA-2 distinto de MSH-10).
    """
    esperado = control_id(payload_hl7)
    try:
        with socket.create_connection((host, int(puerto)), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(VT + payload_hl7.encode('utf-8') + FS + CR)
            ack = _leer_trama(s).decode('utf-8', errors='replace')
    except ErrorEmision:
        raise
    except OSError as e:
        raise ErrorEmision(f"Fallo de conexion a {host}:{puerto} - {e}") from e

    msa = _segmento_msa(ack)
    if msa is None or len(msa) < 2:
        raise ErrorEmision(f"Respuesta sin segmento MSA: {ack[:200]!r}")

    codigo = msa[1]
    if codigo not in ("AA", "CA"):
        texto = msa[3] if len(msa) > 3 else ""
        raise ErrorEmision(f"ACK negativo {codigo} del destino. {texto}".strip())

    recibido = msa[2] if len(msa) > 2 else ""
    if recibido != esperado:
        raise ErrorEmision(
            f"El ACK no corresponde al mensaje enviado (MSA-2={recibido!r}, MSH-10={esperado!r})."
        )
    log.debug("ACK %s recibido de %s:%s para MSH-10=%s", codigo, host, puerto, esperado)
    return ack
