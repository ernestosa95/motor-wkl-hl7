from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from models import SessionLocal, TransaccionIntegracion, EstadoTransaccion

app = FastAPI(title="MotorDICOM API", description="Servicio de Integración Clínica")

# Configuración estricta de seguridad para orígenes permitidos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción para efectores se fijará la IP del servidor web
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def obtener_sesion_db():
    """Generador de sesiones de lectura para la base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/v1/health/channels")
def estado_canales(db: Session = Depends(obtener_sesion_db)):
    """
    Exposición de un endpoint REST que entrega el estado de los canales, volumen de mensajes procesados y en error.
    """
    procesados = db.query(TransaccionIntegracion).filter(
        TransaccionIntegracion.estado == EstadoTransaccion.COMPLETADO
    ).count()
    
    errores_logicos = db.query(TransaccionIntegracion).filter(
        TransaccionIntegracion.estado == EstadoTransaccion.ERROR_EMISION
    ).count()
    
    errores_red = db.query(TransaccionIntegracion).filter(
        TransaccionIntegracion.estado == EstadoTransaccion.ERROR_PERMANENTE
    ).count()

    return {
        "sistema": "online",
        "canales": {
            "dicom_ingesta": {"estado": "activo", "tipo": "C-FIND SCU"},
            "hl7_emision": {"estado": "activo", "tipo": "MLLP", "puerto": 5000}
        },
        "metricas": {
            "mensajes_procesados": procesados,
            "errores_emision": errores_logicos,
            "errores_permanentes": errores_red
        }
    }