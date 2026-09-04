"""Paquete G - Averias, auxilio en carretera y arrastre.

Corresponde a Evidencia del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Evidencia(Base):
    """Polimorfica: entidad_tipo + entidad_id (la FK la valida la aplicacion)."""
    __tablename__ = "evidencia"
    id = Column(Integer, primary_key=True)
    entidad_tipo = Column(String(40), nullable=False)
    entidad_id = Column(Integer, nullable=False)
    url_archivo = Column(String(400), nullable=False)
    descripcion = Column(String(240))
    momento = Column(String(30))
    subida_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha = Column(UTCDateTime, default=_now)


# --------------------------------------------------------------------------- #
# AREA F - Transversales
# --------------------------------------------------------------------------- #
