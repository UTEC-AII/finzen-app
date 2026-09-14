# Esquemas de entrada y salida (validación con Pydantic v2).
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=6)
    preferred_currency: str = "PEN"


class UserUpdate(BaseModel):
    # El correo no se puede editar porque es el identificador único de la cuenta.
    name: Optional[str] = Field(None, min_length=1)
    preferred_currency: Optional[str] = None
    monthly_savings_goal: Optional[Decimal] = Field(
        None, ge=0, max_digits=12, decimal_places=2
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    # from_attributes permite construir el esquema desde un objeto ORM (SQLAlchemy).
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    preferred_currency: str
    monthly_savings_goal: Decimal
    created_at: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
