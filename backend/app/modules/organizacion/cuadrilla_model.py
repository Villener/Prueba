"""Paquete A - Organizacion, plantas y personas.

Corresponde a Cuadrilla del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Cuadrilla(Base, TimestampMixin):
    __tablename__ = "cuadrilla"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False)
    supervisor_id = Column(Integer, ForeignKey("supervisor.usuario_id"))
    activa = Column(Boolean, default=True)

    supervisor = relationship("Supervisor", back_populates="cuadrillas")
    choferes = relationship("Chofer", back_populates="cuadrilla")
