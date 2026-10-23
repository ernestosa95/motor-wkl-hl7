"""Separacion del nombre del paciente en apellido y nombres (regla unica del motor)."""


def separar_nombre(valor):
    """Devuelve (apellido, nombres) a partir del PatientName del worklist.

    - Formato DICOM `APELLIDO^NOMBRE[^...]`: apellido = componente 1, nombres = el resto.
    - Sin `^` (el worklist trae `APELLIDO NOMBRES`): primera palabra = apellido, el resto = nombres.
      Se equivoca con apellidos compuestos (`DE LA CRUZ JUAN`); es una decision conocida y
      aceptada. Se corrige a mano desde la auditoria (Datos del paciente).
    """
    v = str(valor or "").strip()
    if "^" in v:
        comps = v.split("^")
        return comps[0].strip(), " ".join(c.strip() for c in comps[1:] if c.strip())
    palabras = v.split(None, 1)
    return (palabras[0] if palabras else ""), (palabras[1].strip() if len(palabras) > 1 else "")
