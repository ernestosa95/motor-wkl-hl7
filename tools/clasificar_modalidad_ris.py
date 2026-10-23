"""Asigna a cada estudio una modalidad del RIS (una sola, de un conjunto fijo) a partir de su texto.

Entrada: el CSV que exporta la pantalla Estudios ("Exportar pendientes"), con columnas
descripcion_origen;codigo;descripcion_destino;modalidad;ordenes.
Salida: el mismo listado + modalidad_ris, y las columnas revisar/observacion con los
casos dudosos (mezclas, estudios sin modalidad en el texto, procedimientos que no son imagen).

    python tools/clasificar_modalidad_ris.py entrada.csv salida.csv

Criterio: manda el TEXTO del estudio; la modalidad DICOM del worklist solo se usa si el
texto no la indica (es poco fiable: p. ej. un mismo estudio llega como CR, DX y CT).
Si la lista de modalidades del RIS cambia, editar las constantes y REGLAS.
"""
import csv, os, re, sys, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from core.modalidad_ris import clasificar  # reglas compartidas con el motor

if len(sys.argv) != 3:
    sys.exit(__doc__)
ENTRADA, SALIDA = sys.argv[1], sys.argv[2]

filas = list(csv.reader(open(ENTRADA, encoding="utf-8-sig"), delimiter=";"))
cab, datos = filas[0], [f for f in filas[1:] if any(f)]
assert cab[:2] == ["descripcion_origen", "codigo"], cab

res, cuenta = [], collections.Counter()
for f in datos:
    desc, codigo, _, dicom, ordenes = (f + [""] * 5)[:5]
    mod, criterio, nota = clasificar(desc, dicom)
    revisar = "SI" if criterio in ("mixto", "dicom", "sin_clasificar") else "NO"
    cuenta[(mod, revisar)] += 1
    res.append([desc, codigo, desc, mod, dicom, ordenes, revisar, nota])

with open(SALIDA, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh, delimiter=";", lineterminator="\r\n")
    w.writerow(["descripcion_origen", "codigo", "descripcion_destino", "modalidad_ris",
                "modalidad_dicom", "ordenes", "revisar", "observacion"])
    w.writerows(res)

print("Total:", len(res))
for (m, r), n in sorted(cuenta.items()):
    print("%-26s revisar=%s %4d" % (m, r, n))
