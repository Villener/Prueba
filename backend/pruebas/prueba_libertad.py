"""Pruebas del taller de Libertad y de atender una unidad en otra planta (2026-10-08).

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_libertad.py     (Windows)

Libertad nacio como sucursal SIN taller y sus unidades iban a Alamos. Martin
aviso que si tiene taller, y la regla de Baja Gas: una unidad es de su planta
madre aunque a veces la atienda otra planta que tenga lugar en ese momento.

- Una base que ya existia le da su taller a Libertad al arrancar (T-01, T-02).
- La carga diaria deja sus unidades en Libertad, y correrla otra vez no cambia nada.
- La agenda: la propuesta que tenia en Alamos pasa a Libertad; la confirmada se respeta.
- El administrador acepta una solicitud en otra planta con lugar; la unidad
  sigue siendo de la suya. El mecanico no puede.
- La requisicion cuenta en el taller del mecanico que pidio las piezas.
"""
import os
import sys
import traceback
from datetime import date, timedelta

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import HTTPException                           # noqa: E402
from sqlalchemy import create_engine                        # noqa: E402
from sqlalchemy.orm import sessionmaker                     # noqa: E402

from app import models as m                                 # noqa: E402
from app import seed                                        # noqa: E402
from app.core.database import Base                          # noqa: E402
from app.core.tiempo import ahora_utc                       # noqa: E402
from app.importadores import padron                         # noqa: E402
from app.modules.mantenimiento import agenda_service as ag  # noqa: E402
from app.modules.piezas import capturista_controller as cc  # noqa: E402
from app.modules.taller import administrador_controller as ac  # noqa: E402
from app.schemas import (RenglonRequisicionIn, RequisicionIn,  # noqa: E402
                         ResolucionSolicitudIn)

CASOS = []


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


def nueva_db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, autoflush=False)()


def base_como_produccion(db):
    """Las 7 plantas como estaban en produccion: Libertad SIN taller y las
    otras seis con el suyo y su zona."""
    for clave, nombre, central, _con, lat, lng in seed.PLANTAS:
        pl = m.Planta(clave=clave, nombre=nombre, es_central=central,
                      tiene_taller=clave != "LIBERTAD", latitud=lat, longitud=lng)
        db.add(pl)
        db.flush()
        if clave == "LIBERTAD":
            continue
        t = m.Taller(planta_id=pl.id, nombre=nombre,
                     tipo="CENTRAL" if central else "SATELITE")
        db.add(t)
        db.flush()
        z = m.ZonaTaller(taller_id=t.id, nombre="TALLER", cuenta_para_ocupacion=True)
        db.add(z)
        db.flush()
        db.add(m.Espacio(zona_id=z.id, numero="T-01"))
    db.commit()


def taller(db, nombre):
    return db.query(m.Taller).filter(m.Taller.nombre == nombre).one()


def auditoria(db, accion):
    return db.query(m.BitacoraAuditoria).filter(m.BitacoraAuditoria.accion == accion).all()


# ------------------------------------------------------- el taller nace ---- #
@caso("una base con Libertad sin taller: al arrancar le nace el suyo con T-01 y T-02")
def _():
    db = nueva_db()
    base_como_produccion(db)
    r = seed.asegurar_plantas(db)
    assert r["con_taller_nuevo"] == ["LIBERTAD"] and r["talleres"] == 1, r
    lib = taller(db, "Libertad")
    assert lib.tipo == "SATELITE" and lib.activo and lib.planta.clave == "LIBERTAD"
    assert lib.planta.tiene_taller is True
    zonas = db.query(m.ZonaTaller).filter_by(taller_id=lib.id).all()
    assert [(z.nombre, z.capacidad, bool(z.cuenta_para_ocupacion), bool(z.admite_unidades))
            for z in zonas] == [("TALLER", 2, True, True)], zonas
    assert sorted((e.numero, e.estado) for e in zonas[0].espacios) == \
        [("T-01", "libre"), ("T-02", "libre")]
    assert len(auditoria(db, "planta_con_taller")) == 1
    assert len(auditoria(db, "taller_creado")) == 1
    # Las otras seis no se tocan.
    assert db.query(m.Taller).count() == 7
    assert db.query(m.Espacio).count() == 6 + 2

    # Idempotente: la segunda vez no crea nada ni vuelve a auditar.
    r2 = seed.asegurar_plantas(db)
    assert r2["talleres"] == 0 and r2["espacios"] == 0 and not r2["con_taller_nuevo"], r2
    assert db.query(m.Espacio).count() == 8
    assert len(auditoria(db, "planta_con_taller")) == 1
    assert len(auditoria(db, "taller_creado")) == 1


@caso("un taller suelto llamado Libertad se adopta en vez de tumbar el arranque")
def _():
    db = nueva_db()
    base_como_produccion(db)
    db.add(m.Taller(nombre="Libertad"))       # alguien lo dio de alta a mano, sin planta
    db.commit()
    r = seed.asegurar_plantas(db)
    assert not r["no_se_pudo"], r
    lib = taller(db, "Libertad")
    assert lib.planta.clave == "LIBERTAD" and lib.tipo == "SATELITE"
    assert db.query(m.Taller).count() == 7
    assert len(db.query(m.ZonaTaller).filter_by(taller_id=lib.id).one().espacios) == 2


@caso("una base nueva siembra las 7 plantas con su taller, Libertad con 2 casillas")
def _():
    assert ("LIBERTAD", "Libertad", False, True) == seed.PLANTAS[-1][:4]
    assert seed.ESPACIOS_SATELITE["LIBERTAD"] == 2
    assert not hasattr(seed, "TALLER_POR_DEFECTO")
    from app import importador
    assert not hasattr(importador, "TALLER_SUSTITUTO")


# ------------------------------------------------- la carga de las areas -- #
@caso("el padron deja las unidades de Libertad en Libertad, y otra carga no cambia nada")
def _():
    # Desde el 2026-10-09 la planta de cada unidad sale del padron (el control
    # de GPS, ver prueba_padron.py); antes, de UNIDADES BAJA GAS.
    db = nueva_db()
    base_como_produccion(db)
    seed.asegurar_plantas(db)
    alamos, lib = taller(db, "Alamos"), taller(db, "Libertad")
    tipo = m.TipoUnidad(nombre="reparto")
    db.add(tipo)
    db.flush()
    # Como estaban en produccion: las de Libertad, asignadas a Alamos.
    for num in ("2154", "BG384", "1001"):
        db.add(m.Unidad(num_economico=num, tipo_unidad_id=tipo.id,
                        taller_asignado_id=alamos.id, activo=True))
    db.commit()
    def fila(num, planta):
        return {"clave": num, "texto": num, "canal": "REPARTO", "planta": planta,
                "supervisor": None, "placa": "", "vin": "", "modelo": "", "hojas": [],
                "permiso": "LP/14586/DIST/PLA/2016"}
    p = {"unidades": {"2154": fila("2154", "LIBERTAD"), "BG384": fila("BG384", "LIBERTAD"),
                      "1001": fila("1001", "ALAMOS")}, "avisos": []}

    def asignado():
        return {u.num_economico: u.taller_asignado_id for u in db.query(m.Unidad)}

    original = padron.MINIMO_DE_UNIDADES
    padron.MINIMO_DE_UNIDADES = 1
    try:
        r = padron.aplicar(db, p)
        assert asignado() == {"2154": lib.id, "BG384": lib.id, "1001": alamos.id}, asignado()
        assert r["planta_cambiada"] == 2, r
        r = padron.aplicar(db, p)                      # otra noche igual: nada
        assert r["planta_cambiada"] == 0 and asignado()["2154"] == lib.id, r
    finally:
        padron.MINIMO_DE_UNIDADES = original


# --------------------------------------------------------------- agenda ---- #
def agenda_dos_plantas(estado_cita, dias_cita):
    db = nueva_db()
    talleres = {}
    for nombre, tipo_t in (("Alamos", "CENTRAL"), ("Libertad", "SATELITE")):
        t = m.Taller(nombre=nombre, tipo=tipo_t, activo=True, opera_sabado=True)
        db.add(t)
        db.flush()
        z = m.ZonaTaller(taller_id=t.id, nombre="TALLER", cuenta_para_ocupacion=True)
        db.add(z)
        db.flush()
        for i in (1, 2):
            db.add(m.Espacio(zona_id=z.id, numero="T-%02d" % i, activo=True))
        talleres[nombre] = t
    tipo = m.TipoUnidad(nombre="REPARTO", prioridad_operativa=3)
    srv = m.TipoServicio(nombre="Preventivo", criticidad=2, duracion_estimada_dias=1,
                         ocupa_espacio=True)
    db.add_all([tipo, srv])
    db.flush()
    u = m.Unidad(num_economico="1191", tipo_unidad_id=tipo.id, activo=True,
                 taller_asignado_id=talleres["Libertad"].id)
    plan = m.PlanMantenimiento(nombre="plan", tipo_servicio_id=srv.id, activo=True)
    db.add_all([u, plan])
    db.flush()
    hoy = ahora_utc().date()
    prog = m.ProgramaMantenimiento(unidad_id=u.id, plan_id=plan.id,
                                   fecha_limite=hoy + timedelta(days=5), estado="agendado")
    db.add(prog)
    db.flush()
    cita = m.CitaTaller(taller_id=talleres["Alamos"].id, unidad_id=u.id,
                        programa_mantenimiento_id=prog.id, tipo_servicio_id=srv.id,
                        fecha_cita=hoy + timedelta(days=dias_cita),
                        fecha_limite_origen=prog.fecha_limite, duracion_estimada_dias=1,
                        estado=estado_cita, origen_agenda="automatica")
    db.add(cita)
    db.commit()
    return db, talleres, cita, hoy


@caso("agenda: la propuesta que tenia en Alamos pasa a Libertad y deja de contar alla")
def _():
    db, t, cita, hoy = agenda_dos_plantas("propuesta", 3)
    assert ag._citas_por_dia(db, t["Alamos"], hoy, set())          # contaba en Alamos
    r = ag.recalcular(db, t["Libertad"], hoy)
    db.refresh(cita)
    assert cita.taller_id == t["Libertad"].id, r
    assert r.get("cambio_de_planta") == 1 and r["propuestas"] == 0, r
    assert db.query(m.CitaTaller).count() == 1                       # la misma, no otra
    assert not ag._citas_por_dia(db, t["Alamos"], hoy, set())
    assert ag._citas_por_dia(db, t["Libertad"], hoy, set())
    # Y la siguiente corrida ya no la mueve de planta.
    r = ag.recalcular(db, t["Libertad"], hoy)
    assert not r.get("cambio_de_planta"), r


@caso("agenda: la confirmada en otra planta se respeta alla, sin moverla ni duplicarla")
def _():
    db, t, cita, hoy = agenda_dos_plantas("confirmada", 10)   # > 48 h: seria movible
    antes = cita.fecha_cita
    for nombre in ("Libertad", "Alamos"):
        ag.recalcular(db, t[nombre], hoy)
    db.refresh(cita)
    assert (cita.taller_id, cita.fecha_cita, cita.estado) == \
        (t["Alamos"].id, antes, "confirmada")
    assert db.query(m.CitaTaller).count() == 1
    assert ag._citas_por_dia(db, t["Alamos"], hoy, set())            # sigue ocupando alla


# ----------------------------------------- atender en otra planta ---------- #
def solicitudes_libertad(libertad_llena=True):
    db = nueva_db()
    roles = {n: m.Rol(nombre=n) for n in ("administrador", "mecanico", "chofer")}
    db.add_all(roles.values())
    db.flush()

    def persona(nombre, correo, rol):
        u = m.Usuario(nombre=nombre, apellidos="X", email=correo, password_hash="x")
        db.add(u)
        db.flush()
        db.add(m.UsuarioRol(usuario_id=u.id, rol_id=roles[rol].id))
        return u

    talleres, espacios = {}, {}
    for nombre in ("Alamos", "Libertad", "Tecate"):
        t = m.Taller(nombre=nombre, activo=nombre != "Tecate")
        db.add(t)
        db.flush()
        z = m.ZonaTaller(taller_id=t.id, nombre="TALLER", cuenta_para_ocupacion=True)
        db.add(z)
        db.flush()
        e = m.Espacio(zona_id=z.id, numero="T-01", estado="libre")
        db.add(e)
        talleres[nombre], espacios[nombre] = t, e
    if libertad_llena:
        espacios["Libertad"].estado = "ocupado"
    admin = persona("Victor", "e647@bajagas.mx", "administrador")
    mec_lib = persona("Mecanico", "e9001@bajagas.mx", "mecanico")
    mec_al = persona("Erick", "e9002@bajagas.mx", "mecanico")
    db.add_all([
        m.Tecnico(nombre="Mecanico", apellidos="Libertad", num_empleado="9001",
                  especialidad="mecanico", taller_id=talleres["Libertad"].id,
                  usuario_id=mec_lib.id),
        m.Tecnico(nombre="Erick", apellidos="Alamos", num_empleado="9002",
                  especialidad="mecanico", taller_id=talleres["Alamos"].id,
                  usuario_id=mec_al.id)])
    chofer = persona("Chofer", "e1@bajagas.mx", "chofer")
    db.add(m.Chofer(usuario_id=chofer.id))
    tipo = m.TipoUnidad(nombre="Reparto")
    db.add(tipo)
    db.flush()
    u = m.Unidad(num_economico="1191", tipo_unidad_id=tipo.id,
                 taller_asignado_id=talleres["Libertad"].id)
    db.add(u)
    db.flush()
    s = m.SolicitudIngreso(unidad_id=u.id, chofer_id=chofer.id, tipo="correctivo",
                           taller_id=talleres["Libertad"].id, descripcion_falla="frenos")
    db.add(s)
    db.commit()
    return db, {"admin": admin, "mec_lib": mec_lib, "mec_al": mec_al, "chofer": chofer,
                "talleres": talleres, "espacios": espacios, "unidad": u, "sol": s}


@caso("la bandeja dice de que planta es la unidad y donde hay lugar")
def _():
    db, x = solicitudes_libertad()
    [s] = ac.bandeja(usuario=x["admin"], db=db)
    assert s["taller"] == "Libertad" and s["planta_madre"] == "Libertad"
    assert s["espacios_libres_compatibles"] == 0
    # Tecate esta inactivo: no se ofrece.
    assert s["otras_plantas"] == [{"taller_id": x["talleres"]["Alamos"].id,
                                   "nombre": "Alamos", "libres": 1}], s["otras_plantas"]
    # El mecanico de Libertad ve su solicitud, pero no el lugar de las demas plantas.
    [s] = ac.bandeja(usuario=x["mec_lib"], db=db)
    assert s["otras_plantas"] == []
    # Ni el chofer: mandarla a otra planta lo decide el administrador.
    from app.modules.flota import chofer_controller
    [s] = chofer_controller.mis_solicitudes(usuario=x["chofer"], db=db)
    assert s["otras_plantas"] == [] and s["espacios_libres_compatibles"] == 0, s


@caso("el administrador la acepta en Alamos; la unidad sigue siendo de Libertad")
def _():
    db, x = solicitudes_libertad()
    lib, alamos = x["talleres"]["Libertad"], x["talleres"]["Alamos"]
    r = ac.resolver_solicitud(x["sol"].id,
                              ResolucionSolicitudIn(aceptar=True, taller_id=alamos.id),
                              usuario=x["admin"], db=db)
    assert r["estado"] == "aceptada" and r["taller"] == "Alamos", r
    assert r["planta_madre"] == "Libertad"
    orden = db.query(m.OrdenServicio).one()
    assert orden.taller_id == alamos.id
    ocup = db.query(m.OcupacionEspacio).one()
    assert ocup.espacio_id == x["espacios"]["Alamos"].id
    u = db.get(m.Unidad, x["unidad"].id)
    assert u.taller_asignado_id == lib.id and u.taller_actual_id == alamos.id
    reporte = db.query(m.ReporteMantenimiento).one()
    assert (reporte.taller_id, reporte.origen) == (alamos.id, "Libertad")
    [a] = auditoria(db, "solicitud_otra_planta")
    assert (a.datos_antes, a.datos_despues) == ("Libertad", "Alamos")
    aviso = (db.query(m.Notificacion).filter_by(usuario_id=x["chofer"].id)
             .filter(m.Notificacion.titulo == "Solicitud aceptada").one())
    assert "se atiende en Alamos (pediste Libertad)" in aviso.mensaje, aviso.mensaje
    # Al mecanico de Alamos le llega que va para alla; al de Libertad, nada.
    assert db.query(m.Notificacion).filter_by(usuario_id=x["mec_al"].id,
                                              titulo="Unidad de otra planta").count() == 1
    assert db.query(m.Notificacion).filter_by(usuario_id=x["mec_lib"].id).count() == 0


@caso("sin pedir otra planta, todo queda igual que antes")
def _():
    db, x = solicitudes_libertad(libertad_llena=False)
    r = ac.resolver_solicitud(x["sol"].id, ResolucionSolicitudIn(aceptar=True),
                              usuario=x["admin"], db=db)
    assert r["taller"] == "Libertad"
    assert db.query(m.OrdenServicio).one().taller_id == x["talleres"]["Libertad"].id
    assert not auditoria(db, "solicitud_otra_planta")
    aviso = db.query(m.Notificacion).filter_by(usuario_id=x["chofer"].id).one()
    assert aviso.mensaje.startswith("Unidad 1191 en Libertad, TALLER T-01"), aviso.mensaje


@caso("el mecanico no la manda a otra planta; un taller inactivo tampoco se acepta")
def _():
    db, x = solicitudes_libertad()
    alamos, tecate = x["talleres"]["Alamos"], x["talleres"]["Tecate"]
    try:
        ac.resolver_solicitud(x["sol"].id, ResolucionSolicitudIn(aceptar=True, taller_id=alamos.id),
                              usuario=x["mec_lib"], db=db)
    except HTTPException as e:
        assert e.status_code == 403, e.status_code
    else:
        raise AssertionError("el mecanico la mando a otra planta")
    db.rollback()
    for destino, codigo in ((tecate.id, 404), (99999, 404)):
        try:
            ac.resolver_solicitud(x["sol"].id,
                                  ResolucionSolicitudIn(aceptar=True, taller_id=destino),
                                  usuario=x["admin"], db=db)
        except HTTPException as e:
            assert e.status_code == codigo, (destino, e.status_code)
        else:
            raise AssertionError("acepto un taller inactivo o inexistente")
        db.rollback()
    s = db.get(m.SolicitudIngreso, x["sol"].id)
    assert s.estado == "pendiente" and s.taller_id == x["talleres"]["Libertad"].id
    assert db.query(m.OrdenServicio).count() == 0


@caso("si la otra planta tampoco tiene lugar, no se acepta (RN-06)")
def _():
    db, x = solicitudes_libertad()
    x["espacios"]["Alamos"].estado = "ocupado"
    db.commit()
    try:
        ac.resolver_solicitud(x["sol"].id,
                              ResolucionSolicitudIn(aceptar=True,
                                                    taller_id=x["talleres"]["Alamos"].id),
                              usuario=x["admin"], db=db)
    except HTTPException as e:
        assert e.status_code == 409, e.status_code
    else:
        raise AssertionError("acepto sin lugar")


# ---------------------------------------------------------- requisicion ---- #
@caso("la requisicion cuenta en el taller del mecanico que pidio, no en la planta madre")
def _():
    db, x = solicitudes_libertad()
    cap = m.Usuario(nombre="Cap", apellidos="X", email="e2@bajagas.mx", password_hash="x")
    db.add(cap)
    db.commit()
    erick = db.query(m.Tecnico).filter_by(num_empleado="9002").one()

    def capturar(folio, tecnico_id):
        return cc.capturar(RequisicionIn(
            folio=folio, fecha=date(2026, 10, 8), unidad_id=x["unidad"].id,
            tecnico_id=tecnico_id,
            renglones=[RenglonRequisicionIn(descripcion="Balatas", cantidad=1)]),
            usuario=cap, db=db)

    capturar("R-1", erick.id)
    capturar("R-2", None)
    t = {r.folio: r.taller_id for r in db.query(m.Requisicion)}
    assert t == {"R-1": x["talleres"]["Alamos"].id,       # la reparo Alamos
                 "R-2": x["talleres"]["Libertad"].id}, t   # sin mecanico: su planta


if __name__ == "__main__":
    fallas = 0
    for nombre, fn in CASOS:
        try:
            fn()
            print(f"  ok    {nombre}")
        except Exception:
            fallas += 1
            print(f"  FALLA {nombre}")
            traceback.print_exc()
    print(f"\n{len(CASOS) - fallas} de {len(CASOS)} pasaron")
    sys.exit(1 if fallas else 0)
