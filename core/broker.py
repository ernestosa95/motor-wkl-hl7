import os
from huey import SqliteHuey
from core.transformador import procesar_transformacion
from core.auditoria import actualizar_estado
from core.emisor_mllp import enviar_mensaje_mllp
from core.models import EstadoMensaje


def _data_dir() -> str:
    """
    Directorio escribible para la cola SQLite de Huey.
    En Windows empaquetado corre como servicio bajo Program Files (solo lectura),
    por eso la cola debe vivir en ProgramData\\MotorDICOM (via MOTORDICOM_DATA).
    """
    root = os.environ.get(
        "MOTORDICOM_DATA",
        os.path.join(os.environ.get("ProgramData", os.getcwd()), "MotorDICOM"),
    )
    os.makedirs(root, exist_ok=True)
    return root


# Cola persistente en ubicacion escribible (antes: junto al codigo -> fallaba como servicio)
huey = SqliteHuey(filename=os.path.join(_data_dir(), "motor_queue.db"))


@huey.task(retries=3, retry_delay=10)  # 3 intentos con decaimiento temporal
def tarea_procesar_orden(correlation_id, payload_dicom):
    """
    Worker asíncrono: Transforma el payload crudo y lo despacha.
    """
    try:
        # 1. Transformación a HL7 v2.5
        hl7_generado = procesar_transformacion(payload_dicom, "ORM")

        # Actualización de trazabilidad
        actualizar_estado(correlation_id, EstadoMensaje.TRANSFORMADO)

        # 2. Emisión vía socket TCP/IP
        enviar_mensaje_mllp(correlation_id, hl7_generado)

    except Exception as e:
        print(f"[!] Fallo en el worker para {correlation_id}: {e}")
        # Huey gestionará el reintento. Si falla definitivamente, el emisor o el worker
        # se encargarán de asentar ERROR_PERMANENTE.
        raise e