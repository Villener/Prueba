"""Modulo Montacarguista - CU-MON-01 a CU-MON-07."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models as m
from .. import services as svc
from ..database import get_db
from ..schemas import ArrastreOut, AveriaOut, CierreArrastreIn, MensajeOut, UbicacionIn
from ..security import notificar, registrar_bitacora, require_roles

router = APIRouter(prefix="/api/montacarguista", tags=["montacarguista"])
solo_mon = require_roles("montacarguista")


# ---------------------------------------------------------------- CU-MON-01 -- #
@router.get("/alertas", response_model=list[AveriaOut])
def alertas(usuario=Depends(solo_mon), db: Session = Depends(get_db)):
    """Unidades varadas con ubicacion. Las de vialidad publica sin peritaje se
    muestran pero con puede_solicitar_arrastre=false (RN-04)."""
    rs = (db.query(m.ReporteAveria)
          .filter(m.ReporteAveria.estado.in_(["abierto", "esperando_peritos", "en_atencion"]))
          .order_by(m.ReporteAveria.fecha_hora.desc()).all())
    return [svc.averia_out(db, r) for r in rs]


# ---------------------------------------------------------------- CU-MON-02 -- #
@router.post("/arrastres/{arrastre_id}/aceptar", response_model=ArrastreOut)
def aceptar_arrastre(arrastre_id: int, usuario=Depends(solo_mon), db: Session = Depends(get_db)):
    a = db.query(m.Arrastre).filter(m.Arrastre.id == arrastre_id).first()
    if not a:
        raise HTTPException(404, "Arrastre no encontrado")
    if a.estado != "solicitado":
        raise HTTPException(409, f"El arrastre esta en estado '{a.estado}'")
    if not svc.puede_solicitar_arrastre(a.reporte):
        raise HTTPException(409, "RN-04: falta el folio de peritos")
    a.montacarguista_id = usuario.id
    a.estado = "aceptado"
    a.fecha_aceptacion = datetime.utcnow()
    a.unidad.estado = "en_arrastre"
    mo = db.query(m.Montacarguista).filter(m.Montacarguista.usuario_id == usuario.id).first()
    if mo and mo.unidad_grua_id:
        a.unidad_grua_id = mo.unidad_grua_id
    notificar(db, a.chofer_responsable_id, "Arrastre aceptado",
              f"{usuario.nombre_completo} viene en camino. Ya puedes seguirlo en el mapa.",
              "arrastre", "arrastre", a.id)
    registrar_bitacora(db, usuario.id, "arrastre_aceptado", "arrastre", a.id)
    db.commit()
    db.refresh(a)
    return svc.arrastre_out(db, a)


@router.post("/arrastres/{arrastre_id}/rechazar", response_model=MensajeOut)
def rechazar_arrastre(arrastre_id: int, motivo: str = "", usuario=Depends(solo_mon),
                      db: Session = Depends(get_db)):
    a = db.query(m.Arrastre).filter(m.Arrastre.id == arrastre_id).first()
    if not a or a.estado != "solicitado":
        raise HTTPException(404, "Arrastre no disponible")
    a.estado = "rechazado"
    a.motivo_rechazo = motivo
    notificar(db, a.chofer_responsable_id, "Arrastre rechazado", motivo, "arrastre")
    db.commit()
    return {"mensaje": "Arrastre rechazado"}


# ---------------------------------------------------------------- CU-MON-03 -- #
@router.post("/arrastres/{arrastre_id}/ubicacion", response_model=MensajeOut)
def transmitir_ubicacion(arrastre_id: int, datos: UbicacionIn, usuario=Depends(solo_mon),
                         db: Session = Depends(get_db)):
    a = db.query(m.Arrastre).filter(m.Arrastre.id == arrastre_id).first()
    if not a or a.montacarguista_id != usuario.id:
        raise HTTPException(404, "Arrastre no encontrado")
    if a.estado not in ("aceptado", "en_ruta", "en_traslado"):
        raise HTTPException(409, "El arrastre no esta activo")
    db.add(m.UbicacionArrastre(arrastre_id=a.id, latitud=datos.latitud,
                               longitud=datos.longitud, emisor="montacarguista"))
    if a.estado == "aceptado":
        a.estado = "en_ruta"
    db.commit()
    return {"mensaje": "Ubicacion transmitida"}


# ---------------------------------------------------------------- CU-MON-04 -- #
@router.post("/arrastres/{arrastre_id}/llegada", response_model=ArrastreOut)
def registrar_llegada(arrastre_id: int, usuario=Depends(solo_mon),
                      db: Session = Depends(get_db)):
    a = db.query(m.Arrastre).filter(m.Arrastre.id == arrastre_id).first()
    if not a or a.montacarguista_id != usuario.id:
        raise HTTPException(404, "Arrastre no encontrado")
    a.fecha_llegada_sitio = datetime.utcnow()
    a.estado = "en_traslado"
    notificar(db, a.chofer_responsable_id, "El montacargas llego",
              "Ya esta en tu ubicacion", "arrastre", "arrastre", a.id)
    db.commit()
    db.refresh(a)
    return svc.arrastre_out(db, a)


# ------------------------------------------------------------- CU-MON-05/06 -- #
@router.post("/arrastres/{arrastre_id}/cerrar", response_model=ArrastreOut)
def cerrar_arrastre(arrastre_id: int, datos: CierreArrastreIn, usuario=Depends(solo_mon),
                    db: Session = Depends(get_db)):
    """CU-MON-05: deja registro de taller destino, unidad, chofer responsable y hora."""
    a = db.query(m.Arrastre).filter(m.Arrastre.id == arrastre_id).first()
    if not a or a.montacarguista_id != usuario.id:
        raise HTTPException(404, "Arrastre no encontrado")
    if a.estado == "finalizado":
        raise HTTPException(409, "El arrastre ya esta cerrado")
    taller = db.query(m.Taller).filter(m.Taller.id == datos.taller_destino_id).first()
    if not taller:
        raise HTTPException(404, "Taller destino no encontrado")

    a.taller_destino_id = taller.id
    a.estado = "finalizado"
    a.fecha_finalizacion = datetime.utcnow()
    a.km_recorridos = datos.km_recorridos
    a.unidad.estado = "en_taller"
    a.unidad.taller_actual_id = taller.id
    a.reporte.estado = "resuelto"

    # El arrastre genera automaticamente la solicitud de ingreso al taller destino.
    s = m.SolicitudIngreso(unidad_id=a.unidad_arrastrada_id, chofer_id=a.chofer_responsable_id,
                           taller_id=taller.id, tipo="siniestro",
                           descripcion_falla=f"Ingreso por arrastre {a.folio}. "
                                             f"{a.reporte.descripcion_falla or ''}",
                           urgencia="alta", estado="pendiente")
    db.add(s)
    db.flush()
    for admin in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
            m.Rol.nombre == "administrador").all():
        notificar(db, admin.id, "Unidad llego por arrastre",
                  f"{a.unidad.num_economico} en {taller.nombre}. Responsable: "
                  f"{svc.nombre_chofer(db, a.chofer_responsable_id)}",
                  "arrastre", "solicitud_ingreso", s.id)
    notificar(db, a.chofer_responsable_id, "Arrastre finalizado",
              f"Tu unidad quedo en {taller.nombre}", "arrastre", "arrastre", a.id)
    registrar_bitacora(db, usuario.id, "arrastre_cerrado", "arrastre", a.id,
                       f"taller={taller.nombre} unidad={a.unidad.num_economico} "
                       f"responsable={a.chofer_responsable_id}")
    if datos.observaciones:
        db.add(m.Evidencia(entidad_tipo="arrastre", entidad_id=a.id, url_archivo="",
                           descripcion=datos.observaciones, momento="entrega",
                           subida_por_usuario_id=usuario.id))
    db.commit()
    db.refresh(a)
    return svc.arrastre_out(db, a)


# ---------------------------------------------------------------- CU-MON-07 -- #
@router.get("/arrastres", response_model=list[ArrastreOut])
def mis_arrastres(historial: bool = False, usuario=Depends(solo_mon),
                  db: Session = Depends(get_db)):
    q = db.query(m.Arrastre)
    if historial:
        q = q.filter(m.Arrastre.montacarguista_id == usuario.id)
    else:
        q = q.filter((m.Arrastre.estado == "solicitado") |
                     ((m.Arrastre.montacarguista_id == usuario.id) &
                      (m.Arrastre.estado.notin_(["finalizado", "rechazado"]))))
    return [svc.arrastre_out(db, a) for a in
            q.order_by(m.Arrastre.fecha_solicitud.desc()).all()]


@router.get("/talleres")
def talleres(usuario=Depends(solo_mon), db: Session = Depends(get_db)):
    return [{"id": t.id, "nombre": t.nombre, "direccion": t.direccion}
            for t in db.query(m.Taller).filter(m.Taller.activo.is_(True)).all()]
