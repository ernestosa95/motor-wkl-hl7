"""Crea o restablece el usuario 'admin'. Ejecutar una vez tras las migraciones.

    python -m core.crear_admin

Usa la misma DB y modelos que el resto del sistema (core.database / core.models).
"""
from core.database import SessionLocal, engine
from core.models import Base, Usuario
from core.auth import hash_password

# Atajo de arranque: crea la tabla 'usuarios' si aún no existe.
# En un flujo formal esto lo hace Alembic (ver instrucciones de migración).
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    user = db.query(Usuario).filter(Usuario.username == "admin").first()
    if not user:
        db.add(Usuario(username="admin", hashed_password=hash_password("admin123")))
        db.commit()
        print("Usuario 'admin' creado (password: admin123).")
    else:
        user.hashed_password = hash_password("admin123")
        db.commit()
        print("Password de 'admin' restablecida a 'admin123'.")
finally:
    db.close()
