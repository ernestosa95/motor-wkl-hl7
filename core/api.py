from typing import Optional, Dict, List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.models import RegistroTrazabilidad, EstadoMensaje, Usuario
from core.auth import autenticar, crear_token, get_current_user, get_usuario_token, get_db, hash_password
from core import config_repo, mapeo_repo, auditoria, equivalencias_repo
from core.conectividad import test_dicom_echo, test_mllp

app = FastAPI(title="Motor HL7 API", version="1.6")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    config_repo.seed_canales()
    mapeo_repo.seed_mapeos()


# ---------- Autenticación ----------

@app.post("/api/v1/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = autenticar(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Usuario o contraseña incorrectos")
    return {
        "access_token": crear_token(user.username),
        "token_type": "bearer",
        "debe_cambiar_password": bool(user.debe_cambiar_password),
    }


class CambioPasswordIn(BaseModel):
    password_nueva: str


@app.post("/api/v1/auth/cambiar-password")
def cambiar_password(body: CambioPasswordIn,
                     db: Session = Depends(get_db),
                     user: Usuario = Depends(get_usuario_token)):
    nueva = (body.password_nueva or "").strip()
    if len(nueva) < 8:
        raise HTTPException(status_code=400,
                            detail="La contraseña debe tener al menos 8 caracteres")
    u = db.query(Usuario).filter(Usuario.username == user.username).first()
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    u.hashed_password = hash_password(nueva)
    u.debe_cambiar_password = False
    db.commit()
    return {"ok": True}


# ---------- Trazabilidad ----------

@app.get("/api/v1/trazabilidad")
def obtener_registros(db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
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
            "fecha": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "tiene_hl7": bool(r.payload_hl7),
            "mensajes": auditoria.resumen_envios(r.payload_hl7),
        }
        for r in registros
    ]


@app.get("/api/v1/trazabilidad/{correlation_id}/hl7")
def obtener_hl7(correlation_id: str, db: Session = Depends(get_db),
                _user: Usuario = Depends(get_current_user)):
    r = db.query(RegistroTrazabilidad).filter(
        RegistroTrazabilidad.correlation_id == correlation_id
    ).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {
        "accession": r.accession_number,
        "estado": r.estado.name,
        "hl7": r.payload_hl7 or {},
    }


@app.get("/api/v1/trazabilidad/{correlation_id}/auditoria")
def auditoria_orden(correlation_id: str, db: Session = Depends(get_db),
                    _user: Usuario = Depends(get_current_user)):
    """Vista de auditoría: datos de ingreso, estado actual, HL7 y detalle de error."""
    r = db.query(RegistroTrazabilidad).filter(
        RegistroTrazabilidad.correlation_id == correlation_id
    ).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {
        "id": str(r.correlation_id),
        "accession": r.accession_number,
        "paciente": r.patient_id,
        "modalidad": r.modalidad,
        "estado": r.estado.name,
        "reintentos": r.reintentos,
        "ingresado": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
        "actualizado": r.updated_at.strftime("%Y-%m-%d %H:%M:%S") if r.updated_at else None,
        "payload_dicom": r.payload_dicom_raw or {},
        "hl7": r.payload_hl7 or {},
        "detalles_error": r.detalles_error or None,
        "mensajes": {
            t: {**(e or {}), "estado": auditoria.estado_mensaje(e)}
            for t, e in (((r.payload_hl7 or {}).get("envios")) or {}).items()
        },
    }


@app.post("/api/v1/trazabilidad/{correlation_id}/reprocesar")
def reprocesar_orden(correlation_id: str, tipo: Optional[str] = None,
                     db: Session = Depends(get_db),
                     _user: Usuario = Depends(get_current_user)):
    """Reprocesa los mensajes en error permanente (ADT, ORM o ambos con tipo vacio)."""
    r = db.query(RegistroTrazabilidad).filter(
        RegistroTrazabilidad.correlation_id == correlation_id
    ).first()
    if r is None:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    if tipo is not None and tipo.lower() not in ("adt", "orm"):
        raise HTTPException(status_code=400, detail="Tipo de mensaje invalido (adt | orm)")
    if r.estado == EstadoMensaje.COMPLETADO:
        raise HTTPException(status_code=409, detail="La orden ya fue completada")
    if not r.payload_dicom_raw:
        raise HTTPException(status_code=400,
                            detail="No se pudo reprocesar (sin payload original)")
    reencolados = auditoria.reprocesar(correlation_id, tipo)
    if not reencolados:
        # Sin mensajes en error permanente: o ya hay un reintento automatico en cola
        # (reprocesar ahora duplicaria el envio) o ese mensaje ya fue aceptado.
        raise HTTPException(status_code=409,
                            detail="No hay mensajes en error permanente para reprocesar "
                                   "(hay un reintento automatico pendiente o ya fueron aceptados)")
    return {"ok": True, "reprocesados": [t.upper() for t in reencolados]}


@app.get("/api/v1/health/channels")
def estado_canales(db: Session = Depends(get_db), _user: Usuario = Depends(get_current_user)):
    completados = db.query(RegistroTrazabilidad).filter(
        RegistroTrazabilidad.estado == EstadoMensaje.COMPLETADO).count()
    errores = db.query(RegistroTrazabilidad).filter(
        RegistroTrazabilidad.estado.in_([EstadoMensaje.ERROR_EMISION, EstadoMensaje.ERROR_PERMANENTE])).count()
    return {"status": "UP", "metrics": {"volumen_procesado": completados, "volumen_errores": errores}}


# ---------- Canales ----------

class CanalIn(BaseModel):
    host: Optional[str] = None
    puerto: Optional[int] = None
    aet: Optional[str] = None
    aet_local: Optional[str] = None
    activo: Optional[bool] = None


@app.get("/api/v1/canales")
def listar_canales(_user: Usuario = Depends(get_current_user)):
    return config_repo.listar()


@app.put("/api/v1/canales/{clave}")
def actualizar_canal(clave: str, body: CanalIn, _user: Usuario = Depends(get_current_user)):
    actualizado = config_repo.upsert(clave, body.dict(exclude_unset=True))
    if actualizado is None:
        raise HTTPException(status_code=404, detail=f"Canal '{clave}' no encontrado")
    return actualizado


@app.post("/api/v1/canales/{clave}/test")
def probar_canal(clave: str, _user: Usuario = Depends(get_current_user)):
    canal = config_repo.obtener_canal(clave)
    if canal is None:
        raise HTTPException(status_code=404, detail=f"Canal '{clave}' no encontrado")
    if clave == "worklist_scu":
        ok, mensaje = test_dicom_echo(canal["host"], canal["puerto"], canal["aet"], canal["aet_local"])
    else:
        ok, mensaje = test_mllp(canal["host"], canal["puerto"])
    return {"ok": ok, "mensaje": mensaje}


# ---------- Mapeos por tipo ----------

class MapeosIn(BaseModel):
    mapeos: Dict[str, List[str]]
    valores_fijos: Dict[str, str] = {}


@app.get("/api/v1/mapeos/{tipo}")
def obtener_mapeos(tipo: str, _user: Usuario = Depends(get_current_user)):
    tipo = tipo.upper()
    if tipo not in ("ADT", "ORM"):
        raise HTTPException(status_code=404, detail="Tipo de mensaje inválido")
    return mapeo_repo.obtener_todo(tipo)


@app.put("/api/v1/mapeos/{tipo}")
def guardar_mapeos(tipo: str, body: MapeosIn, _user: Usuario = Depends(get_current_user)):
    tipo = tipo.upper()
    if tipo not in ("ADT", "ORM"):
        raise HTTPException(status_code=404, detail="Tipo de mensaje inválido")
    return mapeo_repo.reemplazar(tipo, body.mapeos, body.valores_fijos)


# ---------- Equivalencias de estudio (texto del worklist -> codigo del destino) ----------

class EquivalenciaIn(BaseModel):
    descripcion_origen: str
    codigo_destino: str
    descripcion_destino: str = ""


class ImportarIn(BaseModel):
    csv: str


@app.get("/api/v1/equivalencias")
def listar_equivalencias(_user: Usuario = Depends(get_current_user)):
    return equivalencias_repo.panel()


@app.put("/api/v1/equivalencias")
def guardar_equivalencia(body: EquivalenciaIn, _user: Usuario = Depends(get_current_user)):
    try:
        return equivalencias_repo.upsert(body.descripcion_origen, body.codigo_destino,
                                         body.descripcion_destino)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/equivalencias/{id_}")
def eliminar_equivalencia(id_: str, _user: Usuario = Depends(get_current_user)):
    if not equivalencias_repo.eliminar(id_):
        raise HTTPException(status_code=404, detail="Equivalencia no encontrada")
    return {"ok": True}


@app.post("/api/v1/equivalencias/importar")
def importar_equivalencias(body: ImportarIn, _user: Usuario = Depends(get_current_user)):
    return equivalencias_repo.importar_csv(body.csv)
