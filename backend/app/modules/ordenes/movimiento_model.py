"""El historial de taller que venia del Excel del area.

POR QUE NO ENTRA EN `orden_servicio`, que seria lo obvio.

Una fila de REPARADO NO es una orden de servicio: es el apunte de que una
unidad estuvo en el patio. No tiene folio, ni espacio asignado, ni presupuesto,
ni quien la abrio -- y sobre todo, el 98% no tiene FECHA DE SALIDA, porque el
area corta la fila de PATIO y la pega en REPARADO sin anotar cuando salio.

Meterlas en `orden_servicio` obligaria a dos cosas malas. La primera, inventar
una fecha de salida para 1,830 registros. La segunda es peor: el sistema tiene
un indice unico que impide que una unidad tenga dos ordenes abiertas a la vez
--y con razon, porque hay un solo vehiculo fisico--, asi que 1,869 movimientos
sin salida chocarian entre ellos. La unidad 1002 aparece 18 veces.

Asi que el historial vive aparte. Ademas de evitar el choque, deja algo que
importa para auditar: se distingue lo que ESTE sistema registro de lo que se
importo del Excel. Cuando alguien pregunte de donde salio un numero, la
respuesta esta en la columna `origen`.
"""
from sqlalchemy import (Boolean, Column, Date, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin


class MovimientoTaller(Base, TimestampMixin):
    __tablename__ = "movimiento_taller"
    __table_args__ = (
        # La llave natural del area. Medido sobre los 1,869 registros: solo 3
        # chocan (BG347 el 2024-01-18, 2109 el 2026-01-13 y 2184 el 2026-04-30),
        # o sea 0.16%. Sirve, y ademas hace que reimportar no duplique.
        UniqueConstraint("unidad_id", "fecha_ingreso", name="uq_movimiento_unidad_fecha"),
    )

    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    # Como lo escribio el area, sin normalizar. Sin esto no hay forma de
    # auditar despues por que una fila cruzo con la unidad que cruzo.
    unidad_texto = Column(String(40))

    fecha_ingreso = Column(Date, nullable=False)
    fecha_salida = Column(Date)          # solo la traen los movimientos recientes
    sigue_adentro = Column(Boolean, default=False, nullable=False)

    falla = Column(Text)
    # El apodo del mecanico tal cual: 'PEDRO', 'RIVAS', 'RESENDIZ'. En el
    # historico NO viene el numero de empleado, asi que no se puede ligar a la
    # tabla `tecnico` sin una tabla de apodos que hay que capturar a mano con el
    # jefe de taller. Hasta entonces esto es texto y no sirve para medir
    # productividad; guardarlo como si fuera una FK seria mentir.
    mecanico_texto = Column(String(80))

    uso = Column(String(40))             # REPARTO, PIPA, UTILITARIA, OPERACIONES
    estatus = Column(String(40))         # POR INGRESAR | EN PROCESO | PEDIDO CHINO
    observaciones = Column(String(80))   # P/PROGRAMACION | TRABAJANDO | PARTES CHINAS
    partes_solicitadas = Column(Text)

    # El codigo 1..5 con el que el area clasifica cada unidad del patio. Es lo
    # que alimenta las filas 4-8 de la hoja RESUMEN, y por eso es la clave para
    # poder reconstruir ese Excel desde la base:
    #   1 Por ingresar   2 Pendientes por compras   3 En reparacion
    #   4 Refacciones chinas   5 Talleres externos
    clasificacion = Column(Integer)
    area = Column(String(40))            # ALAMOS, ROSARITO
    origen = Column(String(16))          # 'REPARADO' | 'PATIO'

    unidad = relationship("Unidad")


CLASIFICACION = {
    1: "Unidades por Ingresar",
    2: "Pendientes por Compras",
    3: "Proceso Reparacion",
    4: "Refacciones chinas",
    5: "Talleres Externos",
}
