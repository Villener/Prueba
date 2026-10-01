"""Carga UNA sola vez los preventivos reales que Victor llevaba en Excel.

Hasta ahora las fechas de preventivo de cada unidad las invento el sistema:
meta_preventivo.generar_programas las reparte parejo porque no tenia ningun dato
real. Los Excel de Victor si lo tienen para una parte de la flota: que unidad se
atendio y cuando, y cual se quedo pendiente. Este importador mete ESE dato.

No lee los Excel directo: lee una lista ya revisada (CSV) con una fila por
unidad, armada a partir del analisis del 2026-09-30, usando solo GUAYCURA
PREVENTIVOS (1) y PREVENTIVOS DE ARTURO y dejando fuera lo dudoso (fechas mal
capturadas, sin marca, unidades inactivas). Lo que quedo fuera esta en
excluidos.csv, con su motivo, para que Victor lo revise.

    num_economico,estado,fecha,archivo,fila,unidad_excel
    BG365P,realizado,2026-07-28,PREVENTIVOS DE ARTURO (1).xlsx,15,BG-365P

Por cada unidad:
  - Sus programas vivos (los de fechas inventadas) se cancelan, y sus citas vivas
    tambien. fecha_limite no se edita nunca: se cierra y se crea otro.
  - realizado: un programa 'cumplido' en esa fecha, y el siguiente 'pendiente'
    a fecha + periodicidad del plan de su tipo (pipa 60, demas 90).
  - pendiente: un programa 'pendiente' con fecha limite = la fecha que Victor le
    habia puesto. Ya paso, asi que el job de las 06:00 lo marca vencido y la
    agenda lo pone primero.
Cada movimiento queda en la bitacora de auditoria con archivo y fila.

Dentro del contenedor de la API (va DESPUES de reset_produccion):

    python -m app.importadores.preventivos_reales --csv /datos/areas/preventivos_reales.csv
    python -m app.importadores.preventivos_reales --csv ... --aplicar

Sin --aplicar solo simula: hace todo y lo deshace. Con --aplicar deja la marca
`preventivos_reales_importados` y ya no vuelve a correr.
"""
import argparse
import csv
import datetime
import sys

from sqlalchemy.orm import Session

from .. import models as m
from ..core.security import registrar_bitacora
from ..core.tiempo import TZ_OPERACION, ahora_utc
from ..modules.mantenimiento import meta_preventivo
from ..modules.mantenimiento.plan_model import ESTADOS_PROGRAMA_VIVOS
from . import normaliza as n

MARCA = "preventivos_reales_importados"
ESTADOS = ("realizado", "pendiente")


def leer(ruta: str) -> list:
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _unidad(db: Session, texto: str):
    u = db.query(m.Unidad).filter(m.Unidad.num_economico == texto).first()
    if u:
        return u
    por_clave = {n.clave_unidad(x.num_economico): x for x in db.query(m.Unidad).all()}
    return n.resolver_unidad(n.clave_unidad(texto), por_clave)[0]


def _cerrar_inventados(db: Session, unidad: m.Unidad) -> int:
    vivos = (db.query(m.ProgramaMantenimiento)
             .filter(m.ProgramaMantenimiento.unidad_id == unidad.id,
                     m.ProgramaMantenimiento.estado.in_(ESTADOS_PROGRAMA_VIVOS)).all())
    for p in vivos:
        p.estado = "cancelado"
        for c in (db.query(m.CitaTaller)
                  .filter(m.CitaTaller.programa_mantenimiento_id == p.id,
                          m.CitaTaller.estado.in_(("propuesta", "confirmada",
                                                   "reprogramada"))).all()):
            c.estado = "cancelada"
    return len(vivos)


def cargar(db: Session, filas: list) -> dict:
    """Aplica las filas en la sesion. No hace commit: lo decide quien llama."""
    r = {"realizados": 0, "pendientes": 0, "inventados_cancelados": 0,
         "siguientes_creados": 0, "omitidas": []}
    for f in filas:
        estado = (f.get("estado") or "").strip().lower()
        try:
            fecha = datetime.date.fromisoformat((f.get("fecha") or "").strip())
        except ValueError:
            fecha = None
        if estado not in ESTADOS or fecha is None:
            r["omitidas"].append(f"{f.get('num_economico')}: estado o fecha invalidos")
            continue
        u = _unidad(db, (f.get("num_economico") or "").strip())
        if u is None or not u.activo:
            r["omitidas"].append(f"{f.get('num_economico')}: no existe o esta inactiva")
            continue
        plan = meta_preventivo.plan_vigente(db, u)
        if plan is None:
            r["omitidas"].append(f"{u.num_economico}: su tipo no tiene plan de preventivo")
            continue

        r["inventados_cancelados"] += _cerrar_inventados(db, u)
        origen = f"{f.get('archivo')} fila {f.get('fila')}: {estado} {fecha}"
        if estado == "realizado":
            # Mediodia de Tijuana: guardado en UTC sin recorrer el dia.
            hecho = datetime.datetime.combine(fecha, datetime.time(12)).replace(
                tzinfo=TZ_OPERACION)
            p = m.ProgramaMantenimiento(unidad_id=u.id, plan_id=plan.id,
                                        fecha_programada=fecha, fecha_limite=fecha,
                                        estado="cumplido", fecha_cumplimiento=hecho)
            db.add(p)
            db.flush()
            if meta_preventivo.crear_siguiente_programa(db, p) is not None:
                r["siguientes_creados"] += 1
            r["realizados"] += 1
        else:
            p = m.ProgramaMantenimiento(unidad_id=u.id, plan_id=plan.id,
                                        fecha_programada=fecha, fecha_limite=fecha,
                                        estado="pendiente")
            db.add(p)
            db.flush()
            r["pendientes"] += 1
        registrar_bitacora(db, None, "preventivo_real_importado", "programa_mantenimiento",
                           p.id, datos_despues=origen)
        db.flush()
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--csv", required=True)
    ap.add_argument("--aplicar", action="store_true", help="sin esto solo simula")
    args = ap.parse_args(argv)

    from ..core.database import SessionLocal
    filas = leer(args.csv)
    with SessionLocal() as db:
        if db.query(m.Configuracion).filter_by(clave=MARCA).first():
            print("Los preventivos reales ya se importaron. No se hace nada.")
            return 1
        r = cargar(db, filas)
        print(f"Filas: {len(filas)} | realizados {r['realizados']} | pendientes "
              f"{r['pendientes']} | siguientes creados {r['siguientes_creados']} | "
              f"programas inventados cancelados {r['inventados_cancelados']}")
        for o in r["omitidas"]:
            print("  omitida:", o)
        if not args.aplicar:
            db.rollback()
            print("SIMULACRO: no se guardo nada. Para guardar agrega --aplicar.")
            return 0
        db.add(m.Configuracion(clave=MARCA, valor=ahora_utc().isoformat(), tipo_dato="fecha",
                               descripcion="Carga unica de los preventivos reales de Victor"))
        db.commit()
        print("Guardado. Este importador ya no vuelve a correr.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
