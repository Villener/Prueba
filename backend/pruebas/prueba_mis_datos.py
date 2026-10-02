"""Pruebas de Mis datos: cada quien pone su celular (auth_controller.mi_telefono).

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_mis_datos.py     (Windows)
"""
import os
import sys
import traceback

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import HTTPException                           # noqa: E402
from sqlalchemy import create_engine                        # noqa: E402
from sqlalchemy.orm import sessionmaker                     # noqa: E402

from app import models as m                                 # noqa: E402
from app.core.database import Base                          # noqa: E402
from app.modules.organizacion import auth_controller as ac  # noqa: E402

CASOS = []


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


def escenario(telefono="664-000-0000"):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng, autoflush=False)()
    u = m.Usuario(nombre="Ana", apellidos="Chofer", email="e1@bajagas.mx",
                  password_hash="x", telefono=telefono)
    db.add(u)
    db.commit()
    return db, u


def cambios(db):
    return (db.query(m.BitacoraAuditoria)
            .filter_by(accion="telefono_actualizado").order_by(m.BitacoraAuditoria.id).all())


@caso("guarda el celular en 10 digitos, como el importador, y deja constancia")
def _():
    db, u = escenario()
    r = ac.mi_telefono(ac.TelefonoIn(telefono="+52 (664) 123-4567"), usuario=u, db=db)
    assert r["telefono"] == "6641234567", r
    b = cambios(db)
    assert len(b) == 1 and b[0].usuario_id == u.id
    assert b[0].datos_antes == "664-000-0000" and b[0].datos_despues == "6641234567"


@caso("rechaza lo que no es un celular y el relleno de la semilla")
def _():
    db, u = escenario()
    for malo in ("123", "", "664 000 0000", "52 664 123 456 789 01"):
        try:
            ac.mi_telefono(ac.TelefonoIn(telefono=malo), usuario=u, db=db)
        except HTTPException as e:
            assert e.status_code == 422
        else:
            raise AssertionError(f"acepto {malo!r}")
    db.refresh(u)
    assert u.telefono == "664-000-0000" and cambios(db) == []


@caso("el mismo numero otra vez no ensucia la bitacora")
def _():
    db, u = escenario(telefono="6641234567")
    ac.mi_telefono(ac.TelefonoIn(telefono="664 123 4567"), usuario=u, db=db)
    assert cambios(db) == []


@caso("solo cambia el telefono de quien esta adentro")
def _():
    db, u = escenario()
    otro = m.Usuario(nombre="Beto", apellidos="Chofer", email="e2@bajagas.mx",
                     password_hash="x", telefono=None)
    db.add(otro)
    db.commit()
    ac.mi_telefono(ac.TelefonoIn(telefono="6649998877"), usuario=u, db=db)
    db.refresh(otro)
    assert otro.telefono is None


if __name__ == "__main__":
    ok = fallo = 0
    for i, (nombre, fn) in enumerate(CASOS, 1):
        try:
            fn()
            ok += 1
            print(f"  OK   {i:2d}. {nombre}")
        except Exception:
            fallo += 1
            print(f"  FALLA {i:2d}. {nombre}")
            traceback.print_exc()
    print(f"\n{ok} pasaron, {fallo} fallaron, de {len(CASOS)} casos")
    sys.exit(1 if fallo else 0)
