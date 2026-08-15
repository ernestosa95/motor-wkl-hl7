#!/bin/bash
# Lanzador maestro para MotorDICOM

echo "================================================="
echo "[*] Iniciando Servicios del MotorDICOM..."
echo "================================================="

# 1. Iniciar el Mock MLLP (Simulador del HIS/RIS receptor)
python3 mock_mllp.py > /dev/null 2>&1 &
MOCK_PID=$!
echo "[\u2713] Mock MLLP iniciado (PID: $MOCK_PID)"

# 2. Iniciar el Worker de Huey (Transformación)
huey_consumer transformador.huey > /dev/null 2>&1 &
HUEY_PID=$!
echo "[\u2713] Motor de Transformación iniciado (PID: $HUEY_PID)"

# 3. Iniciar la API REST (FastAPI)
uvicorn api:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
API_PID=$!
echo "[\u2713] API REST iniciada (PID: $API_PID)"

echo "================================================="
echo "[*] Sistema 100% Operativo."
echo " -> Consultar métricas en: http://localhost:8000/api/v1/health/channels"
echo " -> Documentación Swagger: http://localhost:8000/docs"
echo "[!] Presiona Ctrl+C para detener todos los servicios de forma segura."
echo "================================================="

# Función para detener todo al recibir la señal de interrupción
limpiar_procesos() {
    echo ""
    echo "[!] Deteniendo servicios..."
    kill $MOCK_PID $HUEY_PID $API_PID 2>/dev/null
    echo "[\u2713] Todos los procesos finalizados correctamente."
    exit 0
}

trap limpiar_procesos SIGINT SIGTERM

# Mantener el script corriendo a la escucha
wait