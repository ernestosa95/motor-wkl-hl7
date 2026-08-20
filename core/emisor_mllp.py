import socket
import logging
import datetime

from core.database import SessionLocal
from core.models import RegistroTrazabilidad, EstadoMensaje
from core.auditoria import actualizar_estado
from core import config_repo

log = logging.getLogger(__name__)

# Envoltorios estándar MLLP
VT = b'\x0b'
FS = b'\x1c'
CR = b'\x0d'


def _destino(clave_canal: str = "destino_orm"):
    canal = config_repo.obtener_canal(clave_canal)
    if canal and canal.get("host") and canal.get("puerto"):
        return canal["host"], int(canal["puerto"])
    return "127.0.0.1", 2575


def _guardar_error(correlation_id, texto: str):
    """Persiste el motivo del fallo en detalles_error para la auditoría."""
    db = SessionLocal()
    try:
        r = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        if r:
            r.detalles_error = {
                "mensaje": str(texto),
                "cuando": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            db.commit()
    except Exception as e:
        db.rollback()
        log.error("No se pudo guardar detalles_error para %s: %s", correlation_id, e)
    finally:
        db.close()


def enviar_mensaje_mllp(correlation_id, payload_hl7, host=None, puerto=None,
                        clave_canal="destino_orm"):
    """
    Envía el mensaje HL7 encapsulado en MLLP y espera el ACK síncrono.
    Guarda el motivo del fallo en detalles_error para auditoría.
    """
    if host is None or puerto is None:
        host, puerto = _destino(clave_canal)

    mensaje_bytes = VT + payload_hl7.encode('utf-8') + FS + CR

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(15.0)
            s.connect((host, puerto))
            s.sendall(mensaje_bytes)
            ack_data = s.recv(4096)
    except Exception as e:
        actualizar_estado(correlation_id, EstadoMensaje.ERROR_EMISION)
        _guardar_error(correlation_id, f"Fallo de conexion a {host}:{puerto} - {e}")
        log.error("Fallo de conexion MLLP a %s:%s para %s: %s",
                  host, puerto, correlation_id, e)
        raise e

    if b"MSA|AA" in ack_data:
        actualizar_estado(correlation_id, EstadoMensaje.COMPLETADO)
        log.info("ACK recibido. Orden %s COMPLETADA.", correlation_id)
    else:
        actualizar_estado(correlation_id, EstadoMensaje.ERROR_PERMANENTE)
        detalle = ack_data.decode('utf-8', errors='replace')[:200]
        _guardar_error(correlation_id, f"NACK o respuesta invalida del destino: {detalle}")
        log.error("NACK/respuesta invalida del destino para %s: %r",
                  correlation_id, ack_data[:120])
