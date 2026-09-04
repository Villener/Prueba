"""Paquete E - Orden de servicio y traslados.

Corresponde a TrasladoUnidad del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class TrasladoUnidad(Base, TimestampMixin):
    """La satelite no pudo repararla: se manda al central (Alamos) con grua."""
    __tablename__ = "traslado_unidad"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    taller_origen_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    taller_destino_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    orden_servicio_origen_id = Column(Integer, ForeignKey("orden_servicio.id"))
    orden_servicio_destino_id = Column(Integer, ForeignKey("orden_servicio.id"))
    solicitado_por_tecnico_id = Column(Integer, ForeignKey("tecnico.id"))
    motivo = Column(Text, nullable=False)
    requiere_grua = Column(Boolean, default=True, nullable=False)
    arrastre_id = Column(Integer, ForeignKey("arrastre.id"))
    estado = Column(String(16), default="solicitado", nullable=False)
    fecha_solicitud = Column(UTCDateTime, default=_now, nullable=False)
    autorizado_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_autorizacion = Column(UTCDateTime)
    motivo_rechazo = Column(Text)
    fecha_salida = Column(UTCDateTime)
    fecha_llegada = Column(UTCDateTime)

    unidad = relationship("Unidad")
    taller_origen = relationship("Taller", foreign_keys=[taller_origen_id])
    taller_destino = relationship("Taller", foreign_keys=[taller_destino_id])
