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
import csv, re, sys, unicodedata, collections

if len(sys.argv) != 3:
    sys.exit(__doc__)
ENTRADA, SALIDA = sys.argv[1], sys.argv[2]

DENS, ECO, MAMO, NUC = "DENSITOMETRIA OSEA", "ECOGRAFIA", "MAMOGRAFIA", "MEDICINA NUCLEAR"
CONTR, RADIO, RM, TC = "RADIOGRAFIA CONTRASTADA", "RADIOLOGIA", "RESONANCIA MAGNETICA", "TOMOGRAFIA"
DICOM = {"CR": RADIO, "DX": RADIO, "CT": TC, "MR": RM, "MG": MAMO, "US": ECO, "NM": NUC, "BMD": DENS}

def norm(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))

# (patron, modalidad) en orden de prioridad dentro de cada parte del texto
REGLAS = [
    (r"ecograf|ultrasonid", ECO),
    (r"densitometr", DENS),
    (r"medicina nuclear|radioisotop|gammagraf|spect|\bpet\b", NUC),
    (r"mamograf", MAMO),
    (r"resonancia|\brm\b|\brmn\b|angiorresonancia", RM),
    (r"tomograf|\btc\b|\btac\b|angiotomia|angiografia por tc|guia de tc", TC),
    (r"cistouretrograf|seriada|transito esofag|trago de bario|\bbario\b|deglucion|videofluoroscop|fluoroscop|enema|urograf|histerosalping", CONTR),
    (r"radiograf|\brx\b|rayos x", RADIO),
]

def clasifica_parte(p):
    for patron, mod in REGLAS:
        if re.search(patron, p):
            return mod
    return None

filas = list(csv.reader(open(ENTRADA, encoding="utf-8-sig"), delimiter=";"))
cab, datos = filas[0], [f for f in filas[1:] if any(f)]
assert cab[:2] == ["descripcion_origen", "codigo"], cab

res, cuenta = [], collections.Counter()
for f in datos:
    desc, codigo, _, dicom, ordenes = (f + [""] * 5)[:5]
    partes = [p.strip() for p in re.split(r",\s+", norm(desc))]
    mods = [m for m in (clasifica_parte(p) for p in partes) if m]
    unicas = list(dict.fromkeys(mods))
    dicoms = [DICOM[d] for d in dicom.split("/") if d in DICOM]
    nota = ""
    if len(unicas) == 1:
        mod, criterio = unicas[0], "texto"
    elif len(unicas) > 1:
        mod, criterio = unicas[0], "mixto"
        nota = "mezcla " + " + ".join(unicas) + "; se asigno la primera"
    elif dicoms:
        mod, criterio = dicoms[0], "dicom"
        nota = "el texto no indica la modalidad; se uso la DICOM (%s)" % dicom
    else:
        mod, criterio, nota = RADIO, "sin_clasificar", "no se pudo clasificar"
    # contraste entre texto y modalidad DICOM
    if criterio == "texto" and dicoms and mod not in dicoms:
        nota = (nota + "; " if nota else "") + "difiere de la DICOM (%s)" % dicom
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
