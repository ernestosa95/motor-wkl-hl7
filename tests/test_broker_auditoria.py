"""Estados por mensaje, reintentos independientes, reenvio y correccion de datos."""
import datetime

import pytest

from core.models import EstadoMensaje as E
from tests.fakes import Registro, instalar_en_auditoria, PACIENTE_OK

OK = {"ok": True, "estado": "ENVIADO", "destino": "h:1", "cuando": "2026-10-23 17:00:00", "ack": "A"}


# ---------- estado de la orden derivado de los dos mensajes ----------
@pytest.mark.parametrize("envios,esperado", [
    ({"adt": OK, "orm": OK}, E.COMPLETADO),
    ({"adt": OK, "orm": {"estado": "PENDIENTE", "ultimo_error": "x"}}, E.ERROR_EMISION),
    ({"adt": OK, "orm": {"estado": "ERROR_PERMANENTE", "ultimo_error": "x"}}, E.ERROR_PERMANENTE),
    ({"adt": {"estado": "ERROR_PERMANENTE", "ultimo_error": "x"}, "orm": OK}, E.ERROR_PERMANENTE),
    ({"adt": {"estado": "PENDIENTE"}}, E.TRANSFORMADO),
    ({"adt": {"ok": True}, "orm": {"ok": True}}, E.COMPLETADO),       # registros anteriores al desacople
])
def test_estado_orden(envios, esperado):
    import core.auditoria as A
    assert A.estado_orden(envios) == esperado


# ---------- reenvio ----------
def test_reenviar_orden_completada_regenera_con_msh10_nuevo_y_no_duplica(monkeypatch):
    import sys, types
    reg = Registro(PACIENTE_OK, {"adt": "MSH|viejo", "orm": "MSH|viejo", "envios": {"adt": dict(OK), "orm": dict(OK)}}, E.COMPLETADO)
    A = instalar_en_auditoria(monkeypatch, reg)
    encolados = []
    broker = types.ModuleType("core.broker")
    broker.tarea_enviar_mensaje = lambda cid, p, t: encolados.append(t)
    monkeypatch.setitem(sys.modules, "core.broker", broker)

    assert A.reenviar("c1") == ["adt", "orm"] and encolados == ["adt", "orm"]
    e = reg.payload_hl7["envios"]["adt"]
    assert not e["ok"] and e["estado"] == "PENDIENTE" and e["reenvios"] == 1 and e["anterior"]["ack"] == "A"
    assert "adt" not in reg.payload_hl7 and "orm" not in reg.payload_hl7   # se regeneran (MSH-10 nuevo)
    assert reg.estado == E.TRANSFORMADO

    assert A.reenviar("c1") == []                                           # en curso: no duplica
    vieja = (datetime.datetime.now() - datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    reg.payload_hl7["envios"]["orm"]["actualizado"] = vieja
    assert A.reenviar("c1") == ["orm"]                                      # atascado: se libera
    assert A.reenviar("c1", "xyz") == []


# ---------- correccion de datos del paciente ----------
def test_corregir_paciente_registra_antes_y_despues(monkeypatch):
    reg = Registro({**PACIENTE_OK, "00100010": "CARRASCO", "00100040": ""})
    A = instalar_en_auditoria(monkeypatch, reg)
    antes = A.datos_paciente(reg.payload_dicom_raw)
    assert any("nombre de pila" in p for p in antes["problemas"]) and any("sexo" in p for p in antes["problemas"])

    d = A.corregir_paciente("c1", {"nombres": "TANIA", "sexo": "f"}, usuario="ernesto")
    assert d["problemas"] == [] and (d["apellido"], d["nombres"], d["sexo"]) == ("CARRASCO", "TANIA", "F")
    assert reg.payload_dicom_raw["00100010"] == "CARRASCO^TANIA"
    c = reg.payload_dicom_raw["_correcciones"][0]
    assert c["usuario"] == "ernesto" and c["antes"]["00100010"] == "CARRASCO" and c["despues"]["00100040"] == "F"
    A.corregir_paciente("c1", {"sexo": "F"})                                # sin cambios: no agrega registro
    assert len(reg.payload_dicom_raw["_correcciones"]) == 1


@pytest.mark.parametrize("cambios", [{"apellido": "  "}, {"nombres": ""}, {"fecha_nacimiento": "20990101"}, {"sexo": "X"}])
def test_corregir_paciente_rechaza_datos_invalidos(monkeypatch, cambios):
    A = instalar_en_auditoria(monkeypatch, Registro(dict(PACIENTE_OK)))
    with pytest.raises(ValueError):
        A.corregir_paciente("c1", cambios)


# ---------- broker: cada mensaje con su propio estado y reintentos ----------
@pytest.fixture
def entorno(monkeypatch):
    """core.broker con base, equivalencias y MLLP simulados."""
    import types, sys
    import core.auditoria as A
    import core.broker as B
    from core.catalogos import DEFAULT_MAPEOS
    from core.serializador_hl7 import construir_mensaje

    reg = Registro(dict(PACIENTE_OK))
    hl7 = {}
    ctx = {}

    def obtener_hl7(c):
        return dict(hl7) if hl7 else None

    def actualizar_envio(c, tipo, envio=None, mensaje=None, borrar_mensaje=False):
        if borrar_mensaje:
            hl7.pop(tipo, None)
        if mensaje is not None:
            hl7[tipo] = mensaje
        env = hl7.setdefault("envios", {})
        if envio is not None:
            actual = dict(env.get(tipo) or {})
            actual.update(envio)
            env[tipo] = actual
        reg.estado = A.estado_orden(env)

    def transformar(payload, tipo, msg_id=None):
        from core.validacion_paciente import validar
        validar(payload)
        fijos = {"OBR-4": "{codigo_estudio}^{descripcion_estudio}"} if tipo == "ORM" else {}
        return construir_mensaje(payload, DEFAULT_MAPEOS[tipo], fijos, tipo, msg_id=msg_id, contexto=ctx.get("estudio"))

    enviados = []
    estado_red = {"adt_falla": False}

    def mllp(msg, host, puerto):
        tipo = msg.split("\r")[0].split("|")[8]
        if tipo.startswith("ADT") and estado_red["adt_falla"]:
            raise B.ErrorEmision("ACK negativo")
        enviados.append(tipo)
        return "ACK"

    monkeypatch.setattr(B, "obtener_hl7", obtener_hl7)
    monkeypatch.setattr(B, "actualizar_envio", actualizar_envio)
    monkeypatch.setattr(B, "obtener_payload_dicom", lambda c: dict(reg.payload_dicom_raw))
    monkeypatch.setattr(B, "procesar_transformacion", transformar)
    monkeypatch.setattr(B, "enviar_mensaje_mllp", mllp)
    monkeypatch.setattr(B, "_destino", lambda clave: ("h", 1))
    return types.SimpleNamespace(B=B, reg=reg, hl7=hl7, ctx=ctx, enviados=enviados, red=estado_red)


class Tarea:
    def __init__(self, retries):
        self.retries = retries


def correr(B, tipo, quedan=3):
    try:
        B.tarea_enviar_mensaje("c1", {}, tipo, task=Tarea(quedan))
        return "ok"
    except B.ErrorEmision:
        return "reintento"


def test_adt_pasa_y_orm_sin_codigo_de_estudio_se_reintenta_aparte(entorno):
    B = entorno.B
    assert correr(B, "adt") == "ok"
    assert correr(B, "orm", 3) == "reintento"                  # sin equivalencia de estudio
    assert entorno.reg.estado == E.ERROR_EMISION and entorno.enviados == ["ADT^A04"]
    assert correr(B, "orm", 0) == "ok"                         # ultimo intento: ya no relanza
    env = entorno.hl7["envios"]
    assert env["adt"]["ok"] and env["orm"]["estado"] == "ERROR_PERMANENTE"
    assert entorno.reg.estado == E.ERROR_PERMANENTE
    assert "orm" not in entorno.hl7                              # no se emitio un ORM sin codigo

    entorno.ctx["estudio"] = {"codigo_estudio": "523", "descripcion_estudio": "RX TORAX"}
    env["orm"]["estado"] = "PENDIENTE"
    assert correr(B, "orm") == "ok" and correr(B, "adt") == "ok"
    assert entorno.enviados == ["ADT^A04", "ORM^O01"]            # el ADT aceptado no se reenvia
    assert entorno.reg.estado == E.COMPLETADO and "523^RX TORAX" in entorno.hl7["orm"]


def test_cada_mensaje_tiene_sus_reintentos_y_conserva_el_msh10(entorno):
    B, red = entorno.B, entorno.red
    red["adt_falla"] = True
    assert correr(B, "adt", 3) == "reintento"
    id1 = entorno.hl7["adt"].split("\r")[0].split("|")[9]
    assert correr(B, "adt", 2) == "reintento"
    assert entorno.hl7["adt"].split("\r")[0].split("|")[9] == id1   # mismo MSH-10 entre reintentos
    assert entorno.hl7["envios"]["adt"]["intentos_fallidos"] == 2
    red["adt_falla"] = False
    assert correr(B, "adt", 1) == "ok" and entorno.hl7["envios"]["adt"]["ok"]


def test_paciente_incompleto_es_error_permanente_sin_reintentos(entorno):
    entorno.reg.payload_dicom_raw["00100010"] = "CARRASCO"
    assert correr(entorno.B, "adt", 3) == "ok"                  # no relanza: no mejora al reintentar
    e = entorno.hl7["envios"]["adt"]
    assert e["estado"] == "ERROR_PERMANENTE" and "nombre de pila" in e["ultimo_error"]
    assert entorno.enviados == []
    entorno.reg.payload_dicom_raw["00100010"] = "CARRASCO^TANIA"   # se corrige y se reintenta
    e["estado"] = "PENDIENTE"
    assert correr(entorno.B, "adt") == "ok" and entorno.enviados == ["ADT^A04"]
