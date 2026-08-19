#!/usr/bin/env bash
# ==============================================================================
# Motor de Integración DICOM-HL7 — Lanzador completo
#
#   ./run.sh              Levanta todo (mocks + worker + SCU + API + frontend)
#   ./run.sh --setup      Instala deps, migra la DB y crea el admin, luego levanta
#   ./run.sh --no-mocks   No levanta los servidores de prueba (SCP/MLLP)
#   ./run.sh --no-frontend  No levanta el frontend (solo backend)
#
# Ejecutar SIEMPRE desde la raíz del proyecto (donde vive este archivo).
# Los módulos se importan como `core.xxx`, por eso corremos desde la raíz.
# ==============================================================================

# --- Config editable por variables de entorno ---
API_PORT="${API_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-5173}"
MOCK_SCP_PORT="${MWL_SCP_PORT:-4243}"
MOCK_MLLP_PORT="${MLLP_PORT:-2575}"
HUEY_WORKERS="${HUEY_WORKERS:-2}"

# --- Flags ---
DO_SETUP=0
RUN_MOCKS=1
RUN_FRONTEND=1
for arg in "$@"; do
  case "$arg" in
    --setup) DO_SETUP=1 ;;
    --no-mocks) RUN_MOCKS=0 ;;
    --no-frontend) RUN_FRONTEND=0 ;;
    *) echo "Flag desconocido: $arg" ;;
  esac
done

# --- Colores ---
V="\033[0;32m"; A="\033[0;34m"; Y="\033[1;33m"; R="\033[0;31m"; NC="\033[0m"

DIR_BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR_BASE"
export PYTHONPATH="$DIR_BASE"   # para que `core.xxx` resuelva desde la raíz

echo -e "${A}====================================================${NC}"
echo -e "${A}      MOTOR DE INTEGRACIÓN DICOM-HL7 — LANZADOR      ${NC}"
echo -e "${A}====================================================${NC}"

# --- 1. Entorno virtual ---
if [ -d "${DIR_BASE}/.venv" ]; then
  source "${DIR_BASE}/.venv/bin/activate"
elif [ -d "${DIR_BASE}/venv" ]; then
  source "${DIR_BASE}/venv/bin/activate"
else
  echo -e "${Y}[AVISO] No se detectó .venv/venv. Usando el intérprete global.${NC}"
fi

PY="$(command -v python3 || command -v python)"

# --- 2. Setup opcional (primera vez) ---
if [ "$DO_SETUP" -eq 1 ]; then
  echo -e "\n${V}[SETUP] Instalando dependencias...${NC}"
  "$PY" -m pip install -r "${DIR_BASE}/requirements.txt"
fi

# --- 3. Chequeo de PostgreSQL (no fatal) ---
echo -e "\n${V}[1/7] Verificando PostgreSQL...${NC}"
if command -v pg_isready >/dev/null 2>&1; then
  if pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" >/dev/null 2>&1; then
    echo -e "  ➜ PostgreSQL responde."
  else
    echo -e "${Y}  [AVISO] PostgreSQL no responde en ${DB_HOST:-localhost}:${DB_PORT:-5432}. Levantalo antes de continuar.${NC}"
  fi
else
  echo -e "${Y}  [AVISO] pg_isready no está disponible; omito el chequeo.${NC}"
fi

# --- 4. Migraciones (idempotente) ---
echo -e "\n${V}[2/7] Aplicando migraciones (alembic upgrade head)...${NC}"
if [ -f "${DIR_BASE}/core/alembic.ini" ]; then
  alembic -c "${DIR_BASE}/core/alembic.ini" upgrade head \
    && echo -e "  ➜ Esquema sincronizado." \
    || echo -e "${R}  [ERROR] Falló la migración. Revisá la conexión a la DB.${NC}"
else
  echo -e "${Y}  [AVISO] No se encontró core/alembic.ini; omito migraciones.${NC}"
fi

# --- 5. Crear admin en setup ---
if [ "$DO_SETUP" -eq 1 ]; then
  echo -e "\n${V}[SETUP] Creando/reseteando usuario admin...${NC}"
  "$PY" -m core.crear_admin || echo -e "${Y}  [AVISO] No se pudo crear el admin.${NC}"
fi

# --- 6. Limpieza al salir ---
PIDS=()
cleanup() {
  echo -e "\n\n${Y}[SHUTDOWN] Deteniendo servicios...${NC}"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  for port in "$API_PORT" "$FRONT_PORT" "$MOCK_SCP_PORT" "$MOCK_MLLP_PORT"; do
    fuser -k "${port}/tcp" 2>/dev/null || true
  done
  echo -e "${V}✔ Servicios detenidos y puertos liberados.${NC}"
  exit 0
}
trap cleanup SIGINT SIGTERM

# --- 7. Mocks de prueba ---
if [ "$RUN_MOCKS" -eq 1 ]; then
  echo -e "\n${V}[3/7] Levantando mocks de prueba...${NC}"
  "$PY" -m core.mock_scp &  PIDS+=($!)
  echo -e "  ➜ Mock DICOM C-FIND SCP (puerto ${MOCK_SCP_PORT})."
  "$PY" -m core.mock_mllp & PIDS+=($!)
  echo -e "  ➜ Mock receptor HL7/MLLP (puerto ${MOCK_MLLP_PORT})."
  sleep 1   # dar tiempo a que los mocks abran los sockets
else
  echo -e "\n${Y}[3/7] Mocks omitidos (--no-mocks).${NC}"
fi

# --- 8. Worker Huey ---
echo -e "\n${V}[4/7] Iniciando worker Huey...${NC}"
if command -v huey_consumer >/dev/null 2>&1; then
  huey_consumer core.broker.huey -w "$HUEY_WORKERS" -k thread & PIDS+=($!)
else
  "$PY" -m huey.bin.huey_consumer core.broker.huey -w "$HUEY_WORKERS" -k thread & PIDS+=($!)
fi
echo -e "  ➜ Worker consumiendo la cola (transformación + emisión)."

# --- 9. SCU C-FIND en polling ---
echo -e "\n${V}[5/7] Iniciando SCU C-FIND (polling de la Worklist)...${NC}"
"$PY" -m core.worklist_scu & PIDS+=($!)
echo -e "  ➜ Ingesta DICOM activa."

# --- 10. API FastAPI ---
echo -e "\n${V}[6/7] Iniciando API (uvicorn) en el puerto ${API_PORT}...${NC}"
uvicorn core.api:app --host 0.0.0.0 --port "$API_PORT" & PIDS+=($!)
echo -e "  ➜ API + Swagger en http://localhost:${API_PORT}/docs"

# --- 11. Frontend ---
if [ "$RUN_FRONTEND" -eq 1 ] && [ -d "${DIR_BASE}/frontend-motor" ]; then
  echo -e "\n${V}[7/7] Iniciando frontend...${NC}"
  (
    cd "${DIR_BASE}/frontend-motor"
    if [ ! -d node_modules ]; then
      echo -e "${Y}  Instalando dependencias del frontend (npm install)...${NC}"
      npm install
    fi
    npm run dev -- --host --port "$FRONT_PORT"
  ) & PIDS+=($!)
  echo -e "  ➜ Consola web en http://localhost:${FRONT_PORT}"
else
  echo -e "\n${Y}[7/7] Frontend omitido.${NC}"
fi

echo -e "\n${A}====================================================${NC}"
echo -e "${V} Todo levantado. Ctrl+C para detener todo.${NC}"
echo -e "   API:      http://localhost:${API_PORT}/docs"
[ "$RUN_FRONTEND" -eq 1 ] && echo -e "   Frontend: http://localhost:${FRONT_PORT}"
echo -e "   Login:    admin / admin123"
echo -e "${A}====================================================${NC}\n"

wait
