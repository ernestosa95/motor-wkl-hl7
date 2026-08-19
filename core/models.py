import uuid
import enum
from sqlalchemy import (
    Column, String, DateTime, Integer, Boolean, Enum, Index,
    UniqueConstraint, func, text,
)
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
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True, default=uuid.uuid4)
    patient_id = Column(String(64), nullable=True, index=True)
    accession_number = Column(String(64), nullable=True, index=True)
    modalidad = Column(String(16), nullable=True)
    estado = Column(
        Enum(EstadoMensaje, name="estado_mensaje_enum", create_type=False),
        nullable=False, default=EstadoMensaje.INGRESADO, index=True,
    )
    reintentos = Column(Integer, default=0, nullable=False)
    payload_dicom_raw = Column(JSONB, nullable=True)
    payload_hl7 = Column(JSONB, nullable=True)
    detalles_error = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        Index("idx_trazabilidad_estado_fecha", "estado", "created_at"),
        Index("idx_trazabilidad_payload_gin", "payload_dicom_raw", postgresql_using="gin"),
        Index("idx_trazabilidad_hl7_gin", "payload_hl7", postgresql_using="gin"),
    )


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    # Nuevo: fuerza el cambio de contrasena en el primer inicio de sesion
    debe_cambiar_password = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Canal(Base):
    __tablename__ = "canales"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clave = Column(String(32), unique=True, nullable=False, index=True)
    nombre = Column(String(64), nullable=False)
    host = Column(String(128), nullable=False)
    puerto = Column(Integer, nullable=False)
    aet = Column(String(32), nullable=True)
    aet_local = Column(String(32), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Mapeo(Base):
    """Arista de mapeo por tipo de mensaje: (tipo, dicom_tag) -> hl7_field."""
    __tablename__ = "mapeos"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_mensaje = Column(String(8), nullable=False, index=True)  # 'ADT' | 'ORM'
    dicom_tag = Column(String(16), nullable=False, index=True)
    hl7_field = Column(String(16), nullable=False)
    __table_args__ = (
        UniqueConstraint("tipo_mensaje", "dicom_tag", "hl7_field", name="uq_mapeo_tipo_tag_campo"),
    )


class ValorFijo(Base):
    """Valor fijo (constante) para un campo HL7 en un tipo de mensaje."""
    __tablename__ = "valores_fijos"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_mensaje = Column(String(8), nullable=False, index=True)
    hl7_field = Column(String(16), nullable=False)
    valor = Column(String(256), nullable=False)
    __table_args__ = (
        UniqueConstraint("tipo_mensaje", "hl7_field", name="uq_valorfijo_tipo_campo"),
    )