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
    tipo: str
    descripcion_falla: Optional[str] = None
    urgencia: str
    estado: str
    fecha_solicitud: datetime
    motivo_rechazo: Optional[str] = None
    espacios_libres_compatibles: int = 0


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
    km_salida: int
    trabajos_realizados: str
    observaciones: Optional[str] = None
    unidad_operativa: bool = True


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
    latitud: float
    longitud: float
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


class ArrastreOut(ORMModel):
    id: int
    folio: str
    unidad: str
    chofer_responsable: Optional[str] = None
    montacarguista: Optional[str] = None
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
    penalizaciones_mes: int
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


TokenOut.model_rebuild()
