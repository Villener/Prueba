"""Averias, peritaje y arrastre.

Servicio del paquete emergencias: aqui viven las reglas de negocio y los
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


def puede_solicitar_arrastre(reporte: m.ReporteAveria) -> bool:
    """RN-04: en vialidad publica, primero peritos."""
    if not reporte.en_vialidad_publica:
        return True
    return reporte.peritaje is not None and bool(reporte.peritaje.folio_peritos)


# ---------------------------------------------------------- serializadores -- #

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
