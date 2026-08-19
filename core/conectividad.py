"""Pruebas de conectividad de canales.

- Worklist DICOM: C-ECHO (verification) contra el SCP.
- Salidas HL7: conexión TCP al puerto MLLP (verifica alcance, no inyecta mensajes).
"""
import socket

from pynetdicom import AE
from pynetdicom.sop_class import Verification


def test_dicom_echo(host: str, puerto: int, aet_destino: str = None,
                    aet_local: str = None, timeout: float = 5.0):
    """Devuelve (ok: bool, mensaje: str)."""
    try:
        ae = AE(ae_title=aet_local or "MOTOR_WKL")
        ae.add_requested_context(Verification)
        ae.acse_timeout = timeout
        ae.dimse_timeout = timeout
        ae.connection_timeout = timeout

        assoc = ae.associate(host, int(puerto), ae_title=aet_destino or "ANY-SCP")
        if not assoc.is_established:
            return False, "No se pudo asociar. Revisá host, puerto y AE Title del destino."

        status = assoc.send_c_echo()
        assoc.release()

        if status and getattr(status, "Status", None) == 0x0000:
            return True, "C-ECHO exitoso. La Worklist responde."
        return False, "Se asoció pero el C-ECHO no devolvió éxito."
    except Exception as e:
        return False, f"Fallo de conexión DICOM: {e}"


def test_mllp(host: str, puerto: int, timeout: float = 5.0):
    """Devuelve (ok: bool, mensaje: str). Verifica que el puerto MLLP acepte conexión TCP."""
    try:
        with socket.create_connection((host, int(puerto)), timeout=timeout):
            return True, "Conexión TCP establecida. El endpoint MLLP está accesible."
    except Exception as e:
        return False, f"No se pudo conectar al puerto MLLP: {e}"
