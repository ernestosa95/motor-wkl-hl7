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
| **ORM^O01** (orden del estudio) | 🔶 Casi: tras los ajustes, al 17:42 el RIS solo devolvía `I.REST C02 - Exam Code 1 not encoded`. Falta que el **código de examen** enviado exista en el RIS. |

Lo pendiente principal es la **codificación del examen** (sección 11). Lo demás está resuelto o es mejora.

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

Compilar **sin** `/nofront` siempre que haya cambios en `frontend-motor/`.

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

**Componentes:** `SEG-N.M` escribe solo el componente M del campo N, sobre lo que ya tenga (p. ej. `PID-3.4`).
Se aplican **después** de los campos completos.

**Limitaciones conocidas:**
- Un valor fijo **no puede vaciar** un campo mapeado desde DICOM (los valores vacíos se ignoran). Para dejarlo vacío hay
  que quitar el destino en la pestaña de mapeos.
- Los marcadores son `{tag de 8 hex}`, `{tag:apellido|nombres}`, `{ahora}`, `{codigo_estudio}`, `{descripcion_estudio}`. Cualquier otro nombre da error.
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

## 8. Configuración del mensaje ORM (🔶 un error pendiente)

**Valores fijos (pestaña ORM):**

| Campo | Valor | Para qué |
|---|---|---|
| `MSH-5` / `MSH-6` / `MSH-18` | `ESTENSARADIO` / `SUITESTENSA` / `UTF-8` | Receptor y codificación |
| `PID-3` | `{00100020}^^^PK~{00100020}^DU^^CF` | Igual que el ADT |
| `PID-5` | `{00100010:apellido}^^{00100010:nombres}^` | Igual que el ADT. **No copiar la plantilla de `PID-3` aquí** (error ya ocurrido, ver 10) |
| `PV1-2` | `O` (por defecto) | Clase de paciente |
| `PV1-3` | `INT` (valor usado en las pruebas) | Ubicación |
| `ORC-1` | `SN` | Control de orden |
| `ORC-2` | `{00080050}^HIS` | Nº de orden + autoridad |
| `ORC-4` | `{00080050}^HIS` | `PlacerGroupNumber` + `PlacerGroupNumberIssuer` |
| `ORC-7` | `1^^^{ahora}^^1` | Cantidad/tiempo (`Exam Date`, probable) |
| `ORC-9` | `{ahora}` | Fecha/hora de la transacción (`Exam Date`, probable) |
| `ORC-12` | `^SIN DERIVADOR` | Médico solicitante (copiado del ejemplo) |
| `ORC-17` | `INT^integracion` | **Procedencia** (el componente 1 es el código) |
| `OBR-2` | `{00080050}^HIS` | Nº de orden (placer) |
| `OBR-4` | `{codigo_estudio}^{descripcion_estudio}` | **Código de examen** |
| `OBR-25` | `1^^^{ahora}^^1` | Cantidad/tiempo (copiado del ejemplo) |

Recomendado en la pestaña de **mapeos** del ORM: quitar los destinos `OBR-3`, `OBR-24`, `OBR-27` (el ejemplo del RIS los deja vacíos) y no usar `OBR-7`.
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
| `Exam Code 1 not encoded` | `OBR-4` componente 1 | ❌ **Pendiente** (sección 11) |

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
- Interfaz: el Monitor muestra por orden `ADT ✓ / ORM ✕`; la auditoría detalla destino, hora, error e intentos de cada mensaje.

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

---

## 11. 🔶 Pendiente: codificación del examen

**Síntoma:** el motor ya envía `OBR-4` = `1^radiografía simple de tórax` (la equivalencia y la plantilla funcionan), y el RIS responde
`C02 - Exam Code 1 not encoded`: **no encuentra un examen con código `1`**.

### 11.1 Hipótesis (ordenadas)

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

Decisión pendiente: separar el texto por comas (un código por estudio; depende de que el texto no venga cortado) o resolverlo en el origen.

---

## 12. Codificación de caracteres

- El motor envía **UTF-8** (`emisor_mllp.py`) y declara `MSH-18` = `UTF-8`.
- ✅ Se observó en el RIS texto roto (`radiografÃ­a`, `tÃ³rax`): bytes UTF-8 leídos como Windows-1252/ISO-8859-1. En ese momento el ORM
  **salía sin `MSH-18`**. 🔶 Poniendo `MSH-18` = `UTF-8` en la pestaña ORM debería corregirse; **no verificado**.
- Si persiste, revisar en Mirth la **codificación** del conector de entrada (MLLP, puerto 5556) y del conector de salida HTTP: deben ser `UTF-8`.
- Afecta también a **nombres con tilde o ñ**. Probar con un paciente real que los tenga.

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

**Logs:** `C:\ProgramData\MotorDICOM\logs\` (usar `Get-Content <archivo> -Tail 40`; no abrirlos enteros).

---

## 16. Pendientes y mejoras

| Prioridad | Tema |
|---|---|
| **Alta** | Resolver el **código de examen** (sección 11) |
| **Alta** | Decidir el tratamiento de los **textos cortados y órdenes con varios estudios** (11.4) |
| Alta | Verificar `MSH-18` / codificación UTF-8 con un paciente con tildes (sección 12) |
| Media | Abrir el **PR** de `build/script-windows` / `feat/adt-mirth` hacia `main` |
| Media | Quitar `static\` del control de versiones (es salida de build; genera cambios y conflictos en cada compilación) |
| Media | **Reprocesar en masa** los ORM con error (hoy es de a una orden) |
| Media | Validar **datos mínimos del paciente** (apellido y nombre) antes de enviar, reteniendo y avisando si faltan |
| Media | Decidir si el **ORM debe esperar** a que el ADT sea aceptado |
| Media | Regla de **apellidos compuestos** (la regla actual toma solo la primera palabra) |
| Baja | Importar el catálogo del RIS y elegir el código con un buscador / sugerencias por similitud |
| Baja | `ORC-12` fijo en `SIN DERIVADOR`: usar el médico derivante del worklist si viene |
| Baja | `PV1-19` (nº de visita) y códigos de servicio/equipo reales (`PV1-3`, `ORC-17`) si el RIS los exige |

---

## 17. Referencia de código

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
| `core/auditoria.py` | Estado por mensaje, estado de la orden, reproceso |
| `core/emisor_mllp.py` | Envío MLLP y validación del ACK |
| `core/api.py` | API REST de la consola |
| `frontend-motor/src/components/` | `Monitor`, `AuditoriaModal`, `Canales`, `Mapeos`, `Estudios` |
| `tools/consultar_worklist.py` | Inspección del worklist de origen |
| `tools/clasificar_modalidad_ris.py` | Asignación de modalidad del RIS a cada estudio |
| `build.bat`, `installer/` | Construcción del instalador |
