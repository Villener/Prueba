"""Paquete G - Averias, auxilio en carretera y arrastre.

Corresponde a OrdenAuxilio, ESTADOS_AUXILIO, DifusionAuxilio, RespuestaAuxilio del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class OrdenAuxilio(Base, TimestampMixin):
    """Auxilio en carretera con patron DIFUSION Y TOMA.

    La orden se manda a TODOS los mecanicos autonomos disponibles y el primero
    que acepta la gana. La toma se hace con un UPDATE condicional sobre
    `estado`, nunca leyendo y luego escribiendo (dos podrian aceptar a la vez).
    """
    __tablename__ = "orden_auxilio"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True)
    reporte_averia_id = Column(Integer, ForeignKey("reporte_averia.id"), unique=True)
    fecha_emision = Column(UTCDateTime, default=_now, nullable=False)
    estado = Column(String(24), default="difundida", nullable=False)
    tecnico_acepta_id = Column(Integer, ForeignKey("tecnico.id"))
    fecha_aceptacion = Column(UTCDateTime)
    fecha_llegada = Column(UTCDateTime)
    fecha_cierre = Column(UTCDateTime)
    resuelto_en_sitio = Column(Boolean)
    arrastre_id = Column(Integer, ForeignKey("arrastre.id"))

    tecnico = relationship("Tecnico")

ESTADOS_AUXILIO = ["difundida", "aceptada", "en_ruta", "en_sitio", "resuelta",
                   "escalada_a_arrastre", "cancelada"]

class DifusionAuxilio(Base):
    """A quien se le mando la orden y a que distancia estaba.

    Sin esta tabla no se puede demostrar que al mecanico se le aviso.
    """
    __tablename__ = "difusion_auxilio"
    id = Column(Integer, primary_key=True)
    orden_auxilio_id = Column(Integer, ForeignKey("orden_auxilio.id"), nullable=False)
    tecnico_id = Column(Integer, ForeignKey("tecnico.id"), nullable=False)
    notificado_en = Column(UTCDateTime, default=_now, nullable=False)
    distancia_km_estimada = Column(Float)

    __table_args__ = (UniqueConstraint("orden_auxilio_id", "tecnico_id",
                                       name="uq_difusion_orden_tecnico"),)

class RespuestaAuxilio(Base):
    """Guarda TAMBIEN las negativas, con su motivo.

    Si nadie responde en 20 minutos hay que poder distinguir "todos ocupados"
    de "la unidad esta lejos de todos" y de "nadie abrio la app".
    """
    __tablename__ = "respuesta_auxilio"
    id = Column(Integer, primary_key=True)
    orden_auxilio_id = Column(Integer, ForeignKey("orden_auxilio.id"), nullable=False)
    tecnico_id = Column(Integer, ForeignKey("tecnico.id"), nullable=False)
    puede_atender = Column(Boolean, nullable=False)
    motivo_negativa = Column(String(160))
    fecha = Column(UTCDateTime, default=_now, nullable=False)

    tecnico = relationship("Tecnico")

    __table_args__ = (UniqueConstraint("orden_auxilio_id", "tecnico_id",
                                       name="uq_respuesta_orden_tecnico"),)
