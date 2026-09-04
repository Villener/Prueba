"""Responsabilidad de la unidad y prestamos.

Servicio del paquete flota: aqui viven las reglas de negocio y los
serializadores de este dominio. No sabe de HTTP (eso es del _controller) ni
define tablas (eso es del _model).
"""
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import ahora_utc
from ..sistema.comun_service import nombre_chofer, nombre_usuario, siguiente_folio  # noqa: F401


# ------------------------------------------------------- reglas de negocio -- #
def prestamo_activo(db: Session, unidad_id: int):
    """RI-01: una unidad no puede tener dos prestamos activos."""
    return (db.query(m.PrestamoUnidad)
            .filter(m.PrestamoUnidad.unidad_id == unidad_id,
                    m.PrestamoUnidad.estado.in_(["solicitado", "aceptado", "activo"]))
            .first())

def poseedor_actual(db: Session, unidad: m.Unidad):
    """RN-01: quien responde por la unidad HOY. Se DERIVA, no se lee.

    Orden de prelacion (docs/modelo-clases.md §3.2):
        1. jornada abierta   -> quien la esta conduciendo en este momento
        2. prestamo activo   -> quien la recibio
        3. titularidad       -> el titular

    La jornada gana sobre el prestamo a proposito: si el titular presto la
    unidad pero hoy la maneja el, el responsable de hoy es el. El prestamo fija
    la responsabilidad de base; la jornada fija la del momento.

    `Unidad.poseedor_chofer_id` NO es la fuente de verdad: es un cache que
    `sincronizar_poseedor()` mantiene para poder filtrar en SQL. Si alguna vez
    los dos discrepan, manda esta funcion.
    """
    j = (db.query(m.Jornada)
         .filter(m.Jornada.unidad_id == unidad.id, m.Jornada.hora_fin.is_(None))
         .order_by(m.Jornada.hora_inicio.desc()).first())
    if j:
        return j.chofer_id

    # OJO: solo un prestamo ACEPTADO transfiere la responsabilidad. Uno apenas
    # "solicitado" no mueve nada: mientras el receptor no acepte, responde el
    # que presto. Por eso no se reusa prestamo_activo(), que a proposito
    # incluye "solicitado" para impedir prestar dos veces la misma unidad.
    p = (db.query(m.PrestamoUnidad)
         .filter(m.PrestamoUnidad.unidad_id == unidad.id,
                 m.PrestamoUnidad.estado.in_(["aceptado", "activo"]),
                 m.PrestamoUnidad.fecha_fin_real.is_(None))
         .order_by(m.PrestamoUnidad.fecha_aceptacion.desc()).first())
    if p:
        return p.chofer_recibe_id

    return unidad.titular_chofer_id

def sincronizar_poseedor(db: Session, unidad: m.Unidad):
    """Recalcula el cache `poseedor_chofer_id` desde la derivacion real.

    Se llama despues de abrir/cerrar jornada y de aceptar/cerrar prestamo. Sin
    esto el cache se desincroniza y el aviso de incumplimiento le llegaria a la
    persona equivocada, que es justo el dato que no se puede tener mal.
    """
    real = poseedor_actual(db, unidad)
    if unidad.poseedor_chofer_id != real:
        unidad.poseedor_chofer_id = real
    return real

def validar_puede_prestar(db: Session, unidad: m.Unidad, chofer_id: int,
                          chofer_recibe_id: int):
    if poseedor_actual(db, unidad) != chofer_id:
        raise HTTPException(403, "Solo el poseedor actual de la unidad puede prestarla (RN-01)")
    if chofer_id == chofer_recibe_id:
        raise HTTPException(400, "No puedes prestarte la unidad a ti mismo (RI-10)")
    if prestamo_activo(db, unidad.id):
        raise HTTPException(409, "Esta unidad ya tiene un prestamo en curso (RN-02)")

    # RI-B-10. Faltaba `varada`, y era el caso mas facil de provocar: el chofer
    # reporta la averia --que deja la unidad en `varada`-- y mientras espera la
    # grua se la presta a otro. El receptor se llevaba la responsabilidad de una
    # unidad tirada en la carretera que no provoco ni puede resolver.
    BLOQUEADOS = ("varada", "en_taller", "en_reparacion", "en_arrastre",
                  "en_traslado", "baja")
    if unidad.estado in BLOQUEADOS:
        raise HTTPException(409, f"No se puede prestar una unidad en estado "
                                 f"'{unidad.estado}' (RI-B-10)")

    # Cinturon y tirantes: el estado es un campo que alguien pudo dejar viejo;
    # el reporte abierto es un hecho. Si hay una averia sin cerrar la unidad no
    # se presta aunque su estado diga otra cosa.
    averia = (db.query(m.ReporteAveria)
              .filter(m.ReporteAveria.unidad_id == unidad.id,
                      m.ReporteAveria.estado.notin_(("resuelto", "cancelado")))
              .first())
    if averia:
        raise HTTPException(409, f"La unidad tiene la averia {averia.folio} sin cerrar. "
                                 "Primero se atiende, luego se presta (RI-B-10)")

    receptor = db.query(m.Chofer).filter(m.Chofer.usuario_id == chofer_recibe_id).first()
    if not receptor:
        raise HTTPException(404, "El chofer receptor no existe")
    if receptor.vencimiento_licencia and receptor.vencimiento_licencia < date.today():
        raise HTTPException(409, "El chofer receptor tiene la licencia vencida")

    # Un chofer trae UNA unidad. Sin esto el receptor las acumulaba: su pantalla
    # mostraba una de las dos al azar y el que presto quedaba sin ninguna.
    # Se mide con poseedor_actual(), no con el cache.
    ya_trae = [u for u in db.query(m.Unidad).filter(
        m.Unidad.poseedor_chofer_id == chofer_recibe_id).all()
        if u.id != unidad.id and poseedor_actual(db, u) == chofer_recibe_id]
    if ya_trae:
        raise HTTPException(409, f"El receptor ya responde por {ya_trae[0].num_economico}. "
                                 "Un chofer trae una unidad a la vez.")
    return receptor

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
