import os
import logging
import datetime

from huey import SqliteHuey
from core.transformador import procesar_transformacion
from core.auditoria import actualizar_estado, guardar_hl7, obtener_hl7, registrar_fallo
from core.emisor_mllp import enviar_mensaje_mllp, control_id, ErrorEmision
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


def _obtener_o_transformar(correlation_id, payload_dicom) -> dict:
    """Genera los HL7 pendientes con la configuracion de mapeo VIGENTE.

    En cada intento (automatico o 'Reprocesar') se regeneran ADT/ORM que aun no
    fueron aceptados, asi un cambio de mapeo o de valores fijos se aplica al
    reenviar. Se conserva el MSH-10 original, para que el destino pueda detectar
    duplicados. Lo ya aceptado (envios[tipo].ok) no se toca ni se reenvia.
    """
    mensajes = obtener_hl7(correlation_id) or {}
    envios = mensajes.setdefault("envios", {})
    primera_vez = not (mensajes.get("adt") or mensajes.get("orm"))

    for tipo in ("adt", "orm"):
        if envios.get(tipo, {}).get("ok") and mensajes.get(tipo):
            continue
        previo = mensajes.get(tipo)
        mensajes[tipo] = procesar_transformacion(
            payload_dicom, tipo.upper(),
            msg_id=(control_id(previo) or None) if previo else None,
        )

    guardar_hl7(correlation_id, mensajes)
    if primera_vez:
        actualizar_estado(correlation_id, EstadoMensaje.TRANSFORMADO)
    return mensajes


def _emitir(correlation_id, mensajes, tipo, clave_canal, etiqueta):
    """Emite un mensaje a su destino. Devuelve None si salio OK, o el error.

    No relanza: ADT y ORM son independientes, un fallo en uno no aborta el otro.
    """
    try:
        host, puerto = _destino(clave_canal)
        ack = enviar_mensaje_mllp(mensajes[tipo], host=host, puerto=puerto)
    except Exception as e:
        log.error("[%s] fallo de emision para %s: %s", etiqueta, correlation_id, e)
        return str(e)

    mensajes["envios"][tipo] = {"ok": True, "destino": f"{host}:{puerto}",
                                "cuando": _ahora(), "ack": ack}
    guardar_hl7(correlation_id, mensajes)
    log.info("[%s] aceptado (ACK) para %s -> %s:%s", etiqueta, correlation_id, host, puerto)
    return None


@huey.task(retries=REINTENTOS, retry_delay=RETRY_DELAY, context=True)
def tarea_procesar_orden(correlation_id, payload_dicom, task=None):
    """Transforma a ADT + ORM, guarda el HL7 y despacha cada uno a su destino.

    ADT primero, ORM despues, de forma independiente. Cada envio aceptado queda
    registrado en payload_hl7["envios"]; si falta alguno, la tarea se reintenta
    y solo se reenvia lo pendiente. COMPLETADO unicamente con ADT y ORM aceptados.
    """
    quedan = task.retries if task is not None else 0

    try:
        mensajes = _obtener_o_transformar(correlation_id, payload_dicom)
    except Exception as e:
        # Fallo de transformacion (mapeo mal, payload invalido): no es de red,
        # reintentar no lo arregla.
        log.exception("Fallo de transformacion para %s", correlation_id)
        registrar_fallo(correlation_id, final=True, detalle={
            "mensaje": f"Fallo de transformacion: {e}", "cuando": _ahora(), "etapa": "transformacion",
        })
        return

    errores = {}
    for tipo, clave_canal, etiqueta in DESTINOS:
        if mensajes["envios"].get(tipo, {}).get("ok"):
            continue  # ya aceptado en un intento anterior: no se reenvia
        error = _emitir(correlation_id, mensajes, tipo, clave_canal, etiqueta)
        if error:
            errores[etiqueta] = error

    if not errores:
        actualizar_estado(correlation_id, EstadoMensaje.COMPLETADO)
        log.info("Orden %s COMPLETADA (ADT+ORM aceptados).", correlation_id)
        return

    final = quedan == 0
    registrar_fallo(correlation_id, final=final, detalle={
        "mensaje": " | ".join(f"{k}: {v}" for k, v in errores.items()),
        "cuando": _ahora(),
        "pendientes": list(errores),
        "reintentos_restantes": quedan,
    })
    log.warning("Orden %s con envios pendientes %s (quedan %s reintentos).",
                correlation_id, list(errores), quedan)
    if not final:
        # Huey la reencola despues de RETRY_DELAY segundos.
        raise ErrorEmision(f"Envios pendientes: {', '.join(errores)}")
