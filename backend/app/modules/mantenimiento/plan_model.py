"""Paquete D - Mantenimiento preventivo y agenda.

Corresponde a PlanMantenimiento, ProgramaMantenimiento del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class PlanMantenimiento(Base):
    __tablename__ = "plan_mantenimiento"
    id = Column(Integer, primary_key=True)
    tipo_unidad_id = Column(Integer, ForeignKey("tipo_unidad.id"))
    nombre = Column(String(120), nullable=False)
    # Que servicio se hace al cumplirse el plan. De aqui la agenda saca la
    # duracion y la criticidad con las que ordena la cola; sin esto no puede
    # calcular nada (modelo-er.md: TIPO_SERVICIO ||--o{ PLAN_MANTENIMIENTO).
    tipo_servicio_id = Column(Integer, ForeignKey("tipo_servicio.id"))
    periodicidad_dias = Column(Integer)
    periodicidad_km = Column(Integer)
    descripcion = Column(Text)
    activo = Column(Boolean, default=True)

    tipo_servicio = relationship("TipoServicio")

class ProgramaMantenimiento(Base, TimestampMixin):
    __tablename__ = "programa_mantenimiento"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plan_mantenimiento.id"), nullable=False)
    fecha_programada = Column(Date)
    km_programado = Column(Integer)
    fecha_limite = Column(Date, nullable=False)
    estado = Column(String(20), default="pendiente", nullable=False)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"))
    fecha_cumplimiento = Column(UTCDateTime)

    unidad = relationship("Unidad")
    plan = relationship("PlanMantenimiento")
