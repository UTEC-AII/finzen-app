# Cliente de IA: genera embeddings y redacta la respuesta final.
# La clave de OpenAI puede venir de la variable de entorno o del encabezado
# X-OpenAI-Key que envía el BFF de Next.js (nunca desde el navegador).
import hashlib
import os
from decimal import Decimal

import numpy as np
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "3072"))
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")


def _client_for(api_key: str | None) -> OpenAI | None:
    # Prioriza la clave recibida del BFF; si no hay, usa la de entorno.
    key = api_key or OPENAI_API_KEY
    return OpenAI(api_key=key) if key else None


def is_openai_enabled(api_key: str | None = None) -> bool:
    # Indica si se usará OpenAI o el modo local.
    return _client_for(api_key) is not None


def embed_text(text: str, api_key: str | None = None) -> list[float]:
    # Con clave, usa el modelo de embeddings de OpenAI (3072 dimensiones).
    client = _client_for(api_key)
    if client is not None:
        try:
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
            return response.data[0].embedding
        except Exception:
            # Si la clave es inválida o falla la red, se usa el modo local.
            pass

    # Modo local: vector de bolsa de palabras con hashing, determinista y sin internet.
    vector = np.zeros(EMBEDDING_DIM, dtype=float)
    for token in text.lower().split():
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        vector[int(digest, 16) % EMBEDDING_DIM] += 1.0
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()


def generate_answer(question: str, records: list, api_key: str | None = None) -> str:
    # Si no hay movimientos, se responde con claridad y sin inventar datos.
    if not records:
        return "Todavía no tienes movimientos suficientes para analizar."

    # Con OpenAI, se redacta una respuesta en lenguaje natural usando los movimientos recuperados.
    client = _client_for(api_key)
    if client is not None:
        try:
            context = "\n".join(record.text for record in records)
            system_prompt = (
                "Eres el asistente financiero de FinZen. Responde en español y basándote "
                "únicamente en los movimientos del usuario. Si no hay información "
                "suficiente, dilo con claridad y nunca inventes datos."
            )
            user_prompt = f"Movimientos del usuario:\n{context}\n\nPregunta: {question}"
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

    # Modo local: se arma una respuesta sencilla con los movimientos recuperados.
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
        parts.append("Encontré movimientos, pero no son suficientes para un análisis detallado.")

    parts.append("(Respuesta generada en modo local, sin OpenAI, usando tus propios registros.)")
    return " ".join(parts)
