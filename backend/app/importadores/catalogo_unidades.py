"""Actualiza el padron de unidades desde el Catalogo de Unidades del area.

POR QUE EXISTE. La base se sembro de un Excel viejo y dice que hay 714 unidades
activas. El catalogo que lleva logistica dice 628. Las 86 de diferencia son
unidades dadas de baja que el sistema sigue contando, y el director lo noto en la
primera revision: el tablero hablaba de una flota que ya no existe.

QUE TRAE EL CATALOGO QUE LA BASE NO TENIA:

  Estatus     Activa / Inactiva. Es el dato que el director pidio.
  Sucursal    A que planta pertenece la unidad. La base solo sabia en que taller
              esta AHORA -- que son dos cosas distintas y solo 2 unidades lo
              tenian. Sin esto no se puede hacer un piloto de un solo taller.
  Supervisor  Quien responde por ella en campo.
  Ruta        La ruta asignada, cuando la trae.

QUE NO TOCA, Y ES DELIBERADO. No crea unidades que no existan en la base, no
borra ninguna y no toca su estado operativo (disponible, en taller, varada). Solo
corrige el padron: quien sigue en la flota, de que planta es y quien la
supervisa. Una unidad que el catalogo no menciona se deja como esta y se reporta
al final: puede ser un alta reciente que el Excel todavia no tiene, y darla de
baja por ausencia seria sacar de circulacion una unidad que si trabaja.

USO, parado en backend/ y con el entorno virtual activo:

    python -m app.importadores.catalogo_unidades "ruta/al/Catalogo.xlsx"
    python -m app.importadores.catalogo_unidades "ruta.xlsx" --simular

Sin `--simular` escribe. Con `--simular` solo dice que cambiaria.
"""
import argparse
import sys
import unicodedata

from openpyxl import load_workbook

from ..core.database import SessionLocal
from .. import models as m

# La columna que manda para cada cosa. Van por nombre y no por posicion: el area
# reordena columnas entre versiones del archivo, y un importador que lee la
# columna 9 a ciegas escribe supervisores en el campo de la sucursal el dia que
# alguien inserta una al principio.
COL_ECONOMICO = "Unidad"
COL_ESTATUS = "Estatus"
COL_SUCURSAL = "Sucursal"
COL_SUPERVISOR = "Nombre_Supervisor"
COL_RUTA = "Ruta"

# Como se escribe "activa" en el archivo. Se compara sin acentos y en minuscula
# porque el mismo catalogo trae "Activa", "ACTIVA" y "Activa " con espacio.
ACTIVA = "activa"


def _limpio(v) -> str:
    """El texto de una celda, sin acentos, sin espacios de sobra y en minuscula.

    Los nombres de sucursal del catalogo vienen con variaciones que son la misma
    planta: "ALAMOS", "ALAMOS " y "Alamos". Sin normalizar, el importador
    crearia tres sucursales distintas y el piloto por taller saldria partido.
    """
    if v is None:
        return ""
    t = str(v).strip()
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _economico(v) -> str:
    """El numero economico tal como lo guarda la base.

    openpyxl devuelve los numericos como float: la unidad 1001 llega como
    1001.0 y no casa con el '1001' de la base. Se recorta el .0 antes de
    comparar -- sin esto el importador no encuentra una sola unidad y reporta
    que el catalogo entero es desconocido.
    """
    if v is None:
        return ""
    t = str(v).strip()
    return t[:-2] if t.endswith(".0") else t


def leer(ruta: str) -> list:
    """Las filas del catalogo, ya normalizadas."""
    wb = load_workbook(ruta, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    filas = ws.iter_rows(values_only=True)
    encabezado = [str(c).strip() if c else "" for c in next(filas)]

    faltan = [c for c in (COL_ECONOMICO, COL_ESTATUS) if c not in encabezado]
    if faltan:
        raise SystemExit(
            "Al archivo le faltan columnas obligatorias: %s\n"
            "Las que trae son: %s" % (", ".join(faltan), ", ".join(encabezado)))

    idx = {c: encabezado.index(c) for c in encabezado if c}

    def celda(f, nombre):
        """El valor de una columna por nombre, o None.

        Las filas llegan DENTADAS: openpyxl corta cada una en su ultima celda
        con contenido, asi que una fila cuyas ultimas columnas estan vacias
        viene mas corta que el encabezado. Leerla por indice a secas revienta
        con IndexError en la primera fila a la que le falta la columna de hasta
        la derecha -- y son casi todas.
        """
        i = idx.get(nombre)
        if i is None or i >= len(f):
            return None
        return f[i]

    fuera = []
    for f in filas:
        eco = _economico(celda(f, COL_ECONOMICO))
        if not eco:
            continue
        texto = lambda c: (str(celda(f, c)).strip()      # noqa: E731
                           if celda(f, c) not in (None, "") else None)
        fuera.append({
            "economico": eco,
            "activa": _limpio(celda(f, COL_ESTATUS)) == ACTIVA,
            "sucursal": texto(COL_SUCURSAL),
            "supervisor": texto(COL_SUPERVISOR),
            "ruta": texto(COL_RUTA),
        })
    return fuera


def _talleres_por_nombre(db) -> dict:
    """Los talleres de la base, indexados por su nombre normalizado."""
    return {_limpio(t.nombre): t for t in db.query(m.Taller).all()}


def aplicar(db, filas: list, simular: bool = False) -> dict:
    """Corrige el padron. Devuelve el recuento de lo que cambio."""
    unidades = {u.num_economico.strip(): u for u in db.query(m.Unidad).all()
                if u.num_economico}
    talleres = _talleres_por_nombre(db)

    r = {"en_catalogo": len(filas), "activadas": 0, "desactivadas": 0,
         "sin_cambio": 0, "sucursal_puesta": 0, "sucursal_desconocida": {},
         "no_estan_en_la_base": [], "no_vienen_en_el_catalogo": 0}

    vistas = set()
    for f in filas:
        u = unidades.get(f["economico"])
        if u is None:
            r["no_estan_en_la_base"].append(f["economico"])
            continue
        vistas.add(u.id)

        if bool(u.activo) != f["activa"]:
            if not simular:
                u.activo = f["activa"]
            r["activadas" if f["activa"] else "desactivadas"] += 1
        else:
            r["sin_cambio"] += 1

        # La SUCURSAL es de donde es la unidad, no donde esta hoy. Se escribe en
        # taller_asignado_id y NUNCA en taller_actual_id: ese otro dice que la
        # unidad esta fisicamente adentro del taller, y pisarlo aqui meteria al
        # patio 628 unidades que andan en la calle.
        if f["sucursal"]:
            t = talleres.get(_limpio(f["sucursal"]))
            if t is None:
                r["sucursal_desconocida"][f["sucursal"]] = \
                    r["sucursal_desconocida"].get(f["sucursal"], 0) + 1
            elif u.taller_asignado_id != t.id:
                if not simular:
                    u.taller_asignado_id = t.id
                r["sucursal_puesta"] += 1

    r["no_vienen_en_el_catalogo"] = sum(1 for u in unidades.values()
                                        if u.id not in vistas)
    if not simular:
        db.commit()
    return r


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Actualiza el padron de unidades desde el Catalogo de Unidades.")
    p.add_argument("archivo", help="el .xlsx del catalogo")
    p.add_argument("--simular", action="store_true",
                   help="no escribe nada: solo dice que cambiaria")
    args = p.parse_args(argv)

    filas = leer(args.archivo)
    db = SessionLocal()
    try:
        antes_act = db.query(m.Unidad).filter(m.Unidad.activo.is_(True)).count()
        r = aplicar(db, filas, args.simular)
        despues = db.query(m.Unidad).filter(m.Unidad.activo.is_(True)).count()

        print("SIMULACRO -- no se escribio nada\n" if args.simular else "")
        print("Catalogo leido: %d unidades" % r["en_catalogo"])
        print()
        print("  activas antes      : %d" % antes_act)
        print("  activas despues    : %d" % (antes_act if args.simular else despues))
        print("  se dieron de baja  : %d" % r["desactivadas"])
        print("  se reactivaron     : %d" % r["activadas"])
        print("  sin cambio         : %d" % r["sin_cambio"])
        print("  sucursal asignada  : %d" % r["sucursal_puesta"])

        if r["sucursal_desconocida"]:
            print()
            print("  Sucursales del catalogo que NO son un taller de la base.")
            print("  Esas unidades se quedaron sin sucursal:")
            for nom, n in sorted(r["sucursal_desconocida"].items(),
                                 key=lambda x: -x[1]):
                print("    %-28s %d unidad(es)" % (nom, n))

        if r["no_estan_en_la_base"]:
            print()
            print("  En el catalogo pero NO en la base: %d"
                  % len(r["no_estan_en_la_base"]))
            print("    %s" % ", ".join(r["no_estan_en_la_base"][:12]))

        if r["no_vienen_en_el_catalogo"]:
            print()
            print("  En la base pero NO en el catalogo: %d"
                  % r["no_vienen_en_el_catalogo"])
            print("  NO se les toco el estado: pueden ser altas recientes, y")
            print("  darlas de baja por ausencia sacaria de circulacion una")
            print("  unidad que si trabaja. Revisalo con logistica.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
