"""Paquete A - Organizacion, plantas y personas.

Corresponde a Usuario, Rol, UsuarioRol, Chofer, Supervisor, ChoferGrua, LimiteAutorizacion del diagrama de clases.
"""
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from ...core.base_model import Base, TimestampMixin, _now
from ...core.tiempo import UTCDateTime


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
    fecha_alta = Column(UTCDateTime, default=_now)

    roles = relationship("UsuarioRol", back_populates="usuario", cascade="all, delete-orphan")
    chofer = relationship("Chofer", back_populates="usuario", uselist=False)
    supervisor = relationship("Supervisor", back_populates="usuario", uselist=False)
    chofer_grua = relationship("ChoferGrua", back_populates="usuario", uselist=False)

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
    vigente_desde = Column(UTCDateTime, default=_now)
    vigente_hasta = Column(UTCDateTime)

    usuario = relationship("Usuario", back_populates="roles")
    rol = relationship("Rol")

class Chofer(Base):
    __tablename__ = "chofer"
    usuario_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    num_licencia = Column(String(40), unique=True)
    tipo_licencia = Column(String(20))
    vencimiento_licencia = Column(Date)
    plantilla_id = Column(Integer, ForeignKey("plantilla.id"))
    disponible = Column(Boolean, default=True)

    # Los tres salen de los Excel de Logistica y existen para poder ARMAR EL
    # HORARIO del mantenimiento trimestral, que es lo que ninguno de los siete
    # archivos permite hoy.
    #
    # La cuenta: 297 choferes, cada uno cada 3 meses, son 297 visitas sobre
    # unos 64 dias habiles = menos de 5 al dia, y Alamos tiene 31 cajones. El
    # cupo nunca fue el problema. El problema es no dejar una ruta descubierta,
    # y para eso hay que poder repartir por turno y por ruta.
    turno = Column(String(24))     # MATUTINO | VESPERTINO | MATUTINO-VESPERTINO
    ruta = Column(String(24))      # R-2201, R-1132...
    # 'chofer' o 'ayudante'. El ayudante no trae unidad y no se le programa
    # taller; viene marcado asi en la hoja NUMEROS DE CELULAR.
    perfil = Column(String(16))

    usuario = relationship("Usuario", back_populates="chofer")
    plantilla = relationship("Plantilla", back_populates="choferes")

class Supervisor(Base):
    __tablename__ = "supervisor"
    usuario_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    zona = Column(String(80))

    usuario = relationship("Usuario", back_populates="supervisor")
    plantillas = relationship("Plantilla", back_populates="supervisor")

class ChoferGrua(Base):
    __tablename__ = "chofer_grua"
    usuario_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    unidad_grua_id = Column(Integer, ForeignKey("unidad.id"))
    licencia_especial = Column(String(40))
    en_servicio = Column(Boolean, default=True)

    usuario = relationship("Usuario", back_populates="chofer_grua")

class LimiteAutorizacion(Base):
    """Hasta cuanto puede aprobar cada rol sin subir al gerente.

    Va por ROL y con vigencia, no como columna del gerente: asi se puede
    auditar con que techo se aprobo algo el ano pasado.
    """
    __tablename__ = "limite_autorizacion"
    id = Column(Integer, primary_key=True)
    rol_id = Column(Integer, ForeignKey("rol.id"), nullable=False)
    monto_maximo = Column(Numeric(12, 2))       # NULL = sin limite
    moneda = Column(String(3), default="MXN")
    vigente_desde = Column(UTCDateTime, default=_now, nullable=False)
    vigente_hasta = Column(UTCDateTime)
