




"""Procesos automaticos - CU-AUT-01 a CU-AUT-06.

Actor: "Programador de tareas" (el reloj del sistema). Un caso de uso sin actor
esta mal formado; estos los dispara el tiempo, no una persona.

Los tres primeros corren a diario. CU-AUT-06 (recalibrar duraciones) es mensual
por naturaleza -- una muestra nueva al dia no mueve una mediana -- pero se deja
en `correr_todos` porque es idempotente y barato: si no hay muestras nuevas
suficientes, no toca nada.
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from . import models as m
from . import services as svc
from .core.security import notificar
from .core.tiempo import TZ_OPERACION, ahora_utc
from .modules.mantenimiento import agenda_service as agenda


def _config(db: Session, clave: str, defecto: int) -> int:
    c = db.query(m.Configuracion).filter(m.Configuracion.clave == clave).first()
    try:
        return int(c.valor) if c else defecto
    except (TypeError, ValueError):
        return defecto


def _fundamento_poseedor(db: Session, unidad_id: int):
    """De donde sale que ESE chofer era el responsable de la unidad.

    Se guarda con el aviso para que el supervisor pueda ver en que se baso el
    sistema, y no tenga que creerle. Devuelve (fundamento, jornada_id, prestamo_id).
    """
    jor = (db.query(m.Jornada)
           .filter(m.Jornada.unidad_id == unidad_id, m.Jornada.hora_fin.is_(None))
           .first())
    if jor:
        return "jornada", jor.id, None
    pres = (db.query(m.PrestamoUnidad)
            .filter(m.PrestamoUnidad.unidad_id == unidad_id,
                    m.PrestamoUnidad.estado.in_(["aceptado", "activo"]),
                    m.PrestamoUnidad.fecha_fin_real.is_(None)).first())
    if pres:
        return "prestamo", None, pres.id
    return "titularidad", None, None


def _se_presento(db: Session, cita: m.CitaTaller) -> bool:
    """Si la unidad llego al taller para esa cita.

    Se pregunta por la ORDEN DE SERVICIO y no por el estado de la cita porque
    nadie marca `cumplida` todavia: quien recibe la unidad abre una orden, y esa
    orden es la huella real de que el chofer si se presento. El dia en que
    alguien cierre el ciclo marcando la cita, esto se puede reemplazar por una
    lectura del estado.

    El corte se arma en hora de TIJUANA y se convierte a UTC. `fecha_cita` es un
    dia del calendario del taller; tomar su medianoche como si fuera UTC correria
    la frontera siete u ocho horas y daria por presentada a una unidad que entro
    la tarde ANTERIOR a su cita.

    Es deliberadamente generoso: cualquier entrada de esa unidad desde el dia de
    la cita en adelante cuenta como que si se presento, aunque haya llegado
    tarde. Ante la duda no se le genera un aviso a nadie -- el costo de acusar de
    mas a un chofer es mucho mayor que el de dejar pasar un caso.
    """
    inicio_tj = datetime.combine(cita.fecha_cita, datetime.min.time())
    inicio = inicio_tj.replace(tzinfo=TZ_OPERACION).astimezone(timezone.utc)
    return (db.query(m.OrdenServicio)
            .filter(m.OrdenServicio.unidad_id == cita.unidad_id,
                    m.OrdenServicio.fecha_entrada >= inicio)
            .first() is not None)


def generar_avisos_incumplimiento(db: Session) -> int:
    """CU-AUT-01 / RN-05 (v2.0).

    El sistema NO sanciona: emite un AVISO al gerente y al administrador de
    compras, ellos hablan con el chofer en persona y despues marcan el caso
    como atendido. Por eso no hay monto ni proceso de inconformidad.

    EL AVISO CUELGA DE LA CITA, NO DEL PROGRAMA, y ese es el punto entero:

        el chofer incumple si falto a una CITA CONFIRMADA.
        si el taller nunca pudo darsela, el incumplimiento es del TALLER.

    Antes esto se calculaba sobre `ProgramaMantenimiento.estado == 'pendiente'`
    con la fecha limite vencida, sin mirar la cita en ningun momento. Con esa
    version, una unidad que no alcanzo cupo -- o a la que Victor le cancelo la
    cita -- le generaba el aviso al chofer, que es exactamente el defecto que
    docs/agenda-mantenimiento.md vino a corregir. La falta de capacidad ya se
    reporta aparte, en /api/agenda/sin-cupo, y tiene otro responsable.

    Al no haber cita confirmada de por medio, ya no hay forma de que este job
    culpe al chofer por un problema del taller.

    El aviso se emite contra el POSEEDOR de la unidad (RN-01), no contra el
    titular, y se guarda DE DONDE salio esa conclusion (`fundamento_poseedor`).
    """
    tolerancia = _config(db, "dias_tolerancia_aviso", 0)
    limite = date.today() - timedelta(days=tolerancia)
    creados = 0

    # Un mantenimiento vencido se marca como tal -- es un hecho y el tablero lo
    # necesita -- pero eso YA NO genera aviso por si solo. Son dos preguntas
    # distintas: "esta vencido" y "de quien es la culpa".
    for p in (db.query(m.ProgramaMantenimiento)
              .filter(m.ProgramaMantenimiento.estado == "pendiente",
                      m.ProgramaMantenimiento.fecha_limite < limite).all()):
        p.estado = "vencido"

    faltadas = (db.query(m.CitaTaller)
                .filter(m.CitaTaller.estado.in_(("confirmada", "reprogramada")),
                        m.CitaTaller.fecha_cita < limite).all())
    for c in faltadas:
        if not c.unidad:
            continue
        if _se_presento(db, c):
            continue                      # la unidad si llego: no hay nada que avisar

        # Se deja escrito en la cita, que es donde vive el hecho. Sin esto la
        # cita seguiria "viva" para siempre y el recalculo la arrastraria dia
        # tras dia hacia adelante.
        c.estado = "no_asistio"

        # `cita_id` es unique en el modelo: una cita perdida = un solo aviso.
        ya = (db.query(m.AvisoIncumplimiento)
              .filter(m.AvisoIncumplimiento.cita_id == c.id).first())
        if ya:
            continue
        poseedor = svc.poseedor_actual(db, c.unidad)
        if not poseedor:
            continue

        # El atraso se mide contra el compromiso TECNICO (la fecha limite del
        # plan), no contra la cita: la cita se pudo haber movido varias veces y
        # lo que le importa al gerente es cuanto lleva la unidad sin servicio.
        referencia = c.fecha_limite_origen or c.fecha_cita
        dias = (date.today() - referencia).days
        fundamento, jid, pid = _fundamento_poseedor(db, c.unidad_id)

        db.add(m.AvisoIncumplimiento(
            cita_id=c.id, unidad_id=c.unidad_id, chofer_id=poseedor,
            fundamento_poseedor=fundamento, jornada_id=jid, prestamo_id=pid,
            fecha_generacion=c.fecha_cita, dias_atraso=max(0, dias),
            estado="abierto"))

        detalle = (f"Unidad {c.unidad.num_economico}: no se presento a su cita "
                   f"del {c.fecha_cita} en {c.taller.nombre if c.taller else 'el taller'}. "
                   f"Responsable por {fundamento}.")
        # Al gerente y al administrador, que son quienes hablan con el chofer.
        for u in (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
                  .filter(m.Rol.nombre.in_(["gerente", "administrador"])).all()):
            notificar(db, u.id, "Aviso de incumplimiento", detalle,
                      "aviso", "unidad", c.unidad_id)
        # Y al SUPERVISOR de ese chofer, que es quien firma la amonestacion
        # (CU-SUP-10). Sin esto el aviso le llegaba a todos menos a quien tiene
        # que actuar, y la falta se quedaba en la lista sin que nadie la viera.
        ch = db.query(m.Chofer).filter(m.Chofer.usuario_id == poseedor).first()
        if ch and ch.plantilla_id:
            pl = db.query(m.Plantilla).filter(m.Plantilla.id == ch.plantilla_id).first()
            if pl and pl.supervisor_id:
                notificar(db, pl.supervisor_id, "Falta por amonestar",
                          detalle + " Puedes amonestarlo desde Cumplimiento.",
                          "amonestacion", "unidad", c.unidad_id)

        # Y al chofer, para que sepa antes de que le hablen (CU-CHO-17).
        notificar(db, poseedor, "Faltaste a tu cita de taller",
                  f"Unidad {c.unidad.num_economico}: tenias cita el {c.fecha_cita} "
                  f"y no se registro tu entrada al taller.",
                  "aviso", "unidad", c.unidad_id)
        creados += 1

    db.commit()
    return creados


# Nombre viejo, por si algo externo lo llama todavia.
generar_penalizaciones = generar_avisos_incumplimiento


def generar_alertas_unidades_paradas(db: Session) -> int:
    """CU-AUT-02 / RN-08: alerta recurrente hasta que se atienda."""
    meses = _config(db, "meses_unidad_parada", 3)
    corte = ahora_utc() - timedelta(days=30 * meses)
    nuevas = 0

    ordenes = (db.query(m.OrdenServicio)
               .filter(m.OrdenServicio.estado != "cerrada",
                       m.OrdenServicio.fecha_entrada < corte).all())
    gerentes = (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
                .filter(m.Rol.nombre == "gerente").all())

    for o in ordenes:
        alerta = (db.query(m.AlertaGerencia)
                  .filter(m.AlertaGerencia.tipo == "unidad_parada_3_meses",
                          m.AlertaGerencia.unidad_id == o.unidad_id,
                          m.AlertaGerencia.atendida.is_(False)).first())
        dias = (ahora_utc() - o.fecha_entrada).days
        detalle = (f"Unidad {o.unidad.num_economico} lleva {dias} dias en "
                   f"{o.taller.nombre if o.taller else 'taller'} (orden {o.folio})")
        if alerta:
            # Reincide: vuelve a notificar mientras no se atienda.
            alerta.veces_notificada += 1
            alerta.ultima_notificacion = ahora_utc()
            alerta.detalle = detalle
        else:
            alerta = m.AlertaGerencia(tipo="unidad_parada_3_meses", unidad_id=o.unidad_id,
                                      detalle=detalle)
            db.add(alerta)
            nuevas += 1
        for g in gerentes:
            notificar(db, g.id, "Unidad parada mas de 3 meses", detalle, "alerta")

    db.commit()
    return nuevas


def cerrar_prestamos_vencidos(db: Session) -> int:
    """CU-AUT-03 / RN-03: al vencer, la responsabilidad vuelve al titular."""
    cerrados = 0
    vencidos = (db.query(m.PrestamoUnidad)
                .filter(m.PrestamoUnidad.estado == "activo",
                        m.PrestamoUnidad.fecha_fin_prevista < date.today()).all())
    for p in vencidos:
        p.estado = "vencido"
        p.fecha_fin_real = ahora_utc()
        svc.sincronizar_poseedor(db, p.unidad)
        notificar(db, p.chofer_presta_id, "Prestamo vencido",
                  f"La unidad {p.unidad.num_economico} regreso a tu responsabilidad "
                  "por vencimiento del prestamo (RN-03).", "prestamo")
        notificar(db, p.chofer_recibe_id, "Prestamo vencido",
                  f"Ya no eres responsable de la unidad {p.unidad.num_economico}.", "prestamo")
        cerrados += 1
    db.commit()
    return cerrados


def recalcular_agenda(db: Session) -> dict:
    """CU-AUT-04 / disparador D5: la red de seguridad diaria de la agenda.

    Los otros cuatro disparadores (D1 se libera un espacio, D2 llega una
    urgencia, D3 cambia la ETA de las piezas, D4 entra una necesidad nueva) los
    dispara el evento en el momento. Este corre al abrir el taller y recalcula
    todo, que es lo que atrapa las citas que dejaron de caber antes de su fecha
    limite sin que nadie tocara nada.
    """
    total = {"propuestas": 0, "movidas": 0, "sin_cupo": 0}
    for taller in db.query(m.Taller).filter(m.Taller.activo.is_(True)).all():
        r = agenda.recalcular(db, taller)
        for k in total:
            total[k] += r[k]

    # El "sin cupo" NO es incumplimiento del chofer: es capacidad del taller, y
    # por eso va al gerente y a la agenda, no al tablero de incumplimientos.
    sin_cupo = agenda.detectar_sin_cupo(db)
    if sin_cupo:
        for usuario_id in _destinatarios_capacidad(db):
            notificar(db, usuario_id, "Taller sin cupo",
                      f"{len(sin_cupo)} unidad(es) no alcanzan cita antes de su fecha "
                      "limite. Es un problema de capacidad del taller, no del chofer.",
                      "capacidad")
    db.commit()
    return total


def _destinatarios_capacidad(db: Session) -> list[int]:
    """Quien se entera de que el taller no da abasto: gerencia y la agenda."""
    ids = []
    for clave in ("gerente", "administrador"):
        rol = db.query(m.Rol).filter(m.Rol.nombre == clave).first()
        if not rol:
            continue
        ids += [ur.usuario_id for ur in
                db.query(m.UsuarioRol).filter(m.UsuarioRol.rol_id == rol.id).all()]
    return sorted(set(ids))


def avisar_citas_proximas(db: Session) -> int:
    """CU-AUT-05: avisos de cita a 48 h y a 24 h.

    Dos hitos, no uno. El de 48 h es el ultimo momento en que la cita todavia
    se puede mover sola; el de 24 h ya es recordatorio de un compromiso firme.
    Avisar una sola vez a 24 h dejaria al chofer sin margen para reclamar un
    cambio, y avisar solo a 48 h se olvida.

    Idempotente por el par (cita, hito): el job puede correr N veces al dia sin
    duplicar el aviso.
    """
    enviados = 0
    hoy = ahora_utc().date()
    citas = (db.query(m.CitaTaller)
             .filter(m.CitaTaller.estado.in_(("propuesta", "confirmada", "reprogramada")),
                     m.CitaTaller.fecha_cita >= hoy).all())
    for c in citas:
        faltan = (c.fecha_cita - hoy).days
        if faltan not in (1, 2):
            continue
        hito = 24 if faltan == 1 else 48
        titulo = f"Tu cita de taller es en {hito} h"
        # Devuelve el id del chofer, que en este modelo ES su usuario_id.
        # Y va contra el POSEEDOR, no contra el titular: si la unidad estaba
        # prestada, el que tiene que presentarse es el receptor.
        poseedor_id = svc.poseedor_actual(db, c.unidad) if c.unidad else None
        if not poseedor_id:
            continue
        ya = (db.query(m.Notificacion)
              .filter(m.Notificacion.usuario_id == poseedor_id,
                      m.Notificacion.titulo == titulo,
                      m.Notificacion.entidad_tipo == "cita_taller",
                      m.Notificacion.entidad_id == c.id).first())
        if ya:
            continue
        notificar(db, poseedor_id, titulo,
                  f"Unidad {c.unidad.num_economico} en {c.taller.nombre} el "
                  f"{c.fecha_cita}. Confirma que te vas a presentar.", "cita",
                  entidad_tipo="cita_taller", entidad_id=c.id)
        enviados += 1
    db.commit()
    return enviados


def recalibrar_duraciones_servicio(db: Session) -> int:
    """CU-AUT-06: el sistema aprende cuanto dura de verdad cada servicio.

    Los tipos nacen con la mediana medida en el Excel del taller
    (docs/analisis-detallado-taller.md), pero ese numero es PERMANENCIA: incluye
    la espera por refacciones y por autorizacion del gerente. Lo que la agenda
    necesita es cuanto ocupa la unidad la bahia, y eso solo lo puede medir el
    sistema con sus propias ordenes.

    Por eso se exige una muestra propia de al menos MUESTRAS_MINIMAS antes de
    pisar el dato del Excel: cambiar 224 observaciones por 3 seria un retroceso,
    pero cambiarlas por 10 propias no lo es, porque las propias miden la cosa
    correcta.

    Pendiente declarado: todavia NO se descuentan los dias detenida esperando
    refacciones. Hace falta historiar los cambios de estado de la orden
    (modelo-er.md: MEDICION_DURACION.dias_detenida_espera_refacciones). Hasta
    entonces la medicion propia arrastra el mismo sesgo que la del Excel, solo
    que mas chico.
    """
    recalibrados = 0
    for tipo in db.query(m.TipoServicio).filter(m.TipoServicio.activo.is_(True)).all():
        if not tipo.ocupa_espacio:
            continue  # un servicio de paso no tiene duracion que aprender
        cerradas = (db.query(m.OrdenServicio)
                    .filter(m.OrdenServicio.tipo_servicio_id == tipo.id,
                            m.OrdenServicio.fecha_salida.isnot(None),
                            m.OrdenServicio.fecha_entrada.isnot(None)).all())
        if len(cerradas) < m.TipoServicio.MUESTRAS_MINIMAS:
            continue
        if tipo.recalibrar([(o.fecha_salida - o.fecha_entrada).days for o in cerradas]):
            recalibrados += 1
    db.commit()
    return recalibrados


def correr_todos(db: Session) -> dict:
    return {
        "avisos_incumplimiento": generar_avisos_incumplimiento(db),
        "alertas_nuevas": generar_alertas_unidades_paradas(db),
        "prestamos_cerrados": cerrar_prestamos_vencidos(db),
        "agenda": recalcular_agenda(db),
        "avisos_cita": avisar_citas_proximas(db),
        "servicios_recalibrados": recalibrar_duraciones_servicio(db),
    }
