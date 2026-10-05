"""Avisos al celular: suscribir este telefono, quitarlo y mandar una prueba.

El envio de los avisos de verdad no pasa por aqui: sale solo de notificar()
(ver push_service.py). Cada quien maneja unicamente SUS celulares.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models import Usuario
from . import push_service as svc
from .notificacion_model import SuscripcionPush

router = APIRouter(prefix="/api/push", tags=["avisos al celular"])


class Llaves(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=60)


class SuscripcionIn(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: Llaves


class QuitarIn(BaseModel):
    endpoint: str = Field(max_length=1000)


@router.get("/clave")
def clave(usuario: Usuario = Depends(get_current_user)):
    """La clave publica del servidor: el navegador la necesita para suscribirse."""
    return {"clave": svc.claves()["publica"]}


@router.get("/estado")
def estado(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(SuscripcionPush).filter_by(usuario_id=usuario.id).count()
    return {"dispositivos": n}


@router.post("/suscripcion")
def suscribir(datos: SuscripcionIn, request: Request,
              usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not svc.endpoint_valido(datos.endpoint):
        raise HTTPException(422, "Ese navegador no usa un servicio de avisos conocido.")
    agente = request.headers.get("user-agent", "")
    try:
        svc.guardar_suscripcion(db, usuario.id, datos.endpoint, datos.keys.p256dh, datos.keys.auth, agente)
        db.commit()
    except IntegrityError:
        # Dos registros del mismo celular al mismo tiempo (la app sincroniza al
        # abrir y la persona toca "Activar"): el otro ya la inserto. Se vuelve a
        # intentar y esta vez se encuentra y se actualiza.
        db.rollback()
        svc.guardar_suscripcion(db, usuario.id, datos.endpoint, datos.keys.p256dh, datos.keys.auth, agente)
        db.commit()
    return {"dispositivos": db.query(SuscripcionPush).filter_by(usuario_id=usuario.id).count()}


@router.delete("/suscripcion")
def quitar(datos: QuitarIn, usuario: Usuario = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """Este celular deja de recibir los avisos de esta cuenta (al salir, o a mano).
    Solo borra la suscripcion si es de quien la pide."""
    n = (db.query(SuscripcionPush)
         .filter_by(endpoint=datos.endpoint, usuario_id=usuario.id)
         .delete(synchronize_session=False))
    db.commit()
    return {"quitadas": n}


@router.post("/revisar")
def revisar(datos: QuitarIn, usuario: Usuario = Depends(get_current_user),
            db: Session = Depends(get_db)):
    """Si ESTE celular esta registrado a nombre de quien pregunta. Que el
    navegador tenga suscripcion no basta: si el registro en el servidor fallo,
    la pantalla diria "recibe tus avisos" y no le llegaria nada."""
    hay = (db.query(SuscripcionPush)
           .filter_by(endpoint=datos.endpoint, usuario_id=usuario.id).first() is not None)
    return {"registrada": hay}


@router.post("/prueba")
def prueba(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.query(SuscripcionPush).filter_by(usuario_id=usuario.id).count():
        raise HTTPException(409, "Todavia no hay ningun celular con los avisos activados.")
    if not svc.prueba_permitida(usuario.id):
        raise HTTPException(429, "Espera unos segundos antes de mandar otra prueba.")
    return svc.enviar_a_usuario(db, usuario.id, svc._datos(
        "Aviso de prueba",
        f"Hola {usuario.nombre}: si ves esto, los avisos del taller ya te llegan a este celular.",
        url="/#/mis-datos"))
