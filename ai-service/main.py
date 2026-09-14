# Microservicio de IA: vectoriza movimientos y responde consultas en lenguaje natural (HU7).
import json
import os
import re
import uuid
from datetime import datetime, timezone

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

import models
import schemas
from ai_client import (
    NO_INFO_ANSWER,
    current_model_name,
    embed_many_with_model,
    embed_with_model,
    extract_filters,
    generate_answer,
    is_openai_enabled,
)
from database import Base, engine, get_db
from security import get_current_user_id

# Crea las tablas al iniciar el servicio.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FinZen - AI Service", version="1.0.0")

# Orígenes permitidos leídos desde variables de entorno (nunca "*" con credenciales).
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Cantidad de movimientos más relevantes que se recuperan por cada consulta.
TOP_K = 5
# Cuántos candidatos recupera cada buscador (vectorial y palabras clave) antes de fusionar.
CANDIDATES = 20
# Clave usada en la tabla de configuración para guardar la clave de OpenAI.
OPENAI_KEY_SETTING = "openai_api_key"
# Tabla FTS5 para la búsqueda por palabras clave (modo híbrido).
FTS_TABLE = "vectorized_transactions_fts"


def ensure_schema():
    # Migración ligera: agrega columnas nuevas a bases ya existentes y crea la tabla FTS5.
    with engine.begin() as conn:
        columns = [
            row[1]
            for row in conn.exec_driver_sql(
                "PRAGMA table_info(vectorized_transactions)"
            ).fetchall()
        ]
        if columns and "embedding_model" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE vectorized_transactions "
                "ADD COLUMN embedding_model VARCHAR DEFAULT ''"
            )
        if columns and "currency" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE vectorized_transactions ADD COLUMN currency VARCHAR DEFAULT ''"
            )
        conn.exec_driver_sql(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} "
            "USING fts5(id UNINDEXED, user_id UNINDEXED, text, category, description)"
        )


ensure_schema()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Devuelve un formato de error uniforme para toda la API.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Error de validación de datos",
            "code": "VALIDATION_ERROR",
            "details": jsonable_encoder(exc.errors()),
        },
    )


def mask_key(value: str | None) -> str | None:
    # Versión enmascarada para mostrar (nunca la clave completa).
    if not value:
        return None
    if len(value) <= 8:
        return "••••••"
    return f"{value[:3]}••••••{value[-4:]}"


def stored_openai_key(db: Session) -> str | None:
    # Lee la clave guardada en SQLite (tabla settings).
    setting = db.get(models.Setting, OPENAI_KEY_SETTING)
    return setting.value if setting else None


def build_text_from_record(record: models.VectorizedTransaction) -> str:
    # Construye la frase que se vectoriza a partir de un registro guardado.
    label = "Ingreso" if record.record_type == "income" else "Gasto"
    amount_text = f"{record.amount:.2f} {record.currency}".strip()
    parts = [f"{label} de {amount_text}"]
    if record.category:
        parts.append(f"en {record.category}")
    if record.date:
        parts.append(f"el {record.date}")
    if record.description:
        parts.append(f"({record.description})")
    return " ".join(parts)


def build_record_text(payload: schemas.VectorizeRequest) -> str:
    # Construye la frase que se vectoriza a partir del movimiento recibido.
    label = "Ingreso" if payload.record_type == "income" else "Gasto"
    amount_text = f"{payload.amount:.2f} {payload.currency}".strip()
    parts = [f"{label} de {amount_text}"]
    if payload.category:
        parts.append(f"en {payload.category}")
    if payload.date:
        parts.append(f"el {payload.date}")
    if payload.description:
        parts.append(f"({payload.description})")
    return " ".join(parts)


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    # Calcula la similitud coseno entre dos vectores con NumPy.
    array_a = np.asarray(vector_a, dtype=float)
    array_b = np.asarray(vector_b, dtype=float)
    denominator = np.linalg.norm(array_a) * np.linalg.norm(array_b)
    if denominator == 0:
        return 0.0
    return float(np.dot(array_a, array_b) / denominator)


def upsert_fts(db: Session, record: models.VectorizedTransaction) -> None:
    # Mantiene la tabla FTS sincronizada con el registro vectorizado.
    db.execute(text(f"DELETE FROM {FTS_TABLE} WHERE id = :id"), {"id": record.id})
    db.execute(
        text(
            f"INSERT INTO {FTS_TABLE} (id, user_id, text, category, description) "
            "VALUES (:id, :user_id, :text, :category, :description)"
        ),
        {
            "id": record.id,
            "user_id": record.user_id,
            "text": record.text,
            "category": record.category,
            "description": record.description,
        },
    )


def vector_search(records: list, question_vector: list[float], limit: int) -> list[str]:
    # Ranking por similitud coseno (búsqueda semántica).
    scored = sorted(
        records,
        key=lambda record: cosine_similarity(question_vector, json.loads(record.embedding)),
        reverse=True,
    )
    return [record.id for record in scored[:limit]]


def keyword_search(db: Session, user_id: str, question: str, limit: int) -> list[str]:
    # Ranking por palabras clave usando FTS5 (búsqueda léxica).
    tokens = re.findall(r"\w+", question.lower())
    if not tokens:
        return []
    match_query = " OR ".join(f'"{token}"' for token in tokens)
    try:
        rows = db.execute(
            text(
                f"SELECT id FROM {FTS_TABLE} "
                f"WHERE {FTS_TABLE} MATCH :query AND user_id = :user_id LIMIT :limit"
            ),
            {"query": match_query, "user_id": user_id, "limit": limit},
        ).fetchall()
        return [row[0] for row in rows]
    except Exception:
        # Si la consulta FTS falla, se continúa solo con la búsqueda vectorial.
        return []


def reciprocal_rank_fusion(*rankings: list[str], k: int = 60) -> list[str]:
    # Combina varios rankings en uno (Reciprocal Rank Fusion).
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]


@app.get("/health")
def health_check():
    # Endpoint de verificación; indica también si OpenAI está activo.
    return {
        "status": "ok",
        "service": "ai-service",
        "openai_enabled": is_openai_enabled(),
    }


@app.get("/settings/openai-key", response_model=schemas.OpenAIKeyStatus)
def get_openai_key_status(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Devuelve si hay clave configurada y su versión enmascarada.
    value = stored_openai_key(db)
    return schemas.OpenAIKeyStatus(configured=bool(value), masked=mask_key(value))


@app.put("/settings/openai-key", response_model=schemas.OpenAIKeyStatus)
def set_openai_key(
    payload: schemas.OpenAIKeyInput,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Guarda (o actualiza) la clave de OpenAI en la base SQLite.
    key = payload.apiKey.strip()
    if not key.startswith("sk-"):
        raise HTTPException(status_code=400, detail="La clave debe empezar con 'sk-'")
    setting = db.get(models.Setting, OPENAI_KEY_SETTING)
    if setting:
        setting.value = key
    else:
        db.add(models.Setting(key=OPENAI_KEY_SETTING, value=key))
    db.commit()
    return schemas.OpenAIKeyStatus(configured=True, masked=mask_key(key))


@app.delete("/settings/openai-key", response_model=schemas.OpenAIKeyStatus)
def delete_openai_key(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Elimina la clave guardada.
    setting = db.get(models.Setting, OPENAI_KEY_SETTING)
    if setting:
        db.delete(setting)
        db.commit()
    return schemas.OpenAIKeyStatus(configured=False, masked=None)


@app.post("/vectorize", response_model=schemas.VectorizeResponse, status_code=status.HTTP_201_CREATED)
def vectorize(
    payload: schemas.VectorizeRequest,
    db: Session = Depends(get_db),
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
):
    # Endpoint interno: lo llaman income-service y expense-service al crear un movimiento.
    # La clave se toma del encabezado (si viene) o de la guardada en SQLite.
    api_key = x_openai_key or stored_openai_key(db)
    text_value = build_record_text(payload)
    # Se guarda el modelo realmente usado (OpenAI o local).
    embedding, model_name = embed_with_model(text_value, api_key=api_key)

    existing = (
        db.query(models.VectorizedTransaction)
        .filter(models.VectorizedTransaction.id == payload.id)
        .first()
    )
    if existing:
        existing.text = text_value
        existing.embedding = json.dumps(embedding)
        existing.embedding_model = model_name
        existing.amount = payload.amount
        existing.category = payload.category
        existing.currency = payload.currency
        existing.date = payload.date
        existing.description = payload.description
        db.commit()
        db.refresh(existing)
        upsert_fts(db, existing)
        db.commit()
        return schemas.VectorizeResponse(status="updated", id=payload.id)

    record = models.VectorizedTransaction(
        id=payload.id or str(uuid.uuid4()),
        user_id=payload.user_id,
        record_type=payload.record_type,
        category=payload.category,
        currency=payload.currency,
        amount=payload.amount,
        date=payload.date,
        description=payload.description,
        text=text_value,
        embedding=json.dumps(embedding),
        embedding_model=model_name,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    upsert_fts(db, record)
    db.commit()
    return schemas.VectorizeResponse(status="vectorized", id=record.id)


@app.post("/reindex", response_model=schemas.ReindexResponse)
def reindex(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
):
    # Re-indexa (regenera los vectores de) todos los movimientos del usuario
    # con el modelo actual. Se usa al activar la clave real de OpenAI.
    api_key = x_openai_key or stored_openai_key(db)

    records = (
        db.query(models.VectorizedTransaction)
        .filter(models.VectorizedTransaction.user_id == current_user_id)
        .all()
    )
    if not records:
        return schemas.ReindexResponse(reindexed=0, model=current_model_name(api_key))

    for record in records:
        record.text = build_text_from_record(record)
    vectors, model_used = embed_many_with_model(
        [record.text for record in records], api_key=api_key
    )
    for record, vector in zip(records, vectors):
        record.embedding = json.dumps(vector)
        record.embedding_model = model_used
    db.commit()
    # Sincroniza la tabla FTS con todos los movimientos (útil para registros antiguos).
    for record in records:
        upsert_fts(db, record)
    db.commit()

    return schemas.ReindexResponse(reindexed=len(records), model=model_used)


@app.post("/query", response_model=schemas.QueryResponse)
def query(
    payload: schemas.QueryRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
):
    # Solo el propio usuario puede consultar su información financiera.
    if current_user_id != payload.user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este usuario")

    # Recupera todos los movimientos vectorizados del usuario.
    records = (
        db.query(models.VectorizedTransaction)
        .filter(models.VectorizedTransaction.user_id == payload.user_id)
        .all()
    )
    if not records:
        return schemas.QueryResponse(answer=NO_INFO_ANSWER, matched_records=0, sources=[])

    # Clave efectiva: encabezado (si viene) o la guardada en SQLite.
    api_key = x_openai_key or stored_openai_key(db)

    # Vectoriza la pregunta y obtiene el modelo realmente usado.
    question_vector, model_used = embed_with_model(payload.question, api_key=api_key)

    # Re-indexado automático: si algún movimiento quedó con otro modelo (p. ej. local)
    # o su texto está desactualizado (p. ej. sin moneda), se regenera aquí mismo.
    outdated = []
    for record in records:
        expected_text = build_text_from_record(record)
        if (record.embedding_model or "") != model_used or record.text != expected_text:
            record.text = expected_text
            outdated.append(record)
    if outdated:
        vectors, _ = embed_many_with_model([record.text for record in outdated], api_key=api_key)
        for record, vector in zip(outdated, vectors):
            record.embedding = json.dumps(vector)
            record.embedding_model = model_used
        db.commit()
        for record in outdated:
            upsert_fts(db, record)
        db.commit()

    # Pre-filtrado por metadata (categoría, tipo y rango de fechas) antes de buscar.
    categories = sorted({record.category for record in records if record.category})
    record_types = sorted({record.record_type for record in records if record.record_type})
    filters = extract_filters(
        payload.question, categories, record_types, api_key=api_key, timezone=payload.timezone
    )

    candidates = records
    if filters.get("category"):
        candidates = [r for r in candidates if r.category == filters["category"]]
    if filters.get("record_type"):
        candidates = [r for r in candidates if r.record_type == filters["record_type"]]
    if filters.get("start_date"):
        candidates = [r for r in candidates if r.date and r.date >= filters["start_date"]]
    if filters.get("end_date"):
        candidates = [r for r in candidates if r.date and r.date <= filters["end_date"]]
    # Si el filtro deja todo vacío, se usan todos los movimientos (evita respuestas vacías).
    if not candidates:
        candidates = records

    candidate_ids = {record.id for record in candidates}

    # Búsqueda híbrida: vectorial (semántica) + palabras clave (FTS5), fusionadas con RRF.
    vector_ids = vector_search(candidates, question_vector, CANDIDATES)
    keyword_ids = [
        doc_id
        for doc_id in keyword_search(db, payload.user_id, payload.question, CANDIDATES)
        if doc_id in candidate_ids
    ]
    fused_ids = reciprocal_rank_fusion(vector_ids, keyword_ids)

    by_id = {record.id: record for record in records}
    top_records = [by_id[doc_id] for doc_id in fused_ids[:TOP_K] if doc_id in by_id]
    if not top_records:
        top_records = candidates[:TOP_K]

    # Genera la respuesta final a partir de los movimientos más relevantes.
    answer = generate_answer(payload.question, top_records, api_key=api_key)

    # Citas: se extraen los [ID: x] que el modelo usó; si no citó, se devuelven los recuperados.
    cited_ids = set(re.findall(r"\[ID:\s*([^\]]+)\]", answer))
    used_records = [record for record in top_records if record.id in cited_ids] or top_records
    sources = [schemas.SourceItem(id=record.id, text=record.text) for record in used_records]

    return schemas.QueryResponse(
        answer=answer,
        matched_records=len(top_records),
        sources=sources,
    )
