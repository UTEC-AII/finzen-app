#!/usr/bin/env bash
# Levanta los 4 microservicios en local (sin Docker) para pruebas de desarrollo.
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs

# Crea el entorno virtual compartido la primera vez.
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

# Instala las dependencias de los cuatro servicios.
pip install -q \
  -r user-service/requirements.txt \
  -r income-service/requirements.txt \
  -r expense-service/requirements.txt \
  -r ai-service/requirements.txt

# Levanta cada servicio en segundo plano, con su propio archivo de log y su PID.
(cd user-service    && nohup uvicorn main:app --host 0.0.0.0 --port 8001 > ../logs/user-service.log 2>&1 & echo $! > ../logs/user-service.pid)
(cd income-service  && nohup uvicorn main:app --host 0.0.0.0 --port 8002 > ../logs/income-service.log 2>&1 & echo $! > ../logs/income-service.pid)
(cd expense-service && nohup uvicorn main:app --host 0.0.0.0 --port 8003 > ../logs/expense-service.log 2>&1 & echo $! > ../logs/expense-service.pid)
(cd ai-service      && nohup uvicorn main:app --host 0.0.0.0 --port 8004 > ../logs/ai-service.log 2>&1 & echo $! > ../logs/ai-service.pid)

sleep 2
echo "Servicios levantados:"
echo "  user-service    -> http://localhost:8001/docs"
echo "  income-service  -> http://localhost:8002/docs"
echo "  expense-service -> http://localhost:8003/docs"
echo "  ai-service      -> http://localhost:8004/docs"
