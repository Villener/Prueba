"""Paquete F - Piezas, almacen y compras.

Corresponde a SolicitudPieza, ESTADOS_SOLICITUD_PIEZA del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class SolicitudPieza(Base, TimestampMixin):
    """El mecanico autonomo consulta el almacen de Alamos y, si no hay, pide.

    La solicitud llega a los perfiles de administrador, que la evaluan y
    ejecutan la orden de compra. El mecanico ve el estatus todo el tiempo.
    """
    __tablename__ = "solicitud_pieza"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True)
    tecnico_id = Column(Integer, ForeignKey("tecnico.id"), nullable=False)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"))
    pieza_id = Column(Integer, ForeignKey("pieza.id"))
    descripcion_libre = Column(String(240))     # si la pieza no esta en catalogo
    cantidad = Column(Integer, default=1, nullable=False)
    justificacion = Column(Text)
    estado = Column(String(24), default="enviada", nullable=False)
    fecha_solicitud = Column(UTCDateTime, default=_now, nullable=False)
    evaluada_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_evaluacion = Column(UTCDateTime)
    motivo_rechazo = Column(Text)
    fecha_estimada_llegada = Column(Date)
    fecha_surtido = Column(UTCDateTime)

    tecnico = relationship("Tecnico")
    pieza = relationship("Pieza")

    def estatus_para_mecanico(self) -> str:
        """Contesta lo unico que el mecanico quiere saber."""
        if self.estado == "recibida":
            return "Ya llego"
        if self.estado == "surtida_de_almacen":
            return "Surtida del almacen"
        if self.estado == "rechazada":
            return "Rechazada: " + (self.motivo_rechazo or "sin motivo")
        if self.fecha_estimada_llegada:
            return "En proceso, llega el " + self.fecha_estimada_llegada.strftime("%d/%m/%Y")
        return "En proceso, sin fecha todavia"

ESTADOS_SOLICITUD_PIEZA = ["enviada", "en_evaluacion", "surtida_de_almacen",
                           "aprobada_para_compra", "en_compra", "en_transito",
                           "recibida", "rechazada"]
