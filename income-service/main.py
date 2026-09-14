# Microservicio de ingresos: registro, listado, detalle y eliminación (HU2 y HU4).
import os
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db
from integrations import vectorize_record
from security import get_current_user_id

# Crea las tablas al iniciar el servicio.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FinZen - Income Service", version="1.0.0")

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


@app.get("/health")
def health_check():
    # Endpoint de verificación para saber si el servicio está en pie.
    return {"status": "ok", "service": "income-service"}


@app.post("/incomes", response_model=schemas.IncomeOut, status_code=status.HTTP_201_CREATED)
def create_income(
    payload: schemas.IncomeCreate,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # El usuario del token debe coincidir con el dueño del ingreso.
    if current_user_id != payload.user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este usuario")

    income = models.Income(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        type=payload.type,
        amount=payload.amount,
        currency=payload.currency,
        date=payload.date,
        description=payload.description,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(income)
    db.commit()
    db.refresh(income)

    # Vectoriza en segundo plano: la respuesta no espera al ai-service.
    background_tasks.add_task(
        vectorize_record,
        {
            "id": income.id,
            "user_id": income.user_id,
            "record_type": "income",
            "category": income.type,
            "currency": income.currency,
            "amount": str(income.amount),
            "date": income.date.isoformat(),
            "description": income.description,
        },
    )
    return income


@app.get("/incomes/{user_id}", response_model=list[schemas.IncomeOut])
def list_incomes(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Solo el propio usuario puede ver sus ingresos.
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este usuario")
    # Ordenados por fecha, del más reciente al más antiguo.
    return (
        db.query(models.Income)
        .filter(models.Income.user_id == user_id)
        .order_by(models.Income.date.desc())
        .all()
    )


@app.get("/incomes/detail/{income_id}", response_model=schemas.IncomeOut)
def get_income(
    income_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Devuelve el detalle solo si el ingreso pertenece al usuario autenticado.
    income = db.query(models.Income).filter(models.Income.id == income_id).first()
    if not income:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    if income.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este ingreso")
    return income


@app.delete("/incomes/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    income_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Elimina el ingreso solo si pertenece al usuario autenticado.
    income = db.query(models.Income).filter(models.Income.id == income_id).first()
    if not income:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    if income.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este ingreso")
    db.delete(income)
    db.commit()
    return None
