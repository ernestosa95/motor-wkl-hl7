# /home/ernesto/Documentos/02- Tecno/05- Integracion/core/transformador.py
# Proyecto: Motor de Integración Clínica - Tecnoimagen SA

from jinja2 import Template
from broker import huey
from models import SessionLocal, TransaccionIntegracion, EstadoTransaccion
from emisor_mllp import emitir_mensaje
from datetime import datetime

# Se utiliza un enfoque híbrido con motor Jinja2 para cruces estándar de tags DICOM a HL7[cite: 1].
# La cadena "r" al inicio evita el SyntaxWarning con los caracteres de escape obligatorios de HL7.
HL7_TEMPLATE = r"""MSH|^~\&|MOTORDICOM|HIS|PACS|RIS|{{fecha_actual}}||ORM^O01|{{msg_control_id}}|P|2.5
PID|1||{{patient_id}}||{{patient_name}}||{{birth_date}}|{{sex}}
OBR|1|{{accession_number}}|{{accession_number}}|{{procedure_desc}}||||||||||||{{physician_name}}||||||||{{modality}}|||{{scheduled_date}}"""

@huey.task()
def procesar_transformacion(correlation_id: str, dicom_data: dict):
    """
    Tarea asíncrona encolada por Huey.
    Extrae los tags de la Worklist DICOM y aplica la plantilla Jinja2 para generar el mensaje HL7.
    """
    session = SessionLocal()
    try:
        # Recuperación del registro crudo almacenado previamente en la base de datos PostgreSQL[cite: 1].
        transaccion = session.query(TransaccionIntegracion).filter_by(correlation_id=correlation_id).first()
        
        if not transaccion:
            print(f"[X] Transacción {correlation_id} no encontrada en la base de datos.")
            return

        print(f"[*] Transformando registro {correlation_id}...")

        # 1. Mapeo del Segmento PID (Identificación del Paciente)
        patient_id = dicom_data.get("00100020", {}).get("Value", [""])[0]  # Tag (0010,0020) Patient ID hacia PID-3[cite: 1]
        patient_name_dict = dicom_data.get("00100010", {}).get("Value", [{"Alphabetic": ""}])[0]
        patient_name = patient_name_dict.get("Alphabetic", "") if isinstance(patient_name_dict, dict) else str(patient_name_dict) # Tag (0010,0010) Patient's Name hacia PID-5[cite: 1]
        birth_date = dicom_data.get("00100030", {}).get("Value", [""])[0]  # Tag (0010,0030) Patient's Birth Date hacia PID-7[cite: 1]
        sex = dicom_data.get("00100040", {}).get("Value", [""])[0]         # Tag (0010,0040) Patient's Sex hacia PID-8[cite: 1]

        # 2. Mapeo del Segmento OBR (Solicitud de Estudio)
        accession_number = dicom_data.get("00080050", {}).get("Value", [""])[0] # Tag (0008,0050) Accession Number hacia OBR-2 / OBR-3[cite: 1]
        procedure_desc = dicom_data.get("00321060", {}).get("Value", [""])[0]   # Tag (0032,1060) Requested Procedure Description hacia OBR-4[cite: 1]
        physician_name_dict = dicom_data.get("00080090", {}).get("Value", [{"Alphabetic": ""}])[0]
        physician_name = physician_name_dict.get("Alphabetic", "") if isinstance(physician_name_dict, dict) else str(physician_name_dict) # Tag (0008,0090) Referring Physician's Name hacia OBR-16[cite: 1]
        modality = dicom_data.get("00080060", {}).get("Value", [""])[0]         # Tag (0008,0060) Modality hacia OBR-24[cite: 1]
        
        # Secuencia (0040,0002) Scheduled Procedure Step Start Date hacia OBR-27[cite: 1]
        scheduled_date = ""
        sps_sequence = dicom_data.get("00400100", {}).get("Value", [])
        if sps_sequence and isinstance(sps_sequence, list):
            scheduled_date = sps_sequence[0].get("00400002", {}).get("Value", [""])[0]

        # 3. Compilación de la plantilla HL7
        template = Template(HL7_TEMPLATE)
        fecha_generacion = datetime.now().strftime("%Y%m%d%H%M%S")
        
        mensaje_hl7 = template.render(
            fecha_actual=fecha_generacion,
            msg_control_id=correlation_id[:15].replace("-", "").upper(),
            patient_id=patient_id,
            patient_name=patient_name.replace("^", " "),
            birth_date=birth_date,
            sex=sex,
            accession_number=accession_number,
            procedure_desc=procedure_desc,
            physician_name=physician_name.replace("^", " "),
            modality=modality,
            scheduled_date=scheduled_date
        )

        # 4. Actualización de payloads y transición de estado
        # Los payloads crudos (DICOM/HL7) se almacenan en columnas JSONB[cite: 1].
        payloads_actualizados = transaccion.payloads.copy()
        payloads_actualizados["hl7_generado"] = mensaje_hl7
        
        auditoria_nueva = transaccion.auditoria_historica.copy()
        auditoria_nueva.append({
            "fecha": datetime.now().isoformat(),
            "evento": "Transformación HL7 (ORM) exitosa mediante Jinja2",
            "estado_asignado": "TRANSFORMADO"
        })

        transaccion.payloads = payloads_actualizados
        transaccion.auditoria_historica = auditoria_nueva
        
        # Transición obligatoria al estado TRANSFORMADO[cite: 1]
        transaccion.estado = EstadoTransaccion.TRANSFORMADO 
        
        session.commit()
        print(f"[\u2713] Transformación completada. Estado: TRANSFORMADO.")
        
        # 5. Despacho al módulo de comunicación
        # La solución se estructura separando la captura, transformación y comunicación[cite: 1].
        # Envío del payload vía socket TCP/IP (protocolo MLLP)[cite: 1].
        emitir_mensaje(correlation_id, "127.0.0.1", 5000)
        
    except Exception as e:
        session.rollback()
        print(f"[X] Error crítico en la transformación del registro {correlation_id}: {e}")
    finally:
        session.close()