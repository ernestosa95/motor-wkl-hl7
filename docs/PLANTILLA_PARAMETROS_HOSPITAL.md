# Hoja de parámetros por hospital — integración SUITESTENSA

> **Cómo usarla:** copiar este archivo como `PARAMETROS_<hospital>.md`, completar la columna **Valor** y revisarla con los cuatro roles
> antes de instalar. La columna **Caso de referencia** muestra lo que se usó en el primer hospital (sitio `ARP03`), como ejemplo.
> **No guardar contraseñas ni datos de pacientes en este archivo.** Guía completa: [GUIA_DESPLIEGUE_HOSPITAL.md](GUIA_DESPLIEGUE_HOSPITAL.md).

| Hospital | |
|---|---|
| Nombre / código | |
| Fecha de relevamiento | |
| Ambiente | ☐ prueba  ☐ producción (☐ producción todavía sin uso) |

## 1. Contactos

| Rol | Nombre | Teléfono / correo | Disponibilidad |
|---|---|---|---|
| Administrador del origen (worklist / HIS) | | | |
| Administrador de Mirth | | | |
| Administrador del RIS | | | |
| Instalación del motor | | | |
| Responsable de la operación diaria | | | |

## 2. Servidor del motor

| Dato | Valor | Caso de referencia |
|---|---|---|
| Sistema operativo (debe ser Windows x64) | | Windows 10 |
| Nombre / IP del servidor | | |
| Puertos entrantes necesarios | | 8000 (consola), 4242 (DICOM) |
| ¿Acceso a la consola desde otras PC? | | solo local |
| ¿Hay disco para logs y respaldos (≥ 20 GB libres)? | | |
| Ruta de respaldos (si no es la predeterminada) | | `C:\ProgramData\MotorDICOM\backups` |

## 3. Origen: worklist DICOM

| Dato | Valor | Caso de referencia |
|---|---|---|
| Host / IP | | `172.31.3.149` |
| Puerto | | `8000` |
| AET destino (del servidor del worklist) | | `CLLSPS` |
| AET propio (el que se registra para el motor) | | `MOTOR_WKL` |
| ¿El origen debe registrar el AET del motor? | | |
| Frecuencia de consulta | | 30 s (por defecto) |
| Órdenes por día (aprox.) | | |
| Modalidades que llegan | | CR, DX, CT, MR, MG |

Resultado de `tools\consultar_worklist.py` (marcar):

| Pregunta | Respuesta | Caso de referencia |
|---|---|---|
| ¿Trae código de procedimiento? | ☐ sí ☐ no | no |
| ¿Descripción cortada a 64 caracteres? ¿cuántos textos? | | sí, 162 de 522 |
| ¿Órdenes con varios estudios en un texto? | ☐ sí ☐ no | sí (13,6 % de las órdenes) |
| ¿Soporta los campos de comentarios? ¿los llena en las combinadas? | | soporta; sin confirmar |
| `PatientID` es: | ☐ DNI ☐ ID interno del HIS ☐ otro: | DNI |
| ¿Hay otro campo con el ID interno (`OtherPatientIDs`, emisor)? | | no revisado |
| Formato del nombre | ☐ `APELLIDO^NOMBRE` ☐ `APELLIDO NOMBRE` ☐ otro: | `APELLIDO NOMBRE` |
| ¿Apellidos compuestos frecuentes? | | sí; se corrigen a mano |

## 4. Mirth

| Dato | Valor | Caso de referencia |
|---|---|---|
| Host / IP | | `172.31.3.150` |
| Puerto del canal **ADT** | | `5556` |
| Puerto del canal **ORM** | | confirmar (misma dirección) |
| Valores que acepta el filtro: `MSH-3` (aplicación emisora) | | `SISGH` |
| `MSH-4` (establecimiento emisor) | | `ARP03` |
| `MSH-5` (aplicación receptora) | | `ESTENSARADIO` |
| `MSH-6` (establecimiento receptor) | | `SUITESTENSA` |
| Codificación de los conectores | ☐ UTF-8 verificado | UTF-8 (verificado con una ñ) |
| ¿Hay Mirth de prueba? Host y puertos | | |
| `MSH-3` / `MSH-11` en prueba | | `TEST_SISGH` / `T` (según la especificación) |

## 5. RIS (SUITESTENSA)

| Dato | Valor | Caso de referencia |
|---|---|---|
| URL de la consola del RIS | | |
| Se recibió `exams.csv` (catálogo de exámenes) | ☐ | 1000 exámenes |
| Se recibió `equipments.csv` | ☐ | 13 equipos |
| Se recibió la especificación del proveedor | ☐ | `Relevamiento_integracion.xlsx` |
| **Unidad de negocio** (código para `OBR-18`) | | `CD1` |
| **Procedencia** de integración (código para `ORC-17.1`, `PV1-3`) | | `INT` |
| Nombre de la entidad que genera el nº de orden (`ORC-2.2`) | | `SISGH` |
| Rango de **códigos de examen libres** para el motor | | `523–836` (el RIS tenía códigos hasta `5008`) |
| ¿Se verificó que `Code` y `ExternalCode` quedaron iguales tras la carga? | ☐ | sí, en los 208 cargados |

### Equipos por modalidad

Un equipo genérico por modalidad que se integre. `Código` = **`ExternalCode`** del equipo en el RIS (es lo que enviará el motor en `OBR-21`).

| Modalidad del RIS | Equipo en el RIS | Código (`ExternalCode`) | Unidad de negocio | ¿Vinculado a la unidad y a la procedencia? | Caso de referencia |
|---|---|---|---|---|---|
| RADIOLOGIA | | | | ☐ | `RX FIJO TECNO` · `RX001` |
| RADIOGRAFIA CONTRASTADA | | | | ☐ | `SERIOGRAFO DE TECNO` (sin código) |
| TOMOGRAFIA | | | | ☐ | `TOMOGRAFIA` (sin código) |
| RESONANCIA MAGNETICA | | | | ☐ | `MR` · `RMN001` |
| MAMOGRAFIA | | | | ☐ | `MAMOGRAFO` (sin código) |
| ECOGRAFIA | | | | ☐ | `ECO MINDRAY` (sin código) |
| DENSITOMETRIA OSEA | | | | ☐ | no existe equipo |
| MEDICINA NUCLEAR | | | | ☐ | no existe equipo |

Las modalidades sin equipo **retienen el ORM**: hay que decidir si se integran o no.

## 6. Decisiones del hospital

| Decisión | Opciones | Valor elegido | Caso de referencia |
|---|---|---|---|
| `ORC-1` | `SN` (admisión directa) / `NW`+`ORC-5`=`SC` (orden agendada) | | `SN` |
| Clase de paciente `PV1-2` | `O` / `I` / `E` | | `O` |
| `PK` del paciente | ID interno del HIS / DNI | | DNI (riesgo de duplicados aceptado) |
| ORM espera al ADT | sí / no | | no (independientes) |
| Órdenes con varios estudios | examen combinado / un ORM por estudio | | examen combinado |
| Textos cortados | investigar / retener / enviar igual | | investigar con el script |
| Datos incompletos del paciente | retener y avisar / relleno / no validar | | retener y avisar |
| Apellidos compuestos | primera palabra = apellido / otra regla | | primera palabra |
| Retención de respaldos | días | | 14 |

## 7. Valores fijos a cargar (completar con los parámetros de arriba)

**Pestaña ADT**

| Campo | Valor |
|---|---|
| `MSH-3` / `MSH-4` | ⟨sección 4⟩ |
| `MSH-5` / `MSH-6` | ⟨sección 4⟩ |
| `MSH-18` | `UTF-8` |
| `PV1-2` | ⟨decisión⟩ |
| `PID-3` | `{00100020}^^^PK~{00100020}^DU^^CF` |
| `PID-5` | `{00100010:apellido}^^{00100010:nombres}^` |

**Pestaña ORM:** los de la ADT más `PV1-3` = ⟨procedencia⟩, `ORC-1` = ⟨decisión⟩, `ORC-2`/`ORC-4`/`OBR-2` = `{00080050}^⟨entidad⟩`, `ORC-7` y `OBR-27` = `1^^^{cita}^^1`,
`ORC-9` = `{ahora}`, `ORC-12` = `^SIN DERIVADOR`, `ORC-17` = `⟨procedencia⟩^integracion`, `OBR-4` = `{codigo_estudio}^{descripcion_estudio}`,
`OBR-18` = `{unidad_negocio}`, `OBR-21` = `{codigo_equipo}`. Quitar de los mapeos del ORM los destinos `OBR-3` y `OBR-24`.

## 8. Registro de la puesta en marcha

| Hito | Fecha | Responsable | Observaciones |
|---|---|---|---|
| Relevamiento completo | | | |
| RIS configurado (exámenes, equipos, unidad, procedencia, vínculos) | | | |
| Mirth configurado y probado | | | |
| Motor instalado | | | |
| Configuración del motor cargada | | | |
| Plan de pruebas F1–F10 aprobado | | | |
| Datos de prueba eliminados | | | |
| Respaldo programado y restauración probada | | | |
| Puesta en operación | | | |

## 9. Incidencias y particularidades del hospital

*(Anotar aquí lo que no esté previsto en la guía: valores distintos, errores nuevos, decisiones tomadas y por quién.)*
