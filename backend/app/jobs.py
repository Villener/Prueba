




"""Procesos automaticos - CU-AUT-01 a CU-AUT-06.

Actor: "Programador de tareas" (el reloj del sistema). Un caso de uso sin actor
esta mal formado; estos los dispara el tiempo, no una persona.

Los tres primeros corren a diario. CU-AUT-06 (recalibrar duraciones) es mensual
por naturaleza -- una muestra nueva al dia no mueve una mediana -- pero se deja
en `correr_todos` porque es idempotente y barato: si no hay muestras nuevas
suficientes, no toca nada.
"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from . import models as m
from . import services as svc
from .core.security import notificar
from .core.tiempo import ahora_utc
from .modules.mantenimiento import agenda_service as agenda


def _config(db: Session, clave: str, defecto: int) -> int:
    c = db.query(m.Configuracion).filter(m.Configuracion.clave == clave).first()
    try:
        return int(c.valor) if c else defecto
    except (TypeError, ValueError):
        return defecto


def generar_avisos_incumplimiento(db: Session) -> int:
    """CU-AUT-01 / RN-05 (v2.0).

    El sistema NO sanciona: emite un AVISO al gerente y al administrador de
    compras, ellos hablan con el chofer en persona y despues marcan el caso
    como atendido. Por eso no hay monto ni proceso de inconformidad.

    El aviso se emite contra el POSEEDOR de la unidad (RN-01), no contra el
    titular, y se guarda DE DONDE salio esa conclusion (`fundamento_poseedor`)
    para que el supervisor pueda ver quien la tenia a su cargo ese dia.
    """
    tolerancia = _config(db, "dias_tolerancia_aviso", 0)
    limite = date.today() - timedelta(days=tolerancia)
    creados = 0

    vencidos = (db.query(m.ProgramaMantenimiento)
                .filter(m.ProgramaMantenimiento.estado == "pendiente",
                        m.ProgramaMantenimiento.fecha_limite < limite).all())
    for p in vencidos:
        p.estado = "vencido"
        ya = (db.query(m.AvisoIncumplimiento)
              .filter(m.AvisoIncumplimiento.unidad_id == p.unidad_id,
                      m.AvisoIncumplimiento.fecha_generacion == p.fecha_limite).first())
        if ya:
            continue
        poseedor = svc.poseedor_actual(db, p.unidad)
        if not poseedor:
            continue
        dias = (date.today() - p.fecha_limite).days

        # De donde sale que ESE chofer era el responsable.
        jor = (db.query(m.Jornada)
               .filter(m.Jornada.unidad_id == p.unidad_id, m.Jornada.hora_fin.is_(None))
               .first())
        pres = (db.query(m.PrestamoUnidad)
                .filter(m.PrestamoUnidad.unidad_id == p.unidad_id,
                        m.PrestamoUnidad.estado.in_(["aceptado", "activo"]),
                        m.PrestamoUnidad.fecha_fin_real.is_(None)).first())
        if jor:
            fundamento, jid, pid = "jornada", jor.id, None
        elif pres:
            fundamento, jid, pid = "prestamo", None, pres.id
        else:
            fundamento, jid, pid = "titularidad", None, None

        db.add(m.AvisoIncumplimiento(
            unidad_id=p.unidad_id, chofer_id=poseedor,
            fundamento_poseedor=fundamento, jornada_id=jid, prestamo_id=pid,
            fecha_generacion=p.fecha_limite, dias_atraso=dias, estado="abierto"))

        detalle = (f"Unidad {p.unidad.num_economico}: mantenimiento vencido hace {dias} dias. "
                   f"Responsable por {fundamento}.")
        # Al gerente y al administrador, que son quienes hablan con el chofer.
        for u in (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
                  .filter(m.Rol.nombre.in_(["gerente", "administrador"])).all()):
            notificar(db, u.id, "Aviso de incumplimiento", detalle,
                      "aviso", "unidad", p.unidad_id)
        # Y al chofer, para que sepa antes de que le hablen (CU-CHO-17).
        notificar(db, poseedor, "Mantenimiento vencido",
                  f"Unidad {p.unidad.num_economico}: el mantenimiento vencio hace {dias} dias.",
                  "aviso", "unidad", p.unidad_id)
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
