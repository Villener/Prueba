"""Paquete F - Piezas, almacen y compras.

Corresponde a Proveedor, OrdenCompra del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Proveedor(Base):
    __tablename__ = "proveedor"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(160), nullable=False)
    rfc = Column(String(20))
    contacto = Column(String(120))
    telefono = Column(String(30))
    email = Column(String(160))
    activo = Column(Boolean, default=True)

class OrdenCompra(Base, TimestampMixin):
    __tablename__ = "orden_compra"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    presupuesto_id = Column(Integer, ForeignKey("presupuesto.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedor.id"))
    autorizada_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_emision = Column(UTCDateTime, default=_now)
    estado = Column(String(24), default="solicitada", nullable=False)
    fecha_estimada_llegada = Column(Date)
    fecha_recepcion = Column(UTCDateTime)
    total = Column(Numeric(12, 2), default=0)
    numero_rastreo = Column(String(60))

    presupuesto = relationship("Presupuesto")
    proveedor = relationship("Proveedor")


# --------------------------------------------------------------------------- #
# AREA E - Emergencias y arrastre
# --------------------------------------------------------------------------- #
