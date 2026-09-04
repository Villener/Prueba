"""Paquete C - Taller: zonas, espacios y ocupacion.

Corresponde a ZonaTaller, Espacio, OcupacionEspacio del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class ZonaTaller(Base):
    __tablename__ = "zona_taller"
    id = Column(Integer, primary_key=True)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    nombre = Column(String(60), nullable=False)
    proposito = Column(String(30), default="operativa")
    capacidad = Column(Integer, default=0)
    # DOS PREGUNTAS DISTINTAS, y confundirlas fue el defecto:
    #
    #   admite_unidades       -> cabe fisicamente una unidad aqui?
    #   cuenta_para_ocupacion -> cuenta como capacidad de REPARACION?
    #
    # El patio admite unidades -- ahi esperan turno -- pero no es capacidad de
    # atencion. El area de lavado igual. La oficina y el contenedor de basura no
    # admiten nada. Con una sola bandera el patio quedaba inutilizable: no se
    # podia estacionar una unidad en los lugares que existen en el plano.
    admite_unidades = Column(Boolean, default=True, nullable=False)
    cuenta_para_ocupacion = Column(Boolean, default=True, nullable=False)
    orden = Column(Integer, default=0)

    taller = relationship("Taller", back_populates="zonas")
    espacios = relationship("Espacio", back_populates="zona", cascade="all, delete-orphan")

class Espacio(Base):
    __tablename__ = "espacio"
    __table_args__ = (UniqueConstraint("zona_id", "numero", name="uq_espacio_zona_numero"),)
    id = Column(Integer, primary_key=True)
    zona_id = Column(Integer, ForeignKey("zona_taller.id"), nullable=False)
    numero = Column(String(10), nullable=False)  # se repite entre zonas: unico por (zona, numero)
    tipo_unidad_permitido_id = Column(Integer, ForeignKey("tipo_unidad.id"))
    estado = Column(String(20), default="libre", nullable=False)
    pos_x = Column(Integer, default=0)
    pos_y = Column(Integer, default=0)
    activo = Column(Boolean, default=True)

    zona = relationship("ZonaTaller", back_populates="espacios")
    tipo_permitido = relationship("TipoUnidad")

class OcupacionEspacio(Base):
    __tablename__ = "ocupacion_espacio"
    id = Column(Integer, primary_key=True)
    espacio_id = Column(Integer, ForeignKey("espacio.id"), nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"))
    fecha_entrada = Column(UTCDateTime, default=_now)
    fecha_salida = Column(UTCDateTime)
    colocado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    retirado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))

    espacio = relationship("Espacio")
    unidad = relationship("Unidad")
