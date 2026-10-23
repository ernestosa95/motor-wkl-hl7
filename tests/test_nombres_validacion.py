import pytest

from core.nombres import separar_nombre
from core import validacion_paciente as vp
from tests.fakes import PACIENTE_OK


@pytest.mark.parametrize("entrada,esperado", [
    ("CARRASCO TANIA", ("CARRASCO", "TANIA")),
    ("DE LA CRUZ JUAN CARLOS", ("DE", "LA CRUZ JUAN CARLOS")),   # regla aceptada: 1a palabra = apellido
    ("MURANO^MARIANA", ("MURANO", "MARIANA")),
    ("YALETTI^^NEITHAN EMANUEL", ("YALETTI", "NEITHAN EMANUEL")),
    ("SOLO", ("SOLO", "")),
    ("", ("", "")),
    (None, ("", "")),
])
def test_separar_nombre(entrada, esperado):
    assert separar_nombre(entrada) == esperado


def test_paciente_completo_no_tiene_problemas():
    assert vp.problemas(PACIENTE_OK) == []


@pytest.mark.parametrize("cambio,fragmento", [
    ({"00100010": "CARRASCO"}, "nombre de pila"),
    ({"00100010": "10105138"}, "apellido es solo un numero"),
    ({"00100010": ""}, "apellido"),
    ({"00100030": "20990101"}, "nacimiento"),
    ({"00100030": "2005-07-11"}, "nacimiento"),
    ({"00100040": ""}, "sexo"),
    ({"00100020": ""}, "documento"),
])
def test_problemas_detectados(cambio, fragmento):
    assert any(fragmento in p for p in vp.problemas({**PACIENTE_OK, **cambio}))


def test_sexo_O_es_valido():
    assert vp.problemas({**PACIENTE_OK, "00100040": "O"}) == []


def test_validar_lanza_con_motivo_y_se_puede_desactivar(monkeypatch):
    malo = {**PACIENTE_OK, "00100010": "CARRASCO"}
    with pytest.raises(vp.DatosPacienteInvalidos) as e:
        vp.validar(malo)
    assert "nombre de pila" in str(e.value) and "Auditoria" in str(e.value)
    monkeypatch.setenv("MOTORDICOM_VALIDAR_PACIENTE", "0")
    vp.validar(malo)  # no lanza
