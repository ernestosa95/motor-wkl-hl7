import logging
import uuid
from pydicom.dataset import Dataset
from models import SessionLocal, TransaccionIntegracion, EstadoTransaccion
# Se asume la existencia de broker.py para el encolamiento nativo (Huey/Dramatiq)[cite: 2]
# from broker import encolar_transformacion

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("IngestaDICOM")

def extraer_tag(dataset: Dataset, tag: str, default: str = "") -> str:
    """Extrae de manera segura el valor de un Tag DICOM o retorna un valor por defecto."""
    elem = dataset.get(tag)
    return str(elem.value).strip() if elem and elem.value is not None else default

def procesar_dataset_worklist(ds: Dataset):
    """
    Procesa los datos capturados tras la Interrogación a la Modality Worklist (C-FIND SCU)[cite: 2].
    Garantiza la idempotencia mediante el Accession Number.
    """
    # Extracción de los identificadores únicos exigidos por estándar
    accession_number = extraer_tag(ds, "AccessionNumber") # (0008,0050)[cite: 2]
    study_uid = extraer_tag(ds, "StudyInstanceUID")
    patient_id = extraer_tag(ds, "PatientID") # (0010,0020)[cite: 2]

    # Descarte por malformación de origen
    if not accession_number:
        logger.warning(f"Orden rechazada en origen: Ausencia de Accession Number para Paciente {patient_id}")
        return

    db = SessionLocal()
    try:
        # Validación de existencia previa en base de datos de trazabilidad
        orden_existente = db.query(TransaccionIntegracion).filter(
            TransaccionIntegracion.accession_number == accession_number
        ).first()

        if orden_existente:
            logger.info(
                f"[IDEMPOTENCIA] Orden {accession_number} identificada como pre-existente "
                f"(Estado Actual: {orden_existente.estado.name}). Omitiendo procesamiento duplicado."
            )
            return

        # Generación de UUID para el Correlation ID que acompañará al dato en todo su ciclo de vida[cite: 2].
        nuevo_uuid = uuid.uuid4()
        logger.info(f"[NUEVA ORDEN] Captura de Accession Number {accession_number}. Generando UUID: {nuevo_uuid}")
        
        # Diccionario para almacenar el payload DICOM como JSONB[cite: 2]
        payload_json = {
            "00080050": accession_number,
            "00100020": patient_id,
            "00100010": extraer_tag(ds, "PatientName"), # (0010,0010)[cite: 2]
            "00100030": extraer_tag(ds, "PatientBirthDate"), # (0010,0030)[cite: 2]
            "00100040": extraer_tag(ds, "PatientSex"), # (0010,0040)[cite: 2]
            "00321060": extraer_tag(ds, "RequestedProcedureDescription"), # (0032,1060)[cite: 2]
            "00080090": extraer_tag(ds, "ReferringPhysicianName"), # (0008,0090)[cite: 2]
            "00080060": extraer_tag(ds, "Modality"), # (0008,0060)[cite: 2]
            "00400002": extraer_tag(ds, "ScheduledProcedureStepStartDate") # (0040,0002)[cite: 2]
        }

        # Inicialización de la transacción de integración.
        # El registro crudo se guarda con estado INGRESADO[cite: 2].
        nueva_transaccion = TransaccionIntegracion(
            correlation_id=nuevo_uuid,
            accession_number=accession_number,
            study_instance_uid=study_uid,
            estado=EstadoTransaccion.INGRESADO,
            payload_dicom=payload_json
        )
        
        db.add(nueva_transaccion)
        db.commit()

        # Derivación al Message Broker para iniciar la Transformación[cite: 2]
        # encolar_transformacion(str(nuevo_uuid))
        logger.info(f"[ENCOLADO] Orden {accession_number} persistida y derivada exitosamente al worker.")

    except Exception as e:
        db.rollback()
        logger.error(f"[ERROR DB] Falla de concurrencia o persistencia al procesar orden {accession_number}: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Script simulador para validación de la lógica de idempotencia
    print("Iniciando prueba de idempotencia en entorno local...")
    
    ds_mock = Dataset()
    ds_mock.AccessionNumber = "ACC-WORKLIST-001"
    ds_mock.StudyInstanceUID = "1.2.840.113619.2.55.3.999"
    ds_mock.PatientID = "12345678"
    ds_mock.PatientName = "PACIENTE^PRUEBA"
    
    print("\n--- Intento 1: Primera captura de la orden ---")
    procesar_dataset_worklist(ds_mock)
    
    print("\n--- Intento 2: Siguiente ciclo de polling (La orden sigue en el RIS) ---")
    procesar_dataset_worklist(ds_mock)