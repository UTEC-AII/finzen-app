# Esquemas de entrada y salida (validación con Pydantic v2).
from decimal import Decimal

from pydantic import BaseModel, Field


class VectorizeRequest(BaseModel):
    id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    # "income" o "expense".
    record_type: str = Field(..., min_length=1)
    category: str = ""
    amount: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=2)
    date: str = ""
    description: str = ""


class VectorizeResponse(BaseModel):
    status: str
    id: str


class QueryRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)


class QueryResponse(BaseModel):
    answer: str
    matched_records: int


class OpenAIKeyInput(BaseModel):
    apiKey: str = Field(..., min_length=20)


class OpenAIKeyStatus(BaseModel):
    configured: bool
    masked: str | None = None
