"""Modulo Chofer - CU-CHO-01 a CU-CHO-15."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models as m
from .. import services as svc
from ..database import get_db
from ..schemas import (AveriaIn, AveriaOut, MensajeOut, PeritajeIn, PrestamoIn, PrestamoOut,
                       PenalizacionOut, SolicitudIn, SolicitudOut, UbicacionIn, UnidadOut,
                       MantenimientoOut)
from ..security import notificar, registrar_bitacora, require_roles

router = APIRouter(prefix="/api/chofer", tags=["chofer"])
solo_chofer = require_roles("chofer")


def _mi_unidad(db: Session, chofer_id: int) -> m.Unidad:
    """La unidad de la que soy POSEEDOR hoy (RN-01), no necesariamente la que soy titular."""
    u = db.query(m.Unidad).filter(m.Unidad.poseedor_chofer_id == chofer_id).first()
    if not u:
        u = db.query(m.Unidad).filter(m.Unidad.titular_chofer_id == chofer_id,
                                      m.Unidad.poseedor_chofer_id.is_(None)).first()
    return u


# ------------------------------------------------------------- CU-CHO-01/02 -- #
@router.get("/mi-unidad", response_model=UnidadOut | None)
def mi_unidad(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    u = _mi_unidad(db, usuario.id)
    return svc.unidad_out(db, u) if u else None


@router.get("/mantenimientos", response_model=list[MantenimientoOut])
def mis_mantenimientos(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    u = _mi_unidad(db, usuario.id)
    if not u:
        return []
    progs = (db.query(m.ProgramaMantenimiento)
             .filter(m.ProgramaMantenimiento.unidad_id == u.id,
                     m.ProgramaMantenimiento.estado != "cancelado")
             .order_by(m.ProgramaMantenimiento.fecha_limite).all())
    return [svc.mantenimiento_out(p) for p in progs]


# ---------------------------------------------------------------- CU-CHO-03 -- #
@router.post("/jornada/iniciar", response_model=MensajeOut)
def iniciar_jornada(checklist_ok: bool = True, notas: str = "",
                    usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    """CU-CHO-03 con «include» CU-CHO-04: no se abre jornada sin checklist."""
    if not checklist_ok:
        raise HTTPException(400, "No se puede abrir la jornada sin el checklist pre-operacional")
    u = _mi_unidad(db, usuario.id)
    if not u:
        raise HTTPException(404, "No tienes una unidad asignada")
    abierta = (db.query(m.Jornada).filter(m.Jornada.chofer_id == usuario.id,
                                          m.Jornada.hora_fin.is_(None)).first())
    if abierta:
        raise HTTPException(409, "Ya tienes una jornada abierta")
    db.add(m.Jornada(chofer_id=usuario.id, unidad_id=u.id, km_inicio=u.km_actual,
                     checklist_ok=True, checklist_notas=notas))
    if u.estado == "disponible":
        u.estado = "en_ruta"
    registrar_bitacora(db, usuario.id, "jornada_iniciada", "unidad", u.id)
    db.commit()
    return {"mensaje": f"Jornada iniciada con la unidad {u.num_economico}"}


@router.post("/jornada/cerrar", response_model=MensajeOut)
def cerrar_jornada(km_fin: int | None = None, usuario=Depends(solo_chofer),
                   db: Session = Depends(get_db)):
    j = (db.query(m.Jornada).filter(m.Jornada.chofer_id == usuario.id,
                                    m.Jornada.hora_fin.is_(None)).first())
    if not j:
        raise HTTPException(404, "No tienes una jornada abierta")
    j.hora_fin = datetime.utcnow()
    if km_fin:
        j.km_fin = km_fin
        j.unidad.km_actual = km_fin
    if j.unidad.estado == "en_ruta":
        j.unidad.estado = "disponible"
    db.commit()
    return {"mensaje": "Jornada cerrada"}


@router.get("/jornada/actual")
def jornada_actual(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    j = (db.query(m.Jornada).filter(m.Jornada.chofer_id == usuario.id,
                                    m.Jornada.hora_fin.is_(None)).first())
    if not j:
        return {"abierta": False}
    return {"abierta": True, "id": j.id, "hora_inicio": j.hora_inicio,
            "unidad": j.unidad.num_economico}


# ------------------------------------------------------------- CU-CHO-05/06 -- #
@router.post("/solicitudes", response_model=SolicitudOut, status_code=201)
def crear_solicitud(datos: SolicitudIn, usuario=Depends(solo_chofer),
                    db: Session = Depends(get_db)):
    unidad = db.query(m.Unidad).filter(m.Unidad.id == datos.unidad_id).first()
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    if svc.poseedor_actual(db, unidad) != usuario.id:
        raise HTTPException(403, "Solo el poseedor actual puede solicitar el ingreso (RN-01)")
    s = m.SolicitudIngreso(unidad_id=unidad.id, chofer_id=usuario.id, taller_id=datos.taller_id,
                           tipo=datos.tipo, descripcion_falla=datos.descripcion_falla,
                           urgencia=datos.urgencia)
    db.add(s)
    db.flush()
    for admin in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
            m.Rol.nombre == "administrador").all():
        notificar(db, admin.id, "Nueva solicitud de ingreso",
                  f"Unidad {unidad.num_economico} - urgencia {datos.urgencia}",
                  "solicitud", "solicitud_ingreso", s.id)
    registrar_bitacora(db, usuario.id, "solicitud_creada", "solicitud_ingreso", s.id)
    db.commit()
    db.refresh(s)
    return svc.solicitud_out(db, s)


@router.get("/solicitudes", response_model=list[SolicitudOut])
def mis_solicitudes(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    ss = (db.query(m.SolicitudIngreso)
          .filter(m.SolicitudIngreso.chofer_id == usuario.id)
          .order_by(m.SolicitudIngreso.fecha_solicitud.desc()).all())
    return [svc.solicitud_out(db, s) for s in ss]


# ---------------------------------------------------------- CU-CHO-07/08/09 -- #
@router.post("/prestamos", response_model=PrestamoOut, status_code=201)
def prestar_unidad(datos: PrestamoIn, usuario=Depends(solo_chofer),
                   db: Session = Depends(get_db)):
    """CU-CHO-07. La responsabilidad NO se mueve hasta que el receptor acepta."""
    unidad = db.query(m.Unidad).filter(m.Unidad.id == datos.unidad_id).first()
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    svc.validar_puede_prestar(db, unidad, usuario.id, datos.chofer_recibe_id)

    p = m.PrestamoUnidad(unidad_id=unidad.id, chofer_presta_id=usuario.id,
                         chofer_recibe_id=datos.chofer_recibe_id, motivo=datos.motivo,
                         fecha_fin_prevista=datos.fecha_fin_prevista, estado="solicitado")
    db.add(p)
    db.flush()

    # Advertencia: el receptor hereda la obligacion de mantenimiento vencida.
    vencidos = (db.query(m.ProgramaMantenimiento)
                .filter(m.ProgramaMantenimiento.unidad_id == unidad.id,
                        m.ProgramaMantenimiento.estado == "pendiente",
                        m.ProgramaMantenimiento.fecha_limite < date.today()).count())
    aviso = (f" ATENCION: la unidad tiene {vencidos} mantenimiento(s) vencido(s); "
             "al aceptar heredas la responsabilidad.") if vencidos else ""
    notificar(db, datos.chofer_recibe_id, "Te quieren prestar una unidad",
              f"{usuario.nombre_completo} te presta la {unidad.num_economico} "
              f"por {datos.motivo}.{aviso}", "prestamo", "prestamo_unidad", p.id)

    ch = db.query(m.Chofer).filter(m.Chofer.usuario_id == usuario.id).first()
    if ch and ch.cuadrilla and ch.cuadrilla.supervisor_id:
        notificar(db, ch.cuadrilla.supervisor_id, "Prestamo solicitado en tu cuadrilla",
                  f"{usuario.nombre_completo} -> unidad {unidad.num_economico}",
                  "prestamo", "prestamo_unidad", p.id)
    registrar_bitacora(db, usuario.id, "prestamo_solicitado", "prestamo_unidad", p.id)
    db.commit()
    db.refresh(p)
    return svc.prestamo_out(db, p)


@router.post("/prestamos/{prestamo_id}/aceptar", response_model=PrestamoOut)
def aceptar_prestamo(prestamo_id: int, usuario=Depends(solo_chofer),
                     db: Session = Depends(get_db)):
    """CU-CHO-08. Aqui es donde CAMBIA la responsabilidad (RN-01)."""
    p = db.query(m.PrestamoUnidad).filter(m.PrestamoUnidad.id == prestamo_id).first()
    if not p:
        raise HTTPException(404, "Prestamo no encontrado")
    if p.chofer_recibe_id != usuario.id:
        raise HTTPException(403, "Este prestamo no es para ti")
    if p.estado != "solicitado":
        raise HTTPException(409, f"El prestamo esta en estado '{p.estado}'")

    p.estado = "activo"
    p.fecha_aceptacion = datetime.utcnow()
    p.fecha_inicio = datetime.utcnow()
    p.unidad.poseedor_chofer_id = usuario.id          # <-- transferencia de responsabilidad
    notificar(db, p.chofer_presta_id, "Prestamo aceptado",
              f"{usuario.nombre_completo} acepto la unidad {p.unidad.num_economico}",
              "prestamo", "prestamo_unidad", p.id)
    registrar_bitacora(db, usuario.id, "prestamo_aceptado_responsabilidad_transferida",
                       "prestamo_unidad", p.id,
                       f"poseedor {p.chofer_presta_id} -> {usuario.id}")
    db.commit()
    db.refresh(p)
    return svc.prestamo_out(db, p)


@router.post("/prestamos/{prestamo_id}/rechazar", response_model=MensajeOut)
def rechazar_prestamo(prestamo_id: int, motivo: str = "", usuario=Depends(solo_chofer),
                      db: Session = Depends(get_db)):
    p = db.query(m.PrestamoUnidad).filter(m.PrestamoUnidad.id == prestamo_id).first()
    if not p or p.chofer_recibe_id != usuario.id:
        raise HTTPException(404, "Prestamo no encontrado")
    if p.estado != "solicitado":
        raise HTTPException(409, f"El prestamo esta en estado '{p.estado}'")
    p.estado = "rechazado"
    p.motivo_rechazo = motivo
    notificar(db, p.chofer_presta_id, "Prestamo rechazado",
              f"{usuario.nombre_completo} rechazo la unidad. {motivo}", "prestamo")
    db.commit()
    return {"mensaje": "Prestamo rechazado"}


@router.post("/prestamos/{prestamo_id}/devolver", response_model=PrestamoOut)
def devolver_unidad(prestamo_id: int, usuario=Depends(solo_chofer),
                    db: Session = Depends(get_db)):
    """CU-CHO-09. La responsabilidad regresa al titular."""
    p = db.query(m.PrestamoUnidad).filter(m.PrestamoUnidad.id == prestamo_id).first()
    if not p:
        raise HTTPException(404, "Prestamo no encontrado")
    if usuario.id not in (p.chofer_recibe_id, p.chofer_presta_id):
        raise HTTPException(403, "No participas en este prestamo")
    if p.estado != "activo":
        raise HTTPException(409, f"El prestamo esta en estado '{p.estado}'")

    p.estado = "cerrado"
    p.fecha_fin_real = datetime.utcnow()
    p.unidad.poseedor_chofer_id = p.chofer_presta_id   # vuelve al titular
    notificar(db, p.chofer_presta_id, "Unidad devuelta",
              f"La unidad {p.unidad.num_economico} regreso a tu responsabilidad",
              "prestamo", "prestamo_unidad", p.id)
    registrar_bitacora(db, usuario.id, "prestamo_cerrado", "prestamo_unidad", p.id)
    db.commit()
    db.refresh(p)
    return svc.prestamo_out(db, p)


@router.get("/prestamos", response_model=list[PrestamoOut])
def mis_prestamos(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    ps = (db.query(m.PrestamoUnidad)
          .filter((m.PrestamoUnidad.chofer_presta_id == usuario.id) |
                  (m.PrestamoUnidad.chofer_recibe_id == usuario.id))
          .order_by(m.PrestamoUnidad.fecha_solicitud.desc()).all())
    return [svc.prestamo_out(db, p) for p in ps]


@router.get("/companeros")
def companeros(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    """Choferes elegibles para recibir un prestamo (licencia vigente)."""
    out = []
    for c in db.query(m.Chofer).filter(m.Chofer.usuario_id != usuario.id).all():
        if c.vencimiento_licencia and c.vencimiento_licencia < date.today():
            continue
        if not c.usuario or not c.usuario.activo:
            continue
        out.append({"id": c.usuario_id, "nombre": c.usuario.nombre_completo,
                    "cuadrilla": c.cuadrilla.nombre if c.cuadrilla else None})
    return out


# ------------------------------------------------------- CU-CHO-10/11/12/13 -- #
@router.post("/averias", response_model=AveriaOut, status_code=201)
def reportar_averia(datos: AveriaIn, usuario=Depends(solo_chofer),
                    db: Session = Depends(get_db)):
    """CU-CHO-10 con «include» CU-CHO-13 (ubicacion)."""
    unidad = db.query(m.Unidad).filter(m.Unidad.id == datos.unidad_id).first()
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    if svc.poseedor_actual(db, unidad) != usuario.id:
        raise HTTPException(403, "Solo el poseedor actual puede reportar la averia (RN-01)")

    ch = db.query(m.Chofer).filter(m.Chofer.usuario_id == usuario.id).first()
    sup_id = ch.cuadrilla.supervisor_id if ch and ch.cuadrilla else None

    r = m.ReporteAveria(folio=svc.siguiente_folio(db, m.ReporteAveria, "AVE"),
                        unidad_id=unidad.id, chofer_id=usuario.id,
                        latitud=datos.latitud, longitud=datos.longitud,
                        direccion_referencia=datos.direccion_referencia,
                        descripcion_falla=datos.descripcion_falla,
                        en_vialidad_publica=datos.en_vialidad_publica,
                        hay_terceros_involucrados=datos.hay_terceros_involucrados,
                        requiere_arrastre=datos.requiere_arrastre,
                        supervisor_notificado_id=sup_id,
                        estado="esperando_peritos" if datos.en_vialidad_publica else "abierto")
    db.add(r)
    db.add(m.UbicacionUnidad(unidad_id=unidad.id, latitud=datos.latitud,
                             longitud=datos.longitud))
    unidad.estado = "varada"
    db.flush()

    notificar(db, sup_id, "Unidad varada",
              f"{unidad.num_economico} varada. {datos.descripcion_falla}", "averia",
              "reporte_averia", r.id)
    if not datos.en_vialidad_publica:
        for mo in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
                m.Rol.nombre == "montacarguista").all():
            notificar(db, mo.id, "Unidad varada requiere apoyo",
                      f"{unidad.num_economico}: {datos.descripcion_falla}", "averia",
                      "reporte_averia", r.id)
    registrar_bitacora(db, usuario.id, "averia_reportada", "reporte_averia", r.id)
    db.commit()
    db.refresh(r)
    return svc.averia_out(db, r)


@router.post("/averias/{averia_id}/peritaje", response_model=AveriaOut)
def registrar_peritaje(averia_id: int, datos: PeritajeIn, usuario=Depends(solo_chofer),
                       db: Session = Depends(get_db)):
    """CU-CHO-11 «extend» de CU-CHO-10. Desbloquea el arrastre (RN-04)."""
    r = db.query(m.ReporteAveria).filter(m.ReporteAveria.id == averia_id).first()
    if not r or r.chofer_id != usuario.id:
        raise HTTPException(404, "Reporte no encontrado")
    if r.peritaje:
        raise HTTPException(409, "Este reporte ya tiene peritaje registrado")
    db.add(m.ReportePeritaje(reporte_averia_id=r.id, folio_peritos=datos.folio_peritos,
                             aseguradora=datos.aseguradora, nombre_perito=datos.nombre_perito,
                             observaciones=datos.observaciones))
    r.estado = "en_atencion"
    db.flush()
    for mo in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
            m.Rol.nombre == "montacarguista").all():
        notificar(db, mo.id, "Arrastre habilitado (peritos ya avisados)",
                  f"Unidad {r.unidad.num_economico} - folio peritos {datos.folio_peritos}",
                  "averia", "reporte_averia", r.id)
    registrar_bitacora(db, usuario.id, "peritaje_registrado", "reporte_averia", r.id)
    db.commit()
    db.refresh(r)
    return svc.averia_out(db, r)


@router.post("/averias/{averia_id}/arrastre", response_model=MensajeOut)
def solicitar_arrastre(averia_id: int, usuario=Depends(solo_chofer),
                       db: Session = Depends(get_db)):
    """CU-CHO-12. Bloqueado por RN-04 si falta el peritaje."""
    r = db.query(m.ReporteAveria).filter(m.ReporteAveria.id == averia_id).first()
    if not r or r.chofer_id != usuario.id:
        raise HTTPException(404, "Reporte no encontrado")
    if not svc.puede_solicitar_arrastre(r):
        raise HTTPException(
            409, "RN-04: la unidad esta en vialidad publica. Primero registra el aviso a "
                 "peritos con su folio; hasta entonces no se habilita el arrastre.")
    if r.arrastre:
        raise HTTPException(409, "Ya existe un arrastre para este reporte")

    a = m.Arrastre(folio=svc.siguiente_folio(db, m.Arrastre, "ARR"), reporte_averia_id=r.id,
                   unidad_arrastrada_id=r.unidad_id, chofer_responsable_id=usuario.id,
                   estado="solicitado")
    db.add(a)
    r.requiere_arrastre = True
    db.flush()
    for mo in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
            m.Rol.nombre == "montacarguista").all():
        notificar(db, mo.id, "Nuevo arrastre solicitado",
                  f"Unidad {r.unidad.num_economico}", "arrastre", "arrastre", a.id)
    db.commit()
    return {"mensaje": f"Arrastre {a.folio} solicitado"}


@router.get("/averias", response_model=list[AveriaOut])
def mis_averias(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    rs = (db.query(m.ReporteAveria).filter(m.ReporteAveria.chofer_id == usuario.id)
          .order_by(m.ReporteAveria.fecha_hora.desc()).all())
    return [svc.averia_out(db, r) for r in rs]


@router.post("/ubicacion", response_model=MensajeOut)
def enviar_ubicacion(datos: UbicacionIn, usuario=Depends(solo_chofer),
                     db: Session = Depends(get_db)):
    """CU-CHO-13. RN-10: solo se acepta con jornada abierta o averia en curso."""
    j = (db.query(m.Jornada).filter(m.Jornada.chofer_id == usuario.id,
                                    m.Jornada.hora_fin.is_(None)).first())
    unidad = _mi_unidad(db, usuario.id)
    if not unidad:
        raise HTTPException(404, "No tienes unidad asignada")
    if not j and unidad.estado not in ("varada", "en_arrastre"):
        raise HTTPException(403, "RN-10: solo se registra ubicacion en jornada o emergencia")
    db.add(m.UbicacionUnidad(unidad_id=unidad.id, latitud=datos.latitud,
                             longitud=datos.longitud))
    db.commit()
    return {"mensaje": "Ubicacion registrada"}


# ------------------------------------------------------------- CU-CHO-14/15 -- #
@router.get("/penalizaciones", response_model=list[PenalizacionOut])
def mis_penalizaciones(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    ps = (db.query(m.Penalizacion).filter(m.Penalizacion.chofer_id == usuario.id)
          .order_by(m.Penalizacion.fecha_generacion.desc()).all())
    return [{"id": p.id, "unidad": p.unidad.num_economico if p.unidad else "-",
             "chofer": usuario.nombre_completo, "motivo": p.motivo,
             "fecha_generacion": p.fecha_generacion, "dias_atraso": p.dias_atraso,
             "estado": p.estado} for p in ps]


@router.post("/penalizaciones/{pen_id}/inconformidad", response_model=MensajeOut)
def levantar_inconformidad(pen_id: int, motivo: str, usuario=Depends(solo_chofer),
                           db: Session = Depends(get_db)):
    """CU-CHO-15 «extend» de CU-CHO-14."""
    p = db.query(m.Penalizacion).filter(m.Penalizacion.id == pen_id,
                                        m.Penalizacion.chofer_id == usuario.id).first()
    if not p:
        raise HTTPException(404, "Penalizacion no encontrada")
    if p.estado != "aplicada":
        raise HTTPException(409, f"La penalizacion esta en estado '{p.estado}'")
    p.estado = "en_disputa"
    p.resolucion_disputa = f"[{datetime.utcnow():%Y-%m-%d}] Inconformidad del chofer: {motivo}"
    for g in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
            m.Rol.nombre == "gerente").all():
        notificar(db, g.id, "Inconformidad de penalizacion",
                  f"{usuario.nombre_completo}: {motivo}", "penalizacion", "penalizacion", p.id)
    registrar_bitacora(db, usuario.id, "inconformidad_levantada", "penalizacion", p.id)
    db.commit()
    return {"mensaje": "Inconformidad registrada. Gerencia la revisara."}


@router.get("/talleres")
def talleres(usuario=Depends(solo_chofer), db: Session = Depends(get_db)):
    return [{"id": t.id, "nombre": t.nombre, "direccion": t.direccion}
            for t in db.query(m.Taller).filter(m.Taller.activo.is_(True)).all()]
