import socket
import logging

from core.auditoria import actualizar_estado
from core.models import EstadoMensaje
from core import config_repo

log = logging.getLogger(__name__)

# Envoltorios estándar MLLP
VT = b'\x0b'   # inicio de bloque
FS = b'\x1c'   # fin de bloque
CR = b'\x0d'


def _destino(clave_canal: str = "destino_orm"):
    """Lee host/puerto del canal de salida configurado en la consola."""
    canal = config_repo.obtener_canal(clave_canal)
    if canal and canal.get("host") and canal.get("puerto"):
        return canal["host"], int(canal["puerto"])
    # Fallback seguro si el canal no existe todavía
    return "127.0.0.1", 2575


def enviar_mensaje_mllp(correlation_id, payload_hl7, host=None, puerto=None,
                        clave_canal="destino_orm"):
    """
    Envía el mensaje HL7 encapsulado en MLLP y espera el ACK síncrono.

    Si no se pasa host/puerto explícitos, los toma del canal configurado
    (por defecto 'destino_orm') en la base de datos.

    Manejo de estados:
      - ACK (MSA|AA)         -> COMPLETADO
      - NACK explícito        -> ERROR_PERMANENTE (no reintentar, el HL7 fue rechazado)
      - Error de conexión/red -> ERROR_EMISION (transitorio) y relanza para que
                                 Huey reintente segun la politica configurada.
    """
    if host is None or puerto is None:
        host, puerto = _destino(clave_canal)

    mensaje_bytes = VT + payload_hl7.encode('utf-8') + FS + CR

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(15.0)
            s.connect((host, puerto))
            s.sendall(mensaje_bytes)

            # Espera de ACK síncrono
            ack_data = s.recv(4096)

    except Exception as e:
        # Error transitorio de red: marcar ERROR_EMISION y relanzar para reintento.
        # Huey lo reintentará; si agota los reintentos, quedará en este estado.
        actualizar_estado(correlation_id, EstadoMensaje.ERROR_EMISION)
        log.error("Fallo de conexion MLLP a %s:%s para %s: %s",
                  host, puerto, correlation_id, e)
        raise e

    # Conexión OK: evaluar el ACK
    if b"MSA|AA" in ack_data:
        actualizar_estado(correlation_id, EstadoMensaje.COMPLETADO)
        log.info("ACK recibido. Orden %s COMPLETADA.", correlation_id)
    else:
        # El destino recibió pero rechazó el mensaje: error de contenido,
        # reintentar no ayuda -> permanente.
        actualizar_estado(correlation_id, EstadoMensaje.ERROR_PERMANENTE)
        log.error("NACK/respuesta invalida del destino para %s: %r",
                  correlation_id, ack_data[:120])
        # No relanzamos: es permanente, no tiene sentido que Huey reintente.