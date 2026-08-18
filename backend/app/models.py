"""Modelo de datos - implementa docs/modelo-er.md v1.1.

Nota de diseno (v1.1): TECNICO NO es una especializacion de USUARIO. Los mecanicos,
carroceros y electricistas no usan la aplicacion; existen como catalogo asignable y
la FK opcional `usuario_id` queda lista por si alguno recibe acceso mas adelante.
"""
from datetime import datetime

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from .database import Base


def _now():
    return datetime.utcnow()


class TimestampMixin:
    creado_en = Column(DateTime, default=_now, nullable=False)
    actualizado_en = Column(DateTime, default=_now, onupdate=_now, nullable=False)


# --------------------------------------------------------------------------- #
# AREA A - Personas y organizacion
# --------------------------------------------------------------------------- #
class Usuario(Base, TimestampMixin):
    __tablename__ = "usuario"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False)
    apellidos = Column(String(120), nullable=False)
    email = Column(String(160), unique=True, nullable=False, index=True)
    telefono = Column(String(30))
    password_hash = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_alta = Column(DateTime, default=_now)

    roles = relationship("UsuarioRol", back_populates="usuario", cascade="all, delete-orphan")
    chofer = relationship("Chofer", back_populates="usuario", uselist=False)
    supervisor = relationship("Supervisor", back_populates="usuario", uselist=False)
    montacarguista = relationship("Montacarguista", back_populates="usuario", uselist=False)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"

    @property
    def lista_roles(self):
        return [ur.rol.nombre for ur in self.roles]


class Rol(Base):
    __tablename__ = "rol"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(40), unique=True, nullable=False)
    descripcion = Column(String(200))


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"
    usuario_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    rol_id = Column(Integer, ForeignKey("rol.id"), primary_key=True)
    vigente_desde = Column(DateTime, default=_now)
    vigente_hasta = Column(DateTime)

    usuario = relationship("Usuario", back_populates="roles")
    rol = relationship("Rol")


class Cuadrilla(Base, TimestampMixin):
    __tablename__ = "cuadrilla"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False)
    supervisor_id = Column(Integer, ForeignKey("supervisor.usuario_id"))
    activa = Column(Boolean, default=True)

    supervisor = relationship("Supervisor", back_populates="cuadrillas")
    choferes = relationship("Chofer", back_populates="cuadrilla")


class Chofer(Base):
    __tablename__ = "chofer"
    usuario_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    num_licencia = Column(String(40), unique=True)
    tipo_licencia = Column(String(20))
    vencimiento_licencia = Column(Date)
    cuadrilla_id = Column(Integer, ForeignKey("cuadrilla.id"))
    disponible = Column(Boolean, default=True)

    usuario = relationship("Usuario", back_populates="chofer")
    cuadrilla = relationship("Cuadrilla", back_populates="choferes")


class Supervisor(Base):
    __tablename__ = "supervisor"
    usuario_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    zona = Column(String(80))

    usuario = relationship("Usuario", back_populates="supervisor")
    cuadrillas = relationship("Cuadrilla", back_populates="supervisor")


class Montacarguista(Base):
    __tablename__ = "montacarguista"
    usuario_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    unidad_grua_id = Column(Integer, ForeignKey("unidad.id"))
    licencia_especial = Column(String(40))
    en_servicio = Column(Boolean, default=True)

    usuario = relationship("Usuario", back_populates="montacarguista")


class Tecnico(Base, TimestampMixin):
    """Catalogo. NO es usuario del sistema (v1.1)."""
    __tablename__ = "tecnico"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False)
    apellidos = Column(String(120), nullable=False)
    num_empleado = Column(String(30), unique=True)
    especialidad = Column(String(30), nullable=False)  # mecanico|carrocero|electricista|llantero
    taller_id = Column(Integer, ForeignKey("taller.id"))
    telefono = Column(String(30))
    disponible = Column(Boolean, default=True)
    activo = Column(Boolean, default=True)
    # FK opcional: queda lista por si algun tecnico recibe acceso al sistema.
    usuario_id = Column(Integer, ForeignKey("usuario.id"), unique=True, nullable=True)

    taller = relationship("Taller", back_populates="tecnicos")

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"


# --------------------------------------------------------------------------- #
# AREA B - Flota y responsabilidad
# --------------------------------------------------------------------------- #
class TipoUnidad(Base):
    __tablename__ = "tipo_unidad"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(40), unique=True, nullable=False)
    descripcion = Column(String(200))


class Unidad(Base, TimestampMixin):
    __tablename__ = "unidad"
    id = Column(Integer, primary_key=True)
    num_economico = Column(String(20), unique=True, nullable=False)
    placas = Column(String(20), unique=True)
    vin = Column(String(40), unique=True)
    marca = Column(String(60))
    modelo = Column(String(60))
    anio = Column(Integer)
    tipo_unidad_id = Column(Integer, ForeignKey("tipo_unidad.id"), nullable=False)
    titular_chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    poseedor_chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))  # RN-01
    estado = Column(String(24), default="disponible", nullable=False)
    km_actual = Column(Integer, default=0)
    taller_actual_id = Column(Integer, ForeignKey("taller.id"))
    fecha_alta = Column(Date)

    tipo = relationship("TipoUnidad")
    titular = relationship("Chofer", foreign_keys=[titular_chofer_id])
    poseedor = relationship("Chofer", foreign_keys=[poseedor_chofer_id])


ESTADOS_UNIDAD = ["disponible", "en_ruta", "varada", "en_arrastre", "en_taller",
                  "en_reparacion", "lista", "baja"]


class AsignacionUnidad(Base):
    __tablename__ = "asignacion_unidad"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    fecha_inicio = Column(DateTime, default=_now)
    fecha_fin = Column(DateTime)
    asignado_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    motivo = Column(String(200))


class PrestamoUnidad(Base, TimestampMixin):
    """Relacion reflexiva sobre CHOFER con atributos propios."""
    __tablename__ = "prestamo_unidad"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_presta_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    chofer_recibe_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    motivo = Column(String(30), nullable=False)  # vacaciones|incapacidad|apoyo|otro
    fecha_solicitud = Column(DateTime, default=_now)
    fecha_aceptacion = Column(DateTime)
    fecha_inicio = Column(DateTime)
    fecha_fin_prevista = Column(Date, nullable=False)
    fecha_fin_real = Column(DateTime)
    estado = Column(String(20), default="solicitado", nullable=False)
    autorizado_por_supervisor_id = Column(Integer, ForeignKey("supervisor.usuario_id"))
    motivo_rechazo = Column(String(200))

    unidad = relationship("Unidad")
    presta = relationship("Chofer", foreign_keys=[chofer_presta_id])
    recibe = relationship("Chofer", foreign_keys=[chofer_recibe_id])


class Jornada(Base):
    __tablename__ = "jornada"
    id = Column(Integer, primary_key=True)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    hora_inicio = Column(DateTime, default=_now)
    hora_fin = Column(DateTime)
    km_inicio = Column(Integer)
    km_fin = Column(Integer)
    checklist_ok = Column(Boolean, default=False)
    checklist_notas = Column(Text)

    unidad = relationship("Unidad")


class UbicacionUnidad(Base):
    __tablename__ = "ubicacion_unidad"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    capturado_en = Column(DateTime, default=_now)
    fuente = Column(String(20), default="app_chofer")


class PlanMantenimiento(Base):
    __tablename__ = "plan_mantenimiento"
    id = Column(Integer, primary_key=True)
    tipo_unidad_id = Column(Integer, ForeignKey("tipo_unidad.id"))
    nombre = Column(String(120), nullable=False)
    periodicidad_dias = Column(Integer)
    periodicidad_km = Column(Integer)
    descripcion = Column(Text)
    activo = Column(Boolean, default=True)


class ProgramaMantenimiento(Base, TimestampMixin):
    __tablename__ = "programa_mantenimiento"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plan_mantenimiento.id"), nullable=False)
    fecha_programada = Column(Date)
    km_programado = Column(Integer)
    fecha_limite = Column(Date, nullable=False)
    estado = Column(String(20), default="pendiente", nullable=False)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"))
    fecha_cumplimiento = Column(DateTime)

    unidad = relationship("Unidad")
    plan = relationship("PlanMantenimiento")


class Penalizacion(Base, TimestampMixin):
    __tablename__ = "penalizacion"
    id = Column(Integer, primary_key=True)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)  # el POSEEDOR
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    programa_mantenimiento_id = Column(Integer, ForeignKey("programa_mantenimiento.id"),
                                       unique=True)
    motivo = Column(String(240), nullable=False)
    fecha_generacion = Column(Date, default=lambda: datetime.utcnow().date())
    dias_atraso = Column(Integer, default=0)
    estado = Column(String(20), default="aplicada", nullable=False)
    aplicada_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    resolucion_disputa = Column(Text)

    unidad = relationship("Unidad")
    programa = relationship("ProgramaMantenimiento")


# --------------------------------------------------------------------------- #
# AREA C - Taller e infraestructura
# --------------------------------------------------------------------------- #
class Taller(Base, TimestampMixin):
    __tablename__ = "taller"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(120), unique=True, nullable=False)
    direccion = Column(String(240))
    latitud = Column(Float)
    longitud = Column(Float)
    activo = Column(Boolean, default=True)

    zonas = relationship("ZonaTaller", back_populates="taller", cascade="all, delete-orphan")
    tecnicos = relationship("Tecnico", back_populates="taller")


class ZonaTaller(Base):
    __tablename__ = "zona_taller"
    id = Column(Integer, primary_key=True)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    nombre = Column(String(60), nullable=False)
    proposito = Column(String(30), default="operativa")
    capacidad = Column(Integer, default=0)
    # Distingue capacidad real de taller de zonas como YONKE u OFICINA.
    cuenta_para_ocupacion = Column(Boolean, default=True, nullable=False)
    orden = Column(Integer, default=0)

    taller = relationship("Taller", back_populates="zonas")
    espacios = relationship("Espacio", back_populates="zona", cascade="all, delete-orphan")


class Espacio(Base):
    __tablename__ = "espacio"
    __table_args__ = (UniqueConstraint("zona_id", "numero", name="uq_espacio_zona_numero"),)
    id = Column(Integer, primary_key=True)
    zona_id = Column(Integer, ForeignKey("zona_taller.id"), nullable=False)
    numero = Column(String(10), nullable=False)  # se repite entre zonas: unico por (zona, numero)
    tipo_unidad_permitido_id = Column(Integer, ForeignKey("tipo_unidad.id"))
    estado = Column(String(20), default="libre", nullable=False)
    pos_x = Column(Integer, default=0)
    pos_y = Column(Integer, default=0)
    activo = Column(Boolean, default=True)

    zona = relationship("ZonaTaller", back_populates="espacios")
    tipo_permitido = relationship("TipoUnidad")


class OcupacionEspacio(Base):
    __tablename__ = "ocupacion_espacio"
    id = Column(Integer, primary_key=True)
    espacio_id = Column(Integer, ForeignKey("espacio.id"), nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"))
    fecha_entrada = Column(DateTime, default=_now)
    fecha_salida = Column(DateTime)
    colocado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    retirado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))

    espacio = relationship("Espacio")
    unidad = relationship("Unidad")


class SolicitudIngreso(Base, TimestampMixin):
    __tablename__ = "solicitud_ingreso"
    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    tipo = Column(String(20), default="correctivo")
    descripcion_falla = Column(Text)
    urgencia = Column(String(12), default="media")
    fecha_solicitud = Column(DateTime, default=_now)
    estado = Column(String(20), default="pendiente", nullable=False)
    atendida_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_respuesta = Column(DateTime)
    motivo_rechazo = Column(String(240))
    fecha_ingreso_programada = Column(Date)

    unidad = relationship("Unidad")
    taller = relationship("Taller")


class OrdenServicio(Base, TimestampMixin):
    __tablename__ = "orden_servicio"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    taller_id = Column(Integer, ForeignKey("taller.id"), nullable=False)
    solicitud_id = Column(Integer, ForeignKey("solicitud_ingreso.id"))
    arrastre_id = Column(Integer, ForeignKey("arrastre.id"))
    chofer_responsable_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    fecha_entrada = Column(DateTime, default=_now)
    fecha_salida = Column(DateTime)
    estado = Column(String(24), default="abierta", nullable=False)
    km_entrada = Column(Integer)
    km_salida = Column(Integer)
    tipo = Column(String(20), default="correctivo")
    abierta_por_admin_id = Column(Integer, ForeignKey("usuario.id"))

    unidad = relationship("Unidad")
    taller = relationship("Taller")
    asignaciones = relationship("AsignacionTecnico", back_populates="orden",
                                cascade="all, delete-orphan")
    presupuestos = relationship("Presupuesto", back_populates="orden")


class AsignacionTecnico(Base):
    """La 'fila de procesos esperando' del enunciado (RF-ADM-06)."""
    __tablename__ = "asignacion_tecnico"
    id = Column(Integer, primary_key=True)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"), nullable=False)
    tecnico_id = Column(Integer, ForeignKey("tecnico.id"), nullable=False)
    especialidad = Column(String(30))
    orden_en_cola = Column(Integer, default=1, nullable=False)
    estado = Column(String(20), default="en_espera", nullable=False)
    fecha_asignacion = Column(DateTime, default=_now)
    fecha_inicio = Column(DateTime)
    fecha_fin = Column(DateTime)
    diagnostico = Column(Text)          # lo dicta el tecnico
    trabajo_realizado = Column(Text)
    asignado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    capturado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))  # RN-11
    fecha_captura = Column(DateTime)

    orden = relationship("OrdenServicio", back_populates="asignaciones")
    tecnico = relationship("Tecnico")


class FormatoSalida(Base):
    __tablename__ = "formato_salida"
    id = Column(Integer, primary_key=True)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"), unique=True,
                               nullable=False)
    fecha = Column(DateTime, default=_now)
    km_salida = Column(Integer)
    entregado_a_chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    elaborado_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    trabajos_realizados = Column(Text)
    observaciones = Column(Text)
    unidad_operativa = Column(Boolean, default=True)


# --------------------------------------------------------------------------- #
# AREA D - Presupuestos, piezas y compras
# --------------------------------------------------------------------------- #
class Pieza(Base):
    __tablename__ = "pieza"
    id = Column(Integer, primary_key=True)
    sku = Column(String(40), unique=True, nullable=False)
    nombre = Column(String(160), nullable=False)
    descripcion = Column(Text)
    unidad_medida = Column(String(20), default="pieza")
    precio_referencia = Column(Numeric(12, 2), default=0)
    stock_actual = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=0)
    activa = Column(Boolean, default=True)


class Presupuesto(Base, TimestampMixin):
    """v1.1: lo elabora el tecnico en papel y lo captura el administrador (RN-07, RN-11)."""
    __tablename__ = "presupuesto"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    orden_servicio_id = Column(Integer, ForeignKey("orden_servicio.id"), nullable=False)
    tecnico_elaboro_id = Column(Integer, ForeignKey("tecnico.id"), nullable=False)
    capturado_por_admin_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    fecha_elaboracion = Column(Date)     # la que trae el papel
    fecha_captura = Column(DateTime, default=_now)
    folio_papel = Column(String(40))
    costo_mano_obra = Column(Numeric(12, 2), default=0)
    subtotal_piezas = Column(Numeric(12, 2), default=0)
    total = Column(Numeric(12, 2), default=0)
    estado = Column(String(24), default="capturado", nullable=False)
    diagnostico = Column(Text)
    dias_estimados_reparacion = Column(Integer)
    fecha_aviso_al_tecnico = Column(DateTime)

    orden = relationship("OrdenServicio", back_populates="presupuestos")
    tecnico = relationship("Tecnico")
    detalles = relationship("DetallePresupuesto", back_populates="presupuesto",
                            cascade="all, delete-orphan")
    autorizaciones = relationship("Autorizacion", back_populates="presupuesto",
                                  cascade="all, delete-orphan")

    @property
    def dias_retraso_captura(self):
        """fecha_captura - fecha_elaboracion: mide si el 'tiempo real' del gerente es real."""
        if not self.fecha_elaboracion or not self.fecha_captura:
            return None
        return (self.fecha_captura.date() - self.fecha_elaboracion).days


class DetallePresupuesto(Base):
    __tablename__ = "detalle_presupuesto"
    id = Column(Integer, primary_key=True)
    presupuesto_id = Column(Integer, ForeignKey("presupuesto.id"), nullable=False)
    pieza_id = Column(Integer, ForeignKey("pieza.id"))
    descripcion_libre = Column(String(200))
    cantidad = Column(Numeric(10, 2), default=1)
    precio_unitario = Column(Numeric(12, 2), default=0)
    importe = Column(Numeric(12, 2), default=0)
    disponible_en_almacen = Column(Boolean, default=False)

    presupuesto = relationship("Presupuesto", back_populates="detalles")
    pieza = relationship("Pieza")


class Autorizacion(Base):
    """Entidad propia para conservar el historial de idas y vueltas del presupuesto."""
    __tablename__ = "autorizacion"
    id = Column(Integer, primary_key=True)
    presupuesto_id = Column(Integer, ForeignKey("presupuesto.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    nivel = Column(String(20), nullable=False)      # administrador|gerente
    resultado = Column(String(20), nullable=False)  # aprobado|rechazado|devuelto|remitido
    fecha = Column(DateTime, default=_now)
    comentario = Column(Text)

    presupuesto = relationship("Presupuesto", back_populates="autorizaciones")
    usuario = relationship("Usuario")


class Proveedor(Base):
    __tablename__ = "proveedor"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(160), nullable=False)
    rfc = Column(String(20))
    contacto = Column(String(120))
    telefono = Column(String(30))
    email = Column(String(160))
    activo = Column(Boolean, default=True)


class OrdenCompra(Base, TimestampMixin):
    __tablename__ = "orden_compra"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    presupuesto_id = Column(Integer, ForeignKey("presupuesto.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedor.id"))
    autorizada_por_admin_id = Column(Integer, ForeignKey("usuario.id"))
    fecha_emision = Column(DateTime, default=_now)
    estado = Column(String(24), default="solicitada", nullable=False)
    fecha_estimada_llegada = Column(Date)
    fecha_recepcion = Column(DateTime)
    total = Column(Numeric(12, 2), default=0)
    numero_rastreo = Column(String(60))

    presupuesto = relationship("Presupuesto")
    proveedor = relationship("Proveedor")


# --------------------------------------------------------------------------- #
# AREA E - Emergencias y arrastre
# --------------------------------------------------------------------------- #
class ReporteAveria(Base, TimestampMixin):
    __tablename__ = "reporte_averia"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"), nullable=False)
    fecha_hora = Column(DateTime, default=_now)
    latitud = Column(Float)
    longitud = Column(Float)
    direccion_referencia = Column(String(240))
    descripcion_falla = Column(Text)
    en_vialidad_publica = Column(Boolean, default=False, nullable=False)  # RN-04
    hay_terceros_involucrados = Column(Boolean, default=False)
    requiere_arrastre = Column(Boolean, default=False)
    estado = Column(String(24), default="abierto", nullable=False)
    supervisor_notificado_id = Column(Integer, ForeignKey("supervisor.usuario_id"))

    unidad = relationship("Unidad")
    peritaje = relationship("ReportePeritaje", back_populates="reporte", uselist=False,
                            cascade="all, delete-orphan")
    arrastre = relationship("Arrastre", back_populates="reporte", uselist=False)


class ReportePeritaje(Base):
    """RN-04: sin este registro no se habilita el arrastre en vialidad publica."""
    __tablename__ = "reporte_peritaje"
    id = Column(Integer, primary_key=True)
    reporte_averia_id = Column(Integer, ForeignKey("reporte_averia.id"), unique=True,
                               nullable=False)
    folio_peritos = Column(String(60), nullable=False)
    aseguradora = Column(String(120))
    hora_aviso = Column(DateTime, default=_now)
    hora_llegada_perito = Column(DateTime)
    nombre_perito = Column(String(120))
    resultado = Column(String(120))
    observaciones = Column(Text)
    liberada_la_unidad = Column(Boolean, default=False)

    reporte = relationship("ReporteAveria", back_populates="peritaje")


class Arrastre(Base, TimestampMixin):
    __tablename__ = "arrastre"
    id = Column(Integer, primary_key=True)
    folio = Column(String(24), unique=True, nullable=False)
    reporte_averia_id = Column(Integer, ForeignKey("reporte_averia.id"), nullable=False)
    montacarguista_id = Column(Integer, ForeignKey("montacarguista.usuario_id"))
    unidad_arrastrada_id = Column(Integer, ForeignKey("unidad.id"), nullable=False)
    unidad_grua_id = Column(Integer, ForeignKey("unidad.id"))
    chofer_responsable_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    taller_destino_id = Column(Integer, ForeignKey("taller.id"))
    estado = Column(String(20), default="solicitado", nullable=False)
    fecha_solicitud = Column(DateTime, default=_now)
    fecha_aceptacion = Column(DateTime)
    fecha_llegada_sitio = Column(DateTime)
    fecha_finalizacion = Column(DateTime)
    motivo_rechazo = Column(String(240))
    km_recorridos = Column(Float)

    reporte = relationship("ReporteAveria", back_populates="arrastre")
    unidad = relationship("Unidad", foreign_keys=[unidad_arrastrada_id])
    taller_destino = relationship("Taller")


class UbicacionArrastre(Base):
    __tablename__ = "ubicacion_arrastre"
    id = Column(Integer, primary_key=True)
    arrastre_id = Column(Integer, ForeignKey("arrastre.id"), nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    capturado_en = Column(DateTime, default=_now)
    emisor = Column(String(20), default="montacarguista")


class Evidencia(Base):
    """Polimorfica: entidad_tipo + entidad_id (la FK la valida la aplicacion)."""
    __tablename__ = "evidencia"
    id = Column(Integer, primary_key=True)
    entidad_tipo = Column(String(40), nullable=False)
    entidad_id = Column(Integer, nullable=False)
    url_archivo = Column(String(400), nullable=False)
    descripcion = Column(String(240))
    momento = Column(String(30))
    subida_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    fecha = Column(DateTime, default=_now)


# --------------------------------------------------------------------------- #
# AREA F - Transversales
# --------------------------------------------------------------------------- #
class Notificacion(Base):
    __tablename__ = "notificacion"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    tipo = Column(String(40))
    titulo = Column(String(160), nullable=False)
    mensaje = Column(Text)
    entidad_tipo = Column(String(40))
    entidad_id = Column(Integer)
    leida = Column(Boolean, default=False, nullable=False)
    fecha_envio = Column(DateTime, default=_now)
    fecha_lectura = Column(DateTime)


class BitacoraAuditoria(Base):
    __tablename__ = "bitacora_auditoria"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"))
    accion = Column(String(80), nullable=False)
    entidad_tipo = Column(String(40))
    entidad_id = Column(Integer)
    datos_antes = Column(Text)
    datos_despues = Column(Text)
    fecha = Column(DateTime, default=_now)
    ip_origen = Column(String(60))


class AlertaGerencia(Base):
    __tablename__ = "alerta_gerencia"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(50), nullable=False)
    unidad_id = Column(Integer, ForeignKey("unidad.id"))
    chofer_id = Column(Integer, ForeignKey("chofer.usuario_id"))
    fecha_generacion = Column(DateTime, default=_now)
    veces_notificada = Column(Integer, default=1)  # RN-08: reincide hasta atenderse
    ultima_notificacion = Column(DateTime, default=_now)
    atendida = Column(Boolean, default=False, nullable=False)
    fecha_atencion = Column(DateTime)
    atendida_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    detalle = Column(Text)

    unidad = relationship("Unidad")


class Configuracion(Base):
    __tablename__ = "configuracion"
    id = Column(Integer, primary_key=True)
    clave = Column(String(60), unique=True, nullable=False)
    valor = Column(String(200), nullable=False)
    descripcion = Column(String(240))
    tipo_dato = Column(String(20), default="int")
