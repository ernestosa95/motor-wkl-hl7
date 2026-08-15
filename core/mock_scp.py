from pydicom.dataset import Dataset
from pynetdicom import AE, evt
from pynetdicom.sop_class import ModalityWorklistInformationFind

def handle_find(event):
    """Manejador para las peticiones C-FIND (Modality Worklist)"""
    print("\n--- Petición C-FIND recibida desde MotorDICOM ---")
    
    # Creamos un dataset de respuesta simulado con los tags requeridos
    respuesta = Dataset()
    
    # Datos para el Segmento PID (Identificación del Paciente)
    respuesta.PatientID = "12345678"                  # (0010,0020)
    respuesta.PatientName = "PACIENTE^PRUEBA"         # (0010,0010)
    respuesta.PatientBirthDate = "19800101"           # (0010,0030)
    respuesta.PatientSex = "M"                        # (0010,0040)[cite: 1]
    
    # Datos para el Segmento OBR (Solicitud de Estudio)
    respuesta.AccessionNumber = "ACC-9999"            # (0008,0050)[cite: 1]
    respuesta.RequestedProcedureDescription = "RX TORAX" # (0032,1060)[cite: 1]
    respuesta.ReferringPhysicianName = "DR^DERIVANTE" # (0008,0090)[cite: 1]
    respuesta.Modality = "CR"                         # (0008,0060)[cite: 1]
    
    # Secuencia para la fecha programada
    seq_item = Dataset()
    seq_item.ScheduledProcedureStepStartDate = "20260815" # (0040,0002)[cite: 1]
    respuesta.ScheduledProcedureStepSequence = [seq_item]

    # Estado DICOM: Pending (FF00) indica que hay resultados, Success (0000) indica fin.
    yield (0xFF00, respuesta)

# Configuración del Application Entity (AE) del Servidor Simulado
ae = AE(ae_title=b'TEST_PACS')
ae.add_supported_context(ModalityWorklistInformationFind)

# Enlazamos el evento C-FIND a nuestra función manejadora
handlers = [(evt.EVT_C_FIND, handle_find)]

print("Iniciando Mock Worklist Server en localhost:4242...")
print("Esperando conexiones entrantes...")

# Iniciamos el servidor en el puerto 4243
ae.start_server(('127.0.0.1', 4243), evt_handlers=handlers)