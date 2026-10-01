"""Pantalla de carga de datos: el administrador y una cuenta por area.

La logica vive en cargas_service.py. Aqui solo: quien puede, leer el archivo
subido y anotar en la bitacora de auditoria. Los endpoints son `def` y no
`async def` a proposito: el simulacro tarda de 15 a 60 segundos y FastAPI corre
los `def` en un hilo aparte, asi el resto de la aplicacion sigue contestando.
"""
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ... import models as m
from ...core.database import get_db
from ...core.security import registrar_bitacora, require_roles
from . import cargas_service as svc

router = APIRouter(prefix="/api/cargas", tags=["cargas"])
puede_cargar = require_roles(*svc.ROLES_DE_CARGA)

ACCION = "carga_archivo_area"
HISTORIAL_TOPE = 30


def _error(e: svc.ErrorCarga):
    return HTTPException(status_code=e.status, detail=str(e))


@router.get("")
def estado(usuario=Depends(puede_cargar), db: Session = Depends(get_db)):
    """Que archivos puede subir esta persona, cual esta puesto y las ultimas cargas."""
    permitidos = set(svc.tipos_permitidos(usuario.lista_roles))
    out = svc.estado(svc.carpeta_areas(), usuario.lista_roles)
    filas = (db.query(m.BitacoraAuditoria, m.Usuario)
             .outerjoin(m.Usuario, m.Usuario.id == m.BitacoraAuditoria.usuario_id)
             .filter(m.BitacoraAuditoria.accion == ACCION)
             .order_by(m.BitacoraAuditoria.fecha.desc()).limit(200).all())
    historial = []
    for b, u in filas:
        try:
            d = json.loads(b.datos_despues or "{}")
        except ValueError:
            continue
        if d.get("tipo") not in permitidos:
            continue
        historial.append({
            "id": b.id, "fecha": b.fecha, "tipo": d.get("tipo"),
            "original": d.get("original"),
            "quien": f"{u.nombre} {u.apellidos}" if u else None,
            "cambios": sum(x.get("nuevas", 0) + x.get("borradas", 0) + x.get("cambiadas", 0)
                           for x in (d.get("cambios") or {}).values()),
        })
        if len(historial) >= HISTORIAL_TOPE:
            break
    out["historial"] = historial
    return out


@router.post("/{tipo}/simular")
def simular(tipo: str, archivo: UploadFile = File(...), usuario=Depends(puede_cargar)):
    """Revisa el archivo contra una copia de la base. No cambia nada real."""
    if tipo not in svc.TIPOS:
        raise HTTPException(404, "Tipo de archivo desconocido")
    if tipo not in svc.tipos_permitidos(usuario.lista_roles):
        raise HTTPException(403, "Este archivo no es de tu area")
    contenido = archivo.file.read(svc.TOPE_BYTES + 1)
    try:
        return svc.simular(svc.carpeta_areas(), tipo, archivo.filename or "archivo.xlsx",
                           contenido, usuario.id)
    except svc.ErrorCarga as e:
        raise _error(e)


@router.post("/{carga_id}/aplicar")
def aplicar(carga_id: str, usuario=Depends(puede_cargar), db: Session = Depends(get_db)):
    """Pone el archivo revisado en su lugar y sincroniza de verdad."""
    try:
        r = svc.aplicar(svc.carpeta_areas(), carga_id, usuario.lista_roles)
    except svc.ErrorCarga as e:
        raise _error(e)
    registrar_bitacora(db, usuario.id, ACCION, "archivo_area", None,
                       datos_despues=json.dumps(r.pop("asiento"), ensure_ascii=False))
    db.commit()
    return r
