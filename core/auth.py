import os
import datetime

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import Usuario

# En producción, JWT_SECRET DEBE venir de una variable de entorno segura.
SECRET_KEY = os.getenv("JWT_SECRET", "dev-inseguro-cambiar-en-produccion")
ALGORITHM = "HS256"
TOKEN_EXP_MIN = int(os.getenv("JWT_EXP_MIN", "480"))  # 8 horas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plano: str, hasheado: str) -> bool:
    return pwd_context.verify(plano, hasheado)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def autenticar(db: Session, username: str, password: str):
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if not user or not user.activo or not verify_password(password, user.hashed_password):
        return None
    return user


def crear_token(username: str) -> str:
    exp = datetime.datetime.utcnow() + datetime.timedelta(minutes=TOKEN_EXP_MIN)
    return jwt.encode({"sub": username, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise cred_exc
    except jwt.PyJWTError:
        raise cred_exc

    user = db.query(Usuario).filter(Usuario.username == username).first()
    if not user or not user.activo:
        raise cred_exc
    return user
