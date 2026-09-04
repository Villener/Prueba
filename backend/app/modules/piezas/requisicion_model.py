"""Paquete F - Piezas, almacen y compras.

LA REQUISICION es el papel que el capturista teclea todos los dias.

No es lo mismo que `SolicitudPieza`. La solicitud es de UNA pieza y la levanta
el mecanico autonomo desde su telefono. La requisicion es un DOCUMENTO con
folio: una unidad, un mecanico, una fecha y N renglones de material, y quien la
teclea no es quien la pidio. Asi viene en `REQUIS 2026 2.xlsx`, una hoja por
requisicion, y asi la firman abajo tres personas distintas (autorizo / recibio
materiales / entrego almacen).

Meter esto dentro de SolicitudPieza habria obligado a inventar un folio comun
para agrupar renglones sueltos, que es justo la estructura que el Excel ya
trae explicita.
"""
from sqlalchemy import (Boolean, Column, Date, ForeignKey, Integer, Numeric,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class Requisicion(Base, TimestampMixin):
    __tablename__ = "requisicion"
    id = Column(Integer, primary_key=True)
    # El folio que trae el papel (J288, J289...).
    #
    # NO es unico, y eso NO es un descuido: en `REQUIS 2026 2.xlsx` hay 10
    # folios reutilizados para requisiciones distintas --J332 aparece cinco
    # veces, con cinco unidades y cinco fechas diferentes--. Poner UNIQUE aqui
    # habria tumbado la importacion del libro real del cliente.
    folio = Column(String(24), nullable=False, index=True)
    fecha = Column(Date, nullable=False)          # la del papel, no la de captura
    taller_id = Column(Integer, ForeignKey("taller.id"))

    unidad_id = Column(Integer, ForeignKey("unidad.id"))
    # El numero economico TAL CUAL venia escrito. Se guarda aunque `unidad_id`
    # haya casado: el papel dice "BG-354P" y el catalogo "BG354P", y cuando no
    # casa hay que poder ver contra que se estaba comparando.
    unidad_texto = Column(String(40))
    equipo_sap = Column(String(20))               # 1390021083
    centro_gestion = Column(String(10))           # AL01, AL07... (CEGE)

    # Quien pidio el material. Es el mecanico, y NO tiene cuenta en el sistema.
    tecnico_id = Column(Integer, ForeignKey("tecnico.id"))
    solicitante_num_empleado = Column(String(30))
    solicitante_nombre = Column(String(120))

    # Los dos responsables del dato (regla v1.1): quien lo hizo y quien lo
    # tecleo. Sin `capturada_por_usuario_id` no hay a quien preguntarle por un
    # renglon dudoso tres meses despues.
    capturada_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_captura = Column(UTCDateTime, default=_now)

    estado = Column(String(20), default="capturada", nullable=False)
    # 'excel'  la trajo el importador del libro REQUIS (historico)
    # 'app'    la tecleo el capturista aqui
    origen = Column(String(10), default="app", nullable=False)
    observaciones = Column(Text)

    # NO hay restriccion de unicidad, y se probo que no puede haberla. El
    # candidato razonable era (folio, fecha, unidad), pero el libro real trae
    # J331 y J332 repetidos el mismo dia con materiales COMPLETAMENTE distintos:
    # son papeles diferentes a los que les tocó el mismo folio. Con esa
    # restriccion puesta, la importacion descartaba tres requisiciones buenas.
    #
    # El duplicado de verdad --mismo folio, misma fecha, misma unidad Y los
    # mismos materiales-- se detecta donde si se puede comparar el contenido:
    # el importador lo salta y el controlador pide confirmacion explicita.

    renglones = relationship("RenglonRequisicion", back_populates="requisicion",
                             cascade="all, delete-orphan")
    unidad = relationship("Unidad")
    tecnico = relationship("Tecnico")
    taller = relationship("Taller")

    @property
    def total_piezas(self) -> int:
        return sum(r.cantidad or 0 for r in self.renglones)


class RenglonRequisicion(Base):
    """Un material de la requisicion.

    `pieza_id` es OPCIONAL a proposito. El papel trae codigos que no siempre
    estan en el catalogo, y perder el renglon por eso seria peor que guardarlo
    sin casar: el codigo y la descripcion quedan escritos y se pueden reconciliar
    despues. Lo mismo que hace `Pieza.codigo_externo` con SAP.
    """
    __tablename__ = "renglon_requisicion"
    id = Column(Integer, primary_key=True)
    requisicion_id = Column(Integer, ForeignKey("requisicion.id"), nullable=False)
    linea = Column(Integer, default=1, nullable=False)
    pieza_id = Column(Integer, ForeignKey("pieza.id"))
    codigo = Column(String(40), index=True)       # el codigo tecleado del papel
    descripcion = Column(String(200), nullable=False)
    cantidad = Column(Integer, default=1, nullable=False)
    # Se copia del catalogo al capturar. Congelado: el precio de hoy no debe
    # reescribir lo que costo una requisicion del ano pasado.
    costo_unitario = Column(Numeric(12, 2))
    surtido = Column(Boolean, default=False)

    requisicion = relationship("Requisicion", back_populates="renglones")
    pieza = relationship("Pieza")

    __table_args__ = (UniqueConstraint("requisicion_id", "linea",
                                       name="uq_renglon_por_requisicion"),)

    @property
    def importe(self):
        return float(self.costo_unitario or 0) * (self.cantidad or 0)


ESTADOS_REQUISICION = ["capturada", "autorizada", "surtida", "cancelada"]
