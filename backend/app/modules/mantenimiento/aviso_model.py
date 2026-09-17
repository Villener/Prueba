"""Paquete D - Mantenimiento preventivo y agenda.

Corresponde a AvisoIncumplimiento, Penalizacion del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class AvisoIncumplimiento(Base, TimestampMixin):
    """Sustituye a PENALIZACION.

    El sistema NO sanciona: avisa al gerente y a Erick, ellos hablan con el
    chofer en persona y despues marcan el caso como atendido. Por eso no hay
    monto ni proceso de inconformidad.
    """
    __tablename__ = "aviso_incumplimiento"
    id = Column(Integer, primary_key=True)
    cita_id = Column(Integer, ForeignKey("cita_taller.id"), unique=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    # De donde salio que ESE chofer era el responsable ese dia.
    fundamento_poseedor = Column(String(16))     # jornada|prestamo|titularidad
    jornada_id = Column(Integer, ForeignKey("jornada.id"))
    prestamo_id = Column(Integer, ForeignKey("prestamo_unidad.id"))
    asignacion_id = Column(Integer, ForeignKey("asignacion_unidad.id"))
    fecha_generacion = Column(Date, nullable=False)
    dias_atraso = Column(Integer, default=0)
    estado = Column(String(12), default="abierto", nullable=False)  # abierto|atendido|anulado
    fecha_atencion = Column(UTCDateTime)
    atendido_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    nota_atencion = Column(Text)
    veces_recordado = Column(Integer, default=0, nullable=False)

    unidad = relationship("Unidad")
    chofer = relationship("Chofer")

class Penalizacion(Base, TimestampMixin):
    __tablename__ = "penalizacion"
    id = Column(Integer, primary_key=True)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)  # el POSEEDOR
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    programa_mantenimiento_id = Column(Integer, ForeignKey("programa_mantenimiento.id"),
                                       unique=True)
    motivo = Column(String(240), nullable=False)
    fecha_generacion = Column(Date, default=lambda: datetime.utcnow().date())
    dias_atraso = Column(Integer, default=0)
    estado = Column(String(20), default="aplicada", nullable=False)
    aplicada_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    resolucion_disputa = Column(Text)

    unidad = relationship("Unidad")
    programa = relationship("ProgramaMantenimiento")


ESTADOS_AMONESTACION = ["emitida", "inconforme", "ratificada", "anulada"]


class Amonestacion(Base, TimestampMixin):
    """RN-14: el acto administrativo contra el chofer que falto a una cita CONFIRMADA.

    CUELGA DEL AVISO, y ahi esta todo el diseno. El aviso ya es la prueba: solo
    existe si hubo cita confirmada, si la unidad no se presento, y apunta al
    POSEEDOR de ese dia con el fundamento de por que era el (RN-01). Sin aviso
    no hay amonestacion -- y por eso es imposible amonestar a alguien a quien el
    taller nunca le dio cita, que es justo lo que RN-14 prohibe.

    `aviso_id` es unique: una falta, una amonestacion. No se puede sancionar dos
    veces el mismo hecho.

    EL SISTEMA NO LA EMITE SOLO. CU-AUT-08 la propone --arma el expediente y
    avisa-- pero quien firma es una persona (CU-SUP-10). Una sancion que sale
    sola de un cron es la que nadie puede explicar cuando el chofer reclama.

    Es ADMINISTRATIVA, no economica: no hay monto. La nomina sigue fuera de
    alcance y RN-14 lo dice explicitamente.
    """
    __tablename__ = "amonestacion"
    id = Column(Integer, primary_key=True)
    aviso_id = Column(Integer, ForeignKey("aviso_incumplimiento.id"),
                      unique=True, nullable=False)
    # Se copia del aviso aunque sea redundante: el expediente del chofer se
    # consulta miles de veces y no tiene por que pasar por el aviso cada vez.
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    # Cual le toca a ESE chofer: la primera, la segunda, la tercera. El cliente
    # todavia no dice que pasa a la segunda (pregunta abierta #13), pero sin
    # llevar la cuenta desde hoy, el dia que lo decida no habria con que aplicarlo.
    consecutivo = Column(Integer, default=1, nullable=False)
    motivo = Column(String(240), nullable=False)
    nota = Column(Text)
    emitida_por_usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    fecha_emision = Column(UTCDateTime, default=_now, nullable=False)
    estado = Column(String(14), default="emitida", nullable=False)

    # El chofer puede inconformarse (RF-CHO-16). Si la amonestacion va al
    # expediente, tiene que haber a donde reclamar.
    inconformidad = Column(Text)
    fecha_inconformidad = Column(UTCDateTime)
    resolucion = Column(Text)
    resuelta_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_resolucion = Column(UTCDateTime)

    aviso = relationship("AvisoIncumplimiento")
    chofer = relationship("Chofer")


# --------------------------------------------------------------------------- #
# AREA C - Taller e infraestructura
# --------------------------------------------------------------------------- #
