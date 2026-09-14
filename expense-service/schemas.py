# Esquemas de entrada y salida (validación con Pydantic v2).
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    # Decimal con 2 decimales evita los errores de redondeo de Float.
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(..., min_length=1)
    date: date
    description: str = ""


class CategoryListResponse(BaseModel):
    # Respuesta con el catálogo de categorías disponibles.
    categories: list[str]


class ExpenseOut(BaseModel):
    # from_attributes permite construir el esquema desde un objeto ORM (SQLAlchemy).
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    category: str
    amount: Decimal
    currency: str
    date: date
    description: str
    created_at: str
