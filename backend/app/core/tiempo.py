"""Manejo de fecha y hora del sistema.

REGLA UNICA: la base de datos y la API hablan UTC. La pantalla habla Tijuana.
Nunca al reves, y nunca un offset fijo: Baja California cambia de UTC-7 (verano)
a UTC-8 (invierno), asi que sumar o restar horas a mano falla dos veces al ano.

El defecto que esto corrige: `datetime.utcnow()` devuelve la hora UTC pero SIN
marca de zona (naive). Al guardarse y serializarse sin offset, el navegador la
interpreta como hora local y la corre varias horas.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
    TZ_OPERACION = ZoneInfo("America/Tijuana")
except Exception:  # pragma: no cover - entorno sin base de datos de zonas
    TZ_OPERACION = timezone.utc


def ahora_utc() -> datetime:
    """El unico reloj del sistema. Siempre con zona, siempre UTC."""
    return datetime.now(timezone.utc)


def a_utc(valor: datetime) -> datetime:
    """Normaliza a UTC. Un naive se asume UTC (es lo que guardamos)."""
    if valor is None:
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def a_tijuana(valor: datetime) -> datetime:
    """Solo para presentacion y para cortes del dia operativo."""
    if valor is None:
        return None
    return a_utc(valor).astimezone(TZ_OPERACION)


def dia_operativo(valor: datetime) -> "datetime.date":
    """La fecha a la que pertenece un instante segun el calendario del taller.

    Se calcula en Tijuana, no en UTC: a las 17:30 del 18 de agosto en Tijuana
    ya son las 00:30 del 19 en UTC, y ese registro pertenece al dia 18.
    """
    return a_tijuana(valor).date()


class UTCDateTime(TypeDecorator):
    """Columna de fecha-hora que SIEMPRE entrega un datetime con zona UTC.

    Es portable a proposito. PostgreSQL guarda TIMESTAMPTZ y hace el trabajo
    solo; SQLite no sabe de zonas, asi que ahi se guarda UTC sin marca y se le
    vuelve a poner al leer. Sin esto, el mismo codigo se comporta distinto en
    la maquina de desarrollo (SQLite) y en el servidor (PostgreSQL), que es la
    peor clase de defecto: el que no se reproduce.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(DateTime(timezone=True))
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        value = a_utc(value)
        if dialect.name == "postgresql":
            return value
        return value.replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
