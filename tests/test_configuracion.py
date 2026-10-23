"""Exportar / importar la configuracion del motor (core/configuracion_repo.py)."""
import copy
import json
import os

import pytest

from core import configuracion_repo as C
from core import equipos_repo, equivalencias_repo, mapeo_repo, config_repo

MODALIDADES = ["RADIOLOGIA", "RADIOGRAFIA CONTRASTADA", "TOMOGRAFIA", "RESONANCIA MAGNETICA",
               "MAMOGRAFIA", "ECOGRAFIA", "DENSITOMETRIA OSEA", "MEDICINA NUCLEAR"]


class Almacen:
    """Dobles en memoria de los cuatro repositorios."""

    def __init__(self):
        self.mapeos = {"ADT": {"00100020": ["PID-3"]}, "ORM": {"00100020": ["PID-3"], "00080050": ["OBR-3"]}}
        self.fijos = {"ADT": {"MSH-4": "ARP03", "PV1-2": "O"}, "ORM": {"MSH-4": "ARP03", "OBR-21": "{codigo_equipo}"}}
        self.equipos = {m: {"modalidad": m, "codigo_equipo": c, "descripcion_equipo": "EQUIPO " + c, "unidad_negocio": ""}
                        for m, c in zip(MODALIDADES, ["DX", "DX", "CT", "MR", "MG", "US", "BMD", "NM"])}
        self.canales = {k: {"clave": k, "host": "127.0.0.1", "puerto": 2575, "aet": None, "aet_local": None, "activo": True}
                        for k in ("worklist_scu", "destino_adt", "destino_orm")}
        self.equiv = {}
        self.fallar_en = None  # para simular una interrupcion a mitad de camino


@pytest.fixture
def alm(monkeypatch, tmp_path):
    a = Almacen()
    monkeypatch.setenv("MOTORDICOM_DATA", str(tmp_path))
    monkeypatch.setattr(mapeo_repo, "obtener_mapeos", lambda t: copy.deepcopy(a.mapeos[t]))
    monkeypatch.setattr(mapeo_repo, "obtener_valores_fijos", lambda t: dict(a.fijos[t]))

    def reemplazar(t, mapeos, fijos):
        a.mapeos[t], a.fijos[t] = copy.deepcopy(mapeos), {k: v for k, v in fijos.items() if v}
    monkeypatch.setattr(mapeo_repo, "reemplazar", reemplazar)
    monkeypatch.setattr(equipos_repo, "listar", lambda: [dict(a.equipos[m], es_defecto=False) for m in MODALIDADES])

    def guardar(m, cod, desc="", un=""):
        if a.fallar_en == m:
            raise RuntimeError("falla simulada")
        a.equipos[m] = {"modalidad": m, "codigo_equipo": cod, "descripcion_equipo": desc, "unidad_negocio": un}
    monkeypatch.setattr(equipos_repo, "guardar", guardar)
    monkeypatch.setattr(config_repo, "listar", lambda: [dict(c, nombre="x", id="1") for c in a.canales.values()])

    def upsert_canal(clave, datos):
        if clave not in a.canales:
            return None
        a.canales[clave].update({k: v for k, v in datos.items() if v is not None})
        return a.canales[clave]
    monkeypatch.setattr(config_repo, "upsert", upsert_canal)
    monkeypatch.setattr(equivalencias_repo, "listar", lambda: list(a.equiv.values()))

    def upsert_eq(origen, codigo, destino="", modalidad=None):
        k = equivalencias_repo.normalizar(origen)
        previa = (a.equiv.get(k) or {}).get("modalidad_ris")
        a.equiv[k] = {"descripcion_origen": origen, "codigo_destino": codigo, "descripcion_destino": destino or origen,
                      "modalidad_ris": modalidad or previa}
    monkeypatch.setattr(equivalencias_repo, "upsert", upsert_eq)
    return a


def archivo(**secciones):
    return {"formato": C.FORMATO, "version": C.VERSION, "secciones": secciones}


# ---------- exportar ----------
def test_exportar_por_defecto_solo_lo_reutilizable_entre_hospitales(alm):
    cfg = C.exportar(hospital="Hospital A")
    assert cfg["formato"] == C.FORMATO and cfg["version"] == 1 and cfg["origen"]["hospital"] == "Hospital A"
    assert set(cfg["secciones"]) == {"mensajes", "equipos"}            # sin canales ni equivalencias
    assert cfg["secciones"]["mensajes"]["ORM"]["valores_fijos"]["OBR-21"] == "{codigo_equipo}"
    assert [e["modalidad"] for e in cfg["secciones"]["equipos"]] == MODALIDADES
    json.dumps(cfg)                                                       # serializable


def test_exportar_secciones_opcionales_y_desconocida(alm):
    alm.equiv["a"] = {"descripcion_origen": "rx", "codigo_destino": "5", "descripcion_destino": "RX", "modalidad_ris": "RADIOLOGIA"}
    cfg = C.exportar(["canales", "equivalencias"])
    assert set(cfg["secciones"]) == {"canales", "equivalencias"}
    assert cfg["secciones"]["canales"][0].keys() == {"clave", "host", "puerto", "aet", "aet_local", "activo"}
    with pytest.raises(C.ConfiguracionInvalida):
        C.exportar(["inventada"])


def test_ida_y_vuelta_entre_dos_motores_distintos(alm):
    """Se exporta la configuracion de un hospital y se importa en un motor configurado distinto."""
    alm.fijos["ORM"].update({"MSH-4": "HOSP-A", "OBR-18": "{unidad_negocio}", "PID-5": "{00100010:apellido}^^{00100010:nombres}^"})
    alm.equipos["TOMOGRAFIA"].update(codigo_equipo="CT-A", unidad_negocio="UN-A")
    alm.canales["destino_adt"].update(host="10.1.1.1", puerto=5556)
    alm.equiv["tc"] = {"descripcion_origen": "TC", "codigo_destino": "7", "descripcion_destino": "TC", "modalidad_ris": "TOMOGRAFIA"}
    del alm.fijos["ADT"]["PV1-2"]
    original = C.exportar(C.SECCIONES)

    # El "otro hospital": todo distinto
    alm.mapeos = {"ADT": {"00100010": ["PID-9"]}, "ORM": {}}
    alm.fijos = {"ADT": {"MSH-4": "OTRO", "PV1-2": "I"}, "ORM": {"ORC-1": "NW"}}
    alm.equipos["TOMOGRAFIA"].update(codigo_equipo="CT-B", unidad_negocio="")
    alm.canales["destino_adt"].update(host="192.168.0.9", puerto=1)
    alm.equiv = {}
    assert C.exportar(C.SECCIONES)["secciones"] != original["secciones"]

    C.aplicar(json.loads(json.dumps(original)), list(C.SECCIONES))      # pasa por JSON, como el archivo real
    assert C.exportar(C.SECCIONES)["secciones"] == original["secciones"]


# ---------- validar ----------
@pytest.mark.parametrize("cfg,fragmento", [
    ([], "no es una configuracion"),
    ({"formato": "otro"}, "no es una configuracion"),
    ({"formato": C.FORMATO, "version": 99, "secciones": {}}, "version mas nueva"),
    ({"formato": C.FORMATO, "version": 1}, "secciones"),
])
def test_archivo_invalido(alm, cfg, fragmento):
    errores, _ = C.validar(cfg, ["mensajes"])
    assert any(fragmento in e for e in errores)


def test_validaciones_de_mensajes(alm):
    malo = archivo(mensajes={"XYZ": {}, "ADT": {"mapeos": {"zz": ["PID-3"], "00100020": ["pid3"]},
                                                 "valores_fijos": {"PID 5": "x", "PID-5": "{inventado}", "MSH-4": 7}}})
    errores, _ = C.validar(malo, ["mensajes"])
    texto = " | ".join(errores)
    for esperado in ("tipo desconocido 'XYZ'", "tag 'zz'", "campo HL7 invalido 'pid3'", "campo HL7 invalido 'PID 5'",
                     "marcador desconocido {inventado}", "debe ser texto"):
        assert esperado in texto


def test_marcadores_validos_y_campos_fuera_de_catalogo_son_aviso(alm):
    ok = archivo(mensajes={"ORM": {"mapeos": {}, "valores_fijos": {
        "PID-5": "{00100010:apellido}^^{00100010:nombres}^", "ORC-7": "1^^^{cita}^^1", "OBR-18": "{unidad_negocio}", "NTE-9": "x"}}})
    errores, avisos = C.validar(ok, ["mensajes"])
    assert errores == [] and any("NTE-9" in a for a in avisos)


def test_validaciones_de_equipos_canales_y_equivalencias(alm):
    malo = archivo(
        equipos=[{"modalidad": "RADIOLOGIA", "codigo_equipo": ""}, {"modalidad": "INVENTADA", "codigo_equipo": "X"},
                 {"modalidad": "TOMOGRAFIA", "codigo_equipo": "CT"}, {"modalidad": "TOMOGRAFIA", "codigo_equipo": "CT2"}],
        canales=[{"clave": "otro", "host": "h", "puerto": 80}, {"clave": "destino_adt", "host": "", "puerto": 99999},
                 {"clave": "destino_orm", "host": "h", "puerto": "80"}],
        equivalencias=[{"descripcion_origen": "", "codigo_destino": "1"}, {"descripcion_origen": "x", "codigo_destino": "1", "modalidad_ris": "nada"}])
    errores, _ = C.validar(malo, list(C.SECCIONES))
    texto = " | ".join(errores)
    for esperado in ("falta el codigo del equipo", "modalidad no valida 'INVENTADA'", "esta repetida", "clave desconocida 'otro'",
                     "falta el host", "puerto debe ser un entero", "faltan la descripcion de origen", "Modalidad del RIS no valida"):
        assert esperado in texto, esperado


def test_seccion_ausente_es_aviso_no_error(alm):
    errores, avisos = C.validar(archivo(equipos=[]), ["mensajes", "equipos"])
    assert errores == [] and any("'mensajes' no esta en el archivo" in a for a in avisos)


# ---------- comparar / vista previa ----------
def test_vista_previa_agregar_cambiar_quitar(alm):
    nuevo = archivo(mensajes={"ADT": {"mapeos": {"00100020": ["PID-3"], "00100010": ["PID-5"]},
                                       "valores_fijos": {"MSH-4": "OTRO", "MSH-18": "UTF-8"}}})
    r = C.analizar(nuevo)
    c = r["cambios"]["mensajes"]
    assert r["errores"] == [] and (c["agregar"], c["cambiar"], c["quitar"]) == (2, 1, 1)   # +mapeo +MSH-18 / MSH-4 / -PV1-2
    acciones = {(d["clave"], d["accion"]) for d in c["detalle"]}
    assert ("ADT MSH-4", "cambiar") in acciones and ("ADT PV1-2", "quitar") in acciones
    assert not any(k.startswith("ORM") for k, _ in acciones)       # el ORM no viene en el archivo: no se toca
    assert {"mensaje": "ADT", "campo": "MSH-4", "valor": "OTRO"} in r["valores_del_hospital"]


def test_vista_previa_no_modifica_nada(alm):
    antes = copy.deepcopy(alm.fijos)
    C.analizar(archivo(mensajes={"ADT": {"mapeos": {}, "valores_fijos": {"MSH-4": "X"}}}))
    assert alm.fijos == antes


def test_equipos_y_canales_solo_agregan_o_cambian(alm):
    nuevo = archivo(equipos=[{"modalidad": "RADIOLOGIA", "codigo_equipo": "RX001", "descripcion_equipo": "", "unidad_negocio": "CD1"}],
                    canales=[{"clave": "destino_adt", "host": "10.0.0.5", "puerto": 5556}])
    c = C.analizar(nuevo, ["equipos", "canales"])["cambios"]
    assert (c["equipos"]["cambiar"], c["equipos"]["quitar"]) == (1, 0) and (c["canales"]["cambiar"], c["canales"]["quitar"]) == (1, 0)


# ---------- aplicar ----------
def test_aplicar_reemplaza_mensajes_y_guarda_respaldo(alm, tmp_path):
    nuevo = archivo(mensajes={"ADT": {"mapeos": {"00100010": ["PID-5"]}, "valores_fijos": {"MSH-4": "HOSP2", "MSH-18": "UTF-8"}}})
    r = C.aplicar(nuevo, ["mensajes"], usuario="ernesto")
    assert r["aplicado"] and r["resumen"] == {"mensajes": ["ADT"]}
    assert alm.fijos["ADT"] == {"MSH-4": "HOSP2", "MSH-18": "UTF-8"} and alm.mapeos["ADT"] == {"00100010": ["PID-5"]}
    assert alm.fijos["ORM"]["OBR-21"] == "{codigo_equipo}"                  # el ORM no estaba en el archivo: intacto
    resp = json.load(open(r["respaldo"], encoding="utf-8"))                  # el respaldo tiene lo ANTERIOR, completo
    assert os.path.dirname(r["respaldo"]) == str(tmp_path / "backups")
    assert resp["secciones"]["mensajes"]["ADT"]["valores_fijos"]["MSH-4"] == "ARP03" and set(resp["secciones"]) == set(C.SECCIONES)


def test_el_respaldo_permite_volver_atras(alm):
    r = C.aplicar(archivo(mensajes={"ADT": {"mapeos": {}, "valores_fijos": {"MSH-4": "OTRO"}}}), ["mensajes"])
    assert alm.fijos["ADT"] == {"MSH-4": "OTRO"}
    C.aplicar(json.load(open(r["respaldo"], encoding="utf-8")), ["mensajes"])
    assert alm.fijos["ADT"] == {"MSH-4": "ARP03", "PV1-2": "O"}


def test_equipos_canales_y_equivalencias_se_aplican_sin_borrar_lo_demas(alm):
    alm.equiv["otro"] = {"descripcion_origen": "otro", "codigo_destino": "9", "descripcion_destino": "otro", "modalidad_ris": None}
    nuevo = archivo(equipos=[{"modalidad": "ECOGRAFIA", "codigo_equipo": "ECOXERT", "descripcion_equipo": "ECO", "unidad_negocio": "CD1"}],
                    canales=[{"clave": "destino_orm", "host": "172.31.3.150", "puerto": 5556, "aet": None}],
                    equivalencias=[{"descripcion_origen": "TC de cerebro", "codigo_destino": "523", "modalidad_ris": "TOMOGRAFIA"}])
    C.aplicar(nuevo, list(C.SECCIONES))
    assert alm.equipos["ECOGRAFIA"]["codigo_equipo"] == "ECOXERT" and alm.equipos["RADIOLOGIA"]["codigo_equipo"] == "DX"
    assert alm.canales["destino_orm"]["host"] == "172.31.3.150" and alm.canales["destino_adt"]["host"] == "127.0.0.1"
    assert len(alm.equiv) == 2 and alm.equiv["tc de cerebro"]["modalidad_ris"] == "TOMOGRAFIA"


def test_solo_se_aplican_las_secciones_elegidas(alm):
    nuevo = archivo(mensajes={"ADT": {"mapeos": {}, "valores_fijos": {"MSH-4": "X"}}},
                    equipos=[{"modalidad": "ECOGRAFIA", "codigo_equipo": "Z"}])
    C.aplicar(nuevo, ["equipos"])
    assert alm.equipos["ECOGRAFIA"]["codigo_equipo"] == "Z" and alm.fijos["ADT"]["MSH-4"] == "ARP03"


def test_archivo_invalido_no_modifica_ni_respalda(alm, tmp_path):
    with pytest.raises(C.ConfiguracionInvalida) as e:
        C.aplicar(archivo(mensajes={"ADT": {"valores_fijos": {"PID-5": "{inventado}"}}}), ["mensajes"])
    assert "inventado" in str(e.value) and alm.fijos["ADT"]["MSH-4"] == "ARP03"
    assert not (tmp_path / "backups").exists()


def test_interrupcion_a_mitad_informa_y_apunta_al_respaldo(alm):
    alm.fallar_en = "ECOGRAFIA"
    nuevo = archivo(mensajes={"ADT": {"mapeos": {}, "valores_fijos": {"MSH-4": "NUEVO"}}},
                    equipos=[{"modalidad": "ECOGRAFIA", "codigo_equipo": "Z"}])
    with pytest.raises(C.ConfiguracionInvalida) as e:
        C.aplicar(nuevo, ["mensajes", "equipos"])
    msg = str(e.value)
    assert "falla simulada" in msg and "mensajes" in msg and "respaldo" in msg and "configuracion_antes_de_importar" in msg


def test_canal_inexistente_en_este_motor(alm):
    del alm.canales["destino_orm"]
    with pytest.raises(C.ConfiguracionInvalida) as e:
        C.aplicar(archivo(canales=[{"clave": "destino_orm", "host": "h", "puerto": 5}]), ["canales"])
    assert "no existe en este motor" in str(e.value)
