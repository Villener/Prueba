"""Autenticacion JWT y control de acceso por rol (RF-GEN-01, RF-GEN-02, RNF-04).

La autorizacion se aplica del lado del servidor, no solo en la interfaz.
"""
import os
from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import Usuario

SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto-en-produccion-bajagas-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_MINUTES", "480"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

ROLES = ["chofer", "supervisor", "administrador", "montacarguista", "gerente"]


def _to_bytes(plain: str) -> bytes:
    # bcrypt trunca en 72 bytes; se recorta explicitamente para evitar el error.
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_to_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(usuario: Usuario) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(usuario.id),
        "email": usuario.email,
        "roles": usuario.lista_roles,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> Usuario:
    cred_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas o sesion expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise cred_error
    except JWTError:
        raise cred_error

    usuario = db.query(Usuario).filter(Usuario.id == int(user_id)).first()
    if usuario is None or not usuario.activo:
        raise cred_error
    return usuario


def require_roles(*roles_permitidos: str):
    """Dependencia que exige al menos uno de los roles indicados."""
    def _checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if not set(roles_permitidos) & set(usuario.lista_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere uno de los roles: {', '.join(roles_permitidos)}",
            )
        return usuario
    return _checker


def registrar_bitacora(db: Session, usuario_id, accion: str, entidad_tipo: str = None,
                       entidad_id: int = None, datos_despues: str = None):
    """RF-GEN-04: bitacora inmutable de acciones criticas."""
    from .models import BitacoraAuditoria
    db.add(BitacoraAuditoria(
        usuario_id=usuario_id, accion=accion, entidad_tipo=entidad_tipo,
        entidad_id=entidad_id, datos_despues=datos_despues,
    ))


def notificar(db: Session, usuario_id: int, titulo: str, mensaje: str = "",
              tipo: str = "info", entidad_tipo: str = None, entidad_id: int = None):
    """RF-GEN-05: notificacion in-app."""
    from .models import Notificacion
    if usuario_id is None:
        return
    db.add(Notificacion(usuario_id=usuario_id, titulo=titulo, mensaje=mensaje, tipo=tipo,
                        entidad_tipo=entidad_tipo, entidad_id=entidad_id))
