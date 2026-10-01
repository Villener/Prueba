"""El patio de cada planta, para el gerente: que unidades estan adentro y su flota.

Lo pidio el Lic. Tiscareno (2026-10-01): ver los patios con sus unidades, de
cada planta. "Adentro" se arma con TRES fuentes porque ninguna sola lo dice
todo, y cada fila dice de cual salio:

  - el croquis de la app (ocupacion_espacio): lo que Victor acomoda en una
    casilla. Es lo mas exacto, pero solo existe lo que alguien registro;
  - las ordenes de servicio abiertas del taller, aunque no tengan casilla;
  - el Excel RESUMEN del taller (movimiento_taller con sigue_adentro): la hoja
    PATIO que el area lleva a mano. Hoy es el UNICO dato real de patio, y solo
    lo manda Alamos.

Una unidad que sale en varias fuentes aparece una vez, con lo que sepa cada
una. La flota es todo lo activo que tiene esa planta como su taller asignado.
"""
from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import ahora_utc, dia_operativo

# La columna CLASIFICACION de la hoja PATIO (ver movimiento_model.py).
SITUACION = {1: "Por ingresar", 2: "Pendiente por compras", 3: "En reparación",
             4: "Refacciones chinas", 5: "Taller externo"}


def _planta_clave(db: Session, taller: m.Taller):
    p = db.get(m.Planta, taller.planta_id) if taller.planta_id else None
    return p.clave if p else None


def _adentro(db: Session, taller: m.Taller) -> list:
    hoy = dia_operativo(ahora_utc())
    filas: dict = {}

    def fila(u: m.Unidad) -> dict:
        if u.id not in filas:
            filas[u.id] = {"unidad_id": u.id, "unidad": u.num_economico,
                           "tipo": u.tipo.nombre if u.tipo else None,
                           "espacio": None, "orden": None, "falla": None,
                           "situacion": None, "desde": None, "dias": None, "fuentes": []}
        return filas[u.id]

    def desde(f: dict, fecha):
        if fecha and (f["desde"] is None or fecha < f["desde"]):
            f["desde"] = fecha
            f["dias"] = (hoy - fecha).days

    ocupaciones = (db.query(m.OcupacionEspacio)
                   .join(m.Espacio, m.Espacio.id == m.OcupacionEspacio.espacio_id)
                   .join(m.ZonaTaller, m.ZonaTaller.id == m.Espacio.zona_id)
                   .filter(m.ZonaTaller.taller_id == taller.id,
                           m.OcupacionEspacio.fecha_salida.is_(None)).all())
    for o in ocupaciones:
        f = fila(o.unidad)
        f["espacio"] = f"{o.espacio.zona.nombre} {o.espacio.numero}"
        f["fuentes"].append("croquis")
        desde(f, dia_operativo(o.fecha_entrada))

    for o in (db.query(m.OrdenServicio)
              .filter(m.OrdenServicio.taller_id == taller.id,
                      m.OrdenServicio.estado != "cerrada").all()):
        f = fila(o.unidad)
        f["orden"] = o.folio
        f["fuentes"].append("orden")
        desde(f, dia_operativo(o.fecha_entrada))

    clave = _planta_clave(db, taller)
    if clave:
        for mv in (db.query(m.MovimientoTaller)
                   .filter(m.MovimientoTaller.sigue_adentro.is_(True),
                           m.MovimientoTaller.area == clave).all()):
            f = fila(mv.unidad)
            f["falla"] = f["falla"] or mv.falla
            f["situacion"] = SITUACION.get(mv.clasificacion) or mv.estatus
            f["fuentes"].append("excel")
            desde(f, mv.fecha_ingreso)

    return sorted(filas.values(), key=lambda f: (-(f["dias"] or 0), f["unidad"]))


def _flota(db: Session, taller: m.Taller, adentro_ids: set) -> list:
    unidades = (db.query(m.Unidad)
                .filter(m.Unidad.activo.is_(True), m.Unidad.taller_asignado_id == taller.id)
                .order_by(m.Unidad.num_economico).all())
    titulares = {u.id: f"{u.nombre} {u.apellidos}" for u in db.query(m.Usuario).filter(
        m.Usuario.id.in_({x.titular_chofer_id for x in unidades if x.titular_chofer_id})).all()}
    return [{"unidad_id": u.id, "unidad": u.num_economico,
             "tipo": u.tipo.nombre if u.tipo else None,
             "estado": u.estado, "chofer": titulares.get(u.titular_chofer_id),
             "adentro": u.id in adentro_ids} for u in unidades]


def plantas(db: Session) -> list:
    """Una por taller, para el selector, con cuantas tiene adentro y en flota."""
    out = []
    for t in db.query(m.Taller).order_by(m.Taller.id).all():
        adentro = _adentro(db, t)
        flota = (db.query(m.Unidad)
                 .filter(m.Unidad.activo.is_(True), m.Unidad.taller_asignado_id == t.id).count())
        out.append({"taller_id": t.id, "nombre": t.nombre, "planta": _planta_clave(db, t),
                    "adentro": len(adentro), "flota": flota})
    return out


def patio(db: Session, taller: m.Taller) -> dict:
    adentro = _adentro(db, taller)
    flota = _flota(db, taller, {f["unidad_id"] for f in adentro})
    situaciones: dict = {}
    for f in adentro:
        k = f["situacion"] or "Sin clasificar"
        situaciones[k] = situaciones.get(k, 0) + 1
    estados: dict = {}
    for u in flota:
        estados[u["estado"]] = estados.get(u["estado"], 0) + 1
    return {"taller_id": taller.id, "nombre": taller.nombre, "planta": _planta_clave(db, taller),
            "adentro": adentro, "situaciones": situaciones,
            "flota": flota, "estados": estados,
            "sin_planta": (db.query(m.Unidad)
                           .filter(m.Unidad.activo.is_(True),
                                   m.Unidad.taller_asignado_id.is_(None)).count())}
