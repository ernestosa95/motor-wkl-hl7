import uuid
import enum
from sqlalchemy import Column, String, DateTime, Integer, Enum, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class EstadoMensaje(str, enum.Enum):
    INGRESADO = "INGRESADO"
    TRANSFORMADO = "TRANSFORMADO"
    COMPLETADO = "COMPLETADO"
    ERROR_EMISION = "ERROR_EMISION"
    ERROR_PERMANENTE = "ERROR_PERMANENTE"

class RegistroTrazabilidad(Base):
    __tablename__ = "registro_trazabilidad"

    # Llave primaria interna
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identificador clínico único exigido por arquitectura
    correlation_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True, default=uuid.uuid4)
    
    # Datos extraídos para búsquedas rápidas
    patient_id = Column(String(64), nullable=True, index=True)
    accession_number = Column(String(64), nullable=True, index=True)
    modalidad = Column(String(16), nullable=True)
    
    # Estado del flujo y control de reintentos
    estado = Column(
        Enum(EstadoMensaje, name="estado_mensaje_enum", create_type=False),
        nullable=False,
        default=EstadoMensaje.INGRESADO,
        index=True
    )
    reintentos = Column(Integer, default=0, nullable=False)
    
    # Payloads en formato JSONB nativo de PostgreSQL
    payload_dicom_raw = Column(JSONB, nullable=True)
    payload_hl7 = Column(JSONB, nullable=True)
    detalles_error = Column(JSONB, nullable=True)
    
    # Marcas de tiempo para gestión de retención de 30 días
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_trazabilidad_estado_fecha", "estado", "created_at"),
        Index("idx_trazabilidad_payload_gin", "payload_dicom_raw", postgresql_using="gin"),
        Index("idx_trazabilidad_hl7_gin", "payload_hl7", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<RegistroTrazabilidad(correlation_id={self.correlation_id}, estado={self.estado})>"