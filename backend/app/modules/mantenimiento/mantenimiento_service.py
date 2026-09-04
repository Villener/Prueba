"""Programa de mantenimiento.

Servicio del paquete mantenimiento: aqui viven las reglas de negocio y los
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


def mantenimiento_out(p: m.ProgramaMantenimiento) -> dict:
    dias = (p.fecha_limite - date.today()).days
    return {
        "id": p.id, "plan": p.plan.nombre if p.plan else "-",
        "fecha_limite": p.fecha_limite, "km_programado": p.km_programado,
        "estado": p.estado, "dias_restantes": dias,
        "vencido": dias < 0 and p.estado != "cumplido",
    }
