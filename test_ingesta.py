import uuid
from core.auditoria import registrar_ingreso
from core.transformador import procesar_transformacion
from core.emisor_mllp import procesar_emision  # <-- Nueva importación

def test_simulacion_flujo_completo():
    print("Iniciando flujo de integración completo (Ingesta -> Transformación -> Emisión)...")
    
    mock_dicom_payload = {
        "00100020": "PAC-884920",  
        "00100010": "PEREZ^JUAN",  
        "00080050": "ACC-559302",  
        "00080060": "CR",          
        "00400002": "202608161030" 
    }

    correlation_id = uuid.uuid4()

    try:
        # PASO 1: Ingesta DICOM
        registro = registrar_ingreso(
            correlation_id=correlation_id,
            patient_id=mock_dicom_payload["00100020"],
            accession_number=mock_dicom_payload["00080050"],
            modalidad=mock_dicom_payload["00080060"],
            payload_dicom=mock_dicom_payload
        )
        print(f"\n✅ [PASO 1] Ingesta. Estado: {registro.estado}")

        # PASO 2: Transformación a HL7 v2.5
        hl7_generado = procesar_transformacion(
            correlation_id=correlation_id,
            payload_dicom=mock_dicom_payload
        )
        print("✅ [PASO 2] Transformación. Estado actualizado a TRANSFORMADO.")
        
        # PASO 3: Emisión MLLP
        print("\n✅ [PASO 3] Iniciando comunicación por socket TCP/IP...")
        procesar_emision(
            correlation_id=correlation_id,
            host="127.0.0.1",
            puerto=2575, # Puerto que escucha el mock_mllp.py
            payload_hl7=hl7_generado
        )
        
    except Exception as e:
        print(f"\n❌ Error crítico en el pipeline: {e}")

if __name__ == "__main__":
    test_simulacion_flujo_completo()