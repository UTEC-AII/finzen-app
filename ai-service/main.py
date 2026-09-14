# Microservicio de IA: vectoriza movimientos y responde consultas en lenguaje natural (HU7).
import json
import os
import uuid
from datetime import datetime, timezone

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import models
import schemas
from ai_client import embed_text, generate_answer, is_openai_enabled
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


def build_record_text(payload: schemas.VectorizeRequest) -> str:
    # Construye la frase que se vectoriza a partir del movimiento.
    label = "Ingreso" if payload.record_type == "income" else "Gasto"
    parts = [f"{label} de {payload.amount:.2f}"]
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


@app.get("/health")
def health_check():
    # Endpoint de verificación; indica también si OpenAI está activo.
    return {
        "status": "ok",
        "service": "ai-service",
        "openai_enabled": is_openai_enabled(),
    }


@app.post("/vectorize", response_model=schemas.VectorizeResponse, status_code=status.HTTP_201_CREATED)
def vectorize(
    payload: schemas.VectorizeRequest,
    db: Session = Depends(get_db),
    x_openai_key: str | None = Header(default=None, alias="X-OpenAI-Key"),
):
    # Endpoint interno: lo llaman income-service y expense-service al crear un movimiento.
    text = build_record_text(payload)
    embedding = embed_text(text, api_key=x_openai_key)

    existing = (
        db.query(models.VectorizedTransaction)
        .filter(models.VectorizedTransaction.id == payload.id)
        .first()
    )
    if existing:
        existing.text = text
        existing.embedding = json.dumps(embedding)
        existing.amount = payload.amount
        existing.category = payload.category
        existing.date = payload.date
        existing.description = payload.description
        db.commit()
        return schemas.VectorizeResponse(status="updated", id=payload.id)

    record = models.VectorizedTransaction(
        id=payload.id or str(uuid.uuid4()),
        user_id=payload.user_id,
        record_type=payload.record_type,
        category=payload.category,
        amount=payload.amount,
        date=payload.date,
        description=payload.description,
        text=text,
        embedding=json.dumps(embedding),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(record)
    db.commit()
    return schemas.VectorizeResponse(status="vectorized", id=record.id)


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
        return schemas.QueryResponse(
            answer="Todavía no tienes ingresos ni gastos registrados para analizar.",
            matched_records=0,
        )

    # Vectoriza la pregunta y calcula la similitud coseno con cada movimiento.
    question_vector = embed_text(payload.question, api_key=x_openai_key)
    scored = sorted(
        records,
        key=lambda record: cosine_similarity(question_vector, json.loads(record.embedding)),
        reverse=True,
    )
    top_records = scored[:TOP_K]

    # Genera la respuesta final a partir de los movimientos más relevantes.
    answer = generate_answer(payload.question, top_records, api_key=x_openai_key)
    return schemas.QueryResponse(answer=answer, matched_records=len(top_records))
