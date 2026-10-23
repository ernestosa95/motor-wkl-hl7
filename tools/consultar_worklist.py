"""Consulta una Modality Worklist (C-FIND) y muestra QUE datos entrega por cada
estudio, para ver si trae un codigo de procedimiento utilizable.

Por defecto NO muestra datos del paciente (nombre, ID, nacimiento): solo los del
estudio, para poder compartir la salida.

    python tools/consultar_worklist.py 172.31.3.149 8000 CLLSPS MOTOR_WKL
    python tools/consultar_worklist.py HOST PUERTO AET_DESTINO AET_PROPIO [--fecha AAAAMMDD]
                                      [--max N] [--mostrar-paciente]
"""
import argparse
import collections
import datetime
import sys

from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

PACIENTE = ("PatientName", "PatientID", "PatientBirthDate", "OtherPatientIDs",
            "PatientAddress", "PatientTelephoneNumbers", "PatientMotherBirthName")


def _codigo(ds):
    """Secuencias de codigos -> 'valor|esquema|significado'."""
    return ["%s|%s|%s" % (getattr(i, "CodeValue", ""), getattr(i, "CodingSchemeDesignator", ""),
                          getattr(i, "CodeMeaning", "")) for i in ds]


def construir_query(fecha):
    ds = Dataset()
    for attr in ("PatientName", "PatientID", "PatientBirthDate", "PatientSex", "AccessionNumber",
                 "ReferringPhysicianName", "RequestedProcedureID", "RequestedProcedureDescription",
                 "RequestedProcedurePriority", "StudyInstanceUID", "AdmissionID",
                 "ReasonForTheRequestedProcedure"):
        setattr(ds, attr, "")
    cod = Dataset()
    cod.CodeValue = ""
    cod.CodingSchemeDesignator = ""
    cod.CodeMeaning = ""
    ds.RequestedProcedureCodeSequence = [cod]

    sps = Dataset()
    for attr in ("Modality", "ScheduledStationAETitle", "ScheduledStationName",
                 "ScheduledProcedureStepID", "ScheduledProcedureStepDescription",
                 "ScheduledProcedureStepStartTime", "ScheduledProcedureStepLocation",
                 "ScheduledPerformingPhysicianName"):
        setattr(sps, attr, "")
    sps.ScheduledProcedureStepStartDate = fecha
    prot = Dataset()
    prot.CodeValue = ""
    prot.CodingSchemeDesignator = ""
    prot.CodeMeaning = ""
    sps.ScheduledProtocolCodeSequence = [prot]
    ds.ScheduledProcedureStepSequence = [sps]
    return ds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host")
    ap.add_argument("puerto", type=int)
    ap.add_argument("aet_destino")
    ap.add_argument("aet_propio")
    ap.add_argument("--fecha", default=datetime.date.today().strftime("%Y%m%d"),
                    help="fecha programada AAAAMMDD (por defecto hoy; '' = todas)")
    ap.add_argument("--max", type=int, default=3, help="cuantos estudios volcar completos")
    ap.add_argument("--mostrar-paciente", action="store_true", help="incluir datos del paciente")
    a = ap.parse_args()

    ae = AE(ae_title=a.aet_propio)
    ae.add_requested_context(ModalityWorklistInformationFind)
    assoc = ae.associate(a.host, a.puerto, ae_title=a.aet_destino)
    if not assoc.is_established:
        sys.exit("No se pudo asociar con %s:%s (AET %s)" % (a.host, a.puerto, a.aet_destino))

    resultados = []
    for status, ident in assoc.send_c_find(construir_query(a.fecha), ModalityWorklistInformationFind):
        if status and status.Status in (0xFF00, 0xFF01) and ident is not None:
            resultados.append(ident)
    assoc.release()

    print("Estudios recibidos para %s: %d\n" % (a.fecha or "todas las fechas", len(resultados)))
    if not resultados:
        return

    # Volcado completo (sin paciente salvo que se pida) de los primeros estudios
    for n, ds in enumerate(resultados[:a.max], 1):
        if not a.mostrar_paciente:
            for attr in PACIENTE:
                if attr in ds:
                    delattr(ds, attr)
        print("=" * 70, "\nESTUDIO %d (todos los atributos devueltos)\n" % n, "=" * 70, sep="")
        print(ds)

    # Resumen: que combinaciones de procedimiento/codigo aparecen y cuantas veces
    cuenta = collections.Counter()
    for ds in resultados:
        sps = ds.ScheduledProcedureStepSequence[0] if "ScheduledProcedureStepSequence" in ds and ds.ScheduledProcedureStepSequence else Dataset()
        cuenta[(
            str(getattr(ds, "RequestedProcedureDescription", "")),
            str(getattr(ds, "RequestedProcedureID", "")),
            ";".join(_codigo(getattr(ds, "RequestedProcedureCodeSequence", []))),
            str(getattr(sps, "ScheduledProcedureStepDescription", "")),
            ";".join(_codigo(getattr(sps, "ScheduledProtocolCodeSequence", []))),
            str(getattr(sps, "Modality", "")),
            str(getattr(sps, "ScheduledStationAETitle", "")),
        )] += 1
    print("=" * 70, "\nRESUMEN DE PROCEDIMIENTOS (descripcion | RP ID | codigo RP | desc. paso | codigo protocolo | modalidad | estacion)\n", "=" * 70, sep="")
    for clave, n in cuenta.most_common():
        print("%3d x  %s" % (n, "  |  ".join(c or "-" for c in clave)))


if __name__ == "__main__":
    main()
