"""Reglas de negocio y serializadores compartidos.

Aqui viven las restricciones que el diagrama ER no puede expresar (RI-01 a RI-13).
"""
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models as m


# ------------------------------------------------------------------ folios -- #
def siguiente_folio(db: Session, modelo, prefijo: str) -> str:
    n = db.query(func.count(modelo.id)).scalar() or 0
    return f"{prefijo}-{datetime.utcnow().year}-{n + 1:05d}"


# ------------------------------------------------------------ nombres ------- #
def nombre_chofer(db: Session, chofer_id):
    if not chofer_id:
        return None
    u = db.query(m.Usuario).filter(m.Usuario.id == chofer_id).first()
    return u.nombre_completo if u else None


def nombre_usuario(db: Session, usuario_id):
    if not usuario_id:
        return None
    u = db.query(m.Usuario).filter(m.Usuario.id == usuario_id).first()
    return u.nombre_completo if u else None


# ------------------------------------------------------- reglas de negocio -- #
def prestamo_activo(db: Session, unidad_id: int):
    """RI-01: una unidad no puede tener dos prestamos activos."""
    return (db.query(m.PrestamoUnidad)
            .filter(m.PrestamoUnidad.unidad_id == unidad_id,
                    m.PrestamoUnidad.estado.in_(["solicitado", "aceptado", "activo"]))
            .first())


def poseedor_actual(db: Session, unidad: m.Unidad):
    """RN-01: quien responde por la unidad hoy."""
    return unidad.poseedor_chofer_id or unidad.titular_chofer_id


def validar_puede_prestar(db: Session, unidad: m.Unidad, chofer_id: int,
                          chofer_recibe_id: int):
    if poseedor_actual(db, unidad) != chofer_id:
        raise HTTPException(403, "Solo el poseedor actual de la unidad puede prestarla (RN-01)")
    if chofer_id == chofer_recibe_id:
        raise HTTPException(400, "No puedes prestarte la unidad a ti mismo (RI-10)")
    if prestamo_activo(db, unidad.id):
        raise HTTPException(409, "Esta unidad ya tiene un prestamo en curso (RN-02)")
    if unidad.estado in ("en_taller", "en_reparacion", "en_arrastre", "baja"):
        raise HTTPException(409, f"No se puede prestar una unidad en estado '{unidad.estado}' (RN-02)")
    receptor = db.query(m.Chofer).filter(m.Chofer.usuario_id == chofer_recibe_id).first()
    if not receptor:
        raise HTTPException(404, "El chofer receptor no existe")
    if receptor.vencimiento_licencia and receptor.vencimiento_licencia < date.today():
        raise HTTPException(409, "El chofer receptor tiene la licencia vencida")
    return receptor


def espacios_libres_compatibles(db: Session, taller_id: int, tipo_unidad_id: int):
    """RN-06 / RI-04: un espacio solo admite el tipo de unidad para el que fue hecho."""
    return (db.query(m.Espacio)
            .join(m.ZonaTaller)
            .filter(m.ZonaTaller.taller_id == taller_id,
                    m.ZonaTaller.cuenta_para_ocupacion.is_(True),
                    m.Espacio.activo.is_(True),
                    m.Espacio.estado == "libre",
                    ((m.Espacio.tipo_unidad_permitido_id == tipo_unidad_id) |
                     (m.Espacio.tipo_unidad_permitido_id.is_(None))))
            .all())


def ocupacion_abierta_de_unidad(db: Session, unidad_id: int):
    return (db.query(m.OcupacionEspacio)
            .filter(m.OcupacionEspacio.unidad_id == unidad_id,
                    m.OcupacionEspacio.fecha_salida.is_(None))
            .first())


def ocupacion_abierta_de_espacio(db: Session, espacio_id: int):
    return (db.query(m.OcupacionEspacio)
            .filter(m.OcupacionEspacio.espacio_id == espacio_id,
                    m.OcupacionEspacio.fecha_salida.is_(None))
            .first())


def puede_solicitar_arrastre(reporte: m.ReporteAveria) -> bool:
    """RN-04: en vialidad publica, primero peritos."""
    if not reporte.en_vialidad_publica:
        return True
    return reporte.peritaje is not None and bool(reporte.peritaje.folio_peritos)


# ---------------------------------------------------------- serializadores -- #
def unidad_out(db: Session, u: m.Unidad) -> dict:
    prest = prestamo_activo(db, u.id)
    taller = db.query(m.Taller).filter(m.Taller.id == u.taller_actual_id).first() \
        if u.taller_actual_id else None
    return {
        "id": u.id, "num_economico": u.num_economico, "placas": u.placas,
        "marca": u.marca, "modelo": u.modelo, "anio": u.anio,
        "tipo": u.tipo.nombre if u.tipo else None,
        "estado": u.estado, "km_actual": u.km_actual,
        "titular": nombre_chofer(db, u.titular_chofer_id),
        "poseedor": nombre_chofer(db, poseedor_actual(db, u)),
        "es_prestada": bool(prest and prest.estado == "activo"),
        "taller_actual": taller.nombre if taller else None,
    }


def mantenimiento_out(p: m.ProgramaMantenimiento) -> dict:
    dias = (p.fecha_limite - date.today()).days
    return {
        "id": p.id, "plan": p.plan.nombre if p.plan else "-",
        "fecha_limite": p.fecha_limite, "km_programado": p.km_programado,
        "estado": p.estado, "dias_restantes": dias,
        "vencido": dias < 0 and p.estado != "cumplido",
    }


def prestamo_out(db: Session, p: m.PrestamoUnidad) -> dict:
    return {
        "id": p.id,
        "unidad": p.unidad.num_economico if p.unidad else "-",
        "chofer_presta": nombre_chofer(db, p.chofer_presta_id) or "-",
        "chofer_recibe": nombre_chofer(db, p.chofer_recibe_id) or "-",
        "motivo": p.motivo, "estado": p.estado,
        "fecha_solicitud": p.fecha_solicitud,
        "fecha_fin_prevista": p.fecha_fin_prevista,
        "fecha_fin_real": p.fecha_fin_real,
        "vencido": p.estado == "activo" and p.fecha_fin_prevista < date.today(),
    }


def solicitud_out(db: Session, s: m.SolicitudIngreso) -> dict:
    libres = 0
    if s.estado in ("pendiente", "en_cola"):
        libres = len(espacios_libres_compatibles(db, s.taller_id, s.unidad.tipo_unidad_id))
    return {
        "id": s.id, "unidad": s.unidad.num_economico if s.unidad else "-",
        "chofer": nombre_chofer(db, s.chofer_id) or "-",
        "taller": s.taller.nombre if s.taller else "-",
        "tipo": s.tipo, "descripcion_falla": s.descripcion_falla,
        "urgencia": s.urgencia, "estado": s.estado,
        "fecha_solicitud": s.fecha_solicitud, "motivo_rechazo": s.motivo_rechazo,
        "espacios_libres_compatibles": libres,
    }


def asignacion_out(db: Session, a: m.AsignacionTecnico) -> dict:
    return {
        "id": a.id,
        "tecnico": a.tecnico.nombre_completo if a.tecnico else "-",
        "especialidad": a.especialidad, "orden_en_cola": a.orden_en_cola,
        "estado": a.estado, "diagnostico": a.diagnostico,
        "trabajo_realizado": a.trabajo_realizado,
        "capturado_por": nombre_usuario(db, a.capturado_por_admin_id),
        "fecha_captura": a.fecha_captura,
    }


def orden_out(db: Session, o: m.OrdenServicio) -> dict:
    fin = o.fecha_salida or datetime.utcnow()
    ocup = ocupacion_abierta_de_unidad(db, o.unidad_id)
    espacio = None
    if ocup:
        e = ocup.espacio
        espacio = f"{e.zona.nombre} {e.numero}" if e else None
    return {
        "id": o.id, "folio": o.folio,
        "unidad": o.unidad.num_economico if o.unidad else "-",
        "taller": o.taller.nombre if o.taller else "-",
        "estado": o.estado, "tipo": o.tipo,
        "fecha_entrada": o.fecha_entrada, "fecha_salida": o.fecha_salida,
        "dias_en_taller": (fin - o.fecha_entrada).days if o.fecha_entrada else 0,
        "espacio": espacio,
        "asignaciones": [asignacion_out(db, a) for a in
                         sorted(o.asignaciones, key=lambda x: x.orden_en_cola)],
    }


def presupuesto_out(db: Session, p: m.Presupuesto) -> dict:
    return {
        "id": p.id, "folio": p.folio,
        "orden_folio": p.orden.folio if p.orden else "-",
        "unidad": p.orden.unidad.num_economico if p.orden and p.orden.unidad else "-",
        "tecnico_elaboro": p.tecnico.nombre_completo if p.tecnico else "-",
        "capturado_por": nombre_usuario(db, p.capturado_por_admin_id) or "-",
        "fecha_elaboracion": p.fecha_elaboracion, "fecha_captura": p.fecha_captura,
        "dias_retraso_captura": p.dias_retraso_captura,
        "costo_mano_obra": float(p.costo_mano_obra or 0),
        "subtotal_piezas": float(p.subtotal_piezas or 0),
        "total": float(p.total or 0), "estado": p.estado,
        "diagnostico": p.diagnostico,
        "fecha_aviso_al_tecnico": p.fecha_aviso_al_tecnico,
        "detalles": [{
            "id": d.id, "pieza": d.pieza.nombre if d.pieza else None,
            "descripcion_libre": d.descripcion_libre,
            "cantidad": float(d.cantidad or 0),
            "precio_unitario": float(d.precio_unitario or 0),
            "importe": float(d.importe or 0),
            "disponible_en_almacen": d.disponible_en_almacen,
        } for d in p.detalles],
        "autorizaciones": [{
            "id": a.id, "usuario": a.usuario.nombre_completo if a.usuario else "-",
            "nivel": a.nivel, "resultado": a.resultado, "fecha": a.fecha,
            "comentario": a.comentario,
        } for a in sorted(p.autorizaciones, key=lambda x: x.fecha)],
    }


def averia_out(db: Session, r: m.ReporteAveria) -> dict:
    return {
        "id": r.id, "folio": r.folio,
        "unidad": r.unidad.num_economico if r.unidad else "-",
        "chofer": nombre_chofer(db, r.chofer_id) or "-",
        "fecha_hora": r.fecha_hora, "latitud": r.latitud, "longitud": r.longitud,
        "descripcion_falla": r.descripcion_falla,
        "en_vialidad_publica": r.en_vialidad_publica, "estado": r.estado,
        "tiene_peritaje": r.peritaje is not None,
        "folio_peritos": r.peritaje.folio_peritos if r.peritaje else None,
        "puede_solicitar_arrastre": puede_solicitar_arrastre(r),
        "arrastre_id": r.arrastre.id if r.arrastre else None,
        "arrastre_estado": r.arrastre.estado if r.arrastre else None,
    }


def arrastre_out(db: Session, a: m.Arrastre) -> dict:
    ult = (db.query(m.UbicacionArrastre)
           .filter(m.UbicacionArrastre.arrastre_id == a.id)
           .order_by(m.UbicacionArrastre.capturado_en.desc()).first())
    return {
        "id": a.id, "folio": a.folio,
        "unidad": a.unidad.num_economico if a.unidad else "-",
        "chofer_responsable": nombre_chofer(db, a.chofer_responsable_id),
        "montacarguista": nombre_usuario(db, a.montacarguista_id),
        "taller_destino": a.taller_destino.nombre if a.taller_destino else None,
        "estado": a.estado, "fecha_solicitud": a.fecha_solicitud,
        "fecha_finalizacion": a.fecha_finalizacion,
        "latitud_origen": a.reporte.latitud if a.reporte else None,
        "longitud_origen": a.reporte.longitud if a.reporte else None,
        "ultima_lat": ult.latitud if ult else None,
        "ultima_lng": ult.longitud if ult else None,
        "ultima_actualizacion": ult.capturado_en if ult else None,
    }
