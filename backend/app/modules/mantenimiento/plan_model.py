"""Paquete D - Mantenimiento preventivo y agenda.

Corresponde a PlanMantenimiento, ProgramaMantenimiento del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class PlanMantenimiento(Base):
    __tablename__ = "plan_mantenimiento"
    id = Column(Integer, primary_key=True)
    tipo_unidad_id = Column(Integer, ForeignKey("tipo_unidad.id"))
    nombre = Column(String(120), nullable=False)
    # Que servicio se hace al cumplirse el plan. De aqui la agenda saca la
    # duracion y la criticidad con las que ordena la cola; sin esto no puede
    # calcular nada (modelo-er.md: TIPO_SERVICIO ||--o{ PLAN_MANTENIMIENTO).
    tipo_servicio_id = Column(Integer, ForeignKey("tipo_servicio.id"))
    periodicidad_dias = Column(Integer)
    periodicidad_km = Column(Integer)
    descripcion = Column(Text)
    activo = Column(Boolean, default=True)

    tipo_servicio = relationship("TipoServicio")

class ProgramaMantenimiento(Base, TimestampMixin):
    __tablename__ = "programa_mantenimiento"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plan_mantenimiento.id"), nullable=False)
    fecha_programada = Column(Date)
    km_programado = Column(Integer)
    fecha_limite = Column(Date, nullable=False)
    estado = Column(String(20), default="pendiente", nullable=False)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"))
    fecha_cumplimiento = Column(UTCDateTime)

    unidad = relationship("Unidad")
    plan = relationship("PlanMantenimiento")


# Los estados por los que pasa un programa, y cuales lo dan por terminado.
#
# ESTA LISTA EXISTE PORQUE SU AUSENCIA COSTO EL CICLO ENTERO. El estado se
# escribia desde cinco lugares con cadenas sueltas, y cada uno tenia en la
# cabeza su propio mapa de a donde se podia llegar desde donde. El resultado,
# medido en produccion el 2026-09-23: de 718 programas, 573 en `sin_cupo`, 144
# en `agendado` y UNO en `cumplido`.
#
# La causa: el administrador solo daba por cumplido el programa que encontraba
# en `pendiente`, pero la agenda ya lo habia dejado en `agendado` al darle cita.
# O sea que el unico preventivo que el sistema podia cerrar era el que la agenda
# nunca habia agendado -- mientras mejor funcionaba la agenda, mas cerca de cero
# quedaba el tablero de la meta. Y como meta_preventivo excluye del alta a las
# unidades con programa vivo, esa unidad tampoco recibia programa nuevo: el
# ciclo se trababa solo y para siempre.
#
# Quien quiera saber si un programa sigue vivo pregunta aqui, no escribe la
# lista otra vez.
ESTADOS_PROGRAMA = ("pendiente", "agendado", "sin_cupo", "vencido",
                    "cumplido", "cancelado")

# Terminados: ya no piden nada ni bloquean el alta del siguiente programa.
ESTADOS_PROGRAMA_CERRADOS = ("cumplido", "cancelado")

# Vivos: el mantenimiento sigue debiendose, lo diga la palabra que lo diga. Un
# programa en CUALQUIERA de estos se cierra cuando la unidad entra al taller por
# un preventivo -- da igual si estaba esperando cita, si ya la tenia, si se
# quedo sin cupo o si se vencio. Lo que lo cierra es que la unidad LLEGO.
ESTADOS_PROGRAMA_VIVOS = tuple(e for e in ESTADOS_PROGRAMA
                               if e not in ESTADOS_PROGRAMA_CERRADOS)
