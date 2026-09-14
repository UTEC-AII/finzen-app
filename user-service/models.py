# Modelo de la tabla de usuarios.
from sqlalchemy import Column, Numeric, String

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    preferred_currency = Column(String, default="PEN")
    # Zona horaria IANA del usuario (para fechas locales). Ej: "America/Lima".
    timezone = Column(String, default="America/Lima")
    # Monto monetario con precisión fija (nunca Float para dinero).
    monthly_savings_goal = Column(Numeric(12, 2), default=0)
    created_at = Column(String, nullable=False)
