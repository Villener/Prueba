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


def _foto(ruta: str) -> dict:
    """{tabla: {rowid: huella de la fila}}.

    Fila por fila y no solo cuantas hay. La primera version contaba filas, y en
    produccion el simulacro dijo «no cambia ninguna fila» con 86 unidades por
    darse de baja: el catalogo no agrega ni quita unidades, les cambia un campo,
    y un conteo no ve eso. Un simulacro que calla lo que va a hacer es peor que
    no tenerlo.

    `actualizado_en` no cuenta: es la hora del cambio, no el cambio.
    """
    c = sqlite3.connect(ruta)
    try:
        foto = {}
        for (t,) in c.execute("select name from sqlite_master where type='table'"
                              " and name not like 'sqlite_%'").fetchall():
            cols = [r[1] for r in c.execute('pragma table_info("%s")' % t)
                    if r[1] != "actualizado_en"]
            lista = ", ".join('"%s"' % x for x in cols)
            foto[t] = {r[0]: hash(r[1:]) for r in
                       c.execute('select rowid, %s from "%s"' % (lista, t))}
        return foto
    finally:
        c.close()


def _diferencias(antes: dict, despues: dict) -> dict:
    """{tabla: {nuevas, borradas, cambiadas, _muestra}} de las que se movieron.

    `_muestra` son unos cuantos rowid de filas cambiadas, para enseñar QUE
    cambio y no solo cuanto.
    """
    out = {}
    for t in set(antes) | set(despues):
        a, d = antes.get(t, {}), despues.get(t, {})
        nuevas = len(d.keys() - a.keys())
        borradas = len(a.keys() - d.keys())
        cambiadas = [k for k in a.keys() & d.keys() if a[k] != d[k]]
        if nuevas or borradas or cambiadas:
            out[t] = {"nuevas": nuevas, "borradas": borradas,
                      "cambiadas": len(cambiadas), "_muestra": sorted(cambiadas)[:6]}
    return out


def _ejemplos(ruta_antes: str, ruta_despues: str, cambios: dict) -> dict:
    """{tabla: ["id 349: nombre 'Jesus Orlando' -> 'Jesus Or'", ...]}.

    Sin esto el simulacro decia «usuario: 5 cambiadas» y no se veia que la
    sincronizacion estaba mochando nombres de choferes. Los numeros dicen
    cuanto; los ejemplos dicen si esta bien.
    """
    a, d = sqlite3.connect(ruta_antes), sqlite3.connect(ruta_despues)
    out = {}
    try:
        for t, x in cambios.items():
            ids = x.pop("_muestra", [])
            if not ids:
                continue
            cols = [r[1] for r in d.execute('pragma table_info("%s")' % t)
                    if r[1] != "actualizado_en"]
            q = 'select rowid, %s from "%s" where rowid = ?' % (
                ", ".join('"%s"' % c for c in cols), t)
            lineas = []
            for rid in ids:
                fa, fd = a.execute(q, (rid,)).fetchone(), d.execute(q, (rid,)).fetchone()
                if not fa or not fd:
                    continue
                dif = ["%s %r -> %r" % (c, fa[i + 1], fd[i + 1])
                       for i, c in enumerate(cols) if fa[i + 1] != fd[i + 1]]
                lineas.append("fila %s: %s" % (rid, "; ".join(dif)))
            out[t] = lineas
    finally:
        a.close(); d.close()
    return out


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
        antes = _foto(trabajo)
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
        informe["cambios"] = _diferencias(antes, _foto(trabajo))
        informe["ejemplos"] = _ejemplos(
            ruta if simular else informe["respaldo"], trabajo, informe["cambios"])
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
        # Lo que el propio importador dice que hizo, en sus palabras: «se dieron
        # de baja 86» dice mas que «unidad: 86 cambiadas».
        for k, v in (p.get("resultado") or {}).items():
            if isinstance(v, (int, float)) and v and not isinstance(v, bool):
                print("  %9s %-8s   %-28s %s" % ("", "", k, v))
    print()
    if inf["cambios"]:
        print("Filas que cambian:")
        print("  %-26s %8s %8s %9s" % ("", "nuevas", "borradas", "cambiadas"))
        for t, x in sorted(inf["cambios"].items()):
            print("  %-26s %8d %8d %9d" % (t, x["nuevas"], x["borradas"], x["cambiadas"]))
        for t, lineas in sorted(inf.get("ejemplos", {}).items()):
            print()
            print("Ejemplos de %s:" % t)
            for l in lineas:
                print("  " + l)
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
