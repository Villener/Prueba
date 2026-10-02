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


def plantillas(db):
    """Dos supervisores, cada uno con un chofer sin celular."""
    def persona(nombre, correo, tel=None):
        u = m.Usuario(nombre=nombre, apellidos="X", email=correo, password_hash="x", telefono=tel)
        db.add(u)
        db.flush()
        return u
    out = []
    for i in (1, 2):
        sup = persona(f"Sup{i}", f"s{i}@bajagas.mx")
        db.add(m.Supervisor(usuario_id=sup.id))
        db.flush()
        p = m.Plantilla(nombre=f"P{i}", supervisor_id=sup.id)
        db.add(p)
        db.flush()
        ch = persona(f"Chofer{i}", f"c{i}@bajagas.mx", tel="664-000-0000")
        db.add(m.Chofer(usuario_id=ch.id, plantilla_id=p.id))
        out.append((sup, ch))
    db.commit()
    return out


@caso("el supervisor captura el celular de su chofer, queda auditado y el chofer se entera")
def _():
    from app.modules.flota import supervisor_controller as sc
    db, _ = escenario()
    (sup, ch), _otro = plantillas(db)
    r = sc.telefono_del_chofer(ch.id, sc.TelefonoIn(telefono="664-321-0099"), usuario=sup, db=db)
    assert r == {"chofer_id": ch.id, "telefono": "6643210099"}, r
    b = (db.query(m.BitacoraAuditoria)
         .filter_by(accion="telefono_capturado_por_supervisor").one())
    assert b.usuario_id == sup.id and b.entidad_id == ch.id
    assert b.datos_antes == "664-000-0000" and b.datos_despues == "6643210099"
    aviso = db.query(m.Notificacion).filter_by(usuario_id=ch.id).one()
    assert "664 321 0099" in aviso.mensaje
    fila = next(x for x in sc.mi_plantilla(usuario=sup, db=db) if x["chofer_id"] == ch.id)
    assert fila["telefono"] == "6643210099"


@caso("el supervisor no puede tocar el celular de un chofer de otra plantilla")
def _():
    from app.modules.flota import supervisor_controller as sc
    db, _ = escenario()
    (sup1, _ch1), (_sup2, ch2) = plantillas(db)
    try:
        sc.telefono_del_chofer(ch2.id, sc.TelefonoIn(telefono="6641112233"), usuario=sup1, db=db)
    except HTTPException as e:
        assert e.status_code == 403
    else:
        raise AssertionError("dejo cambiar el celular de un chofer ajeno")
    db.refresh(ch2)
    assert ch2.telefono == "664-000-0000"


@caso("el supervisor tampoco puede guardar el relleno ni un numero incompleto")
def _():
    from app.modules.flota import supervisor_controller as sc
    db, _ = escenario()
    (sup, ch), _otro = plantillas(db)
    for malo in ("664 000 0000", "66412"):
        try:
            sc.telefono_del_chofer(ch.id, sc.TelefonoIn(telefono=malo), usuario=sup, db=db)
        except HTTPException as e:
            assert e.status_code == 422
        else:
            raise AssertionError(f"acepto {malo!r}")


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
