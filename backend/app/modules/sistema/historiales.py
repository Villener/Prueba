"""Los cuatro historiales del gerente: por mecanico, por unidad, por chofer y por taller.

DE DONDE SALIO ESTE ARCHIVO. El administrador de taller ya asigna unidades a
mecanicos en el modulo de Reporte de Mantenimiento, pero ese dato se quedaba
adentro del formato: para saber que le toco a cada mecanico habia que abrir
reporte por reporte. El gerente pidio verlo desde SU modulo --todos los
mecanicos con su historial de preventivos y a que unidades fueron-- y de paso
el historial completo de cada unidad, de cada chofer y de cada taller.

Esto es la capa de CALCULO. No sabe de HTTP (eso es del _controller) ni arma
el Excel (eso es de un exportador que consume `tabla_para_excel()` de aqui
abajo, igual que exportar_tablero.py consume estadisticas.tablero_rango).
Esa separacion no es estetica: es la leccion que ya esta escrita en
exportar_tablero.py y en exportar_resumen.py. El dia que la pantalla y el Excel
calculen cada uno por su lado, van a discrepar, y cuando eso pasa el gerente
deja de creerle a los dos.


================================ EL DOBLE CAMINO ==============================

El trabajo de un mecanico llega por DOS tablas distintas y hay que contar las
dos, porque ninguna de las dos lo tiene completo:

  1) ActividadReporte.tecnico_id -> ReporteMantenimiento
     Es la columna "FIRMAS" del papel: que tecnico responde por cada uno de los
     diez sistemas del vehiculo. Hoy: 18 reportes (10 preventivos, 8
     correctivos), 180 actividades, 50 con tecnico.

  2) AsignacionTecnico.tecnico_id -> OrdenServicio
     Es la fila de procesos esperando (RF-ADM-06): a quien se le encargo la
     orden. Hoy: 27 asignaciones.

Y se solapan. `ReporteMantenimiento.orden_servicio_id` es una FK UNICA a
orden_servicio, asi que cuando el reporte esta ligado a una orden --15 de los 18
reportes de hoy lo estan-- el mismo paso por el taller existe por los dos lados.
Sumarlos sin mas le duplica los trabajos al mecanico y le repite las unidades.


CRITERIO DE DEDUPLICACION QUE SE ELIGIO, Y POR QUE ESE:

  UN TRABAJO = UN TECNICO EN UNA ESTANCIA.

  La ESTANCIA es el paso de la unidad por el taller, y se identifica por la
  ORDEN cuando el reporte esta ligado a una, y por el REPORTE cuando no lo esta
  (3 de los 18 de hoy: RM-2026-00001, RM-2026-00002 y RM-2026-00006).
  La llave de deduplicacion es entonces (tecnico_id, estancia).

  POR QUE POR (TECNICO, ESTANCIA) Y NO SOLO POR LA ORDEN COMPARTIDA. Porque los
  dos caminos NO nombran a la misma gente. Medido contra la base: la orden
  OS-2026-00010 trae el reporte RM-2026-00003, cuyas actividades las firma el
  tecnico 2, y trae ademas asignaciones de los tecnicos 3 y 12. Si se
  deduplicara "por orden" habria que quedarse con un camino y tirar el otro, y
  con eso desaparecerian dos mecanicos que si trabajaron esa unidad. Colapsar
  por tecnico dentro de la estancia junta lo que de verdad es lo mismo y no
  toca lo que no lo es.

  POR QUE NO POR (TECNICO, UNIDAD, DIA), que era la otra opcion. Porque el dia
  no es la unidad de trabajo del taller: una orden dura varios dias --y las hay
  de 30--, asi que la misma intervencion se partiria en tantos trabajos como
  dias tenga evidencia, y al reves, dos estancias distintas de la misma unidad
  el mismo dia se pegarian en una. La estancia, en cambio, es un hecho exacto:
  la FK es unica, "misma orden" no es una heuristica.

  LO QUE ADEMAS ARREGLA, Y QUE NO SE HABIA VISTO VENIR. La tabla
  asignacion_tecnico tiene filas REPETIDAS para el mismo par (tecnico, orden) en
  la base de verdad: son 27 asignaciones pero solo 22 pares distintos. El
  tecnico 2 aparece tres veces en la orden 3, y los tecnicos 1 y 13 dos veces
  cada uno. Contando filas, esos tres mecanicos salian con mas trabajo del que
  hicieron aunque el doble camino no existiera. La misma llave los colapsa.

  Y TAMBIEN COLAPSA LOS SISTEMAS. Un tecnico puede firmar varios sistemas del
  MISMO reporte (el tecnico 2 firma suspension y frenos en RM-2026-00003 y en
  RM-2026-00004). Eso es una visita a una unidad, no dos trabajos. Los sistemas
  se juntan en el campo `sistema` del renglon --"frenos, suspension"-- en vez de
  abrir dos renglones, porque el gerente esta leyendo a que unidades fue su
  gente, y diez renglones para una sola visita son ruido que esconde la
  siguiente visita.

  Al 21 de septiembre de 2026 el calculo da 70 trabajos distintos de 77 filas
  crudas (50 actividades con tecnico + 27 asignaciones).


================== OTRAS DECISIONES QUE NO SE VEN EN LA SALIDA ================

SE LISTAN TODOS LOS TECNICOS ACTIVOS, incluidos los que no tienen un solo
trabajo en el rango. Un mecanico en cero es informacion --puede ser que nadie le
asigna nada-- y omitirlo lo esconderia justo cuando hay que mirarlo. Van con
trabajos:0 y ultimo_trabajo:null. Son 42 tecnicos: 28 mecanicos, 7 carroceros,
3 electricistas, 3 gruas y 1 llantero, y 36 de ellos son ASISTIDO (no usan la
app; Erick captura lo suyo), asi que su trabajo llega SIEMPRE por captura de
otro. Esa es otra razon para no esconder al que sale en cero: el cero puede ser
que no le asignaron nada o que nadie lo tecleo, y las dos cosas se atienden.

EL RANGO SE COMPARA CONTRA EL DIA OPERATIVO DE TIJUANA, no contra la fecha UTC
cruda. fecha_entrada, fecha_salida, fecha_realizada y fecha_inicio son
UTCDateTime: una actividad hecha a las 17:30 del 30 de septiembre en el taller
esta guardada como las 00:30 del 1 de octubre en UTC, y compararla asi la saca
del mes que el gerente pidio. fecha_cita, fecha_ingreso y fecha_generacion son
columnas Date y se usan tal cual; pasarlas por dia_operativo() reventaria,
porque no son instantes.

DONDE NO HAY BASE PARA UN PROMEDIO O UN PORCENTAJE VA null, NUNCA 0. Es la misma
regla que ya respetan cumplimiento_choferes() y tablero_rango(): un 0.0 de dias
promedio afirma que se reparo en el acto y un 0% de cumplimiento pinta de
incumplido a quien no fallo a nada. En los CONTEOS el 0 si es legitimo: quiere
decir que hubo periodo y no hubo nada, que es un dato y no un hueco.

LAS LISTAS LARGAS SE ACOTAN Y SE DICE. Son 1,367 unidades y 442 choferes. Una
lista recortada en silencio se lee como "esto es todo lo que hay", que es peor
que no darla: el gerente concluye que la flota es mas chica de lo que es. Cada
respuesta trae `total` (lo que hay), `mostradas` (lo que va en el arreglo) y un
`aviso` en texto cuando los dos no coinciden.

HAY ORDENES SEMBRADAS PARA LA DEMOSTRACION (folio "DEMO-", ver sembrar_demo.py):
439 de las 463. No se tratan distinto --son ordenes validas y el tablero del
gerente vive de ellas-- pero explican por que el historial por mecanico cubre
muchisimas menos ordenes que el total: las DEMO no traen mecanico asignado.


=================== LO QUE EL MODELO REAL NO PERMITE DAR ======================

Tres cosas que se pidieron y que la base de hoy no puede sostener. Van dichas
aqui y en la propia respuesta, porque callarlas produce un numero que parece
bueno:

  movimiento_taller NO TIENE taller_id. Solo trae `area`, texto libre de la hoja
  del area: 1,902 filas dicen ALAMOS, 7 ROSARITO, 5 TECATE, 2 vienen vacias y 2
  dicen EXTERNO / TALLER EXTERNO, que no son ninguno de los seis talleres. El
  filtro por taller sobre las entradas es por lo tanto una coincidencia de TEXTO
  contra el nombre del taller en mayusculas, no una llave, y las 4 filas que no
  casan quedan fuera: la suma de entradas por taller no da el total, y eso es
  correcto, no un error de conteo.

  `chofer` NO TIENE num_empleado. Esa columna existe en `tecnico`, no en
  `chofer`; lo que el chofer tiene es num_licencia, turno, ruta y perfil. Se
  devuelve `num_empleado` en null para no romper el contrato y se agrega
  `num_licencia` al lado con el dato que si existe. Poner la licencia debajo de
  un encabezado que dice "numero de empleado" seria etiquetar mal un dato real,
  que es la forma mas dificil de detectar de mentir.

  LA OCUPACION DE UN TALLER ES DE HOY, NO DEL RANGO. `Espacio.estado` es el
  estado de AHORA y no hay foto diaria guardada; es la misma limitacion que ya
  esta escrita en estadisticas.py e indicadores.py --el 98% del historial
  importado no trae fecha de salida, asi que no se sabe que habia adentro un
  martes de marzo--. Los tres campos de espacios del historial por taller son la
  foto del momento en que se consulto, y la respuesta lo dice en `aviso`.
"""
import datetime

from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import ahora_utc, dia_operativo
from ..taller.taller_service import orden_out

TIPOS = ("preventivo", "correctivo", "todos")
DIMENSIONES = ("mecanicos", "unidades", "choferes", "talleres")

# Cuantas filas devuelve como mucho un listado. 500 y no un numero mas chico por
# una razon medida: son 442 choferes y TIENEN QUE CABER TODOS. Con un tope de
# 300 la lista se cortaba justo donde estan los que no tuvieron ninguna cita --
# van hasta abajo porque se ordena por faltas -- y esos son precisamente los que
# hay que poder ver: al chofer al que el taller nunca le dio cita no se le puede
# reclamar nada, y si no aparece no hay como demostrarlo. Sigue siendo un tope
# para que "todas las unidades de 2021 a 2026" no devuelva los 1,367 renglones
# que el navegador arrastra y que nadie lee; cuando recorta, lo dice.
TOPE_FILAS = 500

# La linea de tiempo de UNA unidad. La 1002 aparece 18 veces solo en
# movimiento_taller, y sumando ordenes, citas y averias un historico de cinco
# anos pasa de los cien eventos. 400 cubre de sobra el caso peor conocido.
TOPE_EVENTOS = 400

# Cuantas ordenes se detallan en el historial de un taller. Es bajo a proposito
# y la razon esta en orden_out(): esa funcion resuelve en que cajon esta la
# unidad y eso le cuesta varias consultas POR ORDEN. Medido: el detalle de
# Alamos con sus 94 ordenes son 330 consultas, o sea unas 3.5 por orden. Se
# reusa igual --tener dos maneras de armar la misma salida es exactamente como
# la pantalla del administrador y la del gerente acaban mostrando distinto el
# mismo folio-- pero entonces la lista se ACOTA a 100, que deja el peor caso en
# unas 350 consultas en vez de las miles de un rango de cinco anos. Se prefirio
# acotar y decirlo antes que copiar orden_out() para hacerla mas rapida: la
# copia es la que termina divergiendo.
TOPE_ORDENES_TALLER = 100

# Cuantas unidades se nombran en el renglon de un mecanico. El contrato pide 12.
# El conteo real va al lado en `unidades_distintas`, asi que la lista se lee como
# lo que es --una muestra-- y no como el total.
TOPE_UNIDADES_MUESTRA = 12


# --------------------------------------------------------------- utilidades -- #
def _fecha_op(valor):
    """La fecha de calendario a la que pertenece un valor de la base.

    Un datetime es un INSTANTE guardado en UTC y se convierte al dia operativo de
    Tijuana antes de compararlo (ver core/tiempo.py). Un date ya es una fecha de
    calendario --fecha_cita, fecha_ingreso, fecha_generacion-- y pasarlo por
    dia_operativo() no solo sobra: truena, porque no tiene hora que convertir.
    """
    if valor is None:
        return None
    if isinstance(valor, datetime.datetime):
        return dia_operativo(valor)
    return valor


def _rango(desde, hasta):
    """Normaliza las dos fechas del calendario que marco el gerente.

    Si vienen al reves se INTERCAMBIAN en vez de devolver un historial vacio. Es
    la misma decision que ya toma estadisticas._periodos_entre() y por la misma
    razon: el gerente se va a equivocar de calendario tarde o temprano, y una
    tabla en blanco no le dice que se equivoco --lo deja concluyendo que en ese
    rango no hubo movimiento, que es justo lo contrario de lo que pasa--.

    NO se reusa _periodos_entre() aunque resuelva esto mismo, porque esa funcion
    trae pegado el TOPE_PERIODOS de 370: recortar a 370 dias es lo correcto para
    una grafica de barras y es lo incorrecto para un historial, donde pedir cinco
    anos de una unidad es la consulta normal, no un abuso.
    """
    hoy = dia_operativo(ahora_utc())
    desde = desde or hasta or hoy
    hasta = hasta or desde
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _en(f, desde, hasta) -> bool:
    return f is not None and desde <= f <= hasta


def _dias(entrada, salida):
    """Dias completos entre dos fechas, o None si no se pueden medir.

    Devuelve None --y no 0-- cuando falta una de las dos o cuando la salida es
    anterior a la entrada. Lo segundo pasa de verdad (captura al reves o una
    fecha corregida a mano) y es la trampa que ya documenta tablero_rango(): un
    timedelta negativo trunca hacia abajo, asi que dos horas al reves dan -1 y
    una sola de esas arrastra el promedio del grupo entero.
    """
    if entrada is None or salida is None:
        return None
    d = (salida - entrada).days
    return d if d >= 0 else None


def _promedio(valores):
    """El promedio de una lista, o None si la lista esta vacia."""
    return round(sum(valores) / len(valores), 1) if valores else None


def _pct(parte: int, total: int):
    """El porcentaje, o None si no hay denominador. Nunca 0 por falta de base."""
    return round(100 * parte / total, 1) if total else None


def _distintos(valores) -> list:
    """Los valores no vacios, sin repetir y en el orden en que aparecieron."""
    return list(dict.fromkeys(v for v in valores if v))


def _aviso_recorte(total: int, mostradas: int, que: str):
    if total <= mostradas:
        return None
    return ("Se muestran %d de %d %s. Acote el rango o el taller para verlos "
            "todos." % (mostradas, total, que))


def _nombres_talleres(db: Session) -> dict:
    return {t.id: t.nombre for t in db.query(m.Taller).all()}


def _nombres_usuarios(db: Session, ids) -> dict:
    """Nombre por id de usuario, en UNA consulta.

    Se resuelve en bloque con un in_() y no llamando a comun_service.nombre_chofer
    dentro del bucle: esa funcion hace una consulta por nombre, y con 298 unidades
    con chofer eso son 298 viajes a la base para pintar una tabla.
    """
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    return {u.id: u.nombre_completo
            for u in db.query(m.Usuario).filter(m.Usuario.id.in_(ids)).all()}


# =========================================================== POR MECANICO === #
def _aportes(db: Session, desde: datetime.date, hasta: datetime.date,
             tipo: str = "todos", taller_id: int | None = None) -> dict:
    """Todo lo que los dos caminos dicen del trabajo de los tecnicos, ya filtrado.

    Devuelve {tecnico_id: [aporte, ...]}. Un aporte es UNA fila cruda --una
    actividad de reporte o una asignacion de orden-- todavia sin deduplicar; de
    juntarlos en trabajos se encarga _trabajos().

    Son DOS consultas para todo el universo de tecnicos, no dos por tecnico. Con
    42 tecnicos la diferencia entre agregar en memoria y consultar en el bucle es
    entre 2 viajes a la base y 84.

    EL `estado` SE DEJA EN EL VOCABULARIO DE SU CAMINO y no se traduce a uno
    comun. Del lado del reporte lo que existe es si la actividad quedo realizada
    o sigue pendiente; del lado de la orden existen en_espera, en_proceso y
    terminada. Forzar los dos a una sola escala inventaria un estado que nadie
    escribio -- una actividad "realizada" no es lo mismo que una asignacion
    "terminada", que ademas implica que el tecnico cerro su parte de la orden.
    """
    fuera: dict = {}

    def agregar(tecnico_id, ap):
        fuera.setdefault(tecnico_id, []).append(ap)

    # CAMINO 1: la columna de firmas del papel. El outerjoin con la orden es lo
    # que deja saber si este reporte comparte estancia con una orden --y cual--
    # sin una segunda consulta por reporte.
    filas = (db.query(m.ActividadReporte, m.ReporteMantenimiento, m.OrdenServicio)
             .join(m.ReporteMantenimiento,
                   m.ReporteMantenimiento.id == m.ActividadReporte.reporte_id)
             .outerjoin(m.OrdenServicio,
                        m.OrdenServicio.id == m.ReporteMantenimiento.orden_servicio_id)
             .filter(m.ActividadReporte.tecnico_id.isnot(None))
             .all())
    for a, r, o in filas:
        if taller_id and r.taller_id != taller_id:
            continue
        if tipo != "todos" and r.tipo_servicio != tipo:
            continue
        # La fecha del trabajo es cuando se hizo. Cuando la actividad no la trae
        # --3 de las 50 de hoy-- se cae a la entrada del reporte, que es la unica
        # fecha cierta de esa estancia. Descartar esas tres seria perder trabajo
        # que si existe solo porque el papel no anoto el dia.
        f = _fecha_op(a.fecha_realizada) or _fecha_op(r.fecha_entrada)
        if not _en(f, desde, hasta):
            continue
        agregar(a.tecnico_id, {
            "estancia": ("O", r.orden_servicio_id) if r.orden_servicio_id else ("R", r.id),
            "origen": "reporte", "fecha": f,
            "folio": r.folio, "folio_orden": o.folio if o else None,
            "unidad_id": r.unidad_id, "taller_id": r.taller_id,
            "tipo_servicio": r.tipo_servicio,
            "sistema": a.sistema,
            "actividad": a.realizada or a.a_realizar,
            "estado": "realizada" if a.realizada else "pendiente",
            "entrada": _fecha_op(o.fecha_entrada if o else r.fecha_entrada),
            "salida": _fecha_op(o.fecha_salida if o else r.fecha_salida),
        })

    # CAMINO 2: la fila de procesos esperando.
    filas = (db.query(m.AsignacionTecnico, m.OrdenServicio)
             .join(m.OrdenServicio,
                   m.OrdenServicio.id == m.AsignacionTecnico.orden_servicio_id)
             .all())
    for g, o in filas:
        if taller_id and o.taller_id != taller_id:
            continue
        if tipo != "todos" and o.tipo != tipo:
            continue
        # fecha_inicio es cuando el tecnico se puso; 14 de las 27 asignaciones de
        # hoy estan en_espera y no la tienen. Se cae a la fecha de asignacion --el
        # dia que se le encargo-- y despues a la entrada de la unidad. Un trabajo
        # encargado y no empezado sigue siendo parte del historial del mecanico:
        # es justo lo que el gerente quiere ver cuando algo lleva semanas parado.
        f = (_fecha_op(g.fecha_inicio) or _fecha_op(g.fecha_asignacion)
             or _fecha_op(o.fecha_entrada))
        if not _en(f, desde, hasta):
            continue
        agregar(g.tecnico_id, {
            "estancia": ("O", o.id),
            "origen": "orden", "fecha": f,
            "folio": o.folio, "folio_orden": o.folio,
            "unidad_id": o.unidad_id, "taller_id": o.taller_id,
            "tipo_servicio": o.tipo,
            "sistema": g.especialidad,
            "actividad": g.trabajo_realizado or g.diagnostico,
            "estado": g.estado,
            "entrada": _fecha_op(o.fecha_entrada),
            "salida": _fecha_op(o.fecha_salida),
        })

    return fuera


def _trabajos(aportes: list) -> list:
    """Colapsa los aportes de UN tecnico en trabajos. Aqui vive la deduplicacion.

    La llave es la estancia (ver el docstring del modulo): un tecnico en un paso
    de la unidad por el taller es UN trabajo, lo digan una tabla, la otra o las
    dos. Sale ordenado del mas reciente al mas viejo.

    CUANDO LA ESTANCIA APARECE POR LOS DOS CAMINOS MANDA EL REPORTE. No es
    arbitrario: el reporte dice QUE SISTEMA se toco y QUE se le hizo, y la
    asignacion solo dice la especialidad del tecnico. Quedarse con el renglon mas
    pobre de los dos seria tirar el dato que el gerente esta buscando. El folio de
    la orden no se pierde -- va en `folio_orden`, de modo que el renglon lleva los
    dos papeles y se puede ir a buscar cualquiera de los dos.
    """
    grupos: dict = {}
    for ap in aportes:
        grupos.setdefault(ap["estancia"], []).append(ap)

    fuera = []
    for grupo in grupos.values():
        del_reporte = [x for x in grupo if x["origen"] == "reporte"]
        base = del_reporte or grupo
        cab = base[0]
        fuera.append({
            # La fecha del trabajo es la MAS RECIENTE de sus evidencias: la
            # ultima vez que ese tecnico toco esa estancia. Asi `ultimo_trabajo`
            # de la lista es exactamente el maximo de estas fechas y no queda
            # corto, que es lo que pasaria tomando la primera.
            "fecha": max(x["fecha"] for x in grupo).isoformat(),
            "origen": cab["origen"],
            "folio": cab["folio"],
            "folio_orden": cab["folio_orden"],
            "unidad_id": cab["unidad_id"],
            "taller_id": cab["taller_id"],
            "tipo_servicio": cab["tipo_servicio"],
            # Los sistemas del mismo tecnico en el mismo reporte se juntan en un
            # solo renglon: "frenos, suspension" es una visita, no dos trabajos.
            "sistema": ", ".join(_distintos(x["sistema"] for x in base)) or None,
            "actividad": " | ".join(_distintos(x["actividad"] for x in base)) or None,
            "estado": cab["estado"],
            "entrada": cab["entrada"],
            "salida": cab["salida"],
            # Que esta misma estancia venia por los dos caminos. Se marca en vez
            # de callarse porque es la unica forma de que alguien pueda auditar
            # despues por que la suma de filas crudas no da el numero de trabajos.
            "por_ambos_caminos": bool(del_reporte) and len(del_reporte) < len(grupo),
        })
    fuera.sort(key=lambda x: x["fecha"], reverse=True)
    return fuera


def _resumen_trabajos(trabajos: list) -> dict:
    """Los conteos de un juego de trabajos ya deduplicado.

    OJO CON LA SUMA: trabajos NO siempre es preventivos + correctivos. Las
    ordenes de servicio admiten un tercer tipo, "siniestro" (hay una en la base),
    que no es ninguno de los dos y que con tipo="todos" cuenta como trabajo pero
    en ninguna de las dos columnas. Repartirla a la fuerza en una de ellas seria
    inventar; dejar el hueco visible es lo correcto.
    """
    unidades = _distintos(t["unidad_id"] for t in trabajos)
    duraciones = [d for d in (_dias(t["entrada"], t["salida"]) for t in trabajos)
                  if d is not None]
    return {
        "trabajos": len(trabajos),
        "preventivos": sum(1 for t in trabajos if t["tipo_servicio"] == "preventivo"),
        "correctivos": sum(1 for t in trabajos if t["tipo_servicio"] == "correctivo"),
        "unidades_distintas": len(unidades),
        # Cuanto duraron en el taller las estancias que atendio, contando solo las
        # que ya cerraron. Sin estancias cerradas va null: un 0.0 afirmaria que
        # sus reparaciones salieron el mismo dia, que es una medicion, no un hueco.
        "dias_promedio": _promedio(duraciones),
        "_unidades": unidades,
        "_ultimo": max((t["fecha"] for t in trabajos), default=None),
    }


def _num_economicos(db: Session, ids) -> dict:
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    return {u.id: u.num_economico
            for u in db.query(m.Unidad).filter(m.Unidad.id.in_(ids)).all()}


def historial_mecanicos(db: Session, desde: datetime.date, hasta: datetime.date,
                        tipo: str = "todos", taller_id: int | None = None) -> dict:
    """Todos los mecanicos con su trabajo en el rango, y a que unidades fueron.

    Es la pantalla que pidio el gerente: la lista completa de su gente tecnica,
    cuanto hizo cada uno, cuanto de eso fue preventivo y en que unidades anduvo.

    ENTRAN TODOS LOS TECNICOS ACTIVOS, tengan o no trabajo en el rango. Ver la
    nota del docstring del modulo: un mecanico en cero es la informacion, no el
    faltante.

    EL FILTRO POR TALLER acota el TRABAJO al taller pedido, y la lista de gente se
    arma con los tecnicos ADSCRITOS a ese taller MAS los que trabajaron ahi
    aunque esten adscritos a otro. Hacerlo solo por adscripcion dejaria fuera al
    autonomo que fue a ayudar a otra planta --y ese viaje es justo el que nadie
    tiene registrado hoy en ningun lado--; hacerlo solo por trabajo escondería al
    tecnico de la casa que no hizo nada, que es el caso que hay que mirar.
    """
    desde, hasta = _rango(desde, hasta)
    tipo = tipo if tipo in TIPOS else "todos"

    por_tecnico = _aportes(db, desde, hasta, tipo, taller_id)
    trabajos = {tid: _trabajos(aps) for tid, aps in por_tecnico.items()}

    tecnicos = db.query(m.Tecnico).filter(m.Tecnico.activo.is_(True)).all()
    if taller_id:
        con_trabajo = set(trabajos)
        tecnicos = [t for t in tecnicos
                    if t.taller_id == taller_id or t.id in con_trabajo]

    talleres = _nombres_talleres(db)
    economicos = _num_economicos(
        db, [t["unidad_id"] for lista in trabajos.values() for t in lista])

    filas = []
    for t in tecnicos:
        res = _resumen_trabajos(trabajos.get(t.id, []))
        nombres = [economicos.get(uid) for uid in res.pop("_unidades")]
        ultimo = res.pop("_ultimo")
        filas.append({
            "tecnico_id": t.id,
            # nombre_completo es una @property de Tecnico, no una columna: se
            # arma en Python y por eso no se puede filtrar ni ordenar por ella en
            # SQL. El orden de la lista se decide aqui abajo, en memoria.
            "nombre": t.nombre_completo,
            "especialidad": t.especialidad,
            "modalidad": t.modalidad,
            "taller": talleres.get(t.taller_id),
            **res,
            "unidades": [n for n in nombres if n][:TOPE_UNIDADES_MUESTRA],
            "ultimo_trabajo": ultimo,
        })

    # Primero quien mas trabajo. Los de cero caen solos hasta abajo, que es donde
    # el gerente los va a encontrar juntos -- y verlos juntos es la lectura util:
    # si son quince, el problema no es de los mecanicos, es de como se reparte.
    filas.sort(key=lambda x: (-x["trabajos"], -x["preventivos"], x["nombre"]))
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "tipo": tipo, "taller_id": taller_id,
        "total": len(filas),
        "mecanicos": filas,
        "aviso": None,
    }


def historial_mecanico(db: Session, tecnico_id: int, desde: datetime.date,
                       hasta: datetime.date, tipo: str = "todos") -> dict | None:
    """El detalle de un mecanico: sus trabajos uno por uno, del mas reciente atras.

    Devuelve None si el tecnico no existe, para que el controlador conteste 404 y
    no un expediente vacio, que se leeria como "este mecanico no ha hecho nada".
    """
    desde, hasta = _rango(desde, hasta)
    tipo = tipo if tipo in TIPOS else "todos"

    t = db.query(m.Tecnico).filter(m.Tecnico.id == tecnico_id).first()
    if not t:
        return None

    trabajos = _trabajos(_aportes(db, desde, hasta, tipo).get(tecnico_id, []))
    res = _resumen_trabajos(trabajos)
    res.pop("_unidades")
    res.pop("_ultimo")

    talleres = _nombres_talleres(db)
    economicos = _num_economicos(db, [x["unidad_id"] for x in trabajos])

    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "tipo": tipo,
        "tecnico": {
            "tecnico_id": t.id, "nombre": t.nombre_completo,
            "especialidad": t.especialidad, "modalidad": t.modalidad,
            "taller": talleres.get(t.taller_id),
        },
        "resumen": res,
        "trabajos": [{
            "fecha": x["fecha"], "origen": x["origen"], "folio": x["folio"],
            "folio_orden": x["folio_orden"],
            "unidad": economicos.get(x["unidad_id"]),
            "taller": talleres.get(x["taller_id"]),
            "tipo_servicio": x["tipo_servicio"], "sistema": x["sistema"],
            "actividad": x["actividad"], "estado": x["estado"],
            "por_ambos_caminos": x["por_ambos_caminos"],
        } for x in trabajos],
    }


# ============================================================= POR UNIDAD === #
def _eventos_por_unidad(db: Session, desde: datetime.date, hasta: datetime.date,
                        taller_id: int | None = None,
                        unidad_id: int | None = None) -> dict:
    """Todo lo que le paso a las unidades en el rango, agrupado por unidad.

    Cinco consultas para toda la flota --movimientos, ordenes, reportes, citas y
    averias-- y la agregacion en memoria, igual que hace tablero_rango(). Con
    1,367 unidades y 1,918 movimientos, una consulta por unidad dentro del bucle
    serian casi siete mil viajes a la base para pintar una tabla.

    `unidad_id` acota las cinco consultas a una sola unidad y es lo que usa el
    detalle; sin el se traen todas, que es lo que usa el listado.
    """
    talleres = _nombres_talleres(db)
    # movimiento_taller no tiene taller_id (ver el docstring del modulo): el
    # filtro por taller sobre las entradas es una coincidencia de texto contra el
    # nombre en mayusculas, y las filas cuya area no casa con ningun taller
    # quedan fuera cuando el filtro esta puesto.
    area_taller = talleres.get(taller_id, "").upper() if taller_id else None

    fuera: dict = {}

    def ev(uid, **kw):
        fuera.setdefault(uid, []).append(kw)

    def acota(q, columna):
        return q.filter(columna == unidad_id) if unidad_id else q

    for x in acota(db.query(m.MovimientoTaller), m.MovimientoTaller.unidad_id).all():
        if area_taller and (x.area or "").upper() != area_taller:
            continue
        # fecha_ingreso es Date, no UTCDateTime: se usa tal cual.
        if not _en(x.fecha_ingreso, desde, hasta):
            continue
        ev(x.unidad_id, fecha=x.fecha_ingreso, tipo="entrada", folio=None,
           taller=x.area, detalle=x.falla, estado=x.estatus,
           # El apodo del mecanico tal como lo escribio el area ('RIVAS',
           # 'RESENDIZ'). movimiento_model.py lo dice con todas sus letras: en el
           # historico no viene el numero de empleado, asi que esto NO es una FK a
           # `tecnico` y no sirve para medir a nadie. Se muestra porque es la
           # unica pista de quien atendio esas 1,918 entradas, y se muestra como
           # texto para que se lea como lo que es.
           tecnico=x.mecanico_texto, uso=x.uso, salida=x.fecha_salida)

    for o in acota(db.query(m.OrdenServicio), m.OrdenServicio.unidad_id).all():
        if taller_id and o.taller_id != taller_id:
            continue
        # La orden se cuenta por su ENTRADA y no por su salida. Es a proposito
        # distinto de tablero_rango(), que la cuenta por la SALIDA porque ahi mide
        # cuando se libero el espacio. Aqui se esta contando la historia de la
        # unidad, y lo que le paso a la unidad fue ENTRAR ese dia: una orden que
        # entro en enero y sigue abierta no puede faltar del historial de enero
        # esperando a que cierre.
        f = _fecha_op(o.fecha_entrada)
        if not _en(f, desde, hasta):
            continue
        ev(o.unidad_id, fecha=f, tipo="orden", folio=o.folio,
           taller=talleres.get(o.taller_id), detalle=None, estado=o.estado,
           tecnico=None, tipo_servicio=o.tipo,
           dias=_dias(f, _fecha_op(o.fecha_salida)), orden_id=o.id)

    for r in acota(db.query(m.ReporteMantenimiento),
                   m.ReporteMantenimiento.unidad_id).all():
        if taller_id and r.taller_id != taller_id:
            continue
        f = _fecha_op(r.fecha_entrada)
        if not _en(f, desde, hasta):
            continue
        ev(r.unidad_id, fecha=f, tipo="reporte", folio=r.folio,
           taller=talleres.get(r.taller_id), detalle=r.notas_ingreso,
           estado=r.estado, tecnico=None, tipo_servicio=r.tipo_servicio,
           reporte_id=r.id)

    for c in acota(db.query(m.CitaTaller), m.CitaTaller.unidad_id).all():
        if taller_id and c.taller_id != taller_id:
            continue
        if not _en(c.fecha_cita, desde, hasta):
            continue
        ev(c.unidad_id, fecha=c.fecha_cita, tipo="cita", folio=None,
           taller=talleres.get(c.taller_id), detalle=None, estado=c.estado,
           tecnico=None)

    for a in acota(db.query(m.ReporteAveria), m.ReporteAveria.unidad_id).all():
        # La averia ocurre en la carretera, no en un taller: no tiene taller_id y
        # por eso el filtro por taller no la toca. Se queda en el historial de la
        # unidad porque es parte de lo que le paso, y quitarla cuando el gerente
        # filtra por taller le escondería el motivo de la entrada que si esta.
        f = _fecha_op(a.fecha_hora)
        if not _en(f, desde, hasta):
            continue
        ev(a.unidad_id, fecha=f, tipo="averia", folio=a.folio, taller=None,
           detalle=a.descripcion_falla, estado=a.estado, tecnico=None)

    return fuera


def _ficha_unidad(u, chofer: str | None) -> dict:
    return {
        "unidad_id": u.id, "num_economico": u.num_economico,
        "marca": u.marca, "modelo": u.modelo, "anio": u.anio,
        "placas": u.placas, "estado": u.estado, "chofer": chofer,
    }


def _resumen_unidad(eventos: list) -> dict:
    ordenes = [e for e in eventos if e["tipo"] == "orden"]
    citas = [e for e in eventos if e["tipo"] == "cita"]
    entradas = [e for e in eventos if e["tipo"] == "entrada"]
    duraciones = [e["dias"] for e in ordenes if e.get("dias") is not None]
    return {
        "entradas_taller": len(entradas),
        "ordenes": len(ordenes),
        "preventivos": sum(1 for e in ordenes if e.get("tipo_servicio") == "preventivo"),
        "correctivos": sum(1 for e in ordenes if e.get("tipo_servicio") == "correctivo"),
        "reportes": sum(1 for e in eventos if e["tipo"] == "reporte"),
        "citas": len(citas),
        "faltas": sum(1 for e in citas if e["estado"] == "no_asistio"),
        "averias": sum(1 for e in eventos if e["tipo"] == "averia"),
        # La suma de dias de las ordenes que YA CERRARON. Va null cuando no cerro
        # ninguna: un 0 diria que la unidad no paso ni un dia en el taller, y lo
        # que pasa cuando hay ordenes abiertas es exactamente lo contrario --
        # sigue adentro y todavia no se sabe cuanto va a durar.
        "dias_en_taller_total": sum(duraciones) if duraciones else None,
        # La ultima vez que la unidad entro, mirando los tres sucesos que son una
        # entrada: el movimiento del historico, la orden y el reporte de la pluma.
        # Tomarla solo de movimiento_taller la dejaria vieja para las unidades que
        # ya se registran con el sistema nuevo, que no escribe esa tabla.
        "ultima_entrada": max((e["fecha"] for e in eventos
                               if e["tipo"] in ("entrada", "orden", "reporte")),
                              default=None),
    }


def historial_unidades(db: Session, desde: datetime.date, hasta: datetime.date,
                       taller_id: int | None = None,
                       solo_con_actividad: bool = True,
                       limite: int = TOPE_FILAS) -> dict:
    """El historial de la flota en el rango, una linea por unidad.

    `solo_con_actividad` viene en True a proposito y es distinto del criterio de
    los mecanicos, donde el que sale en cero SI se lista. La diferencia importa:
    un mecanico sin trabajo asignado es una senal de gestion, pero de las 1,367
    unidades la enorme mayoria simplemente no piso el taller en el rango, y eso
    es lo normal --es una flota que trabaja, no una flota parada--. Una tabla
    donde el 90% de los renglones son ceros esconde el 10% que hay que mirar. En
    False se listan todas, para quien necesite el padron completo.
    """
    desde, hasta = _rango(desde, hasta)
    por_unidad = _eventos_por_unidad(db, desde, hasta, taller_id)

    unidades = db.query(m.Unidad).all()
    if solo_con_actividad:
        unidades = [u for u in unidades if por_unidad.get(u.id)]
    nombres = _nombres_usuarios(
        db, [u.poseedor_chofer_id or u.titular_chofer_id for u in unidades])

    filas = []
    for u in unidades:
        eventos = por_unidad.get(u.id, [])
        # El poseedor manda sobre el titular (RN-01): es quien la trae hoy y a
        # quien se le pregunta. Se cae al titular cuando no hay poseedor, igual
        # que hacen cumplimiento_choferes() y expediente(); hoy las 298 unidades
        # con chofer tienen los dos campos puestos, pero el modelo permite que
        # solo exista el titular y quedarse sin nombre seria perder al
        # responsable por una regla de preferencia.
        cid = u.poseedor_chofer_id or u.titular_chofer_id
        fila = _ficha_unidad(u, nombres.get(cid))
        # Unidad no tiene columna `area`: el area la escribe el taller en cada
        # movimiento (`uso`: PIPA, REPARTO, UTILITARIA, OPERACIONES) y en el
        # reporte de mantenimiento. Se toma la del movimiento mas reciente del
        # rango, que es el ultimo dato que alguien afirmo sobre esta unidad.
        usos = [e.get("uso") for e in sorted(eventos, key=lambda x: x["fecha"], reverse=True)
                if e["tipo"] == "entrada" and e.get("uso")]
        fila["area"] = usos[0] if usos else None
        res = _resumen_unidad(eventos)
        res["ultima_entrada"] = res["ultima_entrada"].isoformat() if res["ultima_entrada"] else None
        fila.update(res)
        filas.append(fila)

    # Las que mas pesan primero: mas entradas, mas ordenes. Es la lista de las
    # unidades que se estan comiendo el taller, que es la pregunta de atras.
    filas.sort(key=lambda x: (-x["entradas_taller"], -x["ordenes"],
                              x["num_economico"] or ""))
    limite = max(1, min(limite, TOPE_FILAS))
    mostradas = filas[:limite]
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "taller_id": taller_id, "solo_con_actividad": solo_con_actividad,
        "total": len(filas), "mostradas": len(mostradas),
        "unidades": mostradas,
        "aviso": _aviso_recorte(len(filas), len(mostradas), "unidades"),
    }


def historial_unidad(db: Session, unidad_id: int, desde: datetime.date,
                     hasta: datetime.date) -> dict | None:
    """La linea de tiempo de una unidad: todo lo que le paso, del ultimo al primero."""
    desde, hasta = _rango(desde, hasta)
    u = db.query(m.Unidad).filter(m.Unidad.id == unidad_id).first()
    if not u:
        return None

    eventos = _eventos_por_unidad(db, desde, hasta, None, unidad_id).get(unidad_id, [])

    # Quien atendio cada orden y cada reporte, en DOS consultas para toda la
    # unidad en vez de una por evento. Un historico de cinco anos de la 1002 son
    # decenas de eventos, y resolverlo evento por evento multiplica los viajes.
    ordenes_ids = [e["orden_id"] for e in eventos if e["tipo"] == "orden"]
    reportes_ids = [e["reporte_id"] for e in eventos if e["tipo"] == "reporte"]
    por_orden: dict = {}
    if ordenes_ids:
        for g, t in (db.query(m.AsignacionTecnico, m.Tecnico)
                     .join(m.Tecnico, m.Tecnico.id == m.AsignacionTecnico.tecnico_id)
                     .filter(m.AsignacionTecnico.orden_servicio_id.in_(ordenes_ids)).all()):
            por_orden.setdefault(g.orden_servicio_id, []).append(t.nombre_completo)
    por_reporte: dict = {}
    if reportes_ids:
        for a, t in (db.query(m.ActividadReporte, m.Tecnico)
                     .join(m.Tecnico, m.Tecnico.id == m.ActividadReporte.tecnico_id)
                     .filter(m.ActividadReporte.reporte_id.in_(reportes_ids)).all()):
            por_reporte.setdefault(a.reporte_id, []).append(t.nombre_completo)

    nombres = _nombres_usuarios(db, [u.poseedor_chofer_id or u.titular_chofer_id])
    res = _resumen_unidad(eventos)
    res["ultima_entrada"] = res["ultima_entrada"].isoformat() if res["ultima_entrada"] else None

    eventos.sort(key=lambda x: x["fecha"], reverse=True)
    linea = []
    for e in eventos[:TOPE_EVENTOS]:
        tecnico = e.get("tecnico")
        if e["tipo"] == "orden":
            tecnico = ", ".join(_distintos(por_orden.get(e["orden_id"], []))) or None
        elif e["tipo"] == "reporte":
            tecnico = ", ".join(_distintos(por_reporte.get(e["reporte_id"], []))) or None
        linea.append({
            "fecha": e["fecha"].isoformat(), "tipo": e["tipo"], "folio": e["folio"],
            "taller": e["taller"], "detalle": e["detalle"], "estado": e["estado"],
            "tecnico": tecnico,
        })

    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "unidad": _ficha_unidad(u, nombres.get(u.poseedor_chofer_id
                                               or u.titular_chofer_id)),
        "resumen": res,
        "eventos": linea,
        "total_eventos": len(eventos),
        "aviso": _aviso_recorte(len(eventos), len(linea), "eventos"),
    }


# ============================================================= POR CHOFER === #
def _citas_por_chofer(db: Session, desde: datetime.date, hasta: datetime.date,
                      poseedor: dict, falta_por_cita: dict) -> dict:
    """Las citas del rango repartidas entre sus responsables, por chofer.

    ES LA UNICA PUERTA A ESA ATRIBUCION, y por eso esta aqui afuera en vez de
    adentro del bucle que la usaba. La lista de choferes cuenta citas con esta
    regla y la hoja de detalle del Excel enumera esas mismas citas: si cada una
    resolviera por su cuenta de quien es la falta, bastaria con que alguien
    tocara una para que el renglon del chofer dijera 3 faltas y su detalle
    listara 4. El gerente que encuentre eso una vez no vuelve a creerle a
    ninguna de las dos pantallas.

    La regla es la de cumplimiento_choferes(): manda el AVISO, porque ya resolvio
    quien poseia la unidad ESE dia y una unidad cambia de manos; la cita sin
    aviso se le carga al poseedor de hoy. Y una falta SIN aviso no se le carga a
    nadie -- se descarta, porque endosarsela al poseedor actual seria acusar a
    quien a lo mejor ni traia la unidad ese dia.
    """
    fuera: dict = {}
    for c in db.query(m.CitaTaller).all():
        if not _en(c.fecha_cita, desde, hasta):
            continue
        if c.estado not in ("confirmada", "cumplida", "no_asistio"):
            continue
        cid = falta_por_cita.get(c.id)
        if cid is None and c.estado == "no_asistio":
            continue
        if cid is None:
            cid = poseedor.get(c.unidad_id)
        if cid is None:
            continue
        fuera.setdefault(cid, []).append({
            "cita_id": c.id, "unidad_id": c.unidad_id,
            "fecha": c.fecha_cita, "estado": c.estado,
            "taller_id": c.taller_id,
            "veces_reprogramada": c.veces_reprogramada,
            # De donde salio la atribucion. Va en el dato y no solo en este
            # comentario porque es lo primero que alguien va a querer saber
            # cuando un chofer reclame una falta que dice que no es suya.
            "por_aviso": c.id in falta_por_cita,
        })
    for lista in fuera.values():
        lista.sort(key=lambda x: x["fecha"], reverse=True)
    return fuera


def historial_choferes(db: Session, desde: datetime.date, hasta: datetime.date,
                       limite: int = TOPE_FILAS) -> dict:
    """Los choferes y su cumplimiento en el rango.

    LA ATRIBUCION ES LA MISMA QUE YA USA cumplimiento_choferes(), copiada paso a
    paso y no reinventada: la falta se le carga al chofer que dice el AVISO
    --porque el aviso ya resolvio quien era el poseedor ESE dia, y una unidad
    cambia de manos-- y la cita sin aviso se le carga al poseedor actual. Tener
    dos criterios de atribucion vivos en la misma aplicacion es como se llega a
    que dos pantallas del gerente den numeros distintos del mismo chofer, y la
    primera vez que eso pasa se acabo la confianza en las dos.

    EL PORCENTAJE SOLO CUENTA CITAS CON DESENLACE, cumplidas mas faltas. Una cita
    confirmada que todavia no llega no es un incumplimiento, y meterla en el
    denominador pintaba de 0% a quien no habia fallado a nada -- que es lo que
    aparecio con los datos reales cuando se hizo al reves.

    SE LISTAN TODOS LOS CHOFERES, incluidos los que no tuvieron una sola cita en
    el rango. Ese caso es el que expediente() existe para defender: al chofer al
    que el taller nunca le dio cita no se le puede reclamar nada, y si no
    apareciera en la lista no habria como demostrarlo. Van con citas:0 y
    cumplimiento:null -- null y no 0%, porque no fallo: no le tocaba nada.
    """
    desde, hasta = _rango(desde, hasta)

    choferes = db.query(m.Chofer).all()
    nombres = _nombres_usuarios(db, [c.usuario_id for c in choferes])

    unidades = db.query(m.Unidad).all()
    poseedor = {u.id: (u.poseedor_chofer_id or u.titular_chofer_id) for u in unidades}
    suyas: dict = {}
    for u in unidades:
        cid = poseedor.get(u.id)
        if cid:
            suyas.setdefault(cid, []).append(u.num_economico)

    falta_por_cita = {a.cita_id: a.chofer_id
                      for a in db.query(m.AvisoIncumplimiento).all() if a.cita_id}

    citas_de = _citas_por_chofer(db, desde, hasta, poseedor, falta_por_cita)

    datos: dict = {}
    for cid, lista in citas_de.items():
        d = datos.setdefault(cid, {"citas": 0, "cumplidas": 0, "faltas": 0,
                                   "pendientes": 0})
        for c in lista:
            d["citas"] += 1
            if c["estado"] == "cumplida":
                d["cumplidas"] += 1
            elif c["estado"] == "no_asistio":
                d["faltas"] += 1
            else:
                d["pendientes"] += 1

    averias: dict = {}
    for a in db.query(m.ReporteAveria).all():
        if _en(_fecha_op(a.fecha_hora), desde, hasta) and a.chofer_id:
            averias[a.chofer_id] = averias.get(a.chofer_id, 0) + 1

    amonestaciones: dict = {}
    for a in db.query(m.Amonestacion).all():
        if a.estado == "anulada":
            continue
        if _en(_fecha_op(a.fecha_emision), desde, hasta):
            amonestaciones[a.chofer_id] = amonestaciones.get(a.chofer_id, 0) + 1

    prestamos: dict = {}
    for p in db.query(m.PrestamoUnidad).all():
        # El prestamo cuenta el dia que EMPIEZA. Los que todavia no arrancan se
        # fechan por la solicitud, que es el unico dato que traen; contarlos por
        # la fecha de fin los mandaria a un rango en el que no habia pasado nada.
        f = _fecha_op(p.fecha_inicio) or _fecha_op(p.fecha_solicitud)
        if _en(f, desde, hasta):
            prestamos[p.chofer_recibe_id] = prestamos.get(p.chofer_recibe_id, 0) + 1

    filas = []
    for c in choferes:
        cid = c.usuario_id
        d = datos.get(cid, {"citas": 0, "cumplidas": 0, "faltas": 0, "pendientes": 0})
        resueltas = d["cumplidas"] + d["faltas"]
        filas.append({
            "chofer_id": cid,
            "nombre": nombres.get(cid),
            # `chofer` no tiene num_empleado -- esa columna es de `tecnico`. Se
            # deja la clave del contrato en null y se da al lado el numero que si
            # existe. Ver la nota del docstring del modulo.
            "num_empleado": None,
            "num_licencia": c.num_licencia,
            "turno": c.turno, "ruta": c.ruta,
            "unidades": sorted(suyas.get(cid, [])),
            "citas": d["citas"], "cumplidas": d["cumplidas"], "faltas": d["faltas"],
            "pendientes": d["pendientes"],
            "cumplimiento": _pct(d["cumplidas"], resueltas),
            "averias": averias.get(cid, 0),
            "amonestaciones": amonestaciones.get(cid, 0),
            "prestamos_recibidos": prestamos.get(cid, 0),
        })

    # Primero los que peor van, igual que cumplimiento_choferes(): es la lista
    # que el gerente necesita ver. El 101 para el null no es un puntaje: es lo
    # que manda al final a quien no tiene porcentaje, porque un chofer sin citas
    # no puede encabezar una lista de incumplimiento.
    filas.sort(key=lambda x: (-x["faltas"],
                              x["cumplimiento"] if x["cumplimiento"] is not None else 101,
                              x["nombre"] or ""))
    limite = max(1, min(limite, TOPE_FILAS))
    mostradas = filas[:limite]
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "total": len(filas), "mostradas": len(mostradas),
        "choferes": mostradas,
        "aviso": _aviso_recorte(len(filas), len(mostradas), "choferes"),
    }


def historial_chofer(db: Session, chofer_id: int, desde: datetime.date,
                     hasta: datetime.date) -> dict | None:
    """El expediente del chofer MAS la linea de tiempo del rango.

    EL EXPEDIENTE NO SE REIMPLEMENTA: se llama a estadisticas.expediente(), que ya
    resuelve las amonestaciones (via amonestacion_service.historial) y el criterio
    de cumplimiento. Reescribir aqui esas cuentas es la forma segura de que dos
    pantallas del gerente den porcentajes distintos del mismo chofer.

    OJO CON LOS DOS HORIZONTES, que es lo unico delicado de esta funcion.
    expediente() es ACUMULADO -- toda la vida del chofer, sin rango, y no admite
    uno --. La linea de tiempo que se le agrega encima SI esta acotada al rango
    que pidio el gerente. Son dos horizontes distintos en la misma respuesta, asi
    que van en dos llaves separadas y con nombre: `acumulado` y `rango`. Mezclarlos
    en un solo bloque plano dejaria al gerente restando el detalle del total y sin
    entender por que no cuadra.
    """
    from . import estadisticas

    desde, hasta = _rango(desde, hasta)
    c = db.query(m.Chofer).filter(m.Chofer.usuario_id == chofer_id).first()
    if not c:
        return None

    acumulado = estadisticas.expediente(db, chofer_id)

    talleres = _nombres_talleres(db)
    unidades = (db.query(m.Unidad)
                .filter((m.Unidad.poseedor_chofer_id == chofer_id)
                        | (m.Unidad.titular_chofer_id == chofer_id)).all())
    ids = [u.id for u in unidades]
    economicos = {u.id: u.num_economico for u in unidades}

    citas = []
    entradas = []
    if ids:
        for x in (db.query(m.CitaTaller)
                  .filter(m.CitaTaller.unidad_id.in_(ids)).all()):
            if _en(x.fecha_cita, desde, hasta):
                citas.append({"fecha": x.fecha_cita.isoformat(),
                              "unidad": economicos.get(x.unidad_id),
                              "taller": talleres.get(x.taller_id),
                              "estado": x.estado,
                              "veces_reprogramada": x.veces_reprogramada})
        # Las entradas a taller de SUS unidades en el rango. Es lo que contesta
        # "y mientras tanto, donde estuvo el vehiculo": un chofer al que se le
        # reclama una falta puede tener la unidad adentro del taller ese mismo
        # dia, y sin esta lista no hay forma de verlo.
        for x in (db.query(m.MovimientoTaller)
                  .filter(m.MovimientoTaller.unidad_id.in_(ids)).all()):
            if _en(x.fecha_ingreso, desde, hasta):
                entradas.append({"fecha": x.fecha_ingreso.isoformat(),
                                 "unidad": economicos.get(x.unidad_id),
                                 "taller": x.area, "detalle": x.falla,
                                 "estado": x.estatus})
        for o in (db.query(m.OrdenServicio)
                  .filter(m.OrdenServicio.unidad_id.in_(ids)).all()):
            f = _fecha_op(o.fecha_entrada)
            if _en(f, desde, hasta):
                entradas.append({"fecha": f.isoformat(),
                                 "unidad": economicos.get(o.unidad_id),
                                 "taller": talleres.get(o.taller_id),
                                 "detalle": o.folio, "estado": o.estado})

    citas.sort(key=lambda x: x["fecha"], reverse=True)
    entradas.sort(key=lambda x: x["fecha"], reverse=True)
    cumplidas = sum(1 for x in citas if x["estado"] == "cumplida")
    faltas = sum(1 for x in citas if x["estado"] == "no_asistio")

    return {
        "chofer_id": chofer_id,
        "nombre": acumulado["chofer"],
        "num_empleado": None,          # ver la nota del docstring del modulo
        "num_licencia": c.num_licencia,
        "turno": c.turno, "ruta": c.ruta, "perfil": c.perfil,
        "acumulado": acumulado,
        "rango": {
            "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "citas": len(citas), "cumplidas": cumplidas, "faltas": faltas,
            "cumplimiento": _pct(cumplidas, cumplidas + faltas),
            "entradas_taller": len(entradas),
            "unidades": sorted(economicos.values()),
        },
        "citas": citas,
        "entradas_taller": entradas,
        "aviso": ("Los totales de 'acumulado' son de toda la historia del chofer "
                  "y no del rango: expediente() no admite fechas. Lo que está "
                  "acotado a las fechas elegidas es el bloque 'rango' y las dos "
                  "listas de abajo."),
    }


# ============================================================= POR TALLER === #
def historial_talleres(db: Session, desde: datetime.date,
                       hasta: datetime.date) -> dict:
    """Los seis talleres y lo que paso en cada uno durante el rango.

    DOS ANCLAS DE FECHA DISTINTAS EN EL MISMO RENGLON, y conviene dejarlo escrito
    antes de que alguien lo "empareje":

      ordenes / preventivos / correctivos  se cuentan por la ENTRADA. Miden el
        trabajo que le LLEGO al taller en el rango, y una orden que entro y
        todavia no cierra es parte de esa carga.

      dias_promedio_reparacion  se calcula sobre las ordenes que CERRARON en el
        rango, que es exactamente el criterio de estadisticas.tablero_rango().
        Tiene que serlo: si el mismo gerente ve 4.2 dias en la pestaña de
        Indicadores y 3.1 aqui, ya no le cree a ninguna de las dos pantallas.

    Por eso el promedio no se saca de las mismas ordenes que se contaron arriba,
    y por eso `ordenes_cerradas` va tambien en el renglon: es el denominador del
    promedio, y sin verlo el numero flota.

    LOS TRES CAMPOS DE ESPACIOS SON LA FOTO DE HOY, no del rango. Espacio.estado
    es el estado actual y no existe foto diaria guardada -- la misma limitacion
    que ya documentan estadisticas.py e indicadores.py --. Va dicho en `aviso`.
    """
    desde, hasta = _rango(desde, hasta)
    talleres = db.query(m.Taller).filter(m.Taller.activo.is_(True)).all()
    vivos = {t.id for t in talleres}

    datos = {t.id: {"ordenes": 0, "preventivos": 0, "correctivos": 0,
                    "citas": 0, "reportes": 0, "unidades": [],
                    "duraciones": [], "cerradas": 0}
             for t in talleres}

    for o in db.query(m.OrdenServicio).all():
        if o.taller_id not in vivos:
            continue
        d = datos[o.taller_id]
        entrada = _fecha_op(o.fecha_entrada)
        salida = _fecha_op(o.fecha_salida)
        if _en(entrada, desde, hasta):
            d["ordenes"] += 1
            if o.tipo == "preventivo":
                d["preventivos"] += 1
            elif o.tipo == "correctivo":
                d["correctivos"] += 1
            d["unidades"].append(o.unidad_id)
        if _en(salida, desde, hasta):
            dias = _dias(entrada, salida)
            if dias is not None:
                d["duraciones"].append(dias)
                d["cerradas"] += 1

    for r in db.query(m.ReporteMantenimiento).all():
        if r.taller_id in vivos and _en(_fecha_op(r.fecha_entrada), desde, hasta):
            datos[r.taller_id]["reportes"] += 1
            datos[r.taller_id]["unidades"].append(r.unidad_id)

    for c in db.query(m.CitaTaller).all():
        if c.taller_id in vivos and _en(c.fecha_cita, desde, hasta):
            datos[c.taller_id]["citas"] += 1

    tecnicos: dict = {}
    for t in db.query(m.Tecnico).filter(m.Tecnico.activo.is_(True)).all():
        tecnicos[t.taller_id] = tecnicos.get(t.taller_id, 0) + 1

    espacios = _espacios_por_taller(db)

    filas = []
    for t in talleres:
        d = datos[t.id]
        esp = espacios.get(t.id, {"totales": 0, "ocupados": 0})
        filas.append({
            "taller_id": t.id, "nombre": t.nombre, "tipo": t.tipo,
            "espacios_totales": esp["totales"],
            "espacios_ocupados": esp["ocupados"],
            # null y no 0 cuando el taller no tiene un solo cajon que cuente para
            # ocupacion. Es distinto de lo que devuelve /gerente/ocupacion, que
            # ahi da 0.0; se respeta la regla transversal de este modulo y se
            # deja anotado para que la diferencia no se lea como un defecto. Hoy
            # no se dispara: los seis talleres tienen espacios (31, 3, 3, 2, 2, 4).
            "ocupacion_pct": _pct(esp["ocupados"], esp["totales"]),
            "tecnicos": tecnicos.get(t.id, 0),
            "ordenes": d["ordenes"],
            "preventivos": d["preventivos"], "correctivos": d["correctivos"],
            "reportes": d["reportes"], "citas": d["citas"],
            "ordenes_cerradas": d["cerradas"],
            "dias_promedio_reparacion": _promedio(d["duraciones"]),
            "unidades_distintas": len(set(d["unidades"])),
        })

    filas.sort(key=lambda x: (-x["ordenes"], x["nombre"]))
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "total": len(filas), "talleres": filas,
        "aviso": ("Espacios totales, ocupados y ocupación son la foto de este "
                  "momento, no del rango: no se guarda una foto diaria del patio, "
                  "así que no se puede saber qué había adentro en una fecha "
                  "pasada. Los demás números sí corresponden al rango."),
    }


def _espacios_por_taller(db: Session) -> dict:
    """Cajones que cuentan para ocupacion, por taller, en UNA consulta.

    Solo las zonas con cuenta_para_ocupacion: el patio admite unidades pero no es
    capacidad de atencion, y el yonke y el area de lavado tampoco. Es el mismo
    criterio de /gerente/ocupacion y de espacios_libres_compatibles(); contarlos
    todos inflaria el indicador y haria ver holgura donde no la hay.
    """
    fuera: dict = {}
    filas = (db.query(m.Espacio, m.ZonaTaller)
             .join(m.ZonaTaller, m.ZonaTaller.id == m.Espacio.zona_id)
             .filter(m.ZonaTaller.cuenta_para_ocupacion.is_(True),
                     m.Espacio.activo.is_(True)).all())
    for e, z in filas:
        d = fuera.setdefault(z.taller_id, {"totales": 0, "ocupados": 0})
        d["totales"] += 1
        if e.estado == "ocupado":
            d["ocupados"] += 1
    return fuera


def historial_taller(db: Session, taller_id: int, desde: datetime.date,
                     hasta: datetime.date) -> dict | None:
    """El detalle de un taller: su gente y sus ordenes en el rango.

    LAS ORDENES SE ARMAN CON taller_service.orden_out(), la misma funcion que usa
    el modulo del administrador, en vez de con un serializador propio. Que la
    orden OS-2026-00010 se vea igual en la pantalla del administrador y en la del
    gerente no es cosmetico: cuando los dos estan hablando por telefono de la
    misma unidad, dos formatos distintos del mismo folio es como empiezan los
    malentendidos.

    Y POR ESO MISMO LA LISTA SE ACOTA. orden_out() resuelve el cajon ocupado con
    una consulta por orden; reusarla sin limite significa 94 consultas para
    Alamos en un rango corto y miles en uno de cinco anos. Se prefirio acotar y
    decirlo antes que copiar la funcion para hacerla mas rapida, porque la copia
    es la que termina divergiendo.

    Los tecnicos salen de historial_mecanicos() con el filtro de taller puesto,
    o sea de la MISMA deduplicacion que la pantalla de mecanicos: los numeros de
    un mecanico tienen que ser los mismos se entre por donde se entre.
    """
    desde, hasta = _rango(desde, hasta)
    t = db.query(m.Taller).filter(m.Taller.id == taller_id).first()
    if not t:
        return None

    resumen = None
    for fila in historial_talleres(db, desde, hasta)["talleres"]:
        if fila["taller_id"] == taller_id:
            resumen = fila
            break
    if resumen is None:
        # El taller existe pero esta dado de baja: historial_talleres() solo trae
        # los activos. Se contesta igual, con el resumen en ceros y el aviso,
        # porque consultar el historial de un taller cerrado es legitimo -- es
        # justo cuando se quiere saber que dejo pendiente.
        resumen = {"taller_id": t.id, "nombre": t.nombre, "ordenes": 0,
                   "preventivos": 0, "correctivos": 0, "citas": 0,
                   "reportes": 0, "ordenes_cerradas": 0,
                   "dias_promedio_reparacion": None, "unidades_distintas": 0,
                   "tecnicos": 0, "espacios_totales": 0, "espacios_ocupados": 0,
                   "ocupacion_pct": None}

    mecanicos = historial_mecanicos(db, desde, hasta, "todos", taller_id)["mecanicos"]
    # DOS CONTEOS DE TECNICOS EN LA MISMA RESPUESTA, y hay que nombrarlos los dos
    # o el gerente los ve discrepar y no sabe cual creer. Alamos hoy: `tecnicos`
    # dice 36 --los ADSCRITOS al taller-- y la lista trae 37, porque uno que esta
    # adscrito a otra planta trabajo aqui. Los dos numeros son correctos y miden
    # cosas distintas: cuanta gente tiene el taller, y cuanta gente paso por el.
    resumen = dict(resumen)
    resumen["tecnicos_listados"] = len(mecanicos)

    ordenes = [o for o in db.query(m.OrdenServicio)
               .filter(m.OrdenServicio.taller_id == taller_id).all()
               if _en(_fecha_op(o.fecha_entrada), desde, hasta)]
    ordenes.sort(key=lambda o: _fecha_op(o.fecha_entrada), reverse=True)
    detalle = [orden_out(db, o) for o in ordenes[:TOPE_ORDENES_TALLER]]

    # Los avisos se ACUMULAN en vez de quedarse con el primero. Antes el recorte
    # de la lista de ordenes pisaba la advertencia de que la ocupacion es la foto
    # de hoy: se perdia justo en el caso donde hay mas que explicar.
    avisos = [_aviso_recorte(len(ordenes), len(detalle), "órdenes")]
    if resumen["tecnicos_listados"] != resumen.get("tecnicos"):
        avisos.append("Se listan %d técnicos y el taller tiene %d adscritos: la "
                      "diferencia es gente de otra planta que trabajó aquí en el "
                      "rango." % (resumen["tecnicos_listados"], resumen.get("tecnicos") or 0))
    avisos.append("Espacios totales, ocupados y ocupación son la foto de este "
                  "momento, no del rango.")

    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "taller": {"taller_id": t.id, "nombre": t.nombre, "tipo": t.tipo,
                   "direccion": t.direccion, "opera_sabado": t.opera_sabado,
                   "activo": t.activo},
        "resumen": resumen,
        "tecnicos": mecanicos,
        "ordenes": detalle,
        "total_ordenes": len(ordenes),
        "aviso": " ".join(a for a in avisos if a),
    }


# =============================================================== EL EXCEL === #
# Tope de renglones de la hoja de detalle. Es mas alto que TOPE_FILAS porque
# aqui cada entidad aporta VARIOS renglones --una unidad con doce entradas son
# doce-- y cortar en 500 dejaria el detalle a la mitad de la primera letra del
# abecedario. Cinco mil renglones abren sin problema en Excel y pesan poco.
TOPE_DETALLE = 5000


def _detalle_para_excel(db: Session, dimension: str, desde: datetime.date,
                        hasta: datetime.date, tipo: str,
                        taller_id: int | None, datos: dict) -> dict | None:
    """La segunda hoja: un renglon por hecho, no por persona ni por unidad.

    POR QUE HACE FALTA. La hoja de resumen contesta "cuanto hizo cada mecanico";
    esta contesta "que hizo exactamente, que dia y sobre que unidad". El gerente
    pidio las dos cosas en la misma frase --los mecanicos con su historial de
    preventivos Y a que unidades fue-- y la primera sola no se puede sostener en
    una junta: cuando alguien pregunta por que Ramon tiene diez trabajos, la
    respuesta esta aqui, renglon por renglon y con su folio.

    SALE DE LAS MISMAS FUNCIONES QUE LA LISTA, no de consultas nuevas. Los
    trabajos de los mecanicos vienen de _aportes() y _trabajos(), que es
    exactamente lo que ya uso historial_mecanicos() para contar; los eventos de
    las unidades, de _eventos_por_unidad(); las citas de los choferes, de
    _citas_por_chofer(). Si el detalle consultara por su cuenta, el dia que
    alguien cambie un criterio la hoja de arriba diria una cosa y la de abajo
    otra -- que es el problema exacto que tiene hoy el area entre su hoja
    Graficos y su hoja RESUMEN, y que este modulo existe para no repetir.

    SE RESPETA EL RECORTE DE LA LISTA. El detalle solo enumera las entidades que
    salieron en la hoja de resumen. Un detalle con renglones de un mecanico que
    no aparece arriba se lee como un error del archivo.
    """
    talleres = _nombres_talleres(db)

    if dimension == "mecanicos":
        por_tecnico = _aportes(db, desde, hasta, tipo, taller_id)
        economicos = _num_economicos(
            db, [a["unidad_id"] for lista in por_tecnico.values() for a in lista])
        nombres = {x["tecnico_id"]: x["nombre"] for x in datos["mecanicos"]}
        filas = []
        for tid, aportes in por_tecnico.items():
            if tid not in nombres:
                continue
            for t in _trabajos(aportes):
                filas.append([
                    nombres[tid], t["fecha"],
                    economicos.get(t["unidad_id"]),
                    (t["tipo_servicio"] or "").capitalize() or None,
                    t["sistema"], t["actividad"],
                    # Los dos folios en columnas separadas y no pegados con un
                    # punto: el gerente filtra por uno o por el otro, y una
                    # celda "RM-... · OS-..." no se puede filtrar por ninguno.
                    t["folio"] if t["origen"] == "reporte" else None,
                    t["folio_orden"],
                    talleres.get(t["taller_id"]), t["estado"],
                ])
        filas.sort(key=lambda f: (f[0] or "", f[1] or ""), reverse=False)
        return {
            "hoja": "DETALLE",
            "titulo": "Un renglón por trabajo",
            "encabezados": ["MECANICO", "FECHA", "UNIDAD", "TIPO", "SISTEMA",
                            "QUÉ SE HIZO", "FOLIO REPORTE", "FOLIO ORDEN",
                            "TALLER", "ESTADO"],
            "formatos": [None] * 10,
            "filas": filas[:TOPE_DETALLE],
            "nota": ("Un renglón es un técnico en una estancia de la unidad, ya "
                     "deduplicado: cuando el mismo paso por el taller viene del "
                     "reporte y de la orden, el renglón lleva LOS DOS folios. "
                     "Si un técnico firmó varios sistemas del mismo reporte, van "
                     "juntos en SISTEMA — es una visita, no varios trabajos. El "
                     "ESTADO se deja en el vocabulario de donde salió el "
                     "renglón: «realizada/pendiente» del lado del reporte, «en "
                     "espera/en proceso/terminada» del lado de la orden."),
            "aviso": _aviso_recorte(len(filas), min(len(filas), TOPE_DETALLE),
                                    "trabajos"),
        }

    if dimension == "unidades":
        vivas = {x["num_economico"] for x in datos["unidades"]}
        por_unidad = _eventos_por_unidad(db, desde, hasta, taller_id)
        economicos = _num_economicos(db, list(por_unidad))
        filas = []
        for uid, eventos in por_unidad.items():
            eco = economicos.get(uid)
            if eco not in vivas:
                continue
            for e in eventos:
                filas.append([eco, e["fecha"], (e["tipo"] or "").capitalize(),
                              e["folio"], e["taller"], e["detalle"],
                              e["estado"], e["tecnico"]])
        filas.sort(key=lambda f: (f[0] or "", f[1] or ""))
        return {
            "hoja": "EVENTOS",
            "titulo": "Un renglón por evento de la unidad",
            "encabezados": ["UNIDAD", "FECHA", "EVENTO", "FOLIO", "TALLER",
                            "DETALLE", "ESTADO", "TÉCNICO"],
            "formatos": [None] * 8,
            "filas": filas[:TOPE_DETALLE],
            "nota": ("Cinco clases de evento en una sola línea de tiempo: "
                     "entrada al taller, orden de servicio, reporte de "
                     "mantenimiento, cita y avería. Una entrada y una orden del "
                     "mismo día no son lo mismo repetido: la entrada la escribe "
                     "el movimiento del patio y la orden la abre el "
                     "administrador."),
            "aviso": _aviso_recorte(len(filas), min(len(filas), TOPE_DETALLE),
                                    "eventos"),
        }

    if dimension == "choferes":
        unidades = db.query(m.Unidad).all()
        poseedor = {u.id: (u.poseedor_chofer_id or u.titular_chofer_id)
                    for u in unidades}
        falta_por_cita = {a.cita_id: a.chofer_id
                          for a in db.query(m.AvisoIncumplimiento).all() if a.cita_id}
        citas_de = _citas_por_chofer(db, desde, hasta, poseedor, falta_por_cita)
        economicos = {u.id: u.num_economico for u in unidades}
        nombres = {x["chofer_id"]: x["nombre"] for x in datos["choferes"]}
        filas = []
        for cid, citas in citas_de.items():
            if cid not in nombres:
                continue
            for c in citas:
                filas.append([
                    nombres[cid], c["fecha"].isoformat(),
                    economicos.get(c["unidad_id"]),
                    talleres.get(c["taller_id"]), c["estado"],
                    c["veces_reprogramada"],
                    # De donde salio la atribucion. Es la columna que contesta
                    # "por que esta falta es mia" sin abrir la base.
                    "aviso" if c["por_aviso"] else "poseedor actual",
                ])
        filas.sort(key=lambda f: (f[0] or "", f[1] or ""))
        return {
            "hoja": "CITAS",
            "titulo": "Un renglón por cita",
            "encabezados": ["CHOFER", "FECHA DE LA CITA", "UNIDAD", "TALLER",
                            "ESTADO", "VECES REPROGRAMADA", "ATRIBUIDA POR"],
            "formatos": [None, None, None, None, None, "0", None],
            "filas": filas[:TOPE_DETALLE],
            "nota": ("Solo las citas CONFIRMADAS, CUMPLIDAS o NO ASISTIDAS: una "
                     "propuesta que nadie confirmó no compromete al chofer. "
                     "ATRIBUIDA POR dice de dónde salió el responsable — «aviso» "
                     "cuando el aviso de incumplimiento ya había resuelto quién "
                     "poseía la unidad ese día, que es el dato bueno, y "
                     "«poseedor actual» cuando se dedujo de quién la trae hoy. "
                     "Una falta sin aviso no aparece: no se sabe de quién fue, y "
                     "cargársela a alguien sería acusarlo sin fundamento."),
            "aviso": _aviso_recorte(len(filas), min(len(filas), TOPE_DETALLE),
                                    "citas"),
        }

    # talleres. NO se llama a historial_taller() aunque sean solo seis, y la
    # razon es el tope: esa funcion acota a TOPE_ORDENES_TALLER porque arma cada
    # renglon con orden_out(), que cuesta unas 3.5 consultas por orden. Con el
    # trabajo repartido segun la plantilla, Alamos tiene 364 ordenes en el
    # periodo y la hoja mostraria 100: el gerente sumaria la columna del detalle
    # y le faltarian 264 contra el numero de la hoja de arriba. Una nota al pie
    # no arregla eso -- lo que se lee es que el archivo esta mal.
    #
    # Aqui los renglones son datos crudos de la orden (folio, fechas, estado) y
    # no numeros derivados, asi que se leen directo en DOS consultas para los
    # seis talleres. El criterio de que orden entra es el MISMO de la hoja de
    # resumen --por fecha de ENTRADA en el rango-- y por eso las dos hojas
    # cuadran por construccion y no por coincidencia.
    nombres_taller = {t["taller_id"]: t["nombre"] for t in datos["talleres"]}
    tecnicos_de_orden: dict = {}
    for g, tec in (db.query(m.AsignacionTecnico, m.Tecnico)
                   .join(m.Tecnico, m.Tecnico.id == m.AsignacionTecnico.tecnico_id)
                   .all()):
        tecnicos_de_orden.setdefault(g.orden_servicio_id, []).append(
            (g.orden_en_cola, tec.nombre_completo))
    economicos = _num_economicos(
        db, [o.unidad_id for o in db.query(m.OrdenServicio).all()])

    filas = []
    for o in db.query(m.OrdenServicio).all():
        if o.taller_id not in nombres_taller:
            continue
        entrada = _fecha_op(o.fecha_entrada)
        if not _en(entrada, desde, hasta):
            continue
        salida = _fecha_op(o.fecha_salida)
        gente = sorted(tecnicos_de_orden.get(o.id, []))
        filas.append([
            nombres_taller[o.taller_id], o.folio, economicos.get(o.unidad_id),
            (o.tipo or "").capitalize() or None,
            entrada.isoformat() if entrada else None,
            salida.isoformat() if salida else None,
            # Los dias solo cuando la orden CERRO. Con la orden abierta el
            # conteo corriendo se leeria como una duracion final, y no lo es:
            # todavia no se sabe cuanto va a durar.
            _dias(entrada, salida) if salida else None,
            o.estado,
            ", ".join(n for _, n in gente) or None,
        ])
    filas.sort(key=lambda f: (f[0] or "", f[4] or ""))
    return {
        "hoja": "ORDENES",
        "titulo": "Un renglón por orden de servicio",
        "encabezados": ["TALLER", "FOLIO", "UNIDAD", "TIPO", "ENTRADA",
                        "SALIDA", "DÍAS", "ESTADO", "TÉCNICOS"],
        "formatos": [None, None, None, None, None, None, "0", None, None],
        "filas": filas[:TOPE_DETALLE],
        "nota": ("Las órdenes que ENTRARON en el rango, cerradas o no — el mismo "
                 "criterio con el que la hoja de resumen cuenta la columna "
                 "ÓRDENES, así que las dos cuadran. SALIDA y DÍAS vacíos "
                 "significan que la unidad sigue adentro: ese renglón tampoco "
                 "entra en el promedio de días de reparación del resumen, "
                 "porque todavía no se sabe cuánto va a durar. DÍAS PROM. DE "
                 "REPARACIÓN del resumen, en cambio, se ancla en la SALIDA, así "
                 "que no se calcula sobre estos mismos renglones y no tiene por "
                 "qué cuadrar con ellos."),
        "aviso": None,
    }


def tabla_para_excel(db: Session, dimension: str, desde: datetime.date,
                     hasta: datetime.date, tipo: str = "todos",
                     taller_id: int | None = None,
                     solo_con_actividad: bool = True) -> dict:
    """La tabla plana de una dimension, lista para volcarse a una hoja.

    ES LA UNICA PUERTA DEL EXPORTADOR, y eso es deliberado. Ni un numero del
    archivo se vuelve a calcular ahi: el exportador pide esta tabla, pinta los
    encabezados y escribe las filas. Es la misma regla que ya obedecen
    exportar_tablero.py y exportar_resumen.py, y la razon esta escrita en los dos:
    el area tiene hoy una hoja Graficos que no cuadra con su hoja RESUMEN porque
    los numeros se copian de una a otra a mano, y llevan meses sin notarlo.

    Devuelve:
      titulo          el encabezado de la hoja
      encabezados     los nombres de columna, en el orden de las filas
      filas           lista de listas, ya en el orden en que van escritas
      formatos        el formato de numero por columna, o None; None deja la
                      celda como venga, que es lo que hay que hacer con el texto
      nota            el renglon en cursiva del pie, explicando que significan
                      las celdas vacias
      nombre_archivo  el nombre del .xlsx, con el rango REAL que se exporto

    LOS None SE PASAN TAL CUAL Y NO SE CONVIERTEN A CERO. openpyxl deja la celda
    VACIA, que es exactamente lo que tiene que quedar donde no hubo base para
    calcular. Quien abra el archivo va a graficar esa columna, y un cero
    inventado en una grafica es indistinguible de una medicion real.
    """
    desde, hasta = _rango(desde, hasta)
    dimension = dimension if dimension in DIMENSIONES else "mecanicos"
    vacia = "Una celda vacía no es un cero: significa que no hubo base para calcular."

    if dimension == "mecanicos":
        datos = historial_mecanicos(db, desde, hasta, tipo, taller_id)
        encabezados = ["MECANICO", "ESPECIALIDAD", "MODALIDAD", "TALLER",
                       "TRABAJOS", "PREVENTIVOS", "CORRECTIVOS",
                       "UNIDADES DISTINTAS", "UNIDADES", "ULTIMO TRABAJO"]
        formatos = [None, None, None, None, "0", "0", "0", "0", None, None]
        filas = [[x["nombre"], x["especialidad"], x["modalidad"], x["taller"],
                  x["trabajos"], x["preventivos"], x["correctivos"],
                  x["unidades_distintas"], ", ".join(x["unidades"]),
                  x["ultimo_trabajo"]]
                 for x in datos["mecanicos"]]
        nota = ("Se listan TODOS los técnicos activos, también los que no "
                "tuvieron un solo trabajo en el rango: un mecánico en cero es "
                "información, no un faltante. TRABAJOS no siempre es "
                "PREVENTIVOS + CORRECTIVOS -- las órdenes de tipo 'siniestro' "
                "cuentan como trabajo y no caen en ninguna de las dos columnas. "
                "Un trabajo es un técnico en una estancia de la unidad, ya "
                "deduplicado entre el reporte de mantenimiento y la orden de "
                "servicio. La columna UNIDADES trae como mucho 12 números "
                "económicos; el total real está en UNIDADES DISTINTAS.")

    elif dimension == "unidades":
        # `solo_con_actividad` viaja hasta aqui y no se deja en su valor por
        # omision. La pantalla tiene una casilla que lo apaga --para poder buscar
        # una unidad que NO entro al taller, que es un resultado legitimo y no un
        # vacio-- y si el Excel ignorara la casilla, el gerente exportaria lo que
        # esta viendo y recibiria un archivo con 460 renglones en vez de 1,367.
        # Un archivo que no coincide con la pantalla desde la que se bajo es
        # exactamente el problema que este modulo existe para no tener.
        datos = historial_unidades(db, desde, hasta, taller_id, solo_con_actividad)
        encabezados = ["UNIDAD", "MARCA", "MODELO", "AÑO", "ESTADO", "ÁREA",
                       "CHOFER", "ENTRADAS", "ÓRDENES", "PREVENTIVOS",
                       "CORRECTIVOS", "CITAS", "FALTAS", "DÍAS EN TALLER",
                       "ÚLTIMA ENTRADA"]
        formatos = [None, None, None, "0", None, None, None, "0", "0", "0",
                    "0", "0", "0", "0", None]
        filas = [[x["num_economico"], x["marca"], x["modelo"], x["anio"],
                  x["estado"], x["area"], x["chofer"], x["entradas_taller"],
                  x["ordenes"], x["preventivos"], x["correctivos"], x["citas"],
                  x["faltas"], x["dias_en_taller_total"], x["ultima_entrada"]]
                 for x in datos["unidades"]]
        nota = (("Solo aparecen las unidades con actividad en el rango. "
                 if solo_con_actividad else
                 "Aparecen TODAS las unidades del padrón, también las que no "
                 "pisaron el taller en el rango: esas van con ceros en todas "
                 "las columnas de conteo. ")
                + "DÍAS EN "
                "TALLER suma únicamente las órdenes que ya cerraron: va vacío "
                "cuando ninguna cerró, porque un cero diría que la unidad no "
                "pasó ni un día adentro, y con órdenes abiertas pasa lo "
                "contrario -- sigue ahí y todavía no se sabe cuánto va a durar. "
                + vacia)

    elif dimension == "choferes":
        datos = historial_choferes(db, desde, hasta)
        encabezados = ["CHOFER", "LICENCIA", "TURNO", "RUTA", "UNIDADES",
                       "CITAS", "CUMPLIDAS", "FALTAS", "PENDIENTES",
                       "CUMPLIMIENTO (%)", "AVERÍAS", "AMONESTACIONES",
                       "PRÉSTAMOS RECIBIDOS"]
        formatos = [None, None, None, None, None, "0", "0", "0", "0", "0.0",
                    "0", "0", "0"]
        filas = [[x["nombre"], x["num_licencia"], x["turno"], x["ruta"],
                  ", ".join(x["unidades"]), x["citas"], x["cumplidas"],
                  x["faltas"], x["pendientes"], x["cumplimiento"], x["averias"],
                  x["amonestaciones"], x["prestamos_recibidos"]]
                 for x in datos["choferes"]]
        nota = ("CUMPLIMIENTO se calcula solo sobre citas con desenlace "
                "(cumplidas + faltas): una cita confirmada que todavía no llega "
                "no es un incumplimiento, y meterla en el denominador pintaba de "
                "0% a quien no había fallado a nada. Por eso va vacío -- y no "
                "0% -- en el chofer al que el taller nunca le dio cita. No hay "
                "columna de número de empleado porque la tabla de choferes no "
                "guarda ese dato; lo que existe es la licencia.")

    else:
        datos = historial_talleres(db, desde, hasta)
        encabezados = ["TALLER", "TIPO", "ESPACIOS", "OCUPADOS", "OCUPACIÓN (%)",
                       "TÉCNICOS", "ÓRDENES", "PREVENTIVOS", "CORRECTIVOS",
                       "REPORTES", "CITAS", "ÓRDENES CERRADAS",
                       "DÍAS PROM. DE REPARACIÓN", "UNIDADES DISTINTAS"]
        formatos = [None, None, "0", "0", "0.0", "0", "0", "0", "0", "0", "0",
                    "0", "0.0", "0"]
        filas = [[x["nombre"], x["tipo"], x["espacios_totales"],
                  x["espacios_ocupados"], x["ocupacion_pct"], x["tecnicos"],
                  x["ordenes"], x["preventivos"], x["correctivos"],
                  x["reportes"], x["citas"], x["ordenes_cerradas"],
                  x["dias_promedio_reparacion"], x["unidades_distintas"]]
                 for x in datos["talleres"]]
        nota = ("ESPACIOS, OCUPADOS y OCUPACIÓN son la foto del momento en que "
                "se generó el archivo, no del rango: no se guarda una foto "
                "diaria del patio. ÓRDENES cuenta las que ENTRARON en el rango; "
                "DÍAS PROM. DE REPARACIÓN se calcula sobre las que CERRARON en "
                "el rango, que es el mismo criterio del tablero de Indicadores, "
                "para que los dos números coincidan. " + vacia)

    detalle = _detalle_para_excel(db, dimension, desde, hasta, tipo, taller_id,
                                  datos)

    titulos = {"mecanicos": "Historial por mecánico",
               "unidades": "Historial por unidad",
               "choferes": "Historial por chofer",
               "talleres": "Historial por taller"}

    # EL NOMBRE LLEVA EL RANGO REAL, el que devolvio el calculo, y no el que
    # llego en la peticion. Si el gerente invirtio los calendarios, _rango() los
    # corrigio, y un archivo que se llama distinto de lo que trae adentro es el
    # que termina citado en una junta con el rango equivocado. Es la misma razon
    # por la que exportar_tablero.construir() devuelve el nombre en vez de
    # dejarselo al controlador.
    #
    # Y LLEVA TAMBIEN EL FILTRO, por lo mismo. Sin el, bajar "solo preventivos"
    # y despues "todos" deja dos archivos llamados igual en la carpeta de
    # Descargas: el navegador le pega un "(1)" al segundo y ya no hay manera de
    # saber cual es cual sin abrirlos. El de los preventivos es justo el que el
    # gerente pidio para la junta --su pregunta era "a que mecanico le asignaron
    # que preventivos"-- asi que es el que no se puede confundir.
    partes = [titulos[dimension]]
    if dimension == "mecanicos" and tipo in ("preventivo", "correctivo"):
        partes.append("solo %ss" % tipo)
    nombre_taller = _nombres_talleres(db).get(taller_id) if taller_id else None
    if nombre_taller:
        partes.append(nombre_taller)
    partes.append("%s a %s" % (desde.isoformat(), hasta.isoformat()))
    nombre = " ".join(partes) + ".xlsx"

    return {
        "dimension": dimension,
        "titulo": titulos[dimension],
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        # Los dos filtros salen tambien por separado, ya resueltos a texto, para
        # que el exportador pueda escribirlos DENTRO de la hoja sin volver a
        # consultar el nombre del taller. El nombre del archivo se pierde en
        # cuanto alguien lo renombra o lo pega en un correo; lo que va escrito
        # adentro viaja con el.
        "tipo": tipo if dimension == "mecanicos" else None,
        "taller": nombre_taller,
        "encabezados": encabezados, "formatos": formatos, "filas": filas,
        "nota": nota,
        "aviso": datos.get("aviso"),
        "total": datos.get("total"),
        "nombre_archivo": nombre,
        # La segunda hoja. Va dentro de la MISMA llamada y no en un endpoint
        # aparte porque el resumen y el detalle tienen que salir del mismo
        # calculo y del mismo rango: dos descargas separadas se hacen con
        # segundos de diferencia, y basta que alguien cierre una orden en medio
        # para que la hoja de arriba y la de abajo ya no cuadren.
        "detalle": detalle,
    }
