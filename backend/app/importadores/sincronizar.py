"""Pone al dia la base con los Excel de las areas, en el orden correcto.

POR QUE EXISTE. Los importadores ya estaban, uno por archivo y cada uno con las
manas de su Excel. Pero se corrian a mano, uno por uno, en un orden que solo
estaba escrito en sus comentarios, y nadie los corria. Este archivo es lo que
los vuelve un alimentador: el reloj del servidor lo corre cada madrugada contra
la carpeta donde se dejan los Excel nuevos de cada area.

EL ORDEN NO ES CAPRICHO:

  1. base       INFO CHOFERES + REQUIS + CODIGOS: plantas, supervisores,
                choferes, unidades, tecnicos y refacciones con su codigo de SAP
  2. limpieza   funde las unidades duplicadas ANTES de que entre el catalogo;
                al reves quedan seis escrituras del mismo camion
  3. flota      UNIDADES BAJA GAS: placas y VIN
  4. catalogo   UNIDADES BAJA GAS: activa/inactiva y sucursal (el 628)
  5. personal   CHOFERES LAN + INFO CHOFERES: telefonos, turnos, rutas
  6. taller     RESUMEN: el historial de entradas y el patio

CADA PASO VA POR SU LADO. Si el archivo de un area no llego, ese paso se salta y
los demas corren: que Logistica no mande su catalogo no es razon para dejar al
taller sin su historial. Si un paso truena, se revierte lo que no alcanzo a
guardar y los demas siguen. Y todos son idempotentes -- medido: corridos dos
veces, la segunda no cambia una sola fila --, asi que correrlo cada noche con
el mismo archivo no hace nada.

--simular corre todo sobre una COPIA de la base y la tira al final. No hay otra
forma honesta: los importadores guardan por dentro (el base hasta dos veces a
media corrida), asi que un simulacro con rollback se quedaria corto.

Antes de una corrida de verdad se respalda la base en la misma carpeta de
datos, y se guardan las ultimas siete.

Uso, dentro del contenedor de la API:

    python -m app.importadores.sincronizar --carpeta /datos/areas --simular
    python -m app.importadores.sincronizar --carpeta /datos/areas

Los archivos van con su nombre de siempre (ver ARCHIVOS abajo). El de REQUIS
puede llevar cualquier cosa despues de 'REQUIS'.
"""
import argparse
import contextlib
import datetime
import glob
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .. import importador
from ..core.database import DATABASE_URL, SessionLocal
from . import catalogo_unidades, flota, limpieza, personal, taller

# Lo que cada paso necesita encontrar en la carpeta. Los nombres se toman de
# cada importador y no se repiten aqui: si un importador cambia de archivo,
# este no se queda buscando el viejo.
ARCHIVOS = {
    "base": [personal.ARCHIVO_INFO],
    "limpieza": [],
    "flota": [flota.ARCHIVO],
    "catalogo": [flota.ARCHIVO],
    "personal": [personal.ARCHIVO_LAN, personal.ARCHIVO_INFO],
    "taller": [taller.ARCHIVO],
}

RESPALDOS_A_GUARDAR = 7


def _pasos(carpeta: str):
    """(nombre, que hace, funcion) en el orden en que tienen que correr."""
    return [
        ("base", "choferes, unidades, supervisores y refacciones de SAP",
         # contrasena=None: una cuenta que nace de madrugada recibe una
         # contrasena al azar, no la de prueba. Ver importador.importar.
         lambda db: importador.importar(db, carpeta, contrasena=None)),
        ("limpieza", "funde unidades duplicadas",
         lambda db: limpieza.limpiar(db)),
        ("flota", "placas y VIN",
         lambda db: flota.importar(db, carpeta)),
        ("catalogo", "unidades activas y su sucursal",
         lambda db: catalogo_unidades.aplicar(
             db, catalogo_unidades.leer(os.path.join(carpeta, flota.ARCHIVO)))),
        ("personal", "telefonos, turnos y rutas",
         lambda db: personal.importar(db, carpeta)),
        ("taller", "historial de entradas y patio",
         lambda db: taller.importar(db, carpeta)),
    ]


def _ruta_base() -> str | None:
    if not DATABASE_URL.startswith("sqlite:///"):
        return None
    return DATABASE_URL[len("sqlite:///"):]


def _copiar_base(origen: str, destino: str):
    """Copia consistente aunque la aplicacion este escribiendo en ese momento.

    Con shutil.copy, una escritura a media copia deja un archivo corrupto. La
    API de respaldo de SQLite copia una foto coherente de la base.
    """
    src = sqlite3.connect(origen)
    dst = sqlite3.connect(destino)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _conteos(ruta: str) -> dict:
    c = sqlite3.connect(ruta)
    try:
        return {t: c.execute("select count(*) from \"%s\"" % t).fetchone()[0]
                for (t,) in c.execute(
                    "select name from sqlite_master where type='table'")}
    finally:
        c.close()


def _resumible(v, tope=20):
    """El resultado de un paso, sin listas de mil elementos."""
    if isinstance(v, dict):
        return {k: _resumible(x, tope) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        v = list(v)
        return v[:tope] + (["... y %d mas" % (len(v) - tope)] if len(v) > tope else [])
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def _respaldar(ruta: str) -> str:
    carpeta = os.path.dirname(ruta)
    hoy = datetime.date.today().isoformat()
    destino = os.path.join(carpeta, "bajagas.db.antes-sincronizar-%s" % hoy)
    _copiar_base(ruta, destino)
    viejos = sorted(glob.glob(os.path.join(carpeta, "bajagas.db.antes-sincronizar-*")))
    for v in viejos[:-RESPALDOS_A_GUARDAR]:
        os.remove(v)
    return destino


def sincronizar(carpeta: str, simular: bool = False) -> dict:
    ruta = _ruta_base()
    if ruta is None:
        raise SystemExit("Solo sabe sincronizar sobre SQLite.")

    informe = {"carpeta": carpeta, "simulacro": simular,
               "inicio": datetime.datetime.now().isoformat(timespec="seconds"),
               "pasos": [], "cambios": {}, "cuentas_nuevas": []}

    temporal = None
    if simular:
        temporal = tempfile.mkdtemp(prefix="simulacro-")
        trabajo = os.path.join(temporal, "copia.db")
        _copiar_base(ruta, trabajo)
        Sesion = sessionmaker(bind=create_engine(
            "sqlite:///" + trabajo, connect_args={"check_same_thread": False}),
            autocommit=False, autoflush=False)
    else:
        trabajo = ruta
        informe["respaldo"] = _respaldar(ruta)
        Sesion = SessionLocal

    try:
        antes = _conteos(trabajo)
        for nombre, que, correr in _pasos(carpeta):
            paso = {"paso": nombre, "que": que}
            faltan = [a for a in ARCHIVOS[nombre]
                      if not os.path.exists(os.path.join(carpeta, a))]
            if faltan:
                paso.update(estado="omitido", motivo="falta " + ", ".join(faltan))
                informe["pasos"].append(paso)
                continue
            db = Sesion()
            t0 = time.time()
            try:
                # Los importadores imprimen su propio informe; aqui estorba.
                with contextlib.redirect_stdout(io.StringIO()):
                    r = correr(db)
                db.commit()
                paso.update(estado="ok", resultado=_resumible(r))
                if isinstance(r, dict):
                    informe["cuentas_nuevas"] += r.get("cuentas_nuevas", [])
            except Exception as e:  # un area rota no tumba a las demas
                db.rollback()
                paso.update(estado="error", motivo="%s: %s" % (type(e).__name__, e))
            finally:
                db.close()
                paso["segundos"] = round(time.time() - t0, 1)
            informe["pasos"].append(paso)
        despues = _conteos(trabajo)
        informe["cambios"] = {t: [antes.get(t, 0), n] for t, n in despues.items()
                              if antes.get(t, 0) != n}
    finally:
        if temporal:
            shutil.rmtree(temporal, ignore_errors=True)

    informe["fin"] = datetime.datetime.now().isoformat(timespec="seconds")
    if not simular:
        # Lo lee quien quiera saber como fue la ultima: la pantalla, el journal.
        with open(os.path.join(carpeta, "ultima-sincronizacion.json"), "w",
                  encoding="utf-8") as f:
            json.dump(informe, f, ensure_ascii=False, indent=1)
    return informe


def _imprimir(inf: dict):
    print("SIMULACRO -- la base real no se toco" if inf["simulacro"]
          else "SINCRONIZACION -- respaldo en %s" % inf.get("respaldo"))
    print("Carpeta: %s\n" % inf["carpeta"])
    for p in inf["pasos"]:
        linea = "  %-9s %-8s %s" % (p["paso"], p["estado"].upper(), p["que"])
        if p["estado"] != "ok":
            linea += "  <- " + p["motivo"]
        print(linea)
    print()
    if inf["cambios"]:
        print("Filas que cambian:")
        for t, (a, d) in sorted(inf["cambios"].items()):
            print("  %-26s %7d -> %7d  (%+d)" % (t, a, d, d - a))
    else:
        print("No cambia ninguna fila: la base ya estaba al dia con estos archivos.")
    if inf["cuentas_nuevas"]:
        print("\nCuentas nuevas (%d). Tienen una contrasena al azar que nadie"
              " conoce: hay que entregarles la suya." % len(inf["cuentas_nuevas"]))
        for c in inf["cuentas_nuevas"][:20]:
            print("  " + c)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Pone al dia la base con los Excel de las areas.")
    p.add_argument("--carpeta", default=os.environ.get(
        "DATOS_REALES", importador.CARPETA_DATOS),
        help="donde estan los Excel (por omision DATOS_REALES o datos/)")
    p.add_argument("--simular", action="store_true",
                   help="corre sobre una copia de la base y dice que cambiaria")
    args = p.parse_args(argv)

    if not os.path.isdir(args.carpeta):
        # No es un error: es la noche en que ningun area ha mandado nada.
        print("No existe la carpeta %s: no hay archivos que sincronizar." % args.carpeta)
        return 0
    inf = sincronizar(args.carpeta, args.simular)
    _imprimir(inf)
    return 1 if any(p["estado"] == "error" for p in inf["pasos"]) else 0


if __name__ == "__main__":
    sys.exit(main())
