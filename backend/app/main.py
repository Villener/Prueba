"""API del Sistema de Gestion de Flota y Taller - Baja Gas.

Implementa docs/requerimientos.md v1.1, docs/modelo-er.md v1.1 y
docs/casos-de-uso.md v1.1. Cada endpoint cita el caso de uso que realiza.
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import jobs
from .database import Base, engine, get_db
from .routers import administrador, auth, chofer, gerente, montacarguista, supervisor
from .security import require_roles
from .seed import sembrar

app = FastAPI(
    title="Baja Gas - Gestion de Flota y Taller",
    version="1.1.0",
    description="5 modulos: Chofer, Supervisor, Administrador, Montacarguista y Gerente. "
                "Los mecanicos no usan la aplicacion: el administrador captura su trabajo.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in [auth.router, chofer.router, supervisor.router, administrador.router,
          montacarguista.router, gerente.router]:
    app.include_router(r)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    from .database import SessionLocal
    db = SessionLocal()
    try:
        sembrar(db)
    finally:
        db.close()


@app.get("/api/health", tags=["sistema"])
def health():
    return {"ok": True, "version": "1.1.0"}


@app.post("/api/jobs/correr", tags=["sistema"])
def correr_jobs(usuario=Depends(require_roles("gerente", "administrador")),
                db: Session = Depends(get_db)):
    """Dispara manualmente los procesos del actor 'Programador de tareas' (CU-AUT-01..03).

    En produccion esto lo lanza un cron diario; aqui se expone para poder
    demostrar RN-05 y RN-08 sin esperar tres meses.
    """
    return jobs.correr_todos(db)
