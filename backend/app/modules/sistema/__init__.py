"""Paquete H - Transversales: avisos, bitacora y configuracion."""
from .notificacion_model import Notificacion, AlertaGerencia  # noqa: F401
from .bitacora_model import BitacoraAuditoria  # noqa: F401
from .configuracion_model import Configuracion  # noqa: F401

__all__ = ["Notificacion", "AlertaGerencia", "BitacoraAuditoria", "Configuracion"]
