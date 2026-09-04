"""Paquete A - Organizacion, plantas y personas.

Corresponde a Tecnico del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Tecnico(Base, TimestampMixin):
    """Catalogo de personal tecnico.

    v2.0: hay DOS modalidades y la diferencia es quien captura su trabajo.
      ASISTIDO  (Alamos)    -> no usa la app; Erick captura lo suyo en papel.
      AUTONOMO  (satelites) -> esta solo en su planta, SI usa la app, tiene
                               vehiculo de servicio y atiende unidades varadas.
    Por eso `usuario_id` es opcional: los autonomos tienen cuenta, los
    asistidos NO deben tenerla (RI-A-18).
    """
    __tablename__ = "tecnico"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False)
    apellidos = Column(String(120), nullable=False)
    num_empleado = Column(String(30), unique=True)
    especialidad = Column(String(30), nullable=False)  # mecanico|carrocero|electricista|llantero
    taller_id = Column(Integer, ForeignKey("taller.id"))
    modalidad = Column(String(12), default="ASISTIDO", nullable=False)  # AUTONOMO|ASISTIDO
    # Solo el autonomo trae vehiculo propio para salir a auxiliar.
    unidad_servicio_id = Column(Integer, ForeignKey("unidad.id"))
    puesto = Column(String(60))
    telefono = Column(String(30))
    disponible = Column(Boolean, default=True)
    activo = Column(Boolean, default=True)
    # FK opcional: los AUTONOMO la tienen, los ASISTIDO deben tenerla en NULL.
    usuario_id = Column(Integer, ForeignKey("usuario.id"), unique=True, nullable=True)

    taller = relationship("Taller", back_populates="tecnicos")

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"


# --------------------------------------------------------------------------- #
# AREA B - Flota y responsabilidad
# --------------------------------------------------------------------------- #
