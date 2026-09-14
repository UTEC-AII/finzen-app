# Cliente de IA: genera embeddings y redacta la respuesta final.
# La clave de OpenAI puede venir de la variable de entorno, de la base SQLite
# (tabla settings) o del encabezado X-OpenAI-Key que envía el BFF de Next.js.
import calendar
import hashlib
import json
import os
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "3072"))
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
LOCAL_MODEL_NAME = "local-hash"

# Mensaje estándar cuando no hay información suficiente (guardrail anti-alucinación).
NO_INFO_ANSWER = (
    "No dispongo de suficiente información en tus registros para responder a esta pregunta."
)


def _client_for(api_key: str | None) -> OpenAI | None:
    # Prioriza la clave recibida; si no hay, usa la de entorno.
    key = api_key or OPENAI_API_KEY
    return OpenAI(api_key=key) if key else None


def is_openai_enabled(api_key: str | None = None) -> bool:
    return _client_for(api_key) is not None


def current_model_name(api_key: str | None = None) -> str:
    # Nombre del modelo de embeddings que se usaría en este momento.
    return EMBEDDING_MODEL if _client_for(api_key) is not None else LOCAL_MODEL_NAME


def _local_embedding(text: str) -> list[float]:
    # Modo local: vector de bolsa de palabras con hashing, determinista y sin internet.
    vector = np.zeros(EMBEDDING_DIM, dtype=float)
    for token in text.lower().split():
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        vector[int(digest, 16) % EMBEDDING_DIM] += 1.0
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()


def _embed_batch(
    texts: list[str], api_key: str | None = None
) -> tuple[list[list[float]], str]:
    # Devuelve (vectores, modelo realmente usado). Si OpenAI falla, cae a local.
    client = _client_for(api_key)
    if client is not None:
        try:
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            return [item.embedding for item in response.data], EMBEDDING_MODEL
        except Exception:
            pass
    return [_local_embedding(text) for text in texts], LOCAL_MODEL_NAME


def embed_text(text: str, api_key: str | None = None) -> list[float]:
    # Vectoriza un solo texto (usado al procesar la consulta del usuario).
    vectors, _ = _embed_batch([text], api_key)
    return vectors[0]


def embed_with_model(
    text: str, api_key: str | None = None
) -> tuple[list[float], str]:
    # Vectoriza un texto y devuelve también el modelo usado.
    vectors, model = _embed_batch([text], api_key)
    return vectors[0], model


def embed_many_with_model(
    texts: list[str], api_key: str | None = None
) -> tuple[list[list[float]], str]:
    # Vectoriza varios textos (lote) y devuelve el modelo usado.
    return _embed_batch(texts, api_key)


def _heuristic_filters(
    question: str, categories: list[str], record_types: list[str]
) -> dict:
    # Modo local (sin OpenAI): detecta filtros por palabras clave en la pregunta.
    q = question.lower()
    filters: dict = {}

    for category in categories:
        if category.lower() in q:
            filters["category"] = category
            break

    if any(word in q for word in ["ingreso", "sueldo", "recibí", "recibi", "gané", "gane"]):
        filters["record_type"] = "income"
    elif any(word in q for word in ["gasto", "gasté", "gaste", "pagué", "pague"]):
        filters["record_type"] = "expense"

    today = date.today()
    if "este mes" in q or "mes actual" in q:
        filters["start_date"] = today.replace(day=1).isoformat()
        filters["end_date"] = today.isoformat()
    elif "mes pasado" in q or "mes anterior" in q:
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        filters["start_date"] = last_prev_month.replace(day=1).isoformat()
        filters["end_date"] = last_prev_month.isoformat()
    elif "este año" in q or "este ano" in q:
        filters["start_date"] = date(today.year, 1, 1).isoformat()
        filters["end_date"] = today.isoformat()

    return filters


def _normalize_date(value, end: bool = False) -> str | None:
    # Normaliza fechas sueltas ("2026", "2026-09", "2026-09-14", ISO) a YYYY-MM-DD.
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()[:10]
    try:
        if len(raw) == 4:
            return f"{raw}-12-31" if end else f"{raw}-01-01"
        if len(raw) == 7:
            year, month = int(raw[:4]), int(raw[5:7])
            if end:
                return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
            return f"{year:04d}-{month:02d}-01"
        return date.fromisoformat(raw).isoformat()
    except Exception:
        return None


def extract_filters(
    question: str,
    categories: list[str],
    record_types: list[str],
    api_key: str | None = None,
) -> dict:
    # Extrae filtros estructurados (categoría, tipo, fechas) de la pregunta.
    # La heurística detecta de forma determinista "este mes", categorías, etc.;
    # el LLM (si hay clave) rellena lo que la heurística no haya encontrado.
    filters = _heuristic_filters(question, categories, record_types)

    client = _client_for(api_key)
    if client is not None:
        try:
            system_prompt = (
                "Extrae filtros de una pregunta financiera. Devuelve SOLO un JSON con las "
                "claves: category (una de la lista o null), record_type ('income', 'expense' "
                "o null), start_date (YYYY-MM-DD o null) y end_date (YYYY-MM-DD o null). "
                f"Categorías posibles: {', '.join(categories) or 'ninguna'}. "
                f"Hoy es {date.today().isoformat()}."
            )
            response = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            for key, value in data.items():
                if value and key not in filters:
                    filters[key] = value
        except Exception:
            pass

    # Normaliza las fechas para que la comparación sea consistente.
    for key, is_end in (("start_date", False), ("end_date", True)):
        if filters.get(key):
            normalized = _normalize_date(filters[key], end=is_end)
            if normalized:
                filters[key] = normalized
            else:
                filters.pop(key, None)

    return filters


def generate_answer(question: str, records: list, api_key: str | None = None) -> str:
    # Si no hay movimientos, se responde con claridad y sin inventar datos.
    if not records:
        return NO_INFO_ANSWER

    # Con OpenAI, se redacta una respuesta en lenguaje natural usando los movimientos recuperados.
    client = _client_for(api_key)
    if client is not None:
        try:
            context = "\n".join(f"- {record.text}" for record in records)
            system_prompt = (
                "Eres FinZen, un asistente de finanzas personales claro, cercano y preciso. "
                "Responde en español, de forma breve y directa, usando la información del CONTEXTO. "
                "El CONTEXTO ya contiene los movimientos del usuario relevantes para la pregunta: "
                "úsalos y respóndela con seguridad. Si el usuario pide un total, suma los movimientos "
                "relevantes y muestra el resultado con su moneda. "
                "Solo si el CONTEXTO no tiene ningún movimiento, responde exactamente: "
                f'"{NO_INFO_ANSWER}" '
                "No inventes montos, fechas, categorías ni comercios."
            )
            user_prompt = f"Movimientos del usuario (CONTEXTO):\n{context}\n\nPREGUNTA: {question}"
            response = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception:
            # Si OpenAI falla, se responde con el resumen local.
            return _build_local_answer(records)
    return _build_local_answer(records)


def _build_local_answer(records: list) -> str:
    # Resume los movimientos recuperados: mayor categoría de gasto y total de ingresos.
    expenses = [record for record in records if record.record_type == "expense"]
    incomes = [record for record in records if record.record_type == "income"]

    parts = []
    if expenses:
        # Se suman montos como Decimal para no perder precisión financiera.
        totals: dict[str, Decimal] = {}
        for record in expenses:
            totals[record.category] = totals.get(record.category, Decimal("0")) + record.amount
        top_category = max(totals, key=totals.get)
        parts.append(
            f"Según tus movimientos más relacionados, tu mayor gasto está en "
            f"{top_category} con {totals[top_category]:.2f}."
        )
    if incomes:
        total_income = sum((record.amount for record in incomes), Decimal("0"))
        parts.append(f"También se consideran ingresos por un total de {total_income:.2f}.")
    if not parts:
        return NO_INFO_ANSWER

    return " ".join(parts)
