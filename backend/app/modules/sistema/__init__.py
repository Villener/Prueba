"""Paquete H - Transversales: avisos, bitacora y configuracion."""
from .notificacion_model import Notificacion, AlertaGerencia, SuscripcionPush  # noqa: F401
from .bitacora_model import BitacoraAuditoria  # noqa: F401
from .configuracion_model import Configuracion  # noqa: F401

__all__ = ["Notificacion", "AlertaGerencia", "SuscripcionPush", "BitacoraAuditoria", "Configuracion"]
