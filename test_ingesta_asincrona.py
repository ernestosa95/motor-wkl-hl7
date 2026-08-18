import uuid
from core.auditoria import registrar_ingreso

# Ya no importamos transformador ni emisor aquí; 
# delegamos esa responsabilidad estructural al broker.
from core.broker import tarea_procesar_orden

def simular_ingesta_worklist():
    print("Iniciando captura de nueva orden desde Worklist...")
    
    # Payload simulado extraído del C-FIND
    mock_dicom_payload = {
        "00100020": "PAC-884920",  
        "00100010": "PEREZ^JUAN",  
        "00080050": "ACC-559302",  
        "00080060": "CR",          
        "00400002": "202608161030" 
    }

    # El identificador único acompañará al dato en todo el ciclo
    correlation_id = uuid.uuid4()

    try:
        # PASO 1: Ingesta DICOM síncrona y rápida
        registro = registrar_ingreso(
            correlation_id=correlation_id,
            patient_id=mock_dicom_payload["00100020"],
            accession_number=mock_dicom_payload["00080050"],
            modalidad=mock_dicom_payload["00080060"],
            payload_dicom=mock_dicom_payload
        )
        print(f"\n✅ [PASO 1] ORDEN CAPTURADA (Estado: INGRESADO)")
        print(f"   Correlation ID: {correlation_id}")

        # PASO 2: Encolamiento Asíncrono (Huey)
        print("\n⏳ [PASO 2] Despachando tarea al broker asíncrono...")
        
        # Al invocar la función decorada, Huey la intercepta y la encola
        tarea_procesar_orden(correlation_id, mock_dicom_payload)
        
        print("✅ Tarea encolada exitosamente.")
        print("   El hilo principal queda libre para consultar nuevas órdenes.")
        
    except Exception as e:
        print(f"\n❌ Error crítico en la captura: {e}")

if __name__ == "__main__":
    simular_ingesta_worklist()
