"""Paquete F - Piezas, almacen y compras.

Corresponde a Pieza, Existencia del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


# --------------------------------------------------------------------------- #
# AREA D - Presupuestos, piezas y compras
# --------------------------------------------------------------------------- #
class Pieza(Base):
    __tablename__ = "pieza"
    id = Column(Integer, primary_key=True)
    sku = Column(String(40), unique=True, nullable=False)
    # El codigo de material de SAP, cuando se pudo casar. Es el ANCLA para el
    # dia que se conecte SAP: sin el, el casado seria por nombre normalizado y
    # fallaria en un porcentaje real de los casos (contexto-del-proyecto-2 §3).
    # NO es unico a proposito: dos renglones del catalogo pueden apuntar al
    # mismo material, y forzar unicidad tumbaria la importacion.
    codigo_externo = Column(String(40), index=True)
    # De donde salio ese codigo: 'sap' cuando caso contra CODIGOS TALLER, o
    # 'nombre' cuando venia pegado a la descripcion. Sin esto no hay forma de
    # auditar un codigo dudoso ni de saber cual confiar el dia que llegue SAP.
    origen_codigo = Column(String(16))
    nombre = Column(String(160), nullable=False)
    descripcion = Column(Text)
    unidad_medida = Column(String(20), default="pieza")
    precio_referencia = Column(Numeric(12, 2), default=0)
    stock_actual = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=0)
    activa = Column(Boolean, default=True)

class Existencia(Base, TimestampMixin):
    """Stock por almacen y pieza.

    Es tabla asociativa y no columnas dentro de PIEZA: hoy solo hay un almacen
    (Alamos) pero el dia que Guaycura guarde sus propios filtros, el modelo ya
    lo soporta sin rehacer el modulo.
    """
    __tablename__ = "existencia"
    id = Column(Integer, primary_key=True)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)  # almacen de la planta
    pieza_id = Column(Integer, ForeignKey("pieza.id"), nullable=False)
    stock_actual = Column(Integer, default=0, nullable=False)
    stock_reservado = Column(Integer, default=0, nullable=False)
    stock_minimo = Column(Integer, default=0)
    ubicacion_fisica = Column(String(60))

    pieza = relationship("Pieza")
    taller = relationship("Taller")

    __table_args__ = (UniqueConstraint("taller_id", "pieza_id",
                                       name="uq_existencia_almacen_pieza"),)

    @property
    def disponible(self) -> int:
        return max(0, (self.stock_actual or 0) - (self.stock_reservado or 0))
