"""Paquete E - Reporte de mantenimiento.

Es el papel que hoy se llena a mano en Alamos: el formato con la revision
rapida, los diez sistemas del vehiculo y las cinco firmas del pie.

POR QUE ES UNA ENTIDAD APARTE Y NO CAMPOS DE `OrdenServicio`.
El reporte y la orden no nacen al mismo tiempo ni los llena la misma persona.
El reporte se abre cuando la unidad CRUZA LA PLUMA -- antes de que exista
espacio, tecnico o diagnostico -- y su parte de arriba (revision rapida,
kilometraje, nivel de combustible) es el estado en que se RECIBIO la unidad,
un hecho que no se puede reescribir despues sin perder la constancia. La orden
de servicio es la reparacion. Aplanarlos en una tabla haria imposible
responder "como entro" cuando la reparacion ya cambio el vehiculo.

Los mecanicos NO usan la aplicacion (v1.1), asi que este formato lo teclea el
administrador a partir del papel: por eso guarda doble responsable (RN-11),
quien firmo y quien capturo.
"""
from sqlalchemy import (Column, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime

# Las diez lineas de la tabla central del papel, en el mismo orden impreso.
# Cambiarles el orden cambia un formato que el taller ya se sabe de memoria.
SISTEMAS = [
    ("soldadura", "Soldadura"),
    ("carroceria_pintura", "Carrocería y pintura"),
    ("motor", "Sistema motor"),
    ("transmision", "Sistema transmisión"),
    ("electrico", "Sistema eléctrico"),
    ("direccion", "Sistema de dirección"),
    ("suspension", "Sistema de suspensión"),
    ("frenos", "Sistema de frenos"),
    ("enfriamiento", "Sistema de enfriamiento"),
    ("llantas", "Llantas"),
]

# La rejilla de "REVISION RAPIDA", leida como esta impresa: por renglones,
# de izquierda a derecha.
PUNTOS_REVISION = [
    ("baterias", "Baterías"),
    ("tapon_combustible", "Tapón de comb."),
    ("tranca_tope", "Tranca / tope"),
    ("extintor", "Extintor"),
    ("rotulos", "Rótulos"),
    ("espejos", "Espejos"),
    ("reflejantes", "Reflejantes"),
    ("placa_delantera", "Placa del."),
    ("parabrisas", "Parabrisas"),
    ("placa_trasera", "Placa tras."),
    ("ventanas", "Ventanas"),
]

# El papel solo tiene una casilla por punto, y esa casilla no distingue "lo
# revise y esta bien" de "no lo revise". Es justo la diferencia que importa
# cuando falta un extintor y hay que saber si la unidad entro sin el o si
# nadie lo miro. Por eso aqui son cuatro estados y no un booleano.
ESTADOS_PUNTO = ["bien", "mal", "no_aplica", "sin_revisar"]

# El dibujito del medidor de gasolina del formato.
NIVELES_COMBUSTIBLE = ["vacio", "1/4", "1/2", "3/4", "lleno"]

# Las casillas de area que van bajo los datos de la unidad.
AREAS = ["reparto", "pipas", "utilitarias", "operaciones", "ventas", "otros"]

TIPOS_SERVICIO = ["correctivo", "preventivo"]

# Los cinco recuadros del pie. `rol_firma` es la llave; el texto es lo que el
# papel imprime encima de la raya.
FIRMAS = [
    ("entrega_taller", "Firma de quien deja la unidad en taller", "Chofer"),
    ("valida_trabajo", "Firma de quien valida el trabajo realizado", "Supervisor"),
    ("recepcion_pluma", "Firma de recepción de unidad", "Encargado de pluma"),
    ("vobo_mantenimiento", "Firma de Vo. Bo.", "Jefe de mantenimiento automotriz"),
    ("recibe_salida", "Nombre y firma de quien recibe la unidad en salida", "Chofer"),
]

# Sin estas dos la unidad no sale. Son las que el taller exige en papel antes
# de levantar la pluma; las otras tres se pueden recabar despues.
FIRMAS_OBLIGATORIAS_SALIDA = ["vobo_mantenimiento", "recibe_salida"]


class ReporteMantenimiento(Base, TimestampMixin):
    """Un papel = un renglon. La cabecera del formato."""
    __tablename__ = "reporte_mantenimiento"

    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)

    # Nullable a proposito: la unidad cruza la pluma antes de que exista orden.
    # El administrador liga el reporte a la orden cuando la abre.
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"), unique=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)

    tipo_servicio = Column(String(12), default="correctivo", nullable=False)
    origen = Column(String(80))
    kilometraje = Column(Integer)
    area = Column(String(16))
    area_otro = Column(String(60))   # el texto que va en la raya de "OTROS"

    # El nombre se guarda ADEMAS del id. El papel trae escrito a mano un nombre
    # que a veces no casa con ninguna cuenta (un eventual, un chofer de otra
    # planta), y perder ese dato por no encontrar al usuario deja el formato
    # sin responsable.
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    chofer_nombre = Column(String(120))
    supervisor_nombre = Column(String(120))

    fecha_entrada = Column(UTCDateTime, default=_now, nullable=False)
    fecha_salida = Column(UTCDateTime)

    nivel_combustible = Column(String(8))
    notas_ingreso = Column(Text)
    comentarios_adicionales = Column(Text)

    estado = Column(String(12), default="abierto", nullable=False)  # abierto | cerrado

    # RN-11: quien lo hizo (las firmas) y quien lo tecleo.
    capturado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_captura = Column(UTCDateTime, default=_now)
    cerrado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))

    unidad = relationship("Unidad")
    taller = relationship("Taller")
    orden = relationship("OrdenServicio")
    puntos = relationship("PuntoRevision", back_populates="reporte",
                          cascade="all, delete-orphan")
    actividades = relationship("ActividadReporte", back_populates="reporte",
                               cascade="all, delete-orphan")
    firmas = relationship("FirmaReporte", back_populates="reporte",
                          cascade="all, delete-orphan")

    def firmas_faltantes_para_salida(self) -> list[str]:
        firmadas = {f.rol_firma for f in self.firmas if f.nombre}
        return [r for r in FIRMAS_OBLIGATORIAS_SALIDA if r not in firmadas]


class PuntoRevision(Base):
    """Un renglon de la rejilla de revision rapida."""
    __tablename__ = "punto_revision"
    __table_args__ = (UniqueConstraint("reporte_id", "punto",
                                       name="uq_punto_por_reporte"),)

    id = Column(Integer, primary_key=True)
    reporte_id = Column(Integer, ForeignKey("reporte_mantenimiento.id"), nullable=False)
    punto = Column(String(24), nullable=False)
    estado = Column(String(12), default="sin_revisar", nullable=False)
    observacion = Column(String(160))

    reporte = relationship("ReporteMantenimiento", back_populates="puntos")


class ActividadReporte(Base):
    """Un sistema del vehiculo: lo que hay que hacerle y lo que se le hizo.

    Las dos columnas del papel viven en la MISMA fila porque en el papel estan
    una frente a otra: lo pedido y lo entregado se leen juntos, y esa
    comparacion es lo que el supervisor firma.
    """
    __tablename__ = "actividad_reporte"
    __table_args__ = (UniqueConstraint("reporte_id", "sistema",
                                       name="uq_sistema_por_reporte"),)

    id = Column(Integer, primary_key=True)
    reporte_id = Column(Integer, ForeignKey("reporte_mantenimiento.id"), nullable=False)
    sistema = Column(String(24), nullable=False)
    a_realizar = Column(Text)
    realizada = Column(Text)

    # La columna "FIRMAS" del papel: que tecnico responde por ese sistema.
    tecnico_id = Column(Integer, ForeignKey("tecnico.id"))
    fecha_realizada = Column(UTCDateTime)
    capturado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))

    reporte = relationship("ReporteMantenimiento", back_populates="actividades")
    tecnico = relationship("Tecnico")


class FirmaReporte(Base):
    """Uno de los cinco recuadros del pie.

    Es tabla y no cinco columnas por la misma razon que `AUTORIZACION` lo es:
    cada firma tiene su propio momento y su propio dueño, y aplanarlas perderia
    cuando se recabo cada una -- que es lo que permite explicar por que una
    unidad se quedo parada esperando un Vo. Bo.
    """
    __tablename__ = "firma_reporte"
    __table_args__ = (UniqueConstraint("reporte_id", "rol_firma",
                                       name="uq_firma_por_reporte"),)

    id = Column(Integer, primary_key=True)
    reporte_id = Column(Integer, ForeignKey("reporte_mantenimiento.id"), nullable=False)
    rol_firma = Column(String(24), nullable=False)
    nombre = Column(String(120))
    usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha = Column(UTCDateTime, default=_now)
    # Quien tecleo que esa firma existe en el papel. La firma es de tinta; esto
    # es la constancia de que alguien la vio.
    registrada_por_admin_id = Column(Integer, ForeignKey("usuario.id"))

    reporte = relationship("ReporteMantenimiento", back_populates="firmas")
