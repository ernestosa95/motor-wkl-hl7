import uuid
from core.database import SessionLocal
from core.models import RegistroTrazabilidad, EstadoMensaje
from core.broker import tarea_procesar_orden

def simular_ingesta_worklist():
    """
    Simula la interrogación a la Modality Worklist (C-FIND SCU).
    Captura la orden, genera el Correlation ID y la persiste en PostgreSQL.
    """
    print("[*] Iniciando captura de nueva orden desde Worklist...")
    
    # Payload simulado con los tags DICOM críticos requeridos para el cruce
    mock_dicom_payload = {
        "00100020": "PAC-884920",  # Patient ID
        "00100010": "PEREZ^JUAN",  # Patient's Name
        "00080050": "ACC-559302",  # Accession Number
        "00080060": "CR",          # Modality
        "00400002": "202608181030" # Scheduled Procedure Step Start Date
    }

    # Generación del identificador único que acompañará al dato en todo su ciclo de vida
    correlation_id = uuid.uuid4()
    db = SessionLocal()

    try:
        # 1. Persistencia segura en PostgreSQL (Estado: INGRESADO)
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
        
        print(f"✅ [PASO 1] ORDEN CAPTURADA (Estado: INGRESADO)")
        print(f"   Correlation ID: {correlation_id}")

        # 2. Despacho al Message Broker (Huey/Dramatiq) para procesamiento asíncrono
        print("⏳ [PASO 2] Despachando tarea al broker asíncrono...")
        tarea_procesar_orden(correlation_id, mock_dicom_payload)
        
        print("✅ Tarea encolada exitosamente. Hilo principal liberado.")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error crítico en la captura de la base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    simular_ingesta_worklist()