"""CU-GEN-01 Iniciar sesion, CU-GEN-02 Recibir notificaciones."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notificacion, Usuario
from ..schemas import LoginIn, MensajeOut, NotificacionOut, TokenOut, UsuarioOut
from ..security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _usuario_out(u: Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "apellidos": u.apellidos, "email": u.email,
            "telefono": u.telefono, "activo": u.activo, "roles": u.lista_roles}


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == datos.email.lower()).first()
    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(401, "Correo o contrasena incorrectos")
    if not usuario.activo:
        raise HTTPException(403, "Usuario inactivo")
    return {"access_token": create_access_token(usuario), "token_type": "bearer",
            "usuario": _usuario_out(usuario)}


@router.post("/token", response_model=TokenOut, include_in_schema=False)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Compatibilidad con el boton Authorize de /docs."""
    usuario = db.query(Usuario).filter(Usuario.email == form.username.lower()).first()
    if not usuario or not verify_password(form.password, usuario.password_hash):
        raise HTTPException(401, "Correo o contrasena incorrectos")
    return {"access_token": create_access_token(usuario), "token_type": "bearer",
            "usuario": _usuario_out(usuario)}


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_user)):
    return _usuario_out(usuario)


@router.get("/notificaciones", response_model=list[NotificacionOut])
def notificaciones(solo_no_leidas: bool = False, usuario: Usuario = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    q = db.query(Notificacion).filter(Notificacion.usuario_id == usuario.id)
    if solo_no_leidas:
        q = q.filter(Notificacion.leida.is_(False))
    return q.order_by(Notificacion.fecha_envio.desc()).limit(50).all()


@router.post("/notificaciones/{notif_id}/leer", response_model=MensajeOut)
def marcar_leida(notif_id: int, usuario: Usuario = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    n = db.query(Notificacion).filter(Notificacion.id == notif_id,
                                      Notificacion.usuario_id == usuario.id).first()
    if not n:
        raise HTTPException(404, "Notificacion no encontrada")
    n.leida = True
    n.fecha_lectura = datetime.utcnow()
    db.commit()
    return {"mensaje": "Notificacion marcada como leida"}
