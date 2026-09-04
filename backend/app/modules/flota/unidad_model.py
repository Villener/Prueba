"""Paquete B - Flota y responsabilidad.

Corresponde a TipoUnidad, Unidad, ESTADOS_UNIDAD, AsignacionUnidad del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


# --------------------------------------------------------------------------- #
# AREA B - Flota y responsabilidad
# --------------------------------------------------------------------------- #
class TipoUnidad(Base):
    __tablename__ = "tipo_unidad"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(40), unique=True, nullable=False)
    descripcion = Column(String(200))
    # Desempate #4 de la cola de la agenda: una pipa parada cuesta mas que un
    # utilitario parado. Menor numero = entra antes. Propuesto por
    # agenda-mantenimiento.md §4.3 y PENDIENTE de confirmar con el gerente.
    prioridad_operativa = Column(Integer, default=5, nullable=False)

class Unidad(Base, TimestampMixin):
    __tablename__ = "unidad"
    id = Column(Integer, primary_key=True)
    num_economico = Column(String(20), unique=True, nullable=False)
    placas = Column(String(20), unique=True)
    vin = Column(String(40), unique=True)
    marca = Column(String(60))
    modelo = Column(String(60))
    anio = Column(Integer)
    tipo_unidad_id = Column(Integer, ForeignKey("tipo_unidad.id"), nullable=False)
    titular_chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    poseedor_chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))  # RN-01
    estado = Column(String(24), default="disponible", nullable=False)
    km_actual = Column(Integer, default=0)
    taller_actual_id = Column(Integer, ForeignKey("taller.id"))
    # v2.0: a que taller va PRIMERO si se vara. Si ahi no la pueden reparar,
    # se traslada al central (Alamos). No es lo mismo que taller_actual_id,
    # que dice donde esta AHORA.
    taller_asignado_id = Column(Integer, ForeignKey("taller.id"))
    activo = Column(Boolean, default=True, nullable=False)
    fecha_baja = Column(Date)
    fecha_alta = Column(Date)

    tipo = relationship("TipoUnidad")
    titular = relationship("Chofer", foreign_keys=[titular_chofer_id])
    poseedor = relationship("Chofer", foreign_keys=[poseedor_chofer_id])
    taller_asignado = relationship("Taller", foreign_keys=[taller_asignado_id])
    taller_actual = relationship("Taller", foreign_keys=[taller_actual_id])

ESTADOS_UNIDAD = ["disponible", "en_ruta", "varada", "en_arrastre", "en_taller",
                  "en_reparacion", "lista", "baja"]

class AsignacionUnidad(Base):
    __tablename__ = "asignacion_unidad"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    fecha_inicio = Column(UTCDateTime, default=_now)
    fecha_fin = Column(UTCDateTime)
    asignado_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    motivo = Column(String(200))
