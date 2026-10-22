import socket

# Caracteres de control MLLP
VT = b'\x0b'
FS = b'\x1c'
CR = b'\x0d'

def iniciar_servidor_mllp(host='127.0.0.1', port=2575):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print(f"Mock HIS/RIS escuchando tráfico MLLP en {host}:{port}...")
        
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(4096)
                if data:
                    print(f"[*] Trama MLLP recibida desde {addr}")
                    
                    # ACK de aceptación (MSA|AA) que referencia el MSH-10 recibido.
                    texto = data.strip(VT + FS + CR).decode('utf-8', errors='replace')
                    msh = texto.split('\r', 1)[0].split('|')
                    ctrl = msh[9] if len(msh) > 9 else ''
                    ack_hl7 = f"MSH|^~\\&|HIS|PACS|MOTORDICOM|RIS|20260815103000||ACK|ACK{ctrl}|P|2.5\rMSA|AA|{ctrl}"
                    respuesta_mllp = VT + ack_hl7.encode('utf-8') + FS + CR
                    
                    conn.sendall(respuesta_mllp)
                    print("[\u2713] ACK (AA) enviado al MotorDICOM.\n")

if __name__ == "__main__":
    iniciar_servidor_mllp()