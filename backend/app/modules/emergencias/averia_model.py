"""Paquete G - Averias, auxilio en carretera y arrastre.

Corresponde a ReporteAveria, ReportePeritaje del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import backref, relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


# --------------------------------------------------------------------------- #
# AREA E - Emergencias y arrastre
# --------------------------------------------------------------------------- #
class ReporteAveria(Base, TimestampMixin):
    __tablename__ = "reporte_averia"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    fecha_hora = Column(UTCDateTime, default=_now)
    latitud = Column(Float)
    longitud = Column(Float)
    direccion_referencia = Column(String(240))
    descripcion_falla = Column(Text)
    # RN-16: chocar y quedarse tirado NO son el mismo procedimiento. Va como
    # discriminador y no como tabla aparte porque la maquinaria que comparten es
    # casi toda --ubicacion, fotos, despacho, arrastre, peritaje-- y duplicarla
    # significaria mantener dos veces el mismo bloqueo. Lo que SI cambia por
    # completo vive en DetalleChoque y en puede_solicitar_arrastre().
    #
    # De paso, asi el gerente puede contar cuantos choques hubo en el ano, que
    # es un numero que cualquier flota necesita y que hoy no existia.
    tipo = Column(String(10), default="averia", nullable=False)   # averia|choque
    en_vialidad_publica = Column(Boolean, default=False, nullable=False)  # RN-04
    hay_terceros_involucrados = Column(Boolean, default=False)
    requiere_arrastre = Column(Boolean, default=False)
    estado = Column(String(24), default="abierto", nullable=False)
    supervisor_notificado_id = Column(Integer, ForeignKey("supervisor.usuario_id"))

    # --- Desenlace del despacho (v1.4) -------------------------------------
    # Sin estas cuatro columnas el sistema solo sabia contar arrastres, y el
    # arrastre es la MINORIA de las averias: la mayoria se resuelve con una
    # llamada en la que el chofer mueve algo el mismo. Eso no se registraba en
    # ningun lado, asi que el corte del mes decia "40 averias, 12 arrastres" y
    # de las otras 28 no habia forma de saber que paso.
    #
    # Ademas es el dato que hace posible cualquier sugerencia automatica mas
    # adelante: sin el desenlace guardado no hay de que aprender.
    desenlace = Column(String(20))              # telefono|llantero|mecanico|grua
    despachado_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_despacho = Column(UTCDateTime)
    nota_despacho = Column(Text)

    unidad = relationship("Unidad")
    peritaje = relationship("ReportePeritaje", back_populates="reporte", uselist=False,
                            cascade="all, delete-orphan")
    arrastre = relationship("Arrastre", back_populates="reporte", uselist=False)

TIPOS_REPORTE = ("averia", "choque")
DESTINOS_CHOQUE = {"carroceria": "Carroceria", "mecanica": "Taller mecanico",
                   "circula": "Sigue circulando"}


class DetalleChoque(Base, TimestampMixin):
    """Lo que un choque tiene y una averia no.

    Va en su propia tabla en vez de como columnas nulas en ReporteAveria: son
    ocho campos que solo aplican al 100% de los choques y al 0% de las averias,
    y mezclarlos dejaria la tabla principal llena de huecos que nadie sabe leer.

    Un choque termina en CARROCERIA y cuesta deducible y prima; una averia
    termina en mecanica y cuesta refaccion y mano de obra. Por eso el destino y
    el deducible viven aqui.
    """
    __tablename__ = "detalle_choque"
    id = Column(Integer, primary_key=True)
    reporte_averia_id = Column(Integer, ForeignKey("reporte_averia.id"),
                               unique=True, nullable=False)
    descripcion_danos = Column(Text)
    cuantos_terceros = Column(Integer, default=0, nullable=False)
    datos_terceros = Column(Text)                 # nombres, placas, aseguradora
    parte_accidente_folio = Column(String(60))
    aseguradora_tercero = Column(String(120))
    # Que la unidad pueda moverse por su cuenta NO la desbloquea: sigue sin
    # poder irse del lugar hasta que haya peritaje (RN-16). Solo dice si al
    # final hara falta grua o se puede ir manejando.
    unidad_puede_circular = Column(Boolean, default=False, nullable=False)
    destino = Column(String(16))                  # carroceria|mecanica|circula
    deducible_estimado = Column(Numeric(12, 2))
    hay_lesionados = Column(Boolean, default=False, nullable=False)

    # uselist=False va en el BACKREF: sin eso, reporte.detalle_choque sale como
    # lista y el serializador revienta pidiendole atributos a una lista.
    reporte = relationship("ReporteAveria",
                           backref=backref("detalle_choque", uselist=False))


class ReportePeritaje(Base):
    """RN-04: sin este registro no se habilita el arrastre en vialidad publica."""
    __tablename__ = "reporte_peritaje"
    id = Column(Integer, primary_key=True)
    reporte_averia_id = Column(Integer, ForeignKey("reporte_averia.id"), unique=True,
                               nullable=False)
    folio_peritos = Column(String(60), nullable=False)
    aseguradora = Column(String(120))
    hora_aviso = Column(UTCDateTime, default=_now)
    hora_llegada_perito = Column(UTCDateTime)
    nombre_perito = Column(String(120))
    resultado = Column(String(120))
    observaciones = Column(Text)
    liberada_la_unidad = Column(Boolean, default=False)

    reporte = relationship("ReporteAveria", back_populates="peritaje")
