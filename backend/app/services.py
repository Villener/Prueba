"""FACHADA de servicios.

Las reglas de negocio viven en app/modules/<dominio>/<dominio>_service.py.
Este archivo solo las reexporta para que los controllers puedan seguir
usando `from ... import services as svc`.
"""
from .modules.sistema.comun_service import (  # noqa: F401
    siguiente_folio, nombre_chofer, nombre_usuario,
)
from .modules.flota.flota_service import (  # noqa: F401
    prestamo_activo, poseedor_actual, sincronizar_poseedor,
    validar_puede_prestar, unidad_out, prestamo_out,
)
from .modules.taller.taller_service import (  # noqa: F401
    espacios_libres_compatibles, ocupacion_abierta_de_unidad, ocupacion_abierta_de_espacio,
    solicitud_out, asignacion_out, orden_out, reporte_out, atendido_por,
    crear_reporte_mantenimiento, reporte_abierto_de_unidad,
    orden_abierta_de_unidad, sacar_del_taller,
)
from .modules.mantenimiento.mantenimiento_service import (  # noqa: F401
    mantenimiento_out,
)
from .modules.mantenimiento.agenda_service import (  # noqa: F401
    capacidad_libre, recalcular, detectar_sin_cupo, cita_out, opera,
    HORIZONTE_DIAS,
)
from .modules.piezas.piezas_service import (  # noqa: F401
    presupuesto_out,
)
from .modules.emergencias.emergencias_service import (  # noqa: F401
    puede_solicitar_arrastre, averia_out, arrastre_out,
)
