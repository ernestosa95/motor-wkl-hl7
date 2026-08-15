from sqlalchemy import Column, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
import uuid
import enum

Base = declarative_base()

class EstadoTransaccion(str, enum.Enum):
    INGRESADO = "INGRESADO"
    TRANSFORMADO = "TRANSFORMADO"
    COMPLETADO = "COMPLETADO"
    ERROR_EMISION = "ERROR_EMISION"
    ERROR_PERMANENTE = "ERROR_PERMANENTE"

class TransaccionIntegracion(Base):
    __tablename__ = 'trazabilidad_transacciones'

    correlation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estado = Column(Enum(EstadoTransaccion), default=EstadoTransaccion.INGRESADO, nullable=False)
    payloads = Column(JSONB, nullable=False, default={})
    auditoria_historica = Column(JSONB, nullable=False, default={})
    fecha_ingesta = Column(DateTime(timezone=True), server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())

# --- AGREGAR ESTA SECCIÓN DE CONEXIÓN ---
# Configuración centralizada para PostgreSQL
# Asegúrate de ajustar las credenciales a las de tu motor local
DATABASE_URL = "postgresql+psycopg2://postgres:tu_contraseña@localhost:5432/motordicom_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)