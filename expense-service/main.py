# Microservicio de gastos: registro, listado con filtros, detalle y categorías (HU3 y HU5).
import os
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db
from integrations import delete_vector, vectorize_record
from security import get_current_user_id

# Crea las tablas al iniciar el servicio.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FinZen - Expense Service", version="1.0.0")

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

# Catálogo de categorías disponibles para clasificar los gastos.
EXPENSE_CATEGORIES = [
    "Alimentacion",
    "Transporte",
    "Vivienda",
    "Entretenimiento",
    "Salud",
    "Educacion",
    "Ropa",
    "Otros",
]


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
    return {"status": "ok", "service": "expense-service"}


@app.get("/expenses/categories/list", response_model=schemas.CategoryListResponse)
def list_categories():
    # Devuelve el catálogo de categorías para poblar el selector del frontend.
    return schemas.CategoryListResponse(categories=EXPENSE_CATEGORIES)


@app.post("/expenses", response_model=schemas.ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: schemas.ExpenseCreate,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # El usuario del token debe coincidir con el dueño del gasto.
    if current_user_id != payload.user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este usuario")
    # Valida que la categoría pertenezca al catálogo permitido.
    if payload.category not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoría no válida")

    expense = models.Expense(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        category=payload.category,
        amount=payload.amount,
        currency=payload.currency,
        date=payload.date,
        description=payload.description,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)

    # Vectoriza en segundo plano: la respuesta no espera al ai-service.
    background_tasks.add_task(
        vectorize_record,
        {
            "id": expense.id,
            "user_id": expense.user_id,
            "record_type": "expense",
            "category": expense.category,
            "currency": expense.currency,
            "amount": str(expense.amount),
            "date": expense.date.isoformat(),
            "description": expense.description,
        },
    )
    return expense


@app.get("/expenses/{user_id}", response_model=list[schemas.ExpenseOut])
def list_expenses(
    user_id: str,
    category: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Solo el propio usuario puede ver sus gastos.
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este usuario")
    # Aplica filtros opcionales por categoría y rango de fechas.
    query = db.query(models.Expense).filter(models.Expense.user_id == user_id)
    if category:
        query = query.filter(models.Expense.category == category)
    if date_from:
        query = query.filter(models.Expense.date >= date_from)
    if date_to:
        query = query.filter(models.Expense.date <= date_to)
    return query.order_by(models.Expense.date.desc()).all()


@app.get("/expenses/detail/{expense_id}", response_model=schemas.ExpenseOut)
def get_expense(
    expense_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Devuelve el detalle solo si el gasto pertenece al usuario autenticado.
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    if expense.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este gasto")
    return expense


@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Elimina el gasto solo si pertenece al usuario autenticado.
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    if expense.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="No autorizado para este gasto")
    db.delete(expense)
    db.commit()
    # Elimina también su vector en el ai-service.
    delete_vector(expense_id)
    return None
