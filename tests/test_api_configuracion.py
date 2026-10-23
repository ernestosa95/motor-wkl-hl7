"""Contrato de los endpoints de configuracion (lo que consume la pantalla)."""
import copy
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("jwt")
pytest.importorskip("passlib")
from fastapi.testclient import TestClient  # noqa: E402

from core import api as API  # noqa: E402
from core.auth import get_current_user  # noqa: E402
from tests.test_configuracion import alm, archivo  # noqa: E402,F401  (reutiliza los dobles en memoria)


@pytest.fixture
def cliente(alm):
    class Usuario:
        username = "ernesto"
    API.app.dependency_overrides[get_current_user] = lambda: Usuario()
    yield TestClient(API.app)
    API.app.dependency_overrides.clear()


def test_exportar_devuelve_el_archivo(cliente):
    r = cliente.get("/api/v1/configuracion/exportar", params={"hospital": "Hospital A", "comentario": "ok"})
    assert r.status_code == 200
    j = r.json()
    assert j["formato"] == "motordicom-configuracion" and j["origen"]["hospital"] == "Hospital A"
    assert set(j["secciones"]) == {"mensajes", "equipos"}


def test_exportar_con_secciones_y_seccion_invalida(cliente):
    r = cliente.get("/api/v1/configuracion/exportar", params={"secciones": "canales,equivalencias"})
    assert set(r.json()["secciones"]) == {"canales", "equivalencias"}
    r = cliente.get("/api/v1/configuracion/exportar", params={"secciones": "inventada"})
    assert r.status_code == 400 and "inventada" in r.json()["detail"]["errores"][0]


def test_importar_vista_previa_no_modifica(cliente, alm):
    antes = copy.deepcopy(alm.fijos)
    cfg = archivo(mensajes={"ADT": {"mapeos": {}, "valores_fijos": {"MSH-4": "HOSP-A"}}})
    r = cliente.post("/api/v1/configuracion/importar", json={"configuracion": cfg, "aplicar": False})
    assert r.status_code == 200
    j = r.json()
    assert j["errores"] == [] and j["cambios"]["mensajes"]["cambiar"] == 1 and j["secciones_en_archivo"] == ["mensajes"]
    assert alm.fijos == antes


def test_importar_aplica_y_devuelve_el_respaldo(cliente, alm):
    cfg = archivo(mensajes={"ADT": {"mapeos": {}, "valores_fijos": {"MSH-4": "HOSP-A"}}},
                  equipos=[{"modalidad": "ECOGRAFIA", "codigo_equipo": "ECOXERT"}])
    r = cliente.post("/api/v1/configuracion/importar", json={"configuracion": cfg, "secciones": ["mensajes"], "aplicar": True})
    assert r.status_code == 200 and r.json()["secciones"] == ["mensajes"] and r.json()["respaldo"].endswith(".json")
    assert alm.fijos["ADT"] == {"MSH-4": "HOSP-A"} and alm.equipos["ECOGRAFIA"]["codigo_equipo"] == "US"   # equipos no elegidos


def test_errores_de_validacion_llegan_como_lista(cliente, alm):
    cfg = archivo(mensajes={"ADT": {"valores_fijos": {"PID-5": "{inventado}"}}})
    for aplicar in (False, True):
        r = cliente.post("/api/v1/configuracion/importar", json={"configuracion": cfg, "secciones": ["mensajes"], "aplicar": aplicar})
        if aplicar:
            assert r.status_code == 400 and "inventado" in " ".join(r.json()["detail"]["errores"])
        else:   # la vista previa responde 200 con los errores adentro; la pantalla bloquea el boton
            assert r.status_code == 200 and "inventado" in " ".join(r.json()["errores"])
    assert alm.fijos["ADT"]["MSH-4"] == "ARP03"


def test_requiere_autenticacion(alm):
    API.app.dependency_overrides.clear()
    r = TestClient(API.app).get("/api/v1/configuracion/exportar")
    assert r.status_code in (401, 403)
