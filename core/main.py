# core/main.py
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from models import SessionLocal, Trazabilidad  # Importado de los archivos del repo[cite: 2]

app = FastAPI(title="Motor de Integración DICOM-HL7")

# Dependencia para asegurar el cierre seguro de la conexión a la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/v1/health/channels")
def get_health_channels(db: Session = Depends(get_db)):
    # Consulta a la base de datos PostgreSQL para estados históricos
    procesados = db.query(Trazabilidad).filter(Trazabilidad.estado == "COMPLETADO").count()
    errores = db.query(Trazabilidad).filter(Trazabilidad.estado.in_(["ERROR_EMISION", "ERROR_PERMANENTE"])).count()
    
    return {
        "status": "ok",
        "canales": "activos",
        "mensajes_procesados": procesados,
        "mensajes_error": errores
    }