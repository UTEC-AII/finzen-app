# Modelo de la tabla de gastos.
from sqlalchemy import Column, Date, Index, Numeric, String

from database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    # Categoría del gasto (ver la lista en main.py).
    category = Column(String, nullable=False)
    # Monto monetario con precisión fija (nunca Float para dinero).
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String, default="")
    created_at = Column(String, nullable=False)

    # Índices compuestos: primero la columna de igualdad (user_id), luego la de rango/uso.
    __table_args__ = (
        Index("idx_expenses_user_date", "user_id", "date"),
        Index("idx_expenses_user_category", "user_id", "category"),
    )
