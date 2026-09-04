"""Paquete D - Mantenimiento preventivo y agenda.

Corresponde a CitaTaller, ESTADOS_CITA, Reprogramacion del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class CitaTaller(Base, TimestampMixin):
    """La promesa operativa: el dia en que el taller recibe la unidad.

    Se separa a proposito de PROGRAMA_MANTENIMIENTO.fecha_limite:
      fecha_limite  -> viene del plan, NUNCA se mueve. Es el compromiso tecnico.
      fecha_cita    -> la asigna la agenda segun capacidad, SI se mueve.
    Por eso el chofer solo incumple si falto a una cita CONFIRMADA: si el
    taller nunca pudo darsela, el problema es de capacidad, no del chofer.
    """
    __tablename__ = "cita_taller"
    id = Column(Integer, primary_key=True)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    programa_mantenimiento_id = Column(Integer, ForeignKey("programa_mantenimiento.id"))
    solicitud_id = Column(Integer, ForeignKey("solicitud_ingreso.id"))
    tipo_servicio_id = Column(Integer, ForeignKey("tipo_servicio.id"))
    fecha_cita = Column(Date, nullable=False)
    fecha_limite_origen = Column(Date)          # copiada del programa; INMUTABLE
    duracion_estimada_dias = Column(Integer, default=1)
    estado = Column(String(16), default="propuesta", nullable=False)
    veces_reprogramada = Column(Integer, default=0, nullable=False)
    score_prioridad = Column(Integer, default=0)
    origen_agenda = Column(String(12), default="automatica")  # automatica|manual
    fecha_confirmacion_taller = Column(UTCDateTime)
    fecha_confirmacion_chofer = Column(UTCDateTime)
    agendada_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))

    taller = relationship("Taller")
    unidad = relationship("Unidad")
    tipo_servicio = relationship("TipoServicio")

ESTADOS_CITA = ["propuesta", "confirmada", "reprogramada", "cumplida",
                "no_asistio", "cancelada"]

class Reprogramacion(Base):
    """Append-only: cada movimiento de fecha deja rastro con su motivo."""
    __tablename__ = "reprogramacion"
    id = Column(Integer, primary_key=True)
    cita_id = Column(Integer, ForeignKey("cita_taller.id"), nullable=False)
    fecha_anterior = Column(Date, nullable=False)
    fecha_nueva = Column(Date, nullable=False)
    motivo = Column(String(30), nullable=False)  # sin_espacio|unidad_atorada|urgencia_desplaza
    automatica = Column(Boolean, default=True, nullable=False)
    requirio_autorizacion = Column(Boolean, default=False)
    aviso_enviado = Column(Boolean, default=False)
    usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha = Column(UTCDateTime, default=_now, nullable=False)

    cita = relationship("CitaTaller")
