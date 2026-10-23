import uuid
import datetime
from sqlalchemy.orm.attributes import flag_modified

from core.database import SessionLocal
from core.models import RegistroTrazabilidad, EstadoMensaje
from core.nombres import separar_nombre
from core import validacion_paciente as vp


def actualizar_estado(correlation_id: uuid.UUID, estado: EstadoMensaje):
    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        if registro:
            registro.estado = estado
            db.commit()
            print(f"[*] Auditoría: {correlation_id} -> {estado.name}")
    except Exception as e:
        db.rollback()
        print(f"[!] Error al actualizar estado: {e}")
    finally:
        db.close()


def guardar_hl7(correlation_id: uuid.UUID, mensajes: dict):
    """Persiste el HL7 emitido (dict con claves 'adt' y 'orm') para auditoría."""
    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        if registro:
            registro.payload_hl7 = dict(mensajes)
            flag_modified(registro, "payload_hl7")
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[!] Error al guardar HL7: {e}")
    finally:
        db.close()


def obtener_hl7(correlation_id: uuid.UUID):
    """Devuelve el payload_hl7 guardado (ADT, ORM y envios confirmados) o None."""
    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        return dict(registro.payload_hl7) if registro and registro.payload_hl7 else None
    finally:
        db.close()


def registrar_fallo(correlation_id: uuid.UUID, final: bool, detalle: dict):
    """Registra un intento fallido: suma un reintento y guarda el motivo.

    final=False -> ERROR_EMISION (queda un reintento automatico en cola).
    final=True  -> ERROR_PERMANENTE (no quedan reintentos; requiere Reprocesar).
    """
    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        if registro:
            registro.estado = EstadoMensaje.ERROR_PERMANENTE if final else EstadoMensaje.ERROR_EMISION
            registro.reintentos = (registro.reintentos or 0) + 1
            registro.detalles_error = detalle
            db.commit()
            print(f"[*] Auditoría: {correlation_id} -> {registro.estado.name}")
    except Exception as e:
        db.rollback()
        print(f"[!] Error al registrar fallo: {e}")
    finally:
        db.close()


def registrar_ingreso(correlation_id: uuid.UUID, patient_id: str,
                      accession_number: str, modalidad: str, payload_dicom: dict):
    db = SessionLocal()
    try:
        nuevo = RegistroTrazabilidad(
            correlation_id=correlation_id,
            patient_id=patient_id,
            accession_number=accession_number,
            modalidad=modalidad,
            payload_dicom_raw=payload_dicom,
            estado=EstadoMensaje.INGRESADO,
        )
        db.add(nuevo)
        db.commit()
        print(f"[*] Auditoría: orden {accession_number} registrada (INGRESADO)")
        return nuevo
    except Exception as e:
        db.rollback()
        print(f"[!] Error al registrar ingreso: {e}")
        raise e
    finally:
        db.close()


def existe_accession(accession_number: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.accession_number == accession_number
        ).first() is not None
    finally:
        db.close()


TIPOS_MENSAJE = ("adt", "orm")


def estado_orden(envios: dict) -> EstadoMensaje:
    """Estado de la orden derivado del estado de cada mensaje (ADT y ORM por separado).

    COMPLETADO: ambos aceptados. ERROR_PERMANENTE: algun mensaje agoto sus reintentos
    (requiere Reprocesar). ERROR_EMISION: algun mensaje fallo y tiene un reintento
    automatico en cola. TRANSFORMADO: en curso, sin errores.
    """
    envios = envios or {}
    por_tipo = [envios.get(t) or {} for t in TIPOS_MENSAJE]
    if all(e.get("ok") for e in por_tipo):
        return EstadoMensaje.COMPLETADO
    if any(e.get("estado") == "ERROR_PERMANENTE" for e in por_tipo):
        return EstadoMensaje.ERROR_PERMANENTE
    if any(e.get("ultimo_error") for e in por_tipo):
        return EstadoMensaje.ERROR_EMISION
    return EstadoMensaje.TRANSFORMADO


def estado_mensaje(envio) -> str:
    """ENVIADO | PENDIENTE | ERROR_PERMANENTE | None (aun sin generar)."""
    if not envio:
        return None
    if envio.get("ok"):
        return "ENVIADO"
    return envio.get("estado") or "PENDIENTE"


def resumen_envios(payload_hl7) -> dict:
    envios = (payload_hl7 or {}).get("envios") or {}
    return {t: estado_mensaje(envios.get(t)) for t in TIPOS_MENSAJE}


def actualizar_envio(correlation_id, tipo: str, envio: dict = None, mensaje: str = None,
                     borrar_mensaje: bool = False):
    """Actualiza UN mensaje (adt|orm) de la orden sin pisar al otro.

    Bloquea la fila (SELECT ... FOR UPDATE): ADT y ORM se envian en tareas
    paralelas y cada una modifica el mismo JSON. Recalcula el estado de la orden,
    el contador de reintentos y el detalle de error a partir de ambos mensajes.
    `envio` se mezcla con el registro actual del mensaje; `mensaje` es el HL7 generado.
    `borrar_mensaje` descarta el HL7 guardado (el siguiente intento lo regenera con un MSH-10 nuevo).
    """
    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).with_for_update().first()
        if registro is None:
            return None
        payload = dict(registro.payload_hl7 or {})
        envios = dict(payload.get("envios") or {})
        if borrar_mensaje:
            payload.pop(tipo, None)
        if mensaje is not None:
            payload[tipo] = mensaje
        if envio is not None:
            actual = dict(envios.get(tipo) or {})
            actual.update(envio)
            actual["actualizado"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            envios[tipo] = actual
        payload["envios"] = envios
        registro.payload_hl7 = payload
        flag_modified(registro, "payload_hl7")

        registro.estado = estado_orden(envios)
        registro.reintentos = sum(int((envios.get(t) or {}).get("intentos_fallidos", 0))
                                  for t in TIPOS_MENSAJE)
        errores = {t.upper(): (envios.get(t) or {}).get("ultimo_error")
                   for t in TIPOS_MENSAJE if (envios.get(t) or {}).get("ultimo_error")}
        if errores:
            registro.detalles_error = {
                "mensaje": " | ".join("%s: %s" % (k, v) for k, v in errores.items()),
                "cuando": max((envios.get(t.lower()) or {}).get("ultimo_intento") or ""
                              for t in errores),
                "pendientes": list(errores),
            }
        else:
            registro.detalles_error = None
        db.commit()
        print(f"[*] Auditoría: {correlation_id} {tipo.upper()} -> {estado_mensaje(envios.get(tipo))}"
              f" | orden {registro.estado.name}")
        return registro.estado
    except Exception as e:
        db.rollback()
        print(f"[!] Error al actualizar envio {tipo}: {e}")
        raise
    finally:
        db.close()


def obtener_payload_dicom(correlation_id):
    """Datos DICOM de la orden tal como estan guardados HOY (incluye correcciones manuales)."""
    db = SessionLocal()
    try:
        r = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id).first()
        return dict(r.payload_dicom_raw) if r and r.payload_dicom_raw else None
    finally:
        db.close()


def datos_paciente(payload: dict) -> dict:
    """Datos del paciente tal como se enviarian, y los motivos por los que no se podrian enviar."""
    payload = payload or {}
    apellido, nombres = separar_nombre(payload.get(vp.TAG_NOMBRE))
    return {
        "documento": str(payload.get(vp.TAG_ID, "") or ""),
        "apellido": apellido,
        "nombres": nombres,
        "fecha_nacimiento": str(payload.get(vp.TAG_NACIMIENTO, "") or ""),
        "sexo": str(payload.get(vp.TAG_SEXO, "") or ""),
        "problemas": vp.problemas(payload),
        "correcciones": list(payload.get("_correcciones") or []),
    }


def corregir_paciente(correlation_id, cambios: dict, usuario: str = ""):
    """Corrige a mano apellido, nombres, fecha de nacimiento y/o sexo de una orden.

    Quedan registrados en payload_dicom_raw["_correcciones"] (quien, cuando, antes y despues).
    No cambia el documento (es la clave del paciente en el RIS). Lanza ValueError si un dato
    no es valido; devuelve None si la orden no existe.
    """
    cambios = {k: v for k, v in (cambios or {}).items() if v is not None}
    if "apellido" in cambios or "nombres" in cambios:
        for k in ("apellido", "nombres"):
            if k in cambios:
                cambios[k] = " ".join(str(cambios[k]).split())
    if "apellido" in cambios and not cambios["apellido"]:
        raise ValueError("El apellido no puede quedar vacio.")
    if "nombres" in cambios and not cambios["nombres"]:
        raise ValueError("El nombre de pila no puede quedar vacio.")
    if "fecha_nacimiento" in cambios:
        cambios["fecha_nacimiento"] = str(cambios["fecha_nacimiento"]).strip().replace("-", "")
        if not vp._fecha_valida(cambios["fecha_nacimiento"]):
            raise ValueError("Fecha de nacimiento invalida (use AAAAMMDD, no futura).")
    if "sexo" in cambios:
        cambios["sexo"] = str(cambios["sexo"]).strip().upper()
        if cambios["sexo"] not in vp.SEXOS_VALIDOS:
            raise ValueError("Sexo invalido (F, M, O o U).")

    db = SessionLocal()
    try:
        r = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).with_for_update().first()
        if r is None or not r.payload_dicom_raw:
            return None
        payload = dict(r.payload_dicom_raw)
        antes, despues = {}, {}

        def poner(tag, valor):
            if str(payload.get(tag, "") or "") != valor:
                antes[tag], despues[tag] = payload.get(tag, ""), valor
                payload[tag] = valor

        if "apellido" in cambios or "nombres" in cambios:
            actual = separar_nombre(payload.get(vp.TAG_NOMBRE))
            ap, no = cambios.get("apellido", actual[0]), cambios.get("nombres", actual[1])
            if (ap, no) != actual:  # solo si cambia de verdad (no por pasar de "A B" a "A^B")
                poner(vp.TAG_NOMBRE, "%s^%s" % (ap, no) if no else ap)
        if "fecha_nacimiento" in cambios:
            poner(vp.TAG_NACIMIENTO, cambios["fecha_nacimiento"])
        if "sexo" in cambios:
            poner(vp.TAG_SEXO, cambios["sexo"])

        if despues:
            payload["_correcciones"] = list(payload.get("_correcciones") or []) + [{
                "cuando": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "usuario": usuario, "antes": antes, "despues": despues,
            }]
            r.payload_dicom_raw = payload
            flag_modified(r, "payload_dicom_raw")
            db.commit()
            print(f"[*] Auditoría: datos del paciente corregidos en {correlation_id} por {usuario}: {list(despues)}")
        return datos_paciente(payload)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


MINUTOS_ATASCADO = 10  # un envio "pendiente" sin actividad por mas tiempo se considera perdido


def _en_curso(envio: dict) -> bool:
    """True si el mensaje se esta enviando o reintentando ahora (hay una tarea viva)."""
    if not envio or envio.get("ok") or envio.get("estado") != "PENDIENTE":
        return False
    try:
        ultima = datetime.datetime.strptime(envio.get("actualizado", ""), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True  # sin marca de tiempo (registro anterior): no se asume atascado
    return (datetime.datetime.now() - ultima) < datetime.timedelta(minutes=MINUTOS_ATASCADO)


def reenviar(correlation_id: str, tipo: str = None) -> list:
    """Reenvia ADT y/o ORM de una orden aunque ya hayan sido aceptados.

    A diferencia de reprocesar (solo mensajes en ERROR_PERMANENTE), sirve para
    retransmitir a proposito, p. ej. tras corregir la configuracion o el destino.
    Se regenera con la configuracion vigente y un MSH-10 NUEVO (es una transmision
    nueva, no un reintento, asi que no debe tomarse por duplicado). Se conserva el
    registro de la aceptacion anterior en envios[tipo].anterior. Un mensaje que
    esta enviandose o reintentando se omite (duplicaria el envio), salvo que lleve
    mas de MINUTOS_ATASCADO sin actividad (tarea perdida, p. ej. por un reinicio).
    Devuelve la lista de tipos re-encolados.
    """
    from core.broker import tarea_enviar_mensaje  # evita el import circular

    tipos = [tipo.lower()] if tipo else list(TIPOS_MENSAJE)
    if any(t not in TIPOS_MENSAJE for t in tipos):
        return []

    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        if registro is None or not registro.payload_dicom_raw:
            return []
        payload = registro.payload_dicom_raw
        envios = (registro.payload_hl7 or {}).get("envios") or {}
        cid = registro.correlation_id
        elegibles = [t for t in tipos if not _en_curso(envios.get(t))]
    except Exception as e:
        db.rollback()
        print(f"[!] Error al preparar reenvio: {e}")
        return []
    finally:
        db.close()

    for t in elegibles:
        e = envios.get(t) or {}
        anterior = ({k: e.get(k) for k in ("destino", "cuando", "ack")} if e.get("ok") else e.get("anterior"))
        actualizar_envio(cid, t, {
            "ok": False, "estado": "PENDIENTE", "ultimo_error": None,
            "reenvios": int(e.get("reenvios", 0)) + 1, "anterior": anterior,
        }, borrar_mensaje=True)
        print(f"[*] Auditoría: reenviando {correlation_id} ({t.upper()})")
    for t in elegibles:
        tarea_enviar_mensaje(cid, payload, t)
    return elegibles


def reprocesar(correlation_id: str, tipo: str = None) -> list:
    """Re-encola los mensajes (ADT/ORM) que agotaron sus reintentos, sin tocar el otro.

    Un mensaje es reprocesable solo si esta en ERROR_PERMANENTE (si tiene un
    reintento automatico en cola, reprocesar duplicaria el envio). Se reutiliza
    payload_dicom_raw y el mismo correlation_id. El HL7 se regenera con la
    configuracion vigente. `tipo` ('adt' | 'orm') limita a un solo mensaje.
    Devuelve la lista de tipos re-encolados (vacia si no habia nada reprocesable).
    """
    # Import local para evitar import circular (broker -> auditoria -> broker)
    from core.broker import tarea_enviar_mensaje

    tipos = [tipo.lower()] if tipo else list(TIPOS_MENSAJE)
    if any(t not in TIPOS_MENSAJE for t in tipos):
        return []

    db = SessionLocal()
    try:
        registro = db.query(RegistroTrazabilidad).filter(
            RegistroTrazabilidad.correlation_id == correlation_id
        ).first()
        if registro is None or not registro.payload_dicom_raw:
            return []
        payload = registro.payload_dicom_raw
        envios = (registro.payload_hl7 or {}).get("envios") or {}
        legacy_fallido = registro.estado == EstadoMensaje.ERROR_PERMANENTE
        elegibles = []
        for t in tipos:
            e = envios.get(t) or {}
            if e.get("ok"):
                continue
            # Registros anteriores al desacople no tienen "estado" por mensaje.
            if e.get("estado") == "ERROR_PERMANENTE" or (not e.get("estado") and legacy_fallido):
                elegibles.append(t)
        cid = registro.correlation_id
    except Exception as e:
        db.rollback()
        print(f"[!] Error al preparar reproceso: {e}")
        return []
    finally:
        db.close()

    for t in elegibles:
        actualizar_envio(cid, t, {"estado": "PENDIENTE", "ultimo_error": None})
        print(f"[*] Auditoría: reprocesando {correlation_id} ({t.upper()})")
    # Re-despacho fuera de la sesion de DB
    for t in elegibles:
        tarea_enviar_mensaje(cid, payload, t)
    return elegibles
