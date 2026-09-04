"""Paquete D - Mantenimiento preventivo y agenda.

Corresponde a TipoServicio del diagrama de clases.
"""
import math

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


class TipoServicio(Base):
    """Catalogo de servicios de taller.

    Ya NO se arranca a ciegas. `docs/analisis-detallado-taller.md` midio 869
    reparaciones reales de Alamos (2025-01 a 2026-08) y de ahi salen la
    mediana y el p90 con los que nace cada tipo. El sistema sigue aprendiendo:
    `recalibrar()` recalcula con las ordenes que va cerrando.

    DOS FLUJOS, y confundirlos rompe el calculo de capacidad. El taller atiende
    ~26 unidades al dia que entran y salen el mismo dia (NIVELES, ajustes,
    luces) y en paralelo repara unidades que se quedan dias o semanas. Solo las
    segundas ocupan un espacio del plano. Si la agenda las cuenta igual, con 31
    espacios el taller siempre aparece lleno y no se puede agendar nada.
    Por eso existe `ocupa_espacio`.
    """
    __tablename__ = "tipo_servicio"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(60), unique=True, nullable=False)
    criticidad = Column(Integer, default=2, nullable=False)  # 1=seguridad 2=preventivo 3=estetico
    duracion_estimada_dias = Column(Integer, default=1, nullable=False)

    # La MEDIANA es la que manda, no el promedio. La distribucion real tiene
    # una cola larguisima -- TRANSMISION va de 11 dias de mediana a 222 en el
    # p90 -- y con esa forma el promedio no describe ningun caso real.
    # `duracion_real_promedio` se conserva porque el diagrama de clases v2.0 la
    # nombra y porque sirve para estimar costo, pero NO se usa para agendar.
    duracion_mediana_dias = Column(Float)
    duracion_p90_dias = Column(Integer)
    duracion_real_promedio = Column(Float)
    muestras_medidas = Column(Integer, default=0, nullable=False)

    # False = servicio de paso: entra y sale el mismo dia, no toma bahia.
    ocupa_espacio = Column(Boolean, default=True, nullable=False)
    # De donde salio la duracion con la que nacio el tipo. Sin esto, en seis
    # meses nadie sabe si un numero se midio o se invento.
    origen_duracion = Column(String(40), default="estimado", nullable=False)

    requiere_fosa = Column(Boolean, default=False)
    activo = Column(Boolean, default=True, nullable=False)

    MUESTRAS_MINIMAS = 10

    def duracion_a_usar(self) -> int:
        """Dias que hay que reservar para este servicio.

        Un servicio de paso devuelve 0: no bloquea el espacio de nadie.
        """
        if not self.ocupa_espacio:
            return 0
        if self.muestras_medidas >= self.MUESTRAS_MINIMAS and self.duracion_mediana_dias:
            # Hacia ARRIBA, no `round`. Reservar de menos suelta la bahia antes
            # de que la unidad salga y encima le mete otra cita; reservar de mas
            # solo desperdicia medio dia. Y `round` en Python redondea 6.5 a 6,
            # que es justo el lado malo del error.
            return max(1, math.ceil(self.duracion_mediana_dias))
        return self.duracion_estimada_dias

    def rango_a_usar(self) -> tuple[int, int]:
        """Rango honesto (tipico, pesimista) para proponerle una cita al chofer.

        Mientras haya pocas muestras la agenda propone rangos y no fechas
        exactas (modelo-clases.md §10). Con la cola que tiene la distribucion
        real, el p90 no es un adorno: una de cada diez unidades lo alcanza.
        """
        if not self.ocupa_espacio:
            return (0, 0)
        tipico = self.duracion_a_usar()
        return (tipico, max(tipico, self.duracion_p90_dias or tipico))

    def recalibrar(self, duraciones) -> bool:
        """Recalcula con las duraciones medidas. Devuelve si cambio algo.

        Se pide la lista completa y no un acumulado incremental porque la
        mediana no se puede actualizar sumando: hay que reordenar la muestra.
        """
        muestras = sorted(d for d in duraciones if d is not None and d >= 0)
        if not muestras:
            return False
        n = len(muestras)
        self.duracion_mediana_dias = float(
            muestras[n // 2] if n % 2 else (muestras[n // 2 - 1] + muestras[n // 2]) / 2)
        self.duracion_p90_dias = int(muestras[min(n - 1, int(n * 0.9))])
        self.duracion_real_promedio = sum(muestras) / n
        self.muestras_medidas = n
        self.origen_duracion = "medido:ordenes_cerradas"
        return True
