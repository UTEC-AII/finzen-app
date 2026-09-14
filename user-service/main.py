# Microservicio de usuarios: registro, login y perfil (HU1 y HU6).
import os
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db
from security import create_access_token, get_current_user_id, hash_password, verify_password

# Crea las tablas al iniciar el servicio.
Base.metadata.create_all(bind=engine)


def ensure_schema():
    # Migración ligera: agrega columnas nuevas a bases ya existentes.
    with engine.begin() as conn:
        columns = [
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
        ]
        if columns and "timezone" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN timezone VARCHAR DEFAULT 'America/Lima'"
            )


ensure_schema()

app = FastAPI(title="FinZen - User Service", version="1.0.0")

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
    return {"status": "ok", "service": "user-service"}


@app.post("/users", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    # Verifica que el correo no esté registrado antes de crear la cuenta.
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="El correo ya está registrado")

    user = models.User(
        id=str(uuid.uuid4()),
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        preferred_currency=payload.preferred_currency,
        timezone=payload.timezone,
        monthly_savings_goal=0,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.LoginResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    # Busca al usuario y valida la contraseña.
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    # Mensaje genérico para no revelar si el correo existe o no.
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_access_token(user.id)
    return schemas.LoginResponse(
        access_token=token,
        user=schemas.UserOut.model_validate(user),
    )


@app.get("/users/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Solo el propio usuario puede ver su perfil.
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="No autorizado para ver este perfil")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@app.put("/users/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: str,
    payload: schemas.UserUpdate,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Solo el propio usuario puede editar su perfil.
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="No autorizado para editar este perfil")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Actualiza solo los campos enviados (nombre, moneda o meta de ahorro).
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
