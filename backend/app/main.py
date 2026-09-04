"""API del Sistema de Gestion de Flota y Taller - Baja Gas.

Implementa docs/requerimientos.md v1.1, docs/modelo-er.md v1.1 y
docs/casos-de-uso.md v1.1. Cada endpoint cita el caso de uso que realiza.
"""
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import jobs
from .core.database import Base, engine, get_db
from .modules.emergencias.montacarguista_controller import router as router_montacarguista
from .modules.flota.chofer_controller import router as router_chofer
from .modules.flota.supervisor_controller import router as router_supervisor
from .modules.mantenimiento.agenda_controller import router as router_agenda
from .modules.organizacion.auth_controller import router as router_auth
from .modules.piezas.capturista_controller import router as router_capturista
from .modules.sistema.gerente_controller import router as router_gerente
from .modules.taller.administrador_controller import router as router_administrador
from .core.security import require_roles
from .core.migraciones import asegurar_columnas, asegurar_indices
from .seed import (asegurar_plano, asegurar_reportes_de_ordenes_abiertas,
                   asegurar_roles, asegurar_tipos_servicio,
                   asegurar_usuarios_demo, reconciliar_cuentas, sembrar)

app = FastAPI(
    title="Baja Gas - Gestion de Flota y Taller",
    version="1.2.0",
    description="6 modulos: Chofer, Supervisor, Administrador, Capturista, Montacarguista "
                "y Gerente. Los mecanicos no usan la aplicacion: el administrador captura "
                "su trabajo de taller y el capturista teclea las requisiciones.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Un controller por dominio. Cada uno vive junto a los modelos que usa,
# en app/modules/<dominio>/, igual que en el diagrama de clases.
for r in [router_auth, router_chofer, router_supervisor, router_administrador,
          router_agenda, router_montacarguista, router_gerente, router_capturista]:
    app.include_router(r)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    # create_all no toca las tablas que YA existian: ni les agrega las columnas
    # nuevas del modelo ni los indices. Sin estos dos pasos, una base previa
    # empieza a dar error 500 tras cada cambio de modelo.
    log = logging.getLogger("bajagas")

    # La clave por defecto esta escrita en core/security.py, o sea que es
    # publica: cualquiera que lea el repositorio puede firmarse un token de
    # gerente valido. Mientras esto vivia en localhost no importaba; detras de
    # una URL publica es la puerta de atras. Se avisa fuerte en cada arranque
    # porque un fallo silencioso aqui no se descubre hasta que ya paso algo.
    from .core.security import SECRET_KEY
    if SECRET_KEY == "cambia-esto-en-produccion-bajagas-2026":
        log.warning("=" * 70)
        log.warning("SECRET_KEY es la de por defecto, que esta publicada en el codigo.")
        log.warning("Para exponer esto fuera de la red local, arranca con una propia:")
        log.warning('  SECRET_KEY="$(openssl rand -hex 32)" docker compose up -d')
        log.warning("=" * 70)

    for hecho in asegurar_columnas(engine, Base.metadata):
        log.info("migracion: %s", hecho)
    for aviso in asegurar_indices(engine):
        log.warning(aviso)
    from .core.database import SessionLocal
    db = SessionLocal()
    try:
        # ANTES de sembrar: los planes de mantenimiento apuntan a un tipo de
        # servicio, asi que el catalogo tiene que existir primero. Y va en
        # funcion aparte porque sembrar() se rinde si la base ya tiene datos,
        # y el catalogo tambien tiene que llegarle a una base previa.
        log.info("tipos de servicio: %s", asegurar_tipos_servicio(db))
        sembrar(db)
        # Despues de sembrar: pone al dia el plano de una base que ya existia
        # (etiquetas por fila y que zonas admiten unidad). En una base nueva no
        # encuentra nada que arreglar.
        log.info("plano: %s", asegurar_plano(db))
        # Antes de tocar cuentas: un rol nuevo (capturista) tiene que existir
        # en el catalogo o su cuenta se salta en silencio.
        log.info("roles: %s", asegurar_roles(db))
        # Primero se reconcilian las cuentas inventadas de versiones anteriores
        # --se renombran a la persona real o se desactivan-- y luego se crean
        # las que falten. Al reves, quedarian dos cuentas para la misma persona.
        log.info("reconciliacion: %s", reconciliar_cuentas(db))
        log.info("cuentas reales: %s", asegurar_usuarios_demo(db))
        # Al final: necesita las ordenes ya sembradas para saber a que unidades
        # les falta formato (v1.3, el reporte nace con el ingreso).
        log.info("reportes: %s", asegurar_reportes_de_ordenes_abiertas(db))
    finally:
        db.close()


@app.get("/api/health", tags=["sistema"])
def health():
    return {"ok": True, "version": "1.2.0"}


@app.post("/api/jobs/correr", tags=["sistema"])
def correr_jobs(usuario=Depends(require_roles("gerente", "administrador")),
                db: Session = Depends(get_db)):
    """Dispara manualmente los procesos del actor 'Programador de tareas' (CU-AUT-01..03).

    En produccion esto lo lanza un cron diario; aqui se expone para poder
    demostrar RN-05 y RN-08 sin esperar tres meses.
    """
    return jobs.correr_todos(db)
