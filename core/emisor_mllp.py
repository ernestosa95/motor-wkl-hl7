import socket
import time
from models import SessionLocal, TransaccionIntegracion, EstadoTransaccion

# Caracteres de control estándar para MLLP
VT = b'\x0b'  # Vertical Tab (Inicio de bloque)
FS = b'\x1c'  # File Separator (Fin de bloque)
CR = b'\x0d'  # Carriage Return

def empaquetar_mllp(mensaje_hl7: str) -> bytes:
    """Envuelve el string HL7 en la trama MLLP requerida por el estándar TCP/IP."""
    return VT + mensaje_hl7.encode('utf-8') + FS + CR

def desempaquetar_mllp(trama_bytes: bytes) -> str:
    """Limpia los caracteres de control de la respuesta síncrona."""
    trama_limpia = trama_bytes.replace(VT, b'').replace(FS, b'').replace(CR, b'')
    return trama_limpia.decode('utf-8', errors='ignore')

def emitir_mensaje(correlation_id: str, ip_destino: str, puerto: int):
    """
    Gestiona el envío del payload vía socket TCP/IP (protocolo MLLP)[cite: 1].
    Incluye la política de reintentos basada en estándares (3 intentos con decaimiento temporal)[cite: 1].
    """
    session = SessionLocal()
    try:
        transaccion = session.query(TransaccionIntegracion).filter_by(correlation_id=correlation_id).first()
        
        if not transaccion or transaccion.estado != EstadoTransaccion.TRANSFORMADO:
            print(f"[X] Transacción no válida para emisión: {correlation_id}")
            return

        mensaje_hl7 = transaccion.payloads.get("hl7_generado", "")
        payload_mllp = empaquetar_mllp(mensaje_hl7)

        max_intentos = 3
        intento_actual = 0
        exito_red = False
        respuesta_ack_cruda = b''

        # Ejecución de la política de reintentos[cite: 1]
        while intento_actual < max_intentos and not exito_red:
            intento_actual += 1
            try:
                print(f"[*] Intento {intento_actual}/3: Conectando a {ip_destino}:{puerto}...")
                
                # La comunicación MLLP inicial sobre red interna[cite: 1]
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5.0)
                    s.connect((ip_destino, puerto))
                    
                    s.sendall(payload_mllp)
                    
                    # Captura de la respuesta síncrona[cite: 1]
                    respuesta_ack_cruda = s.recv(4096)
                    if respuesta_ack_cruda:
                        exito_red = True
                        
            except Exception as e:
                print(f"[!] Falla de red en intento {intento_actual}: {e}")
                if intento_actual < max_intentos:
                    time.sleep(2 ** intento_actual) # Decaimiento temporal[cite: 1]

        # Actualización estricta de trazabilidad en columnas JSONB[cite: 1]
        auditoria_nueva = transaccion.auditoria_historica.copy()
        payloads_actualizados = transaccion.payloads.copy()
        
        if exito_red:
            ack_limpio = desempaquetar_mllp(respuesta_ack_cruda)
            payloads_actualizados["ack_recibido"] = ack_limpio
            
            # Verificación del tipo de ACK (AA = Accept, AE/AR = Error/Reject)
            if "MSA|AA" in ack_limpio:
                transaccion.estado = EstadoTransaccion.COMPLETADO # Estado final exitoso[cite: 1]
                auditoria_nueva.append({
                    "evento": "Emisión exitosa y ACK positivo recibido",
                    "estado_asignado": "COMPLETADO"
                })
                print(f"[\u2713] Emisión completada con éxito. Correlation ID: {correlation_id}")
            else:
                transaccion.estado = EstadoTransaccion.ERROR_EMISION # Estado final con rechazo lógico[cite: 1]
                auditoria_nueva.append({
                    "evento": f"Rechazo lógico del destino (NACK)",
                    "estado_asignado": "ERROR_EMISION"
                })
                print(f"[X] Sistema destino rechazó el mensaje (ERROR_EMISION).")
        else:
            # Estado ante falla definitiva de conexión[cite: 1]
            transaccion.estado = EstadoTransaccion.ERROR_PERMANENTE
            auditoria_nueva.append({
                "evento": "Falla de red definitiva tras 3 intentos",
                "estado_asignado": "ERROR_PERMANENTE"
            })
            print(f"[X] Fallaron los {max_intentos} intentos. Estado: ERROR_PERMANENTE.")

        # Reasignación de los diccionarios copiados para forzar el guardado en PostgreSQL[cite: 1]
        transaccion.payloads = payloads_actualizados
        transaccion.auditoria_historica = auditoria_nueva
        session.commit()

    except Exception as e:
        session.rollback()
        print(f"[X] Error crítico en el módulo de emisión: {e}")
    finally:
        session.close()