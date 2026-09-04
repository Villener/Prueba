"""Paquete G - Averias, auxilio en carretera y arrastre.

Corresponde a Arrastre, UbicacionArrastre del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Arrastre(Base, TimestampMixin):
    __tablename__ = "arrastre"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    reporte_averia_id = Column(Integer, ForeignKey("reporte_averia.id"), nullable=False)
    montacarguista_id = Column(Integer, ForeignKey("montacarguista.usuario_id"))
    unidad_arrastrada_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    unidad_grua_id = Column(Integer, ForeignKey("unidad.id"))
    chofer_responsable_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    taller_destino_id = Column(Integer, ForeignKey("taller.id"))
    estado = Column(String(20), default="solicitado", nullable=False)
    fecha_solicitud = Column(UTCDateTime, default=_now)
    fecha_aceptacion = Column(UTCDateTime)
    fecha_llegada_sitio = Column(UTCDateTime)
    fecha_finalizacion = Column(UTCDateTime)
    motivo_rechazo = Column(String(240))
    km_recorridos = Column(Float)

    reporte = relationship("ReporteAveria", back_populates="arrastre")
    unidad = relationship("Unidad", foreign_keys=[unidad_arrastrada_id])
    taller_destino = relationship("Taller")

class UbicacionArrastre(Base):
    __tablename__ = "ubicacion_arrastre"
    id = Column(Integer, primary_key=True)
    arrastre_id = Column(Integer, ForeignKey("arrastre.id"), nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    capturado_en = Column(UTCDateTime, default=_now)
    emisor = Column(String(20), default="montacarguista")
