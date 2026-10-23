"""Configuracion comun de las pruebas.

No necesitan PostgreSQL ni Huey: se reemplazan por dobles en memoria. Ejecutar con
    pip install -r requirements-dev.txt
    python -m pytest tests -q
"""
import os
import sys
import types

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, RAIZ)
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("MOTORDICOM_DATA", os.path.join(RAIZ, "tests", ".datos"))

# Huey real abriria una cola SQLite; las tareas se ejecutan como funciones normales.
huey = types.ModuleType("huey")


class _SqliteHuey:
    def __init__(self, *a, **k):
        pass

    def task(self, *a, **k):
        return lambda f: f


huey.SqliteHuey = _SqliteHuey
sys.modules.setdefault("huey", huey)
