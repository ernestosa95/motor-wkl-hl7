"""Dobles de prueba: una sesion de base de datos en memoria con un solo registro."""
from core.models import EstadoMensaje


class Registro:
    def __init__(self, payload_dicom=None, payload_hl7=None, estado=EstadoMensaje.INGRESADO):
        self.correlation_id = "c1"
        self.payload_dicom_raw = payload_dicom
        self.payload_hl7 = payload_hl7
        self.estado = estado
        self.reintentos = 0
        self.detalles_error = None


class _Consulta:
    def __init__(self, registro):
        self.registro = registro

    def filter(self, *a):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.registro


class Sesion:
    def __init__(self, registro):
        self.registro = registro

    def query(self, *a):
        return _Consulta(self.registro)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def instalar_en_auditoria(monkeypatch, registro):
    """Hace que core.auditoria trabaje contra `registro` en memoria."""
    import core.auditoria as A
    monkeypatch.setattr(A, "SessionLocal", lambda: Sesion(registro))
    monkeypatch.setattr(A, "flag_modified", lambda *a, **k: None)
    return A


PACIENTE_OK = {
    "00100020": "46561380", "00100010": "CARRASCO TANIA", "00100030": "20050711",
    "00100040": "F", "00080050": "1004832", "00321060": "radiografía simple de tórax",
    "00080060": "CR", "00400002": "20261023", "00400003": "180000",
}
