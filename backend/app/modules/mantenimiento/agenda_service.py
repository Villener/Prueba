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

# Un programa entra a la agenda cuando le faltan estos dias para su fecha limite.
# Se cambia sin desplegar con la clave de configuracion.
CLAVE_ANTICIPACION = "dias_anticipacion_preventivo"
ANTICIPACION_DIAS = 30

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

    Es su planta madre (`taller_asignado_id`): ahi se le agenda el preventivo,
    aunque a veces la atienda otra planta que tenga lugar en ese momento.
    Si no tiene taller asignado cae a la CENTRAL. Sin este respaldo, una unidad
    sin el campo lleno queda invisible para la agenda para siempre -- y ninguna
    de las unidades importadas lo trae.
    """
    if unidad is None:
        return None
    if unidad.taller_asignado_id:
        return unidad.taller_asignado_id
    central = db.query(m.Taller).filter(m.Taller.tipo == "CENTRAL",
                                        m.Taller.activo.is_(True)).first()
    return central.id if central else None


def dias_anticipacion(db: Session) -> int:
    """Cuantos dias antes de su fecha limite entra un programa a la agenda."""
    c = (db.query(m.Configuracion)
         .filter(m.Configuracion.clave == CLAVE_ANTICIPACION).first())
    try:
        return max(0, int(c.valor)) if c else ANTICIPACION_DIAS
    except (TypeError, ValueError):
        return ANTICIPACION_DIAS


def tope_preventivos_por_dia(db: Session) -> int:
    """Cuantas citas de preventivo acepta un taller en un mismo dia (0 = sin tope).

    Es el techo de RN-12 (`meta_preventivos_max`), el numero que ya acordo el
    cliente. Hace falta desde que el preventivo dura horas y no 8 dias: con un
    dia por unidad lo unico que limitaba era el numero de bahias, y la agenda
    llegaba a meter 18 preventivos el mismo dia en Alamos. Las bahias no hacen el
    trabajo; los mecanicos si.
    """
    c = db.query(m.Configuracion).filter(m.Configuracion.clave == "meta_preventivos_max").first()
    try:
        return max(0, int(c.valor)) if c else 7
    except (TypeError, ValueError):
        return 7


def _citas_por_dia(db: Session, taller: m.Taller, desde: date, excluir: set) -> dict:
    cuenta: dict = {}
    for (f,) in (db.query(m.CitaTaller.fecha_cita)
                 .filter(m.CitaTaller.taller_id == taller.id,
                         m.CitaTaller.estado.in_(ESTADOS_VIVOS),
                         m.CitaTaller.fecha_cita >= desde,
                         ~m.CitaTaller.id.in_(excluir or {-1}))):
        cuenta[f] = cuenta.get(f, 0) + 1
    return cuenta


def _pendientes(db: Session, taller: m.Taller, hoy: date | None = None):
    """Programas que necesitan cita en este taller y todavia no la tienen firme.

    `vencido` va en la lista: que un mantenimiento se haya pasado de su fecha
    limite no lo cancela, al contrario -- es el que mas urge. Sin este estado
    aqui, el job que marca los vencidos los sacaba de la cola para siempre y la
    unidad no volvia a recibir cita nunca.

    Y solo los que vencen pronto. La agenda le da a cada programa el PRIMER dia
    con cupo, sin mirar su fecha limite; con la cola entera adentro, una unidad
    recien atendida -- cuyo siguiente servicio vence en 90 dias -- recibia otra
    cita en cuanto sobraba espacio, y el taller haria preventivos cada semana a
    las mismas unidades. Un programa entra a la cola `dias_anticipacion` antes
    de su fecha limite.
    """
    hoy = hoy or ahora_utc().date()
    tope = hoy + timedelta(days=dias_anticipacion(db))
    programas = (db.query(m.ProgramaMantenimiento)
                 .filter(m.ProgramaMantenimiento.estado.in_(("pendiente", "agendado",
                                                             "sin_cupo", "vencido")))
                 .all())
    salida = []
    for p in programas:
        # Dada de baja o bloqueada por Logistica: no se le guarda lugar. El
        # programa sigue vivo y vuelve a la cola solo si la reactivan.
        if p.unidad is None or not p.unidad.activo:
            continue
        if taller_de(db, p.unidad) != taller.id:
            continue
        cita = (db.query(m.CitaTaller)
                .filter(m.CitaTaller.programa_mantenimiento_id == p.id,
                        m.CitaTaller.estado.in_(ESTADOS_VIVOS))
                .first())
        if cita is None and p.fecha_limite > tope:
            # Todavia no le toca. Si se habia quedado 'sin_cupo' de una corrida
            # anterior, ya no es un problema de capacidad: vuelve a 'pendiente'.
            if p.estado == "sin_cupo":
                p.estado = "pendiente"
            continue
        p.cita_actual = cita          # atributo de trabajo, no columna
        if cita and cita.taller_id != taller.id and cita.estado not in ESTADOS_MOVIBLES:
            # Su cita viva es de OTRA planta y el chofer ya la confirmo: se
            # atiende alla y la unidad sigue siendo de esta (le cambiaron la
            # planta madre, como a las de Libertad el 2026-10-08, o la atiende
            # otra planta con lugar). Se respeta donde esta; si entrara a esta
            # cola, la fecha se calcularia contra esta planta y el lugar se
            # seguiria contando en la otra.
            continue
        if cita and cita.estado not in ESTADOS_MOVIBLES and not _movible(cita):
            continue                  # compromiso firme con el chofer: no se toca
        salida.append(p)
    return salida


def _avisar_movimiento(db: Session, cita: m.CitaTaller, anterior: date):
    """Le dice al poseedor que el recalculo le movio una cita comprometida."""
    # Import local: flota_service y security no deben cargarse al importar este
    # modulo (las pruebas de la agenda lo usan solo con los modelos).
    from ...core.security import notificar
    from ..flota.flota_service import poseedor_actual
    poseedor = poseedor_actual(db, cita.unidad) if cita.unidad else None
    if poseedor:
        notificar(db, poseedor, "Se movio tu cita de taller",
                  f"Unidad {cita.unidad.num_economico}: por falta de espacio pasa del "
                  f"{anterior} al {cita.fecha_cita}. Confirma la fecha nueva.",
                  "cita", entidad_tipo="cita_taller", entidad_id=cita.id)


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

    cola = sorted(_pendientes(db, taller, hoy), key=lambda p: clave_prioridad(p, hoy))

    # La corrida va a recolocar TODAS las citas de la cola, asi que ninguna de
    # ellas cuenta como ocupante: la unica version valida de donde queda cada
    # una es `reservas`, que se va llenando aqui abajo. Sin esta exclusion cada
    # cita se estorba a si misma y ademas se cuenta doble -- una vez desde la
    # base y otra desde `reservas` -- y la agenda empuja las citas un dia mas
    # en cada corrida del job diario. Eso es lo que hace que el chofer reciba
    # un cambio de fecha cada manana y deje de mirar la app.
    ids_cola = {c.id for c in (getattr(p, "cita_actual", None) for p in cola) if c}
    reservas: dict = {}
    tope = tope_preventivos_por_dia(db)
    en_el_dia = _citas_por_dia(db, taller, hoy, ids_cola)   # fijas + las de esta corrida

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
            if tope and en_el_dia.get(dia, 0) >= tope:
                continue
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
        en_el_dia[colocada] = en_el_dia.get(colocada, 0) + 1

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

        # Una propuesta que nacio en otra planta (la unidad cambio de planta
        # madre) se queda en ESTA: la fecha que se le acaba de dar es contra el
        # lugar de esta planta. Sin esto la cita conservaba el taller viejo y
        # le quitaba un lugar alla que nadie iba a usar. Solo llega aqui en
        # `propuesta`: las confirmadas de otra planta no entran a la cola.
        if cita.taller_id != taller.id:
            cita.taller_id = taller.id
            res["cambio_de_planta"] = res.get("cambio_de_planta", 0) + 1

        if cita is not None and cita.fecha_cita != colocada:
            # Una cita confirmada (o ya reprogramada) es un compromiso que el
            # chofer conoce. Moverla sin decirle nada lo dejaba presentandose en
            # la fecha vieja y, si no llegaba en la nueva, el job lo acusaba de
            # falta. Se le avisa y tiene que volver a confirmar, igual que
            # cuando Victor la mueve a mano (agenda_controller.reprogramar).
            comprometida = cita.estado in ("confirmada", "reprogramada")
            anterior = cita.fecha_cita
            db.add(m.Reprogramacion(
                cita_id=cita.id, fecha_anterior=anterior, fecha_nueva=colocada,
                motivo="sin_espacio", automatica=True,
                requirio_autorizacion=cita.estado == "confirmada",
                aviso_enviado=comprometida))
            cita.fecha_cita = colocada
            cita.duracion_estimada_dias = dura
            cita.veces_reprogramada = (cita.veces_reprogramada or 0) + 1
            cita.score_prioridad = score_prioridad(clave)
            if comprometida:
                cita.estado = "reprogramada"
                cita.fecha_confirmacion_chofer = None
                _avisar_movimiento(db, cita, anterior)
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

    chofer = telefono = None
    if c.unidad:
        from ..flota.flota_service import poseedor_actual
        from ..sistema.comun_service import nombre_chofer
        pid = poseedor_actual(db, c.unidad)
        chofer = nombre_chofer(db, pid) if pid else None
        if pid:
            u = db.query(m.Usuario.telefono).filter(m.Usuario.id == pid).first()
            telefono = u[0] if u else None

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
        # Para el boton de WhatsApp de la agenda: Victor le escribe al chofer
        # desde su propio telefono, sin servidor de mensajes de por medio.
        "chofer_telefono": telefono,
    }
