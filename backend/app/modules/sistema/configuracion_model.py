"""Paquete H - Transversales: avisos, bitacora y configuracion.

Corresponde a Configuracion del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Configuracion(Base):
    __tablename__ = "configuracion"
    id = Column(Integer, primary_key=True)
    clave = Column(String(60), unique=True, nullable=False)
    valor = Column(String(200), nullable=False)
    descripcion = Column(String(240))
    tipo_dato = Column(String(20), default="int")


# ---------------------------------------------------------------------------
# Candados de integridad que el codigo por si solo no garantiza.
#
# Solo hay UN vehiculo fisico: no puede tener dos estancias abiertas ni ocupar
# dos espacios. Aceptar dos solicitudes de la misma unidad lo duplicaba en el
# taller. La validacion en el servicio da el mensaje; estos indices son los que
# hacen que el defecto sea imposible aunque alguien llame a la API directo o
# dos administradores acepten al mismo tiempo.


# =========================================================================== #
#  ENTIDADES v2.0  (docs/modelo-clases.md y docs/modelo-er.md)
#  Multi-planta, mecanico autonomo, agenda de mantenimiento, auxilio en
#  carretera, almacen consultable y traslados entre plantas.
# =========================================================================== #
