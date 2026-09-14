# Modelo de la tabla de ingresos.
from sqlalchemy import Column, Date, Index, Numeric, String

from database import Base


class Income(Base):
    __tablename__ = "incomes"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    # Tipo de ingreso: Sueldo, Freelance, Bono, Inversion u Otro.
    type = Column(String, nullable=False)
    # Monto monetario con precisión fija (nunca Float para dinero).
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String, default="")
    created_at = Column(String, nullable=False)

    # Índices compuestos: primero la columna de igualdad (user_id), luego la de rango/uso.
    __table_args__ = (
        Index("idx_incomes_user_date", "user_id", "date"),
        Index("idx_incomes_user_type", "user_id", "type"),
    )
