"""tools/cruzar_catalogo_ris.py: colisiones de codigo con el catalogo del RIS."""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import cruzar_catalogo_ris as C  # noqa: E402


def ris(*examenes):
    return [{"Description": d, "Code": c, "ExternalCode": e} for d, c, e in examenes]


def est(desc, codigo=""):
    return {"descripcion_origen": desc, "codigo": codigo}


def estados(res):
    return [(r["estado"].split(":")[0], r["codigo_final"]) for r in res]


def test_cargado_bien_colision_y_sin_codigo():
    catalogo = ris(("mamografía bilateral", "2", "2"), ("D.M.O. DENSITOMETRÍA ÓSEA", "1", "0"), ("otro", "5008", "0"))
    res = C.asignar_codigos([est("Mamografía  bilateral", "2"), est("radiografía de tórax", "1"), est("TC de cerebro", "")],
                            catalogo, desde=523)
    assert estados(res) == [("CARGADO OK", "2"), ("COLISION", "523"), ("SIN CODIGO", "524")]
    assert res[1]["ocupa"] == "D.M.O. DENSITOMETRÍA ÓSEA"


def test_codigo_libre_en_el_ris_se_conserva_y_no_se_lo_lleva_otro():
    # el estudio 'a' pide el 523, que esta libre; 'b' no tiene codigo y empieza a buscar en 523
    res = C.asignar_codigos([est("b"), est("a", "523")], ris(("x", "1", "1")), desde=523)
    assert estados(res) == [("SIN CODIGO", "524"), ("NUEVO", "523")]


def test_externalcode_tambien_cuenta_como_ocupado_pero_cero_y_null_no():
    catalogo = ris(("a", "10", "ABC"), ("b", "11", "NULL"), ("c", "12", "0"))
    ocupados, _ = C.codigos_ocupados(catalogo)
    assert {"10", "ABC", "11", "12"} <= ocupados and not ({"0", "NULL", ""} & ocupados)
    assert C.asignar_codigos([est("x", "ABC")], catalogo, desde=1)[0]["estado"].startswith("COLISION")


def test_codigos_nuevos_saltan_los_ocupados_y_no_se_repiten():
    res = C.asignar_codigos([est("x"), est("y"), est("z")], ris(("a", "523", "0"), ("b", "525", "0")), desde=523)
    assert [r["codigo_final"] for r in res] == ["524", "526", "527"]


def test_duplicado_dentro_del_listado():
    res = C.asignar_codigos([est("uno", "7"), est("dos", "7")], [], desde=100)
    assert estados(res) == [("NUEVO", "7"), ("DUPLICADO en el listado", "100")]


def test_por_defecto_empieza_despues_del_mayor_codigo_numerico():
    res = C.asignar_codigos([est("x", "")], ris(("a", "5008", "0"), ("b", "VC", "VC")))
    assert res[0]["codigo_final"] == "5009"


def test_cli_genera_los_tres_archivos(tmp_path):
    motor, exams = tmp_path / "motor.csv", tmp_path / "exams.csv"
    motor.write_text("descripcion_origen;codigo;modalidad_ris\r\nmamo;2;MAMOGRAFIA\r\nrx;1;RADIOLOGIA\r\n", encoding="utf-8-sig")
    exams.write_text("Description;Code;ExternalCode\r\nmamo;2;2\r\nDMO;1;0\r\n", encoding="utf-8-sig")
    C.main([str(motor), str(exams), "--salida", str(tmp_path / "out"), "--desde", "100"])
    leer = lambda n: list(csv.DictReader(open(tmp_path / "out" / n, encoding="utf-8-sig"), delimiter=";"))
    assert [(f["descripcion_origen"], f["codigo"], f["modalidad_ris"]) for f in leer("estudios_motor_importar.csv")] == [
        ("mamo", "2", "MAMOGRAFIA"), ("rx", "100", "RADIOLOGIA")]
    assert [f["descripcion_origen"] for f in leer("estudios_a_cargar_en_ris.csv")] == ["rx"]
    informe = leer("informe_diferencias.csv")
    assert informe[1]["estado"].startswith("COLISION") and informe[1]["examen_que_ocupa_el_codigo"] == "DMO"
