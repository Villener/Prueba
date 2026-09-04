"""Base declarativa y mixin de sellos de tiempo.

Vive aparte para que los modelos de cada dominio no dependan unos de
otros solo por heredar de Base.
"""
from sqlalchemy import Column

from .database import Base
from .tiempo import UTCDateTime, ahora_utc


def _now():
    """El unico reloj del sistema (ver app/tiempo.py)."""
    return ahora_utc()


class TimestampMixin:
    creado_en = Column(UTCDateTime, default=_now, nullable=False)
    actualizado_en = Column(UTCDateTime, default=_now, onupdate=_now, nullable=False)


__all__ = ["Base", "TimestampMixin", "_now"]
