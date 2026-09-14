# Cliente para enviar cada movimiento al microservicio de IA (vectorización).
import os

import httpx

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8004")


def vectorize_record(record: dict) -> None:
    # Envía el registro al ai-service. Si la IA falla, no se interrumpe el guardado.
    try:
        httpx.post(f"{AI_SERVICE_URL}/vectorize", json=record, timeout=5.0)
    except Exception:
        # El registro ya quedó guardado; solo queda temporalmente fuera de las consultas de IA.
        pass
