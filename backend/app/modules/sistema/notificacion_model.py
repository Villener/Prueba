"""Paquete H - Transversales: avisos, bitacora y configuracion.

Corresponde a Notificacion, AlertaGerencia del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


# --------------------------------------------------------------------------- #
# AREA F - Transversales
# --------------------------------------------------------------------------- #
class Notificacion(Base):
    __tablename__ = "notificacion"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    tipo = Column(String(40))
    titulo = Column(String(160), nullable=False)
    mensaje = Column(Text)
    entidad_tipo = Column(String(40))
    entidad_id = Column(Integer)
    leida = Column(Boolean, default=False, nullable=False)
    fecha_envio = Column(UTCDateTime, default=_now)
    fecha_lectura = Column(UTCDateTime)


class SuscripcionPush(Base):
    """Un celular (o navegador) que acepto recibir los avisos de UNA cuenta.

    El `endpoint` lo da el servicio de avisos del fabricante (Google, Apple,
    Mozilla, Microsoft) y es uno por navegador instalado. Por eso es unico: si
    en ese mismo telefono entra otra persona, la fila cambia de dueno en vez de
    duplicarse, y los avisos de la anterior dejan de llegarle a la nueva."""
    __tablename__ = "suscripcion_push"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(60), nullable=False)
    # El navegador que la pidio, recortado: para reconocer cual es cual.
    dispositivo = Column(String(200))
    creada_en = Column(UTCDateTime, default=_now)
    ultimo_envio = Column(UTCDateTime)
    # Fallos SEGUIDOS. Se vuelve a cero con cada envio bueno.
    fallos = Column(Integer, default=0, nullable=False)


class AlertaGerencia(Base):
    __tablename__ = "alerta_gerencia"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(50), nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"))
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    fecha_generacion = Column(UTCDateTime, default=_now)
    veces_notificada = Column(Integer, default=1)  # RN-08: reincide hasta atenderse
    ultima_notificacion = Column(UTCDateTime, default=_now)
    atendida = Column(Boolean, default=False, nullable=False)
    fecha_atencion = Column(UTCDateTime)
    atendida_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    detalle = Column(Text)

    unidad = relationship("Unidad")
