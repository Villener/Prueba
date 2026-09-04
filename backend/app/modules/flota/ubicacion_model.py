"""Paquete B - Flota y responsabilidad.

Corresponde a UbicacionUnidad del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class UbicacionUnidad(Base):
    __tablename__ = "ubicacion_unidad"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    capturado_en = Column(UTCDateTime, default=_now)
    fuente = Column(String(20), default="app_chofer")
