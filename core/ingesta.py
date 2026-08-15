import uuid
from datetime import datetime
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind
# Reemplazar la definición local de engine y SessionLocal por esta importación:
from models import TransaccionIntegracion, EstadoTransaccion, SessionLocal

# Integración con SQLAlchemy para persistencia en PostgreSQL[cite: 1]
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Integración con el Message Broker para encolamiento asíncrono
from transformador import procesar_transformacion

# Configuración de base de datos local (ajusta la contraseña según tu entorno)
DATABASE_URL = "postgresql+psycopg2://postgres:tu_contraseña@localhost:5432/motordicom_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def persistir_orden(orden_dict):
    """Guarda la transacción en PostgreSQL y la envía a la cola de procesamiento."""
    session = SessionLocal()
    try:
        # El registro crudo se guarda con estado INGRESADO[cite: 1]
        # Se almacenan los payloads crudos y auditorías en columnas JSONB[cite: 1]
        nueva_transaccion = TransaccionIntegracion(
            correlation_id=orden_dict["correlation_id"],
            estado=EstadoTransaccion.INGRESADO, 
            payloads={"dicom_raw": orden_dict["payload_dicom"]}, 
            auditoria_historica=[{
                "fecha": orden_dict["fecha_ingesta"], 
                "evento": "Captura exitosa desde Modality Worklist",
                "estado_asignado": "INGRESADO"
            }]
        )
        session.add(nueva_transaccion)
        session.commit()
        print(f"[\u2713] Registro consolidado en DB. Correlation ID: {orden_dict['correlation_id']}")
        
        # Encolar la tarea asíncrona de transformación al Message Broker
        procesar_transformacion(orden_dict["correlation_id"], orden_dict["payload_dicom"])
        print(f"[\u2713] Tarea de transformación encolada exitosamente.")

    except Exception as e:
        session.rollback()
        print(f"[X] Error de seguridad al persistir los datos: {e}")
    finally:
        session.close()

def consultar_worklist(ae_title, ip, puerto):
    """Ejecuta la interrogación a la Modality Worklist (C-FIND SCU)[cite: 1]."""
    ae = AE(ae_title=b'MOTORDICOM')
    ae.add_requested_context(ModalityWorklistInformationFind)

    # Estructura base de tags requeridos para la consulta
    ds = Dataset()
    ds.PatientID = ""
    ds.PatientName = ""
    ds.PatientBirthDate = ""
    ds.PatientSex = ""
    ds.AccessionNumber = ""
    ds.RequestedProcedureDescription = ""
    ds.ReferringPhysicianName = ""
    ds.Modality = ""
    ds.ScheduledProcedureStepSequence = [Dataset()]
    ds.ScheduledProcedureStepSequence[0].ScheduledProcedureStepStartDate = ""

    print(f"Iniciando asociación DICOM con {ip}:{puerto}...")
    assoc = ae.associate(ip, puerto, ae_title=ae_title)

    if assoc.is_established:
        respuestas = assoc.send_c_find(ds, ModalityWorklistInformationFind)
        
        ordenes_capturadas = []
        for (status, identifier) in respuestas:
            # Capturar cuando el estado es 0xFF00 (Pending / Datos adjuntos)
            if status and identifier and status.Status == 0xFF00:
                
                # Se genera un Correlation ID (UUID) que acompañará al dato en todo su ciclo de vida[cite: 1]
                correlation_id = str(uuid.uuid4())
                
                orden = {
                    "correlation_id": correlation_id,
                    "payload_dicom": identifier.to_json_dict(),
                    "fecha_ingesta": datetime.now().isoformat()
                }
                
                # Invocamos la persistencia y el encolamiento
                persistir_orden(orden)
                ordenes_capturadas.append(orden)
                
        assoc.release()
        return ordenes_capturadas
    else:
        print("Asociación rechazada, abortada o fallida.")
        return []

if __name__ == "__main__":
    # Prueba local contra el servidor Mock SCP configurado en el puerto 4242
    resultados = consultar_worklist(b'TEST_PACS', '127.0.0.1', 4243)
    print(f"Total procesado en esta ejecución: {len(resultados)}")