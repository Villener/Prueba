"""FACHADA del modelo de datos.

Las clases ya NO viven aqui: estan en app/modules/<dominio>/, un paquete
por cada paquete del diagrama de clases (docs/modelo-clases.md). Este
archivo solo las reexporta para que `from .. import models as m` siga
funcionando y para que SQLAlchemy las registre TODAS antes de create_all.
"""
from sqlalchemy import Index

from .core.base_model import Base, TimestampMixin, _now  # noqa: F401

# Paquete A - Organizacion, plantas y personas
from .modules.organizacion import (  # noqa: F401
    Planta, Taller, Usuario, Rol,
    UsuarioRol, Chofer, Supervisor, ChoferGrua,
    LimiteAutorizacion, Plantilla, Tecnico,
)

# Paquete B - Flota y responsabilidad
from .modules.flota import (  # noqa: F401
    TipoUnidad, Unidad, ESTADOS_UNIDAD, AsignacionUnidad,
    PrestamoUnidad, Jornada, UbicacionUnidad,
)

# Paquete C - Taller: zonas, espacios y ocupacion
from .modules.taller import (  # noqa: F401
    ZonaTaller, Espacio, OcupacionEspacio,
)

# Paquete D - Mantenimiento preventivo y agenda
from .modules.mantenimiento import (  # noqa: F401
    PlanMantenimiento, ProgramaMantenimiento, TipoServicio, CitaTaller,
    ESTADOS_CITA, Reprogramacion, AvisoIncumplimiento, Penalizacion,
)

# Paquete E - Orden de servicio, reporte de mantenimiento y traslados
from .modules.ordenes import (  # noqa: F401
    SolicitudIngreso, OrdenServicio, AsignacionTecnico, FormatoSalida,
    ReporteMantenimiento, PuntoRevision, ActividadReporte, FirmaReporte,
    MovimientoTaller,
    SISTEMAS, PUNTOS_REVISION, ESTADOS_PUNTO, NIVELES_COMBUSTIBLE, AREAS,
    TIPOS_SERVICIO, FIRMAS, FIRMAS_OBLIGATORIAS_SALIDA,
    TrasladoUnidad,
)

# Paquete F - Piezas, almacen y compras
from .modules.piezas import (  # noqa: F401
    Pieza, Existencia, SolicitudPieza, ESTADOS_SOLICITUD_PIEZA,
    Presupuesto, DetallePresupuesto, Autorizacion, Proveedor,
    OrdenCompra, Requisicion, RenglonRequisicion, ESTADOS_REQUISICION,
)

# Paquete G - Averias, auxilio en carretera y arrastre
from .modules.emergencias import (  # noqa: F401
    ReporteAveria, ReportePeritaje, OrdenAuxilio, ESTADOS_AUXILIO,
    DifusionAuxilio, RespuestaAuxilio, Arrastre, UbicacionArrastre,
    Evidencia,
)

# Paquete H - Transversales: avisos, bitacora y configuracion
from .modules.sistema import (  # noqa: F401
    Notificacion, AlertaGerencia, BitacoraAuditoria, Configuracion,
)

# ---------------------------------------------------------------------------

Index("uq_orden_abierta_por_unidad", OrdenServicio.unidad_id, unique=True,
      sqlite_where=OrdenServicio.fecha_salida.is_(None),
      postgresql_where=OrdenServicio.fecha_salida.is_(None))

Index("uq_ocupacion_abierta_por_unidad", OcupacionEspacio.unidad_id, unique=True,
      sqlite_where=OcupacionEspacio.fecha_salida.is_(None),
      postgresql_where=OcupacionEspacio.fecha_salida.is_(None))

Index("uq_ocupacion_abierta_por_espacio", OcupacionEspacio.espacio_id, unique=True,
      sqlite_where=OcupacionEspacio.fecha_salida.is_(None),
      postgresql_where=OcupacionEspacio.fecha_salida.is_(None))

# Un formato de mantenimiento vivo por unidad. El controller ya lo valida, pero
# dos peticiones simultaneas pueden pasar la validacion a la vez: el candado
# tiene que estar en la base, igual que para la orden de servicio.
Index("uq_reporte_abierto_por_unidad", ReporteMantenimiento.unidad_id, unique=True,
      sqlite_where=ReporteMantenimiento.fecha_salida.is_(None),
      postgresql_where=ReporteMantenimiento.fecha_salida.is_(None))
