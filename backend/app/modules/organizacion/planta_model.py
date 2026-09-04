"""Paquete A - Organizacion, plantas y personas.

Corresponde a Planta, Taller del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


# --------------------------------------------------------------------------- #
# AREA C - Taller e infraestructura
# --------------------------------------------------------------------------- #
class Planta(Base, TimestampMixin):
    """Las sedes de Baja Gas. El taller toma el nombre de su planta."""
    __tablename__ = "planta"
    id = Column(Integer, primary_key=True)
    clave = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(80), nullable=False)
    direccion = Column(String(240))
    latitud = Column(Float)
    longitud = Column(Float)
    es_central = Column(Boolean, default=False, nullable=False)  # solo ALAMOS
    tiene_taller = Column(Boolean, default=True, nullable=False)  # LIBERTAD no
    activo = Column(Boolean, default=True, nullable=False)

    taller = relationship("Taller", back_populates="planta", uselist=False)

class Taller(Base, TimestampMixin):
    __tablename__ = "taller"
    id = Column(Integer, primary_key=True)
    # 1:1 con la planta: el taller se llama como ella.
    planta_id = Column(Integer, ForeignKey("planta.id"), unique=True)
    nombre = Column(String(120), unique=True, nullable=False)
    tipo = Column(String(10), default="SATELITE", nullable=False)  # CENTRAL|SATELITE
    direccion = Column(String(240))
    latitud = Column(Float)
    longitud = Column(Float)
    opera_sabado = Column(Boolean, default=True, nullable=False)
    activo = Column(Boolean, default=True)

    planta = relationship("Planta", back_populates="taller")

    zonas = relationship("ZonaTaller", back_populates="taller", cascade="all, delete-orphan")
    tecnicos = relationship("Tecnico", back_populates="taller")
