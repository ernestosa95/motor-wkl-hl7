import pytest

from core.catalogos import DEFAULT_MAPEOS
from core.serializador_hl7 import (
    construir_mensaje, escapar, EstudioSinCodigo, EquipoSinConfigurar, _fecha_hora_cita,
)
from tests.fakes import PACIENTE_OK


def segmentos(msg):
    return {l.split("|")[0]: l.split("|") for l in msg.split("\r")}


def orm(fijos, contexto=None, payload=None):
    return construir_mensaje(payload or PACIENTE_OK, DEFAULT_MAPEOS["ORM"], fijos, "ORM", contexto=contexto)


def test_msh_automatico_y_emisor():
    s = segmentos(orm({}))
    assert s["MSH"][2:4] == ["SISGH", "ARP03"] and s["MSH"][8] == "ORM^O01" and s["MSH"][11] == "2.5"


def test_valor_fijo_es_hl7_literal_con_repeticiones_y_componentes():
    s = segmentos(orm({"PID-3": "{00100020}^^^PK~{00100020}^DU^^CF"}))
    assert s["PID"][3] == "46561380^^^PK~46561380^DU^^CF"


def test_componente_se_aplica_sobre_el_campo_mapeado():
    s = segmentos(orm({"PID-3.4": "ARP03", "PID-3.5": "DNI"}))
    assert s["PID"][3] == "46561380^^^ARP03^DNI"


def test_nombre_apellido_y_nombres():
    s = segmentos(orm({"PID-5": "{00100010:apellido}^^{00100010:nombres}^"}))
    assert s["PID"][5] == "CARRASCO^^TANIA^"


def test_dato_dicom_se_escapa_pero_el_valor_fijo_no():
    assert escapar("A|B&C~D") == "A\\F\\B\\T\\C\\R\\D"
    p = {**PACIENTE_OK, "00080050": "12|3"}
    s = segmentos(orm({"ORC-2": "{00080050}~X"}, payload=p))
    assert s["ORC"][2] == "12\\F\\3~X"


def test_cita_y_ahora():
    assert _fecha_hora_cita({"00400002": "20261023", "00400003": "105000"}, "AHORA") == "20261023105000"
    assert _fecha_hora_cita({"00400002": "20261023", "00400003": "1050"}, "AHORA") == "20261023105000"
    assert _fecha_hora_cita({"00400002": "20261023"}, "AHORA") == "20261023000000"
    assert _fecha_hora_cita({}, "AHORA") == "AHORA"
    s = segmentos(orm({"ORC-7": "1^^^{cita}^^1", "ORC-9": "{ahora}"}))
    assert s["ORC"][7] == "1^^^20261023180000^^1" and s["ORC"][9] == s["MSH"][6]  # MSH-7 (MSH-1 es el separador)


def test_estudio_y_equipo_se_resuelven_o_el_mensaje_no_se_emite():
    fijos = {"OBR-4": "{codigo_estudio}^{descripcion_estudio}", "OBR-21": "{codigo_equipo}", "OBR-18": "{unidad_negocio}"}
    ctx = {"codigo_estudio": "523", "descripcion_estudio": "TC", "codigo_equipo": "CT", "unidad_negocio": "CD1"}
    s = segmentos(orm(fijos, ctx))
    assert s["OBR"][4] == "523^TC" and s["OBR"][21] == "CT" and s["OBR"][18] == "CD1"
    with pytest.raises(EstudioSinCodigo):
        orm({"OBR-4": "{codigo_estudio}"}, {})
    with pytest.raises(EquipoSinConfigurar):
        orm({"OBR-21": "{codigo_equipo}"}, {"_modalidad": "RADIOLOGIA"})
    with pytest.raises(EquipoSinConfigurar):  # unidad de negocio vacia
        orm({"OBR-18": "{unidad_negocio}"}, {"unidad_negocio": ""})


def test_marcador_desconocido_da_error():
    with pytest.raises(ValueError):
        orm({"OBR-4": "{inventado}"})


def test_msh10_se_puede_conservar():
    m = construir_mensaje(PACIENTE_OK, DEFAULT_MAPEOS["ADT"], {}, "ADT", msg_id="ABC123")
    assert segmentos(m)["MSH"][9] == "ABC123"
