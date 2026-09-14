#!/usr/bin/env python3
"""Evaluación sencilla del RAG de FinZen.

Crea un usuario de prueba, registra movimientos conocidos, lanza un conjunto de
preguntas y mide el "retrieval recall": si los movimientos esperados aparecen
entre las fuentes que devuelve el asistente.

Uso:
    python scripts/evaluate_rag.py [BASE_URL]

BASE_URL por defecto: http://localhost (a través de Nginx en Docker).
"""
import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost"

# Movimientos de prueba (verdad de terreno).
EXPENSES = [
    {"category": "Alimentacion", "amount": "450.50", "date": "2026-09-05", "description": "Supermercado Wong"},
    {"category": "Transporte", "amount": "120.00", "date": "2026-09-06", "description": "Taxi Uber"},
    {"category": "Alimentacion", "amount": "200.00", "date": "2026-09-07", "description": "Restaurante Central"},
    {"category": "Entretenimiento", "amount": "80.00", "date": "2026-09-08", "description": "Netflix"},
    {"category": "Salud", "amount": "150.00", "date": "2026-08-20", "description": "Farmacia"},
]
INCOMES = [
    {"type": "Sueldo", "amount": "3500.50", "date": "2026-09-01", "description": "Sueldo setiembre"},
    {"type": "Freelance", "amount": "800.00", "date": "2026-09-10", "description": "Proyecto freelance"},
]

# Preguntas y las descripciones que deberían aparecer entre las fuentes.
DATASET = [
    {"question": "¿cuánto gasté en supermercado?", "expect": ["Supermercado Wong"]},
    {"question": "¿qué gastos de transporte tuve?", "expect": ["Taxi Uber"]},
    {"question": "¿cuánto recibí de sueldo?", "expect": ["Sueldo setiembre"]},
    {"question": "¿en qué gasté en entretenimiento?", "expect": ["Netflix"]},
    {"question": "¿cuánto gasté en salud?", "expect": ["Farmacia"]},
    {"question": "¿qué ingresos freelance tuve?", "expect": ["Proyecto freelance"]},
    {"question": "¿gastos en restaurantes?", "expect": ["Restaurante Central"]},
    {"question": "¿cuál fue mi sueldo?", "expect": ["Sueldo setiembre"]},
    {"question": "¿gasté en comida?", "expect": ["Supermercado Wong", "Restaurante Central"]},
    {"question": "¿pagué transporte?", "expect": ["Taxi Uber"]},
]


def request(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None


def main():
    email = f"eval{int(time.time())}@test.com"
    user = request(
        "POST",
        "/api/users/users",
        body={"name": "Eval", "email": email, "password": "secreto123", "preferred_currency": "PEN"},
    )
    login = request("POST", "/api/users/auth/login", body={"email": email, "password": "secreto123"})
    token = login["access_token"]
    user_id = user["id"]

    for expense in EXPENSES:
        request("POST", "/api/expenses/expenses", token, {"user_id": user_id, "currency": "PEN", **expense})
    for income in INCOMES:
        request("POST", "/api/incomes/incomes", token, {"user_id": user_id, "currency": "PEN", **income})

    time.sleep(2)  # Espera a la vectorización en segundo plano.

    hits = 0
    total = len(DATASET)
    print(f"Evaluación RAG de FinZen ({total} preguntas)")
    print("-" * 56)
    for item in DATASET:
        result = request("POST", "/api/ai/query", token, {"user_id": user_id, "question": item["question"]})
        source_text = " ".join(source["text"] for source in result.get("sources", []))
        found = any(expected in source_text for expected in item["expect"])
        hits += 1 if found else 0
        mark = "OK  " if found else "MISS"
        print(f"[{mark}] {item['question']}  (fuentes: {len(result.get('sources', []))})")
    print("-" * 56)
    print(f"Retrieval Recall: {hits}/{total} = {hits / total * 100:.1f}%")


if __name__ == "__main__":
    main()
