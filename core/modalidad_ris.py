"""Modalidades del RIS y su deduccion a partir del texto del estudio.

El RIS admite UNA modalidad por estudio, de un conjunto fijo. La modalidad DICOM del
worklist es poco fiable (un mismo estudio llega como CR, DX y CT), por eso manda el
TEXTO y la DICOM solo se usa si el texto no la indica. Si el RIS cambia sus modalidades,
editar las constantes y REGLAS.
"""
import re
import unicodedata

DENSITOMETRIA = "DENSITOMETRIA OSEA"
ECOGRAFIA = "ECOGRAFIA"
MAMOGRAFIA = "MAMOGRAFIA"
MEDICINA_NUCLEAR = "MEDICINA NUCLEAR"
CONTRASTADA = "RADIOGRAFIA CONTRASTADA"
RADIOLOGIA = "RADIOLOGIA"
RESONANCIA = "RESONANCIA MAGNETICA"
TOMOGRAFIA = "TOMOGRAFIA"

# Orden en que se muestran
MODALIDADES_RIS = [RADIOLOGIA, CONTRASTADA, TOMOGRAFIA, RESONANCIA,
                   MAMOGRAFIA, ECOGRAFIA, DENSITOMETRIA, MEDICINA_NUCLEAR]

# Modalidad DICOM -> modalidad del RIS (solo como ultimo recurso)
DESDE_DICOM = {"CR": RADIOLOGIA, "DX": RADIOLOGIA, "CT": TOMOGRAFIA, "MR": RESONANCIA,
               "MG": MAMOGRAFIA, "US": ECOGRAFIA, "NM": MEDICINA_NUCLEAR, "BMD": DENSITOMETRIA}

# (patron sobre el texto normalizado, modalidad); gana la primera coincidencia de cada parte
REGLAS = [
    (r"ecograf|ultrasonid", ECOGRAFIA),
    (r"densitometr", DENSITOMETRIA),
    (r"medicina nuclear|radioisotop|gammagraf|spect|\bpet\b", MEDICINA_NUCLEAR),
    (r"mamograf", MAMOGRAFIA),
    (r"resonancia|\brm\b|\brmn\b|angiorresonancia", RESONANCIA),
    (r"tomograf|\btc\b|\btac\b|angiotomia|angiografia por tc|guia de tc", TOMOGRAFIA),
    (r"cistouretrograf|seriada|transito esofag|trago de bario|\bbario\b|deglucion|videofluoroscop"
     r"|fluoroscop|enema|urograf|histerosalping", CONTRASTADA),
    (r"radiograf|\brx\b|rayos x", RADIOLOGIA),
]


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _clasifica_parte(parte: str):
    for patron, mod in REGLAS:
        if re.search(patron, parte):
            return mod
    return None


def clasificar(texto: str, dicom: str = ""):
    """Devuelve (modalidad_ris, criterio, observacion).

    criterio: 'texto' | 'mixto' (el texto mezcla modalidades; se toma la primera) |
    'dicom' (el texto no la indica) | 'sin_clasificar'. 'dicom' es la modalidad DICOM
    del worklist, p. ej. 'CR/DX' o 'CT'.
    """
    partes = [p.strip() for p in re.split(r",\s+", _norm(texto))]
    mods = [m for m in (_clasifica_parte(p) for p in partes) if m]
    unicas = list(dict.fromkeys(mods))
    dicoms = [DESDE_DICOM[d.strip()] for d in str(dicom or "").split("/") if d.strip() in DESDE_DICOM]
    if len(unicas) == 1:
        obs = ""
        if dicoms and unicas[0] not in dicoms:
            obs = "difiere de la DICOM (%s)" % dicom
        return unicas[0], "texto", obs
    if len(unicas) > 1:
        return unicas[0], "mixto", "mezcla " + " + ".join(unicas) + "; se asigno la primera"
    if dicoms:
        return dicoms[0], "dicom", "el texto no indica la modalidad; se uso la DICOM (%s)" % dicom
    return RADIOLOGIA, "sin_clasificar", "no se pudo clasificar"
