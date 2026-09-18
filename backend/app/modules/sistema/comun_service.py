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


def buscar_unidades(db: Session, q: str = "", limite: int = 10) -> list:
    """Buscador de unidad por numero economico, sin guiones ni espacios.

    El papel escribe "BG-354P" y el catalogo "BG354P". Sin normalizar, la mitad
    de las unidades del libro no casan y el usuario acaba dejando el campo en
    blanco.

    Vive aqui y no en un controlador porque lo necesitan tres roles con
    endpoints distintos --capturista, administrador y ahora el mecanico
    autonomo-- y cada uno solo puede llamar al suyo. Tener el mismo algoritmo
    copiado tres veces garantiza que se arreglen dos de las tres.
    """
    termino = (q or "").strip()
    if len(termino) < 1:
        return []
    plano = "".join(c for c in termino.upper() if c.isalnum())
    # SQLite no tiene una funcion para quitar caracteres arbitrarios, asi que se
    # recorre en Python. Son ~700 unidades: cabe de sobra.
    candidatas = (db.query(m.Unidad)
                  .filter(m.Unidad.num_economico.isnot(None))
                  .order_by(m.Unidad.num_economico).all())
    out = []
    for u in candidatas:
        clave = "".join(c for c in u.num_economico.upper() if c.isalnum())
        if plano in clave:
            out.append({"id": u.id, "num_economico": u.num_economico,
                        "marca": u.marca, "modelo": u.modelo, "anio": u.anio,
                        "vin": u.vin, "estado": u.estado, "activo": u.activo,
                        "exacto": clave == plano})
        if len(out) >= max(1, min(limite, 50)) and any(x["exacto"] for x in out):
            break
    out.sort(key=lambda x: (not x["exacto"], len(x["num_economico"])))
    return out[: max(1, min(limite, 50))]
