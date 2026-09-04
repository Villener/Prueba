"""Paquete B - Flota y responsabilidad.

Corresponde a PrestamoUnidad del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class PrestamoUnidad(Base, TimestampMixin):
    """Relacion reflexiva sobre CHOFER con atributos propios."""
    __tablename__ = "prestamo_unidad"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_presta_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    chofer_recibe_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    motivo = Column(String(30), nullable=False)  # vacaciones|incapacidad|apoyo|otro
    fecha_solicitud = Column(UTCDateTime, default=_now)
    fecha_aceptacion = Column(UTCDateTime)
    fecha_inicio = Column(UTCDateTime)
    fecha_fin_prevista = Column(Date, nullable=False)
    fecha_fin_real = Column(UTCDateTime)
    estado = Column(String(20), default="solicitado", nullable=False)
    autorizado_por_supervisor_id = Column(Integer, ForeignKey("supervisor.usuario_id"))
    motivo_rechazo = Column(String(200))

    unidad = relationship("Unidad")
    presta = relationship("Chofer", foreign_keys=[chofer_presta_id])
    recibe = relationship("Chofer", foreign_keys=[chofer_recibe_id])
