# Cliente de IA: genera embeddings y redacta la respuesta final.
# La clave de OpenAI puede venir de la variable de entorno, de la base SQLite
# (tabla settings) o del encabezado X-OpenAI-Key que envía el BFF de Next.js.
import hashlib
import os
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


def generate_answer(question: str, records: list, api_key: str | None = None) -> str:
    # Si no hay movimientos, se responde con claridad y sin inventar datos.
    if not records:
        return NO_INFO_ANSWER

    # Con OpenAI, se redacta una respuesta en lenguaje natural usando los movimientos recuperados.
    client = _client_for(api_key)
    if client is not None:
        try:
            context = "\n".join(f"[ID: {record.id}] {record.text}" for record in records)
            system_prompt = (
                "Eres FinZen, un asistente de finanzas personales estricto y preciso. "
                "Responde ÚNICAMENTE con la información del CONTEXTO. "
                "Si el contexto no alcanza para responder con certeza, responde exactamente: "
                f'"{NO_INFO_ANSWER}" '
                "Nunca inventes montos, fechas, categorías ni comercios. "
                "Cita los movimientos que uses con su ID entre corchetes, por ejemplo [ID: 45]."
            )
            user_prompt = f"CONTEXTO:\n{context}\n\nPREGUNTA: {question}"
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
        parts.append(NO_INFO_ANSWER)

    parts.append("(Respuesta generada en modo local, sin OpenAI, usando tus propios registros.)")
    return " ".join(parts)
