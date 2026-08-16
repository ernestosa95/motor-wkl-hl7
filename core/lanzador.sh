#!/usr/bin/env bash
# ==============================================================================
# MotorDICOM - Script de Orquestación y Lanzamiento Local
# Entorno: Linux (Tecnoimagen SA / Integración Clínica)
# ==============================================================================

set -e

DIR_BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR_CORE="${DIR_BASE}/core"
DIR_FRONTEND="${DIR_BASE}/frontend"

# Configuración de colores para consola
VERDE="\033[0;32m"
AZUL="\033[0;34m"
AMARILLO="\033[1;33m"
ROJO="\033[0;31m"
NC="\033[0m"

echo -e "${AZUL}====================================================${NC}"
echo -e "${AZUL}         INICIALIZANDO MOTOR DE INTEGRACIÓN         ${NC}"
echo -e "${AZUL}====================================================${NC}"

# 1. Validación de Entorno Virtual Python
if [ -d "${DIR_BASE}/venv" ]; then
    source "${DIR_BASE}/venv/bin/activate"
elif [ -d "${DIR_BASE}/.venv" ]; then
    source "${DIR_BASE}/.venv/bin/activate"
else
    echo -e "${AMARILLO}[AVISO] No se detectó venv local. Usando intérprete global.${NC}"
fi

# 2. Control de Migraciones de Base de Datos (PostgreSQL)
echo -e "\n${VERDE}[1/5] Verificando esquema en PostgreSQL...${NC}"
if [ -f "${DIR_CORE}/alembic.ini" ]; then
    (cd "${DIR_CORE}" && alembic upgrade head)
    echo -e "${VERDE}✔ Esquema y columnas JSONB sincronizados correctamente.[cite: 2]${NC}"
fi

# 3. Función de Limpieza de Procesos al Salir (SIGINT / SIGTERM)
PIDS=()
cleanup() {
    echo -e "\n\n${AMARILLO}[SHUTDOWN] Deteniendo todos los servicios del motor...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    
    # Liberar puertos por seguridad
    fuser -k 8000/tcp 2>/dev/null || true
    fuser -k 5000/tcp 2>/dev/null || true
    
    echo -e "${VERDE}✔ Servicios detenidos y puertos liberados con éxito.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 4. Lanzamiento de Mocks Clínicos (DICOM SCP y MLLP TCP)
echo -e "\n${VERDE}[2/5] Levantando servicios de pruebas (Mocks)...${NC}"
if [ -f "${DIR_CORE}/mock_scp.py" ]; then
    python3 "${DIR_CORE}/mock_scp.py" &
    PIDS+=($!)
    echo -e "  ➜ Mock DICOM C-FIND SCP activo.[cite: 2]"
fi

if [ -f "${DIR_CORE}/mock_mllp.py" ]; then
    python3 "${DIR_CORE}/mock_mllp.py" &
    PIDS+=($!)
    echo -e "  ➜ Mock Receptor HL7 (MLLP/TCP Puerto 5000) activo.[cite: 2]"
fi

# 5. Worker Asíncrono de Trazabilidad y Transformación (Huey / Broker)
echo -e "\n${VERDE}[3/5] Iniciando Worker Asíncrono de Procesamiento...${NC}"
if [ -f "${DIR_CORE}/broker.py" ]; then
    (cd "${DIR_CORE}" && huey_consumer.py broker.huey -w 2 -k thread) &
    PIDS+=($!)
    echo -e "  ➜ Worker Huey iniciado para consumo de colas y reintentos.[cite: 2]"
fi

# 6. API Backend REST (FastAPI / Uvicorn)
echo -e "\n${VERDE}[4/5] Iniciando API REST de Trazabilidad y Configuración...${NC}"
(cd "${DIR_CORE}" && uvicorn api:app --host 0.0.0.0 --port 8000 --reload) &
PIDS+=($!)
echo -e "  ➜ API disponible en: http://localhost:8000 (Health: /api/v1/health/channels)[cite: 2]"

# 7. Frontend de Administración (React / Vite)
if [ -d "${DIR_FRONTEND}" ] && [ -f "${DIR_FRONTEND}/package.json" ]; then
    echo -e "\n${VERDE}[5/5] Levantando Frontend Web de Administración...${NC}"
    (cd "${DIR_FRONTEND}" && npm run dev) &
    PIDS+=($!)
    echo -e "  ➜ Consola web disponible en: http://localhost:5173"
fi

echo -e "\n${AZUL}====================================================${NC}"
echo -e "${AZUL}      SISTEMA EN EJECUCIÓN - Presione Ctrl+C para salir     ${NC}"
echo -e "${AZUL}====================================================${NC}\n"

# Mantener script en espera activa
wait