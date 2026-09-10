"""Agenda automatica de mantenimiento - implementa docs/agenda-mantenimiento.md.

Es el paquete H del diagrama de clases: `AgendaMantenimiento`. No es una entidad
del mundo real, es logica que no pertenece a ninguna. Vive aparte porque
`CitaTaller` no debe saber nada de los demas talleres ni de la capacidad.

LAS DOS FECHAS QUE NO HAY QUE CONFUNDIR, que es de donde sale todo lo demas:

    ProgramaMantenimiento.fecha_limite   viene del plan.  NUNCA se mueve.
    CitaTaller.fecha_cita                la asigna esto.  SI se mueve.

De ahi que el chofer solo incumpla si falto a una cita CONFIRMADA. Si el taller
nunca pudo darsela, el problema es de capacidad del taller y va a otro tablero
-- `detectar_sin_cupo()`. Sin esa separacion el sistema castigaria al chofer por
un problema que no es suyo, que era el defecto que este diseno vino a corregir.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import ahora_utc

# Mas alla de esto el sistema NO propone fecha: dice "sin cupo" y alerta. Planear
# a seis meses con datos que cambian a diario es inventar certidumbre.
HORIZONTE_DIAS = 30

# Anticipacion por debajo de la cual una cita confirmada ya no se mueve sola.
HORAS_INTOCABLE = 48

ESTADOS_MOVIBLES = ("propuesta",)
ESTADOS_VIVOS = ("propuesta", "confirmada", "reprogramada")


# --------------------------------------------------------------------------- #
# Calendario
# --------------------------------------------------------------------------- #
def opera(taller: m.Taller, dia: date) -> bool:
    """Domingo nunca; sabado segun el taller.

    Es por taller y no global a proposito: es probable que Alamos abra sabado y
    alguna satelite no. Cuando exista TALLER_HORARIO esto lo consulta a la tabla
    y deja de ser una bandera.
    """
    if dia.weekday() == 6:
        return False
    if dia.weekday() == 5:
        return bool(taller.opera_sabado)
    return True


def dias_habiles(taller: m.Taller, desde: date, cuantos: int):
    """Los siguientes `cuantos` dias naturales que el taller si opera."""
    dia, vistos = desde, 0
    while vistos < cuantos:
        if opera(taller, dia):
            yield dia
            vistos += 1
        dia += timedelta(days=1)


# --------------------------------------------------------------------------- #
# Capacidad -- SIEMPRE por tipo de espacio, nunca global
# --------------------------------------------------------------------------- #
def espacios_del_taller(db: Session, taller_id: int):
    """Los espacios que de verdad cuentan como capacidad.

    Quedan fuera las zonas con `cuenta_para_ocupacion = False` -- el patio de
    45 lugares, el yonke, el area de lavado. Sin ese filtro la agenda creeria
    que Alamos tiene 76 espacios en vez de 31.
    """
    return (db.query(m.Espacio)
            .join(m.ZonaTaller)
            .filter(m.ZonaTaller.taller_id == taller_id,
                    m.ZonaTaller.cuenta_para_ocupacion.is_(True),
                    m.Espacio.activo.is_(True),
                    m.Espacio.estado != "bloqueado")
            .all())


def _admite(espacio: m.Espacio, tipo_unidad_id: int) -> bool:
    """Un espacio sin tipo declarado admite cualquier unidad (RN-06 / RI-04)."""
    return (espacio.tipo_unidad_permitido_id is None
            or espacio.tipo_unidad_permitido_id == tipo_unidad_id)


def _libera_en(db: Session, ocupacion: m.OcupacionEspacio) -> date | None:
    """Cuando se espera que este espacio quede libre. None = indefinido.

    Pesimista a proposito: si la unidad esta esperando refacciones y nadie
    registro la ETA, el espacio se considera ocupado por tiempo indefinido. Es
    preferible agendar de menos que citar a un chofer para un espacio que no va
    a existir.
    """
    orden = (db.query(m.OrdenServicio)
             .filter(m.OrdenServicio.id == ocupacion.orden_servicio_id).first()
             if ocupacion.orden_servicio_id else None)
    return orden.fecha_salida_estimada if orden else None


def _demanda_por_tipo(db: Session, taller: m.Taller, dia: date,
                      reservas: dict | None,
                      excluir_citas: set | int | None = None) -> dict:
    """Cuantas unidades de cada tipo compiten por un espacio ese dia.

    Suma las citas ya guardadas y las que esta corrida acaba de colocar y
    todavia no estan en la base (`reservas`, con clave `(dia, tipo)`).

    `excluir_citas` saca del conteo a las citas que se estan moviendo: si no,
    se estorbarian a si mismas y el dia al que ya pertenecen apareceria con un
    lugar menos del que de verdad va a tener.

    Es un CONJUNTO y no una sola cita porque `recalcular` recoloca toda la cola
    de una pasada: una cita que ya esta en la base y ademas ya se aparto un
    lugar en `reservas` se contaria DOS veces, y con la capacidad asi de
    inflada la agenda empuja las citas un dia mas en cada corrida. Se acepta un
    int suelto por comodidad de quien solo mueve una.
    """
    excluidas = (excluir_citas if isinstance(excluir_citas, (set, frozenset))
                 else {excluir_citas} if excluir_citas else set())
    demanda: dict = {}
    for c in (db.query(m.CitaTaller)
              .filter(m.CitaTaller.taller_id == taller.id,
                      m.CitaTaller.estado.in_(ESTADOS_VIVOS),
                      m.CitaTaller.fecha_cita <= dia).all()):
        if not c.unidad or c.id in excluidas:
            continue
        # Duracion 0 = servicio de paso: entra y sale el mismo dia, no toma
        # bahia. Un `max(1, ...)` aqui lo convertiria en un dia de ocupacion y
        # con las ~26 unidades de paso que Alamos atiende a diario el taller
        # apareceria lleno siempre, que es justo lo que `ocupa_espacio` vino a
        # evitar. `None` es una cita vieja sin el dato: esa si cuenta como 1.
        dura = 1 if c.duracion_estimada_dias is None else c.duracion_estimada_dias
        if dura <= 0:
            continue
        if c.fecha_cita + timedelta(days=dura - 1) < dia:
            continue
        t = c.unidad.tipo_unidad_id
        demanda[t] = demanda.get(t, 0) + 1
    for (d, t), n in (reservas or {}).items():
        if d == dia:
            demanda[t] = demanda.get(t, 0) + n
    return demanda


def capacidad_libre(db: Session, taller: m.Taller, dia: date, tipo_unidad_id: int,
                    reservas: dict | None = None,
                    excluir_citas: set | int | None = None) -> int:
    """Cuantas unidades de ese tipo caben ese dia.

    NO es una simple resta, y el motivo es el plano real de Alamos: hay
    espacios DEDICADOS (los 8 de PIPAS solo admiten pipas) y espacios
    GENERICOS sin tipo declarado (ELECTRICOS, LLANTERA) que sirven para
    cualquiera. Los genericos son un pozo comun, asi que una cita de reparto
    tambien le quita lugar a una pipa -- pero solo despues de que el reparto
    llene sus propios espacios dedicados.

    Contar unicamente las citas del mismo tipo sobreestima la capacidad, y
    contarlas todas la subestima. Se hace en dos pasos:

        1. cada tipo agota primero SUS espacios dedicados
        2. lo que le sobre a cada tipo pelea por el pozo comun

    El traslape tambien importa: un servicio de 3 dias que arranca el lunes
    ocupa martes y miercoles. Contarlo solo el lunes es lo que haria que la
    agenda prometiera mas de lo que el taller aguanta.
    """
    if not opera(taller, dia):
        return 0

    espacios = espacios_del_taller(db, taller.id)
    compatibles = [e for e in espacios if _admite(e, tipo_unidad_id)]
    if not compatibles:
        return 0

    # Los ocupados de verdad salen del pozo antes que nada.
    ocupados_por_tipo: dict = {}
    ids = {e.id for e in espacios}
    for oc in (db.query(m.OcupacionEspacio)
               .filter(m.OcupacionEspacio.espacio_id.in_(ids),
                       m.OcupacionEspacio.fecha_salida.is_(None)).all()):
        libera = _libera_en(db, oc)
        if libera is not None and libera <= dia:
            continue
        esp = next((e for e in espacios if e.id == oc.espacio_id), None)
        if esp is None:
            continue
        clave = esp.tipo_unidad_permitido_id  # None = generico
        ocupados_por_tipo[clave] = ocupados_por_tipo.get(clave, 0) + 1

    dedicados = sum(1 for e in compatibles
                    if e.tipo_unidad_permitido_id == tipo_unidad_id)
    genericos = sum(1 for e in compatibles if e.tipo_unidad_permitido_id is None)
    dedicados = max(0, dedicados - ocupados_por_tipo.get(tipo_unidad_id, 0))
    genericos = max(0, genericos - ocupados_por_tipo.get(None, 0))

    demanda = _demanda_por_tipo(db, taller, dia, reservas, excluir_citas)

    # Lo que cada OTRO tipo no alcanzo a meter en sus dedicados se viene al pozo.
    for t, n in demanda.items():
        if t == tipo_unidad_id:
            continue
        propios = sum(1 for e in espacios if e.tipo_unidad_permitido_id == t)
        propios = max(0, propios - ocupados_por_tipo.get(t, 0))
        genericos = max(0, genericos - max(0, n - propios))

    mias = demanda.get(tipo_unidad_id, 0)
    return max(0, dedicados + genericos - mias)


# --------------------------------------------------------------------------- #
# Prioridad -- lexicografica, no una suma ponderada
# --------------------------------------------------------------------------- #
def clave_prioridad(programa: m.ProgramaMantenimiento, hoy: date) -> tuple:
    """Orden de la cola. Se compara criterio por criterio, en orden.

    Con pesos (`0.4*criticidad + 0.3*atraso + ...`) habria que justificar de
    donde salio cada numero, y cuando alguien reclame por que su unidad quedo
    atras no habria como explicarlo. Asi la respuesta siempre cabe en una
    frase: "quedo despues porque la otra tiene un servicio de seguridad".
    """
    plan = programa.plan
    tipo = plan.tipo_servicio if plan else None
    unidad = programa.unidad

    cita = getattr(programa, "cita_actual", None)
    veces = (cita.veces_reprogramada or 0) if cita else 0

    return (
        tipo.criticidad if tipo else 2,                     # 1 seguridad primero
        (programa.fecha_limite - hoy).days,                 # lo vencido primero
        -veces,                                             # ANTI-INANICION
        unidad.tipo.prioridad_operativa if unidad and unidad.tipo else 5,
        programa.id,                                        # FIFO
    )


def score_prioridad(clave: tuple) -> int:
    """Aplana la clave a un entero para poder auditar el orden despues.

    Es solo para poder responder "por que esta cita fue antes que la otra"
    meses despues; el orden real lo decide la tupla, no este numero.
    """
    crit, dias, veces, oper, _ = clave
    return crit * 1_000_000 + max(-999, min(9999, dias)) * 100 + veces * 10 + oper


# --------------------------------------------------------------------------- #
# El algoritmo
# --------------------------------------------------------------------------- #
def taller_de(db: Session, unidad: m.Unidad) -> int | None:
    """A que taller le toca esta unidad.

    Si no tiene taller asignado cae a la CENTRAL, que es la regla real de Baja
    Gas: Libertad es sucursal sin taller y sus unidades se atienden en Alamos.
    Sin este respaldo, una unidad sin el campo lleno queda invisible para la
    agenda para siempre -- y ninguna de las unidades importadas lo trae.
    """
    if unidad is None:
        return None
    if unidad.taller_asignado_id:
        return unidad.taller_asignado_id
    central = db.query(m.Taller).filter(m.Taller.tipo == "CENTRAL",
                                        m.Taller.activo.is_(True)).first()
    return central.id if central else None


def _pendientes(db: Session, taller: m.Taller):
    """Programas que necesitan cita en este taller y todavia no la tienen firme."""
    programas = (db.query(m.ProgramaMantenimiento)
                 .filter(m.ProgramaMantenimiento.estado.in_(("pendiente", "agendado",
                                                             "sin_cupo")))
                 .all())
    salida = []
    for p in programas:
        if taller_de(db, p.unidad) != taller.id:
            continue
        cita = (db.query(m.CitaTaller)
                .filter(m.CitaTaller.programa_mantenimiento_id == p.id,
                        m.CitaTaller.estado.in_(ESTADOS_VIVOS))
                .first())
        p.cita_actual = cita          # atributo de trabajo, no columna
        if cita and cita.estado not in ESTADOS_MOVIBLES and not _movible(cita):
            continue                  # compromiso firme con el chofer: no se toca
        salida.append(p)
    return salida


def _movible(cita: m.CitaTaller) -> bool:
    """Si el recalculo puede mover esta cita sin pedirle permiso a Victor.

    `propuesta`     -> si, libremente: todavia no es un compromiso.
    `confirmada`    -> solo con mas de 48 h de anticipacion, y avisando.
    a menos de 48 h -> no. Al chofer que ya viene en camino no se le mueve la
                       cita: a la tercera vez deja de mirar la app, y ahi se
                       acaba el sistema.
    """
    if cita.estado in ESTADOS_MOVIBLES:
        return True
    if cita.estado not in ESTADOS_VIVOS:
        return False
    faltan = (cita.fecha_cita - ahora_utc().date()).days
    return faltan * 24 > HORAS_INTOCABLE


def recalcular(db: Session, taller: m.Taller, hoy: date | None = None) -> dict:
    """Reparte los programas pendientes sobre la capacidad de los proximos 30 dias.

    Una cola con prioridad asignada dia a dia. No hace falta nada mas
    sofisticado, y conviene que no lo sea: un algoritmo que nadie entiende es
    un algoritmo en el que nadie confia.

    Las citas nacen en `propuesta`. Victor las confirma; a partir de ahi son un
    compromiso y ya no se mueven solas.
    """
    hoy = hoy or ahora_utc().date()
    res = {"propuestas": 0, "movidas": 0, "sin_cupo": 0, "taller": taller.nombre}

    cola = sorted(_pendientes(db, taller), key=lambda p: clave_prioridad(p, hoy))

    # La corrida va a recolocar TODAS las citas de la cola, asi que ninguna de
    # ellas cuenta como ocupante: la unica version valida de donde queda cada
    # una es `reservas`, que se va llenando aqui abajo. Sin esta exclusion cada
    # cita se estorba a si misma y ademas se cuenta doble -- una vez desde la
    # base y otra desde `reservas` -- y la agenda empuja las citas un dia mas
    # en cada corrida del job diario. Eso es lo que hace que el chofer reciba
    # un cambio de fecha cada manana y deje de mirar la app.
    ids_cola = {c.id for c in (getattr(p, "cita_actual", None) for p in cola) if c}
    reservas: dict = {}

    for programa in cola:
        plan = programa.plan
        tipo = plan.tipo_servicio if plan else None
        unidad = programa.unidad
        # Un servicio de paso no toma bahia: se atiende el mismo dia y no
        # compite por capacidad. Meterlo a la cola es lo que haria que el
        # taller apareciera lleno todos los dias y no se pudiera agendar nada.
        dura = tipo.duracion_a_usar() if tipo else 1
        colocada = None

        for dia in dias_habiles(taller, hoy, HORIZONTE_DIAS):
            if dura == 0:
                colocada = dia
                break
            if all(capacidad_libre(db, taller, d, unidad.tipo_unidad_id, reservas,
                                   excluir_citas=ids_cola) > 0
                   for d in _tramo(taller, dia, dura)):
                colocada = dia
                break

        if colocada is None:
            programa.estado = "sin_cupo"
            res["sin_cupo"] += 1
            continue

        # Un servicio de paso no consume capacidad: no se le reserva nada.
        # La reserva va por (dia, tipo) porque la capacidad se calcula por tipo:
        # apuntarla sin el tipo haria que una pipa le quitara lugar a un
        # reparto aunque cada uno tenga sus propios espacios.
        if dura > 0:
            for d in _tramo(taller, colocada, dura):
                clave = (d, unidad.tipo_unidad_id)
                reservas[clave] = reservas.get(clave, 0) + 1

        clave = clave_prioridad(programa, hoy)
        cita = getattr(programa, "cita_actual", None)
        if cita is None:
            cita = m.CitaTaller(
                taller_id=taller.id, unidad_id=unidad.id,
                programa_mantenimiento_id=programa.id,
                tipo_servicio_id=tipo.id if tipo else None,
                fecha_cita=colocada,
                # Copiada del programa y NUNCA se toca: es lo que hace que
                # mover la cita no mueva el compromiso tecnico.
                fecha_limite_origen=programa.fecha_limite,
                duracion_estimada_dias=dura,
                estado="propuesta", origen_agenda="automatica",
                score_prioridad=score_prioridad(clave))
            db.add(cita)
            res["propuestas"] += 1
        # Una cita creada antes de que el plan tuviera tipo de servicio se quedo
        # sin el. Se repara aqui y no en una migracion porque el dato correcto
        # solo se conoce recorriendo el plan, que es justo lo que este bucle ya
        # hizo. Va antes del `elif` para que se corrija aunque la fecha no cambie.
        elif tipo and cita.tipo_servicio_id != tipo.id:
            cita.tipo_servicio_id = tipo.id
            cita.duracion_estimada_dias = dura

        if cita is not None and cita.fecha_cita != colocada:
            db.add(m.Reprogramacion(
                cita_id=cita.id, fecha_anterior=cita.fecha_cita, fecha_nueva=colocada,
                motivo="sin_espacio", automatica=True,
                requirio_autorizacion=cita.estado == "confirmada"))
            cita.fecha_cita = colocada
            cita.duracion_estimada_dias = dura
            cita.veces_reprogramada = (cita.veces_reprogramada or 0) + 1
            cita.score_prioridad = score_prioridad(clave)
            if cita.estado == "confirmada":
                cita.estado = "reprogramada"
            res["movidas"] += 1

        programa.estado = "agendado"

    db.commit()
    return res


def _tramo(taller: m.Taller, inicio: date, dias: int):
    """Los dias habiles que ocupa un servicio que arranca en `inicio`."""
    return list(dias_habiles(taller, inicio, max(1, dias)))


def dias_sin_cupo(db: Session, cita: m.CitaTaller, inicio: date) -> list:
    """De los dias que ocuparia la cita si empezara en `inicio`, cuales no caben.

    Existe porque el algoritmo automatico cuida la capacidad con detalle y el
    movimiento MANUAL se la saltaba entera: Victor podia mandar una cita a un
    dia con cero espacios libres y el sistema decia que si. Una agenda que se
    respeta sola pero cede a cualquier clic no es una agenda, es una sugerencia.

    Se revisa el TRAMO completo y no solo el primer dia: un servicio de tres
    dias que arranca el lunes tambien necesita martes y miercoles.

    Devuelve [(dia, libres)] de los dias donde no alcanza. Vacio = si cabe.
    """
    taller, unidad = cita.taller, cita.unidad
    if not taller or not unidad:
        return []
    dura = cita.duracion_estimada_dias or 1
    if dura <= 0:
        return []          # servicio de paso: no toma bahia, siempre cabe
    faltantes = []
    for d in _tramo(taller, inicio, dura):
        libres = capacidad_libre(db, taller, d, unidad.tipo_unidad_id,
                                 excluir_citas={cita.id})
        if libres <= 0:
            faltantes.append((d, libres))
    return faltantes


def detectar_sin_cupo(db: Session, taller: m.Taller | None = None):
    """Programas que no alcanzan cita ANTES de su fecha limite.

    Esto NO es incumplimiento del chofer: es falta de capacidad del taller, y
    va a otro tablero. Distinguirlo es la razon de ser de todo este modulo.

    Son DOS casos y los dos cuentan, aunque solo el primero sea obvio:

      1. No cupo nada en los 30 dias del horizonte -> estado 'sin_cupo'.
      2. Si cupo, pero la cita quedo DESPUES de la fecha limite.

    El segundo es el que se escapa si uno solo mira el estado. Para el chofer
    es lo mismo -- le dieron una fecha en la que ya va tarde -- y el
    responsable tambien es el mismo: el taller no alcanzo. Dejarlo fuera de
    esta lista lo empujaria al tablero de incumplimientos, que es exactamente
    el error que este diseno vino a corregir.

    Devuelve (programa, cita_o_None) para que quien llame sepa cual de los dos
    casos es sin tener que volver a consultar.
    """
    fuera = []
    for p in db.query(m.ProgramaMantenimiento).filter(
            m.ProgramaMantenimiento.estado.in_(("sin_cupo", "agendado"))).all():
        if taller and taller_de(db, p.unidad) != taller.id:
            continue
        if p.estado == "sin_cupo":
            fuera.append((p, None))
            continue
        cita = (db.query(m.CitaTaller)
                .filter(m.CitaTaller.programa_mantenimiento_id == p.id,
                        m.CitaTaller.estado.in_(ESTADOS_VIVOS))
                .order_by(m.CitaTaller.fecha_cita).first())
        if cita and p.fecha_limite and cita.fecha_cita > p.fecha_limite:
            fuera.append((p, cita))
    return fuera


def cita_out(db: Session, c: m.CitaTaller) -> dict:
    tipo = c.tipo_servicio
    rango = tipo.rango_a_usar() if tipo else (1, 1)

    # Holgura = cuantos dias le sobran a la cita antes del limite tecnico.
    # Negativo significa que la cita cae DESPUES del limite: el taller no
    # alcanzo, y eso no es falta del chofer.
    holgura = None
    if c.fecha_limite_origen and c.fecha_cita:
        holgura = (c.fecha_limite_origen - c.fecha_cita).days

    chofer = None
    if c.unidad:
        from ..flota.flota_service import poseedor_actual
        from ..sistema.comun_service import nombre_chofer
        pid = poseedor_actual(db, c.unidad)
        chofer = nombre_chofer(db, pid) if pid else None

    return {
        "id": c.id,
        "unidad": c.unidad.num_economico if c.unidad else "-",
        "unidad_id": c.unidad_id,
        "tipo_unidad_id": c.unidad.tipo_unidad_id if c.unidad else None,
        "taller": c.taller.nombre if c.taller else "-",
        "taller_id": c.taller_id,
        "servicio": tipo.nombre if tipo else "-",
        "fecha_cita": c.fecha_cita,
        "fecha_limite_origen": c.fecha_limite_origen,
        "dias_de_holgura": holgura,
        "estado": c.estado,
        "duracion_estimada_dias": c.duracion_estimada_dias,
        # Rango y no fecha exacta mientras la muestra sea chica: es menos
        # vistoso y mucho mas honesto que una fecha falsa con precision fingida.
        "duracion_rango": {"tipico": rango[0], "pesimista": rango[1]},
        "veces_reprogramada": c.veces_reprogramada or 0,
        "score_prioridad": c.score_prioridad,
        "movible": _movible(c),
        "confirmada_por_taller": c.fecha_confirmacion_taller is not None,
        "confirmada_por_chofer": c.fecha_confirmacion_chofer is not None,
        # Va contra el POSEEDOR, no el titular: si la unidad esta prestada,
        # el que tiene que presentarse es el receptor.
        "chofer": chofer,
    }
