"""Paquete A - Organizacion, plantas y personas.

Corresponde a Usuario, Rol, UsuarioRol, Chofer, Supervisor, Montacarguista, LimiteAutorizacion del diagrama de clases.
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
