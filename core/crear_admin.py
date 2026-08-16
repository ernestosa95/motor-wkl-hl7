from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Usuario
from passlib.context import CryptContext

# 1. Definición estricta de la cadena de conexión a la BD correcta
DATABASE_URL = "postgresql+psycopg2://usuario:usuario@localhost:5432/motordicom_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. Inicialización de seguridad y sesión
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

try:
    # Print de control de trazabilidad
    print(f"Auditando conexión... Destino: {engine.url.database}")
    
    # Búsqueda o creación del usuario
    user = db.query(Usuario).filter(Usuario.username == "admin").first()
    
    if not user:
        hashed_pw = pwd_context.hash("admin123")
        nuevo_usuario = Usuario(username="admin", hashed_password=hashed_pw)
        db.add(nuevo_usuario)
        db.commit()
        print("Éxito: Usuario 'admin' creado y encriptado.")
    else:
        user.hashed_password = pwd_context.hash("admin123")
        db.commit()
        print("Éxito: Contraseña del usuario 'admin' restablecida.")
except Exception as e:
    print(f"Error al interactuar con la base de datos: {e}")
finally:
    db.close()