"""Utilidades transversales.

Lo que usan todos los dominios: folios y resolucion de nombres.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import ahora_utc


# ------------------------------------------------------------------ folios -- #
def siguiente_folio(db: Session, modelo, prefijo: str) -> str:
    n = db.query(func.count(modelo.id)).scalar() or 0
    return f"{prefijo}-{ahora_utc().year}-{n + 1:05d}"


# ------------------------------------------------------------ nombres ------- #

# ------------------------------------------------------------ nombres ------- #
def nombre_chofer(db: Session, chofer_id):
    if not chofer_id:
        return None
    u = db.query(m.Usuario).filter(m.Usuario.id == chofer_id).first()
    return u.nombre_completo if u else None

def nombre_usuario(db: Session, usuario_id):
    if not usuario_id:
        return None
    u = db.query(m.Usuario).filter(m.Usuario.id == usuario_id).first()
    return u.nombre_completo if u else None


# ------------------------------------------------------- reglas de negocio -- #
