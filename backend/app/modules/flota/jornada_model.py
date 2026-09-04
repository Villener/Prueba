"""Paquete B - Flota y responsabilidad.

Corresponde a Jornada del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Jornada(Base):
    __tablename__ = "jornada"
    id = Column(Integer, primary_key=True)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    hora_inicio = Column(UTCDateTime, default=_now)
    hora_fin = Column(UTCDateTime)
    km_inicio = Column(Integer)
    km_fin = Column(Integer)
    checklist_ok = Column(Boolean, default=False)
    checklist_notas = Column(Text)

    unidad = relationship("Unidad")
