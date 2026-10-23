"""La ingesta pide y guarda los campos de comentarios del worklist."""
import pytest

pytest.importorskip("pynetdicom")  # la ingesta usa pynetdicom/pydicom (no estan en requirements-dev)
from pydicom.dataset import Dataset  # noqa: E402

from core import ingesta  # noqa: E402


def _respuesta(**extra):
    ds = Dataset()
    ds.PatientID = "1"
    ds.PatientName = "A B"
    ds.AccessionNumber = "77"
    ds.RequestedProcedureDescription = "radiografía simple de tórax, radiografía simple de ab"
    ds.RequestedProcedureComments = "radiografía simple de tórax, radiografía simple de abdomen, radiografía de mano"
    ds.ImagingServiceRequestComments = "nota del servicio"
    sps = Dataset()
    sps.Modality = "DX"
    sps.ScheduledProcedureStepStartDate = "20261023"
    sps.CommentsOnTheScheduledProcedureStep = "comentario del paso"
    ds.ScheduledProcedureStepSequence = [sps]
    for k, v in extra.items():
        setattr(ds, k, v)
    return ds


def test_payload_guarda_los_comentarios():
    p = ingesta._dataset_a_payload(_respuesta())
    assert p["00401400"].endswith("radiografía de mano")        # texto completo, sin el corte de 64
    assert p["00402400"] == "nota del servicio" and p["00400400"] == "comentario del paso"
    assert len(p["00321060"]) < len(p["00401400"])


def test_payload_sin_comentarios_queda_vacio():
    ds = _respuesta()
    del ds.RequestedProcedureComments, ds.ImagingServiceRequestComments
    p = ingesta._dataset_a_payload(ds)
    assert p["00401400"] == "" and p["00402400"] == ""


def test_la_consulta_pide_los_campos_de_comentarios():
    q = ingesta._construir_query("20261023")
    assert "RequestedProcedureComments" in q and "ImagingServiceRequestComments" in q
    assert "CommentsOnTheScheduledProcedureStep" in q.ScheduledProcedureStepSequence[0]
