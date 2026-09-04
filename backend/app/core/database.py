"""Conexion a la base de datos y sesion de SQLAlchemy."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# backend/app/core/database.py -> backend/
#
# Van TRES dirname, no dos. Con dos, la base cae dentro de app/, o sea DENTRO
# del paquete de Python. Ese fue el efecto silencioso de mover este archivo de
# app/database.py a app/core/database.py en la reestructuracion: la ruta se
# recorrio un nivel y SQLite, en vez de fallar, creo una base nueva y vacia.
# Quedaron dos archivos y los documentos apuntaban al que ya nadie usaba.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'bajagas.db')}")

# check_same_thread solo aplica a SQLite; en PostgreSQL se ignora.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
