"""Paquete E - Orden de servicio y traslados.

Corresponde a SolicitudIngreso del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class SolicitudIngreso(Base, TimestampMixin):
    __tablename__ = "solicitud_ingreso"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    tipo = Column(String(20), default="correctivo")
    descripcion_falla = Column(Text)
    urgencia = Column(String(12), default="media")
    fecha_solicitud = Column(UTCDateTime, default=_now)
    estado = Column(String(20), default="pendiente", nullable=False)
    atendida_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_respuesta = Column(UTCDateTime)
    motivo_rechazo = Column(String(240))
    fecha_ingreso_programada = Column(Date)

    unidad = relationship("Unidad")
    taller = relationship("Taller")
