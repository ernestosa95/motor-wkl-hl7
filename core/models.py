import uuid
import enum
from sqlalchemy import Column, String, Enum, Index, Integer, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine

Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)

class EstadoTransaccion(enum.Enum):
    INGRESADO = "INGRESADO"
    TRANSFORMADO = "TRANSFORMADO"
    COMPLETADO = "COMPLETADO"
    ERROR_EMISION = "ERROR_EMISION"
    ERROR_PERMANENTE = "ERROR_PERMANENTE"

class TransaccionIntegracion(Base):
    __tablename__ = "trazabilidad_integracion"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    accession_number = Column(String(64), index=True, nullable=False)
    study_instance_uid = Column(String(128), index=True, nullable=True)
    estado = Column(Enum(EstadoTransaccion), nullable=False, default=EstadoTransaccion.INGRESADO)
    
    # Base de Datos: PostgreSQL. Almacenará auditorías y payloads crudos en JSONB.
    payload_dicom = Column(JSONB, nullable=True)
    payload_hl7 = Column(String, nullable=True)

    __table_args__ = (
        Index('idx_orden_unica', 'accession_number', 'study_instance_uid', unique=True),
    )

class ConfiguracionNodo(Base):
    __tablename__ = "configuracion_nodos"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tipo = Column(String(20), nullable=False, default="WORKLIST_SCU") 
    aetitle = Column(String(16), nullable=False)
    ip = Column(String(15), nullable=False)
    puerto = Column(Integer, nullable=False)
    activo = Column(Boolean, default=True)

class ReglaMapeo(Base):
    __tablename__ = "reglas_mapeo"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tag_dicom = Column(String(20), nullable=False)
    nombre_dicom = Column(String(100), nullable=True)
    campo_hl7 = Column(String(20), nullable=False)
    activo = Column(Boolean, default=True)

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/motordicom"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)