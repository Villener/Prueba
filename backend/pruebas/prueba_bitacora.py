# -*- coding: utf-8 -*-
"""Pruebas del libro de bitacora de mantenimiento (PROY-NOM-030-ASEA-2026, 7.1.10).

Verifica app/modules/bitacora/ y los caminos del reporte de mantenimiento que
escriben en el libro. Cada caso arma su propia base SQLite en memoria CON los
candados de la base (asegurar_candados_bitacora), porque `create_all` no crea
disparadores y sin ellos la prueba no se pareceria a produccion.

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_bitacora.py     (Windows)
    .venv/bin/python pruebas/prueba_bitacora.py             (Linux / Docker)

Los endpoints se llaman como funciones, con la sesion y el usuario a mano: no
hay TestClient porque httpx no es dependencia del proyecto. Lo que eso NO
prueba (el paso de parametros por HTTP) se prueba aparte contra el servidor.
"""
import os
import sys
import traceback
from datetime import date, timedelta

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["DATABASE_URL"] = "sqlite://"
# Las fotos de prueba van a una carpeta temporal, nunca a /datos/evidencias.
import tempfile                                             # noqa: E402
EVIDENCIAS = tempfile.mkdtemp(prefix="evid-prueba-")
os.environ["EVIDENCIAS_DIR"] = EVIDENCIAS

from fastapi import HTTPException                           # noqa: E402
from sqlalchemy import create_engine, text                  # noqa: E402
from sqlalchemy.exc import IntegrityError                   # noqa: E402
from sqlalchemy.orm import sessionmaker                     # noqa: E402

from app import models as m                                 # noqa: E402
from app import schemas as sc                               # noqa: E402
from app import services as svc                             # noqa: E402
from app.core.database import Base                          # noqa: E402
from app.core.migraciones import asegurar_candados_bitacora  # noqa: E402
from app.core.tiempo import ahora_utc, dia_operativo        # noqa: E402
from app.importadores import limpieza                       # noqa: E402
from app.modules.bitacora import bitacora_controller as bc  # noqa: E402
from app.modules.bitacora import bitacora_service as bs     # noqa: E402
from app.modules.emergencias import mecanico_controller as mc  # noqa: E402
from app.modules.taller import administrador_controller as ac  # noqa: E402
from app.seed import asegurar_asientos_de_reportes, asegurar_parametros  # noqa: E402

CASOS = []


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


# --------------------------------------------------------------------- #
def nueva_db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    asegurar_candados_bitacora(eng)
    db = sessionmaker(bind=eng, autocommit=False, autoflush=False)()
    asegurar_parametros(db)
    return db


class Mundo:
    """Un taller, una pipa, un administrador, un chofer titular, un tecnico."""

    def __init__(self, db):
        self.db = db
        self.taller = m.Taller(nombre="Alamos", tipo="CENTRAL")
        self.pipa = m.TipoUnidad(nombre="pipa", prioridad_operativa=1)
        self.util = m.TipoUnidad(nombre="utilitario", prioridad_operativa=5)
        db.add_all([self.taller, self.pipa, self.util]); db.flush()

        self.admin = self._usuario("Pedro", "Admin", "admin@x.mx", "administrador")
        self.chofer_u = self._usuario("Juan", "Chofer", "juan@x.mx", "chofer")
        self.otro_chofer = self._usuario("Luis", "Otro", "luis@x.mx", "chofer")
        db.add_all([m.Chofer(usuario_id=self.chofer_u.id),
                    m.Chofer(usuario_id=self.otro_chofer.id)]); db.flush()
        self.mec_u = self._usuario("Mario", "Mecanico", "mario@x.mx", "mecanico")
        self.tecnico = m.Tecnico(nombre="Ramon", apellidos="Lopez", especialidad="mecanico",
                                 taller_id=self.taller.id)
        self.tec_mec = m.Tecnico(nombre="Mario", apellidos="Mecanico", especialidad="mecanico",
                                 taller_id=self.taller.id, modalidad="AUTONOMO",
                                 usuario_id=self.mec_u.id)
        db.add_all([self.tecnico, self.tec_mec]); db.flush()

        self.unidad = m.Unidad(num_economico="BG-900P", tipo_unidad_id=self.pipa.id,
                               titular_chofer_id=self.chofer_u.id, marca="International")
        db.add(self.unidad); db.flush()
        db.commit()

    def _usuario(self, nombre, apellidos, email, rol):
        r = self.db.query(m.Rol).filter_by(nombre=rol).first()
        if not r:
            r = m.Rol(nombre=rol); self.db.add(r); self.db.flush()
        u = m.Usuario(nombre=nombre, apellidos=apellidos, email=email, password_hash="x")
        self.db.add(u); self.db.flush()
        self.db.add(m.UsuarioRol(usuario_id=u.id, rol_id=r.id)); self.db.flush()
        return u

    def reporte(self, tipo="correctivo", unidad=None, orden=None):
        # Entra hace tres dias: asi "ayer" es una fecha de trabajo valida.
        r = svc.crear_reporte_mantenimiento(
            self.db, unidad=unidad or self.unidad, taller_id=self.taller.id,
            admin_id=self.admin.id, tipo_servicio=tipo, orden=orden,
            fecha_entrada=ahora_utc() - timedelta(days=3))
        self.db.commit()
        return r


def fila(sistema, **k):
    return sc.ActividadReporteIn(sistema=sistema, **k)


def completa(sistema, tecnico_id, **extra):
    """Un renglon realizado con todo lo que pide la NOM-030."""
    hoy = dia_operativo(ahora_utc())
    base = dict(a_realizar="Cambiar balatas", realizada="Balatas cambiadas",
                tecnico_id=tecnico_id, resultado="conforme", acciones_requeridas="Ninguna",
                fecha_inicio=hoy - timedelta(days=1), fecha_termino=hoy)
    base.update(extra)
    return fila(sistema, **base)


def libro(db, unidad_id):
    return bs.asientos_de_unidad(db, unidad_id)


def espera_http(fn, status):
    try:
        fn()
    except HTTPException as e:
        assert e.status_code == status, f"esperaba {status}, llego {e.status_code}: {e.detail}"
        return e
    raise AssertionError(f"esperaba HTTP {status} y no hubo error")


# ===================================================================== #
@caso("1. Abrir un formato abre su asiento, con usuario y hora del servidor")
def c1():
    db = nueva_db(); w = Mundo(db)
    antes = ahora_utc()
    r = w.reporte()
    ls = libro(db, w.unidad.id)
    assert len(ls) == 1 and ls[0].tipo == "apertura", [a.tipo for a in ls]
    a = ls[0]
    assert a.numero == 1 and a.hash_anterior == bs.GENESIS
    assert a.registrado_por_nombre == "Pedro Admin", a.registrado_por_nombre
    assert a.registrado_en >= antes, "la hora debe ser la del servidor al registrar"
    assert a.num_economico == "BG-900P" and a.reporte_id == r.id
    assert bs.verificar(ls)["integra"]
    return "asiento 1 de BG-900P, registrado por Pedro Admin, cadena integra"


@caso("2. Dar un sistema por realizado exige inicio, termino, resultado, acciones y responsable")
def c2():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    e = espera_http(lambda: ac.capturar_actividades(
        r.id, sc.ActividadesIn(actividades=[fila("frenos", a_realizar="Balatas",
                                                 realizada="Hecho")]),
        usuario=w.admin, db=db), 422)
    falta = e.detail["sistemas_incompletos"][0]["falta"]
    for f in ("fecha de inicio", "fecha de término", "resultado", "acciones requeridas",
              "responsable"):
        assert f in falta, (f, falta)
    db.rollback()
    assert len(libro(db, w.unidad.id)) == 1, "un intento rechazado no deja asiento"
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        completa("frenos", w.tecnico.id)]), usuario=w.admin, db=db)
    ls = libro(db, w.unidad.id)
    assert len(ls) == 2 and ls[1].tipo == "actividad" and ls[1].sistema == "frenos"
    assert ls[1].resultado == "conforme" and ls[1].responsable_nombre == "Ramon Lopez"
    assert ls[1].fecha_inicio and ls[1].fecha_termino
    return "422 con los 5 faltantes; completo deja 1 asiento con los datos de 7.1.10"


@caso("3. Guardar los diez sistemas solo asienta los que cambiaron")
def c3():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    todas = [fila(k) for k, _ in m.SISTEMAS]
    todas[7] = fila("frenos", a_realizar="Revisar")
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=todas), usuario=w.admin, db=db)
    assert len(libro(db, w.unidad.id)) == 2
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=todas), usuario=w.admin, db=db)
    assert len(libro(db, w.unidad.id)) == 2, "guardar sin cambios no debe asentar nada"
    return "10 renglones enviados, 1 asiento; reenviar igual, 0 asientos"


@caso("4. Cambiar un texto ya escrito es una correccion que apunta al asiento anterior")
def c4():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        fila("motor", a_realizar="Cambio de aceite")]), usuario=w.admin, db=db)
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        fila("motor", a_realizar="Cambio de aceite y filtro")]), usuario=w.admin, db=db)
    ls = libro(db, w.unidad.id)
    ultimo = ls[-1]
    assert ultimo.corrige_a_id == ls[-2].id, "debe apuntar al asiento que corrige"
    assert "Corrige el asiento 2" in ultimo.descripcion and "Cambio de aceite»" in ultimo.descripcion
    assert ls[-2].descripcion.startswith("Sistema motor"), "el asiento viejo sigue intacto"
    return "asiento 3 corrige al 2 y dice lo que decia antes; el 2 no cambio"


@caso("5. La base rechaza editar o borrar un asiento, y borrar un formato")
def c5():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    # Los disparadores son por renglon: sobre una tabla vacia no hay nada que
    # detener. La auditoria necesita al menos un asiento para probarse.
    from app.core.security import registrar_bitacora
    registrar_bitacora(db, w.admin.id, "prueba"); db.commit()
    for sql in ("UPDATE bitacora_mantenimiento SET descripcion = 'x'",
                "DELETE FROM bitacora_mantenimiento",
                f"DELETE FROM reporte_mantenimiento WHERE id = {r.id}",
                f"DELETE FROM actividad_reporte WHERE reporte_id = {r.id}",
                "DELETE FROM bitacora_auditoria"):
        try:
            db.execute(text(sql)); db.commit()
        except IntegrityError as e:
            db.rollback()
            assert "NOM-030" in str(e.orig), e
            continue
        raise AssertionError(f"la base acepto: {sql}")
    return "5 de 5 escrituras prohibidas abortadas por los candados"


@caso("6. Cerrar un formato con actividades funciona y deja asiento de cierre")
def c6():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        completa("frenos", w.tecnico.id), fila("llantas", a_realizar="Rotar")]),
        usuario=w.admin, db=db)
    for rol in ("vobo_mantenimiento", "recibe_salida"):
        ac.registrar_firma(r.id, sc.FirmaReporteIn(rol_firma=rol, nombre="Fulano Tal"),
                           usuario=w.admin, db=db)
    out = ac.cerrar_reporte(r.id, sc.CierreReporteIn(unidad_operativa=False,
                                                     comentarios_adicionales="Sale sin llantas"),
                            usuario=w.admin, db=db)
    assert out["estado"] == "cerrado"
    ls = libro(db, w.unidad.id)
    tipos = [a.tipo for a in ls]
    assert tipos[-1] == "cierre" and "comentarios" in tipos and tipos.count("firma") == 2, tipos
    cierre = ls[-1]
    assert cierre.resultado == "no_conforme" and "Llantas" in cierre.acciones_requeridas
    assert bs.verificar(ls)["integra"]
    # Y ya cerrado, la base no deja tocar sus renglones.
    try:
        db.execute(text(f"UPDATE actividad_reporte SET realizada='x' WHERE reporte_id={r.id}"))
        db.commit()
        raise AssertionError("se pudo editar un renglon de un formato cerrado")
    except IntegrityError:
        db.rollback()
    return f"cerrado con {len(ls)} asientos: {', '.join(tipos)}"


@caso("7. No cierra si un sistema realizado no trae los datos de la NOM (renglon viejo)")
def c7():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    a = next(x for x in r.actividades if x.sistema == "motor")
    a.realizada = "Hecho antes de la NOM"; a.fecha_realizada = ahora_utc(); db.commit()
    for rol in ("vobo_mantenimiento", "recibe_salida"):
        ac.registrar_firma(r.id, sc.FirmaReporteIn(rol_firma=rol, nombre="Fulano Tal"),
                           usuario=w.admin, db=db)
    e = espera_http(lambda: ac.cerrar_reporte(r.id, sc.CierreReporteIn(), usuario=w.admin,
                                              db=db), 409)
    assert e.detail["sistemas_incompletos"][0]["sistema"] == "motor", e.detail
    return "409 con el sistema y lo que le falta"


@caso("8. La salida por la orden (CU-ADM-10) tambien deja el asiento de cierre")
def c8():
    db = nueva_db(); w = Mundo(db)
    o = m.OrdenServicio(folio="OS-1", unidad_id=w.unidad.id, taller_id=w.taller.id)
    db.add(o); db.flush()
    r = svc.crear_reporte_mantenimiento(db, unidad=w.unidad, taller_id=w.taller.id,
                                        admin_id=w.admin.id, orden=o)
    db.commit()
    for rol in ("vobo_mantenimiento", "recibe_salida"):
        ac.registrar_firma(r.id, sc.FirmaReporteIn(rol_firma=rol, nombre="Fulano Tal"),
                           usuario=w.admin, db=db)
    ac.emitir_salida(o.id, sc.FormatoSalidaIn(operacion_a_realizar="Reparto"),
                     usuario=w.admin, db=db)
    db.refresh(r)
    assert r.estado == "cerrado"
    assert libro(db, w.unidad.id)[-1].tipo == "cierre"
    return "formato cerrado por la orden, con su asiento de cierre"


@caso("9. Corregir un formato cerrado agrega un asiento y no toca el formato")
def c9():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        completa("frenos", w.tecnico.id)]), usuario=w.admin, db=db)
    for rol in ("vobo_mantenimiento", "recibe_salida"):
        ac.registrar_firma(r.id, sc.FirmaReporteIn(rol_firma=rol, nombre="Fulano Tal"),
                           usuario=w.admin, db=db)
    ac.cerrar_reporte(r.id, sc.CierreReporteIn(), usuario=w.admin, db=db)
    frenos = next(a for a in libro(db, w.unidad.id) if a.sistema == "frenos")
    espera_http(lambda: ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        fila("frenos", a_realizar="otra cosa")]), usuario=w.admin, db=db), 409)
    out = ac.corregir_reporte(r.id, sc.CorreccionIn(
        asiento_id=frenos.id, texto="Eran balatas traseras, no delanteras",
        motivo="Error de dedo al capturar"), usuario=w.admin, db=db)
    ls = libro(db, w.unidad.id)
    assert ls[-1].tipo == "correccion" and ls[-1].corrige_a_id == frenos.id
    assert out["correcciones"] and out["correcciones"][0]["corrige_a_numero"] == frenos.numero
    act = next(a for a in out["actividades"] if a["sistema"] == "frenos")
    assert act["realizada"] == "Balatas cambiadas", "el formato no debe cambiar"
    # Un asiento de otro formato no se puede corregir desde este.
    otra = m.Unidad(num_economico="BG-901", tipo_unidad_id=w.pipa.id)
    db.add(otra); db.commit()
    r2 = w.reporte(unidad=otra)
    ajeno = libro(db, r2.unidad_id)[0]
    espera_http(lambda: ac.corregir_reporte(r.id, sc.CorreccionIn(
        asiento_id=ajeno.id, texto="xxxx", motivo="yyyy"), usuario=w.admin, db=db), 404)
    return "asiento de correccion ligado; el formato sigue diciendo lo mismo"


@caso("10. La verificacion detecta un asiento editado o borrado por fuera")
def c10():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        fila("motor", a_realizar="Aceite"), fila("frenos", a_realizar="Balatas")]),
        usuario=w.admin, db=db)
    assert bs.verificar(libro(db, w.unidad.id))["integra"]
    # Alguien con acceso a la base quita el candado y edita el asiento 2.
    db.execute(text("DROP TRIGGER bitacora_mant_no_se_altera"))
    db.execute(text("UPDATE bitacora_mantenimiento SET descripcion='nada' WHERE numero=2"))
    db.commit(); db.expire_all()
    v = bs.verificar(libro(db, w.unidad.id))
    assert not v["integra"] and v["falla_en"] == 2, v
    db.execute(text("DROP TRIGGER bitacora_mant_no_se_borra"))
    db.execute(text("DELETE FROM bitacora_mantenimiento WHERE numero=2")); db.commit()
    db.expire_all()
    v = bs.verificar(libro(db, w.unidad.id))
    assert not v["integra"] and v["falla_en"] == 2, v
    return "edicion detectada en el asiento 2; borrado detectado como hueco en el 2"


@caso("11. Los formatos anteriores al libro se transcriben UNA vez; los nuevos sin asiento no")
def c11():
    db = nueva_db(); w = Mundo(db)
    # Formato viejo: se crea "a mano", como existian antes del libro.
    viejo = m.ReporteMantenimiento(folio="RM-2026-00001", unidad_id=w.unidad.id,
                                   taller_id=w.taller.id, estado="cerrado",
                                   fecha_salida=ahora_utc(),
                                   capturado_por_admin_id=w.admin.id)
    db.add(viejo); db.commit()
    res = asegurar_asientos_de_reportes(db)
    assert res.startswith("1 formato"), res
    ls = libro(db, w.unidad.id)
    assert ls[0].tipo == "migracion" and ls[0].registrado_por_id is None
    assert "Sistema" in ls[0].registrado_por_nombre
    assert asegurar_asientos_de_reportes(db).startswith("0 formato"), "no es idempotente"
    # Un formato nacido DESPUES del libro y sin apertura es un defecto: no se tapa.
    raro = m.ReporteMantenimiento(folio="RM-2026-00099", unidad_id=w.unidad.id,
                                  taller_id=w.taller.id,
                                  creado_en=ahora_utc() + timedelta(seconds=5))
    db.add(raro); db.commit()
    res = asegurar_asientos_de_reportes(db)
    assert "sin apertura" in res and len(libro(db, w.unidad.id)) == 1, res
    return "1 transcrito, 0 la segunda vez, y el hueco posterior se reporta"


@caso("12. El mecanico no puede terminar sin resultado, y con el deja asiento")
def c12():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    a = next(x for x in r.actividades if x.sistema == "electrico")
    a.tecnico_id = w.tec_mec.id; db.commit()
    mc.registrar_diagnostico(a.id, "Alternador flojo", db=db, usuario=w.mec_u)
    e = espera_http(lambda: mc.registrar_avance(a.id, "Listo", terminada=True, datos=None,
                                                db=db, usuario=w.mec_u), 422)
    assert "resultado" in e.detail["falta"], e.detail
    db.rollback()
    hoy = dia_operativo(ahora_utc())
    espera_http(lambda: mc.registrar_avance(a.id, "Listo", terminada=True,
                datos=sc.AvanceActividadIn(fecha_inicio=hoy, fecha_termino=hoy + timedelta(days=2),
                                           resultado="conforme", acciones_requeridas="Ninguna"),
                db=db, usuario=w.mec_u), 422)
    db.rollback()
    mc.registrar_avance(a.id, "Alternador ajustado", terminada=True,
                        datos=sc.AvanceActividadIn(fecha_inicio=hoy, fecha_termino=hoy,
                                                   resultado="conforme",
                                                   acciones_requeridas="Revisar en 30 dias"),
                        db=db, usuario=w.mec_u)
    ls = libro(db, w.unidad.id)
    assert ls[-1].registrado_por_nombre == "Mario Mecanico" and ls[-1].resultado == "conforme"
    assert ls[-1].acciones_requeridas == "Revisar en 30 dias"
    return "422 sin resultado, 422 con termino futuro; completo asienta a nombre del mecanico"


@caso("13. El chofer titular ve el libro de su unidad aunque no la traiga; otro chofer no")
def c13():
    db = nueva_db(); w = Mundo(db); w.reporte()
    w.unidad.poseedor_chofer_id = w.otro_chofer.id; db.commit()
    out = bc.libro_de_unidad(w.unidad.id, usuario=w.chofer_u, db=db)
    assert out["integridad"]["integra"] and out["cabecera"]["num_economico"] == "BG-900P"
    extra = m.Unidad(num_economico="BG-777", tipo_unidad_id=w.pipa.id)
    db.add(extra); db.commit()
    espera_http(lambda: bc.libro_de_unidad(extra.id, usuario=w.chofer_u, db=db), 403)
    mis = bc.mis_unidades(usuario=w.chofer_u, db=db)
    assert [x["num_economico"] for x in mis] == ["BG-900P"] and not mis[0]["la_traigo"]
    return "titular: lo ve; unidad ajena: 403"


@caso("14. Sin permiso capturado, una pipa lo marca; una utilitaria no")
def c14():
    db = nueva_db(); w = Mundo(db)
    out = bc.libro_de_unidad(w.unidad.id, usuario=w.admin, db=db)
    assert "número de permiso" in out["faltan_datos_nom030"], out["faltan_datos_nom030"]
    u = m.Unidad(num_economico="UT-1", tipo_unidad_id=w.util.id); db.add(u); db.commit()
    assert bc.libro_de_unidad(u.id, usuario=w.admin, db=db)["faltan_datos_nom030"] == []
    bc.fijar_regulado(bc.ReguladoIn(razon_social="Gas SA de CV", permiso="LP/123/DIST/2020"),
                      usuario=w.admin, db=db)
    bc.fijar_identificacion(w.unidad.id, bc.IdentificacionUnidadIn(
        personal_auxiliar="Pepe Ayudante"), usuario=w.admin, db=db)
    out = bc.libro_de_unidad(w.unidad.id, usuario=w.admin, db=db)
    assert out["cabecera"]["permiso"] == "LP/123/DIST/2020"
    assert out["faltan_datos_nom030"] == [], out["faltan_datos_nom030"]
    return "pipa: falta permiso -> capturado -> completo; utilitaria: no aplica"


@caso("15. La fusion nocturna no toca una unidad que ya tiene libro")
def c15():
    db = nueva_db(); w = Mundo(db)
    a = m.Unidad(num_economico="BG-439", tipo_unidad_id=w.pipa.id, marca="X")
    b = m.Unidad(num_economico="BG439P", tipo_unidad_id=w.pipa.id)
    db.add_all([a, b]); db.commit()
    w.reporte(unidad=b)
    hecho = limpieza.limpiar(db); db.commit()
    assert any("libro de bitacora" in x for x in hecho["avisos"]), hecho
    assert db.query(m.Unidad).filter_by(num_economico="BG439P").first() is not None
    assert bs.verificar(libro(db, b.id))["integra"]
    return "la pareja con libro se salta con aviso; el libro sigue integro"


@caso("16. Reasignar y firmar dejan asiento, con el motivo")
def c16():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        fila("frenos", a_realizar="Balatas", tecnico_id=w.tecnico.id)]),
        usuario=w.admin, db=db)
    ac.reasignar_sistema(r.id, sc.ReasignacionIn(sistema="frenos", tecnico_id=w.tec_mec.id,
                                                 motivo="Ramon se fue a otra urgencia"),
                         usuario=w.admin, db=db)
    ls = libro(db, w.unidad.id)
    assert ls[-1].tipo == "reasignacion" and ls[-1].motivo == "Ramon se fue a otra urgencia"
    assert "Antes: responsable Ramon Lopez" in ls[-1].descripcion, ls[-1].descripcion
    return "asiento de reasignacion con el responsable anterior y el motivo"


def firmar_salida(w, r):
    for rol in ("vobo_mantenimiento", "recibe_salida"):
        ac.registrar_firma(r.id, sc.FirmaReporteIn(rol_firma=rol, nombre="Fulano Tal"),
                           usuario=w.admin, db=w.db)


# ===================================================================== #
# Lo que encontro la revision adversarial del 2026-09-28
# ===================================================================== #
@caso("17. Borrar lo realizado no deja un 'conforme' fantasma en el libro")
def c17():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    hoy = dia_operativo(ahora_utc())
    # Lo que manda la pantalla si escribieron, se propusieron fecha y "Ninguna",
    # eligieron Conforme... y luego borraron el texto de realizadas.
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[fila(
        "frenos", a_realizar="Balatas", realizada="", resultado="conforme",
        acciones_requeridas="Ninguna", fecha_inicio=hoy, fecha_termino=hoy)]),
        usuario=w.admin, db=db)
    a = next(x for x in r.actividades if x.sistema == "frenos")
    assert (a.resultado, a.acciones_requeridas, a.fecha_inicio, a.fecha_termino) == \
        (None, None, None, None), (a.resultado, a.fecha_inicio)
    ult = libro(db, w.unidad.id)[-1]
    assert ult.resultado is None and "conforme" not in ult.descripcion, ult.descripcion
    return "sin realizada, sin resultado ni fechas: el libro no dice 'conforme'"


@caso("18. Un 'no conforme' no puede decir que no requiere acciones")
def c18():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    e = espera_http(lambda: ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        completa("frenos", w.tecnico.id, resultado="no_conforme",
                 acciones_requeridas="Ninguna")]), usuario=w.admin, db=db), 422)
    assert "no conforme requiere" in e.detail["mensaje"], e.detail
    return "422: 'no conforme' con 'Ninguna' se rechaza"


@caso("19. Las fechas caben en la estancia: ni antes de la entrada, ni salida antes del trabajo")
def c19():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    hoy = dia_operativo(ahora_utc())
    e = espera_http(lambda: ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        completa("frenos", w.tecnico.id, fecha_inicio=hoy - timedelta(days=400))]),
        usuario=w.admin, db=db), 422)
    assert "anterior a la entrada" in e.detail, e.detail
    db.rollback()
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        completa("frenos", w.tecnico.id)]), usuario=w.admin, db=db)
    firmar_salida(w, r)
    e = espera_http(lambda: ac.cerrar_reporte(r.id, sc.CierreReporteIn(
        fecha_salida=r.fecha_entrada + timedelta(hours=2)), usuario=w.admin, db=db), 422)
    assert "termino del ultimo" in e.detail, e.detail
    return "inicio 400 dias antes: 422; salida antes del ultimo termino: 422"


@caso("20. Un preventivo no se cierra sin ninguna actividad realizada")
def c20():
    db = nueva_db(); w = Mundo(db); r = w.reporte(tipo="preventivo")
    db.add(m.Evidencia(entidad_tipo="reporte_mantenimiento", entidad_id=r.id,
                       url_archivo="reporte_mantenimiento/x.jpg")); db.commit()
    firmar_salida(w, r)
    e = espera_http(lambda: ac.cerrar_reporte(r.id, sc.CierreReporteIn(), usuario=w.admin,
                                              db=db), 409)
    assert e.detail.get("sin_actividades"), e.detail
    return "409: preventivo con foto y firmas pero sin trabajo no cierra"


@caso("21. El libro no se da por integro si le falta la apertura o el cierre de un formato")
def c21():
    db = nueva_db(); w = Mundo(db)
    asegurar_asientos_de_reportes(db)        # nace el libro
    r = w.reporte()
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[
        completa("frenos", w.tecnico.id)]), usuario=w.admin, db=db)
    firmar_salida(w, r)
    ac.cerrar_reporte(r.id, sc.CierreReporteIn(), usuario=w.admin, db=db)
    assert bc.libro_de_unidad(w.unidad.id, usuario=w.admin, db=db)["integridad"]["integra"]
    # Alguien con acceso a la base vacia el libro de la unidad.
    db.execute(text("DROP TRIGGER bitacora_mant_no_se_borra"))
    db.execute(text(f"DELETE FROM bitacora_mantenimiento WHERE unidad_id = {w.unidad.id}"))
    db.commit()
    v = bc.libro_de_unidad(w.unidad.id, usuario=w.admin, db=db)["integridad"]
    assert not v["integra"] and r.folio in v["motivo"], v
    return f"libro vaciado: '{v['motivo']}'"


@caso("22. Cambiar el personal auxiliar deja asiento; cada entrada conserva el de su dia")
def c22():
    db = nueva_db(); w = Mundo(db)
    bc.fijar_identificacion(w.unidad.id, bc.IdentificacionUnidadIn(personal_auxiliar="Jose"),
                            usuario=w.admin, db=db)
    r = w.reporte()
    bc.fijar_identificacion(w.unidad.id, bc.IdentificacionUnidadIn(personal_auxiliar="Pedro"),
                            usuario=w.admin, db=db)
    out = bc.libro_de_unidad(w.unidad.id, usuario=w.admin, db=db)
    tipos = [a["tipo"] for a in out["asientos"]]
    assert tipos == ["identificacion", "apertura", "identificacion"], tipos
    apertura = next(a for a in out["asientos"] if a["tipo"] == "apertura")
    assert apertura["identificacion"]["personal_auxiliar"] == "Jose", apertura["identificacion"]
    assert out["cabecera"]["personal_auxiliar"] == "Pedro"
    bc.fijar_regulado(bc.ReguladoIn(razon_social="Gas SA", permiso="LP/1"), usuario=w.admin, db=db)
    assert libro(db, w.unidad.id)[-1].tipo == "identificacion"
    return "hoy dice Pedro; la entrada dice Jose; cada cambio tiene su asiento"


@caso("23. La base no deja AGREGAR firmas ni renglones a un formato cerrado")
def c23():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    firmar_salida(w, r)
    ac.cerrar_reporte(r.id, sc.CierreReporteIn(), usuario=w.admin, db=db)
    for sql in (f"INSERT INTO firma_reporte (reporte_id, rol_firma, nombre) "
                f"VALUES ({r.id}, 'valida_trabajo', 'Otro')",
                f"INSERT INTO punto_revision (reporte_id, punto, estado) "
                f"VALUES ({r.id}, 'extra', 'bien')"):
        try:
            db.execute(text(sql)); db.commit()
        except IntegrityError:
            db.rollback(); continue
        raise AssertionError(f"la base acepto: {sql}")
    return "INSERT en hijos de un cerrado: abortado"


@caso("24. Dar por terminado un avance que ya estaba escrito deja asiento")
def c24():
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    a = next(x for x in r.actividades if x.sistema == "frenos")
    hoy = dia_operativo(ahora_utc())
    a.realizada = "Balatas puestas"; a.tecnico_id = w.tecnico.id; a.resultado = "conforme"
    a.acciones_requeridas = "Ninguna"; a.fecha_inicio = hoy; a.fecha_termino = hoy
    db.commit()                      # un avance del mecanico: texto sin sello
    antes = len(libro(db, w.unidad.id))
    ac.capturar_actividades(r.id, sc.ActividadesIn(actividades=[fila(
        "frenos", realizada="Balatas puestas", tecnico_id=w.tecnico.id, resultado="conforme",
        acciones_requeridas="Ninguna", fecha_inicio=hoy, fecha_termino=hoy)]),
        usuario=w.admin, db=db)
    ls = libro(db, w.unidad.id)
    assert len(ls) == antes + 1 and "se da por terminado" in ls[-1].descripcion, \
        [x.descripcion for x in ls[antes:]]
    return "el sello de terminado queda asentado aunque ningun texto cambie"


@caso("25. Levantar a mano no acepta lo realizado; ligar una orden deja asiento")
def c25():
    db = nueva_db(); w = Mundo(db)
    espera_http(lambda: ac.abrir_reporte(sc.ReporteMantenimientoIn(
        unidad_id=w.unidad.id, taller_id=w.taller.id,
        actividades=[fila("frenos", realizada="Hecho")]), usuario=w.admin, db=db), 422)
    db.rollback()
    r = w.reporte()
    o = m.OrdenServicio(folio="OS-9", unidad_id=w.unidad.id, taller_id=w.taller.id)
    db.add(o); db.flush()
    svc.crear_reporte_mantenimiento(db, unidad=w.unidad, taller_id=w.taller.id,
                                    admin_id=w.admin.id, orden=o)
    db.commit()
    ult = libro(db, w.unidad.id)[-1]
    assert ult.tipo == "vinculo" and "OS-9" in ult.descripcion and ult.reporte_id == r.id
    return "422 con realizada al abrir; la orden ligada despues queda asentada"


@caso("26. Los registros viejos por asignacion ya no escriben fuera del libro (410)")
def c26():
    db = nueva_db(); w = Mundo(db)
    espera_http(lambda: ac.registrar_avance(1, sc.AvanceIn(estado="terminada"),
                                            usuario=w.admin, db=db), 410)
    espera_http(lambda: ac.capturar_diagnostico(1, sc.CapturaDiagnosticoIn(diagnostico="x"),
                                                usuario=w.admin, db=db), 410)
    return "410 en los dos"


@caso("27. La huella de la foto es la de lo RECIBIDO, aunque en el disco haya otra cosa")
def c27():
    import hashlib
    import io
    from fastapi import UploadFile
    from starlette.datastructures import Headers
    db = nueva_db(); w = Mundo(db); r = w.reporte()
    foto = b"\xff\xd8\xff" + b"foto de verdad" * 50
    huella = hashlib.sha256(foto).hexdigest()
    carpeta = os.path.join(EVIDENCIAS, "reporte_mantenimiento")
    os.makedirs(carpeta, exist_ok=True)
    impostora = os.path.join(carpeta, huella[:32] + ".jpg")
    open(impostora, "wb").write(b"SUSTITUIDA")
    archivo = UploadFile(file=io.BytesIO(foto), filename="x.jpg",
                         headers=Headers({"content-type": "image/jpeg"}))
    ac.subir_evidencia_reporte(r.id, archivo=archivo, usuario=w.admin, db=db)
    import json
    ult = libro(db, w.unidad.id)[-1]
    assert json.loads(ult.datos)["sha256"] == huella
    assert open(impostora, "rb").read() == foto, "el archivo sustituido debio reponerse"
    return "la huella es la de lo subido y el archivo sustituido se repuso"


# ===================================================================== #
def main():
    ok = fallo = 0
    print("=" * 78)
    for nombre, fn in CASOS:
        try:
            detalle = fn()
            print("[ OK ]  %s\n        -> %s" % (nombre, detalle))
            ok += 1
        except AssertionError as e:
            fallo += 1
            print("[FALLA] %s\n        -> %s" % (nombre, e))
        except Exception:
            fallo += 1
            print("[ERROR] %s" % nombre)
            print("        " + traceback.format_exc().replace("\n", "\n        "))
    print("=" * 78)
    print("%d pasaron, %d fallaron, de %d casos" % (ok, fallo, len(CASOS)))
    return 1 if fallo else 0


if __name__ == "__main__":
    sys.exit(main())
