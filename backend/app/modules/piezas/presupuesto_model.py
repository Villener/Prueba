"""Paquete F - Piezas, almacen y compras.

Corresponde a Presupuesto, DetallePresupuesto, Autorizacion del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Presupuesto(Base, TimestampMixin):
    """v1.1: lo elabora el tecnico en papel y lo captura el administrador (RN-07, RN-11)."""
    __tablename__ = "presupuesto"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"), nullable=False)
    tecnico_elaboro_id = Column(Integer, ForeignKey("tecnico.id"), nullable=False)
    capturado_por_admin_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    fecha_elaboracion = Column(Date)     # la que trae el papel
    fecha_captura = Column(UTCDateTime, default=_now)
    folio_papel = Column(String(40))
    costo_mano_obra = Column(Numeric(12, 2), default=0)
    subtotal_piezas = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), default=0)
    estado = Column(String(24), default="capturado", nullable=False)
    diagnostico = Column(Text)
    dias_estimados_reparacion = Column(Integer)
    fecha_aviso_al_tecnico = Column(UTCDateTime)

    orden = relationship("OrdenServicio", back_populates="presupuestos")
    tecnico = relationship("Tecnico")
    detalles = relationship("DetallePresupuesto", back_populates="presupuesto",
                            cascade="all, delete-orphan")
    autorizaciones = relationship("Autorizacion", back_populates="presupuesto",
                                  cascade="all, delete-orphan")

    @property
    def dias_retraso_captura(self):
        """fecha_captura - fecha_elaboracion: mide si el 'tiempo real' del gerente es real."""
        if not self.fecha_elaboracion or not self.fecha_captura:
            return None
        return (self.fecha_captura.date() - self.fecha_elaboracion).days

class DetallePresupuesto(Base):
    __tablename__ = "detalle_presupuesto"
    id = Column(Integer, primary_key=True)
    presupuesto_id = Column(Integer, ForeignKey("presupuesto.id"), nullable=False)
    pieza_id = Column(Integer, ForeignKey("pieza.id"))
    descripcion_libre = Column(String(200))
    cantidad = Column(Numeric(10, 2), default=1)
    precio_unitario = Column(Numeric(12, 2), default=0)
    importe = Column(Numeric(12, 2), default=0)
    disponible_en_almacen = Column(Boolean, default=False)

    presupuesto = relationship("Presupuesto", back_populates="detalles")
    pieza = relationship("Pieza")

class Autorizacion(Base):
    """Entidad propia para conservar el historial de idas y vueltas del presupuesto."""
    __tablename__ = "autorizacion"
    id = Column(Integer, primary_key=True)
    presupuesto_id = Column(Integer, ForeignKey("presupuesto.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    nivel = Column(String(20), nullable=False)      # administrador|gerente
    resultado = Column(String(20), nullable=False)  # aprobado|rechazado|devuelto|remitido
    fecha = Column(UTCDateTime, default=_now)
    comentario = Column(Text)

    presupuesto = relationship("Presupuesto", back_populates="autorizaciones")
    usuario = relationship("Usuario")
