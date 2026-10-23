import os
import logging
import datetime

from huey import SqliteHuey
from core.transformador import procesar_transformacion
from core.serializador_hl7 import DatoSinEquivalencia
from core.auditoria import actualizar_envio, obtener_hl7
from core.emisor_mllp import enviar_mensaje_mllp, control_id, ErrorEmision
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

# Reintentos automaticos ante fallas de emision (red caida, NACK, timeout).
REINTENTOS = int(os.environ.get("MLLP_REINTENTOS", "3"))
RETRY_DELAY = int(os.environ.get("MLLP_RETRY_DELAY", "30"))  # segundos

# (clave en payload_hl7, clave del canal destino, etiqueta)
DESTINOS = (("adt", "destino_adt", "ADT"), ("orm", "destino_orm", "ORM"))


def _ahora() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _destino(clave):
    """Host y puerto del canal. Sin canal configurado no se envia a ningun lado."""
    canal = config_repo.obtener_canal(clave)
    if canal and canal.get("host") and canal.get("puerto"):
        return canal["host"], int(canal["puerto"])
    raise ErrorEmision(f"El canal '{clave}' no tiene host/puerto configurado.")


def _generar(correlation_id, payload_dicom, tipo):
    """HL7 de UN mensaje con la configuracion VIGENTE (mapeo, valores fijos, equivalencias).

    Se regenera en cada intento, asi un cambio de configuracion se aplica al reenviar.
    Se conserva el MSH-10 del mensaje previo, para que el destino detecte duplicados.
    Lanza DatoSinEquivalencia si falta la equivalencia del estudio o el equipo de su modalidad.
    """
    previo = (obtener_hl7(correlation_id) or {}).get(tipo)
    return procesar_transformacion(
        payload_dicom, tipo.upper(),
        msg_id=(control_id(previo) or None) if previo else None,
    )


@huey.task(retries=REINTENTOS, retry_delay=RETRY_DELAY, context=True)
def tarea_enviar_mensaje(correlation_id, payload_dicom, tipo, task=None):
    """Genera y envia UN mensaje (tipo 'adt' | 'orm') a su destino.

    Cada mensaje es independiente de su par: tiene su propia tarea, sus propios
    reintentos y su propio estado en payload_hl7["envios"][tipo]. Que el ORM falle
    no afecta al ADT ya aceptado (ni al reves). El estado de la orden se deriva de
    ambos (auditoria.estado_orden).
    """
    quedan = task.retries if task is not None else 0
    _, clave_canal, etiqueta = next(d for d in DESTINOS if d[0] == tipo)

    previo = ((obtener_hl7(correlation_id) or {}).get("envios") or {}).get(tipo) or {}
    if previo.get("ok"):
        return  # ya aceptado: no se reenvia

    error, reintentable = None, True
    try:
        mensaje = _generar(correlation_id, payload_dicom, tipo)
        actualizar_envio(correlation_id, tipo, {"estado": "PENDIENTE"}, mensaje=mensaje)
        host, puerto = _destino(clave_canal)
        ack = enviar_mensaje_mllp(mensaje, host=host, puerto=puerto)
    except DatoSinEquivalencia as e:
        error = str(e)  # se resuelve en Estudios (equivalencia o equipo): los reintentos lo recogen
    except ErrorEmision as e:
        error = str(e)
    except Exception as e:
        # Fallo de transformacion o de otro tipo (mapeo mal, payload invalido): no es
        # de red, reintentar no lo arregla.
        log.exception("[%s] fallo inesperado para %s", etiqueta, correlation_id)
        error, reintentable = f"Fallo de transformacion: {e}", False

    if error is None:
        actualizar_envio(correlation_id, tipo, {
            "ok": True, "estado": "ENVIADO", "destino": f"{host}:{puerto}",
            "cuando": _ahora(), "ack": ack, "ultimo_error": None,
        })
        log.info("[%s] aceptado (ACK) para %s -> %s:%s", etiqueta, correlation_id, host, puerto)
        return

    final = quedan == 0 or not reintentable
    log.warning("[%s] %s para %s (quedan %s reintentos)", etiqueta, error, correlation_id, quedan)
    actual = ((obtener_hl7(correlation_id) or {}).get("envios") or {}).get(tipo) or {}
    actualizar_envio(correlation_id, tipo, {
        "ok": False,
        "estado": "ERROR_PERMANENTE" if final else "PENDIENTE",
        "ultimo_error": error,
        "ultimo_intento": _ahora(),
        "intentos_fallidos": int(actual.get("intentos_fallidos", 0)) + 1,
    })
    if not final:
        # Huey la reencola despues de RETRY_DELAY segundos.
        raise ErrorEmision(f"{etiqueta} pendiente: {error}")


def tarea_procesar_orden(correlation_id, payload_dicom):
    """Encola el envio de ADT y de ORM como tareas independientes.

    ADT primero (el paciente debe existir antes que la orden), pero ninguno espera
    al otro ni comparte reintentos con el.
    """
    for tipo, _, _ in DESTINOS:
        tarea_enviar_mensaje(correlation_id, payload_dicom, tipo)
