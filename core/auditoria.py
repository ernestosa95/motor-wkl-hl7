import json
from models import SessionLocal, TransaccionIntegracion

def auditar_ultima_transaccion():
    """
    Consulta la base de datos PostgreSQL para auditar la última transacción procesada.
    Valida la trazabilidad total del dato mediante el Correlation ID y los payloads en JSONB.
    """
    session = SessionLocal()
    try:
        # Obtenemos el registro más reciente basado en la fecha de ingesta
        tx = session.query(TransaccionIntegracion).order_by(TransaccionIntegracion.fecha_ingesta.desc()).first()
        
        if not tx:
            print("[!] No se encontraron registros de transacciones en la base de datos.")
            return

        print("\n" + "="*70)
        # El Correlation ID acompaña al dato en todo su ciclo de vida
        print(f"[*] AUDITORÍA DE TRANSACCIÓN | Correlation ID: {tx.correlation_id}")
        print(f"[*] Estado Final: {tx.estado.value}")
        print(f"[*] Fecha de Ingesta: {tx.fecha_ingesta}")
        print("="*70)
        
        print("\n[1] TRAZABILIDAD HISTÓRICA (Auditoría JSONB):")
        # Mostramos los saltos de estado (INGRESADO -> TRANSFORMADO -> COMPLETADO/ERROR)[cite: 1]
        if tx.auditoria_historica:
            for evento in tx.auditoria_historica:
                fecha = evento.get('fecha', 'Fecha no registrada')
                estado = evento.get('estado_asignado', 'N/A')
                desc = evento.get('evento', '')
                print(f"    -> [{estado}] {fecha} | {desc}")
        else:
            print("    Sin eventos registrados.")

        print("\n[2] PAYLOAD GENERADO (Transformación a HL7 v2.5):")
        # Extracción de strings HL7 (ADT y ORM) desde la columna JSONB[cite: 1]
        hl7_generado = tx.payloads.get("hl7_generado")
        if hl7_generado:
            for linea in hl7_generado.split('\n'):
                print(f"    {linea}")
        else:
            print("    [!] Mensaje HL7 no generado o no disponible.")

        print("\n[3] RESPUESTA DEL SISTEMA DESTINO (Recepción de ACK):")
        # Registro de respuesta síncrona del sistema destino[cite: 1]
        ack_recibido = tx.payloads.get("ack_recibido")
        if ack_recibido:
            for linea in ack_recibido.split('\r'):
                if linea.strip():
                    print(f"    {linea}")
        else:
            print("    [!] Sin respuesta (ACK) registrada.")
            
        print("="*70 + "\n")

    except Exception as e:
        print(f"[X] Error de seguridad al consultar PostgreSQL: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    auditar_ultima_transaccion()