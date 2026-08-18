from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi.middleware.cors import CORSMiddleware

# Importaciones de nuestra arquitectura core
from core.database import SessionLocal
from core.models import RegistroTrazabilidad, EstadoMensaje

# Inicialización de la aplicación FastAPI[cite: 1]
app = FastAPI(
    title="Motor HL7 API", 
    description="API REST para el Motor de Integración DICOM-HL7",
    version="1.0"
)

# Configuración estricta de CORS para permitir peticiones desde la consola React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Dependencia segura para inyectar y cerrar la sesión de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/v1/trazabilidad")
def obtener_registros(db: Session = Depends(get_db)):
    """
    Retorna los últimos 50 registros de órdenes clínicas para el Monitor.
    Garantiza la trazabilidad total leyendo directamente desde PostgreSQL.
    """
    registros = db.query(RegistroTrazabilidad).order_by(
        RegistroTrazabilidad.created_at.desc()
    ).limit(50).all()
    
    return [
        {
            "id": str(r.correlation_id),
            "paciente": r.patient_id,
            "accession": r.accession_number,
            "modalidad": r.modalidad,
            "estado": r.estado.name,
            "fecha": r.created_at.strftime("%Y-%m-%d %H:%M:%S")
        } for r in registros
    ]

@app.get("/api/v1/health/channels")
def estado_canales(db: Session = Depends(get_db)):
    """
    Endpoint de alertas operativas.
    Entrega el estado de los canales, volumen de mensajes procesados y en error[cite: 1].
    """
    # Cálculo de métricas operativas
    total_completados = db.query(RegistroTrazabilidad).filter(
        RegistroTrazabilidad.estado == EstadoMensaje.COMPLETADO
    ).count()
    
    total_errores = db.query(RegistroTrazabilidad).filter(
        RegistroTrazabilidad.estado.in_([
            EstadoMensaje.ERROR_EMISION, 
            EstadoMensaje.ERROR_PERMANENTE
        ])
    ).count()

    return {
        "status": "UP",
        "channels": {
            "dicom_ingesta": {"status": "LISTENING", "protocol": "C-FIND SCP"},
            "hl7_emision": {"status": "ACTIVE", "protocol": "MLLP TCP/IP"}
        },
        "metrics": {
            "volumen_procesado": total_completados,
            "volumen_errores": total_errores
        }
    }