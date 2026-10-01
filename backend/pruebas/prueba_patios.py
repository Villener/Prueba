"""Pruebas de los patios por planta del gerente (modules/sistema/patios.py).

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_patios.py     (Windows)
"""
import os
import sys
import traceback
from datetime import date, timedelta

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["DATABASE_URL"] = "sqlite://"

from sqlalchemy import create_engine                        # noqa: E402
from sqlalchemy.orm import sessionmaker                     # noqa: E402

from app import models as m                                 # noqa: E402
from app.core.database import Base                          # noqa: E402
from app.core.tiempo import ahora_utc                      # noqa: E402
from app.modules.sistema import patios                      # noqa: E402

CASOS = []


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


def escenario():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng, autoflush=False)()
    alamos, tecate = m.Planta(clave="ALAMOS", nombre="Alamos"), m.Planta(clave="TECATE", nombre="Tecate")
    db.add_all([alamos, tecate])
    db.flush()
    ta, tt = m.Taller(nombre="Alamos", planta_id=alamos.id), m.Taller(nombre="Tecate", planta_id=tecate.id)
    db.add_all([ta, tt])
    db.flush()
    z = m.ZonaTaller(taller_id=ta.id, nombre="PATIO", orden=1, cuenta_para_ocupacion=False)
    db.add(z)
    db.flush()
    e = m.Espacio(zona_id=z.id, numero="7", estado="ocupado")
    pipa = m.TipoUnidad(nombre="pipa", prioridad_operativa=1)
    db.add_all([e, pipa])
    db.flush()

    def unidad(num, taller, activo=True):
        u = m.Unidad(num_economico=num, tipo_unidad_id=pipa.id, taller_asignado_id=taller.id,
                     activo=activo, estado="disponible")
        db.add(u)
        db.flush()
        return u

    u_excel = unidad("100", ta)          # solo en el Excel del patio
    u_doble = unidad("200", ta)          # en el croquis Y en el Excel
    u_ajena = unidad("300", tt)          # de Tecate, reparandose en Alamos
    u_orden = unidad("400", ta)          # con orden abierta, sin casilla
    unidad("500", ta)                    # en la calle
    unidad("600", ta, activo=False)      # dada de baja: no es flota
    hace = lambda d: date.today() - timedelta(days=d)  # noqa: E731
    db.add_all([
        m.MovimientoTaller(unidad_id=u_excel.id, fecha_ingreso=hace(40), sigue_adentro=True,
                           area="ALAMOS", clasificacion=2, falla="FRENOS"),
        m.MovimientoTaller(unidad_id=u_doble.id, fecha_ingreso=hace(10), sigue_adentro=True,
                           area="ALAMOS", clasificacion=3, falla="MOTOR"),
        m.MovimientoTaller(unidad_id=u_ajena.id, fecha_ingreso=hace(5), sigue_adentro=True,
                           area="ALAMOS", clasificacion=1),
        # Ya salio: no cuenta aunque sea de Alamos.
        m.MovimientoTaller(unidad_id=u_orden.id, fecha_ingreso=hace(90), sigue_adentro=False,
                           area="ALAMOS"),
        m.OcupacionEspacio(espacio_id=e.id, unidad_id=u_doble.id,
                           fecha_entrada=ahora_utc() - timedelta(days=3)),
        m.OrdenServicio(folio="OS-1", unidad_id=u_orden.id, taller_id=ta.id, estado="abierta",
                        fecha_entrada=ahora_utc() - timedelta(days=2)),
    ])
    db.flush()
    return db, ta, tt


@caso("adentro junta croquis, ordenes y Excel, una vez por unidad")
def _():
    db, ta, _ = escenario()
    p = patios.patio(db, ta)
    por = {f["unidad"]: f for f in p["adentro"]}
    assert set(por) == {"100", "200", "300", "400"}, sorted(por)
    assert por["200"]["fuentes"] == ["croquis", "excel"] and por["200"]["espacio"] == "PATIO 7"
    assert por["200"]["dias"] == 10, "debe contar desde la entrada mas vieja (la del Excel)"
    assert por["400"]["orden"] == "OS-1" and por["400"]["fuentes"] == ["orden"]
    assert por["100"]["situacion"] == "Pendiente por compras" and por["100"]["falla"] == "FRENOS"
    assert [f["unidad"] for f in p["adentro"]][0] == "100", "la que mas dias lleva va primero"
    assert p["situaciones"]["En reparación"] == 1 and p["situaciones"]["Sin clasificar"] == 1


@caso("la flota es lo activo asignado a la planta, marcando lo que esta adentro")
def _():
    db, ta, tt = escenario()
    p = patios.patio(db, ta)
    flota = {u["unidad"]: u["adentro"] for u in p["flota"]}
    assert flota == {"100": True, "200": True, "400": True, "500": False}, flota
    t = patios.patio(db, tt)
    assert [u["unidad"] for u in t["flota"]] == ["300"] and t["adentro"] == []
    assert t["flota"][0]["adentro"] is False, "esta adentro de OTRA planta, no de la suya"


@caso("el selector cuenta adentro y flota de cada planta")
def _():
    db, ta, tt = escenario()
    lista = {x["nombre"]: (x["adentro"], x["flota"]) for x in patios.plantas(db)}
    assert lista == {"Alamos": (4, 4), "Tecate": (0, 1)}, lista


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
