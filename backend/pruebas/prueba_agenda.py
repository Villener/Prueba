# -*- coding: utf-8 -*-
"""Pruebas de la agenda automatica de mantenimiento.

Verifica app/modules/mantenimiento/agenda_service.py contra las reglas de
docs/agenda-mantenimiento.md. Cada caso arma su propia base SQLite en memoria
y siembra un taller chico, asi que no toca bajagas.db ni necesita el servidor
levantado.

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_agenda.py     (Windows)
    .venv/bin/python pruebas/prueba_agenda.py             (Linux / Docker)

No usa pytest a proposito: no es dependencia del proyecto y esto tiene que
poder correrse en cualquier maquina donde ya funcione el backend.

Un caso marcado PENDIENTE es un defecto conocido que todavia no se arregla.
Falla a proposito y no cuenta como error: esta escrito para que el dia que se
corrija, la prueba avise sola.
"""
import os
import sys
import traceback
from datetime import date, timedelta

# backend/pruebas/prueba_agenda.py -> backend/
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

# Antes de importar la app: que no abra la base de verdad.
os.environ["DATABASE_URL"] = "sqlite://"

from sqlalchemy import create_engine                       # noqa: E402
from sqlalchemy.orm import sessionmaker                    # noqa: E402

from app import models as m                                # noqa: E402
from app.core.database import Base                         # noqa: E402
from app.modules.mantenimiento import agenda_service as ag  # noqa: E402

CASOS = []


def caso(nombre, pendiente=False):
    """Registra un caso. `pendiente` = defecto conocido, aun sin arreglar."""
    def deco(fn):
        CASOS.append((nombre, fn, pendiente))
        return fn
    return deco


# --------------------------------------------------------------------- #
# Utilidades para sembrar un taller de prueba
# --------------------------------------------------------------------- #
def nueva_db():
    """Base limpia en memoria, con la misma sesion que usa la app."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    # autoflush=False igual que app.core.database.SessionLocal: con autoflush
    # encendido las citas recien creadas se guardarian solas a media corrida y
    # la prueba dejaria de parecerse a produccion.
    return sessionmaker(bind=eng, autocommit=False, autoflush=False)()


def sembrar(db, opera_sabado=True, dedicados_pipa=0, dedicados_rep=0,
            genericos=0, patio=0):
    """Un taller con dos zonas: OPERATIVA (capacidad) y PATIO (no cuenta)."""
    t = m.Taller(nombre="Alamos", tipo="CENTRAL", opera_sabado=opera_sabado, activo=True)
    db.add(t); db.flush()
    pipa = m.TipoUnidad(nombre="PIPA", prioridad_operativa=1)
    rep = m.TipoUnidad(nombre="REPARTO", prioridad_operativa=3)
    db.add_all([pipa, rep]); db.flush()

    z = m.ZonaTaller(taller_id=t.id, nombre="OPERATIVA", cuenta_para_ocupacion=True)
    zp = m.ZonaTaller(taller_id=t.id, nombre="PATIO", cuenta_para_ocupacion=False)
    db.add_all([z, zp]); db.flush()

    n = 0
    for _ in range(dedicados_pipa):
        n += 1
        db.add(m.Espacio(zona_id=z.id, numero="P%d" % n,
                         tipo_unidad_permitido_id=pipa.id, activo=True))
    for _ in range(dedicados_rep):
        n += 1
        db.add(m.Espacio(zona_id=z.id, numero="R%d" % n,
                         tipo_unidad_permitido_id=rep.id, activo=True))
    for _ in range(genericos):
        n += 1
        db.add(m.Espacio(zona_id=z.id, numero="G%d" % n, activo=True))
    for _ in range(patio):
        n += 1
        db.add(m.Espacio(zona_id=zp.id, numero="Y%d" % n, activo=True))
    db.flush()
    return t, pipa, rep


def servicio(db, nombre, criticidad=2, dias=1, ocupa=True):
    s = m.TipoServicio(nombre=nombre, criticidad=criticidad,
                       duracion_estimada_dias=dias, ocupa_espacio=ocupa)
    db.add(s); db.flush()
    return s


def unidad(db, eco, tipo, taller=None):
    u = m.Unidad(num_economico=eco, tipo_unidad_id=tipo.id,
                 taller_asignado_id=(taller.id if taller else None), activo=True)
    db.add(u); db.flush()
    return u


def programa(db, u, srv, limite):
    p = m.PlanMantenimiento(nombre="plan-" + srv.nombre, tipo_servicio_id=srv.id,
                            activo=True)
    db.add(p); db.flush()
    pr = m.ProgramaMantenimiento(unidad_id=u.id, plan_id=p.id, fecha_limite=limite,
                                 estado="pendiente")
    db.add(pr); db.flush()
    return pr


def citas(db):
    return db.query(m.CitaTaller).order_by(m.CitaTaller.id).all()


LUNES = date(2026, 9, 14)   # un lunes de verdad, para que el calendario cuadre


# ===================================================================== #
# Calendario y capacidad
# ===================================================================== #
@caso("1. Calendario: domingo nunca opera; sabado depende del taller")
def c1():
    db = nueva_db()
    t, _, _ = sembrar(db, opera_sabado=False, genericos=5)
    dom, sab = date(2026, 9, 13), date(2026, 9, 12)
    assert ag.opera(t, dom) is False, "domingo no debe operar"
    assert ag.opera(t, sab) is False, "sabado no debe operar con opera_sabado=False"
    assert ag.opera(t, LUNES) is True
    t.opera_sabado = True
    assert ag.opera(t, sab) is True, "sabado debe operar con opera_sabado=True"
    assert ag.opera(t, dom) is False, "domingo sigue cerrado aunque opere sabado"
    t.opera_sabado = False
    ds = list(ag.dias_habiles(t, date(2026, 9, 11), 3))   # arranca en viernes
    assert ds == [date(2026, 9, 11), LUNES, date(2026, 9, 15)], ds
    return "domingo cerrado, sabado configurable, dias_habiles salta el fin de semana"


@caso("2. Capacidad: el patio (cuenta_para_ocupacion=False) NO es capacidad")
def c2():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=3, patio=45)
    libre = ag.capacidad_libre(db, t, LUNES, pipa.id)
    assert libre == 3, "esperaba 3 (solo la zona operativa), dio %s" % libre
    return "45 lugares de patio no inflan la capacidad: quedan 3"


@caso("3. Espacio dedicado + pozo comun de genericos")
def c3():
    db = nueva_db()
    t, pipa, rep = sembrar(db, dedicados_pipa=2, dedicados_rep=1, genericos=2)
    assert ag.capacidad_libre(db, t, LUNES, pipa.id) == 4
    assert ag.capacidad_libre(db, t, LUNES, rep.id) == 3
    srv = servicio(db, "aceite", dias=1)
    for i in (1, 2):
        u = unidad(db, "R%d" % i, rep, t)
        db.add(m.CitaTaller(taller_id=t.id, unidad_id=u.id, fecha_cita=LUNES,
                            duracion_estimada_dias=1, estado="propuesta",
                            tipo_servicio_id=srv.id))
    db.flush()
    libre_pipa = ag.capacidad_libre(db, t, LUNES, pipa.id)
    assert libre_pipa == 3, \
        "la 2a cita de reparto debe robar 1 generico: esperaba 3, dio %s" % libre_pipa
    return "reparto agota su dedicado antes de tocar el pozo comun (pipa: 4 -> 3)"


@caso("4. Traslape: un servicio de 3 dias ocupa los 3, no solo el primero")
def c4():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "transmision", dias=3)
    u = unidad(db, "P1", pipa, t)
    db.add(m.CitaTaller(taller_id=t.id, unidad_id=u.id, fecha_cita=LUNES,
                        duracion_estimada_dias=3, estado="propuesta",
                        tipo_servicio_id=srv.id))
    db.flush()
    libres = [ag.capacidad_libre(db, t, LUNES + timedelta(days=i), pipa.id)
              for i in range(4)]
    assert libres == [0, 0, 0, 1], "esperaba [0,0,0,1], dio %s" % libres
    return "lun/mar/mie ocupados, jueves libre"


@caso("5. Servicio de paso (ocupa_espacio=False) no consume capacidad")
def c5():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    paso = servicio(db, "niveles", dias=1, ocupa=False)
    assert paso.duracion_a_usar() == 0
    for i in range(5):
        u = unidad(db, "N%d" % i, pipa, t)
        programa(db, u, paso, LUNES + timedelta(days=30))
    r = ag.recalcular(db, t, hoy=LUNES)
    cs = citas(db)
    assert r["sin_cupo"] == 0, "ningun servicio de paso debe quedar sin cupo: %s" % r
    assert all(c.fecha_cita == LUNES for c in cs), [c.fecha_cita for c in cs]
    assert ag.capacidad_libre(db, t, LUNES, pipa.id) == 1, "no debe consumir la bahia"
    return "5 servicios de paso el mismo dia con 1 sola bahia, y la bahia sigue libre"


@caso("6. Una cita de paso guardada no le quita el lugar a nadie")
def c6():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    paso = servicio(db, "niveles", dias=1, ocupa=False)
    u = unidad(db, "S1", pipa, t)
    db.add(m.CitaTaller(taller_id=t.id, unidad_id=u.id, fecha_cita=LUNES,
                        duracion_estimada_dias=0, estado="propuesta",
                        tipo_servicio_id=paso.id))
    db.flush()
    libre = ag.capacidad_libre(db, t, LUNES, pipa.id)
    dem = ag._demanda_por_tipo(db, t, LUNES, None)
    assert libre == 1, \
        ("una cita con duracion 0 consumio bahia: libres=%s demanda=%s" % (libre, dem))
    return "duracion 0 no consume capacidad"


@caso("7. Los servicios de paso no tapan el taller en la corrida siguiente")
def c7():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    paso = servicio(db, "niveles", dias=1, ocupa=False)
    real = servicio(db, "afinacion", dias=1, ocupa=True)
    for i in range(5):
        u = unidad(db, "T%d" % i, pipa, t)
        programa(db, u, paso, LUNES + timedelta(days=30))
    ag.recalcular(db, t, hoy=LUNES)          # 1a corrida: solo servicios de paso
    u = unidad(db, "TR", pipa, t)
    pr = programa(db, u, real, LUNES + timedelta(days=5))
    ag.recalcular(db, t, hoy=LUNES)          # 2a corrida: entra un servicio real
    c = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=pr.id).one()
    assert c.fecha_cita == LUNES, \
        ("con la bahia libre la afinacion debio quedar el %s y quedo el %s: las "
         "citas de paso ya guardadas ocuparon la capacidad" % (LUNES, c.fecha_cita))
    return "la afinacion entra el lunes pese a las 5 citas de paso"


@caso("8. Ocupacion real: sin ETA el espacio se cuenta ocupado indefinido")
def c8():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    u = unidad(db, "I1", pipa, t)
    o = m.OrdenServicio(folio="OS-1", unidad_id=u.id, taller_id=t.id,
                        estado="espera_refacciones")
    db.add(o); db.flush()
    esp = db.query(m.Espacio).first()
    db.add(m.OcupacionEspacio(espacio_id=esp.id, unidad_id=u.id, orden_servicio_id=o.id))
    db.flush()
    lejos = ag.capacidad_libre(db, t, LUNES + timedelta(days=25), pipa.id)
    assert lejos == 0, "sin ETA el espacio no se libera nunca: dio %s" % lejos
    o.fecha_salida_estimada = LUNES + timedelta(days=3)
    antes = ag.capacidad_libre(db, t, LUNES + timedelta(days=2), pipa.id)
    despues = ag.capacidad_libre(db, t, LUNES + timedelta(days=4), pipa.id)
    assert antes == 0 and despues == 1, "antes=%s despues=%s" % (antes, despues)
    return "sin ETA ocupado indefinido; con ETA el dia 3, libre desde el dia 4"


# ===================================================================== #
# Orden de la cola
# ===================================================================== #
@caso("9. Prioridad: seguridad antes que preventivo, aunque venza despues")
def c9():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    seg = servicio(db, "frenos", criticidad=1, dias=1)
    prev = servicio(db, "afinacion", criticidad=2, dias=1)
    u1 = unidad(db, "A1", pipa, t); p1 = programa(db, u1, prev, LUNES)
    u2 = unidad(db, "A2", pipa, t); p2 = programa(db, u2, seg, LUNES + timedelta(days=10))
    ag.recalcular(db, t, hoy=LUNES)
    c_seg = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=p2.id).one()
    c_prev = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=p1.id).one()
    assert c_seg.fecha_cita < c_prev.fecha_cita, \
        "seguridad debe ir primero: seg=%s prev=%s" % (c_seg.fecha_cita, c_prev.fecha_cita)
    return "frenos %s antes que afinacion %s" % (c_seg.fecha_cita, c_prev.fecha_cita)


@caso("10. Prioridad: a igual criticidad, primero el que vence antes")
def c10():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", criticidad=2, dias=1)
    u1 = unidad(db, "B1", pipa, t); p1 = programa(db, u1, srv, LUNES + timedelta(days=20))
    u2 = unidad(db, "B2", pipa, t); p2 = programa(db, u2, srv, LUNES - timedelta(days=3))
    ag.recalcular(db, t, hoy=LUNES)
    ca = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=p1.id).one()
    cb = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=p2.id).one()
    assert cb.fecha_cita < ca.fecha_cita, \
        "vencido=%s holgado=%s" % (cb.fecha_cita, ca.fecha_cita)
    return "el vencido toma %s, el holgado %s" % (cb.fecha_cita, ca.fecha_cita)


@caso("11. Desempate por prioridad_operativa: pipa antes que reparto")
def c11():
    db = nueva_db()
    t, pipa, rep = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", criticidad=2, dias=1)
    lim = LUNES + timedelta(days=10)
    u1 = unidad(db, "C1", rep, t); p1 = programa(db, u1, srv, lim)   # id menor: FIFO
    u2 = unidad(db, "C2", pipa, t); p2 = programa(db, u2, srv, lim)
    ag.recalcular(db, t, hoy=LUNES)
    c_rep = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=p1.id).one()
    c_pip = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=p2.id).one()
    assert c_pip.fecha_cita < c_rep.fecha_cita, \
        "pipa (prio 1) debe ganar al reparto (prio 3): pipa=%s rep=%s" % (
            c_pip.fecha_cita, c_rep.fecha_cita)
    return "pipa %s antes que reparto %s pese al FIFO" % (c_pip.fecha_cita, c_rep.fecha_cita)


@caso("12. Anti-inanicion: la cita muy reprogramada sube en la cola")
def c12():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", criticidad=2, dias=1)
    lim = LUNES + timedelta(days=10)
    u1 = unidad(db, "K1", pipa, t); p1 = programa(db, u1, srv, lim)
    u2 = unidad(db, "K2", pipa, t); p2 = programa(db, u2, srv, lim)
    for p, veces in ((p1, 0), (p2, 4)):
        p.cita_actual = type("X", (), {"veces_reprogramada": veces})()
    k1 = ag.clave_prioridad(p1, LUNES)
    k2 = ag.clave_prioridad(p2, LUNES)
    assert k2 < k1, "la reprogramada 4 veces debe ir primero: k2=%s k1=%s" % (k2, k1)
    return "clave con 4 reprogramaciones %s < clave sin reprogramaciones %s" % (k2, k1)


@caso("13. score_prioridad no contradice el orden real de la tupla")
def c13():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    seg = servicio(db, "frenos", criticidad=1, dias=1)
    prev = servicio(db, "afinacion", criticidad=2, dias=1)
    u1 = unidad(db, "M1", pipa, t); p1 = programa(db, u1, seg, LUNES + timedelta(days=200))
    u2 = unidad(db, "M2", pipa, t); p2 = programa(db, u2, prev, LUNES - timedelta(days=900))
    k1, k2 = ag.clave_prioridad(p1, LUNES), ag.clave_prioridad(p2, LUNES)
    s1, s2 = ag.score_prioridad(k1), ag.score_prioridad(k2)
    assert (k1 < k2) == (s1 < s2), \
        ("el score contradice el orden real: tupla seguridad=%s preventivo=%s "
         "pero score seguridad=%s preventivo=%s" % (k1, k2, s1, s2))
    return "score coherente (%s vs %s)" % (s1, s2)


# ===================================================================== #
# Las dos fechas, y la promesa que se le hace al chofer
# ===================================================================== #
@caso("14. fecha_limite_origen NUNCA se mueve al reprogramar")
def c14():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", dias=1)
    u = unidad(db, "F1", pipa, t); p = programa(db, u, srv, LUNES + timedelta(days=5))
    ag.recalcular(db, t, hoy=LUNES)
    c = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=p.id).one()
    limite0, fecha0 = c.fecha_limite_origen, c.fecha_cita
    seg = servicio(db, "frenos", criticidad=1, dias=2)   # urgencia que ocupa la bahia
    u2 = unidad(db, "F2", pipa, t); programa(db, u2, seg, LUNES)
    ag.recalcular(db, t, hoy=LUNES)
    db.refresh(c)
    assert c.fecha_limite_origen == limite0, \
        "el limite tecnico se movio: %s -> %s" % (limite0, c.fecha_limite_origen)
    reps = db.query(m.Reprogramacion).filter_by(cita_id=c.id).all()
    if c.fecha_cita != fecha0:
        assert reps, "toda reprogramacion debe dejar rastro en REPROGRAMACION"
    return "limite intacto (%s); cita %s -> %s; %d registro(s) de reprogramacion" % (
        limite0, fecha0, c.fecha_cita, len(reps))


@caso("15. _movible: propuesta si; confirmada a +5 dias si; confirmada manana NO")
def c15():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    u = unidad(db, "G1", pipa, t)
    hoy = date.today()

    def mk(est, d):
        return m.CitaTaller(taller_id=t.id, unidad_id=u.id, estado=est,
                            fecha_cita=hoy + timedelta(days=d),
                            duracion_estimada_dias=1)

    assert ag._movible(mk("propuesta", 1)) is True, "una propuesta siempre se puede mover"
    assert ag._movible(mk("confirmada", 5)) is True, "confirmada lejana si se mueve"
    assert ag._movible(mk("confirmada", 1)) is False, "a <48h no se le mueve al chofer"
    assert ag._movible(mk("confirmada", 2)) is False, "48h exactas: tampoco"
    assert ag._movible(mk("cancelada", 9)) is False
    return "propuesta=movible, confirmada>48h=movible, confirmada<=48h=intocable"


@caso("16. Una cita confirmada a <48h no la mueve el recalculo")
def c16():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", dias=1)
    hoy = date.today()
    u = unidad(db, "H1", pipa, t); p = programa(db, u, srv, hoy + timedelta(days=10))
    c = m.CitaTaller(taller_id=t.id, unidad_id=u.id, programa_mantenimiento_id=p.id,
                     tipo_servicio_id=srv.id, fecha_cita=hoy + timedelta(days=1),
                     fecha_limite_origen=p.fecha_limite, duracion_estimada_dias=1,
                     estado="confirmada")
    db.add(c); db.flush()
    p.estado = "agendado"
    seg = servicio(db, "frenos", criticidad=1, dias=1)   # urgencia que querria la bahia
    u2 = unidad(db, "H2", pipa, t); programa(db, u2, seg, hoy)
    ag.recalcular(db, t, hoy=hoy)
    db.refresh(c)
    assert c.fecha_cita == hoy + timedelta(days=1), \
        "le movieron la cita al chofer: %s" % c.fecha_cita
    assert c.estado == "confirmada"
    return "la cita confirmada de manana quedo intacta"


# ===================================================================== #
# Estabilidad del recalculo: el job diario D5 no debe mover la agenda sola
# ===================================================================== #
@caso("17. La unica cita del taller no se estorba a si misma")
def c17():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", dias=1)
    u = unidad(db, "U1", pipa, t)
    pr = programa(db, u, srv, LUNES + timedelta(days=20))
    ag.recalcular(db, t, hoy=LUNES)
    c = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=pr.id).one()
    primera = c.fecha_cita
    ag.recalcular(db, t, hoy=LUNES)     # nada cambio: no deberia moverse
    db.refresh(c)
    assert c.fecha_cita == primera, \
        "la unica cita del taller se movio sola de %s a %s" % (primera, c.fecha_cita)
    assert (c.veces_reprogramada or 0) == 0, \
        "acumulo %d reprogramaciones sin que nada cambiara" % c.veces_reprogramada
    return "cita estable en %s tras recalcular de nuevo" % primera


@caso("18. Idempotencia: recalcular dos veces no mueve nada")
def c18():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=2)
    srv = servicio(db, "aceite", dias=1)
    for i in range(3):
        u = unidad(db, "L%d" % i, pipa, t)
        programa(db, u, srv, LUNES + timedelta(days=20))
    r1 = ag.recalcular(db, t, hoy=LUNES)
    antes = dict((c.id, c.fecha_cita) for c in citas(db))
    r2 = ag.recalcular(db, t, hoy=LUNES)
    despues = dict((c.id, c.fecha_cita) for c in citas(db))
    movidas = dict((k, (antes[k], despues[k])) for k in antes if antes[k] != despues[k])
    assert r2["movidas"] == 0 and not movidas, \
        "la 2a corrida movio citas sin que cambiara nada: %s; r1=%s r2=%s" % (
            movidas, r1, r2)
    return "2a corrida estable: %s" % r2


@caso("19. Cinco corridas del job diario sobre una agenda que no cambia")
def c19():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=2)
    srv = servicio(db, "aceite", dias=1)
    for i in range(3):
        u = unidad(db, "V%d" % i, pipa, t)
        programa(db, u, srv, LUNES + timedelta(days=25))
    traza = []
    for _ in range(5):
        ag.recalcular(db, t, hoy=LUNES)
        traza.append(sorted(c.fecha_cita.isoformat() for c in citas(db)))
    veces = [c.veces_reprogramada for c in citas(db)]
    reps = db.query(m.Reprogramacion).count()
    distintas = [i + 1 for i, x in enumerate(traza) if x != traza[0]]
    assert not distintas, \
        ("la agenda no se queda quieta aunque nada cambie (corridas %s difieren):\n"
         % distintas
         + "".join("        corrida %d: %s\n" % (i + 1, x) for i, x in enumerate(traza))
         + "        veces_reprogramada=%s, %d registros de reprogramacion"
         % (veces, reps))
    assert reps == 0, "%d reprogramaciones sin que entrara trabajo nuevo" % reps
    return "estable en las 5 corridas: %s" % traza[-1]


# ===================================================================== #
# Falta de cupo: es del taller, no del chofer
# ===================================================================== #
@caso("20. Sin cupo: mas demanda que horizonte -> estado 'sin_cupo'", pendiente=True)
def c20():
    # PENDIENTE: HORIZONTE_DIAS=30 se le pasa a dias_habiles(), que cuenta dias
    # HABILES, no naturales. Sin sabado el horizonte real llega a ~42 dias
    # naturales, asi que estas 30 unidades alcanzan lugar y no se declara ni un
    # sin_cupo. Ver el caso 21.
    db = nueva_db()
    t, pipa, _ = sembrar(db, opera_sabado=False, genericos=1)
    srv = servicio(db, "afinacion", dias=1)
    progs = []
    for i in range(30):
        u = unidad(db, "D%d" % i, pipa, t)
        progs.append(programa(db, u, srv, LUNES + timedelta(days=60)))
    r = ag.recalcular(db, t, hoy=LUNES)
    sin = [p for p in progs if p.estado == "sin_cupo"]
    assert r["sin_cupo"] > 0, "debia declarar sin cupo: %s" % r
    assert len(sin) == r["sin_cupo"]
    return "%s agendadas, %s declaradas sin cupo" % (r["propuestas"], r["sin_cupo"])


@caso("21. El horizonte deberia ser de 30 dias naturales, no habiles", pendiente=True)
def c21():
    # PENDIENTE: el doc dice "mas alla de 30 dias el sistema NO propone fecha".
    # El codigo entrega 30 dias HABILES = 5 a 6 semanas naturales.
    db = nueva_db()
    t, _, _ = sembrar(db, opera_sabado=False, genericos=1)
    dias = list(ag.dias_habiles(t, LUNES, ag.HORIZONTE_DIAS))
    span = (dias[-1] - dias[0]).days
    assert span <= ag.HORIZONTE_DIAS, \
        ("HORIZONTE_DIAS=%d pero el ultimo dia del horizonte es %s: %d dias naturales"
         % (ag.HORIZONTE_DIAS, dias[-1], span))
    return "horizonte de %d dias naturales" % span


@caso("22. detectar_sin_cupo: la cita DESPUES del limite tambien cuenta")
def c22():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", dias=1)
    u1 = unidad(db, "E1", pipa, t); programa(db, u1, srv, LUNES)
    u2 = unidad(db, "E2", pipa, t); programa(db, u2, srv, LUNES)   # 1 bahia, 2 unidades
    ag.recalcular(db, t, hoy=LUNES)
    fuera = ag.detectar_sin_cupo(db, t)
    ids = set(p.id for p, _ in fuera)
    tarde = [c for c in citas(db) if c.fecha_cita > c.fecha_limite_origen]
    assert tarde, "el segundo debio caer despues del limite"
    assert tarde[0].programa_mantenimiento_id in ids, \
        "una cita fuera de limite debe salir en detectar_sin_cupo, no como falta del chofer"
    return "%d programa(s) reportado(s) como falta de capacidad del taller" % len(fuera)


@caso("23. dias_sin_cupo protege el movimiento MANUAL de Victor")
def c23():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "transmision", dias=3)
    u1 = unidad(db, "O1", pipa, t)
    ocupante = m.CitaTaller(taller_id=t.id, unidad_id=u1.id, fecha_cita=LUNES,
                            duracion_estimada_dias=3, estado="confirmada",
                            tipo_servicio_id=srv.id)
    u2 = unidad(db, "O2", pipa, t)
    mover = m.CitaTaller(taller_id=t.id, unidad_id=u2.id,
                         fecha_cita=LUNES + timedelta(days=20),
                         duracion_estimada_dias=3, estado="propuesta",
                         tipo_servicio_id=srv.id)
    db.add_all([ocupante, mover]); db.flush()
    faltan = ag.dias_sin_cupo(db, mover, LUNES)
    assert len(faltan) == 3, "los 3 dias del tramo deben marcarse llenos, dio %s" % faltan
    libre = ag.dias_sin_cupo(db, mover, LUNES + timedelta(days=3))
    assert libre == [], "el jueves si cabe, pero dijo %s" % libre
    propia = ag.dias_sin_cupo(db, ocupante, LUNES)
    assert propia == [], "la cita se estorba a si misma en su propio dia: %s" % propia
    return "3 dias bloqueados, tramo libre aceptado, y no se estorba a si misma"


# ===================================================================== #
# Ruteo y dias en que se cita
# ===================================================================== #
@caso("24. taller_de: unidad sin taller asignado cae a la CENTRAL")
def c24():
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    u = unidad(db, "J1", pipa, None)
    assert u.taller_asignado_id is None
    assert ag.taller_de(db, u) == t.id, "debe caer a Alamos (CENTRAL)"
    srv = servicio(db, "aceite", dias=1)
    programa(db, u, srv, LUNES + timedelta(days=5))
    r = ag.recalcular(db, t, hoy=LUNES)
    assert r["propuestas"] == 1, "la unidad sin taller quedo invisible: %s" % r
    return "unidad sin taller asignado se agenda en la CENTRAL"


@caso("25. La agenda no propone dias en que el taller esta cerrado")
def c25():
    db = nueva_db()
    t, pipa, _ = sembrar(db, opera_sabado=False, genericos=1)
    srv = servicio(db, "aceite", dias=1)
    viernes = date(2026, 9, 11)
    for i in range(4):
        u = unidad(db, "N%d" % i, pipa, t)
        programa(db, u, srv, viernes + timedelta(days=20))
    ag.recalcular(db, t, hoy=viernes)
    fechas = sorted(c.fecha_cita for c in citas(db))
    malos = [f for f in fechas if f.weekday() >= 5]
    assert not malos, "cito en fin de semana con el taller cerrado: %s" % malos
    return "fechas %s (ningun sabado ni domingo)" % [f.isoformat() for f in fechas]


@caso("26. No se cita al chofer para HOY mismo", pendiente=True)
def c26():
    # PENDIENTE: es una decision de Victor, no un error de calculo. El horizonte
    # arranca en `hoy`, asi que un preventivo puede caer el mismo dia y el
    # chofer no alcanza a enterarse. Para una urgencia puede ser lo deseado.
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", dias=1)
    u = unidad(db, "Q1", pipa, t); p = programa(db, u, srv, LUNES + timedelta(days=5))
    ag.recalcular(db, t, hoy=LUNES)
    c = db.query(m.CitaTaller).filter_by(programa_mantenimiento_id=p.id).one()
    assert c.fecha_cita != LUNES, "cito para HOY mismo (%s)" % c.fecha_cita
    return "primera fecha propuesta: %s" % c.fecha_cita


@caso("27. Las 48h tambien valen para la fecha DESTINO", pendiente=True)
def c27():
    # PENDIENTE: `_movible` solo mira cuanto falta para la fecha ACTUAL. Una
    # cita confirmada para dentro de 10 dias se deja mover, pero nada impide
    # que aterrice HOY, o sea con cero horas de aviso. Falta un piso en la
    # fecha a la que se la manda.
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", dias=1)
    hoy = date.today()
    u = unidad(db, "W1", pipa, t); p = programa(db, u, srv, hoy + timedelta(days=25))
    c = m.CitaTaller(taller_id=t.id, unidad_id=u.id, programa_mantenimiento_id=p.id,
                     tipo_servicio_id=srv.id, fecha_cita=hoy + timedelta(days=10),
                     fecha_limite_origen=p.fecha_limite, duracion_estimada_dias=1,
                     estado="confirmada")
    db.add(c); db.flush()
    p.estado = "agendado"
    fecha0 = c.fecha_cita
    for _ in range(3):
        ag.recalcular(db, t, hoy=hoy)
    db.refresh(c)
    assert (c.fecha_cita - hoy).days * 24 > ag.HORAS_INTOCABLE, \
        ("la cita CONFIRMADA se movio de %s a %s: %d dias de aviso, menos que las "
         "%dh que el diseno le promete al chofer"
         % (fecha0, c.fecha_cita, (c.fecha_cita - hoy).days, ag.HORAS_INTOCABLE))
    return "cita confirmada con aviso suficiente (%s)" % c.fecha_cita


# ===================================================================== #
# El aviso de incumplimiento cuelga de la cita, no del programa
# ===================================================================== #
def _chofer(db, usuario_id=1):
    """Un chofer minimo, poseedor de la unidad que se le pase despues."""
    u = m.Usuario(id=usuario_id, nombre="Chofer", apellidos="De Prueba",
                  email="chofer%d@prueba.mx" % usuario_id, password_hash="x")
    db.add(u); db.flush()
    ch = m.Chofer(usuario_id=u.id)
    db.add(ch); db.flush()
    return ch


def _cita_perdida(db, t, pipa, dias_atras=5, estado="confirmada"):
    """Una cita cuya fecha ya paso, con su programa y su chofer poseedor."""
    ch = _chofer(db)
    srv = servicio(db, "aceite", dias=1)
    hoy = date.today()
    u = unidad(db, "X1", pipa, t)
    u.poseedor_chofer_id = ch.usuario_id
    u.titular_chofer_id = ch.usuario_id
    db.flush()
    p = programa(db, u, srv, hoy - timedelta(days=dias_atras + 2))
    p.estado = "agendado"
    c = m.CitaTaller(taller_id=t.id, unidad_id=u.id, programa_mantenimiento_id=p.id,
                     tipo_servicio_id=srv.id, fecha_cita=hoy - timedelta(days=dias_atras),
                     fecha_limite_origen=p.fecha_limite, duracion_estimada_dias=1,
                     estado=estado)
    db.add(c); db.flush()
    return u, p, c


@caso("28. Faltar a una cita confirmada SI genera aviso, y marca no_asistio")
def c28():
    from app import jobs
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    u, p, c = _cita_perdida(db, t, pipa)
    creados = jobs.generar_avisos_incumplimiento(db)
    db.refresh(c)
    assert creados == 1, "esperaba 1 aviso, dio %d" % creados
    av = db.query(m.AvisoIncumplimiento).one()
    assert av.cita_id == c.id, "el aviso debe colgar de la cita, no del programa"
    assert av.unidad_id == u.id and av.chofer_id is not None
    assert c.estado == "no_asistio", "la cita quedo en '%s'" % c.estado
    return "aviso ligado a la cita %d, chofer %s, cita marcada no_asistio" % (
        av.cita_id, av.chofer_id)


@caso("29. Si la unidad SI llego al taller, no hay aviso")
def c29():
    from app import jobs
    from datetime import datetime as dt
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    u, p, c = _cita_perdida(db, t, pipa)
    db.add(m.OrdenServicio(folio="OS-9", unidad_id=u.id, taller_id=t.id,
                           fecha_entrada=dt.combine(c.fecha_cita, dt.min.time()),
                           estado="abierta"))
    db.flush()
    creados = jobs.generar_avisos_incumplimiento(db)
    assert creados == 0, "se presento y aun asi genero %d aviso(s)" % creados
    assert db.query(m.AvisoIncumplimiento).count() == 0
    return "orden de servicio abierta ese dia = se presento, sin aviso"


@caso("30. Falta de CUPO no genera aviso al chofer (era el defecto viejo)")
def c30():
    from app import jobs
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    ch = _chofer(db)
    srv = servicio(db, "aceite", dias=1)
    hoy = date.today()
    u = unidad(db, "Y1", pipa, t)
    u.poseedor_chofer_id = ch.usuario_id
    db.flush()
    # Programa vencido que NUNCA alcanzo cita: es culpa del taller.
    p = programa(db, u, srv, hoy - timedelta(days=10))
    p.estado = "sin_cupo"
    creados = jobs.generar_avisos_incumplimiento(db)
    assert creados == 0, \
        "genero %d aviso(s) por falta de cupo: eso es del taller, no del chofer" % creados
    return "sin_cupo no culpa al chofer; eso sale por /api/agenda/sin-cupo"


@caso("31. Cita cancelada por el taller no genera aviso")
def c31():
    from app import jobs
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    u, p, c = _cita_perdida(db, t, pipa, estado="cancelada")
    p.estado = "pendiente"      # es lo que hace el endpoint /cancelar
    creados = jobs.generar_avisos_incumplimiento(db)
    assert creados == 0, \
        "cancelar una cita le genero %d aviso(s) al chofer" % creados
    return "cancelar no culpa al chofer"


@caso("32. Un mismo faltante no genera dos avisos")
def c32():
    from app import jobs
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    _cita_perdida(db, t, pipa)
    n1 = jobs.generar_avisos_incumplimiento(db)
    n2 = jobs.generar_avisos_incumplimiento(db)
    total = db.query(m.AvisoIncumplimiento).count()
    assert (n1, n2, total) == (1, 0, 1), "n1=%s n2=%s total=%s" % (n1, n2, total)
    return "2 corridas del job, 1 solo aviso"


@caso("33. Entrar la TARDE ANTERIOR no cuenta como haberse presentado")
def c33b():
    from app import jobs
    from datetime import datetime as dt
    from app.core.tiempo import TZ_OPERACION
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    u, p, c = _cita_perdida(db, t, pipa)
    # 18:00 hora Tijuana del dia ANTERIOR a la cita. En UTC eso cae al dia
    # siguiente, asi que un corte hecho en UTC lo daria por presentado.
    vispera = dt.combine(c.fecha_cita - timedelta(days=1), dt.min.time()) \
        .replace(hour=18, tzinfo=TZ_OPERACION)
    db.add(m.OrdenServicio(folio="OS-8", unidad_id=u.id, taller_id=t.id,
                           fecha_entrada=vispera, estado="abierta"))
    db.flush()
    creados = jobs.generar_avisos_incumplimiento(db)
    assert creados == 1, \
        ("una entrada de la vispera (18:00 Tijuana = %s UTC) se conto como "
         "asistencia: el corte se esta haciendo en UTC y no en hora del taller"
         % vispera.astimezone(__import__("datetime").timezone.utc).date())
    return "el corte respeta el calendario del taller, no el UTC"


@caso("34. Un programa vencido sigue recibiendo cita")
def c33():
    from app import jobs
    db = nueva_db()
    t, pipa, _ = sembrar(db, genericos=1)
    srv = servicio(db, "aceite", dias=1)
    hoy = date.today()
    u = unidad(db, "Z1", pipa, t)
    p = programa(db, u, srv, hoy - timedelta(days=10))   # ya vencido
    jobs.generar_avisos_incumplimiento(db)              # lo marca 'vencido'
    db.refresh(p)
    assert p.estado == "vencido", "esperaba 'vencido', quedo '%s'" % p.estado
    r = ag.recalcular(db, t, hoy=hoy)
    assert r["propuestas"] == 1, \
        ("un mantenimiento vencido dejo de agendarse: %s. Vencerse no lo cancela, "
         "al contrario: es el que mas urge" % r)
    return "el programa vencido vuelve a la cola y recibe cita"


# ===================================================================== #
def main():
    ok = fallo = pend = 0
    print("=" * 78)
    for nombre, fn, pendiente in CASOS:
        try:
            detalle = fn()
            if pendiente:
                print("[ OK ]  %s\n        -> %s\n        (marcado PENDIENTE: ya se "
                      "puede quitar la marca)" % (nombre, detalle))
            else:
                print("[ OK ]  %s\n        -> %s" % (nombre, detalle))
            ok += 1
        except AssertionError as e:
            if pendiente:
                pend += 1
                print("[PEND]  %s\n        -> %s" % (nombre, e))
            else:
                fallo += 1
                print("[FALLA] %s\n        -> %s" % (nombre, e))
        except Exception:
            fallo += 1
            print("[ERROR] %s" % nombre)
            print("        " + traceback.format_exc().replace("\n", "\n        "))
    print("=" * 78)
    print("%d pasaron, %d fallaron, %d pendientes conocidos, de %d casos"
          % (ok, fallo, pend, len(CASOS)))
    return 1 if fallo else 0


if __name__ == "__main__":
    sys.exit(main())
