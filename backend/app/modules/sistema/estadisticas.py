"""RF-GER-14 a 18: el eje de tiempo del tablero del gerente.

El tablero de hoy ensena el AHORA: ocupacion, unidades paradas, piezas en
camino. Util, pero no contesta "como vamos" -- y eso fue lo que el cliente pidio
en la junta: los mismos indicadores por dia, por mes y por ano, y en graficos.

DE DONDE SALE CADA SERIE, y por que de ahi:

  entradas al taller   MovimientoTaller.fecha_ingreso   1,918 registros desde
                       2021. Es el unico historico largo que existe.
  preventivos          ProgramaMantenimiento.fecha_cumplimiento
                       El compromiso tecnico cumplido, no la cita (ver RN-12).
  citas / faltas       CitaTaller.fecha_cita + estado
                       Confirmadas contra las que terminaron en no_asistio.
  amonestaciones       Amonestacion.fecha_emision, sin contar las anuladas.
  averias              ReporteAveria.fecha_hora

LO QUE NO SE PUEDE, y conviene no prometerlo: la ocupacion del patio dia por
dia hacia atras. El 98% del historial importado no trae fecha de SALIDA, asi
que no hay forma de saber que habia adentro un martes de marzo de 2024. Se
puede desde hoy, guardando una foto diaria; hacia atras no se recupera.
"""
import datetime

from sqlalchemy.orm import Session

from ... import models as m

GRANULARIDADES = ("dia", "mes", "anio")


def _clave(f, gran: str) -> str | None:
    """La etiqueta del periodo al que cae una fecha."""
    if f is None:
        return None
    if isinstance(f, datetime.datetime):
        f = f.date()
    if gran == "dia":
        return f.isoformat()
    if gran == "mes":
        return "%04d-%02d" % (f.year, f.month)
    return "%04d" % f.year


def _periodos(gran: str, cuantos: int, hasta: datetime.date) -> list:
    """Las etiquetas de los ultimos N periodos, en orden, incluyendo los vacios.

    Los vacios importan: un mes sin un solo preventivo es informacion, y si se
    omitiera la grafica lo escondería juntando los meses que si tuvieron.
    """
    fuera = []
    if gran == "dia":
        for i in range(cuantos - 1, -1, -1):
            fuera.append((hasta - datetime.timedelta(days=i)).isoformat())
    elif gran == "mes":
        y, mth = hasta.year, hasta.month
        for _ in range(cuantos):
            fuera.append("%04d-%02d" % (y, mth))
            mth -= 1
            if mth == 0:
                y, mth = y - 1, 12
        fuera.reverse()
    else:
        for i in range(cuantos - 1, -1, -1):
            fuera.append("%04d" % (hasta.year - i))
    return fuera


def _contar(filas, gran: str, campo: str, etiquetas: list) -> list:
    cuenta = {e: 0 for e in etiquetas}
    for x in filas:
        k = _clave(getattr(x, campo, None), gran)
        if k in cuenta:
            cuenta[k] += 1
    return [cuenta[e] for e in etiquetas]


def serie(db: Session, gran: str = "mes", cuantos: int = 12,
          hasta: datetime.date | None = None) -> dict:
    """Los indicadores del taller a lo largo del tiempo."""
    gran = gran if gran in GRANULARIDADES else "mes"
    cuantos = max(2, min(cuantos, 120))
    hasta = hasta or datetime.date.today()
    etiquetas = _periodos(gran, cuantos, hasta)

    movs = db.query(m.MovimientoTaller).all()
    progs = (db.query(m.ProgramaMantenimiento)
             .filter(m.ProgramaMantenimiento.fecha_cumplimiento.isnot(None)).all())
    citas = db.query(m.CitaTaller).all()
    faltas = [c for c in citas if c.estado == "no_asistio"]
    confirmadas = [c for c in citas if c.estado in ("confirmada", "cumplida", "no_asistio")]
    amon = [a for a in db.query(m.Amonestacion).all() if a.estado != "anulada"]
    averias = db.query(m.ReporteAveria).all()

    series = [
        {"clave": "entradas", "nombre": "Entradas al taller",
         "datos": _contar(movs, gran, "fecha_ingreso", etiquetas)},
        {"clave": "preventivos", "nombre": "Preventivos cumplidos",
         "datos": _contar(progs, gran, "fecha_cumplimiento", etiquetas)},
        {"clave": "citas", "nombre": "Citas confirmadas",
         "datos": _contar(confirmadas, gran, "fecha_cita", etiquetas)},
        {"clave": "faltas", "nombre": "Faltas a cita",
         "datos": _contar(faltas, gran, "fecha_cita", etiquetas)},
        {"clave": "amonestaciones", "nombre": "Amonestaciones",
         "datos": _contar(amon, gran, "fecha_emision", etiquetas)},
        {"clave": "averias", "nombre": "Averias reportadas",
         "datos": _contar(averias, gran, "fecha_hora", etiquetas)},
    ]
    return {"granularidad": gran, "hasta": hasta.isoformat(),
            "etiquetas": etiquetas, "series": series}


def _nombre(db: Session, usuario_id) -> str | None:
    u = db.query(m.Usuario).filter(m.Usuario.id == usuario_id).first()
    return u.nombre_completo if u else None


def cumplimiento_choferes(db: Session, gran: str = "mes", cuantos: int = 6,
                          hasta: datetime.date | None = None,
                          limite: int = 25) -> dict:
    """RF-GER-17: el cumplimiento de cada chofer, cortado por mes o por ano.

    Se mide sobre CITAS, no sobre programas: el chofer responde por presentarse
    a la cita que le confirmaron. Si el taller nunca se la dio, no aparece aqui
    -- y esa es la diferencia entre medir al chofer y medir al taller.

    Se mide contra el POSEEDOR de la unidad ese dia (RN-01), que es de donde
    sale `aviso.chofer_id`.
    """
    gran = gran if gran in GRANULARIDADES else "mes"
    hasta = hasta or datetime.date.today()
    etiquetas = _periodos(gran, max(1, min(cuantos, 36)), hasta)
    vivos = set(etiquetas)

    # La cita no guarda chofer: el responsable de una falta se sabe por el
    # aviso, que ya resolvio quien era el poseedor ese dia.
    avisos = db.query(m.AvisoIncumplimiento).all()
    falta_por_cita = {a.cita_id: a.chofer_id for a in avisos if a.cita_id}

    por_chofer: dict = {}
    for c in db.query(m.CitaTaller).all():
        k = _clave(c.fecha_cita, gran)
        if k not in vivos:
            continue
        if c.estado not in ("confirmada", "cumplida", "no_asistio"):
            continue
        ch = falta_por_cita.get(c.id)
        if ch is None and c.estado == "no_asistio":
            continue                      # falta sin aviso: no se sabe de quien
        if ch is None:
            # Cita cumplida o vigente: responde el poseedor actual de la unidad.
            uni = db.query(m.Unidad).filter(m.Unidad.id == c.unidad_id).first()
            ch = uni.poseedor_chofer_id or uni.titular_chofer_id if uni else None
        if ch is None:
            continue
        d = por_chofer.setdefault(ch, {"confirmadas": 0, "cumplidas": 0, "faltas": 0})
        d["confirmadas"] += 1
        if c.estado == "cumplida":
            d["cumplidas"] += 1
        elif c.estado == "no_asistio":
            d["faltas"] += 1

    amon_por_chofer: dict = {}
    for a in db.query(m.Amonestacion).all():
        if a.estado == "anulada":
            continue
        if _clave(a.fecha_emision, gran) in vivos:
            amon_por_chofer[a.chofer_id] = amon_por_chofer.get(a.chofer_id, 0) + 1

    filas = []
    for ch, d in por_chofer.items():
        conf = d["confirmadas"]
        filas.append({
            "chofer_id": ch, "chofer": _nombre(db, ch),
            "confirmadas": conf, "cumplidas": d["cumplidas"], "faltas": d["faltas"],
            "amonestaciones": amon_por_chofer.get(ch, 0),
            "cumplimiento": round(100 * d["cumplidas"] / conf, 1) if conf else None,
        })
    # Primero los que peor van: es la lista que el gerente necesita ver.
    filas.sort(key=lambda x: (-x["faltas"], x["cumplimiento"] if x["cumplimiento"] is not None else 101))
    return {"granularidad": gran, "desde": etiquetas[0], "hasta": etiquetas[-1],
            "choferes": filas[:limite], "total_choferes": len(filas)}


def expediente(db: Session, chofer_id: int) -> dict:
    """RF-GER-16: el historial acumulado de un chofer.

    Sirve para dos cosas opuestas y las dos importan: sostener una amonestacion
    con historial, y DEFENDER al chofer al que el taller nunca le dio cita.
    """
    from ..mantenimiento import amonestacion_service as amon

    avisos = (db.query(m.AvisoIncumplimiento)
              .filter(m.AvisoIncumplimiento.chofer_id == chofer_id).all())
    citas_faltadas = {a.cita_id for a in avisos if a.cita_id}
    unidades = (db.query(m.Unidad)
                .filter((m.Unidad.poseedor_chofer_id == chofer_id)
                        | (m.Unidad.titular_chofer_id == chofer_id)).all())
    ids_unidad = [u.id for u in unidades]

    confirmadas = cumplidas = 0
    if ids_unidad:
        for c in (db.query(m.CitaTaller)
                  .filter(m.CitaTaller.unidad_id.in_(ids_unidad)).all()):
            if c.estado in ("confirmada", "cumplida", "no_asistio"):
                confirmadas += 1
            if c.estado == "cumplida":
                cumplidas += 1

    # Sin guardas `hasattr`: si un nombre de columna cambia, que reviente aqui y
    # no que devuelva 0 calladamente. Un cero falso en un expediente es peor que
    # un error -- se lee como "nunca recibio una unidad prestada".
    prestamos = (db.query(m.PrestamoUnidad)
                 .filter(m.PrestamoUnidad.chofer_recibe_id == chofer_id).count())
    averias = (db.query(m.ReporteAveria)
               .filter(m.ReporteAveria.chofer_id == chofer_id).count())

    h = amon.historial(db, chofer_id)
    return {
        "chofer_id": chofer_id,
        "chofer": _nombre(db, chofer_id),
        "unidades": [u.num_economico for u in unidades],
        "citas_confirmadas": confirmadas,
        "citas_cumplidas": cumplidas,
        "faltas": len(citas_faltadas),
        "cumplimiento": round(100 * cumplidas / confirmadas, 1) if confirmadas else None,
        "prestamos_recibidos": prestamos,
        "averias_reportadas": averias,
        "amonestaciones": h,
    }
