"""Los numeros del taller, calculados de los movimientos.

Es la fuente de UNA sola verdad para las dos salidas: los graficos de pantalla y
el Excel que se descarga. Si las cubetas vivieran en dos archivos, el dia que
alguien cambie un rango el Excel y la pantalla dirian cosas distintas -- que es
exactamente el problema que tiene hoy el area: su hoja Graficos no cuadra con su
hoja RESUMEN, que es su propia fuente, y llevan meses sin notarlo.

QUE NO SE PUEDE CALCULAR, Y POR QUE.

El archivo del area tiene una serie diaria de 204 columnas con el inventario del
patio dia por dia. Eso NO se reconstruye: su hoja REPARADO no anota la fecha de
SALIDA en el 98% de los registros, asi que no hay forma de saber que habia en el
patio un martes de marzo. Lo que si se puede es contar ENTRADAS por mes, porque
la fecha de ingreso existe en el 100% de los movimientos.

Para tener la serie historica de verdad hay que empezar a guardar una foto
diaria. Se puede, pero hacia atras no se recupera.
"""
import datetime

from sqlalchemy.orm import Session

from ... import models as m

# Las mismas cinco etiquetas que usa el area, en su orden.
POR_ESTADO = [
    (1, "Unidades por Ingresar"),
    (2, "Pendientes por Compras"),
    (3, "Proceso Reparacion"),
    (4, "Refacciones chinas"),
    (5, "Talleres Externos"),
]

# La ultima cubeta NO existe en el archivo del area: ellos cortan en 366 dias y
# meten ahi todo lo mas viejo. Separarla es lo que hace visible que hay unidades
# con mas de tres anos paradas, que es justo el caso que habria que mirar.
POR_ANTIGUEDAD = [
    ("de 1 a 30 dias", 0, 30, False),
    ("31 a 60 dias", 31, 60, False),
    ("61 a 90 dias", 61, 90, False),
    ("91 a 180 dias", 91, 180, False),
    ("181 a 366 dias", 181, 366, False),
    ("mas de 366 dias", 367, 10 ** 6, True),
]


def _dias(ingreso: datetime.date, hoy: datetime.date) -> int:
    return (hoy - ingreso).days


def movimientos(db: Session, taller: str | None = None):
    """Los movimientos del taller pedido, o de todos."""
    q = db.query(m.MovimientoTaller)
    if taller:
        q = q.filter(m.MovimientoTaller.area == taller.upper())
    return q.all()


def calcular(db: Session, taller: str | None = None,
             hoy: datetime.date | None = None) -> dict:
    hoy = hoy or datetime.date.today()
    todos = movimientos(db, taller)
    adentro = [x for x in todos if x.sigue_adentro]

    por_estado = [{"etiqueta": etq,
                   "cuantas": sum(1 for x in adentro if x.clasificacion == cod)}
                  for cod, etq in POR_ESTADO]
    sin_clasificar = sum(1 for x in adentro if x.clasificacion is None)
    if sin_clasificar:
        por_estado.append({"etiqueta": "(sin clasificar)", "cuantas": sin_clasificar})

    por_antiguedad = [
        {"etiqueta": etq, "alerta": alerta,
         "cuantas": sum(1 for x in adentro if desde <= _dias(x.fecha_ingreso, hoy) <= hasta)}
        for etq, desde, hasta, alerta in POR_ANTIGUEDAD]

    areas = {}
    for x in adentro:
        clave = x.uso or "(sin area)"
        areas[clave] = areas.get(clave, 0) + 1
    por_area = [{"etiqueta": k, "cuantas": v}
                for k, v in sorted(areas.items(), key=lambda p: -p[1])]

    meses = {}
    for x in todos:
        clave = f"{x.fecha_ingreso:%Y-%m}"
        meses[clave] = meses.get(clave, 0) + 1
    entradas = [{"etiqueta": k, "cuantas": v} for k, v in sorted(meses.items())][-12:]

    # Unidades que vuelven una y otra vez. Es la pregunta que el Excel no puede
    # contestar, porque contarlo a mano sobre 1,869 renglones no lo hace nadie.
    visitas = {}
    for x in todos:
        clave = x.unidad_texto or (x.unidad.num_economico if x.unidad else "?")
        visitas[clave] = visitas.get(clave, 0) + 1
    reincidentes = [{"etiqueta": k, "cuantas": v}
                    for k, v in sorted(visitas.items(), key=lambda p: -p[1])[:8]]

    dias_adentro = [_dias(x.fecha_ingreso, hoy) for x in adentro]
    mas_vieja = max(adentro, key=lambda x: _dias(x.fecha_ingreso, hoy)) if adentro else None

    return {
        "hoy": hoy.isoformat(),
        "taller": taller,
        "en_patio": len(adentro),
        "dias_promedio": round(sum(dias_adentro) / len(dias_adentro), 1) if dias_adentro else 0,
        "mas_vieja": ({"unidad": mas_vieja.unidad_texto,
                       "dias": _dias(mas_vieja.fecha_ingreso, hoy),
                       "desde": mas_vieja.fecha_ingreso.isoformat()}
                      if mas_vieja else None),
        "movimientos_totales": len(todos),
        "por_estado": por_estado,
        "por_antiguedad": por_antiguedad,
        "por_area": por_area,
        "entradas_por_mes": entradas,
        "reincidentes": reincidentes,
    }
