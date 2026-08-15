# Documentación del Proyecto: Motor de Integración DICOM-HL7

## 1. Descripción General del Proyecto
Diseño de solución de integración clínica inspirada en Mirth Connect, basada 100% en tecnologías open source detallada en el documento "Requerimientos_Motor_Integracion.pdf"[cite: 1]. El sistema ingesta órdenes desde una Worklist DICOM, las transforma en mensajes HL7 v2.5 (ADT^A01/A04 y ORM^O01) garantizando la trazabilidad total del dato[cite: 1]. 

## 2. Trabajo Realizado y Estructura Core
Hasta el momento, hemos consolidado la arquitectura base separando la captura, transformación y comunicación para asegurar escalabilidad y resiliencia[cite: 1]:

*   **Base de Datos (PostgreSQL):** Se modelaron las tablas y se aplicaron migraciones (Alembic). El esquema almacena el estado histórico, auditorías y payloads crudos (DICOM/HL7) en columnas JSONB[cite: 1].
*   **Ingesta DICOM:** Se desarrolló la interrogación a la Modality Worklist (C-FIND SCU)[cite: 1]. Se implementó la generación de un Correlation ID (UUID) en el momento de la captura de la orden, el cual acompañará al dato en todo su ciclo de vida[cite: 1]. El registro crudo se guarda con estado INGRESADO[cite: 1].
*   **Encolamiento (Message Broker):** Se configuró Huey con SQLite, garantizando compatibilidad nativa tanto en entornos Linux como Windows, sin necesidad obligatoria de Docker[cite: 1].
*   **Motor de Transformación:** Se programó el Mapper con un enfoque híbrido utilizando un motor Jinja2 para cruces estándar de tags DICOM a HL7[cite: 1]. Se mapearon con precisión los segmentos PID y OBR, logrando la transición del registro al estado TRANSFORMADO[cite: 1].
*   **Módulo de Emisión:** Se programó el envío del payload vía socket TCP/IP (protocolo MLLP)[cite: 1]. El script incluye la política de reintentos basada en estándares (3 intentos con decaimiento temporal)[cite: 1] y el manejo del estado ante falla definitiva (ERROR_PERMANENTE)[cite: 1].

## 3. Pruebas Ejecutadas (Testing Local)
El ecosistema fue testeado de manera modular para garantizar la seguridad de los datos:

*   **Prueba de Persistencia:** Inserción exitosa verificada en la base de datos PostgreSQL local.
*   **Prueba de Red DICOM:** Creación y ejecución de un servidor *Mock SCP* (puerto 4242) para validar la captura de los tags requeridos sin requerir un PACS completo.
*   **Prueba Asíncrona:** Ejecución del worker `huey_consumer`, procesando la transformación a HL7 en memoria en 0.039 segundos sin bloqueos del hilo principal.

## 4. Próximos Pasos
*   **Validación de Comunicación MLLP:** Ejecutar el *Mock HIS/RIS* local (puerto 5000) para probar la recepción de ACK (Registro de respuesta síncrona del sistema destino) y el cambio a estado final: COMPLETADO o ERROR_EMISION[cite: 1].
*   **Desarrollo de API Backend:** Inicializar el Framework FastAPI/Django para la API[cite: 1], exponiendo el endpoint REST (ej. `/api/v1/health/channels`) para entregar métricas operativas[cite: 1].
*   **Desarrollo del Frontend Web (React/Vue.js):**
    *   Estructurar el estilo visual aplicando un fondo de lienzo blanco puro[cite: 1].
    *   Construir una barra lateral que abra las vistas en la misma pestaña de forma dinámica[cite: 1].
    *   Configurar la carga inicial para que muestre el Monitor en Tiempo Real de Trazabilidad por defecto[cite: 1].
    *   Implementar el uso de tarjetas colapsables para los formularios de configuración de canales[cite: 1].
    *   Integrar un componente tipo Monaco Editor dentro de las tarjetas de configuración web para la edición en caliente[cite: 1].
