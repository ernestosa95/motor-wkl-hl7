import socket
from core.auditoria import actualizar_estado
from core.models import EstadoMensaje

def enviar_mensaje_mllp(correlation_id, payload_hl7, host="127.0.0.1", puerto=2575):
    """
    Envía el mensaje HL7 encapsulado en MLLP y espera el ACK síncrono.
    """
    # Envoltorios estándar MLLP
    VT = b'\x0b'
    FS = b'\x1c'
    CR = b'\x0d'
    
    mensaje_bytes = VT + payload_hl7.encode('utf-8') + FS + CR
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(15.0)
            s.connect((host, puerto))
            s.sendall(mensaje_bytes)
            
            # Espera de ACK síncrono
            ack_data = s.recv(4096)
            
            if b"MSA|AA" in ack_data:
                actualizar_estado(correlation_id, EstadoMensaje.COMPLETADO)
                print(f"[OK] ACK recibido. Orden {correlation_id} completada.")
            else:
                actualizar_estado(correlation_id, EstadoMensaje.ERROR_EMISION)
                print(f"[!] NACK recibido para {correlation_id}.")
                raise ValueError("NACK devuelto por el sistema destino.")
                
    except Exception as e:
        actualizar_estado(correlation_id, EstadoMensaje.ERROR_PERMANENTE)
        print(f"[ERROR] Falla definitiva de conexión para {correlation_id}: {e}")
        raise e