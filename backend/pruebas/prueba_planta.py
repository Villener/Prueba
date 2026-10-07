"""Pruebas del mecanico de planta y de las cuentas corregidas (2026-10-07).

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_planta.py     (Windows)

- El mecanico ve y trabaja SOLO su planta: plano, casillas y solicitudes.
- El administrador lo cambia de planta y desde ahi ve la nueva y no la vieja.
- Rechazar una solicitud exige motivo, avisa al chofer y deja constancia.
- Victor y Pablo con su nombre real; Jaime Yair dado de baja.
"""
import os
import sys
import traceback

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import HTTPException                           # noqa: E402
from sqlalchemy import create_engine                        # noqa: E402
from sqlalchemy.orm import sessionmaker                     # noqa: E402

from app import models as m                                 # noqa: E402
from app import seed                                        # noqa: E402
from app.core.database import Base                          # noqa: E402
from app.modules.taller import administrador_controller as ac  # noqa: E402
from app.schemas import ResolucionSolicitudIn               # noqa: E402

CASOS = []


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


def prohibido(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except HTTPException as e:
        assert e.status_code == 403, e.status_code
        return e.detail
    raise AssertionError("lo dejo pasar")


def escenario():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng, autoflush=False)()
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
    for nombre in ("Alamos", "Tecate"):
        t = m.Taller(nombre=nombre)
        db.add(t)
        db.flush()
        z = m.ZonaTaller(taller_id=t.id, nombre="TALLER", cuenta_para_ocupacion=True)
        db.add(z)
        db.flush()
        e = m.Espacio(zona_id=z.id, numero="T-01", estado="libre")
        db.add(e)
        talleres[nombre], espacios[nombre] = t, e
    admin = persona("Victor", "e647@bajagas.mx", "administrador")
    mec = persona("Efren Jose", "e3205@bajagas.mx", "mecanico")
    tec = m.Tecnico(nombre="Efren Jose", apellidos="Martinez Garcia", num_empleado="3205",
                    especialidad="mecanico", modalidad="AUTONOMO",
                    taller_id=talleres["Tecate"].id, usuario_id=mec.id)
    db.add(tec)
    chofer_u = persona("Chofer", "e1@bajagas.mx", "chofer")
    db.add(m.Chofer(usuario_id=chofer_u.id))
    tipo = m.TipoUnidad(nombre="Reparto")
    db.add(tipo)
    db.flush()
    sol = {}
    for nombre, num in (("Alamos", "1001"), ("Tecate", "2002")):
        u = m.Unidad(num_economico=num, tipo_unidad_id=tipo.id)
        db.add(u)
        db.flush()
        s = m.SolicitudIngreso(unidad_id=u.id, chofer_id=chofer_u.id,
                               taller_id=talleres[nombre].id, descripcion_falla="ruido")
        db.add(s)
        sol[nombre] = s
    db.commit()
    return db, {"admin": admin, "mec": mec, "tec": tec, "chofer": chofer_u,
                "talleres": talleres, "espacios": espacios, "sol": sol}


@caso("el mecanico solo ve su planta en el selector y en el plano")
def _():
    db, x = escenario()
    assert [t["nombre"] for t in ac.talleres(usuario=x["mec"], db=db)] == ["Tecate"]
    assert len(ac.talleres(usuario=x["admin"], db=db)) == 2
    assert ac.plano_taller(x["talleres"]["Tecate"].id, usuario=x["mec"], db=db)["nombre"] == "Tecate"
    prohibido(ac.plano_taller, x["talleres"]["Alamos"].id, usuario=x["mec"], db=db)


@caso("el mecanico solo ve y atiende las solicitudes de su planta")
def _():
    db, x = escenario()
    vistas = ac.bandeja(usuario=x["mec"], db=db)
    assert [s["unidad"] for s in vistas] == ["2002"], vistas
    assert len(ac.bandeja(usuario=x["admin"], db=db)) == 2
    prohibido(ac.resolver_solicitud, x["sol"]["Alamos"].id,
              ResolucionSolicitudIn(aceptar=False, motivo_rechazo="no"), usuario=x["mec"], db=db)


@caso("no puede tocar casillas de otra planta, ni verlas")
def _():
    db, x = escenario()
    prohibido(ac.detalle_espacio, x["espacios"]["Alamos"].id, usuario=x["mec"], db=db)
    assert ac.detalle_espacio(x["espacios"]["Tecate"].id, usuario=x["mec"], db=db)["numero"] == "T-01"


@caso("rechazar exige motivo, avisa al chofer con la unidad y deja constancia")
def _():
    db, x = escenario()
    s = x["sol"]["Tecate"]
    try:
        ac.resolver_solicitud(s.id, ResolucionSolicitudIn(aceptar=False, motivo_rechazo="   "),
                              usuario=x["mec"], db=db)
    except HTTPException as e:
        assert e.status_code == 400
    else:
        raise AssertionError("rechazo sin motivo")
    r = ac.resolver_solicitud(s.id, ResolucionSolicitudIn(aceptar=False,
                              motivo_rechazo="La unidad se atiende en Alamos"),
                              usuario=x["mec"], db=db)
    assert r["estado"] == "rechazada" and r["atendida_por"].startswith("Efren")
    aviso = db.query(m.Notificacion).filter_by(usuario_id=x["chofer"].id).one()
    assert "2002" in aviso.mensaje and "Alamos" in aviso.mensaje
    b = db.query(m.BitacoraAuditoria).filter_by(accion="solicitud_rechazada").one()
    assert b.usuario_id == x["mec"].id and b.datos_despues == "La unidad se atiende en Alamos"


@caso("con una orden cerrada de su planta no puede sacar una unidad de un cajon de otra")
def _():
    db, x = escenario()
    tecate, alamos = x["talleres"]["Tecate"], x["talleres"]["Alamos"]
    u = db.query(m.Unidad).filter_by(num_economico="1001").one()
    vieja = m.OrdenServicio(folio="OS-1", unidad_id=u.id, taller_id=tecate.id, estado="cerrada",
                            fecha_salida=ac.ahora_utc())
    nueva = m.OrdenServicio(folio="OS-2", unidad_id=u.id, taller_id=alamos.id, estado="abierta")
    db.add_all([vieja, nueva])
    db.flush()
    cajon_alamos = x["espacios"]["Alamos"]
    db.add(m.OcupacionEspacio(espacio_id=cajon_alamos.id, unidad_id=u.id, orden_servicio_id=nueva.id))
    cajon_alamos.estado = "ocupado"
    db.commit()
    try:
        ac.mover_unidad(x["espacios"]["Tecate"].id, vieja.id, usuario=x["mec"], db=db)
    except ac.HTTPException as e:
        assert e.status_code in (403, 409), e.status_code
    else:
        raise AssertionError("dejo mover con una orden cerrada")
    db.refresh(cajon_alamos)
    assert cajon_alamos.estado == "ocupado"
    assert db.query(m.OcupacionEspacio).filter_by(espacio_id=cajon_alamos.id, fecha_salida=None).count() == 1
    # Ni el administrador estaciona una orden de Alamos en un cajon de Tecate.
    try:
        ac.mover_unidad(x["espacios"]["Tecate"].id, nueva.id, usuario=x["admin"], db=db)
    except ac.HTTPException as e:
        assert e.status_code == 409, e.status_code
    else:
        raise AssertionError("dejo cruzar plantas")


@caso("las requisiciones nuevas no se le asignan al capturista que ya se fue")
def _():
    db, x = escenario()
    rol = m.Rol(nombre="capturista")
    db.add(rol)
    db.flush()
    ido = m.Usuario(nombre="Jaime Yair", apellidos="X", email="e13905@bajagas.mx",
                    password_hash="x", activo=False)
    nuevo = m.Usuario(nombre="Nuevo", apellidos="Capturista", email="e2@bajagas.mx", password_hash="x")
    db.add_all([ido, nuevo])
    db.flush()
    db.add_all([m.UsuarioRol(usuario_id=ido.id, rol_id=rol.id),
                m.UsuarioRol(usuario_id=nuevo.id, rol_id=rol.id)])
    db.commit()
    cap = (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
           .filter(m.Rol.nombre == "capturista", m.Usuario.activo.is_(True))
           .order_by(m.Usuario.id).first())
    assert cap.id == nuevo.id
    import inspect
    from app import importador
    assert "m.Usuario.activo.is_(True)" in inspect.getsource(importador._importar_requisiciones)


@caso("el administrador lo cambia de planta: ve la nueva y ya no la vieja")
def _():
    db, x = escenario()
    alamos, tecate = x["talleres"]["Alamos"], x["talleres"]["Tecate"]
    r = ac.cambiar_planta(x["tec"].id, alamos.id, usuario=x["admin"], db=db)
    assert r["taller"] == "Alamos"
    assert ac.plano_taller(alamos.id, usuario=x["mec"], db=db)["nombre"] == "Alamos"
    prohibido(ac.plano_taller, tecate.id, usuario=x["mec"], db=db)
    b = db.query(m.BitacoraAuditoria).filter_by(accion="tecnico_cambio_de_planta").one()
    assert (b.datos_antes, b.datos_despues) == ("Tecate", "Alamos")
    assert db.query(m.Notificacion).filter_by(usuario_id=x["mec"].id).count() == 1
    fila = next(f for f in ac.mecanicos_de_planta(usuario=x["admin"], db=db)
                if f["id"] == x["tec"].id)
    assert fila["taller"] == "Alamos"


@caso("sin planta asignada, el mecanico no ve ninguna y se le dice por que")
def _():
    db, x = escenario()
    x["tec"].taller_id = None
    db.commit()
    detalle = prohibido(ac.talleres, usuario=x["mec"], db=db)
    assert "planta asignada" in detalle


@caso("la solicitud nueva le llega tambien al mecanico de esa planta")
def _():
    from app import services as svc
    db, x = escenario()
    assert svc.mecanicos_de_planta(db, x["talleres"]["Tecate"].id) == [x["mec"].id]
    assert svc.mecanicos_de_planta(db, x["talleres"]["Alamos"].id) == []


@caso("cuentas: Victor y Pablo con su nombre real, Jaime Yair dado de baja")
def _():
    db, _x = escenario()
    db.query(m.Usuario).filter_by(email="e647@bajagas.mx").update(
        {"nombre": "Victor", "apellidos": "Sallas Molina"})
    db.add(m.Usuario(nombre="Pablo", apellidos="Reyes Arturo", email="e11807@bajagas.mx",
                     password_hash="clave-de-pablo"))
    db.add(m.Usuario(nombre="Jaime Yair", apellidos="Dominguez Sanchez",
                     email="e13905@bajagas.mx", password_hash="x"))
    db.add(m.Tecnico(nombre="Jaime Yair", apellidos="Dominguez Sanchez", num_empleado="13905",
                     especialidad="mecanico"))
    db.commit()
    r = seed.corregir_cuentas_de_staff(db)
    assert r == {"renombradas": 2, "dadas_de_baja": 1}, r
    v = db.query(m.Usuario).filter_by(email="e647@bajagas.mx").one()
    p = db.query(m.Usuario).filter_by(email="e11807@bajagas.mx").one()
    j = db.query(m.Usuario).filter_by(email="e13905@bajagas.mx").one()
    assert (v.nombre, v.apellidos) == ("Víctor Manuel", "Reséndiz Martínez")
    assert (p.nombre, p.apellidos) == ("Pablo Arturo", "Reyes González")
    assert p.password_hash == "clave-de-pablo", "corregir el nombre no toca la contrasena"
    assert not j.activo
    assert not db.query(m.Tecnico).filter_by(num_empleado="13905").one().activo
    # Idempotente, y no pisa una correccion hecha despues a mano.
    v.apellidos = "Resendiz Martinez"
    db.commit()
    assert seed.corregir_cuentas_de_staff(db) == {"renombradas": 0, "dadas_de_baja": 0}
    db.refresh(v)
    assert v.apellidos == "Resendiz Martinez"
    # Una base nueva ya no crea la cuenta del capturista que renuncio.
    assert not any(c == "e13905@bajagas.mx" for _, _, c, _, _ in seed.USUARIOS_DEMO)


if __name__ == "__main__":
    ok = fallo = 0
    for i, (nombre, fn) in enumerate(CASOS, 1):
        try:
            fn()
            ok += 1
            print(f"  OK   {i:2d}. {nombre}")
        except Exception:
            fallo += 1
            print(f"  FALLA {i:2d}. {nombre}")
            traceback.print_exc()
    print(f"\n{ok} pasaron, {fallo} fallaron, de {len(CASOS)} casos")
    sys.exit(1 if fallo else 0)
