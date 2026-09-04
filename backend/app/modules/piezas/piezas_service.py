"""Presupuestos y almacen.

Servicio del paquete piezas: aqui viven las reglas de negocio y los
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
