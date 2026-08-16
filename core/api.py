from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from models import SessionLocal, TransaccionIntegracion, EstadoTransaccion, ConfiguracionNodo, ReglaMapeo, Usuario

# Configuración JWT y Seguridad
SECRET_KEY = "tecnoimagen_llave_secreta_integracion_clinica"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")

app = FastAPI(title="MotorDICOM API", description="Servicio de Integración Clínica")

# Configuración de Orígenes Permitidos (CORS)
origins = [
    "http://localhost:5173",  # Puerto por defecto de Vite/React/Vue
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Permite GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],
)

def obtener_sesion_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FUNCIONES DE SEGURIDAD ---
def verificar_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def obtener_hash_password(password):
    return pwd_context.hash(password)

def crear_token_acceso(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obtener_usuario_actual(token: str = Depends(oauth2_scheme), db: Session = Depends(obtener_sesion_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# --- SCHEMAS ---
class NodoConfig(BaseModel):
    ip: str
    aetitle: str
    puerto: int

class MapeoReglaSchema(BaseModel):
    tag_dicom: str
    nombre_dicom: str
    campo_hl7: str

# --- ENDPOINTS DE AUTENTICACIÓN ---
@app.post("/api/v1/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(obtener_sesion_db)):
    # Inyección de usuario admin inicial si la tabla está vacía
    if not db.query(Usuario).first():
        db.add(Usuario(username="admin", hashed_password=obtener_hash_password("admin123")))
        db.commit()

    user = db.query(Usuario).filter(Usuario.username == form_data.username).first()
    if not user or not verificar_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = crear_token_acceso(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

# --- ENDPOINTS PROTEGIDOS ---
@app.get("/api/v1/health/channels")
def estado_canales(db: Session = Depends(obtener_sesion_db), current_user: Usuario = Depends(obtener_usuario_actual)):
    procesados = db.query(TransaccionIntegracion).filter(TransaccionIntegracion.estado == EstadoTransaccion.COMPLETADO).count()
    errores_logicos = db.query(TransaccionIntegracion).filter(TransaccionIntegracion.estado == EstadoTransaccion.ERROR_EMISION).count()
    errores_red = db.query(TransaccionIntegracion).filter(TransaccionIntegracion.estado == EstadoTransaccion.ERROR_PERMANENTE).count()

    return {
        "sistema": "online",
        "canales": {
            "dicom_ingesta": {"estado": "activo", "tipo": "C-FIND SCU"},
            "hl7_emision": {"estado": "activo", "tipo": "MLLP", "puerto": 5000}
        },
        "metricas": {"mensajes_procesados": procesados, "errores_emision": errores_logicos, "errores_permanentes": errores_red}
    }

@app.get("/api/v1/config/nodo")
def obtener_configuracion(db: Session = Depends(obtener_sesion_db), current_user: Usuario = Depends(obtener_usuario_actual)):
    nodo = db.query(ConfiguracionNodo).first()
    if not nodo:
        return {"ip": "", "aetitle": "", "puerto": 104}
    return {"ip": nodo.ip, "aetitle": nodo.aetitle, "puerto": nodo.puerto}

@app.post("/api/v1/config/nodo")
def guardar_configuracion(config: NodoConfig, db: Session = Depends(obtener_sesion_db), current_user: Usuario = Depends(obtener_usuario_actual)):
    nodo = db.query(ConfiguracionNodo).first()
    if not nodo:
        nodo = ConfiguracionNodo(ip=config.ip, aetitle=config.aetitle, puerto=config.puerto)
        db.add(nodo)
    else:
        nodo.ip, nodo.aetitle, nodo.puerto = config.ip, config.aetitle, config.puerto
    db.commit()
    return {"mensaje": "Configuración guardada exitosamente"}

@app.get("/api/v1/mapeos")
def obtener_mapeos(db: Session = Depends(obtener_sesion_db), current_user: Usuario = Depends(obtener_usuario_actual)):
    mapeos = db.query(ReglaMapeo).all()
    if not mapeos:
        defaults = [
            {"tag_dicom": "(0010,0020)", "nombre_dicom": "Patient ID", "campo_hl7": "PID-3"},
            {"tag_dicom": "(0010,0010)", "nombre_dicom": "Patient's Name", "campo_hl7": "PID-5"},
            {"tag_dicom": "(0010,0030)", "nombre_dicom": "Patient's Birth Date", "campo_hl7": "PID-7"},
            {"tag_dicom": "(0010,0040)", "nombre_dicom": "Patient's Sex", "campo_hl7": "PID-8"},
            {"tag_dicom": "(0008,0050)", "nombre_dicom": "Accession Number", "campo_hl7": "OBR-2 / OBR-3"},
            {"tag_dicom": "(0032,1060)", "nombre_dicom": "Requested Procedure Description", "campo_hl7": "OBR-4"},
            {"tag_dicom": "(0008,0090)", "nombre_dicom": "Referring Physician's Name", "campo_hl7": "OBR-16"},
            {"tag_dicom": "(0008,0060)", "nombre_dicom": "Modality", "campo_hl7": "OBR-24"},
            {"tag_dicom": "(0040,0002)", "nombre_dicom": "Scheduled Procedure Step Start Date", "campo_hl7": "OBR-27"}
        ]
        for d in defaults: db.add(ReglaMapeo(**d))
        db.commit()
        mapeos = db.query(ReglaMapeo).all()
    return mapeos

@app.post("/api/v1/mapeos")
def actualizar_mapeos(reglas: List[MapeoReglaSchema], db: Session = Depends(obtener_sesion_db), current_user: Usuario = Depends(obtener_usuario_actual)):
    db.query(ReglaMapeo).delete()
    for r in reglas: db.add(ReglaMapeo(tag_dicom=r.tag_dicom, nombre_dicom=r.nombre_dicom, campo_hl7=r.campo_hl7))
    db.commit()
    return {"mensaje": "Reglas guardadas"}

@app.get("/api/v1/worklist/activas")
def ordenes_activas(accession: Optional[str] = None, paciente: Optional[str] = None, db: Session = Depends(obtener_sesion_db), current_user: Usuario = Depends(obtener_usuario_actual)):
    query = db.query(TransaccionIntegracion).filter(TransaccionIntegracion.estado == EstadoTransaccion.INGRESADO)
    if accession: query = query.filter(TransaccionIntegracion.payload_dicom['00080050'].astext.ilike(f"%{accession}%"))
    if paciente: query = query.filter(TransaccionIntegracion.payload_dicom['00100010'].astext.ilike(f"%{paciente}%"))
    return [{
        "correlation_id": str(r.correlation_id),
        "accession_number": (r.payload_dicom or {}).get("00080050", "N/A"),
        "patient_id": (r.payload_dicom or {}).get("00100020", "N/A"),
        "paciente": (r.payload_dicom or {}).get("00100010", "N/A").replace("^", " "),
        "estudio": (r.payload_dicom or {}).get("00321060", "ESTUDIO NO ESPECIFICADO"),
        "estado": r.estado.value
    } for r in query.all()]