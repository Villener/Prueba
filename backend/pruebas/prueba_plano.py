"""Pruebas del plano: el estado de cada casilla cuadra con quien esta adentro.

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_plano.py     (Windows)

El caso real que las origino: en produccion T-01 y T-02 de REPARTO NORTE
quedaron "ocupadas" sin unidad adentro despues del arranque operativo.
"""
import json
import os
import sys
import traceback

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["DATABASE_URL"] = "sqlite://"

from sqlalchemy import create_engine                        # noqa: E402
from sqlalchemy.orm import sessionmaker                     # noqa: E402

from app import models as m                                 # noqa: E402
from app.core.database import Base                          # noqa: E402
from app.modules.taller import administrador_controller as ac  # noqa: E402
from app.modules.taller.taller_service import reconciliar_espacios  # noqa: E402

CASOS = []


class Admin:
    """Quien mira el plano: el servidor ahora pregunta quien es (el mecanico solo
    ve su planta)."""
    id = 0
    lista_roles = ["administrador"]


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


def escenario():
    """Alamos con REPARTO NORTE de cuatro casillas: T-01 y T-02 'ocupadas' sin
    nadie adentro (lo de produccion), T-03 libre con una unidad que SI entro, y
    T-04 bloqueada a proposito."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng, autoflush=False)()
    t = m.Taller(nombre="Alamos")
    db.add(t)
    db.flush()
    z = m.ZonaTaller(taller_id=t.id, nombre="REPARTO NORTE", cuenta_para_ocupacion=True)
    db.add(z)
    db.flush()
    esp = {}
    for num, estado in (("T-01", "ocupado"), ("T-02", "ocupado"), ("T-03", "libre"), ("T-04", "bloqueado")):
        e = m.Espacio(zona_id=z.id, numero=num, estado=estado)
        db.add(e)
        esp[num] = e
    tipo = m.TipoUnidad(nombre="Reparto")
    db.add(tipo)
    db.flush()
    u = m.Unidad(num_economico="1009", tipo_unidad_id=tipo.id)
    db.add(u)
    db.flush()
    db.add(m.OcupacionEspacio(espacio_id=esp["T-03"].id, unidad_id=u.id))
    db.commit()
    return db, t, esp


@caso("libera las casillas 'ocupadas' sin unidad y ocupa la que si tiene una")
def _():
    db, _t, esp = escenario()
    r = reconciliar_espacios(db)
    db.commit()
    assert r == {"liberados": 2, "ocupados": 1}, r
    for e in esp.values():
        db.refresh(e)
    assert [esp[n].estado for n in ("T-01", "T-02", "T-03", "T-04")] == ["libre", "libre", "ocupado", "bloqueado"]


@caso("deja constancia de que casillas corrigio")
def _():
    db, _t, esp = escenario()
    reconciliar_espacios(db)
    db.commit()
    b = db.query(m.BitacoraAuditoria).filter_by(accion="espacios_reconciliados").one()
    d = json.loads(b.datos_despues)
    assert sorted(d["liberados"]) == sorted([esp["T-01"].id, esp["T-02"].id])
    assert d["ocupados"] == [esp["T-03"].id]


@caso("si ya cuadra, no cambia nada ni ensucia la bitacora")
def _():
    db, _t, _esp = escenario()
    reconciliar_espacios(db)
    db.commit()
    assert reconciliar_espacios(db) == {"liberados": 0, "ocupados": 0}
    db.commit()
    assert db.query(m.BitacoraAuditoria).filter_by(accion="espacios_reconciliados").count() == 1


@caso("despues de cuadrar, el contador del plano dice lo mismo que las casillas")
def _():
    db, t, _esp = escenario()
    antes = ac.plano_taller(t.id, usuario=Admin(), db=db)
    assert antes["ocupados"] == 2  # lo que veia Martin: 2 ocupados sin nadie adentro
    reconciliar_espacios(db)
    db.commit()
    p = ac.plano_taller(t.id, usuario=Admin(), db=db)
    casillas = {e["numero"]: e for z in p["zonas"] for e in z["espacios"]}
    assert p["ocupados"] == 1 and casillas["T-03"]["unidad"] == "1009"
    for n in ("T-01", "T-02"):
        assert casillas[n]["estado"] == "libre" and casillas[n]["unidad"] is None


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
