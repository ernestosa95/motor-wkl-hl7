import pytest

from core import modalidad_ris as M
from core import equivalencias_repo as eq


@pytest.mark.parametrize("texto,dicom,esperada", [
    ("radiografía simple de tórax", "CR/DX/CT", M.RADIOLOGIA),
    ("TC de cerebro", "CR", M.TOMOGRAFIA),                       # manda el texto, no la DICOM
    ("tomografía computarizada de cerebro", "CT", M.TOMOGRAFIA),
    ("resonancia magnética de rodilla", "MR", M.RESONANCIA),
    ("RMN (resonancia magnética) de cerebro con contraste", "MR", M.RESONANCIA),
    ("mamografía bilateral", "MG/DX/CT", M.MAMOGRAFIA),
    ("deglución por videofluoroscopia", "CR", M.CONTRASTADA),
    ("estudio de tórax con radioisótopos", "CR", M.MEDICINA_NUCLEAR),
    ("ecografía de abdomen", "US", M.ECOGRAFIA),
    ("drenaje", "CT", M.TOMOGRAFIA),                            # sin pista en el texto: usa la DICOM
])
def test_clasificar(texto, dicom, esperada):
    assert M.clasificar(texto, dicom)[0] == esperada


def test_mezcla_de_modalidades_se_marca():
    mod, criterio, _ = M.clasificar("radiografía simple de pelvis, ecografía de la cadera", "CR")
    assert (mod, criterio) == (M.RADIOLOGIA, "mixto")


def test_normalizar():
    assert eq.normalizar("  Radiografía   SIMPLE de Tórax ") == "radiografia simple de torax"


def test_csv_con_columna_modalidad_ris_por_nombre():
    t = ("descripcion_origen;codigo;descripcion_destino;modalidad_ris;modalidad_dicom;ordenes\r\n"
         "rx torax;1;;RADIOLOGIA;CR;5\r\n"
         "TC;2;;tomografia;CT;1\r\n"
         "mamo;3;;INVENTADA;MG;1\r\n"
         "pendiente;;;RADIOLOGIA;CR;9\r\n")
    filas, errores, omitidas = eq.parsear_csv(t)
    assert [f[0] for f in filas] == ["rx torax", "TC"]
    assert [f[3] for f in filas] == ["RADIOLOGIA", "TOMOGRAFIA"]   # se normaliza (mayusculas, sin espacios)
    assert omitidas == 1 and any("no valida" in e for e in errores)


def test_csv_comillas_separadores_y_sin_modalidad():
    filas, errores, omitidas = eq.parsear_csv('descripcion_origen;codigo\r\n"TC ""contraste""; abdomen";22\r\n')
    assert filas == [('TC "contraste"; abdomen', "22", "", "")] and not errores
    assert eq.parsear_csv("estudio,codigo\nrx,1\n")[0] == [("rx", "1", "", "")]
    assert eq.parsear_csv("a\tb\nrx\t5\n")[0][1] == ("rx", "5", "", "")


def test_modalidad_valida_tolera_tildes_y_mayusculas():
    assert eq._modalidad_valida("  Tomografía ") == "TOMOGRAFIA"
    assert eq._modalidad_valida("") is None
    with pytest.raises(ValueError):
        eq._modalidad_valida("inventada")
