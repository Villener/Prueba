"""Paquete D - Mantenimiento preventivo y agenda.

Corresponde a AvisoIncumplimiento, Penalizacion del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class AvisoIncumplimiento(Base, TimestampMixin):
    """Sustituye a PENALIZACION.

    El sistema NO sanciona: avisa al gerente y a Erick, ellos hablan con el
    chofer en persona y despues marcan el caso como atendido. Por eso no hay
    monto ni proceso de inconformidad.
    """
    __tablename__ = "aviso_incumplimiento"
    id = Column(Integer, primary_key=True)
    cita_id = Column(Integer, ForeignKey("cita_taller.id"), unique=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    # De donde salio que ESE chofer era el responsable ese dia.
    fundamento_poseedor = Column(String(16))     # jornada|prestamo|titularidad
    jornada_id = Column(Integer, ForeignKey("jornada.id"))
    prestamo_id = Column(Integer, ForeignKey("prestamo_unidad.id"))
    asignacion_id = Column(Integer, ForeignKey("asignacion_unidad.id"))
    fecha_generacion = Column(Date, nullable=False)
    dias_atraso = Column(Integer, default=0)
    estado = Column(String(12), default="abierto", nullable=False)  # abierto|atendido|anulado
    fecha_atencion = Column(UTCDateTime)
    atendido_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    nota_atencion = Column(Text)
    veces_recordado = Column(Integer, default=0, nullable=False)

    unidad = relationship("Unidad")
    chofer = relationship("Chofer")

class Penalizacion(Base, TimestampMixin):
    __tablename__ = "penalizacion"
    id = Column(Integer, primary_key=True)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)  # el POSEEDOR
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    programa_mantenimiento_id = Column(Integer, ForeignKey("programa_mantenimiento.id"),
                                       unique=True)
    motivo = Column(String(240), nullable=False)
    fecha_generacion = Column(Date, default=lambda: datetime.utcnow().date())
    dias_atraso = Column(Integer, default=0)
    estado = Column(String(20), default="aplicada", nullable=False)
    aplicada_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    resolucion_disputa = Column(Text)

    unidad = relationship("Unidad")
    programa = relationship("ProgramaMantenimiento")


# --------------------------------------------------------------------------- #
# AREA C - Taller e infraestructura
# --------------------------------------------------------------------------- #
