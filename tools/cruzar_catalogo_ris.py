"""Cruza los estudios del motor con el catalogo de examenes del RIS y evita colisiones de codigo.

Problema que resuelve: si se dan de alta en el RIS estudios con codigos que ya ocupa otro examen,
el RIS NO los carga (o los carga sin codigo de integracion) y despues rechaza los ORM con
"Exam Code N not encoded". En el primer hospital, 314 de 522 codigos chocaban.

Entrada
  motor.csv   listado de estudios del motor (pantalla Estudios > Exportar, o la salida de
              clasificar_modalidad_ris.py): descripcion_origen;codigo;descripcion_destino;modalidad_ris;...
              La columna `codigo` puede estar vacia: se asigna uno libre.
  exams.csv   catalogo de examenes exportado del RIS (columnas Description;Code;ExternalCode;...)

Salida (en --salida)
  informe_diferencias.csv   una fila por estudio: estado, que examen ocupa hoy su codigo, codigo propuesto
  estudios_a_cargar_en_ris.csv   solo los estudios que hay que dar de alta (codigo nuevo o aun no cargado)
  estudios_motor_importar.csv    todos los estudios con su codigo FINAL (para Estudios > Importar CSV)

    python tools/cruzar_catalogo_ris.py motor.csv exams.csv --salida salida [--desde 523]

Un codigo se considera ocupado si aparece en `Code` o en `ExternalCode` (distinto de vacio, NULL o 0)
de CUALQUIER examen del RIS. Estados: CARGADO OK (el RIS ya tiene ese texto con ese codigo), NUEVO (codigo
libre: se conserva y hay que darlo de alta), COLISION (lo ocupa otro examen), DUPLICADO (repetido en el
listado) y SIN CODIGO; en los tres ultimos se asigna un codigo libre. Los codigos nuevos son numericos y
consecutivos a partir de --desde (por defecto, el siguiente al mayor codigo numerico del RIS o del listado).
"""
import argparse
import csv
import os
import re
import sys
import unicodedata

VACIOS = {"", "NULL", "0"}


def normalizar(texto):
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip()


def leer_csv(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        lector = csv.DictReader(fh, delimiter=";")
        return list(lector), list(lector.fieldnames or [])


def codigos_ocupados(examenes_ris):
    """Codigos que el RIS ya usa, y mapa codigo -> descripcion del examen que lo ocupa."""
    ocupados, dueno = set(), {}
    for e in examenes_ris:
        for campo in ("Code", "ExternalCode"):
            c = (e.get(campo) or "").strip()
            if c.upper() not in VACIOS:
                ocupados.add(c)
                dueno.setdefault(c, (e.get("Description") or "").strip())
    return ocupados, dueno


def asignar_codigos(estudios, examenes_ris, desde=None):
    """Devuelve la lista de resultados por estudio: dict(estado, codigo_final, ocupa, estudio)."""
    ocupados, dueno = codigos_ocupados(examenes_ris)
    usados_motor = set()
    numericos = [int(c) for c in list(ocupados) + [(e.get("codigo") or "").strip() for e in estudios]
                 if re.fullmatch(r"\d+", c or "")]
    siguiente = desde if desde is not None else (max(numericos) + 1 if numericos else 1)

    def libre():
        nonlocal siguiente
        while str(siguiente) in ocupados or str(siguiente) in usados_motor:
            siguiente += 1
        c = str(siguiente)
        siguiente += 1
        return c

    resultados = []
    # Pasada 1: los estudios ya bien cargados (mismo texto en ese codigo) conservan el suyo
    for e in estudios:
        cod = (e.get("codigo") or "").strip()
        texto = normalizar(e.get("descripcion_origen"))
        en_ris = dueno.get(cod)
        if cod and en_ris is not None and normalizar(en_ris) == texto and cod not in usados_motor:
            usados_motor.add(cod)
            resultados.append({"estudio": e, "estado": "CARGADO OK", "codigo_final": cod, "ocupa": en_ris})
        else:
            resultados.append({"estudio": e, "estado": None, "codigo_final": None, "ocupa": en_ris or ""})

    # Pasada 2: un codigo libre en el RIS se conserva (hay que darlo de alta) y se reserva
    # antes de repartir codigos nuevos, para que no se los lleve otro estudio.
    for r in resultados:
        if r["estado"]:
            continue
        cod = (r["estudio"].get("codigo") or "").strip()
        if not cod:
            r["estado"] = "SIN CODIGO: se asigna uno libre"
        elif cod in usados_motor:
            r["estado"] = "DUPLICADO en el listado: se asigna otro"
        elif cod in ocupados:
            r["estado"] = "COLISION: el codigo lo ocupa otro examen"
        else:
            r["estado"] = "NUEVO: codigo libre, se da de alta"
            r["codigo_final"] = cod
            usados_motor.add(cod)

    # Pasada 3: se reparten codigos nuevos a los que lo necesitan
    for r in resultados:
        if r["codigo_final"] is None:
            r["codigo_final"] = libre()
            usados_motor.add(r["codigo_final"])
    return resultados


def escribir(ruta, cabecera, filas):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\r\n")
        w.writerow(cabecera)
        w.writerows(filas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("motor")
    ap.add_argument("exams")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--desde", type=int, default=None, help="primer codigo nuevo a usar")
    a = ap.parse_args(argv)

    estudios, cab = leer_csv(a.motor)
    ris, _ = leer_csv(a.exams)
    if "descripcion_origen" not in cab:
        sys.exit("El listado del motor debe tener la columna descripcion_origen.")
    if "codigo" not in cab:
        cab.insert(1, "codigo")
    resultados = asignar_codigos(estudios, ris, a.desde)

    os.makedirs(a.salida, exist_ok=True)
    informe, a_cargar, importar = [], [], []
    for r in resultados:
        e = r["estudio"]
        fila = [r["codigo_final"] if c == "codigo" else (e.get(c) or "") for c in cab]
        importar.append(fila)
        if r["estado"] != "CARGADO OK":
            a_cargar.append(fila)
        informe.append([e.get("codigo") or "", e.get("descripcion_origen") or "", r["estado"],
                        r["ocupa"] if r["estado"].startswith("COLISION") else "", r["codigo_final"]])
    escribir(os.path.join(a.salida, "informe_diferencias.csv"),
             ["codigo_motor", "descripcion_motor", "estado", "examen_que_ocupa_el_codigo", "codigo_final"], informe)
    escribir(os.path.join(a.salida, "estudios_a_cargar_en_ris.csv"), cab, a_cargar)
    escribir(os.path.join(a.salida, "estudios_motor_importar.csv"), cab, importar)

    print("Estudios: %d | ya cargados: %d | a dar de alta: %d" % (len(resultados), len(importar) - len(a_cargar), len(a_cargar)))
    for estado in sorted({r["estado"] for r in resultados}):
        print("  %-48s %d" % (estado, sum(1 for r in resultados if r["estado"] == estado)))
    if a_cargar:
        nuevos = [int(f[cab.index("codigo")]) for f in a_cargar if f[cab.index("codigo")].isdigit()]
        if nuevos:
            print("Codigos nuevos: %d a %d" % (min(nuevos), max(nuevos)))
    print("Archivos en", os.path.abspath(a.salida))


if __name__ == "__main__":
    main()
