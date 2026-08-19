import os
import time
import uuid

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

from core.auditoria import registrar_ingreso, existe_accession
from core.broker import tarea_procesar_orden
from core import config_repo

POLL_INTERVAL = int(os.getenv("MWL_POLL_INTERVAL", "30"))  # segundos

# Fallbacks si el canal no estuviera en la base.
FALLBACK = {"host": "127.0.0.1", "puerto": 4243, "aet": "TEST_PACS", "aet_local": "MOTOR_WKL"}


def _config():
    canal = config_repo.obtener_canal("worklist_scu")
    return canal or FALLBACK


def _build_query() -> Dataset:
    ds = Dataset()
    ds.PatientID = ""
    ds.PatientName = ""
    ds.PatientBirthDate = ""
    ds.PatientSex = ""
    ds.AccessionNumber = ""
    ds.RequestedProcedureDescription = ""
    ds.ReferringPhysicianName = ""
    sps = Dataset()
    sps.Modality = ""
    sps.ScheduledProcedureStepStartDate = ""
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def _g(dataset, attr) -> str:
    return str(getattr(dataset, attr, "") or "")


def _to_payload(ds: Dataset) -> dict:
    if "ScheduledProcedureStepSequence" in ds and ds.ScheduledProcedureStepSequence:
        sps = ds.ScheduledProcedureStepSequence[0]
    else:
        sps = Dataset()
    return {
        "00100020": _g(ds, "PatientID"),
        "00100010": _g(ds, "PatientName"),
        "00100030": _g(ds, "PatientBirthDate"),
        "00100040": _g(ds, "PatientSex"),
        "00080050": _g(ds, "AccessionNumber"),
        "00321060": _g(ds, "RequestedProcedureDescription"),
        "00080090": _g(ds, "ReferringPhysicianName"),
        "00080060": _g(sps, "Modality") or _g(ds, "Modality"),
        "00400002": _g(sps, "ScheduledProcedureStepStartDate") or _g(ds, "ScheduledProcedureStepStartDate"),
    }


def poll_once() -> int:
    cfg = _config()
    ae = AE(ae_title=cfg.get("aet_local") or "MOTOR_WKL")
    ae.add_requested_context(ModalityWorklistInformationFind)

    assoc = ae.associate(cfg["host"], int(cfg["puerto"]), ae_title=cfg.get("aet") or "TEST_PACS")
    if not assoc.is_established:
        print(f"[SCU] No se pudo asociar con {cfg['host']}:{cfg['puerto']}")
        return 0

    nuevas = 0
    try:
        responses = assoc.send_c_find(_build_query(), ModalityWorklistInformationFind)
        for (status, identifier) in responses:
            if not status or status.Status not in (0xFF00, 0xFF01) or identifier is None:
                continue
            payload = _to_payload(identifier)
            accession = payload["00080050"]
            if not accession or existe_accession(accession):
                continue
            correlation_id = uuid.uuid4()
            registrar_ingreso(
                correlation_id=correlation_id,
                patient_id=payload["00100020"],
                accession_number=accession,
                modalidad=payload["00080060"],
                payload_dicom=payload,
            )
            tarea_procesar_orden(correlation_id, payload)
            nuevas += 1
            print(f"[SCU] Orden ingestada: accession={accession} corr_id={correlation_id}")
    finally:
        assoc.release()
    return nuevas


def run_polling():
    config_repo.seed_canales()  # asegura que el canal exista
    cfg = _config()
    print(f"[SCU] Polling MWL cada {POLL_INTERVAL}s -> {cfg['host']}:{cfg['puerto']}")
    while True:
        try:
            n = poll_once()
            if n:
                print(f"[SCU] {n} orden(es) nueva(s) en este ciclo.")
        except Exception as e:
            print(f"[SCU] Error en ciclo de polling: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_polling()
