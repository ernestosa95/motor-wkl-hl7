import uuid
import datetime
from jinja2 import Template

# Plantilla base para ORM^O01 (HL7 v2.5) utilizando Jinja2
# El diseño en texto plano facilitará la edición dinámica posterior desde la web
PLANTILLA_ORM = """MSH|^~\&|DICOM_WKL|TECNOIMAGEN|HIS|HOSPITAL|{{ fecha }}||ORM^O01|{{ msg_id }}|P|2.5
PID|1||{{ pid_3 }}||{{ pid_5 }}||{{ pid_7 }}|{{ pid_8 }}
ORC|NW|{{ obr_2 }}
OBR|1|{{ obr_2 }}|{{ obr_3 }}|{{ obr_4 }}||||||||||||{{ obr_16 }}||||||||{{ obr_24 }}|||{{ obr_27 }}"""

def procesar_transformacion(payload_dicom: dict, tipo_mensaje: str = "ORM") -> str:
    """
    Recibe un diccionario JSONB con los tags DICOM crudos y retorna un string HL7 v2.5.
    Garantiza el cruce exacto de los segmentos PID y OBR según la especificación clínica.
    """
    
    # Mapeo de variables clínicas según la especificación de tags DICOM
    datos_mapeo = {
        "fecha": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        "msg_id": str(uuid.uuid4().hex)[:10].upper(),
        
        # Segmento PID (Identificación del Paciente)
        "pid_3": payload_dicom.get("00100020", ""),  # Patient ID
        "pid_5": payload_dicom.get("00100010", ""),  # Patient's Name
        "pid_7": payload_dicom.get("00100030", ""),  # Patient's Birth Date
        "pid_8": payload_dicom.get("00100040", ""),  # Patient's Sex
        
        # Segmento OBR (Solicitud de Estudio)
        "obr_2": payload_dicom.get("00080050", ""),  # Accession Number
        "obr_3": payload_dicom.get("00080050", ""),  # Accession Number (Repetición estándar)
        "obr_4": payload_dicom.get("00321060", ""),  # Requested Procedure Description
        "obr_16": payload_dicom.get("00080090", ""), # Referring Physician's Name
        "obr_24": payload_dicom.get("00080060", ""), # Modality
        "obr_27": payload_dicom.get("00400002", "")  # Scheduled Procedure Step Start Date
    }

    # Renderizado de la plantilla con el motor Jinja2
    template = Template(PLANTILLA_ORM)
    mensaje_hl7 = template.render(**datos_mapeo)
    
    # HL7 requiere el retorno de carro (\r) como separador estricto de segmentos
    return mensaje_hl7.replace('\n', '\r')