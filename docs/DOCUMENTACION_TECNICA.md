# Motor de Integración DICOM → HL7
## Documentación técnica de la solución

**Producto:** MotorDICOM — Motor de integración clínica
**Organización:** Tecnoimagen SA
**Estado:** MVP funcional, validado de punta a punta
**Fecha:** Agosto 2026

---

## 1. Descripción general

MotorDICOM es un motor de integración clínica que automatiza el flujo de
información entre una **Modality Worklist DICOM** y un **sistema de información
hospitalaria (HIS/RIS)** vía **HL7 v2.5**. El motor consulta periódicamente la
worklist, captura las órdenes de estudio, las transforma en mensajes HL7
(admisión ADT y orden ORM) y las emite al sistema destino por protocolo MLLP,
manteniendo trazabilidad completa de cada orden a lo largo de su ciclo de vida.

La solución se distribuye como un **instalador único para Windows** que despliega
todos sus componentes de forma autónoma, sin dependencias externas que el usuario
deba instalar por separado.

---

## 2. Arquitectura

La solución separa captura, transformación y comunicación en componentes
independientes, orquestados como servicios de Windows.

### 2.1. Componentes

| Componente | Rol | Tecnología |
|---|---|---|
| **API + Consola web** | Backend REST y interfaz de administración | FastAPI (uvicorn) + React |
| **Worker** | Procesamiento asíncrono (transformación + emisión) | Huey |
| **Ingesta** | Consulta periódica a la Worklist DICOM (C-FIND SCU) | pynetdicom / pydicom |
| **Base de datos** | Persistencia y trazabilidad | PostgreSQL |
| **Cola de tareas** | Encolamiento de trabajos pendientes | Huey + SQLite |

Cada uno corre como un **servicio de Windows independiente**, gestionado con NSSM,
con arranque automático y dependencias declaradas (los servicios de aplicación
dependen de PostgreSQL).

### 2.2. Flujo de datos

```
┌────────────────┐   C-FIND    ┌───────────┐   encola    ┌──────────┐
│ Modality       │ ──────────► │  Ingesta  │ ──────────► │  Worker  │
│ Worklist DICOM │  (cada 30s) │  (SCU)    │             │  (Huey)  │
└────────────────┘             └─────┬─────┘             └────┬─────┘
                                     │ persiste                │ transforma
                                     ▼                         ▼
                             ┌───────────────┐         ┌──────────────┐
                             │  PostgreSQL   │         │ HL7 ADT+ORM  │
                             │ (trazabilidad)│         └──────┬───────┘
                             └───────────────┘                │ MLLP
                                                              ▼
                                                      ┌──────────────┐
                                                      │  HIS / RIS   │
                                                      │  (Mirth...)  │
                                                      └──────────────┘
```

1. **Ingesta:** consulta la worklist por C-FIND cada 30 segundos (configurable),
   filtrando por la fecha del día. Cada orden nueva recibe un **Correlation ID
   (UUID)** que la acompaña en todo su ciclo de vida.
2. **Deduplicación:** antes de procesar, se verifica por número de accession que
   la orden no haya sido ingerida previamente, evitando duplicados en cada ciclo.
3. **Persistencia:** la orden se guarda con estado `INGRESADO` y su payload DICOM
   crudo en formato JSONB.
4. **Transformación:** el worker genera los mensajes HL7 (ADT^A04 y ORM^O01) según
   el mapeo configurable, y pasa al estado `TRANSFORMADO`.
5. **Emisión:** cada mensaje se envía por MLLP a su destino (ADT y ORM tienen
   destinos independientes), con espera de ACK síncrono.
6. **Estado final:** `COMPLETADO` si el destino confirma con ACK (MSA|AA); en caso
   de fallo, `ERROR_EMISION` (transitorio) o `ERROR_PERMANENTE`, registrando el
   motivo del error.

---

## 3. Modelo de datos (PostgreSQL)

| Tabla | Contenido |
|---|---|
| `registro_trazabilidad` | Ciclo de vida de cada orden: estado, payloads DICOM/HL7 (JSONB), detalle de error, marcas de tiempo |
| `usuarios` | Cuentas de acceso a la consola (hash de contraseña, flag de cambio obligatorio) |
| `canales` | Configuración de conexiones (worklist de origen, destinos ADT y ORM) |
| `mapeos` | Reglas de mapeo DICOM → HL7 por tipo de mensaje |
| `valores_fijos` | Valores constantes por campo HL7 y tipo de mensaje |

El esquema se gestiona con **migraciones Alembic**, aplicadas automáticamente en
la instalación. Los payloads crudos (DICOM y HL7) se almacenan en columnas
**JSONB** con índices GIN para consultas eficientes.

### Estados de una orden

`INGRESADO` → `TRANSFORMADO` → `COMPLETADO`
con ramas de error: `ERROR_EMISION` (transitorio, reprocesable) y
`ERROR_PERMANENTE`.

---

## 4. Consola de administración web

Interfaz React servida por el propio backend (mismo origen, puerto 8000):

- **Monitor de trazabilidad:** listado en vivo de órdenes con su estado, métricas
  agregadas (ingresados / transformados / completados / errores), y actualización
  automática cada 3 segundos.
- **Buscadores por columna:** filtrado por accession, paciente, modalidad y estado.
- **Reprocesamiento:** botón para reintentar manualmente órdenes en estado de error.
- **Auditoría por orden:** ventana con la línea de tiempo (ingreso y último cambio),
  detalle del error si corresponde, y los mensajes HL7 generados (ADT y ORM).
- **Canales:** configuración de host/puerto/AE Title de la worklist de origen y de
  los destinos MLLP, con prueba de conectividad.
- **Mapeo:** edición de las reglas DICOM → HL7 por tipo de mensaje.

---

## 5. Seguridad

- **Autenticación por JWT:** el acceso a la consola y a todos los endpoints de la
  API requiere un token JWT (algoritmo HS256, expiración configurable, 8h por
  defecto). El secreto de firma se **genera aleatoriamente en cada instalación**.
- **Contraseñas hasheadas:** las contraseñas se almacenan con **bcrypt** (nunca en
  texto plano).
- **Cambio obligatorio en el primer acceso:** el usuario administrador inicial
  (`admin`) debe definir una contraseña nueva en su primer inicio de sesión, antes
  de poder operar el sistema.
- **Aislamiento de red:** la base de datos PostgreSQL escucha únicamente en
  `localhost` (puerto 5433), no expuesta a la red. Solo se abren en el firewall los
  puertos estrictamente necesarios (8000 web, 4242 DICOM). La emisión MLLP es
  saliente y no requiere puertos de entrada.
- **Datos en reposo:** los datos operativos (base de datos, colas, logs,
  configuración) se almacenan en `C:\ProgramData\MotorDICOM`, separados de los
  binarios de la aplicación.

---

## 6. Trazabilidad y auditoría

- **Correlation ID único (UUID)** por orden, que la identifica de forma
  inequívoca desde la captura en la worklist hasta la confirmación del destino.
- **Registro del payload crudo DICOM** tal como se recibió, para auditoría.
- **Registro de los mensajes HL7 generados** (ADT y ORM) para cada orden.
- **Registro del motivo de error** cuando una emisión falla (conexión rechazada,
  NACK, etc.), con marca de tiempo.
- **Control de reintentos:** política de reintento ante fallos transitorios, con
  posibilidad de reprocesamiento manual desde la consola.
- **Marcas de tiempo** de ingreso y de último cambio de estado por orden.

---

## 7. Empaquetado y distribución

- **Ejecutable único** generado con PyInstaller que agrupa todos los componentes;
  el comportamiento se selecciona por subcomando (`api`, `worker`, `ingesta`,
  `migrate`, `crear-admin`).
- **Frontend compilado** (React/Vite) servido como estáticos por el backend; no
  requiere Node.js en el equipo destino.
- **PostgreSQL embebido:** los binarios se incluyen en el instalador y se
  inicializa un cluster propio en la instalación, sin requerir una instalación
  previa de PostgreSQL.
- **Visual C++ Redistributable** incluido y auto-instalado (requerido por los
  binarios de PostgreSQL).
- **Instalador Inno Setup** que despliega binarios, inicializa la base, aplica
  migraciones, siembra el usuario administrador, registra los servicios de Windows
  y configura el firewall.
- **Idempotencia:** el instalador tolera reinstalaciones sobre instalaciones
  existentes conservando los datos; una instalación desde cero es una acción
  explícita (borrado manual del directorio de datos).

---

## 8. Requisitos del entorno destino

- Windows 10/11 o Windows Server 2019/2022, **64 bits**.
- Privilegios de administrador para la instalación.
- En entornos virtualizados (Proxmox/KVM), el modelo de CPU de la VM debe exponer
  el set de instrucciones del procesador físico (CPU tipo `host` o equivalente),
  requerido por los binarios de PostgreSQL.

---

## 9. Parámetros de red por defecto

| Parámetro | Valor por defecto | Configurable |
|---|---|---|
| Puerto consola web / API | 8000 | Sí (.env) |
| Puerto PostgreSQL (local) | 5433 | Sí (.env) |
| Intervalo de ingesta | 30 segundos | Sí (.env) |
| Worklist de origen (C-FIND) | Configurable en consola | Sí (consola) |
| Destinos MLLP (ADT / ORM) | Configurable en consola | Sí (consola) |

---

## 10. Mejoras futuras identificadas

- **Registro de eventos por transición:** tabla de historial que capture cada
  cambio de estado con su marca de tiempo (hoy se conserva el estado actual y las
  marcas de ingreso y último cambio).
- **Retención automática de datos:** tarea de limpieza de registros antiguos.
- **Backups automatizados** de la base de datos.
- **Firma de código** del instalador para evitar advertencias de SmartScreen.
- **Configuración del intervalo de ingesta desde la consola.**

---

*Documento generado para uso interno de Tecnoimagen SA.*
