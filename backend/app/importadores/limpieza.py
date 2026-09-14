"""Deja la tabla `unidad` en condiciones ANTES de importar el catalogo real.

Hay que correrlo primero y no despues: la base trae cuatro parejas de la misma
unidad cargada dos veces, y si el catalogo entra encima quedan seis escrituras
del mismo camion sin forma de saber cual es la buena.

Las 383 filas de hoy son 379 unidades reales.

QUE SE HACE CON CADA COSA, Y POR QUE NO TODO SE BORRA:

  'AYTE'                 se BORRA. No es un vehiculo: es la etiqueta de
                         'ayudante' que se colo desde el bloque AYTE de
                         INFO CHOFERES. No tiene un solo registro colgando.

  U-101, U-102,          se DESACTIVAN y se les quitan la placa y el VIN
  U-201, U-301           inventados, pero NO se borran. Entre las cuatro tienen
                         44 registros dependientes --ordenes, averias,
                         prestamos, arrastres, programas de mantenimiento--
                         que son el historial con el que se demuestra el
                         sistema. Borrar la unidad se lo lleva por delante.
                         Lo que estorba de ellas no es que existan: es que sus
                         placas falsas ('AB-123-CD') son las UNICAS placas de
                         la base y contaminan el dato que estamos por importar.

  Las 4 parejas          se FUSIONAN. Sobrevive la fila con mas datos y se le
                         pone el nombre con el que la escribe el catalogo
                         maestro, que es contra quien va a cruzar despues.

Es idempotente: correrlo dos veces no hace nada la segunda vez.
"""
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m

log = logging.getLogger(__name__)

# No son vehiculos. Se borran si nada las referencia.
NO_SON_UNIDAD = ["AYTE"]

# Datos semilla: se conservan por su historial, pero desarmados.
DE_DEMO = ["U-101", "U-102", "U-201", "U-301"]

# (se queda, se absorbe, como lo escribe el catalogo maestro)
#
# El sobreviviente de cada pareja es el que trae marca y modelo; el otro entro
# vacio. Pero el NOMBRE que se conserva es el del catalogo, no el del
# sobreviviente: el taller escribe 'BG-439' y el catalogo 'BG439P', y es contra
# el catalogo contra quien hay que cruzar manana.
PAREJAS = [
    ("BG-677", "BG677", "BG677"),
    ("BG-439", "BG439P", "BG439P"),
    ("BG-458", "BG458P", "BG458P"),
    ("BG430", "BG430P", "BG430P"),
]


def _tablas_que_apuntan_a_unidad(db: Session):
    """Las columnas de todo el esquema que son FK a unidad.id.

    Se descubren del propio modelo y no se listan a mano: cuando alguien agregue
    una tabla que referencie unidad, la fusion la va a repuntar sola. Una lista
    escrita a mano se queda vieja sin avisar y deja filas huerfanas.
    """
    salida = []
    for tabla in m.Base.metadata.sorted_tables:
        for col in tabla.columns:
            for fk in col.foreign_keys:
                if fk.column.table.name == "unidad":
                    salida.append((tabla, col))
    return salida


def _contar(db: Session, tabla, col, unidad_id: int) -> int:
    """Cuantas filas de esa tabla apuntan a esa unidad."""
    return db.execute(
        select(func.count()).select_from(tabla).where(col == unidad_id)
    ).scalar() or 0


def limpiar(db: Session) -> dict:
    """Deja la tabla lista para el catalogo. Devuelve que hizo."""
    hecho = {"borradas": [], "desactivadas": [], "fusionadas": [], "avisos": []}
    refs = _tablas_que_apuntan_a_unidad(db)

    # ---------------------------------------------------------------- borrar --
    for nombre in NO_SON_UNIDAD:
        u = db.query(m.Unidad).filter(m.Unidad.num_economico == nombre).first()
        if not u:
            continue
        colgando = sum(_contar(db, t, c, u.id) for t, c in refs)
        if colgando:
            hecho["avisos"].append(
                f"{nombre} no se borro: tiene {colgando} registro(s) apuntandole. "
                "Revisalo a mano.")
            continue
        db.delete(u)
        hecho["borradas"].append(nombre)

    # ----------------------------------------------------------- desactivar --
    for nombre in DE_DEMO:
        u = db.query(m.Unidad).filter(m.Unidad.num_economico == nombre).first()
        if not u or (u.placas is None and u.vin is None and not u.activo):
            continue  # ya paso por aqui
        u.placas = None
        u.vin = None
        u.activo = False
        hecho["desactivadas"].append(nombre)

    # --------------------------------------------------------------- fusionar --
    for queda, absorbida, nombre_catalogo in PAREJAS:
        a = db.query(m.Unidad).filter(m.Unidad.num_economico == queda).first()
        b = db.query(m.Unidad).filter(m.Unidad.num_economico == absorbida).first()
        if a is None or b is None:
            # Ya se fusionaron, o esta base nunca tuvo la pareja.
            solo = a or b
            if solo is not None and solo.num_economico != nombre_catalogo:
                solo.num_economico = nombre_catalogo
                hecho["fusionadas"].append(f"{solo.num_economico} (renombrada)")
            continue

        # Se repunta TODO lo que apunte a la absorbida antes de borrarla.
        movidos = 0
        for tabla, col in refs:
            r = db.execute(tabla.update().where(col == b.id).values({col: a.id}))
            movidos += r.rowcount or 0

        # El chofer titular de la absorbida no se pisa encima del que ya tiene
        # la sobreviviente: se avisa para que alguien decida. Son dos personas
        # distintas asignadas al mismo camion escrito de dos formas.
        if b.titular_chofer_id and a.titular_chofer_id \
                and b.titular_chofer_id != a.titular_chofer_id:
            hecho["avisos"].append(
                f"{queda}/{absorbida}: dos titulares distintos "
                f"(se conservo el {a.titular_chofer_id}, se descarto el "
                f"{b.titular_chofer_id}). Confirmalo con el supervisor.")
        elif b.titular_chofer_id and not a.titular_chofer_id:
            a.titular_chofer_id = b.titular_chofer_id

        # Se rellenan los huecos de la sobreviviente con lo que traiga la otra.
        for campo in ("placas", "vin", "marca", "modelo", "anio",
                      "taller_asignado_id", "poseedor_chofer_id"):
            if getattr(a, campo, None) in (None, "") and getattr(b, campo, None):
                setattr(a, campo, getattr(b, campo))

        # El borrado va ANTES del renombre, y con su propio flush. Sin esto
        # SQLAlchemy emite el UPDATE del nombre antes que el DELETE, y la fila
        # sobreviviente choca contra la que todavia no se ha ido:
        # "UNIQUE constraint failed: unidad.num_economico".
        db.delete(b)
        db.flush()

        a.num_economico = nombre_catalogo
        db.flush()
        hecho["fusionadas"].append(
            f"{queda} + {absorbida} -> {nombre_catalogo}"
            + (f" ({movidos} registro(s) repuntado(s))" if movidos else ""))

    db.commit()

    for aviso in hecho["avisos"]:
        log.warning("limpieza: %s", aviso)
    return hecho


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from ..core.database import SessionLocal

    db = SessionLocal()
    try:
        antes = db.query(m.Unidad).count()
        r = limpiar(db)
        despues = db.query(m.Unidad).count()
        print(f"unidades: {antes} -> {despues}")
        for clave in ("borradas", "desactivadas", "fusionadas"):
            if r[clave]:
                print(f"  {clave}: {', '.join(r[clave])}")
        for aviso in r["avisos"]:
            print(f"  AVISO: {aviso}")
    finally:
        db.close()
