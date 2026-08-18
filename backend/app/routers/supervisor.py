"""Modulo Supervisor - CU-SUP-01 a CU-SUP-09."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models as m
from .. import services as svc
from ..database import get_db
from ..schemas import AveriaOut, MensajeOut, PrestamoOut
from ..security import notificar, registrar_bitacora, require_roles

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])
solo_sup = require_roles("supervisor")


def _mis_choferes(db: Session, supervisor_id: int):
    return (db.query(m.Chofer).join(m.Cuadrilla)
            .filter(m.Cuadrilla.supervisor_id == supervisor_id).all())


# ------------------------------------------------------------- CU-SUP-01/02 -- #
@router.get("/cuadrilla")
def mi_cuadrilla(usuario=Depends(solo_sup), db: Session = Depends(get_db)):
    """CU-SUP-02: quien esta conduciendo, con que unidad, y quien no."""
    out = []
    for c in _mis_choferes(db, usuario.id):
        jornada = (db.query(m.Jornada)
                   .filter(m.Jornada.chofer_id == c.usuario_id,
                           m.Jornada.hora_fin.is_(None)).first())
        # Un chofer puede responder por varias unidades a la vez (la suya y una prestada).
        unidades = (db.query(m.Unidad)
                    .filter(m.Unidad.poseedor_chofer_id == c.usuario_id).all())
        unidad = unidades[0] if unidades else None
        prest = svc.prestamo_activo(db, unidad.id) if unidad else None
        ubic = None
        if unidad:
            u = (db.query(m.UbicacionUnidad)
                 .filter(m.UbicacionUnidad.unidad_id == unidad.id)
                 .order_by(m.UbicacionUnidad.capturado_en.desc()).first())
            if u:
                ubic = {"lat": u.latitud, "lng": u.longitud, "fecha": u.capturado_en}
        out.append({
            "chofer_id": c.usuario_id,
            "chofer": c.usuario.nombre_completo if c.usuario else "-",
            "conduciendo": jornada is not None,
            "desde": jornada.hora_inicio if jornada else None,
            "unidad": unidad.num_economico if unidad else None,
            "unidad_id": unidad.id if unidad else None,
            "estado_unidad": unidad.estado if unidad else None,
            "unidades": [{"num_economico": x.num_economico, "estado": x.estado}
                         for x in unidades],
            "taller": unidad.taller_actual_id is not None if unidad else False,
            "es_prestada": bool(prest and prest.estado == "activo"),
            "prestada_por": svc.nombre_chofer(db, prest.chofer_presta_id)
                            if prest and prest.estado == "activo" else None,
            "ubicacion": ubic,
        })
    return out


# ---------------------------------------------------------------- CU-SUP-03 -- #
@router.get("/prestamos", response_model=list[PrestamoOut])
def prestamos_cuadrilla(usuario=Depends(solo_sup), db: Session = Depends(get_db)):
    ids = [c.usuario_id for c in _mis_choferes(db, usuario.id)]
    if not ids:
        return []
    ps = (db.query(m.PrestamoUnidad)
          .filter((m.PrestamoUnidad.chofer_presta_id.in_(ids)) |
                  (m.PrestamoUnidad.chofer_recibe_id.in_(ids)))
          .order_by(m.PrestamoUnidad.fecha_solicitud.desc()).all())
    return [svc.prestamo_out(db, p) for p in ps]


# ---------------------------------------------------------------- CU-SUP-04 -- #
@router.post("/prestamos/{prestamo_id}/vetar", response_model=MensajeOut)
def vetar_prestamo(prestamo_id: int, motivo: str, usuario=Depends(solo_sup),
                   db: Session = Depends(get_db)):
    p = db.query(m.PrestamoUnidad).filter(m.PrestamoUnidad.id == prestamo_id).first()
    if not p:
        raise HTTPException(404, "Prestamo no encontrado")
    if p.estado not in ("solicitado", "activo"):
        raise HTTPException(409, f"El prestamo esta en estado '{p.estado}'")
    era_activo = p.estado == "activo"
    p.estado = "rechazado"
    p.motivo_rechazo = motivo
    p.autorizado_por_supervisor_id = usuario.id
    if era_activo:
        p.unidad.poseedor_chofer_id = p.chofer_presta_id  # revierte la responsabilidad
        p.fecha_fin_real = datetime.utcnow()
    for cid in (p.chofer_presta_id, p.chofer_recibe_id):
        notificar(db, cid, "Prestamo vetado por el supervisor", motivo, "prestamo")
    registrar_bitacora(db, usuario.id, "prestamo_vetado", "prestamo_unidad", p.id, motivo)
    db.commit()
    return {"mensaje": "Prestamo vetado"}


# ------------------------------------------------------------- CU-SUP-05/06 -- #
@router.get("/averias", response_model=list[AveriaOut])
def averias_cuadrilla(usuario=Depends(solo_sup), db: Session = Depends(get_db)):
    ids = [c.usuario_id for c in _mis_choferes(db, usuario.id)]
    rs = (db.query(m.ReporteAveria)
          .filter(m.ReporteAveria.chofer_id.in_(ids) if ids else False,
                  m.ReporteAveria.estado != "resuelto")
          .order_by(m.ReporteAveria.fecha_hora.desc()).all())
    return [svc.averia_out(db, r) for r in rs]


# ------------------------------------------------------------- CU-SUP-07/09 -- #
@router.post("/averias/{averia_id}/despachar", response_model=MensajeOut)
def despachar_apoyo(averia_id: int, tipo: str = "montacarguista", tecnico_id: int | None = None,
                    usuario=Depends(solo_sup), db: Session = Depends(get_db)):
    """CU-SUP-07 (montacarguista) y CU-SUP-09 (mecanico a sitio).

    CU-SUP-09 absorbe al antiguo CU-MEC-07: como el mecanico no usa la app, el
    supervisor deja la constancia del envio.
    """
    r = db.query(m.ReporteAveria).filter(m.ReporteAveria.id == averia_id).first()
    if not r:
        raise HTTPException(404, "Reporte no encontrado")

    if tipo == "mecanico":
        if not tecnico_id:
            raise HTTPException(400, "Indica que tecnico se envio a sitio")
        t = db.query(m.Tecnico).filter(m.Tecnico.id == tecnico_id).first()
        if not t:
            raise HTTPException(404, "Tecnico no encontrado")
        r.estado = "en_atencion"
        registrar_bitacora(db, usuario.id, "mecanico_enviado_a_sitio", "reporte_averia", r.id,
                           f"tecnico={t.nombre_completo}")
        notificar(db, r.chofer_id, "Mecanico en camino",
                  f"Se envio a {t.nombre_completo} ({t.telefono or 'sin telefono'}) a tu ubicacion",
                  "averia", "reporte_averia", r.id)
        db.commit()
        return {"mensaje": f"Envio de {t.nombre_completo} registrado (CU-SUP-09)"}

    if not svc.puede_solicitar_arrastre(r):
        raise HTTPException(409, "RN-04: falta registrar el aviso a peritos antes del arrastre")
    for mo in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
            m.Rol.nombre == "montacarguista").all():
        notificar(db, mo.id, "Escalamiento del supervisor",
                  f"Unidad {r.unidad.num_economico} sigue varada", "arrastre",
                  "reporte_averia", r.id)
    registrar_bitacora(db, usuario.id, "apoyo_escalado", "reporte_averia", r.id)
    db.commit()
    return {"mensaje": "Apoyo escalado a los montacarguistas"}


# ---------------------------------------------------------------- CU-SUP-08 -- #
@router.get("/cumplimiento")
def cumplimiento(usuario=Depends(solo_sup), db: Session = Depends(get_db)):
    ids = [c.usuario_id for c in _mis_choferes(db, usuario.id)]
    out = []
    for cid in ids:
        unidad = db.query(m.Unidad).filter(m.Unidad.poseedor_chofer_id == cid).first()
        if not unidad:
            continue
        vencidos = (db.query(m.ProgramaMantenimiento)
                    .filter(m.ProgramaMantenimiento.unidad_id == unidad.id,
                            m.ProgramaMantenimiento.estado == "pendiente",
                            m.ProgramaMantenimiento.fecha_limite < date.today()).all())
        pen = db.query(m.Penalizacion).filter(m.Penalizacion.chofer_id == cid,
                                              m.Penalizacion.estado == "aplicada").count()
        out.append({
            "chofer": svc.nombre_chofer(db, cid), "chofer_id": cid,
            "unidad": unidad.num_economico,
            "mantenimientos_vencidos": len(vencidos),
            "dias_atraso_max": max([(date.today() - v.fecha_limite).days for v in vencidos],
                                   default=0),
            "penalizaciones": pen,
        })
    return sorted(out, key=lambda x: -x["dias_atraso_max"])


@router.get("/tecnicos")
def tecnicos(usuario=Depends(solo_sup), db: Session = Depends(get_db)):
    return [{"id": t.id, "nombre": t.nombre_completo, "especialidad": t.especialidad,
             "telefono": t.telefono}
            for t in db.query(m.Tecnico).filter(m.Tecnico.activo.is_(True)).all()]
