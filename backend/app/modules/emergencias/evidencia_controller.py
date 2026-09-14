"""Fotos de las averias - subida y entrega.

La tabla `Evidencia` existia desde la v1.1 pero nunca hubo por donde subir ni
por donde ver un archivo: `url_archivo` se guardaba vacia. Aqui se cierra eso.

DONDE SE GUARDAN. En /datos/evidencias, dentro del MISMO volumen que la base.
No en la imagen: reconstruir el contenedor la borra, y las fotos de un percance
en vialidad publica son material del expediente del seguro. No en la base como
base64 tampoco: una foto de telefono son 2-4 MB y meterlas en SQLite hincha el
archivo que se respalda a diario por algo que se mira dos veces.

QUIEN LAS VE. Cualquier usuario con sesion, no solo quien la subio: la foto la
sube el chofer y la miran el administrador de taller, el supervisor y el chofer
de grua que va en camino. Restringirla al autor la volveria inutil.

El nombre del archivo lo pone el servidor --nunca el que traiga el navegador--
porque un nombre de archivo es texto que viene de fuera y con `..` se sale del
directorio.
"""
import hashlib
import os
import pathlib

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ... import models as m
from ...core.database import get_db
from ...core.security import get_current_user, registrar_bitacora

router = APIRouter(prefix="/api/evidencias", tags=["evidencias"])

# Junto a la base, en el volumen. La variable existe para poder apuntarlo a
# otro lado en desarrollo, donde no hay /datos.
RAIZ = pathlib.Path(os.environ.get("EVIDENCIAS_DIR", "/datos/evidencias"))

# Un telefono moderno saca fotos de 3-5 MB. 8 da margen sin permitir que
# alguien suba un video de media hora por equivocacion.
MAX_BYTES = 8 * 1024 * 1024

# Se valida por tipo declarado Y por los primeros bytes del archivo. Solo con
# el content-type bastaria con renombrar cualquier cosa a .jpg.
TIPOS = {
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png":  (".png", b"\x89PNG\r\n\x1a\n"),
    "image/webp": (".webp", b"RIFF"),
}


def guardar(db: Session, usuario_id: int, entidad_tipo: str, entidad_id: int,
            archivo: UploadFile, descripcion: str | None = None,
            momento: str | None = None) -> m.Evidencia:
    """Escribe el archivo y deja el renglon en `evidencia`. Devuelve el renglon."""
    if archivo.content_type not in TIPOS:
        raise HTTPException(
            415, f"Solo se aceptan fotos JPG, PNG o WEBP. Llego '{archivo.content_type}'.")
    datos = archivo.file.read(MAX_BYTES + 1)
    if len(datos) > MAX_BYTES:
        raise HTTPException(413, f"La foto pasa de {MAX_BYTES // (1024 * 1024)} MB.")
    if not datos:
        raise HTTPException(400, "El archivo llego vacio")

    extension, firma = TIPOS[archivo.content_type]
    if not datos.startswith(firma):
        # El content-type lo elige el navegador y se puede mentir; los primeros
        # bytes son el archivo de verdad.
        raise HTTPException(415, "El archivo no es una imagen valida.")

    # El nombre sale del contenido, no de lo que mande el cliente. De paso, dos
    # subidas de la misma foto no ocupan el doble.
    nombre = hashlib.sha256(datos).hexdigest()[:32] + extension
    carpeta = RAIZ / entidad_tipo
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / nombre
    if not destino.exists():
        destino.write_bytes(datos)

    ev = m.Evidencia(entidad_tipo=entidad_tipo, entidad_id=entidad_id,
                     url_archivo=f"{entidad_tipo}/{nombre}", descripcion=descripcion,
                     momento=momento, subida_por_usuario_id=usuario_id)
    db.add(ev)
    db.flush()
    return ev


def evidencia_out(db: Session, ev: m.Evidencia) -> dict:
    from ..sistema.comun_service import nombre_usuario
    return {
        "id": ev.id,
        "descripcion": ev.descripcion,
        "momento": ev.momento,
        "fecha": ev.fecha,
        "subida_por": (nombre_usuario(db, ev.subida_por_usuario_id)
                       if ev.subida_por_usuario_id else None),
    }


@router.get("/{evidencia_id}")
def ver(evidencia_id: int, usuario=Depends(get_current_user), db: Session = Depends(get_db)):
    """Entrega el archivo. Exige sesion, sin importar el rol.

    Se sirve desde aqui y no como archivo estatico de nginx a proposito: en
    estatico, quien adivine la URL ve la foto de un percance sin estar dentro
    del sistema.
    """
    ev = db.query(m.Evidencia).filter(m.Evidencia.id == evidencia_id).first()
    if not ev or not ev.url_archivo:
        raise HTTPException(404, "Evidencia no encontrada")

    ruta = (RAIZ / ev.url_archivo).resolve()
    # Candado por si alguna vez se escribiera un url_archivo con "..": la ruta
    # resuelta tiene que seguir cayendo dentro de RAIZ.
    if not str(ruta).startswith(str(RAIZ.resolve())) or not ruta.exists():
        raise HTTPException(404, "El archivo ya no esta en el servidor")
    return FileResponse(ruta)
