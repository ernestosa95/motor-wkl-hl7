# Documentación

| Documento | Para qué sirve |
|---|---|
| [GUIA_DESPLIEGUE_HOSPITAL.md](GUIA_DESPLIEGUE_HOSPITAL.md) | **Poner en marcha la integración con SUITESTENSA en un hospital nuevo**: fases, valores base, plan de pruebas, catálogo de errores, operación y checklist de puesta en operación |
| [PLANTILLA_PARAMETROS_HOSPITAL.md](PLANTILLA_PARAMETROS_HOSPITAL.md) | Hoja para completar por hospital antes de instalar (contactos, direcciones, códigos del RIS, decisiones) |
| [INTEGRACION_SUITESTENSA.md](INTEGRACION_SUITESTENSA.md) | **Caso de referencia** (primer hospital): detalle técnico, hallazgos del RIS y de su especificación, bitácora de problemas, decisiones y pendientes |
| [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md) | Arquitectura general del motor, modelo de datos, seguridad y empaquetado |

**Herramientas** (`tools/`): `consultar_worklist.py` (inspeccionar el worklist de origen), `clasificar_modalidad_ris.py` (modalidad del RIS por estudio) y
`cruzar_catalogo_ris.py` (evitar colisiones de códigos con el catálogo del RIS). Cada una explica su uso al ejecutarla sin argumentos o en su encabezado.
