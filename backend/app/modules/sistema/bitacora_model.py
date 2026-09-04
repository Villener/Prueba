"""Paquete H - Transversales: avisos, bitacora y configuracion.

Corresponde a BitacoraAuditoria del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class BitacoraAuditoria(Base):
    __tablename__ = "bitacora_auditoria"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"))
    accion = Column(String(80), nullable=False)
    entidad_tipo = Column(String(40))
    entidad_id = Column(Integer)
    datos_antes = Column(Text)
    datos_despues = Column(Text)
    fecha = Column(UTCDateTime, default=_now)
    ip_origen = Column(String(60))
