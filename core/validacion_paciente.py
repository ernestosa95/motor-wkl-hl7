"""Validacion de los datos minimos del paciente antes de generar ADT/ORM.

El RIS rechaza (o crea fichas con datos inventados) cuando faltan el apellido, el nombre de
pila, la fecha de nacimiento o el sexo (PID-5, PID-7 y PID-8 son obligatorios segun su
especificacion). Una orden con datos incompletos se RETIENE con un motivo claro en vez de
enviarse: los datos no cambian con los reintentos, se corrigen desde la auditoria.
Se desactiva con MOTORDICOM_VALIDAR_PACIENTE=0.
"""
import datetime
import os
import re

from core.nombres import separar_nombre

TAG_ID, TAG_NOMBRE, TAG_NACIMIENTO, TAG_SEXO = "00100020", "00100010", "00100030", "00100040"
SEXOS_VALIDOS = ("F", "M", "O", "U")


class DatosPacienteInvalidos(Exception):
    """Faltan o son invalidos datos minimos del paciente. No mejora al reintentar."""


def _solo_numeros(texto: str) -> bool:
    return bool(re.fullmatch(r"[\d\s.\-/]+", texto or ""))


def _fecha_valida(valor: str) -> bool:
    if not re.fullmatch(r"\d{8}", valor or ""):
        return False
    try:
        f = datetime.datetime.strptime(valor, "%Y%m%d").date()
    except ValueError:
        return False
    return datetime.date(1900, 1, 1) <= f <= datetime.date.today()


def problemas(payload: dict) -> list:
    """Lista de motivos por los que el paciente no se puede enviar (vacia si esta completo)."""
    p = []
    if not str(payload.get(TAG_ID, "") or "").strip():
        p.append("falta el documento / ID del paciente")
    apellido, nombres = separar_nombre(payload.get(TAG_NOMBRE))
    if not apellido:
        p.append("falta el apellido")
    elif _solo_numeros(apellido):
        p.append("el apellido es solo un numero (%s)" % apellido)
    if apellido and not nombres:
        p.append("falta el nombre de pila")
    elif nombres and _solo_numeros(nombres):
        p.append("el nombre de pila es solo un numero")
    if not _fecha_valida(str(payload.get(TAG_NACIMIENTO, "") or "").strip()):
        p.append("fecha de nacimiento ausente o invalida")
    if str(payload.get(TAG_SEXO, "") or "").strip().upper() not in SEXOS_VALIDOS:
        p.append("sexo ausente o invalido")
    return p


def validar(payload: dict):
    """Lanza DatosPacienteInvalidos si el paciente esta incompleto."""
    if os.environ.get("MOTORDICOM_VALIDAR_PACIENTE", "1") == "0":
        return
    faltas = problemas(payload)
    if faltas:
        raise DatosPacienteInvalidos(
            "Datos del paciente incompletos: " + "; ".join(faltas)
            + ". Corrigelos en Auditoria > Datos del paciente y reenvia.")
