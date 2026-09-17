"""Esquemas Pydantic de entrada y salida de la API."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class ORMModel(BaseModel):
    model_config = {"from_attributes": True}


# ------------------------------------------------------------------ auth ---- #
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: "UsuarioOut"


class UsuarioOut(ORMModel):
    id: int
    nombre: str
    apellidos: str
    email: str
    telefono: Optional[str] = None
    activo: bool
    roles: List[str] = []


# ----------------------------------------------------------------- flota ---- #
class UnidadOut(ORMModel):
    id: int
    num_economico: str
    placas: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    tipo: Optional[str] = None
    estado: str
    km_actual: Optional[int] = 0
    titular: Optional[str] = None
    poseedor: Optional[str] = None
    es_prestada: bool = False
    taller_actual: Optional[str] = None


class MantenimientoOut(ORMModel):
    id: int
    plan: str
    fecha_limite: date
    km_programado: Optional[int] = None
    estado: str
    dias_restantes: int
    vencido: bool


class PrestamoIn(BaseModel):
    unidad_id: int
    chofer_recibe_id: int
    motivo: str = Field(pattern="^(vacaciones|incapacidad|apoyo|otro)$")
    fecha_fin_prevista: date


class PrestamoOut(ORMModel):
    id: int
    unidad: str
    chofer_presta: str
    chofer_recibe: str
    motivo: str
    estado: str
    fecha_solicitud: datetime
    fecha_fin_prevista: date
    fecha_fin_real: Optional[datetime] = None
    vencido: bool = False


class PenalizacionOut(ORMModel):
    id: int
    unidad: str
    chofer: str
    motivo: str
    fecha_generacion: date
    dias_atraso: int
    estado: str


# ---------------------------------------------------------------- taller ---- #
class SolicitudIn(BaseModel):
    unidad_id: int
    taller_id: int
    tipo: str = "correctivo"
    descripcion_falla: str
    urgencia: str = Field(default="media", pattern="^(baja|media|alta|critica)$")


class SolicitudOut(ORMModel):
    id: int
    unidad: str
    chofer: str
    taller: str
    taller_id: int
    tipo: str
    descripcion_falla: Optional[str] = None
    urgencia: str
    estado: str
    fecha_solicitud: datetime
    motivo_rechazo: Optional[str] = None
    espacios_libres_compatibles: int = 0
    # A donde sigue el trabajo despues de aceptar. Al dar acceso al vehiculo se
    # abre su formato (CU-ADM-26); sin este dato la pantalla tendria que
    # buscarlo por su cuenta para poder llevar al administrador ahi.
    orden_folio: Optional[str] = None
    reporte_id: Optional[int] = None
    reporte_folio: Optional[str] = None


class ResolucionSolicitudIn(BaseModel):
    aceptar: bool
    espacio_id: Optional[int] = None
    motivo_rechazo: Optional[str] = None
    dejar_en_cola: bool = False


class EspacioOut(ORMModel):
    id: int
    numero: str
    zona: str
    estado: str
    tipo_permitido: Optional[str] = None
    unidad: Optional[str] = None
    orden_servicio_id: Optional[int] = None
    dias_ocupado: Optional[int] = None
    pos_x: int = 0
    pos_y: int = 0


class ZonaOut(ORMModel):
    id: int
    nombre: str
    proposito: str
    cuenta_para_ocupacion: bool
    espacios: List[EspacioOut] = []


class TallerOut(ORMModel):
    id: int
    nombre: str
    direccion: Optional[str] = None
    zonas: List[ZonaOut] = []
    total_operativos: int = 0
    ocupados: int = 0
    libres: int = 0


class AsignacionTecnicoIn(BaseModel):
    tecnico_id: int
    especialidad: Optional[str] = None


class AsignacionTecnicoOut(ORMModel):
    id: int
    tecnico: str
    especialidad: Optional[str] = None
    orden_en_cola: int
    estado: str
    diagnostico: Optional[str] = None
    trabajo_realizado: Optional[str] = None
    capturado_por: Optional[str] = None
    fecha_captura: Optional[datetime] = None


class CapturaDiagnosticoIn(BaseModel):
    diagnostico: str


class AvanceIn(BaseModel):
    estado: str = Field(pattern="^(en_espera|en_proceso|pausada|terminada)$")
    trabajo_realizado: Optional[str] = None


class OrdenServicioOut(ORMModel):
    id: int
    folio: str
    unidad: str
    taller: str
    estado: str
    tipo: str
    fecha_entrada: datetime
    fecha_salida: Optional[datetime] = None
    dias_en_taller: int = 0
    espacio: Optional[str] = None
    asignaciones: List[AsignacionTecnicoOut] = []


class FormatoSalidaIn(BaseModel):
    """El formato que se le entrega al chofer al sacar la unidad.

    Ya NO pide kilometraje ni observaciones: el cliente los quito del formato.
    Y `trabajos_realizados` paso a ser la operacion A REALIZAR -- el formato se
    llena cuando la unidad SALE hacia el trabajo, no despues de hacerlo, asi
    que pedirlo en pasado obligaba a inventar.
    """
    operacion_a_realizar: str
    unidad_operativa: bool = True


# ------------------------------------------- reporte de mantenimiento ------ #
# El formato de papel de Alamos. Los `pattern` no son adorno: son la unica
# defensa contra que la pantalla mande un estado que despues nadie sabe leer,
# y el catalogo real vive en modules/ordenes/reporte_model.py.
class PuntoRevisionIn(BaseModel):
    punto: str
    estado: str = Field(default="sin_revisar",
                        pattern="^(bien|mal|no_aplica|sin_revisar)$")
    observacion: Optional[str] = None


class PuntoRevisionOut(ORMModel):
    punto: str
    etiqueta: str
    estado: str
    observacion: Optional[str] = None


class ActividadReporteIn(BaseModel):
    sistema: str
    a_realizar: Optional[str] = None
    realizada: Optional[str] = None
    tecnico_id: Optional[int] = None


class ActividadReporteOut(ORMModel):
    id: int
    sistema: str
    etiqueta: str
    a_realizar: Optional[str] = None
    realizada: Optional[str] = None
    tecnico_id: Optional[int] = None
    tecnico: Optional[str] = None
    fecha_realizada: Optional[datetime] = None
    capturado_por: Optional[str] = None


class FirmaReporteIn(BaseModel):
    rol_firma: str = Field(
        pattern="^(entrega_taller|valida_trabajo|recepcion_pluma|"
                "vobo_mantenimiento|recibe_salida)$")
    # El nombre es obligatorio: una firma sin nombre no es constancia de nada.
    nombre: str = Field(min_length=2, max_length=120)
    usuario_id: Optional[int] = None


class FirmaReporteOut(ORMModel):
    rol_firma: str
    etiqueta: str
    quien: str
    nombre: Optional[str] = None
    fecha: Optional[datetime] = None
    registrada_por: Optional[str] = None


class ReporteMantenimientoIn(BaseModel):
    """Lo que se teclea al recibir la unidad en la pluma.

    `puntos` y `actividades` pueden venir vacios: el servidor siembra los 11
    puntos y los 10 sistemas del formato para que la pantalla siempre pinte la
    hoja completa, aunque el papel llegue a medio llenar.
    """
    unidad_id: int
    taller_id: int
    orden_servicio_id: Optional[int] = None
    tipo_servicio: str = Field(default="correctivo", pattern="^(correctivo|preventivo)$")
    origen: Optional[str] = None
    kilometraje: Optional[int] = Field(default=None, ge=0)
    area: Optional[str] = Field(
        default=None,
        pattern="^(reparto|pipas|utilitarias|operaciones|ventas|otros)$")
    area_otro: Optional[str] = None
    chofer_id: Optional[int] = None
    chofer_nombre: Optional[str] = None
    supervisor_nombre: Optional[str] = None
    fecha_entrada: Optional[datetime] = None
    nivel_combustible: Optional[str] = Field(
        default=None, pattern="^(vacio|1/4|1/2|3/4|lleno)$")
    notas_ingreso: Optional[str] = None
    puntos: List[PuntoRevisionIn] = []
    actividades: List[ActividadReporteIn] = []


class ActividadesIn(BaseModel):
    """Actualiza la tabla central. Solo llegan los sistemas que cambiaron."""
    actividades: List[ActividadReporteIn] = []
    comentarios_adicionales: Optional[str] = None


class ReasignacionIn(BaseModel):
    """Cambia el responsable de un sistema del formato.

    `motivo` es obligatorio a proposito. Una reasignacion sin motivo es
    indistinguible de una correccion de dedo, y son cosas distintas: la primera
    hay que poder explicarla, la segunda no.
    """
    sistema: str
    tecnico_id: Optional[int] = None   # None = dejarlo sin asignar
    motivo: str = Field(min_length=4, max_length=200)


class CierreReporteIn(BaseModel):
    """Cerrar el formato ES sacar la unidad del taller (v1.3).

    Por eso hereda los dos campos que antes pedia el formato de salida: si la
    unidad sale operativa, y que va a hacer al salir. Tenerlos en dos pantallas
    distintas dejaba la unidad a medio salir.
    """
    fecha_salida: Optional[datetime] = None
    comentarios_adicionales: Optional[str] = None
    unidad_operativa: bool = True
    operacion_a_realizar: Optional[str] = None


class ReporteMantenimientoOut(ORMModel):
    id: int
    folio: str
    orden_servicio_id: Optional[int] = None
    orden_folio: Optional[str] = None
    unidad_id: int
    unidad: str
    unidad_placas: Optional[str] = None
    taller_id: int
    taller: str
    tipo_servicio: str
    origen: Optional[str] = None
    kilometraje: Optional[int] = None
    area: Optional[str] = None
    area_otro: Optional[str] = None
    chofer_id: Optional[int] = None
    chofer_nombre: Optional[str] = None
    supervisor_nombre: Optional[str] = None
    fecha_entrada: datetime
    fecha_salida: Optional[datetime] = None
    horas_en_taller: float = 0
    nivel_combustible: Optional[str] = None
    notas_ingreso: Optional[str] = None
    comentarios_adicionales: Optional[str] = None
    estado: str
    espacio: Optional[str] = None
    colocado_por: Optional[str] = None
    atendido_por: List[dict] = []
    capturado_por: Optional[str] = None
    fecha_captura: Optional[datetime] = None
    firmas_faltantes: List[str] = []
    puntos: List[PuntoRevisionOut] = []
    actividades: List[ActividadReporteOut] = []
    firmas: List[FirmaReporteOut] = []


class CatalogoReporteOut(BaseModel):
    """Los catalogos del formato, servidos por el backend.

    La pantalla NO los lleva escritos: si el papel cambia, cambia en un solo
    lugar y las dos capas siguen de acuerdo.
    """
    sistemas: List[dict] = []
    puntos: List[dict] = []
    firmas: List[dict] = []
    areas: List[str] = []
    niveles_combustible: List[str] = []
    estados_punto: List[str] = []
    tipos_servicio: List[str] = []


# ---------------------------------------------------------- presupuestos ---- #
class DetallePresupuestoIn(BaseModel):
    pieza_id: Optional[int] = None
    descripcion_libre: Optional[str] = None
    cantidad: float = 1
    precio_unitario: float = 0
    disponible_en_almacen: bool = False


class PresupuestoIn(BaseModel):
    """Lo captura el ADMINISTRADOR a partir del papel que entrega el mecanico."""
    orden_servicio_id: int
    tecnico_elaboro_id: int
    fecha_elaboracion: date
    folio_papel: Optional[str] = None
    costo_mano_obra: float = 0
    diagnostico: Optional[str] = None
    dias_estimados_reparacion: Optional[int] = None
    detalles: List[DetallePresupuestoIn] = []


class DetallePresupuestoOut(ORMModel):
    id: int
    pieza: Optional[str] = None
    descripcion_libre: Optional[str] = None
    cantidad: float
    precio_unitario: float
    importe: float
    disponible_en_almacen: bool


class AutorizacionOut(ORMModel):
    id: int
    usuario: str
    nivel: str
    resultado: str
    fecha: datetime
    comentario: Optional[str] = None


class PresupuestoOut(ORMModel):
    id: int
    folio: str
    orden_folio: str
    unidad: str
    tecnico_elaboro: str
    capturado_por: str
    fecha_elaboracion: Optional[date] = None
    fecha_captura: datetime
    dias_retraso_captura: Optional[int] = None
    costo_mano_obra: float
    subtotal_piezas: float
    total: float
    estado: str
    diagnostico: Optional[str] = None
    fecha_aviso_al_tecnico: Optional[datetime] = None
    detalles: List[DetallePresupuestoOut] = []
    autorizaciones: List[AutorizacionOut] = []


class ResolucionPresupuestoIn(BaseModel):
    resultado: str = Field(pattern="^(aprobado|rechazado|devuelto)$")
    comentario: Optional[str] = None


# ------------------------------------------------------------ emergencia ---- #
class AveriaIn(BaseModel):
    unidad_id: int
    # Opcionales A PROPOSITO. Antes eran obligatorias y el formulario, cuando el
    # navegador negaba el GPS, mandaba en silencio las coordenadas del taller de
    # Alamos. Asi quedo AVE-2026-00005: dice estar en el taller y en realidad
    # nadie sabe donde estaba. Una averia sin ubicacion sirve mucho mas que una
    # averia con la ubicacion equivocada.
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    descripcion_falla: str
    direccion_referencia: Optional[str] = None
    en_vialidad_publica: bool = False
    hay_terceros_involucrados: bool = False
    requiere_arrastre: bool = False


class PeritajeIn(BaseModel):
    folio_peritos: str
    aseguradora: Optional[str] = None
    nombre_perito: Optional[str] = None
    observaciones: Optional[str] = None


class AveriaOut(ORMModel):
    id: int
    folio: str
    unidad: str
    chofer: str
    fecha_hora: datetime
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    descripcion_falla: Optional[str] = None
    en_vialidad_publica: bool
    estado: str
    tiene_peritaje: bool = False
    folio_peritos: Optional[str] = None
    puede_solicitar_arrastre: bool = False   # RN-04
    arrastre_id: Optional[int] = None
    arrastre_estado: Optional[str] = None
    # Desenlace del despacho (v1.4). Ausente mientras nadie haya decidido.
    fotos: list = []
    desenlace: Optional[str] = None
    desenlace_texto: Optional[str] = None
    despachado_por: Optional[str] = None
    fecha_despacho: Optional[datetime] = None
    nota_despacho: Optional[str] = None


class ArrastreOut(ORMModel):
    id: int
    folio: str
    unidad: str
    chofer_responsable: Optional[str] = None
    chofer_grua: Optional[str] = None
    taller_destino: Optional[str] = None
    estado: str
    fecha_solicitud: datetime
    fecha_finalizacion: Optional[datetime] = None
    latitud_origen: Optional[float] = None
    longitud_origen: Optional[float] = None
    ultima_lat: Optional[float] = None
    ultima_lng: Optional[float] = None
    ultima_actualizacion: Optional[datetime] = None


class UbicacionIn(BaseModel):
    latitud: float
    longitud: float


class CierreArrastreIn(BaseModel):
    taller_destino_id: int
    km_recorridos: Optional[float] = None
    observaciones: Optional[str] = None


# --------------------------------------------------------------- gerente ---- #
class KpiOut(BaseModel):
    unidades_total: int
    unidades_en_taller: int
    unidades_en_ruta: int
    unidades_varadas: int
    ocupacion_pct: float
    espacios_ocupados: int
    espacios_totales: int
    choferes_incumpliendo: int
    # Antes "penalizaciones_mes". La palabra la elimino la v2.0 y seguia aqui.
    avisos_mes: int
    presupuestos_pendientes: int
    piezas_en_camino: int
    alertas_abiertas: int
    unidades_atendidas_periodo: int
    retraso_captura_promedio: Optional[float] = None


class IncumplimientoOut(BaseModel):
    chofer: str
    chofer_id: int
    unidad: str
    plan: str
    fecha_limite: date
    dias_atraso: int
    es_poseedor_por_prestamo: bool


class AlertaOut(ORMModel):
    id: int
    tipo: str
    unidad: Optional[str] = None
    detalle: Optional[str] = None
    fecha_generacion: datetime
    veces_notificada: int
    atendida: bool


class NotificacionOut(ORMModel):
    id: int
    titulo: str
    mensaje: Optional[str] = None
    tipo: Optional[str] = None
    leida: bool
    fecha_envio: datetime


class MensajeOut(BaseModel):
    ok: bool = True
    mensaje: str


# ----------------------------------------------------------------- agenda --- #
class RangoDuracionOut(BaseModel):
    """Rango honesto en vez de una fecha con precision fingida.

    Mientras la muestra sea chica la agenda propone un intervalo. Con la cola
    que tiene la distribucion real, el pesimista no es adorno: una de cada diez
    unidades lo alcanza.
    """
    tipico: int
    pesimista: int


class CitaOut(ORMModel):
    id: int
    unidad: str
    unidad_id: Optional[int] = None
    # Lo necesita el calendario: la capacidad se consulta POR TIPO de unidad,
    # nunca en total.
    tipo_unidad_id: Optional[int] = None
    taller: str
    taller_id: Optional[int] = None
    servicio: str
    fecha_cita: date
    # Viene del plan y NUNCA se mueve. Que aparezca junto a fecha_cita es a
    # proposito: es lo que deja ver de un vistazo si la cita llega a tiempo.
    fecha_limite_origen: Optional[date] = None
    dias_de_holgura: Optional[int] = None
    estado: str
    duracion_estimada_dias: Optional[int] = None
    duracion_rango: RangoDuracionOut
    veces_reprogramada: int = 0
    score_prioridad: Optional[int] = None
    movible: bool
    confirmada_por_taller: bool = False
    confirmada_por_chofer: bool = False
    chofer: Optional[str] = None


class ReprogramarIn(BaseModel):
    fecha_nueva: date
    motivo: str = Field(
        default="solicitud_chofer",
        description="sin_espacio|unidad_atorada|urgencia_desplaza|solicitud_chofer")
    # Sobrecupo deliberado. Se pide explicito para que meter una unidad de mas
    # sea una decision con dueno y no un descuido: por omision se rechaza.
    forzar: bool = False


class SinCupoOut(BaseModel):
    """Un programa que no alcanza cita antes de su fecha limite.

    NO es incumplimiento del chofer: es capacidad del taller, y por eso va en
    una lista aparte y no en el tablero de incumplimientos.
    """
    programa_id: int
    unidad: str
    servicio: str
    fecha_limite: date
    dias_vencido: int
    taller: str


class CapacidadDiaOut(BaseModel):
    fecha: date
    opera: bool
    libres: int


class CapacidadOut(BaseModel):
    taller: str
    tipo_unidad: str
    horizonte_dias: int
    dias: List[CapacidadDiaOut]


class RecalculoOut(BaseModel):
    propuestas: int
    movidas: int
    sin_cupo: int

# ---------------------------------------------------------- requisiciones ---- #
class RenglonRequisicionIn(BaseModel):
    """Un material del papel.

    `pieza_id` es opcional: el papel trae codigos que no siempre estan en el
    catalogo, y perder el renglon por eso seria peor que guardarlo sin casar.
    """
    pieza_id: Optional[int] = None
    codigo: Optional[str] = None
    descripcion: str = Field(min_length=2, max_length=200)
    cantidad: int = Field(default=1, ge=1, le=9999)


class RequisicionIn(BaseModel):
    folio: str = Field(min_length=2, max_length=24)
    fecha: date
    unidad_id: Optional[int] = None
    unidad_texto: Optional[str] = None
    tecnico_id: Optional[int] = None
    solicitante_num_empleado: Optional[str] = None
    solicitante_nombre: Optional[str] = None
    equipo_sap: Optional[str] = None
    centro_gestion: Optional[str] = None
    observaciones: Optional[str] = None
    renglones: List[RenglonRequisicionIn] = Field(min_length=1)
    # Guardar aunque ya exista una requisicion con el mismo folio, fecha y
    # unidad. Se pide explicito porque en el libro real eso pasa de verdad, y
    # tambien pasa que alguien teclee el mismo papel dos veces: solo quien
    # tiene el papel enfrente puede distinguirlo.
    forzar: bool = False


class RenglonRequisicionOut(ORMModel):
    id: int
    linea: int
    pieza_id: Optional[int] = None
    codigo: Optional[str] = None
    descripcion: str
    cantidad: int
    # Falso cuando el codigo del papel no existe en el catalogo. La pantalla lo
    # marca para que el capturista sepa cual reconciliar; no lo bloquea.
    en_catalogo: bool = False


class RequisicionOut(ORMModel):
    id: int
    folio: str
    fecha: date
    unidad: Optional[str] = None
    unidad_id: Optional[int] = None
    equipo_sap: Optional[str] = None
    centro_gestion: Optional[str] = None
    solicitante: Optional[str] = None
    solicitante_num_empleado: Optional[str] = None
    taller: Optional[str] = None
    estado: str
    origen: str
    capturada_por: Optional[str] = None
    fecha_captura: Optional[datetime] = None
    observaciones: Optional[str] = None
    total_renglones: int = 0
    total_piezas: int = 0
    renglones: List[RenglonRequisicionOut] = []


TokenOut.model_rebuild()


# ------------------------------------------------------------- CU-ADM-30 -- #
class DespachoIn(BaseModel):
    """Lo que el administrador decide cuando ve una unidad varada."""
    tipo: str                                   # telefono|llantero|mecanico|grua
    tecnico_id: Optional[int] = None            # obligatorio en llantero y mecanico
    chofer_grua_id: Optional[int] = None        # opcional en grua: si no, se difunde
    taller_destino_id: Optional[int] = None
    nota: Optional[str] = None


class ApoyoTecnicoOut(BaseModel):
    id: int
    nombre: str
    especialidad: str
    modalidad: str
    taller: Optional[str] = None
    telefono: Optional[str] = None
    km: Optional[float] = None
    sale_a_carretera: bool
    vehiculo_en_taller: bool = False


class ApoyoGruaOut(BaseModel):
    usuario_id: int
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    grua: Optional[str] = None
    grua_desconocida: bool = False
    libre: bool
    motivo: Optional[str] = None


class TallerCercaOut(BaseModel):
    id: int
    nombre: str
    km: Optional[float] = None


class ApoyoOut(BaseModel):
    """Todo lo que el administrador necesita para decidir, en una sola llamada."""
    tecnicos: list[ApoyoTecnicoOut] = []
    gruas: list[ApoyoGruaOut] = []
    talleres: list[TallerCercaOut] = []


class ChoqueIn(BaseModel):
    """RN-16: lo que se captura al reportar un CHOQUE.

    No reusa AveriaIn a proposito. Un choque no tiene "descripcion de falla":
    tiene danos, terceros y un parte de accidente. Meterlos en el mismo
    formulario obligaba al chofer a describir un impacto en un campo de falla,
    y dejaba al gerente sin poder contar cuantos choques hubo en el ano.
    """
    unidad_id: int
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    direccion_referencia: Optional[str] = None
    descripcion_danos: str
    hay_lesionados: bool = False
    cuantos_terceros: int = 0
    datos_terceros: Optional[str] = None
    unidad_puede_circular: bool = False
    en_vialidad_publica: bool = True
