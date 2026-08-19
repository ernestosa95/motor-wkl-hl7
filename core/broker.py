import os
from huey import SqliteHuey
from core.transformador import procesar_transformacion
from core.auditoria import actualizar_estado, guardar_hl7
from core.emisor_mllp import enviar_mensaje_mllp
from core.models import EstadoMensaje
from core import config_repo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
huey = SqliteHuey(filename=os.path.join(BASE_DIR, "motor_queue.db"))

FALLBACK = {"host": "127.0.0.1", "puerto": 2575}


def _destino(clave):
    canal = config_repo.obtener_canal(clave)
    if canal:
        return canal["host"], int(canal["puerto"])
    return FALLBACK["host"], FALLBACK["puerto"]


@huey.task(retries=3, retry_delay=10)
def tarea_procesar_orden(correlation_id, payload_dicom):
    """Transforma a ADT + ORM, guarda el HL7 y despacha cada uno a su destino."""
    try:
        hl7_adt = procesar_transformacion(payload_dicom, "ADT")
        hl7_orm = procesar_transformacion(payload_dicom, "ORM")

        actualizar_estado(correlation_id, EstadoMensaje.TRANSFORMADO)
        guardar_hl7(correlation_id, {"adt": hl7_adt, "orm": hl7_orm})

        host_adt, puerto_adt = _destino("destino_adt")
        enviar_mensaje_mllp(correlation_id, hl7_adt, host=host_adt, puerto=puerto_adt)

        host_orm, puerto_orm = _destino("destino_orm")
        enviar_mensaje_mllp(correlation_id, hl7_orm, host=host_orm, puerto=puerto_orm)

    except Exception as e:
        print(f"[!] Fallo en el worker para {correlation_id}: {e}")
        raise e
