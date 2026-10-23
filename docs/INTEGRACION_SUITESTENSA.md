# Integración con SUITESTENSA — guía de configuración y bitácora

> Estado al **2026-10-23**. Este documento recoge lo que se construyó, lo que se configuró, lo que se
> descubrió del sistema destino y lo que queda pendiente. Complementa a `DOCUMENTACION_TECNICA.md`
> (arquitectura general). No contiene datos de pacientes: los ejemplos son ficticios.
>
> **Marca de confianza.** Cada afirmación sobre el RIS o Mirth está marcada:
> ✅ verificado con una respuesta real del sistema · 🔶 inferido (hipótesis razonable, no confirmada) ·
> ❓ desconocido.

---

## 1. Resumen ejecutivo

| Mensaje | Estado |
|---|---|
| **ADT^A04** (alta/admisión del paciente) | ✅ Funciona de punta a punta: el RIS crea el paciente (`Resultado: Yes`). |
| **ORM^O01** (orden del estudio) | ✅ **Funciona** (2026-10-23): las órdenes aparecen en la pantalla *Ejecución* de SUITESTENSA con su estudio, hora y equipo (p. ej. `TC de abdomen y pelvis` → `TOMOGRAFIA`; `radiografía simple de mano` → `RX FIJO TECNO`). Hizo falta corregir 314 códigos de examen en colisión (11.0), mapear el equipo y la unidad de negocio (10.2) y configurar en el RIS las relaciones de la unidad de negocio (8.2). |

Lo pendiente principal ya no es el flujo básico sino la **robustez**: codificación de caracteres (sección 12), órdenes con varios estudios (11.4 y 18), identidad del paciente (`PK`) y los flujos RIS → HIS (sección 16).

Cadena completa:

```
Worklist DICOM (C-FIND, cada 30 s)
        │  172.31.3.149:8000  AET CLLSPS / local MOTOR_WKL
        ▼
   Motor (ingesta) ──► registro_trazabilidad (PostgreSQL)
        │
        ├─► tarea ADT ──┐   reintentos y estado propios por mensaje
        └─► tarea ORM ──┤
                         ▼
                 MLLP/TCP ──► Mirth 172.31.3.150:5556 ──► HTTP (I.REST) ──► RIS SUITESTENSA
```

---

## 2. Ramas y despliegue

| Rama | Contenido | Estado |
|---|---|---|
| `main` | Base del MVP | — |
| `build/script-windows` | `build.bat`, instalador, fixes de `bcrypt`, logs, parada de servicios | **Sin PR abierto** |
| `feat/adt-mirth` | Todo lo anterior + integración HL7 con SUITESTENSA, estudios, desacople ADT/ORM | **Sin PR abierto** (parte de la anterior) |

Se debe integrar `feat/adt-mirth` en `main` cuando se dé por estable. Compilar y desplegar:

```
git checkout feat/adt-mirth && git pull
build.bat 1.0.1            # compila frontend + backend + instalador
build.bat 1.0.1 /nofront   # reutiliza static\ (solo si NO cambió el frontend)
```

Compilar **sin** `/nofront` siempre que haya cambios en `frontend-motor/`. `static\` ya **no está versionado** (lo genera el build): si `git pull` protesta por archivos modificados en `static\`, ejecutar `git checkout -- static` antes.

---

## 3. Entorno de ejecución (Windows)

### 3.1 Construcción del instalador (`build.bat`)

`build.bat [version] [/deps] [/nofront] [/noinstaller]` ejecuta 5 pasos y deja el detalle en `build.log`:
requisitos → frontend (`npm`) → PyInstaller (`MotorDICOM.spec`) → verificación del bundle (arranca el exe, código 2 esperado) →
Inno Setup (`dist_installer\MotorDICOM-Setup-<version>.exe`).

Requisitos de la PC de compilación:

- Python con las dependencias (`build.bat /deps` las instala), Node/npm, **Inno Setup 6**
  (se detecta en `PATH`, `Program Files` o `%LOCALAPPDATA%\Programs\Inno Setup 6` si se instaló por usuario).
- Carpeta **`vendor\`** (no versionada, está en `.gitignore`; repetirla en cada PC de compilación):
  - `vendor\pgsql\` (PostgreSQL portable x64; `bin\initdb.exe`, `pg_ctl.exe`, `psql.exe`)
  - `vendor\nssm.exe` (64 bits)
  - `vendor\vc_redist.x64.exe`

### 3.2 Instalación

- Instalar como **administrador**. Instala en `C:\Program Files\MotorDICOM` y registra los servicios
  `MotorDICOM API`, `MotorDICOM Worker`, `MotorDICOM Ingesta` y `MotorDICOM Postgres` (NSSM).
- El instalador **detiene los servicios** antes de copiar archivos (sin esto: `DeleteFile falló; código 5`).
- Datos en `C:\ProgramData\MotorDICOM\` (sobreviven a reinstalaciones y desinstalaciones):

| Ruta | Contenido |
|---|---|
| `.env` | Configuración (credenciales de BD, `JWT_SECRET`, puertos) |
| `.superpw` | Contraseña del superusuario de PostgreSQL |
| `pgdata\` | Base de datos (PostgreSQL, puerto **5433**) |
| `logs\` | `api.log`, `worker.log`, `ingesta.log` (NSSM) y `motordicom-<proceso>.log` (aplicación) |
| `motor_queue.db` | Cola de tareas (Huey/SQLite) |

- Puertos: consola web **8000**; DICOM **4242** (regla de firewall); PostgreSQL **5433**.
- Primer acceso: `admin` / `admin123`, con **cambio de contraseña obligatorio**.

### 3.3 Reinicio de servicios

La configuración funcional (valores fijos, mapeos, equivalencias de estudio, canales) se lee de la base en cada
intento: **no requiere reinicio**. Solo hace falta si cambia `.env` o se instala una versión nueva:

```
net stop "MotorDICOM Ingesta" & net stop "MotorDICOM Worker" & net stop "MotorDICOM API"
net start "MotorDICOM API" & net start "MotorDICOM Worker" & net start "MotorDICOM Ingesta"
```

Las tareas en reintento quedan en la cola y se retoman. Al actualizar desde una versión anterior al desacople
ADT/ORM, conviene hacerlo con la cola vacía (las tareas con el formato anterior se pierden).

### 3.4 Variables de entorno (`.env`)

| Variable | Defecto | Uso |
|---|---|---|
| `HL7_SENDING_APP` / `HL7_SENDING_FACILITY` | `SISGH` / `ARP03` | `MSH-3` / `MSH-4` (también editables en Valores fijos) |
| `MLLP_REINTENTOS` / `MLLP_RETRY_DELAY` | `3` / `30` s | Reintentos automáticos por mensaje |
| `INGESTA_INTERVALO_SEG` | `30` | Frecuencia de consulta al worklist |
| `MOTORDICOM_LOG_DICOM` | (no definida) | `1` reactiva el log detallado de `pynetdicom` (**contiene datos de pacientes**) |
| `MOTORDICOM_DATA` | `C:\ProgramData\MotorDICOM` | Raíz de datos |
| `ADMIN_USER` / `ADMIN_PASS` | `admin` / `admin123` | Solo para el sembrado inicial |

---

## 4. Canales (pantalla *Canales*)

| Canal | Valor | Notas |
|---|---|---|
| Origen: Worklist DICOM (C-FIND) | `172.31.3.149`, puerto `8000`, AET destino `CLLSPS`, AET propio `MOTOR_WKL` | ✅ responde |
| Destino MLLP: ADT (`destino_adt`) | `172.31.3.150`, puerto `5556` | ✅ |
| Destino MLLP: ORM (`destino_orm`) | ❓ confirmar | Los errores `I.REST` del ORM provienen del mismo RIS; verificar el canal |

El botón *Probar* de un canal MLLP solo verifica que el puerto acepte la conexión TCP, no envía ningún mensaje.

---

## 5. Origen: qué entrega el worklist

Consulta realizada con `tools/consultar_worklist.py` (C-FIND ampliado):

```
python tools\consultar_worklist.py 172.31.3.149 8000 CLLSPS MOTOR_WKL [--fecha AAAAMMDD] [--max N] [--mostrar-paciente]
```

Por defecto **oculta los datos del paciente**. ✅ Hallazgos:

- **No entrega ningún código de procedimiento**: las secuencias de código no se devuelven. Solo hay **texto**
  (`RequestedProcedureDescription`).
- `RequestedProcedureID` y `ScheduledProcedureStepID` valen lo mismo que el **número de accesión**: no identifican el tipo de estudio.
- `AdmissionID` (nº de visita) llega **vacío**.
- El `StudyInstanceUID` termina con el **número del paciente**: no compartir esa salida sin borrarlo.
- La descripción llega **cortada a 64 caracteres** (límite del VR `LO` de DICOM) y, en muchas órdenes, concatena
  **varios estudios** separados por coma (ver sección 11.4).
- La modalidad DICOM es poco fiable (un mismo estudio llega como `CR`, `DX` y `CT`).

Tags que captura el motor (todos mapeables y usables como `{tag}`):

| Tag | Nombre | Tag | Nombre |
|---|---|---|---|
| `00100020` | Patient ID | `00400002` | Scheduled Procedure Step Start Date |
| `00100010` | Patient's Name | `00400003` | …Start Time |
| `00100030` | Birth Date | `00400009` | Scheduled Procedure Step ID |
| `00100040` | Sex | `00400007` | Scheduled Procedure Step Description |
| `00080050` | Accession Number | `00400001` | Scheduled Station AE Title |
| `00321060` | Requested Procedure Description | `00401001` | Requested Procedure ID |
| `00080090` | Referring Physician | `00321064` | Requested Procedure Code Value |
| `00080060` | Modality | | |

---

## 6. Cómo se arma un mensaje (pantalla *Mapeo*)

Cada mensaje (ADT u ORM) tiene **su propia pestaña**. Se construye así, en este orden:

1. **Valores fijos del serializador** (`serializador_hl7.py`): `MSH` automático (`MSH-9` tipo, `MSH-10` id único, `MSH-7` fecha/hora), `PID-1`, `PV1-1`, etc.
2. **Mapeo DICOM → HL7** (los destinos que se asignan a cada tag). El valor DICOM se escapa (`| ~ \ &`).
3. **Valores fijos del usuario** (*Opciones avanzadas*): **sobrescriben** lo anterior.

### 6.1 Sintaxis de los valores fijos

Un valor fijo es **HL7 literal**: `^` `~` `&` se respetan tal cual (permite repeticiones y componentes).

| Marcador | Inserta |
|---|---|
| `{00100020}` | Valor del tag DICOM (escapado) |
| `{00100010:apellido}` / `{00100010:nombres}` | Parte del nombre: con `^` usa el formato DICOM (`APELLIDO^NOMBRE`); sin `^`, **primera palabra = apellido**, resto = nombres |
| `{ahora}` | Fecha/hora del mensaje (`AAAAMMDDhhmmss`, la misma de `MSH-7`) |
| `{codigo_estudio}` / `{descripcion_estudio}` | Equivalencia del estudio (pantalla *Estudios*); si falta, **el mensaje no se emite** (sección 9) |
| `{codigo_equipo}` / `{descripcion_equipo}` / `{unidad_negocio}` | Equipo genérico de la **modalidad del RIS** del estudio (sección 10.2); si la modalidad no tiene equipo, **el mensaje no se emite** |

**Componentes:** `SEG-N.M` escribe solo el componente M del campo N, sobre lo que ya tenga (p. ej. `PID-3.4`).
Se aplican **después** de los campos completos.

**Limitaciones conocidas:**
- Un valor fijo **no puede vaciar** un campo mapeado desde DICOM (los valores vacíos se ignoran). Para dejarlo vacío hay
  que quitar el destino en la pestaña de mapeos.
- Los marcadores son `{tag de 8 hex}`, `{tag:apellido|nombres}`, `{ahora}`, `{codigo_estudio}`, `{descripcion_estudio}`, `{codigo_equipo}`, `{descripcion_equipo}`, `{unidad_negocio}`. Cualquier otro nombre da error.
- El tipo/longitud de los campos **no se valida**: lo que se escribe va tal cual.
- Un apellido compuesto (`DE LA CRUZ JUAN`) se separaría mal con la regla de la primera palabra.

El catálogo de campos fijables (`core/catalogos.py`) cubre `MSH`, `EVN`, `PID`, `PV1`, `ORC`, `OBR`.

---

## 7. Configuración del mensaje ADT (✅ funcionando)

**Valores fijos (pestaña ADT):**

| Campo | Valor |
|---|---|
| `MSH-3` / `MSH-4` | `SISGH` / `ARP03` (por defecto en el código) |
| `MSH-5` / `MSH-6` | `ESTENSARADIO` / `SUITESTENSA` |
| `MSH-18` | `UTF-8` |
| `PV1-2` | `O` |
| `PID-3` | `{00100020}^^^PK~{00100020}^DU^^CF` |
| `PID-5` | `{00100010:apellido}^^{00100010:nombres}^` |

Mapeo por defecto: `PID-7` ← fecha de nacimiento, `PID-8` ← sexo, `PV1-7` ← médico derivante, `PV1-10` ← modalidad.

**Ejemplo** (datos ficticios):

```
MSH|^~\&|SISGH|ARP03|ESTENSARADIO|SUITESTENSA|20261023120000||ADT^A04|AB12CD34EF|P|2.5||||||UTF-8
EVN|A04|20261023120000
PID|1||12345678^^^PK~12345678^DU^^CF||GARCIA^^MARIA ELENA^||19800101|F
PV1|1|O|...
```

### 7.1 Lo aprendido del RIS con el ADT

| Hecho | Detalle |
|---|---|
| ✅ Referencia aceptada por el RIS | `MSH-5/6` = `ESTENSARADIO` / `SUITESTENSA`; `MSH-18` = `UTF-8`; `PV1-2` = `O`; `PID-3` con **dos repeticiones** (`id^^^PK` y `doc^DU^^CF`); `PID-5` con el apellido en el componente 1 y **todos los nombres en el componente 3** (el 2 vacío) |
| ✅ `PK` | El número de paciente del worklist (8 dígitos) sirve como clave `PK`: los pacientes aparecen en el RIS con `ID paciente` = `Otro Id` y fuente `PK` |
| ✅ Filtro de Mirth | Un ADT con el receptor invertido (`SUITESTENSA\|ESTENSARADIO`) quedaba `FILTERED`. El canal toma el origen (`SOURCE`) de `MSH-4` |
| ✅ Nombre | `Missing Patient Given Name` aparece si el nombre no se separa en componentes (`PID-5`) |
| ✅ Clave externa | `Missing Patient Key External` aparece si `PID-3` no lleva la repetición con autoridad `PK` |

---

## 8. Configuración del mensaje ORM (✅ funcionando)

**Valores fijos (pestaña ORM):**

| Campo | Valor | Para qué |
|---|---|---|
| `MSH-5` / `MSH-6` / `MSH-18` | `ESTENSARADIO` / `SUITESTENSA` / `UTF-8` | Receptor y codificación |
| `PID-3` | `{00100020}^^^PK~{00100020}^DU^^CF` | Igual que el ADT |
| `PID-5` | `{00100010:apellido}^^{00100010:nombres}^` | Igual que el ADT. **No copiar la plantilla de `PID-3` aquí** (error ya ocurrido, ver 10) |
| `PV1-2` | `O` (por defecto) | Clase de paciente |
| `PV1-3` | `INT` | **Ubicación de origen del paciente** (no es el equipo; ver sección 17) |
| `ORC-1` | `SN` | Control de orden |
| `ORC-2` | `{00080050}^SISGH` | Nº de orden + entidad que lo genera (la especificación usa `SISGH`) |
| `ORC-4` | `{00080050}^SISGH` | `PlacerGroupNumber` + `PlacerGroupNumberIssuer` (mismo valor que `ORC-2`) |
| `ORC-7` | `1^^^{cita}^^1` | `ORC-7.4` = fecha/hora de la cita (`Exam Date`) |
| `ORC-9` | `{ahora}` | Fecha/hora de la transacción (`Exam Date`, probable) |
| `ORC-12` | `^SIN DERIVADOR` | Médico solicitante (copiado del ejemplo) |
| `ORC-17` | `INT^integracion` | **Procedencia** (el componente 1 es el código) |
| `OBR-2` | `{00080050}^SISGH` | Nº de orden (placer), igual a `ORC-2` |
| `OBR-4` | `{codigo_estudio}^{descripcion_estudio}` | **Código de examen** |
| `OBR-18` | `{unidad_negocio}` | **`BusinessUnit`**: centro de costo / unidad que realiza el estudio (sección 10.2) |
| `OBR-21` | `{codigo_equipo}` | **`IdEquipment`**: recurso/equipo donde se realiza (sección 10.2) |
| `OBR-27` | `1^^^{cita}^^1` | `OBR-27.4` = fecha/hora de la cita (según la especificación; el ejemplo del RIS la ponía en `OBR-25`) |

Recomendado en la pestaña de **mapeos** del ORM: quitar el destino `OBR-3` (la especificación lo deja vacío) y `OBR-24`. `OBR-27` está mapeado por defecto con solo la fecha DICOM, pero el valor fijo de arriba lo **sobrescribe**. No usar `OBR-7` ni `OBR-25` (si quedaron cargados en un valor fijo, vaciarlos).
`PV1-19` (nº de visita) se deja **vacío** por decisión (no es obligatorio).

**Ejemplo del ORM de referencia del RIS** (datos ficticios, estructura real):

```
MSH|^~\&|HIS|HIS|ESTENSARADIO|SUITESTENSA|20260611103059||ORM^O01|MSG-UUID-683700|P|2.5||||||UTF-8
PID|1||41392^^^PK~59919175^DU^^CF||APELLIDO^^NOMBRES^||20230716|M
PV1|1|O|02020501^^^^^^^ECOGRAFO ESAOTE TWINCE||||||||||||||||61908063^^^^^^^^
ORC|SN|683700^HIS||683700^HIS|||1^^^20260611103059^^1||20260611103059|||^SIN DERIVADOR|||||02020501^O
OBR|1|683700^HIS||11461^GUARDIA ODONTOLOGICA|||||||||||||||||||||1^^^20260611103059^^1
```

### 8.1 Errores del RIS en el ORM y su causa

El RIS responde por HTTP (`HTTP/1.1 531 ...`), que Mirth devuelve como `ACK AE`. Cada error nombra la propiedad que falta.

| Error del RIS | Campo que lo alimenta | Estado |
|---|---|---|
| `PlacerGroupNumber NULL or Empty` / `PlacerGroupNumberIssuer NULL or Empty` | `ORC-4` (número y autoridad) | ✅ se resuelve con `ORC-4` = `{00080050}^HIS` |
| `Exam Date NULL` | 🔶 `ORC-7` y/o `ORC-9` (no se resolvía con solo `OBR-7`/`OBR-25`) | Resuelto al cargar `ORC-7`/`ORC-9` (se deduce del último error) |
| `Provenance NULL` → `Provenance Code 1 not encoded` | ✅ **`ORC-17` componente 1** (cambió al poner `1^INT`) | Resuelto con `ORC-17` = `INT^integracion` |
| `Exam Code <texto> not encoded` | `OBR-4` componente 1 | El texto se enviaba como código → resuelto con equivalencias |
| `Exam Code 1 not encoded` | `OBR-4` componente 1 | ✅ Causa: colisión de códigos (sección 11.0) |
| `Mandatory data ... IdEquipment and BusinessUnit are null` | ✅ `OBR-21` (equipo) y `OBR-18` (unidad de negocio), según la especificación | Resuelto con equipo por modalidad (10.2) |
| `EquipmentMandatory is true but IdEquipment is null` | `OBR-21` **vacío** en el mensaje (no estaba cargado el valor fijo) | Cargar `OBR-21` = `{codigo_equipo}`; el código debe coincidir con el `ExternalCode` del equipo en el RIS |
| `Configuration error in DB: LsBusinessUnitEquipment - LsBusinessUnitModality - LsBusinessUnitProvenance ... is empty` | Configuración del **RIS** (no del mensaje) | Ver 8.2 |

### 8.2 Configuración necesaria en el RIS (la hace su administrador)

Para que una orden se acepte, el RIS necesita estos datos de maestros; sin ellos rechaza el ORM aunque el mensaje sea correcto:

| Dato | Cómo lo reconoce el RIS | Observaciones |
|---|---|---|
| **Examen** | `ExternalCode` del examen = código enviado en `OBR-4.1` | Un código que exista pero con `ExternalCode` distinto (p. ej. `0`) da `Exam Code ... not encoded` |
| **Equipo** | `ExternalCode` del equipo = `OBR-21` | De 13 equipos, solo 4 tenían `ExternalCode`: `RX001`, `RMN001`, `ECOXERT`, `ECOOOOO2`. Hay que asignarlo a los que se vayan a usar |
| **Unidad de negocio** | Código enviado en `OBR-18` (p. ej. `CD1`) | |
| **Procedencia** | Código enviado en `ORC-17.1` (p. ej. `INT`) | Se creó una procedencia genérica de integración |
| **Relaciones de la unidad de negocio** | Tablas `LsBusinessUnitEquipment`, `LsBusinessUnitModality`, `LsBusinessUnitProvenance` | La unidad debe estar vinculada a **cada equipo, modalidad y procedencia** que se use; si falta alguna: `Configuration error in DB ... is empty` |

Por cada modalidad nueva que se integre hay que repetir: equipo con `ExternalCode`, vínculo con la unidad de negocio y con la modalidad,
y cargar el código en *Estudios → Equipo por modalidad*. Equipos vistos en el RIS: `RX FIJO TECNO`, `RX RODANTE TECNO`, `CR TECNO`,
`SERIOGRAFO DE TECNO` (DX\RF), `TOMOGRAFIA`, `MAMOGRAFO`, `MR`, `ECO MINDRAY`, `ECO2`, `US-TEST`, `Telecomandato XYZ`; **no hay equipo de densitometría ni de medicina nuclear**.

---

## 9. Envío, reintentos y estados (desacople ADT/ORM)

Cada mensaje tiene su **propia tarea, sus propios reintentos y su propio estado**; que uno falle no afecta al otro.

**Estado de un mensaje** (`payload_hl7.envios.<adt|orm>`): `PENDIENTE` (reintentando) · `ENVIADO` · `ERROR_PERMANENTE`.

**Estado de la orden** (derivado de los dos):

| Condición | Estado |
|---|---|
| ADT **y** ORM aceptados | `COMPLETADO` |
| Algún mensaje sin reintentos restantes | `ERROR_PERMANENTE` (requiere *Reprocesar*) |
| Algún mensaje fallando pero con reintento en cola | `ERROR_EMISION` |
| En curso, sin errores | `TRANSFORMADO` |

- Reintentos: `MLLP_REINTENTOS` (3) cada `MLLP_RETRY_DELAY` (30 s) por mensaje.
- **Cada intento regenera el HL7** con la configuración vigente (mapeo, valores fijos, equivalencias) y conserva el `MSH-10`
  original para que el destino detecte duplicados. Lo ya aceptado **no se reenvía**.
- **Reprocesar** (por orden, o ADT / ORM por separado desde la auditoría) solo re-encola los mensajes en `ERROR_PERMANENTE`.
  Con reintento automático pendiente o mensaje ya aceptado responde 409.
- **Decisión vigente:** ambos mensajes salen sin esperarse (el ADT se encola primero). Si el RIS exigiera el paciente
  antes que la orden, un ORM tras un ADT fallido será rechazado; alternativa: retener el ORM hasta que el ADT sea aceptado.
- **Reenviar** (cualquier orden, aunque esté `COMPLETADO`): botón en cada fila del Monitor (ambos mensajes) y en la auditoría (por mensaje o la orden
  completa). Pide confirmación si el destino ya aceptó el mensaje. Regenera con la configuración vigente y un **`MSH-10` nuevo** (es una transmisión
  nueva, no un reintento) y guarda la aceptación anterior en `envios.<tipo>.anterior` y el nº de reenvíos en `reenvios`. API:
  `POST /api/v1/trazabilidad/{id}/reenviar[?tipo=adt|orm]`. Un mensaje que se está enviando o reintentando se omite (409); se considera atascado
  (y se puede reenviar) si lleva más de 10 minutos sin actividad (`MINUTOS_ATASCADO`).
  **Cuidado:** reenviar un ADT/ORM ya aceptado puede duplicar o modificar datos en el RIS; el comportamiento del RIS ante un ORM repetido (mismo `ORC-2`) no está verificado.
- Interfaz: el Monitor muestra por orden `ADT ✓ / ORM ✕`. La **auditoría** es una ventana ancha de dos columnas que cabe en una sola pantalla
  (estado, estado por mensaje y error a la izquierda; ADT y ORM con un segmento por línea a la derecha); se refresca sola mientras haya un mensaje en curso.

### 9.1 Datos mínimos del paciente (validación y corrección)

Antes de generar **cualquier** ADT u ORM se valida el paciente (`core/validacion_paciente.py`). Se retiene la orden con un motivo claro si:
falta el documento, el apellido o el nombre de pila (o alguno es solo un número), la fecha de nacimiento falta, es inválida o futura, o el sexo
falta o no es `F`/`M`/`O`/`U`. Los datos no cambian al reintentar, así que el mensaje pasa **directo a `ERROR_PERMANENTE`** (sin gastar reintentos).
Se desactiva con `MOTORDICOM_VALIDAR_PACIENTE=0`.

- **Corrección:** *Auditoría → Datos del paciente → Corregir* (apellido, nombres, nacimiento `DD/MM/AAAA` y sexo), con **Guardar** o **Guardar y reenviar**.
  Se guarda en `payload_dicom_raw` y queda registro en `payload_dicom_raw._correcciones` (usuario, fecha, antes y después). No se edita el documento (es la clave del paciente).
  API: `PUT /api/v1/trazabilidad/{id}/paciente`. Cada envío lee el paciente **de la base** en ese momento, así una corrección vale aunque la tarea ya estuviera encolada.
- El sexo DICOM `O` se envía como `U` (el RIS acepta `F`, `M`, `U`).

---

## 10. Estudios (equivalencia texto → código) — pantalla *Estudios*

Como el worklist no trae código, el motor traduce el **texto** del estudio al **código del RIS** con una tabla propia.

- **Clave:** el texto normalizado (sin tildes, minúsculas, espacios colapsados). Un texto = un código (la modalidad no forma parte de la clave).
- **Sin equivalencia:** el **ORM se retiene** (`Estudio sin codigo de equivalencia: '<texto>'`) y el **ADT sale igual**.
  Al cargar la equivalencia, los reintentos lo recogen; si ya se agotaron, usar *Reprocesar ORM*.
- La pantalla muestra **Sin código** (estudios que ya llegaron, con nº de órdenes y modalidad DICOM) y las **Equivalencias** cargadas.
- **Exportar pendientes (CSV)** → completar `codigo` (y `descripcion_destino`) → **Importar CSV**. Formato:
  `descripcion_origen;codigo;descripcion_destino;modalidad;ordenes` (`;`, UTF-8 con BOM). Solo se leen las 3 primeras columnas;
  las filas sin código se omiten (sin error); se aceptan `;`, `,` o tabulador; acepta archivos Windows-1252.
- Se usa en el ORM con `OBR-4` = `{codigo_estudio}^{descripcion_estudio}`.

### 10.1 Clasificación por modalidad del RIS

Para dar de alta los estudios en el RIS se asignó a cada uno **una sola** modalidad de las 8 del RIS
(`DENSITOMETRIA OSEA`, `ECOGRAFIA`, `MAMOGRAFIA`, `MEDICINA NUCLEAR`, `RADIOGRAFIA CONTRASTADA`, `RADIOLOGIA`,
`RESONANCIA MAGNETICA`, `TOMOGRAFIA`) con `tools/clasificar_modalidad_ris.py`:

```
python tools/clasificar_modalidad_ris.py estudios_pendientes.csv salida.csv
```

Criterio: manda el **texto**; la modalidad DICOM solo se usa si el texto no la indica. Resultado sobre los 522 estudios:
RADIOLOGIA 294 · TOMOGRAFIA 160 · RESONANCIA MAGNETICA 49 · MAMOGRAFIA 10 · RADIOGRAFIA CONTRASTADA 8 · MEDICINA NUCLEAR 1.
**12 filas quedan con `revisar = SI`** (sin modalidad en el texto, procedimientos que no son imagen —manometría, sondas,
radioterapia—, o mezcla de modalidades en un texto). Los fluoroscópicos con bario se asignaron a `RADIOGRAFIA CONTRASTADA`.
La salida conserva el texto original y los códigos (1 a 522) y agrega `modalidad_ris`, `revisar`, `observacion`.

### 10.2 Equipo por modalidad (`IdEquipment` y `BusinessUnit`)

El RIS rechazó el ORM con `Mandatory data in ... IdEquipment and BusinessUnit are null` (✅ error real). Decisión: un **equipo genérico por
modalidad**, configurable desde la pantalla *Estudios → Equipo por modalidad*.

- **Modalidad del RIS de cada estudio:** se guarda en la equivalencia (`modalidad_ris`). Si no se indicó, se **deduce del texto** del estudio
  (`core/modalidad_ris.py`; la modalidad DICOM del worklist solo se usa si el texto no la indica). En la pantalla se puede cambiar por estudio.
- **Tabla `equipos_modalidad`** (se crea y siembra sola): una fila por modalidad con `codigo_equipo`, `descripcion_equipo` y `unidad_negocio`.
  Valores por defecto: RADIOLOGIA `DX`, RADIOGRAFIA CONTRASTADA `DX`, TOMOGRAFIA `CT`, RESONANCIA MAGNETICA `MR`, MAMOGRAFIA `MG`,
  ECOGRAFIA `US`, DENSITOMETRIA OSEA `BMD`, MEDICINA NUCLEAR `NM`; descripción `EQUIPO GENERICO <código>`; unidad de negocio vacía.
  Editables y restaurables (*Restaurar por defecto*).
- **Uso (según la especificación del proveedor, sección 17):** `OBR-21` = `{codigo_equipo}` (recurso donde se realiza el estudio) y
  `OBR-18` = `{unidad_negocio}` (centro de costo / unidad que lo realiza). **No** se usa `PV1-3`, que es la ubicación de origen del paciente.
  Si se usa un marcador y la modalidad no tiene ese dato configurado, el ORM se retiene (`Sin equipo configurado ...`).
  La descripción del equipo es solo informativa: `OBR-21` y `OBR-18` llevan únicamente el código.
  **Los códigos de equipo y de unidad de negocio deben existir en el RIS** (los genéricos `DX`, `US`... hay que crearlos allí).
- **CSV:** *Exportar pendientes* trae `modalidad_ris` (la sugerida) y `modalidad_dicom`; *Importar CSV* lee `modalidad_ris` **por nombre de columna**
  (si falta, se conserva la que ya tenía el estudio). Una modalidad fuera de las 8 del RIS se rechaza con el número de fila.
- `Radiografía contrastada` usa `DX` por defecto (decisión pendiente de confirmar: el RIS podría tener un equipo de fluoroscopia).

---

## 11. Codificación del examen (causa resuelta; queda 11.4)

**Síntoma:** el motor ya envía `OBR-4` = `1^radiografía simple de tórax` (la equivalencia y la plantilla funcionan), y el RIS responde
`C02 - Exam Code 1 not encoded`: **no encuentra un examen con código `1`**.

### 11.0 Causa encontrada (catálogo del RIS, `exams.csv`, 1000 exámenes)

Al cruzar el catálogo del RIS con los 522 estudios del motor (códigos 1 a 522):

- Los 522 códigos **existen** en el RIS, pero **314 están ocupados por otros exámenes ya existentes** (RX, mamografías, densitometría...),
  que el RIS conserva con `ExternalCode = 0`. Al dar de alta el listado, esos 314 **no se cargaron** (colisión de código).
- Rangos: **cargados bien** `2–100`, `122–200`, `493–522` (208 estudios, `ExternalCode = Code`); **en colisión** `1`, `101–121`, `201–492` (314).
- **Explica el error:** el código `1` del RIS es `D.M.O. DENSITOMETRÍA ÓSEA` con `ExternalCode 0`; el motor enviaba `1` para
  `radiografía simple de tórax` y el RIS respondía `Exam Code 1 not encoded`. 🔶 Inferencia: el RIS reconoce el código enviado en `OBR-4`
  por su **`ExternalCode`** (si usara `Code`, el `1` existiría).
- En los 208 cargados, la **modalidad** del RIS coincide al 100 % con la asignada por `tools/clasificar_modalidad_ris.py`.
- El RIS tiene códigos numéricos de `1` a `5008`; **no hay huecos entre 1 y 519**, y el siguiente bloque empieza en `1001`.

**Riesgo (mientras no se corrija):** el motor tiene cargados esos 314 códigos. Hoy el RIS los rechaza (`not encoded`), pero si alguna vez
reconociera un código por `Code`, una orden se registraría con el examen equivocado (p. ej. `101` = `MAMOGRAFIA BILATERAL`).

**Corrección propuesta** (archivos generados el 2026-10-23):
1. Dar de alta en el RIS los 314 estudios con **códigos nuevos `523–836`** (hueco libre del RIS, sin colisión).
2. Importar en *Estudios* el listado completo corregido (208 sin cambios + 314 con código nuevo); la importación actualiza los existentes.
3. Reprocesar el ORM de las órdenes retenidas.

Alternativa: en vez de dar de alta duplicados, **enlazar** los estudios con exámenes que el RIS ya tiene (`RX PIE PERFIL`, etc.): requiere revisión manual de equivalencias.

### 11.1 Hipótesis iniciales (antes de ver el catálogo del RIS)

1. 🔶 El RIS **asignó su propia numeración** al dar de alta los estudios y el código real no es `1`. Verificar qué código tiene `radiografía simple de tórax` en el RIS.
2. 🔶 El examen existe pero **no está vinculado** al servicio / modalidad / procedencia (`INT`) con que llega la orden.
3. 🔶 El RIS espera el código con **otro formato** (ceros a la izquierda —los códigos del ejemplo son `11461`, `02020501`—, un sistema de codificación en `OBR-4.3`, o ambos).
4. 🔶 Los estudios aún no están **activos / publicados** en el RIS tras el alta.

### 11.2 Prueba de diagnóstico recomendada

Cargar **temporalmente** en *Estudios* una equivalencia con un código que el RIS **sí** tenga (por ejemplo `11461`, del ORM de referencia)
y reprocesar un ORM. Si el error `Exam Code` desaparece, el mecanismo del motor es correcto y el problema es el alta/numeración en el RIS.
Retirar luego esa equivalencia de prueba.

### 11.3 Si cambia la numeración

Reimportar el CSV con los códigos reales del RIS (la importación **actualiza** los existentes, no duplica).

### 11.4 Textos cortados y órdenes con varios estudios

De los 522 textos distintos, **169 miden exactamente 64 caracteres** (cortados por el origen) y casi todos son **órdenes con varios
estudios en un solo texto** (`radiografía simple de tórax, radiografía simple de abdomen`). Consecuencias:
- Darlos de alta en el RIS tal cual crea "estudios" con nombres truncados y combinados.
- El motor envía **un solo código y un solo `OBR`** por orden, cuando debería haber **un `OBR` (y un código) por cada estudio**.

**Datos medidos** (3636 órdenes, 522 textos distintos): 230 textos listan varios procedimientos (494 órdenes, 13,6 %); 162 de ellos están cortados a 64
caracteres (337 órdenes, ~9 %). En 197 de los 230, cada parte ya existe como estudio individual.

**Decisiones (sección 18):** las órdenes con varios estudios se **mantienen como examen combinado** (así se dieron de alta en el RIS: un ORM con un solo `OBR`).
Para los **textos cortados** hay que **investigar** si el worklist trae el texto completo en otro campo:
`python tools\consultar_worklist.py <host> <puerto> <AET destino> <AET propio> --combinadas` (pide además `RequestedProcedureComments`,
`ImagingServiceRequestComments` y `CommentsOnTheScheduledProcedureStep`). **Riesgo mientras tanto:** si el texto se cortó, un estudio puede haber desaparecido
sin que se note (por eso un texto de exactamente 64 caracteres es sospechoso).

---

## 12. Codificación de caracteres

- El motor envía **UTF-8** (`emisor_mllp.py`) y declara `MSH-18` = `UTF-8`.
- ✅ Se observó en el RIS texto roto (`radiografÃ­a`, `tÃ³rax`, y el apellido `CASTAÃ'O`): bytes UTF-8 leídos como Windows-1252/ISO-8859-1.
- **Resuelto (2026-10-23):** se configuró la codificación `UTF-8` en Mirth y se **verificó** que un paciente con ñ llega bien al RIS.
- **Pendiente:** los pacientes creados **antes** del cambio pueden tener el nombre corrupto; se identifican con la consulta de la sección 15 y se corrigen en el RIS.
- Si volviera a aparecer: revisar que los conectores de Mirth (entrada MLLP puerto 5556 y salida HTTP al RIS) sigan en `UTF-8`.

---

## 13. Registro de problemas encontrados y su solución

| # | Problema | Causa | Solución |
|---|---|---|---|
| 1 | `build.bat`: no encuentra Inno Setup | Instalación por usuario en `%LOCALAPPDATA%` | Se agregó esa ruta a la búsqueda |
| 2 | Instalador: `DeleteFile falló; código 5` | Los servicios mantenían abierto `MotorDICOM.exe` | El instalador detiene los servicios antes de copiar |
| 3 | Login: `password cannot be longer than 72 bytes` | `passlib` incompatible con `bcrypt` 5.x | `requirements.txt`: `bcrypt>=4.0.1,<5` |
| 4 | Logs de ~5,5 GB y con datos de pacientes | `pynetdicom` en INFO volcaba cada C-FIND; sin rotación | `pynetdicom` a WARNING, rotación 10 MB × 5, un log por proceso, rotación NSSM |
| 5 | `npm run build` falla | Llaves `{...}` en texto JSX se interpretan como código | El texto de ayuda va como cadena |
| 6 | ADT `FILTERED` en Mirth | Receptor `MSH-5/6` invertido | `ESTENSARADIO` / `SUITESTENSA` |
| 7 | ADT: `Missing Patient Given Name / Key External` | `PID-5` y `PID-3` sin formato del RIS | Plantillas de la sección 7 |
| 8 | ORM: apellido = nº de documento, sin nombre | La plantilla de `PID-3` quedó copiada en `PID-5` (pestaña ORM) | Corregir `PID-5` |
| 9 | Reprocesar reenviaba el mensaje viejo | Se reutilizaba el HL7 guardado | Cada intento regenera con la configuración vigente |
| 10 | Una orden con ORM fallido quedaba toda en error | Una sola tarea/estado/contador para ADT y ORM | Desacople (sección 9) |
| 11 | Estudio sin código creaba ORM inválidos | — | El ORM se retiene y el ADT sale igual |
| 12 | `Exam Code 1 not encoded` | 314 de los 522 códigos del motor chocaban con exámenes preexistentes del RIS (`ExternalCode = 0`) | Recodificar esos 314 (`523–836`), dar de alta e importar (11.0) |
| 13 | `IdEquipment and BusinessUnit are null` | Se había supuesto `PV1-3`; la especificación usa `OBR-21` y `OBR-18` | Equipo y unidad de negocio por modalidad (10.2) |
| 14 | `EquipmentMandatory ... IdEquipment is null` | `OBR-21` sin cargar | Valor fijo `OBR-21` = `{codigo_equipo}` y `ExternalCode` del equipo = ese código |
| 15 | `Configuration error in DB: LsBusinessUnit...` | Faltaban las relaciones de la unidad de negocio en el RIS | Configuración del RIS (8.2) |
| 17 | La ventana de auditoría quedaba recortada y "muy abajo" en el scroll | La capa fija estaba anclada a un contenedor del Monitor y no a la pantalla | Se dibuja en `<body>` (portal) y se rediseñó en dos columnas |
| 16 | Apellido `CASTAÃ'O` en el RIS | Mirth/RIS leen como Latin-1 los bytes UTF-8 (el motor envía UTF-8 con `MSH-18`) | **Pendiente**: codificación UTF-8 en los conectores de Mirth (sección 12) |

---

## 14. Seguridad y datos personales

- Los **datos de pacientes** circulan por logs, mensajes HL7 guardados en `registro_trazabilidad` y la consola. El log de `pynetdicom` está
  apagado por defecto por ese motivo (`MOTORDICOM_LOG_DICOM=1` lo reactiva).
- **No compartir** salidas del worklist sin revisar: el `StudyInstanceUID` contiene el número del paciente.
- Cambiar la contraseña inicial `admin` en el primer acceso (es obligatorio). El `JWT_SECRET` se genera en la instalación.
- `C:\ProgramData\MotorDICOM\` guarda la contraseña de PostgreSQL (`.superpw`, `.env`): restringir el acceso.

---

## 15. Operación: consultas y procedimientos útiles

`psql` del motor: `"C:\Program Files\MotorDICOM\pgsql\bin\psql.exe" -h localhost -p 5433 -U postgres -d <DB_NAME>`
(contraseña en `.superpw`; el nombre de la base está en `.env`, `DB_NAME`).

```sql
-- Estudios más frecuentes y su modalidad DICOM
select payload_dicom_raw->>'00321060' estudio, payload_dicom_raw->>'00080060' modalidad, count(*)
from registro_trazabilidad group by 1,2 order by 3 desc;

-- Estado de las órdenes y de cada mensaje
select estado, count(*) from registro_trazabilidad group by 1;
select accession_number, estado, payload_hl7->'envios'->'orm'->>'estado' orm,
       payload_hl7->'envios'->'orm'->>'ultimo_error' error_orm
from registro_trazabilidad where estado like 'ERROR%' order by created_at desc limit 20;
```

**Reenviar una orden ya procesada con la configuración nueva:** *Reprocesar* solo actúa sobre mensajes en `ERROR_PERMANENTE`.
Un mensaje **aceptado** no se reenvía. Solo en entornos de prueba se puede borrar el registro
(`delete from registro_trazabilidad where accession_number = '...'`) para que la ingesta lo capture de nuevo;
esto elimina su trazabilidad.

**Respaldo de la base:** `installer\backup_db.ps1` (se instala en `C:\Program Files\MotorDICOM\installer`). Hace un `pg_dump` en
`C:\ProgramData\MotorDICOM\backups` y conserva 14 días. Se programa con `powershell -File backup_db.ps1 -Programar` (tarea diaria a las 02:00, como administrador).
Instrucciones de restauración en el encabezado del script. Guardar aparte `.env` y `.superpw`. 🔶 Escrito pero **no probado** en Windows.

**Pacientes que pudieron crearse con el nombre corrupto** (anteriores al cambio a UTF-8 en Mirth): órdenes con caracteres no ASCII en el nombre.

```sql
select accession_number, patient_id, payload_dicom_raw->>'00100010' nombre, created_at
from registro_trazabilidad
where payload_dicom_raw->>'00100010' ~ '[^\x01-\x7F]'
order by created_at;
```

**Pruebas automatizadas:** `pip install -r requirements-dev.txt` y `python -m pytest tests -q` (no necesitan PostgreSQL ni la cola: usan dobles en memoria).
Cubren marcadores y componentes del serializador, separación de nombres, validación del paciente, clasificación de modalidades, CSV, estados por mensaje,
reintentos independientes, reenvío y corrección de datos.

**Logs:** `C:\ProgramData\MotorDICOM\logs\` (usar `Get-Content <archivo> -Tail 40`; no abrirlos enteros).

---

## 16. Pendientes y mejoras

Estado tras las decisiones de la sección 18. **Resuelto** en esta etapa: validación de datos del paciente, corrección manual, reenvío de órdenes,
auditoría en una sola pantalla, sexo `O` → `U`, respaldo de la base, pruebas automatizadas y `static\` fuera del repositorio.

| Prioridad | Tema | Notas |
|---|---|---|
| **Alta** | **Textos cortados a 64 caracteres** (162 textos, 337 órdenes, ~9 %) | Correr `tools/consultar_worklist.py --combinadas` y ver si el worklist trae el texto completo en `RequestedProcedureComments`, `ImagingServiceRequestComments` o `CommentsOnTheScheduledProcedureStep`. Hasta entonces se envían como hoy; riesgo: un estudio omitido pasa desapercibido |
| **Alta** | **Pacientes creados antes del cambio a UTF-8** con el nombre corrupto | Identificarlos con la consulta de la sección 15 y corregirlos en el RIS (el motor aún no genera `A08`; reenviar un ADT `A04` puede o no actualizarlos: no verificado) |
| **Alta** | `PK` = DNI (decisión 18) | Riesgo de **pacientes duplicados** si SISGH envía el IDHC real como `PK`. Revisar antes de operar con el origen definitivo |
| **Alta** | **Pasar de pruebas a operación**: el RIS destino es producción todavía sin uso | Antes de operar: limpiar los pacientes y órdenes de prueba, cambiar `admin`/`admin123`, programar el respaldo y confirmar `MSH-4` |
| Media | Equipos del RIS de las demás modalidades | `ExternalCode` de cada equipo y vínculos con la unidad `CD1` (sección 8.2). Densitometría y medicina nuclear no tienen equipo: su ORM queda retenido |
| Media | Flujos **RIS → HIS** sin implementar | ORM de estado (`XO`/`CM`/`CA`) y ORU de resultados |
| Media | Mensaje `A08` (actualización de paciente) | Para corregir datos de pacientes ya creados |
| Baja | Apellidos compuestos | Decisión vigente: primera palabra = apellido; se corrige a mano desde la auditoría |
| Baja | `ORC-12` fijo en `SIN DERIVADOR` | Usar el médico derivante del worklist si algún día viene (hoy llega vacío) |
| Baja | Sugerencias de código por similitud al cargar equivalencias | Si el catálogo del RIS crece |
| Baja | `PV1-19` (nº de visita) | No exigido en las pruebas |

---

## 17. Especificación del proveedor del RIS (`Relevamiento_integracion.xlsx`)

Documento recibido el 2026-10-23 (hojas por segmento y mensaje). Resume lo que **exige el RIS** y cómo se refleja en el motor.
Referencias a hojas entre corchetes. La especificación habla de un HIS llamado *GOMEDISYS/SISGH* y usa ejemplos de otra institución (`PAMI1`, `MILSTEIN`).

### 17.1 Reglas generales
- **Cada ORM contiene una sola orden (`ORC`) y un solo procedimiento (`OBR`)** [Order Management; PV1: "UN PROCEDIMIENTO POR MENSAJE"].
  Una orden con varios estudios debe viajar como **varios ORM**. Hoy el motor envía un ORM por orden (sección 11.4).
- Segmentos obligatorios del ORM: `MSH`, `PID`, `PV1`, `ORC`, `OBR`. Opcionales: `ZDS` (Study Instance UID) y `OBX`.
- `MSH`: `MSH-3` = `SISGH` (prod) / `TEST_SISGH` (prueba); `MSH-5`/`MSH-6` = `SUITESTENSA`; `MSH-9` = `ADT^A04` / `ORM^O01`; `MSH-10` autonumérico único;
  `MSH-11` = `P` (prod) / `T` (prueba); `MSH-12` = `2.5`; **`MSH-18` = `UTF-8`**.
- `ACK`: `MSA-1` = `AA` (correcto), `AE` (mensaje no gestionado), `AR` (error de parseo o procesamiento); `MSA-2` = `MSH-10` del mensaje.
- `ADT`: `A04` y `A08` son equivalentes para crear pacientes; `A08` también actualiza datos; `A40`/`A34` unifican pacientes. La **creación de pacientes también ocurre por mensajería ORM**.

### 17.2 `PID`
- `PID-3` (obligatorio, repetible): `IDHC^^^PK~NUMERO_DOCUMENTO^TIPO_DOC^^CF~NUMERO_AFILIADO`.
  `PK` = **ID interno autoincremental de SISGH (IDHC)**; `CF` = documento (tipo en el componente 2: `DU` documento único, `DE` extranjero, `PA` pasaporte, `LC`, `LE`, `RN` recién nacido).
- `PID-5`: `APELLIDO^DOBLE APELLIDO^NOMBRE1^NOMBRE2...` (coincide con lo implementado).
- `PID-7` `AAAAMMDD`; `PID-8` `F`/`M`/`U`. `PID-11` domicilio, `PID-13` teléfono, `PID-18` (`NUMERO_DOCUMENTO^^^DU`) y `PID-19` (afiliado) son opcionales y hoy no se envían.

### 17.3 `PV1`
- `PV1-2` (clase de paciente) **obligatorio** en las órdenes: `O` ambulatorio, `I` internado, `E` urgencia/guardia.
- **`PV1-3`: código de la ubicación de donde viene el paciente** (configurado en el HIS), con la descripción en `PV1-3-9`. **No es el equipo.**
- `PV1-19` (nº de visita): "número de orden de trabajo", entero; llega vacío en el ADT y con valor en el ORM. En las pruebas no fue exigido.

### 17.4 `ORC`
| Campo | Qué pide el RIS |
|---|---|
| `ORC-1` / `ORC-5` | `NW` + `SC` (nueva orden con cita, HIS → RIS) o `SN` + vacío (admisión directa, aparece en la lista del técnico). También `XO`, `CM`, `CA` en el sentido RIS → HIS |
| `ORC-2` | Nº de orden (**entero único por orden**) `^` entidad que lo genera (`<nº>^SISGH`). Obligatorio |
| `ORC-3` | Vacío desde el HIS (lo completa el RIS al devolver) |
| `ORC-4` | Placer group number: el mismo valor que `ORC-2` o una parte; `ORC-4-2` = `ORC-2-2`. Obligatorio |
| `ORC-7` | `ORC-7.4` = fecha/hora de la cita (o de la creación de la orden si no tiene cita); `ORC-7.6` = prioridad. Ej.: `^^^20200427141200^^1` |
| `ORC-9` | Momento en que se generó la orden |
| `ORC-12` | Médico solicitante: `id^apellido^nombre` |
| `ORC-17` | **Procedencia** (origen del paciente): `código^descripción`. Obligatorio |

### 17.5 `OBR`
| Campo | Qué pide el RIS |
|---|---|
| `OBR-2` | Igual que `ORC-2` (`<nº>^SISGH`) |
| `OBR-3` | Vacío (igual que `ORC-3`) |
| `OBR-4` | `código^descripción` del examen. **El código es el de la parametrización del RIS (p. ej. `RX001`), no el ID (GUID)** |
| **`OBR-18`** | **Código de la unidad de negocio / centro de costo que realiza el examen** (`BusinessUnit`) |
| **`OBR-21`** | **Código del recurso (sala, consultorio, equipo) donde se realiza** (`IdEquipment`) |
| `OBR-27` | `1^^^AAAAMMDDhhmmss^^1`: fecha/hora de la cita, o de creación de la orden si no tiene cita. `OBR-27.6` = prioridad |
| `OBR-13` / `OBR-31` | Información clínica / motivo del estudio (opcionales) |

### 17.6 Canales de la especificación
`ADT` y `ORM` HIS → RIS por TCP (puertos 2200 y 2201), `ORM` RIS → HIS (2202, cambios de estado) y `ORU` RIS → HIS (2203, resultados).
En este entorno el motor entrega a Mirth (`172.31.3.150:5556`); los flujos RIS → HIS (estados y resultados) **no están implementados**.

### 17.7 Correcciones que surgieron de esta especificación
1. Equipo y unidad de negocio van en **`OBR-21` y `OBR-18`**, no en `PV1-3` (que era una suposición errónea basada en el ORM de ejemplo).
2. La fecha/hora de la cita va en `ORC-7.4` y `OBR-27.4` (el ejemplo del RIS tenía el valor en `OBR-25`). Se agregó el marcador `{cita}` (fecha y hora programadas del worklist; si no hay fecha, usa la del mensaje).
3. La entidad emisora del número de orden es `SISGH` (no `HIS`).

---

## 18. Decisiones registradas (2026-10-23)

| Tema | Decisión | Consecuencia |
|---|---|---|
| `PatientID` del worklist | Es un **DNI** y se mantiene como `PK` | El RIS espera el IDHC de SISGH como `PK`: posible duplicación de pacientes (ver 16) |
| `ORC-1` | Se mantiene **`SN`** (admisión directa) | La orden aparece de inmediato en la lista de ejecución del técnico |
| ADT y ORM | Siguen **independientes** | La especificación dice que los pacientes también se crean por el ORM (lleva el `PID` completo) |
| Datos mínimos del paciente | **Retener y avisar** (9.1) | Una orden con datos incompletos no se envía; se corrige y se reenvía desde la auditoría |
| Corrección de datos | **Editor en el motor** (auditoría → *Datos del paciente*) | Queda registrado quién, cuándo, antes y después |
| Nombres | Primera palabra = **apellido** | Falla con apellidos compuestos; se corrige a mano |
| Entorno | El RIS al que se envía es **producción, todavía sin uso** | Los datos creados son reales; ver lista previa a operar en 16 |
| Órdenes con varios estudios | Se mantienen como **examen combinado** (como se dio de alta en el RIS) | Un ORM con un solo `OBR`; no se separa por estudio |
| Textos cortados a 64 caracteres | **Investigar primero** si el worklist trae el texto completo | Mientras tanto se envían como hoy |
| Codificación de caracteres | Mirth ya en UTF-8; **verificado**: la ñ llega bien | Solo quedan por corregir los pacientes creados antes del cambio |
| Reproceso en masa | **Descartado** por ahora | Se usa *Reenviar* por orden |

---

## 19. Referencia de código

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Subcomandos (`api`, `worker`, `ingesta`, `migrate`, `crear-admin`), logging |
| `core/ingesta.py` | Consulta C-FIND al worklist y alta de órdenes |
| `core/broker.py` | Tareas de envío por mensaje (Huey), reintentos |
| `core/serializador_hl7.py` | Construcción del HL7: valores fijos, componentes, marcadores |
| `core/transformador.py` | Mapeo + valores fijos + equivalencia de estudio |
| `core/catalogos.py` | Catálogo de tags DICOM y campos HL7, mapeos por defecto |
| `core/mapeo_repo.py`, `core/config_repo.py` | Mapeos/valores fijos y canales en BD |
| `core/equivalencias_repo.py` | Equivalencias de estudio, CSV, pendientes, modalidades |
| `core/equipos_repo.py`, `core/modalidad_ris.py` | Equipo por modalidad; modalidades del RIS y su deducción desde el texto |
| `core/auditoria.py` | Estado por mensaje, estado de la orden, reproceso |
| `core/emisor_mllp.py` | Envío MLLP y validación del ACK |
| `core/api.py` | API REST de la consola |
| `frontend-motor/src/components/` | `Monitor`, `AuditoriaModal`, `Canales`, `Mapeos`, `Estudios` |
| `tools/consultar_worklist.py` | Inspección del worklist de origen |
| `tools/clasificar_modalidad_ris.py` | Asignación de modalidad del RIS a cada estudio (usa `core/modalidad_ris.py`) |
| `build.bat`, `installer/` | Construcción del instalador |

---

## Exportar / importar la configuración (replicar en otros hospitales)

Menú **Configuración** de la interfaz. Evita recargar a mano las pestañas ADT/ORM, los valores fijos y los equipos en cada hospital.

**Exportar** genera `configuracion_<hospital>_<AAAAMMDD>.json` (formato `motordicom-configuracion`, versión 1) con las secciones elegidas:

| Sección | Contenido | Por defecto | Al importar |
|---|---|---|---|
| `mensajes` | mapeos y valores fijos ADT/ORM | sí | **reemplaza** los tipos presentes en el archivo |
| `equipos` | equipo por modalidad / unidad de negocio | sí | agrega o actualiza (no borra) |
| `canales` | destinos MLLP (IP, puerto) | no (propio de cada hospital) | agrega o actualiza |
| `equivalencias` | catálogo de estudios (códigos del RIS) | no (propio de cada hospital) | agrega o actualiza |

**Importar**: se elige el archivo y primero se muestra una **vista previa** (nuevos / modificados / quitados / sin cambios, con detalle) sin escribir nada. Los errores de validación bloquean la aplicación. Se destacan los valores que suelen diferir por hospital (`MSH-3/4/5/6/11`, `PV1-2/3`, `ORC-17`) para revisarlos antes de aplicar. Al aplicar se guarda un **respaldo automático** de toda la configuración previa en `<MOTORDICOM_DATA>\backups\configuracion_antes_de_importar_<fecha>.json`; ese mismo archivo se puede importar para revertir.

**API** (requiere autenticación): `GET /api/v1/configuracion/exportar?secciones=&hospital=&comentario=` y `POST /api/v1/configuracion/importar` con `{configuracion, secciones, aplicar}` (`aplicar=false` = vista previa; errores → HTTP 400 con `detail.errores`).

Código: `core/configuracion_repo.py`, `frontend-motor/src/components/Configuracion.jsx`, pruebas `tests/test_configuracion.py` y `tests/test_api_configuracion.py`.
