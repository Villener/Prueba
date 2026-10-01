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

EL TABLERO POR RANGO (tablero_rango): el gerente escoge dos fechas del
calendario y la granularidad, y ve cuatro indicadores de las unidades. La
semantica de los cuatro queda cerrada aqui a proposito, porque cada uno se
puede calcular de tres o cuatro maneras defendibles y cada una da un numero
distinto; el dia que la pantalla y el Excel discrepen, nadie va a volver a
creerle al tablero.

  dias_reparacion   OrdenServicio con fecha_salida NO nula, agrupada por el
                    periodo de la SALIDA y no de la entrada: una unidad que
                    entro en enero y salio en marzo habla de marzo, que es
                    cuando por fin libero el espacio. Valor = promedio de
                    (fecha_salida - fecha_entrada).days redondeado a un
                    decimal. Un periodo SIN ordenes cerradas vale null y NO
                    cero: cero dias de reparacion promedio es una afirmacion
                    --se reparo en el acto--, no un hueco.
  tasa_concretadas  por periodo de CitaTaller.fecha_cita,
                    cumplidas / (cumplidas + no_asistio) * 100 a un decimal.
                    SOLO citas con desenlace, que es el mismo criterio que ya
                    usa cumplimiento_choferes() mas abajo: una cita confirmada
                    que todavia no llega no es un incumplimiento, y meterla al
                    denominador pintaba de 0% a quien no habia fallado a nada.
                    Sin citas con desenlace -> null.
  citas_totales     CitaTaller con fecha_cita en el periodo, todos los estados
                    de ESTADOS_CITA menos "cancelada". Una cita cancelada nunca
                    llego a ser un compromiso vivo. Aqui el 0 SI es legitimo:
                    quiere decir que hubo periodo y no hubo citas, y eso es un
                    dato, no una falta de dato.
  atenciones        CitaTaller con estado == "cumplida" y fecha_cita en el
                    periodo. El 0 tambien es legitimo, por lo mismo.
"""
import datetime

from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import ahora_utc, dia_operativo

GRANULARIDADES = ("dia", "mes", "anio")

# Cuantos puntos como maximo puede devolver un rango. 370 no es un numero
# redondo por capricho: cubre un ano completo dia por dia (366 en bisiesto) con
# unos dias de sobra, y por mes o por ano es mas historia de la que existe en la
# base. El tope es lo unico que separa a "del 1 de enero de 2016 al 31 de
# diciembre de 2026, por dia" --4,018 puntos, una grafica ilegible y un JSON que
# el navegador arrastra-- de una pantalla que responde. Cuando el rango lo
# excede se recortan los periodos MAS VIEJOS, porque la pregunta del gerente
# siempre es "como vamos", y se le avisa en la respuesta que cambie la
# granularidad si quiere ver todo el rango.
TOPE_PERIODOS = 370


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


def _periodos_entre(gran: str, desde: datetime.date, hasta: datetime.date,
                    tope: int = TOPE_PERIODOS) -> tuple:
    """Las etiquetas de TODOS los periodos entre dos fechas, vacios incluidos.

    Es el hermano de _periodos(), que solo sabe contar N periodos hacia atras
    desde una fecha. Eso sirve cuando la pantalla elige el rango, pero no cuando
    lo elige el gerente con dos calendarios: ahi el rango es lo que el marco, y
    puede ser de tres dias o de seis anos.

    Los periodos vacios se incluyen por la misma razon que en _periodos(): un
    mes sin una sola cita es informacion, y omitirlo no deja un hueco en la
    grafica sino algo peor --pega el mes de antes con el de despues y el bajon
    desaparece de la vista.

    Si las fechas vienen al reves se INTERCAMBIAN en vez de devolver una lista
    vacia. El gerente va a equivocarse de calendario tarde o temprano, y una
    pantalla en blanco no le dice que se equivoco: lo deja pensando que no hubo
    movimiento en ese rango, que es exactamente la conclusion contraria.

    Devuelve (etiquetas, desde_real, hasta_real, recortado). `desde_real` es la
    fecha que hay que devolverle a la pantalla: la que pidio si se respeto tal
    cual, o el arranque del periodo mas viejo que si cupo si hubo que recortar.
    """
    hoy = dia_operativo(ahora_utc())
    desde = desde or hasta or hoy
    hasta = hasta or desde
    if desde > hasta:
        desde, hasta = hasta, desde
    tope = max(1, tope)

    fuera: list = []
    # Se enumera de HASTA hacia atras, no de DESDE hacia adelante, para que el
    # tope recorte solo lo viejo sin tener que armar antes la lista completa: un
    # rango absurdo de cien anos por dia nunca llega a existir en memoria.
    if gran == "dia":
        f = hasta
        while f >= desde and len(fuera) < tope:
            fuera.append(f.isoformat())
            f -= datetime.timedelta(days=1)
        recortado = f >= desde
        primero = datetime.date.fromisoformat(fuera[-1])
    elif gran == "mes":
        y, mth = hasta.year, hasta.month
        while (y, mth) >= (desde.year, desde.month) and len(fuera) < tope:
            fuera.append("%04d-%02d" % (y, mth))
            mth -= 1
            if mth == 0:
                y, mth = y - 1, 12
        recortado = (y, mth) >= (desde.year, desde.month)
        primero = datetime.date(int(fuera[-1][:4]), int(fuera[-1][5:]), 1)
    else:
        y = hasta.year
        while y >= desde.year and len(fuera) < tope:
            fuera.append("%04d" % y)
            y -= 1
        recortado = y >= desde.year
        primero = datetime.date(int(fuera[-1]), 1, 1)

    fuera.reverse()
    return fuera, (primero if recortado else desde), hasta, recortado


def _contar(filas, gran: str, campo: str, etiquetas: list) -> list:
    cuenta = {e: 0 for e in etiquetas}
    for x in filas:
        k = _clave(getattr(x, campo, None), gran)
        if k in cuenta:
            cuenta[k] += 1
    return [cuenta[e] for e in etiquetas]


def serie(db: Session, gran: str = "mes", cuantos: int = 12,
          hasta: datetime.date | None = None,
          desde: datetime.date | None = None) -> dict:
    """Los indicadores del taller a lo largo del tiempo.

    `desde` es opcional y llego despues: con el, el rango son las dos fechas que
    el gerente marco en los calendarios y `cuantos` se ignora; sin el, la
    funcion se comporta EXACTAMENTE como antes --los ultimos `cuantos` periodos
    hacia atras desde `hasta`--. Se agrego al final de la firma justo para eso:
    la pantalla de estadisticas que ya esta viva llama serie(db, gran, cuantos)
    por posicion y no se entera de que este parametro existe.
    """
    gran = gran if gran in GRANULARIDADES else "mes"
    cuantos = max(2, min(cuantos, 120))
    hasta = hasta or datetime.date.today()
    if desde is None:
        etiquetas = _periodos(gran, cuantos, hasta)
    else:
        etiquetas, desde, hasta, _ = _periodos_entre(gran, desde, hasta)

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
    return {
        "granularidad": gran, "hasta": hasta.isoformat(),
        # Se agrega sin condicion --null cuando nadie pidio rango-- porque una
        # clave que a veces esta y a veces no obliga a la pantalla a preguntar
        # por ella antes de leerla, y ese es el tipo de detalle que se olvida.
        "desde": desde.isoformat() if desde else None,
        "etiquetas": etiquetas, "series": series,
        # El periodo que TODAVIA NO TERMINA. La pantalla lo pinta apagado para
        # que no se lea como una caida: un mes a medias contra meses completos
        # siempre sale abajo, y con granularidad de dia es peor todavia --a las
        # 9 de la manana el dia de hoy va a la mitad de cualquier otro.
        #
        # Es el mismo criterio que ya seguian la meta de preventivos (el dia en
        # curso no cuenta como incumplido) y el cumplimiento por chofer (una
        # cita que no ha llegado no baja el porcentaje). Un periodo que no ha
        # terminado no se juzga.
        #
        # Se calcula por el periodo que contiene HOY, no por "el ultimo de la
        # lista": si alguien pide una serie que termina en el pasado, ahi no hay
        # nada en curso.
        "en_curso": _clave(datetime.date.today(), gran),
    }


def _meta_pct_preventivo(db: Session) -> int:
    c = (db.query(m.Configuracion)
         .filter(m.Configuracion.clave == "meta_pct_preventivo").first())
    try:
        return int(c.valor) if c else 80
    except (TypeError, ValueError):
        return 80


TOPE_PASTEL_MECANICOS = 5


def _mecanicos_preventivo(db: Session, desde: datetime.date, hasta: datetime.date) -> dict:
    """Quien hace los preventivos: el pastel y el ranking del gerente.

    Sale de historiales.historial_mecanicos, la MISMA cuenta de la pantalla de
    Historiales, para que los dos numeros nunca se contradigan. Un mecanico
    suma un preventivo cuando esta capturado como responsable en el formato de
    mantenimiento; el que trabajo sin quedar capturado no aparece, y eso es lo
    que hay que corregir en el taller, no aqui.

    Es la base para el premio que quiere dar el Lic. Tiscareno: el criterio y
    el monto los decide el; el sistema solo pone los numeros del periodo.
    """
    from .historiales import historial_mecanicos
    filas = [f for f in historial_mecanicos(db, desde, hasta, "todos")["mecanicos"]
             if f["preventivos"]]
    filas.sort(key=lambda f: (-f["preventivos"], f["nombre"]))
    total = sum(f["preventivos"] for f in filas)

    def pct(n):
        return round(100 * n / total, 1) if total else 0.0

    partes = [{"clave": f"m{i}", "nombre": f["nombre"], "cuantas": f["preventivos"],
               "pct": pct(f["preventivos"])}
              for i, f in enumerate(filas[:TOPE_PASTEL_MECANICOS])]
    resto = filas[TOPE_PASTEL_MECANICOS:]
    if resto:
        n = sum(f["preventivos"] for f in resto)
        partes.append({"clave": "otros", "nombre": f"Otros {len(resto)}",
                       "cuantas": n, "pct": pct(n)})
    ranking = [{"lugar": i + 1, "nombre": f["nombre"], "taller": f["taller"],
                "preventivos": f["preventivos"], "correctivos": f["correctivos"],
                "pct_preventivo": (round(100 * f["preventivos"] / f["trabajos"], 1)
                                   if f["trabajos"] else None)}
               for i, f in enumerate(filas)]
    return {"total": total, "partes": partes, "ranking": ranking}


def tablero_rango(db: Session, desde: datetime.date, hasta: datetime.date,
                  gran: str = "mes") -> dict:
    """Los cuatro indicadores de las unidades entre dos fechas del calendario.

    Es lo que el gerente pidio despues de la junta: elegir del calendario 1 al
    calendario 2, elegir dia, mes o ano, y ver en la MISMA pantalla el tiempo
    promedio de reparacion, el porcentaje de citas que si se concretaron, las
    citas totales y las atenciones. Hasta ahora eso lo obligaba a entrar al otro
    modulo con otro correo y otra contrasena para mirar la mitad de los numeros.

    La semantica exacta de los cuatro esta en el docstring del modulo, arriba.
    Dos decisiones que no se ven en la forma de la respuesta y conviene dejar
    escritas:

    EL RESUMEN SE CALCULA SOBRE LOS MISMOS PERIODOS QUE LAS BARRAS, no sobre el
    rango literal de fechas. Si el gerente pide del 15 de enero al 21 de
    septiembre por MES, la barra de "2026-01" trae el mes de enero completo
    --incluido del 1 al 14--, porque una barra mensual a medias no se puede leer
    contra las otras once. Entonces el total de arriba tiene que contar tambien
    ese pedazo: si no, el numero grande no cuadra con la suma de las barras que
    estan debajo, el gerente lo suma a mano una vez, no cuadra, y deja de
    creerle al tablero completo. Con granularidad de dia los dos criterios
    coinciden y no hay nada que decidir.

    EL PERIODO DE UNA ORDEN SE SACA DE SU DIA OPERATIVO EN TIJUANA, no de la
    fecha UTC cruda. fecha_salida es UTCDateTime (ver orden_model.py), asi que
    una orden cerrada a las 17:30 del 30 de septiembre en el taller esta
    guardada como las 00:30 del 1 de octubre en UTC: tomarle .date() directo la
    mandaba al mes siguiente. En el corte de mes eso no es un decimal de mas,
    es una orden que desaparece de septiembre y aparece en octubre.
    """
    gran = gran if gran in GRANULARIDADES else "mes"
    etiquetas, desde, hasta, recortado = _periodos_entre(gran, desde, hasta)
    vivos = set(etiquetas)

    # Se acumula suma y conteo por separado en vez de guardar las listas de
    # duraciones: el promedio del rango completo NO es el promedio de los
    # promedios por periodo. Un mes con una sola orden de 30 dias pesaria igual
    # que uno con cuarenta ordenes de un dia, y el resumen de arriba diria una
    # cosa distinta de lo que se ve en la grafica.
    suma_dias = {e: 0 for e in etiquetas}
    n_ordenes = {e: 0 for e in etiquetas}
    for o in (db.query(m.OrdenServicio)
              .filter(m.OrdenServicio.fecha_salida.isnot(None)).all()):
        if o.fecha_entrada is None:
            # fecha_entrada es nullable aunque traiga default. Una orden cerrada
            # sin entrada no tiene duracion que medir; contarla como 0 dias
            # bajaria el promedio con una reparacion que nunca se midio.
            continue
        k = _clave(dia_operativo(o.fecha_salida), gran)
        if k not in vivos:
            continue
        dias = (o.fecha_salida - o.fecha_entrada).days
        if dias < 0:
            # Salida anterior a la entrada: captura al reves o correccion a mano
            # de una fecha. Se descarta en vez de dejarla pasar porque .days de
            # un timedelta negativo trunca hacia abajo --dos horas al reves dan
            # -1, no 0-- y una sola de estas arrastra el promedio del periodo.
            continue
        suma_dias[k] += dias
        n_ordenes[k] += 1

    # Las citas se traen todas y se filtran por etiqueta, igual que en
    # cumplimiento_choferes(). Acotar por fecha en SQL obligaria a calcular en
    # que dia empieza y termina cada periodo aqui tambien, y esa cuenta ya vive
    # en _periodos_entre(): tenerla en dos lados es como se llega a que la
    # grafica y el total digan cosas distintas el dia que alguien toque una.
    totales = {e: 0 for e in etiquetas}
    cumplidas = {e: 0 for e in etiquetas}
    faltas = {e: 0 for e in etiquetas}
    for c in db.query(m.CitaTaller).all():
        k = _clave(c.fecha_cita, gran)
        if k not in vivos:
            continue
        if c.estado != "cancelada":
            totales[k] += 1
        if c.estado == "cumplida":
            cumplidas[k] += 1
        elif c.estado == "no_asistio":
            faltas[k] += 1

    # El null de dias_reparacion es el hueco y el 0.0 es una medicion. Los dos
    # se ven parecido en una grafica y por eso aqui no se pueden confundir: de
    # las 22 ordenes cerradas que hay en la base, 20 entraron y salieron el
    # mismo dia --.days da 0-- y solo dos duraron 1 y 3 dias. O sea que el 0.0
    # de un periodo es casi siempre un promedio real y no un vacio; devolverlo
    # como null dejaria una semana de reparaciones en el dia leyendose igual que
    # una semana en la que el taller no cerro una sola orden.
    dias_prom = [round(suma_dias[e] / n_ordenes[e], 1) if n_ordenes[e] else None
                 for e in etiquetas]
    tasa = [round(100 * cumplidas[e] / (cumplidas[e] + faltas[e]), 1)
            if (cumplidas[e] + faltas[e]) else None for e in etiquetas]

    tot_ordenes = sum(n_ordenes.values())
    tot_cumplidas = sum(cumplidas.values())
    tot_resueltas = tot_cumplidas + sum(faltas.values())
    hoy = _clave(dia_operativo(ahora_utc()), gran)

    # LA MEZCLA: cuanto del trabajo del taller fue preventivo y cuanto correctivo.
    #
    # Es la pregunta que el gerente hace primero y que ninguna grafica de barras
    # contesta bien, porque no es una serie en el tiempo: es un reparto de un
    # total. Un taller que atiende 70% preventivo esta adelantandose a las
    # fallas; uno que atiende 70% correctivo va apagando incendios. Ese es el
    # numero que dice si el programa de mantenimiento sirve de algo.
    #
    # Se cuenta por la ENTRADA de la orden y no por la salida, a diferencia del
    # tiempo de reparacion: la pregunta es que clase de trabajo LLEGO al taller
    # en el periodo. Una unidad que entro en enero por un correctivo y sigue
    # adentro ya gasto la capacidad de enero, haya salido o no.
    #
    # `siniestro` sale como su propia rebanada en vez de esconderse en "otros":
    # son pocas, pero meterlas con los correctivos hace ver al taller peor de lo
    # que esta -- un choque no es una falla de mantenimiento.
    # Se decide por la ETIQUETA del periodo, igual que todo lo de arriba, y no
    # comparando la fecha contra el rango crudo. Asi la rebanada cubre
    # exactamente los mismos periodos que las barras: si el tope recorto el
    # rango, la mezcla se recorta con el, y el porcentaje de la dona siempre
    # habla de lo que se esta viendo en pantalla.
    mezcla = {"preventivo": 0, "correctivo": 0, "siniestro": 0, "otros": 0}
    for o in db.query(m.OrdenServicio).all():
        if o.fecha_entrada is None:
            continue
        if _clave(dia_operativo(o.fecha_entrada), gran) not in vivos:
            continue
        clave = (o.tipo or "").lower()
        mezcla[clave if clave in mezcla else "otros"] += 1
    tot_mezcla = sum(mezcla.values())

    return {
        "granularidad": gran,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "etiquetas": etiquetas,
        # El periodo que TODAVIA NO TERMINA, para que la pantalla lo pinte
        # apagado y no se lea como una caida. Se busca dentro del rango y no se
        # asume que es el ultimo de la lista: si el gerente pidio un rango que
        # termino el ano pasado, ahi no hay nada en curso y esto vale null.
        "en_curso": hoy if hoy in vivos else None,
        "resumen": {
            "dias_reparacion_prom": (round(sum(suma_dias.values()) / tot_ordenes, 1)
                                     if tot_ordenes else None),
            "tasa_concretadas": (round(100 * tot_cumplidas / tot_resueltas, 1)
                                 if tot_resueltas else None),
            "citas_totales": sum(totales.values()),
            "atenciones": tot_cumplidas,
            "ordenes_cerradas": tot_ordenes,
        },
        # El reparto preventivo/correctivo del periodo, para la dona.
        #
        # El porcentaje se calcula AQUI y no en la pantalla: es el numero que el
        # gerente va a leer en voz alta en una junta, y si la pantalla lo
        # redondeara por su cuenta acabaria diciendo algo distinto del Excel que
        # sale del mismo dato. Un solo lugar decide.
        #
        # Con el rango vacio va `total: 0` y las rebanadas en cero -- no null:
        # aqui el cero SI es una medicion ("no entro una sola orden"), a
        # diferencia de un promedio, que sin base no existe.
        "mecanicos_preventivo": _mecanicos_preventivo(db, desde, hasta),
        "mezcla": {
            "total": tot_mezcla,
            # La meta del gerente (80% preventivo). Vive en configuracion para
            # poder moverla sin desplegar.
            "meta_pct": _meta_pct_preventivo(db),
            "partes": [
                {"clave": k, "nombre": n, "cuantas": mezcla[k],
                 "pct": round(100 * mezcla[k] / tot_mezcla, 1) if tot_mezcla else 0.0}
                for k, n in (("preventivo", "Preventivo"),
                             ("correctivo", "Correctivo"),
                             ("siniestro", "Siniestro"),
                             ("otros", "Otros"))
                # Una rebanada en cero no se dibuja: ensucia la leyenda con
                # nombres que no estan en la grafica.
                if mezcla[k]
            ],
        },
        "series": [
            {"clave": "dias_reparacion", "nombre": "Tiempo promedio de reparacion",
             "unidad": "dias", "datos": dias_prom},
            {"clave": "tasa_concretadas", "nombre": "Citas concretadas",
             "unidad": "pct", "datos": tasa},
            {"clave": "citas_totales", "nombre": "Citas totales",
             "unidad": "conteo", "datos": [totales[e] for e in etiquetas]},
            {"clave": "atenciones", "nombre": "Atenciones a citas",
             "unidad": "conteo", "datos": [cumplidas[e] for e in etiquetas]},
        ],
        # Cuando el tope recorto el rango hay que DECIRLO. Callarlo deja al
        # gerente viendo una grafica que empieza donde el no pidio, y lo que va
        # a concluir es que antes de esa fecha no hubo nada.
        "aviso": ("El rango pedido pasa de %d periodos; se muestran los más "
                  "recientes. Para verlo completo, cambie la granularidad a mes "
                  "o año." % TOPE_PERIODOS) if recortado else None,
    }


def _nombre(db: Session, usuario_id) -> str | None:
    u = db.query(m.Usuario).filter(m.Usuario.id == usuario_id).first()
    return u.nombre_completo if u else None


def cumplimiento_choferes(db: Session, gran: str = "mes", cuantos: int = 6,
                          hasta: datetime.date | None = None,
                          limite: int = 25,
                          desde: datetime.date | None = None) -> dict:
    """RF-GER-17: el cumplimiento de cada chofer, cortado por mes o por ano.

    Se mide sobre CITAS, no sobre programas: el chofer responde por presentarse
    a la cita que le confirmaron. Si el taller nunca se la dio, no aparece aqui
    -- y esa es la diferencia entre medir al chofer y medir al taller.

    Se mide contra el POSEEDOR de la unidad ese dia (RN-01), que es de donde
    sale `aviso.chofer_id`.

    `desde` es opcional y va al final de la firma a proposito: la pantalla que
    ya esta viva llama cumplimiento_choferes(db, granularidad, cuantos) por
    posicion, y agregarlo en medio le habria cambiado el significado a `hasta`
    sin que nadie lo notara hasta ver la tabla mal. Con `desde` el rango son las
    dos fechas del calendario y `cuantos` se ignora; sin el, no cambia nada.
    """
    gran = gran if gran in GRANULARIDADES else "mes"
    hasta = hasta or datetime.date.today()
    if desde is None:
        etiquetas = _periodos(gran, max(1, min(cuantos, 36)), hasta)
    else:
        etiquetas, _, _, _ = _periodos_entre(gran, desde, hasta)
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
        d = por_chofer.setdefault(ch, {"confirmadas": 0, "cumplidas": 0,
                                       "faltas": 0, "pendientes": 0})
        d["confirmadas"] += 1
        if c.estado == "cumplida":
            d["cumplidas"] += 1
        elif c.estado == "no_asistio":
            d["faltas"] += 1
        else:
            # Confirmada y sin desenlace todavia: la cita no ha llegado o no se
            # ha cerrado. NO cuenta para el porcentaje.
            d["pendientes"] += 1

    amon_por_chofer: dict = {}
    for a in db.query(m.Amonestacion).all():
        if a.estado == "anulada":
            continue
        if _clave(a.fecha_emision, gran) in vivos:
            amon_por_chofer[a.chofer_id] = amon_por_chofer.get(a.chofer_id, 0) + 1

    filas = []
    for ch, d in por_chofer.items():
        # El porcentaje se calcula SOLO sobre citas con desenlace: cumplidas mas
        # faltas. Una cita confirmada que todavia no llega no es un
        # incumplimiento, y meterla en el denominador pintaba de 0% a un chofer
        # que no ha fallado a nada -- que fue justo lo que aparecio con los datos
        # reales de produccion.
        resueltas = d["cumplidas"] + d["faltas"]
        filas.append({
            "chofer_id": ch, "chofer": _nombre(db, ch),
            "confirmadas": d["confirmadas"], "cumplidas": d["cumplidas"],
            "faltas": d["faltas"], "pendientes": d["pendientes"],
            "amonestaciones": amon_por_chofer.get(ch, 0),
            "cumplimiento": round(100 * d["cumplidas"] / resueltas, 1) if resueltas else None,
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

    confirmadas = cumplidas = faltadas = 0
    if ids_unidad:
        for c in (db.query(m.CitaTaller)
                  .filter(m.CitaTaller.unidad_id.in_(ids_unidad)).all()):
            if c.estado in ("confirmada", "cumplida", "no_asistio"):
                confirmadas += 1
            if c.estado == "cumplida":
                cumplidas += 1
            elif c.estado == "no_asistio":
                faltadas += 1

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
        # Mismo criterio que cumplimiento_choferes(): solo las citas con
        # desenlace. Una confirmada que no ha llegado no es un incumplimiento.
        "cumplimiento": (round(100 * cumplidas / (cumplidas + faltadas), 1)
                         if (cumplidas + faltadas) else None),
        "prestamos_recibidos": prestamos,
        "averias_reportadas": averias,
        "amonestaciones": h,
    }
