"""RN-12: la meta de 5 a 7 unidades en mantenimiento preventivo por dia.

Es techo Y PISO, y el piso es lo que la hace distinta de una restriccion de
capacidad. Un dia con 3 preventivos no esta "dentro de capacidad": esta por
debajo de la meta, y el que incumplio es el taller. Esa distincion es la que
decide si un chofer que falto es responsable o no: si el taller lleva semanas
por debajo del piso, nunca hubo cupo para todos y el incumplimiento no le es
imputable (ver RN-14 y el diagrama de Victor).

DE DONDE SALE EL NUMERO.

De `programa_mantenimiento.fecha_cumplimiento`, no de las citas. La cita es la
promesa --puede moverse, cancelarse o quedar en "no_asistio"-- mientras que el
programa es el compromiso tecnico y guarda la fecha real en que el servicio se
dio por hecho. Contar citas cumplidas daria casi el mismo numero hoy, pero se
separaria el dia que alguien cierre un preventivo que entro sin cita, que es
justo el caso del arrastre de madrugada.

LO QUE ESTE MODULO NO PUEDE INVENTAR.

Si la flota no tiene programas cargados, aqui no hay nada que contar. Y hoy no
los tiene: son 4 programas para 1,367 unidades. Por eso `del_dia()` distingue
"cero preventivos" de "no hay programas": un tablero que dice 0 de 5 culpa al
taller de un hueco de datos, y eso es peor que no tener tablero.
"""
import datetime

from sqlalchemy.orm import Session

from ... import models as m

# Valores por omision de RN-12. Se pueden cambiar sin desplegar: viven en la
# tabla `configuracion` con estas claves.
CLAVE_MIN = "meta_preventivos_min"
CLAVE_MAX = "meta_preventivos_max"
META_MIN = 5
META_MAX = 7


def _entero(db: Session, clave: str, defecto: int) -> int:
    c = db.query(m.Configuracion).filter(m.Configuracion.clave == clave).first()
    try:
        return int(c.valor) if c else defecto
    except (TypeError, ValueError):
        return defecto


def banda(db: Session) -> tuple[int, int]:
    """El piso y el techo vigentes. Si alguien los invierte, se ordenan."""
    lo = _entero(db, CLAVE_MIN, META_MIN)
    hi = _entero(db, CLAVE_MAX, META_MAX)
    return (lo, hi) if lo <= hi else (hi, lo)


def _fecha(valor) -> datetime.date | None:
    """`fecha_cumplimiento` es datetime; la meta se mide por dia."""
    if valor is None:
        return None
    return valor.date() if isinstance(valor, datetime.datetime) else valor


def hay_programas(db: Session) -> int:
    return db.query(m.ProgramaMantenimiento).count()


def unidades_con_plan(db: Session) -> int:
    """Unidades activas cuyo tipo SI tiene un plan de mantenimiento vigente.

    Es el denominador honesto: contra el total de la flota saldria una cobertura
    artificialmente baja por las unidades que ningun plan cubre.
    """
    tipos = [p.tipo_unidad_id for p in
             db.query(m.PlanMantenimiento)
             .filter(m.PlanMantenimiento.activo.is_(True)).all()
             if p.tipo_unidad_id]
    if not tipos:
        return 0
    return (db.query(m.Unidad)
            .filter(m.Unidad.tipo_unidad_id.in_(tipos),
                    m.Unidad.activo.is_(True)).count())


def cobertura(db: Session) -> dict:
    """Que tanto de la flota tiene programa. Decide si la meta es medible.

    Con 4 programas para 714 unidades, contar "0 de 5" no mide al taller: mide
    un hueco de captura, y lo pinta de rojo como si fuera culpa suya. El umbral
    es deliberadamente generoso -- basta que un decimo de la flota este cargada
    para que el numero empiece a querer decir algo.
    """
    progs = hay_programas(db)
    universo = unidades_con_plan(db)
    frac = (progs / universo) if universo else 0.0
    return {"programas": progs, "unidades_con_plan": universo,
            "porcentaje": round(frac * 100, 1)}


def cumplidos_por_dia(db: Session, desde: datetime.date,
                      hasta: datetime.date) -> dict:
    """{fecha: cuantos} de los preventivos dados por cumplidos en el rango."""
    cuenta: dict = {}
    q = (db.query(m.ProgramaMantenimiento)
         .filter(m.ProgramaMantenimiento.fecha_cumplimiento.isnot(None)))
    for p in q.all():
        d = _fecha(p.fecha_cumplimiento)
        if d and desde <= d <= hasta:
            cuenta[d] = cuenta.get(d, 0) + 1
    return cuenta


def demanda_diaria(db: Session) -> dict:
    """Cuantos preventivos al dia PIDE la flota, por plan.

    Es la otra mitad de la meta y la que nadie mira: de nada sirve cumplir 5 al
    dia si la flota pide 9. Se calcula como unidades activas de cada tipo entre
    la periodicidad de su plan.
    """
    detalle = []
    total = 0.0
    planes = (db.query(m.PlanMantenimiento)
              .filter(m.PlanMantenimiento.activo.is_(True)).all())
    for plan in planes:
        if not plan.periodicidad_dias or not plan.tipo_unidad_id:
            continue
        unidades = (db.query(m.Unidad)
                    .filter(m.Unidad.tipo_unidad_id == plan.tipo_unidad_id,
                            m.Unidad.activo.is_(True)).count())
        porcion = unidades / plan.periodicidad_dias
        total += porcion
        detalle.append({"plan": plan.nombre, "unidades": unidades,
                        "cada_dias": plan.periodicidad_dias,
                        "al_dia": round(porcion, 2)})
    detalle.sort(key=lambda x: x["al_dia"], reverse=True)
    return {"al_dia": round(total, 1), "detalle": detalle}


def del_dia(db: Session, dia: datetime.date | None = None) -> dict:
    """El avance de hoy contra la meta, para el tablero del administrador."""
    dia = dia or datetime.date.today()
    lo, hi = banda(db)
    cob = cobertura(db)
    cumplidos = cumplidos_por_dia(db, dia, dia).get(dia, 0)

    agendados = (db.query(m.CitaTaller)
                 .filter(m.CitaTaller.fecha_cita == dia,
                         m.CitaTaller.programa_mantenimiento_id.isnot(None),
                         m.CitaTaller.estado.in_(["propuesta", "confirmada",
                                                  "reprogramada"]))
                 .count())

    # Medible solo si hay con que: ni siquiera `lo` programas en total, o menos
    # del 10% de la flota cargada, significa que el 0 es de captura y no de taller.
    if cob["programas"] < lo or cob["porcentaje"] < 10:
        estado = "sin_datos"
    elif cumplidos < lo:
        estado = "bajo"
    elif cumplidos > hi:
        estado = "sobre"
    else:
        estado = "dentro"

    return {
        "fecha": dia.isoformat(),
        "meta_min": lo,
        "meta_max": hi,
        "cumplidos": cumplidos,
        "agendados_pendientes": agendados,
        "faltan_para_el_piso": max(0, lo - cumplidos),
        "estado": estado,
        "cobertura": cob,
        "demanda": demanda_diaria(db),
    }


def serie(db: Session, dias: int = 30,
          hasta: datetime.date | None = None) -> dict:
    """La tendencia de los ultimos dias, con los que quedaron bajo el piso.

    El dia de hoy se marca aparte y NO cuenta como incumplido: todavia no
    termina, y contarlo pintaria de rojo cada manana.
    """
    hasta = hasta or datetime.date.today()
    desde = hasta - datetime.timedelta(days=dias - 1)
    lo, hi = banda(db)
    cuenta = cumplidos_por_dia(db, desde, hasta)

    puntos = []
    bajo = 0
    for i in range(dias):
        d = desde + datetime.timedelta(days=i)
        n = cuenta.get(d, 0)
        es_hoy = d == hasta
        incumplido = (not es_hoy) and n < lo
        if incumplido:
            bajo += 1
        puntos.append({"fecha": d.isoformat(), "cumplidos": n,
                       "bajo_piso": incumplido, "es_hoy": es_hoy})

    cerrados = [p for p in puntos if not p["es_hoy"]]
    promedio = (round(sum(p["cumplidos"] for p in cerrados) / len(cerrados), 1)
                if cerrados else 0)
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "meta_min": lo, "meta_max": hi,
        "puntos": puntos,
        "dias_bajo_piso": bajo,
        "dias_evaluados": len(cerrados),
        "promedio": promedio,
        "cobertura": cobertura(db),
        "demanda": demanda_diaria(db),
    }
