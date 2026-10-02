"""CU-GEN-01 Iniciar sesion, CU-GEN-02 Recibir notificaciones."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.intentos import (ip_del_cliente, limpiar, registrar_fallo,
                              segundos_de_espera)
from ...models import Notificacion, Usuario
from ...schemas import LoginIn, MensajeOut, NotificacionOut, TokenOut, UsuarioOut
from ...core.security import (create_access_token, get_current_user, registrar_bitacora,
                              verify_password)
from ...importadores import normaliza as n
from ...core.tiempo import ahora_utc

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _usuario_out(u: Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "apellidos": u.apellidos, "email": u.email,
            "telefono": u.telefono, "activo": u.activo, "roles": u.lista_roles}


def _autenticar(request: Request, db: Session, correo: str, password: str) -> Usuario:
    """El unico camino para cambiar una contrasena por un usuario.

    Los dos endpoints de login pasan por aqui para que no se repita lo que ya
    habia pasado: `/login` comprobaba `activo` y `/token` no. Dos puertas a la
    misma casa con cerraduras distintas es como se cuelan las cosas.
    """
    correo = (correo or "").lower()
    ip = ip_del_cliente(request)

    espera = segundos_de_espera(correo, ip)
    if espera:
        raise HTTPException(
            429,
            f"Demasiados intentos fallidos. Vuelve a intentar en {espera // 60 + 1} minuto(s).",
            headers={"Retry-After": str(espera)},
        )

    usuario = db.query(Usuario).filter(Usuario.email == correo).first()
    if not usuario or not verify_password(password, usuario.password_hash):
        registrar_fallo(correo, ip)
        # El mismo mensaje para "no existe" y para "contrasena mala": decir cual
        # de los dos fue le confirma a quien prueba que el correo es valido, y
        # con la convencion e<num_empleado>@bajagas.mx eso es media plantilla.
        raise HTTPException(401, "Correo o contrasena incorrectos")

    if not usuario.activo:
        registrar_fallo(correo, ip)
        raise HTTPException(403, "Usuario inactivo")

    limpiar(correo, ip)
    return usuario


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, request: Request, db: Session = Depends(get_db)):
    usuario = _autenticar(request, db, datos.email, datos.password)
    return {"access_token": create_access_token(usuario), "token_type": "bearer",
            "usuario": _usuario_out(usuario)}


@router.post("/token", response_model=TokenOut, include_in_schema=False)
def login_form(request: Request, form: OAuth2PasswordRequestForm = Depends(),
               db: Session = Depends(get_db)):
    """Compatibilidad con el boton Authorize de /docs."""
    usuario = _autenticar(request, db, form.username, form.password)
    return {"access_token": create_access_token(usuario), "token_type": "bearer",
            "usuario": _usuario_out(usuario)}


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_user)):
    return _usuario_out(usuario)


class TelefonoIn(BaseModel):
    telefono: str


@router.put("/me/telefono", response_model=UsuarioOut)
def mi_telefono(datos: TelefonoIn, usuario: Usuario = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Cada quien pone SU celular, ya dentro de su cuenta (pantalla Mis datos).

    No es un registro: no crea cuentas, solo completa el dato de alguien que ya
    entro con la suya. 350 de 434 personas no traen telefono en ningun Excel, y
    sin el no hay WhatsApp para avisar de una cita. Se guarda con las mismas
    reglas que el importador (normaliza.telefono: 10 digitos, sin lada de pais),
    y el importador no lo vuelve a pisar porque solo llena telefonos vacios.
    """
    nuevo = n.celular(datos.telefono)
    if not nuevo:
        raise HTTPException(422, "Escribe un celular de 10 digitos, por ejemplo 664 123 4567")
    u = db.get(Usuario, usuario.id)
    anterior = u.telefono
    if anterior != nuevo:
        u.telefono = nuevo
        registrar_bitacora(db, u.id, "telefono_actualizado", "usuario", u.id,
                           datos_despues=nuevo, datos_antes=anterior)
        db.commit()
    return _usuario_out(u)


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
    n.fecha_lectura = ahora_utc()
    db.commit()
    return {"mensaje": "Notificacion marcada como leida"}
