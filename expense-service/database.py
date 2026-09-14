# Conexión a la base de datos SQLite propia de este microservicio.
# Cada microservicio administra su propio archivo .db (patrón database-per-microservice).
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# Ruta del archivo SQLite. Se puede sobrescribir con la variable de entorno DB_PATH.
DB_PATH = Path(os.getenv("DB_PATH", "data/expenses.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# check_same_thread=False permite reutilizar la conexión entre los hilos de FastAPI.
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # Configura SQLite para un uso concurrente y consistente:
    #   WAL: permite varias lecturas mientras hay una escritura.
    #   busy_timeout: reintenta en lugar de fallar con SQLITE_BUSY.
    #   synchronous=NORMAL: buen equilibrio entre integridad y velocidad en modo WAL.
    #   foreign_keys=ON: obliga a respetar las claves foráneas declaradas.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    # Abre una sesión de base de datos por petición y la cierra al terminar.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
