# Guía de despliegue de la integración SUITESTENSA en un hospital

> **Para quién:** quien vaya a poner en marcha el motor en un hospital nuevo. Está escrita a partir del primer despliegue (caso de referencia,
> sitio `ARP03`), con todos los errores que aparecieron y cómo se resolvieron, para no repetirlos.
> **Cómo usarla:** completar primero la [hoja de parámetros](PLANTILLA_PARAMETROS_HOSPITAL.md) del hospital y seguir las fases en orden.
> **Detalle y bitácora del caso de referencia:** [INTEGRACION_SUITESTENSA.md](INTEGRACION_SUITESTENSA.md). Arquitectura general: [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md).
>
> Marcas de confianza: ✅ verificado con el sistema real · 🔶 inferido, hay que confirmarlo en cada hospital · ❓ no se sabe.
> No contiene datos de pacientes; los ejemplos son ficticios.

---

## 0. Cómo está pensado: qué es común y qué es de cada hospital

**Una instancia del motor por hospital.** El motor guarda una sola configuración (un conjunto de canales, mapeos y equivalencias, en una base PostgreSQL local);
no es multi-hospital. Replicar = instalar el mismo instalador en el servidor de cada hospital y configurarlo con los parámetros de ese sitio.

```
 Worklist DICOM ──C-FIND──► MOTOR (1 por hospital) ──MLLP──► Mirth ──HTTP──► RIS SUITESTENSA
 (origen del hospital)       ingesta · ADT · ORM              (canal del hospital)
```

| Es **común** a todos los hospitales (viene en el instalador) | Es **específico** de cada hospital (se configura) |
|---|---|
| Código del motor, instalador, servicios y pantallas | Dirección, puerto y AET del worklist de origen |
| Estructura de `PID-3`, `PID-5`, `ORC`, `OBR` y todos los marcadores | Direcciones y puertos de los canales MLLP hacia Mirth |
| Validación de datos del paciente, reintentos, estados, reenvío | **Código del hospital** en `MSH-4` y el receptor `MSH-5`/`MSH-6` que acepta su Mirth |
| Clasificación de estudios por modalidad (`core/modalidad_ris.py`) | Código de **procedencia**, **unidad de negocio** y **equipos** definidos en su RIS |
| Herramientas de `tools/` | **Códigos de los exámenes** en su RIS (cada RIS tiene su propia numeración) |
| Esta guía | Qué es el `PatientID` del origen (DNI o ID interno del HIS) |

**Quién participa** (en cada hospital suelen ser equipos distintos; sin ellos no se avanza):

| Rol | Qué aporta |
|---|---|
| Administrador del **origen** (worklist / HIS) | Acceso DICOM, AET, qué datos entrega, identidad del paciente |
| Administrador de **Mirth** | Canales, filtros, codificación UTF-8, ambiente de prueba |
| Administrador del **RIS** | Exámenes, equipos, unidades de negocio, procedencias y sus vínculos |
| Quien instala el **motor** | Servidor Windows, build, instalación y configuración |

---

## 1. Fase A — Relevamiento (antes de tocar nada)

Completar la [hoja de parámetros](PLANTILLA_PARAMETROS_HOSPITAL.md). Cada pregunta existe porque, si se omite, aparece un error concreto más adelante.

### 1.1 Origen (worklist)
Correr desde el servidor del motor (o una PC con acceso al worklist):
```
python tools\consultar_worklist.py <host> <puerto> <AET destino> <AET propio> --max 3
python tools\consultar_worklist.py <host> <puerto> <AET destino> <AET propio> --combinadas
```
(Por defecto oculta los datos del paciente.) Anotar:

| Qué mirar | Por qué importa | Caso de referencia |
|---|---|---|
| ¿Trae un **código de procedimiento** (`Requested Procedure Code`)? | Si lo trae, la tabla de equivalencias puede usarlo en vez del texto | ✅ No: solo texto |
| ¿Trae el **texto completo** o lo corta a 64 caracteres? | La descripción DICOM (`LO`) tiene ese límite; un estudio cortado puede perderse sin avisar | ✅ Cortado a 64: **162 de 522 textos distintos (31 %)**, que son el 9 % de las órdenes |
| ¿Hay órdenes con **varios estudios** en un solo texto? | El RIS pide un procedimiento por mensaje | ✅ Sí, separados por coma (13,6 % de las órdenes) |
| ¿Soporta `RequestedProcedureComments`, `ImagingServiceRequestComments`, `CommentsOnTheScheduledProcedureStep`? | Podrían traer el texto completo | ✅ Los soporta (vacíos en estudios simples); 🔶 sin confirmar si los llena en las combinadas |
| ¿Qué es el `PatientID`: **DNI** o **ID interno del HIS**? | El RIS espera el ID interno como `PK`; si se envía el DNI como `PK` puede haber **pacientes duplicados** | ✅ Es un DNI; se usó como `PK` (riesgo aceptado y documentado) |
| ¿Cómo viene el nombre? | Con `^` se separa bien; sin `^` se toma la primera palabra como apellido | ✅ `APELLIDO NOMBRES`, sin `^` |
| ¿Qué modalidades y cuántas órdenes por día? | Dimensiona equipos y pruebas | ✅ CR/DX/CT/MR/MG |

### 1.2 Mirth
- Puertos y direcciones de los canales de **ADT** y **ORM** (pueden ser el mismo).
- ¿Filtra por `MSH-3`/`MSH-4`/`MSH-5`/`MSH-6`? Un mensaje con el receptor invertido o un emisor no reconocido queda **`FILTERED`**. ✅
- Codificación de los conectores (entrada MLLP y salida HTTP): **UTF-8**. Si no, los nombres con ñ o tilde llegan corruptos (`CASTAÃ'O`). ✅
- Si hay un Mirth de **prueba** distinto del de producción.

### 1.3 RIS (SUITESTENSA)
Pedir al administrador del RIS, en el mismo formato que los CSV de exportación:
1. **Catálogo de exámenes** (`exams.csv`: `Description;Code;ExternalCode;IdModality;...`).
2. **Lista de equipos** (`equipments.csv`: `Description;ExternalCode;DICOMModalityCode;...`).
3. Unidades de negocio, procedencias y sus vínculos (`LsBusinessUnitEquipment`, `LsBusinessUnitModality`, `LsBusinessUnitProvenance`).
4. La **especificación del proveedor** del hospital (`Relevamiento_integracion.xlsx`): puede traer valores propios (nombre de la aplicación, facility).

> ✅ **Regla central del RIS:** reconoce exámenes y equipos por su **`ExternalCode`** (código de integración), no por el ID interno ni por `Code`.
> Un examen o equipo que existe pero tiene `ExternalCode` vacío o `0` se rechaza como "not encoded".

---

## 2. Fase B — Configuración del RIS (la hace su administrador)

| # | Qué crear | Detalle |
|---|---|---|
| B1 | **Exámenes** | Uno por cada estudio que llegue del worklist, con su `ExternalCode` = código que enviará el motor (`OBR-4.1`) y su modalidad. **Usar `tools/cruzar_catalogo_ris.py` para evitar colisiones** (ver Fase E, paso E4). Si un código ya lo ocupa otro examen, **la carga lo omite sin avisar** |
| B2 | **Equipos** | Uno por modalidad que se integre, con `ExternalCode` = código que enviará el motor (`OBR-21`). En el caso de referencia, solo 4 de 13 equipos tenían `ExternalCode` |
| B3 | **Unidad de negocio** | El centro de costo que realiza los estudios (`OBR-18`), p. ej. `CD1` |
| B4 | **Procedencia** de integración | Código (`ORC-17.1`), p. ej. `INT`. Si no existe: `Provenance Code X not encoded` |
| B5 | **Vínculos de la unidad de negocio** | Con **cada equipo, modalidad y procedencia** que se use. Si falta alguno: `Configuration error in DB: LsBusinessUnit... is empty` |

Por cada **modalidad nueva** que se integre después hay que repetir B2 y B5.

---

## 3. Fase C — Mirth (lo hace su administrador)

1. Canal(es) de entrada MLLP para `ADT^A04` y `ORM^O01`, hacia el RIS por HTTP.
2. **Codificación UTF-8** en el conector de entrada y en el de salida. ✅
3. Si hay filtro por emisor/receptor: aceptar los valores del hospital (`MSH-3`, `MSH-4`, `MSH-5`, `MSH-6`).
4. Probar con un mensaje de ejemplo (el que genera el motor, sección 6) antes de conectar el motor.
5. 🔶 Definir si el ambiente es de **prueba** (`MSH-3 = TEST_SISGH`, `MSH-11 = T` según la especificación) o producción.

---

## 4. Fase D — Instalar el motor

### 4.1 Preparar la PC de compilación (una vez)
- Python con las dependencias, Node/npm, **Inno Setup 6** (también vale la instalación por usuario) y Git.
- Carpeta `vendor\` (no está en el repositorio; repetirla en cada PC de compilación): `vendor\pgsql\` (PostgreSQL portable x64, con `bin\initdb.exe`, `pg_ctl.exe`, `psql.exe`, `pg_dump.exe`),
  `vendor\nssm.exe` (64 bits) y `vendor\vc_redist.x64.exe`.

### 4.2 Compilar
```
git checkout main && git pull
build.bat 1.0.1 /deps        # la primera vez instala dependencias; luego basta build.bat 1.0.1
```
- Compilar **sin** `/nofront` siempre que cambie el frontend. `static\` ya no está versionado: si `git pull` protesta por archivos de `static\`, ejecutar antes `git checkout -- static`.
- Termina en `BUILD OK` y deja `dist_installer\MotorDICOM-Setup-1.0.1.exe`. El detalle va a `build.log`.
- Pruebas automáticas (opcional): `pip install -r requirements-dev.txt` y `python -m pytest tests -q`.

### 4.3 Instalar en el servidor del hospital
1. Ejecutar el instalador **como administrador**. Instala en `C:\Program Files\MotorDICOM`, crea los servicios `MotorDICOM API`, `Worker`, `Ingesta` y `Postgres`, y los datos en `C:\ProgramData\MotorDICOM`.
2. Abrir `http://localhost:8000` (desde el servidor). Primer acceso: `admin` / `admin123`, con **cambio de contraseña obligatorio**.
3. Abrir el puerto 8000 en el firewall solo si se accederá a la consola desde otras PC (el instalador ya abre 8000 y 4242).
4. Comprobar que los 4 servicios estén en ejecución (`services.msc`).

> **Actualizar** una instalación existente: instalar con la cola de tareas vacía si es posible (las tareas en reintento con un formato anterior se pierden);
> los datos y la configuración se conservan. El instalador detiene los servicios solo.

---

## 5. Fase E — Configurar el motor

Todo desde la consola web. **Sin reiniciar**: la configuración se lee de la base en cada intento.

### E1. Canales
*Canales →* cargar el worklist (host, puerto, AET destino y AET propio), el destino ADT y el destino ORM (host y puerto de Mirth). Usar **Probar** en cada uno
(el de los canales MLLP solo comprueba que el puerto acepte la conexión; no envía nada).

### E2. Mapeo → valores fijos
*Mapeo →* pestaña **ADT** y pestaña **ORM** → *Opciones avanzadas*. Las dos pestañas son independientes: cargar los valores en **cada una** (un valor copiado en la pestaña equivocada
causó que el apellido saliera como el número de documento). Valores base en la sección 6. Los marcados ⟨así⟩ son de cada hospital.

### E3. Equipo por modalidad
*Estudios → Equipo por modalidad*: para cada modalidad que se integre, poner el **código de equipo** (= `ExternalCode` del equipo en el RIS, B2) y la **unidad de negocio** (B3).
Los valores por defecto (`DX`, `CT`, `MR`, `MG`, `US`, `BMD`, `NM`) solo sirven si el administrador del RIS usó exactamente esos códigos. Una modalidad sin equipo **retiene el ORM** con un aviso claro.

### E4. Estudios y códigos de examen (el paso con más riesgo)
1. Dejar que el motor ingiera órdenes unos días (o ejecutar con órdenes de prueba) para que en *Estudios* aparezca la lista **Sin código**.
2. **Exportar pendientes (CSV)**.
3. Asignar la modalidad del RIS a cada estudio:
   ```
   python tools\clasificar_modalidad_ris.py estudios_pendientes.csv con_modalidad.csv
   ```
   Revisar las filas con `revisar = SI` (sin modalidad en el texto, procedimientos que no son imagen, mezclas de modalidades).
4. **Cruzar con el catálogo del RIS** y asignar códigos sin colisión:
   ```
   python tools\cruzar_catalogo_ris.py con_modalidad.csv exams.csv --salida cruce
   ```
   Genera `informe_diferencias.csv`, `estudios_a_cargar_en_ris.csv` y `estudios_motor_importar.csv`. Si el listado no trae códigos, los asigna libres
   (por defecto a partir del mayor código numérico del RIS). En el primer hospital, sin este paso, **314 de 522 códigos chocaron** con exámenes existentes.
5. El administrador del RIS **da de alta** `estudios_a_cargar_en_ris.csv` (con su modalidad). Verificar con un `exams.csv` nuevo que `Code` y `ExternalCode` quedaron iguales al código.
6. Recién entonces **Importar CSV** `estudios_motor_importar.csv` en *Estudios*. La importación actualiza los existentes; no duplica.
7. Revisar en *Estudios* que la lista **Sin código** quede vacía.

### E5. Estado de las órdenes retenidas
Una orden retenida (sin código de estudio, sin equipo o con datos del paciente incompletos) se destraba al corregir el dato y pulsar **Reprocesar** o **Reenviar**.

---

## 6. Valores base (copiar y completar los ⟨⟩)

### 6.1 Pestaña ADT
| Campo | Valor | Notas |
|---|---|---|
| `MSH-3` / `MSH-4` | `SISGH` / ⟨facility del hospital, p. ej. `ARP03`⟩ | `MSH-3` = nombre de la aplicación origen; `MSH-4` identifica al hospital (también por `.env`: `HL7_SENDING_APP`, `HL7_SENDING_FACILITY`) |
| `MSH-5` / `MSH-6` | ⟨`ESTENSARADIO` / `SUITESTENSA`⟩ | Lo que acepta el filtro de **su** Mirth (la especificación general indica `SUITESTENSA` en ambos) |
| `MSH-11` | `P` (producción) / `T` (prueba) | Por defecto `P` |
| `MSH-18` | `UTF-8` | |
| `PV1-2` | `O` | Ambulatorio (`I` internado, `E` urgencia) |
| `PID-3` | `{00100020}^^^PK~{00100020}^DU^^CF` | 🔶 Ver riesgo del `PK` (sección 1.1) |
| `PID-5` | `{00100010:apellido}^^{00100010:nombres}^` | Apellido en el componente 1, **nombres en el 3** |

### 6.2 Pestaña ORM
| Campo | Valor | Notas |
|---|---|---|
| `MSH-3`, `MSH-4`, `MSH-5`, `MSH-6`, `MSH-18` | igual que el ADT | |
| `PID-3` y `PID-5` | igual que el ADT | **No** pegar `PID-3` en `PID-5` |
| `PV1-2` | `O` | |
| `PV1-3` | ⟨código de procedencia, p. ej. `INT`⟩ | Ubicación de origen del paciente |
| `ORC-1` | `SN` | Admisión directa (aparece en la lista del técnico). Alternativa: `NW` + `ORC-5`=`SC` (orden agendada) |
| `ORC-2`, `ORC-4`, `OBR-2` | `{00080050}^SISGH` | Nº de orden + entidad que lo genera (`ORC-4` = `ORC-2`) |
| `ORC-7` | `1^^^{cita}^^1` | Fecha/hora de la cita en el componente 4 |
| `ORC-9` | `{ahora}` | |
| `ORC-12` | `^SIN DERIVADOR` | Médico solicitante |
| `ORC-17` | `⟨INT⟩^integracion` | **Procedencia**: el componente 1 es el código |
| `OBR-4` | `{codigo_estudio}^{descripcion_estudio}` | Código de examen (`ExternalCode` del RIS) |
| `OBR-18` | `{unidad_negocio}` | Unidad de negocio (centro de costo) |
| `OBR-21` | `{codigo_equipo}` | Equipo (`ExternalCode` del equipo) |
| `OBR-27` | `1^^^{cita}^^1` | Fecha/hora de la cita |

En la pestaña de **mapeos** del ORM: quitar los destinos `OBR-3` y `OBR-24`. **Vaciar** (no usar) `OBR-7` y `OBR-25`.
Un valor fijo **no puede vaciar** un campo ya mapeado: para dejarlo vacío hay que quitar el destino.

### 6.3 Marcadores disponibles
`{00100020}` (cualquier tag DICOM de 8 dígitos) · `{00100010:apellido}` / `{00100010:nombres}` · `{ahora}` · `{cita}` · `{codigo_estudio}` / `{descripcion_estudio}` ·
`{codigo_equipo}` / `{descripcion_equipo}` / `{unidad_negocio}`. Los valores fijos son **HL7 literal** (`^`, `~` y `&` se respetan); los datos que se insertan con marcadores se escapan.

### 6.4 Ejemplo de mensaje esperado (ficticio)
```
MSH|^~\&|SISGH|<facility>|<recep-app>|<recep-fac>|20261023191904||ORM^O01|EE70277880|P|2.5||||||UTF-8
PID|1||46561380^^^PK~46561380^DU^^CF||CARRASCO^^TANIA^||20050711|F
PV1|1|O|INT
ORC|SN|1004832^SISGH||1004832^SISGH|||1^^^20261023180000^^1||20261023191904||||||||INT^integracion
OBR|1|1004832^SISGH||523^radiografía simple de tórax|||||||||||||CD1|||RX001|||CR|||1^^^20261023180000^^1
```
Se puede ver en la consola (*Monitor → Auditoría*, o *Ver*) para cualquier orden.

---

## 7. Fase F — Plan de pruebas

Usar **pacientes y órdenes de prueba** y, si es posible, el Mirth/RIS de prueba. Criterio de aceptación: todas las pruebas en verde antes de pasar a operación.

| # | Prueba | Qué hacer | Resultado esperado |
|---|---|---|---|
| F1 | Conectividad | *Canales → Probar* en los tres canales | Los tres responden |
| F2 | ADT | Dejar entrar una orden de un paciente de prueba | En el RIS (*Monitorización de integraciones*) el ADT figura `Resultado: Yes`; el paciente existe con nombre, nacimiento y sexo correctos |
| F3 | Caracteres | Orden de un paciente con **ñ y tilde** | El apellido se ve bien en el RIS (no `Ã'`) |
| F4 | ORM por modalidad | Una orden de **cada modalidad** que se integre | Aparece en *Ejecución* del RIS con el estudio, la hora de la cita y el **equipo** correcto |
| F5 | Paciente incompleto | Orden sin nombre de pila | Queda retenida con el motivo; se corrige en *Auditoría → Datos del paciente* y **Guardar y reenviar** funciona |
| F6 | Estudio sin equivalencia | Orden de un estudio no cargado | El **ADT sale** y el ORM queda retenido (`Estudio sin codigo de equivalencia`); al cargarlo, los reintentos lo envían |
| F7 | Modalidad sin equipo | Orden de una modalidad sin equipo | ORM retenido (`Sin equipo configurado...`) |
| F8 | Reenvío | **Reenviar** una orden ya aceptada | 🔶 Ver cómo reacciona el RIS a un ORM repetido (con mismo `ORC-2`) antes de usarlo en operación |
| F9 | Reinicio | Reiniciar los servicios con una orden en reintento | La orden se retoma sin duplicarse |
| F10 | Respaldo | `installer\backup_db.ps1` y restaurar en una base de prueba | El dump se crea y se restaura |

Consultas útiles durante las pruebas: sección 8.

---

## 8. Operación diaria y mantenimiento

**Rutina diaria (2 minutos):** *Monitor* → tarjetas de **Errores**; en cada orden con error, *Auditoría* muestra por mensaje (`ADT ✓ / ORM ✕`) el estado y el motivo exacto.

| Situación | Qué hacer |
|---|---|
| Orden con error permanente | Corregir la causa (ver catálogo de errores, sección 9) y **Reprocesar** (solo los mensajes en error) |
| Quiero volver a mandar una orden ya aceptada | **Reenviar** (confirma antes; usa `MSH-10` nuevo) |
| Un mensaje quedó "pendiente" para siempre | Pasados 10 minutos sin actividad se considera atascado y se puede **Reenviar** |
| Datos del paciente incompletos o mal separados (apellido compuesto) | *Auditoría → Datos del paciente → Corregir* |

**Reinicio de servicios** (solo si cambia `.env` o se instala una versión): detener `Ingesta`, `Worker`, `API`; iniciar `API`, `Worker`, `Ingesta`.

**Respaldo:** `powershell -File "C:\Program Files\MotorDICOM\installer\backup_db.ps1" -Programar` (tarea diaria 02:00, conserva 14 días). 🔶 Escrito pero no probado en Windows en el primer hospital.
Guardar aparte `C:\ProgramData\MotorDICOM\.env` y `.superpw`.

**Logs:** `C:\ProgramData\MotorDICOM\logs\` (rotados a 10 MB; no abrir enteros, usar `Get-Content <archivo> -Tail 40`). El detalle de `pynetdicom` está apagado porque contiene datos de pacientes.

**Consultas SQL** (`psql`: `"C:\Program Files\MotorDICOM\pgsql\bin\psql.exe" -h localhost -p 5433 -U postgres -d motor_dicom_hl7`; la contraseña está en `.superpw`):
```sql
select estado, count(*) from registro_trazabilidad group by 1;
select accession_number, payload_hl7->'envios'->'orm'->>'ultimo_error' as error_orm
from registro_trazabilidad where estado like 'ERROR%' order by created_at desc limit 20;
select payload_dicom_raw->>'00321060' as estudio, count(*) from registro_trazabilidad group by 1 order by 2 desc;
```

**Actualizar a una versión nueva:** `git checkout main && git pull` → `build.bat <version>` (sin `/nofront` si cambió el frontend) → instalar encima como administrador. Las tablas y columnas nuevas se crean solas.

---

## 9. Catálogo de errores (síntoma → causa → solución)

### 9.1 Instalación y construcción
| Síntoma | Causa | Solución |
|---|---|---|
| `build.bat` no se reconoce | Estás en una rama o carpeta sin el archivo | `git checkout main && git pull`, y ejecutar desde la carpeta del repositorio |
| `Faltan binarios en vendor\` | La carpeta `vendor\` no está en el repositorio | Descargar PostgreSQL portable, `nssm.exe` y `vc_redist.x64.exe` (sección 4.1) |
| `No se encontro Inno Setup 6` | Instalado solo para el usuario | Se detecta en `%LOCALAPPDATA%\Programs\Inno Setup 6`; si no, instalarlo |
| `git pull`: "local changes ... static/" | Archivos de `static\` modificados por compilaciones anteriores | `git checkout -- static` y luego `git pull` |
| `Falta static\index.html` | Compilaste con `/nofront` sin haber generado `static\` | Compilar sin `/nofront` |
| `npm run build` falla | Código del frontend con un error de sintaxis | Revisar `build.log` |
| Instalador: `DeleteFile falló; código 5` | Servicios que mantenían abierto `MotorDICOM.exe` | Versión actual del instalador los detiene solo; si ocurre, `net stop` de los 4 servicios |
| Login: `password cannot be longer than 72 bytes` | `passlib` incompatible con `bcrypt` 5 | Ya fijado (`bcrypt<5`); recompilar con `/deps` |
| Logs de varios GB | `pynetdicom` en INFO, sin rotación | Ya corregido; borrar los logs viejos (contienen datos de pacientes) |

### 9.2 Respuestas de Mirth y del RIS (visibles en *Auditoría* como `ACK negativo AE ...`)
| Síntoma | Causa | Solución |
|---|---|---|
| Mirth: mensaje `FILTERED`; `IP not valid!` | `MSH-3/4/5/6` no coinciden con lo que acepta el filtro (p. ej. receptor invertido) | Ajustar valores fijos `MSH-5/6` (y `MSH-3/4`) a los del filtro de ese Mirth |
| `C01 - Missing Patient Key External` | `PID-3` sin la repetición con autoridad `PK` | `PID-3` = `{00100020}^^^PK~{00100020}^DU^^CF` |
| `C01 - Missing Patient Given Name` | Nombre sin separar en componentes | `PID-5` = `{00100010:apellido}^^{00100010:nombres}^` |
| Apellido = nº de documento, sin nombre | La plantilla de `PID-3` quedó en `PID-5` (pestaña ORM) | Corregir `PID-5` |
| `Exam Code N not encoded` | Examen inexistente, **o existente con `ExternalCode` vacío/0** (colisión de códigos) | Ver Fase E4: cruzar con el catálogo y dar de alta con códigos libres |
| `PlacerGroupNumber NULL` / `...Issuer NULL` | `ORC-4` sin cargar | `ORC-4` = `{00080050}^SISGH` |
| `Exam Date NULL` | Fecha de la cita ausente | `ORC-7` y `OBR-27` = `1^^^{cita}^^1` (y `ORC-9` = `{ahora}`) |
| `Provenance NULL` | `ORC-17` vacío | `ORC-17` = `<código>^<texto>` |
| `Provenance Code X not encoded` | El código de `ORC-17.1` no existe en el RIS (p. ej. se envió `1^INT`) | Usar el código real de la procedencia (`INT^integracion`) o crearla (B4) |
| `Mandatory data ... IdEquipment and BusinessUnit are null` | `OBR-21` y `OBR-18` vacíos | `OBR-21` = `{codigo_equipo}`, `OBR-18` = `{unidad_negocio}` |
| `EquipmentMandatory is true but IdEquipment is null` | `OBR-21` vacío o el código no es el `ExternalCode` de un equipo | Cargar `OBR-21` y asignar el `ExternalCode` al equipo del RIS |
| `Configuration error in DB: LsBusinessUnit... is empty` | Faltan los vínculos de la unidad de negocio en el RIS | Vincular unidad ↔ equipo ↔ modalidad ↔ procedencia (B5) |
| Nombres con `Ã'`, `Ã³` | Mirth/RIS leen UTF-8 como Latin-1 | UTF-8 en los conectores de Mirth (Fase C). Pacientes ya creados: corregir en el RIS |

### 9.3 Avisos del propio motor (orden retenida o con error permanente)
| Mensaje | Qué significa | Cómo se resuelve |
|---|---|---|
| `Datos del paciente incompletos: falta el nombre de pila; ...` | Faltan apellido, nombre, nacimiento válido, sexo o documento | *Auditoría → Datos del paciente → Corregir → Guardar y reenviar* |
| `Estudio sin codigo de equivalencia: '<texto>'` | El estudio no está en *Estudios* | Cargarlo (Fase E4) y **Reprocesar** |
| `Sin equipo configurado para la modalidad '<X>'` | La modalidad no tiene equipo en *Equipo por modalidad* | Configurarlo (E3) |
| `Sin unidad de negocio configurada para la modalidad '<X>'` | Se usa `{unidad_negocio}` y está vacía | Completarla (E3) |
| `El canal 'destino_orm' no tiene host/puerto configurado` | Canal sin completar | Completar *Canales* |
| `Fallo de conexion a host:puerto` | Mirth caído, puerto o red | Verificar conectividad; los reintentos lo envían al volver |
| `No hay mensajes para reenviar: se estan enviando o reintentando` | Ya hay una tarea viva para ese mensaje | Esperar; pasados 10 min sin actividad se libera |

---

## 10. Lecciones aprendidas del primer despliegue

1. **Cruzar siempre con el catálogo del RIS antes de dar de alta exámenes.** Una colisión de códigos no da error al cargar: el examen simplemente no se crea.
2. **El RIS identifica por `ExternalCode`**, no por `Code` ni por ID. Vale para exámenes y equipos.
3. **El equipo y la unidad de negocio van en `OBR-21` y `OBR-18`**, no en `PV1-3` (que es la ubicación de origen del paciente). Se perdió tiempo por suponerlo de un ejemplo.
4. **Pedir la especificación del proveedor desde el principio.** Resolvió en una hora lo que se estaba averiguando por prueba y error.
5. **Los errores del RIS son explícitos**: cada uno nombra el campo que falta. Se avanza más rápido enviando una orden y leyendo el error que adivinando.
6. **Las dos pestañas (ADT y ORM) son independientes.** Copiar un valor en la equivocada produjo datos incorrectos en el RIS.
7. **Verificar la codificación con un paciente con ñ antes de operar.** Los pacientes creados con el nombre corrupto no se corrigen solos.
8. **La descripción DICOM llega cortada a 64 caracteres.** Un estudio omitido por el truncado pasa desapercibido.
9. **Un valor fijo no puede vaciar un campo mapeado.** Hay que quitar el destino del mapeo.
10. **Probar sobre un RIS de producción es delicado**: los pacientes y órdenes de prueba son datos reales. Usar el ambiente de prueba siempre que exista.

---

## 11. Checklist de puesta en operación

- [ ] Hoja de parámetros completa y revisada por los cuatro roles.
- [ ] RIS: exámenes, equipos, unidad de negocio, procedencia y **vínculos** configurados y verificados con un `exams.csv`/`equipments.csv` nuevo.
- [ ] Mirth: canales de ADT y ORM, codificación **UTF-8**, filtros aceptando los valores del hospital.
- [ ] Motor instalado desde `main`; los 4 servicios en ejecución; **contraseña de `admin` cambiada**.
- [ ] Canales, valores fijos (ADT y ORM), equipos y equivalencias cargados; la lista **Sin código** vacía.
- [ ] Plan de pruebas F1–F10 en verde (F8 revisado con el administrador del RIS).
- [ ] **Datos de prueba eliminados** del RIS (pacientes y órdenes) y del motor si corresponde.
- [ ] `MSH-11 = P` y `MSH-3` de producción (si el ambiente de prueba usaba `T` / `TEST_SISGH`).
- [ ] Respaldo programado y restauración probada; `.env` y `.superpw` guardados aparte.
- [ ] Responsable de la rutina diaria definido y alertas de disco/servicios acordadas.
- [ ] Contacto de soporte de cada rol anotado en la hoja de parámetros.

---

## 12. Mejoras sugeridas para multiplicar hospitales

El proceso funciona, pero estos puntos recortarían el esfuerzo por hospital (no implementados):

| Mejora | Qué evitaría |
|---|---|
| **Exportar/importar la configuración** (valores fijos ADT/ORM, mapeos, equipos y canales) como un archivo | Cargar a mano las dos pestañas; el error de copiar el valor en la pestaña equivocada |
| **Modo prueba/producción** (cambia `MSH-3` y `MSH-11` en un solo lugar) | Olvidarse de cambiarlos al pasar a producción |
| **Botón "enviar mensaje de prueba"** con un paciente ficticio | Probar con órdenes reales |
| **Asistente de verificación** que compruebe contra los `exams.csv`/`equipments.csv` que cada código del motor existe con `ExternalCode` | Descubrir los códigos mal cargados orden por orden |
| Separar un ORM por procedimiento y resolver el truncado a 64 caracteres | Estudios omitidos en órdenes combinadas |
| Mensaje `A08` (actualizar paciente) | Corregir en el RIS pacientes ya creados con datos erróneos |
| Flujos RIS → HIS (estados `XO`/`CM`/`CA` y resultados ORU) | Que el HIS no se entere de lo realizado |

**Si el hospital usa otro RIS o HIS:** son específicos de SUITESTENSA el significado de `OBR-18`/`OBR-21`, la identificación por `ExternalCode`, las vinculaciones de la unidad de negocio
y el texto de los errores `I.REST`. El motor, la validación, los reintentos y el resto de las herramientas son independientes del RIS.
