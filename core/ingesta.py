import os
import time
import uuid
import logging
import datetime

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

from core.database import SessionLocal
from core.models import RegistroTrazabilidad, EstadoMensaje
from core.broker import tarea_procesar_orden
from core import config_repo

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversion del Dataset DICOM devuelto por el C-FIND al dict de tags
# que esperan registrar/transformar (mismas claves que usa el transformador).
# ---------------------------------------------------------------------------
def _v(ds, attr):
    valor = getattr(ds, attr, "")
    return str(valor) if valor not in (None, "") else ""


def _dataset_a_payload(ds: Dataset) -> dict:
    payload = {
        "00100020": _v(ds, "PatientID"),
        "00100010": _v(ds, "PatientName"),
        "00100030": _v(ds, "PatientBirthDate"),
        "00100040": _v(ds, "PatientSex"),
        "00080050": _v(ds, "AccessionNumber"),
        "00321060": _v(ds, "RequestedProcedureDescription"),
        "00080090": _v(ds, "ReferringPhysicianName"),
        "00080060": _v(ds, "Modality"),
        "00400002": "",
    }
    # Modality y fecha suelen venir dentro de ScheduledProcedureStepSequence
    sps_seq = getattr(ds, "ScheduledProcedureStepSequence", None)
    if sps_seq and len(sps_seq) > 0:
        sps = sps_seq[0]
        if not payload["00080060"]:
            payload["00080060"] = _v(sps, "Modality")
        payload["00400002"] = _v(sps, "ScheduledProcedureStepStartDate")
    return payload


def _construir_query(fecha_str: str) -> Dataset:
    """Query de Modality Worklist. Universal matching + fecha de hoy como clave."""
    ds = Dataset()
    ds.PatientName = ""
    ds.PatientID = ""
    ds.PatientBirthDate = ""
    ds.PatientSex = ""
    ds.AccessionNumber = ""
    ds.RequestedProcedureDescription = ""
    ds.ReferringPhysicianName = ""

    sps = Dataset()
    sps.Modality = ""
    sps.ScheduledStationAETitle = ""
    sps.ScheduledProcedureStepStartDate = fecha_str  # clave de matching: HOY
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def _ya_ingerida(db, accession: str) -> bool:
    """Dedup: evita reprocesar la misma orden en cada poll."""
    if not accession:
        return False
    existe = db.query(RegistroTrazabilidad).filter(
        RegistroTrazabilidad.accession_number == accession
    ).first()
    return existe is not None


def _procesar_orden(payload: dict) -> bool:
    """Persiste la orden (si es nueva) y la despacha al broker. Devuelve True si ingirio."""
    accession = payload.get("00080050", "")
    db = SessionLocal()
    try:
        if _ya_ingerida(db, accession):
            return False
        correlation_id = uuid.uuid4()
        nuevo = RegistroTrazabilidad(
            correlation_id=correlation_id,
            patient_id=payload.get("00100020") or None,
            accession_number=accession or None,
            modalidad=payload.get("00080060") or None,
            payload_dicom_raw=payload,
            estado=EstadoMensaje.INGRESADO,
        )
        db.add(nuevo)
        db.commit()
        log.info("Orden capturada: accession=%s correlation=%s", accession, correlation_id)

        # Despacho asincrono al broker (transformacion + emision + reintentos)
        tarea_procesar_orden(correlation_id, payload)
        return True
    except Exception:
        db.rollback()
        log.exception("Error al persistir/despachar orden accession=%s", accession)
        return False
    finally:
        db.close()


def consultar_worklist_una_vez():
    """Ejecuta un C-FIND contra la worklist configurada en el canal 'worklist_scu'."""
    canal = config_repo.obtener_canal("worklist_scu")
    if not canal:
        log.warning("Canal 'worklist_scu' inexistente; configuralo en la consola.")
        return
    if not canal.get("activo", True):
        log.info("Canal 'worklist_scu' inactivo; se omite la consulta.")
        return

    host = canal["host"]
    puerto = int(canal["puerto"])
    aet_remoto = canal.get("aet") or "ANY-SCP"
    aet_local = canal.get("aet_local") or "MOTOR_WKL"

    ae = AE(ae_title=aet_local)
    ae.add_requested_context(ModalityWorklistInformationFind)

    fecha_hoy = datetime.date.today().strftime("%Y%m%d")
    query = _construir_query(fecha_hoy)

    log.info("C-FIND -> %s:%s (AET remoto=%s, local=%s, fecha=%s)",
             host, puerto, aet_remoto, aet_local, fecha_hoy)

    assoc = ae.associate(host, puerto, ae_title=aet_remoto)
    if not assoc.is_established:
        log.error("No se pudo establecer la asociacion DICOM con %s:%s", host, puerto)
        return

    try:
        nuevas = 0
        total = 0
        for (status, identifier) in assoc.send_c_find(query, ModalityWorklistInformationFind):
            if status and status.Status in (0xFF00, 0xFF01) and identifier is not None:
                total += 1
                payload = _dataset_a_payload(identifier)
                if _procesar_orden(payload):
                    nuevas += 1
        log.info("C-FIND completado. Ordenes recibidas=%s, nuevas ingeridas=%s", total, nuevas)
    finally:
        assoc.release()


def iniciar_ingesta():
    """Entrypoint del servicio de ingesta: poll periodico de la worklist."""
    intervalo = int(os.environ.get("INGESTA_INTERVALO_SEG", "30"))
    log.info("Ingesta C-FIND iniciada (poll cada %ss)", intervalo)
    while True:
        try:
            consultar_worklist_una_vez()
        except Exception:
            log.exception("Fallo en el ciclo de ingesta; se reintenta en el proximo poll")
        time.sleep(intervalo)


# ---------------------------------------------------------------------------
# Simulacion original (se conserva intacta para pruebas locales)
# ---------------------------------------------------------------------------
def simular_ingesta_worklist():
    """
    Simula la interrogación a la Modality Worklist (C-FIND SCU).
    Captura la orden, genera el Correlation ID y la persiste en PostgreSQL.
    """
    print("[*] Iniciando captura de nueva orden desde Worklist...")

    mock_dicom_payload = {
        "00100020": "PAC-884920",   # Patient ID
        "00100010": "PEREZ^JUAN",   # Patient's Name
        "00080050": "ACC-559302",   # Accession Number
        "00080060": "CR",           # Modality
        "00400002": "202608181030"  # Scheduled Procedure Step Start Date
    }

    correlation_id = uuid.uuid4()
    db = SessionLocal()
    try:
        nuevo_registro = RegistroTrazabilidad(
            correlation_id=correlation_id,
            patient_id=mock_dicom_payload["00100020"],
            accession_number=mock_dicom_payload["00080050"],
            modalidad=mock_dicom_payload["00080060"],
            payload_dicom_raw=mock_dicom_payload,
            estado=EstadoMensaje.INGRESADO
        )
        db.add(nuevo_registro)
        db.commit()
        print("[PASO 1] ORDEN CAPTURADA (Estado: INGRESADO)")
        print(f"   Correlation ID: {correlation_id}")
        print("[PASO 2] Despachando tarea al broker asincrono...")
        tarea_procesar_orden(correlation_id, mock_dicom_payload)
        print("Tarea encolada exitosamente. Hilo principal liberado.")
    except Exception as e:
        db.rollback()
        print(f"Error critico en la captura de la base de datos: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    simular_ingesta_worklist()