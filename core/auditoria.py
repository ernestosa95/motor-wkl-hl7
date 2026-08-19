import uuid
from core.database import SessionLocal
from core.models import RegistroTrazabilidad, EstadoMensaje


def actualizar_estado(correlation_id: uuid.UUID, estado: EstadoMensaje):
    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        if registro:
            registro.estado = estado
            db.commit()
            print(f"[*] Auditoría: {correlation_id} -> {estado.name}")
    except Exception as e:
        db.rollback()
        print(f"[!] Error al actualizar estado: {e}")
    finally:
        db.close()


def guardar_hl7(correlation_id: uuid.UUID, mensajes: dict):
    """Persiste el HL7 emitido (dict con claves 'adt' y 'orm') para auditoría."""
    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        if registro:
            registro.payload_hl7 = mensajes
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[!] Error al guardar HL7: {e}")
    finally:
        db.close()


def registrar_ingreso(correlation_id: uuid.UUID, patient_id: str,
                      accession_number: str, modalidad: str, payload_dicom: dict):
    db = SessionLocal()
    try:
        nuevo = RegistroTrazabilidad(
            correlation_id=correlation_id,
            patient_id=patient_id,
            accession_number=accession_number,
            modalidad=modalidad,
            payload_dicom_raw=payload_dicom,
            estado=EstadoMensaje.INGRESADO,
        )
        db.add(nuevo)
        db.commit()
        print(f"[*] Auditoría: orden {accession_number} registrada (INGRESADO)")
        return nuevo
    except Exception as e:
        db.rollback()
        print(f"[!] Error al registrar ingreso: {e}")
        raise e
    finally:
        db.close()


def existe_accession(accession_number: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.accession_number == accession_number
        ).first() is not None
    finally:
        db.close()
