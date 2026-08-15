import socket

# Caracteres de control MLLP
VT = b'\x0b'
FS = b'\x1c'
CR = b'\x0d'

def iniciar_servidor_mllp(host='127.0.0.1', port=5000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f"Mock HIS/RIS escuchando tráfico MLLP en {host}:{port}...")
        
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(4096)
                if data:
                    print(f"[*] Trama MLLP recibida desde {addr}")
                    
                    # Generamos una respuesta de aceptación síncrona (ACK - MSA|AA)
                    ack_hl7 = "MSH|^~\\&|HIS|PACS|MOTORDICOM|RIS|20260815103000||ACK^O01|MSG00001|P|2.5\rMSA|AA|MSG00001"
                    respuesta_mllp = VT + ack_hl7.encode('utf-8') + FS + CR
                    
                    conn.sendall(respuesta_mllp)
                    print("[\u2713] ACK (AA) enviado al MotorDICOM.\n")

if __name__ == "__main__":
    iniciar_servidor_mllp()