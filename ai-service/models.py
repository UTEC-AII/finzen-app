# Modelo de la tabla de transacciones vectorizadas.
from sqlalchemy import Column, Index, Numeric, String, Text

from database import Base


class VectorizedTransaction(Base):
    __tablename__ = "vectorized_transactions"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    # Tipo de registro: "income" (ingreso) o "expense" (gasto).
    record_type = Column(String, nullable=False)
    category = Column(String, default="")
    # Monto monetario con precisión fija (nunca Float para dinero).
    amount = Column(Numeric(12, 2), default=0)
    date = Column(String, default="")
    description = Column(String, default="")
    # Frase generada a partir del registro, usada para calcular el embedding.
    text = Column(String, nullable=False)
    # Vector guardado como texto JSON dentro de SQLite.
    embedding = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)

    __table_args__ = (Index("idx_vectors_user_type", "user_id", "record_type"),)
