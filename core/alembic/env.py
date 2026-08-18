import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. Importamos la URL de conexión segura directamente desde database
from core.database import DATABASE_URL

# 2. Importamos Base Y el modelo directamente desde models.
# Esto asegura que Alembic registre en memoria la estructura clínica exacta antes de comparar.
from core.models import Base, RegistroTrazabilidad

# Este es el objeto de configuración de Alembic, que proporciona
# acceso a los valores dentro del archivo .ini en uso.
config = context.config

# Interpretamos el archivo de configuración para el manejo de logs.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Sobrescribimos dinámicamente la URL con nuestra cadena de conexión a PostgreSQL.
# Fundamental para la persistencia del histórico y auditorías.
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Enlazamos los metadatos de nuestros modelos para que Alembic detecte los esquemas.
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Ejecuta las migraciones en modo 'offline'.
    
    Configura el contexto con solo una URL y no un Engine. 
    Las llamadas a context.execute() emitirán las sentencias a la salida estándar,
    útil para auditar los scripts SQL generados antes de impactarlos.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Ejecuta las migraciones en modo 'online'.
    
    Crea un Engine atómico y asocia la conexión de PostgreSQL con el contexto
    para aplicar los esquemas de tablas e índices requeridos por la arquitectura.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()