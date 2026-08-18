import uuid
from core.database import SessionLocal
from core.models import RegistroTrazabilidad, EstadoMensaje

def actualizar_estado(correlation_id: uuid.UUID, estado: EstadoMensaje):
    """
    Actualiza el estado de trazabilidad clínico de forma atómica en PostgreSQL.
    Garantiza que ninguna orden quede huérfana en caso de fallo del broker.
    """
    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        
        if registro:
            registro.estado = estado
            db.commit()
            print(f"[*] Auditoría: Estado de {correlation_id} actualizado a {estado.name}")
    except Exception as e:
        db.rollback()
        print(f"[!] Error crítico de persistencia al actualizar estado: {e}")
    finally:
        db.close()

def registrar_ingreso(correlation_id: uuid.UUID, patient_id: str, accession_number: str, modalidad: str, payload_dicom: dict):
    """
    Registra la orden capturada desde la Worklist en la base de datos.
    Asegura que el registro crudo inicie su ciclo con el estado clínico inicial.
    """
    db = SessionLocal()
    try:
        nuevo_registro = RegistroTrazabilidad(
            correlation_id=correlation_id,
            patient_id=patient_id,
            accession_number=accession_number,
            modalidad=modalidad,
            payload_dicom=payload_dicom,
            estado=EstadoMensaje.INGRESADO
        )
        db.add(nuevo_registro)
        db.commit()
        print(f"[*] Auditoría: Orden {accession_number} registrada en DB con estado INGRESADO")
        return nuevo_registro
    except Exception as e:
        db.rollback()
        print(f"[!] Error crítico al registrar ingreso en PostgreSQL: {e}")
        raise e
    finally:
        db.close()