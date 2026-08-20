import os
import logging
from huey import SqliteHuey
from core.transformador import procesar_transformacion
from core.auditoria import actualizar_estado, guardar_hl7
from core.emisor_mllp import enviar_mensaje_mllp
from core.models import EstadoMensaje
from core import config_repo

log = logging.getLogger(__name__)


def _data_dir() -> str:
    """
    Directorio escribible para la cola SQLite de Huey.
    Empaquetado corre como servicio bajo Program Files (solo lectura),
    por eso la cola debe vivir en ProgramData\\MotorDICOM (via MOTORDICOM_DATA).
    """
    root = os.environ.get(
        "MOTORDICOM_DATA",
        os.path.join(os.environ.get("ProgramData", os.getcwd()), "MotorDICOM"),
    )
    os.makedirs(root, exist_ok=True)
    return root


huey = SqliteHuey(filename=os.path.join(_data_dir(), "motor_queue.db"))

FALLBACK = {"host": "127.0.0.1", "puerto": 2575}


def _destino(clave):
    canal = config_repo.obtener_canal(clave)
    if canal and canal.get("host") and canal.get("puerto"):
        return canal["host"], int(canal["puerto"])
    return FALLBACK["host"], FALLBACK["puerto"]


def _emitir(correlation_id, hl7, clave_canal, etiqueta):
    """Emite un mensaje a su destino de forma aislada. Devuelve True si salio OK.

    No relanza la excepcion: cada mensaje (ADT/ORM) es independiente, por eso
    un fallo en uno no debe abortar el otro ni disparar el reintento global.
    """
    host, puerto = _destino(clave_canal)
    try:
        enviar_mensaje_mllp(correlation_id, hl7, host=host, puerto=puerto,
                            clave_canal=clave_canal)
        log.info("[%s] emitido OK para %s -> %s:%s", etiqueta, correlation_id, host, puerto)
        return True
    except Exception as e:
        log.error("[%s] fallo de emision para %s -> %s:%s: %s",
                  etiqueta, correlation_id, host, puerto, e)
        return False


@huey.task()
def tarea_procesar_orden(correlation_id, payload_dicom):
    """Transforma a ADT + ORM, guarda el HL7 y despacha cada uno a su destino.

    ADT primero, ORM despues. Independientes: si el ADT falla, la ORM se envia
    igual. El estado final se decide segun el resultado de ambas emisiones.
    """
    try:
        hl7_adt = procesar_transformacion(payload_dicom, "ADT")
        hl7_orm = procesar_transformacion(payload_dicom, "ORM")
    except Exception:
        # Fallo de transformacion (mapeo mal, payload invalido): no es de red.
        actualizar_estado(correlation_id, EstadoMensaje.ERROR_PERMANENTE)
        log.exception("Fallo de transformacion para %s", correlation_id)
        return

    actualizar_estado(correlation_id, EstadoMensaje.TRANSFORMADO)
    guardar_hl7(correlation_id, {"adt": hl7_adt, "orm": hl7_orm})

    # Emision secuencial e independiente
    ok_adt = _emitir(correlation_id, hl7_adt, "destino_adt", "ADT")
    ok_orm = _emitir(correlation_id, hl7_orm, "destino_orm", "ORM")

    # Estado final: COMPLETADO solo si ambos salieron; si no, error de emision.
    if ok_adt and ok_orm:
        actualizar_estado(correlation_id, EstadoMensaje.COMPLETADO)
        log.info("Orden %s COMPLETADA (ADT+ORM emitidos).", correlation_id)
    else:
        actualizar_estado(correlation_id, EstadoMensaje.ERROR_EMISION)
        log.warning("Orden %s parcial/fallida (ADT ok=%s, ORM ok=%s).",
                    correlation_id, ok_adt, ok_orm)