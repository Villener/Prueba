"""Paquete E - Orden de servicio y traslados.

Corresponde a OrdenServicio, AsignacionTecnico, FormatoSalida del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class OrdenServicio(Base, TimestampMixin):
    __tablename__ = "orden_servicio"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    solicitud_id = Column(Integer, ForeignKey("solicitud_ingreso.id"))
    arrastre_id = Column(Integer, ForeignKey("arrastre.id"))
    # Que se le hizo. Va en la orden y no solo en la cita porque la mayoria de
    # las estancias son correctivas y nunca tuvieron cita: sin esto no hay como
    # atribuirle la duracion medida a un tipo de servicio (CU-AUT-06).
    tipo_servicio_id = Column(Integer, ForeignKey("tipo_servicio.id"))
    chofer_responsable_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    fecha_entrada = Column(UTCDateTime, default=_now)
    # Cuando se espera que la unidad libere el espacio. Es el disparador D3 de
    # agenda-mantenimiento.md §3, el que mas se olvida: sin esta fecha la agenda
    # no puede saber cuando aparece capacidad y planea a ciegas. La escribe
    # Erick al registrar la ETA de las piezas.
    fecha_salida_estimada = Column(Date)
    fecha_salida = Column(UTCDateTime)
    estado = Column(String(24), default="abierta", nullable=False)
    km_entrada = Column(Integer)
    km_salida = Column(Integer)
    tipo = Column(String(20), default="correctivo")
    abierta_por_admin_id = Column(Integer, ForeignKey("usuario.id"))

    unidad = relationship("Unidad")
    taller = relationship("Taller")
    tipo_servicio = relationship("TipoServicio")
    asignaciones = relationship("AsignacionTecnico", back_populates="orden",
                                cascade="all, delete-orphan")
    presupuestos = relationship("Presupuesto", back_populates="orden")

class AsignacionTecnico(Base):
    """La 'fila de procesos esperando' del enunciado (RF-ADM-06)."""
    __tablename__ = "asignacion_tecnico"
    id = Column(Integer, primary_key=True)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"), nullable=False)
    tecnico_id = Column(Integer, ForeignKey("tecnico.id"), nullable=False)
    especialidad = Column(String(30))
    orden_en_cola = Column(Integer, default=1, nullable=False)
    estado = Column(String(20), default="en_espera", nullable=False)
    fecha_asignacion = Column(UTCDateTime, default=_now)
    fecha_inicio = Column(UTCDateTime)
    fecha_fin = Column(UTCDateTime)
    diagnostico = Column(Text)          # lo dicta el tecnico
    trabajo_realizado = Column(Text)
    asignado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    capturado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))  # RN-11
    fecha_captura = Column(UTCDateTime)

    orden = relationship("OrdenServicio", back_populates="asignaciones")
    tecnico = relationship("Tecnico")

class FormatoSalida(Base):
    __tablename__ = "formato_salida"
    id = Column(Integer, primary_key=True)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"), unique=True,
                               nullable=False)
    fecha = Column(UTCDateTime, default=_now)
    entregado_a_chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    elaborado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    # Antes era `trabajos_realizados`. El formato se llena cuando la unidad SALE
    # hacia el trabajo, no cuando ya se hizo: pedirlo en pasado obligaba a
    # escribir algo que todavia no ocurria.
    operacion_a_realizar = Column(Text)
    unidad_operativa = Column(Boolean, default=True)

    # `km_salida` y `observaciones` se retiraron del formato a peticion del
    # cliente. Las columnas se dejan de escribir; no se borran de la tabla
    # porque hay formatos viejos con ese dato y borrarlas lo perderia.
    km_salida = Column(Integer)
    observaciones = Column(Text)
    trabajos_realizados = Column(Text)

    orden = relationship("OrdenServicio")


# --------------------------------------------------------------------------- #
# AREA D - Presupuestos, piezas y compras
# --------------------------------------------------------------------------- #
