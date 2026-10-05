"""Arranque operativo oficial: borra la operacion de prueba, deja los catalogos.

La NOM-030 (7.1.10) pide que la bitacora diga la verdad y que lo que se escriba
en ella ya no se borre. Por eso este script se corre UNA sola vez, antes de que
el taller empiece a registrar en serio, y despues se niega a correr: deja la
marca `arranque_operativo` en configuracion.

Dentro del contenedor de la API:

    python -m app.reset_produccion                             # simula
    python -m app.reset_produccion --ejecutar --confirmo ARRANQUE

La simulacion hace TODO sobre una copia temporal de la base y reporta lo que
paso ahi; la base real no se toca. Al ejecutar:

  1. Respalda la base completa junto a ella (bajagas.db.antes-arranque-<fecha>).
  2. En UNA transaccion: quita los candados NOM-030, borra la operacion de
     prueba, devuelve unidades y programas al estado sin esa operacion, deja
     constancia en la bitacora de auditoria y vuelve a poner los candados. Si
     algo falla, no queda nada a medias.
  3. Mueve las fotos de evidencia a una carpeta aparte (no las borra).

Se conserva: unidades, usuarios, roles, choferes, supervisores, tecnicos,
plantillas, talleres y espacios, refacciones y existencias, proveedores, planes
y programas de mantenimiento, requisiciones (vienen del papel/SAP), el historial
de entradas del Excel del taller (movimiento_taller), configuracion y la
bitacora de auditoria.

Los folios se calculan contando renglones (siguiente_folio), asi que al quedar
vacias las tablas vuelven a empezar en 00001.
"""
import argparse
import json
import os
import pathlib
import shutil
import sqlite3
import sys
import tempfile

from .core.migraciones import CANDADOS, sql_candado
from .core.tiempo import ahora_utc

CLAVE_ARRANQUE = "arranque_operativo"
CLAVE_LIBRO_DESDE = "nom030_libro_desde"
PALABRA = "ARRANQUE"

# En el orden en que se borran: primero lo que cuelga, luego de lo que cuelga.
GRUPOS = [
    ("Libro de bitacora y formatos de mantenimiento",
     ["bitacora_mantenimiento", "punto_revision", "firma_reporte",
      "actividad_reporte", "reporte_mantenimiento"]),
    ("Piezas pedidas por las ordenes",
     ["orden_compra", "autorizacion", "detalle_presupuesto", "presupuesto",
      "solicitud_pieza"]),
    ("Ordenes de servicio",
     ["traslado_unidad", "ocupacion_espacio", "formato_salida",
      "asignacion_tecnico", "orden_servicio"]),
    ("Fallas, arrastres y auxilio",
     ["respuesta_auxilio", "difusion_auxilio", "orden_auxilio",
      "ubicacion_arrastre", "arrastre", "reporte_peritaje", "detalle_choque",
      "reporte_averia"]),
    ("Agenda y avisos a choferes",
     ["amonestacion", "penalizacion", "aviso_incumplimiento", "reprogramacion",
      "cita_taller", "solicitud_ingreso"]),
    ("Jornadas, prestamos y ubicaciones",
     ["prestamo_unidad", "jornada", "ubicacion_unidad"]),
    ("Notificaciones",
     ["notificacion", "alerta_gerencia"]),
    ("Evidencias (fotos)",
     ["evidencia"]),
]
TABLAS = [t for _, ts in GRUPOS for t in ts]

VIVOS = ("pendiente", "agendado", "sin_cupo", "vencido")
COLUMNAS_FECHA = ("creado_en", "fecha", "fecha_reporte", "fecha_entrada",
                  "fecha_inicio", "fecha_cita", "registrado_en", "fecha_creacion")


def _ruta_base() -> str:
    from .core.database import engine
    if engine.dialect.name != "sqlite":
        sys.exit(f"Este script es para SQLite; la base es {engine.dialect.name}.")
    return engine.url.database


def _raiz_evidencias() -> pathlib.Path:
    return pathlib.Path(os.environ.get("EVIDENCIAS_DIR", "/datos/evidencias"))


def _copiar(origen: str, destino: str):
    src, dst = sqlite3.connect(origen), sqlite3.connect(destino)
    try:
        src.backup(dst)
        ok = dst.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        src.close()
        dst.close()
    if ok != "ok":
        raise RuntimeError(f"El respaldo {destino} salio danado: {ok}")


def _tablas(cx) -> set:
    return {r[0] for r in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _config(cx, clave):
    r = cx.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
    return r[0] if r else None


def _poner_config(cx, clave, valor, descripcion):
    if _config(cx, clave) is None:
        cx.execute("INSERT INTO configuracion (clave, valor, descripcion, tipo_dato) "
                   "VALUES (?, ?, ?, 'fecha')", (clave, valor, descripcion))
    else:
        cx.execute("UPDATE configuracion SET valor = ? WHERE clave = ?", (valor, clave))


def _rango(cx, tabla) -> str:
    cols = {r[1] for r in cx.execute(f"PRAGMA table_info({tabla})")}
    for c in COLUMNAS_FECHA:
        if c in cols:
            lo, hi = cx.execute(f"SELECT min({c}), max({c}) FROM {tabla}").fetchone()
            if lo:
                return f"{str(lo)[:10]} a {str(hi)[:10]}"
    return ""


def _fk_rotas(cx) -> set:
    return {(r[0], r[1], r[2]) for r in cx.execute("PRAGMA foreign_key_check")}


def inventario(cx) -> dict:
    """Lo que hay hoy, para que un humano confirme que es de prueba."""
    existentes = _tablas(cx)
    tablas = {}
    for t in TABLAS:
        if t in existentes:
            n = cx.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            tablas[t] = {"renglones": n, "fechas": _rango(cx, t) if n else ""}
    quien = cx.execute(
        "SELECT coalesce(u.nombre || ' ' || coalesce(u.apellidos, ''), '(sin usuario)'), count(*) "
        "FROM orden_servicio o LEFT JOIN usuario u ON u.id = o.abierta_por_admin_id "
        "GROUP BY 1 ORDER BY 2 DESC").fetchall()
    # Catalogo que NO es verdadero y este script no toca (lo pidio asi el
    # cliente: catalogos intactos). Se avisa para decidirlo aparte.
    from .seed import TECNICOS_DEMO
    nums = [n for _, _, n, _ in TECNICOS_DEMO]
    tecnicos = cx.execute(
        f"SELECT nombre || ' ' || apellidos FROM tecnico WHERE num_empleado IN "
        f"({','.join('?' * len(nums))})", nums).fetchall()
    unidades = cx.execute(
        "SELECT num_economico FROM unidad WHERE vin LIKE 'VIN%0000000'").fetchall()
    return {"tablas": tablas, "ordenes_por": quien,
            "tecnicos_de_prueba": [r[0] for r in tecnicos],
            "unidades_de_prueba": [r[0] for r in unidades]}


def purgar(cx, ahora, respaldo, evidencias_a) -> dict:
    """Todo en una transaccion. Devuelve lo que hizo; si falla, ROLLBACK."""
    existentes = _tablas(cx)
    rotas_antes = _fk_rotas(cx)
    cx.execute("BEGIN IMMEDIATE")
    try:
        for nombre, _, tabla, _, _ in CANDADOS:
            cx.execute(f"DROP TRIGGER IF EXISTS {nombre}")

        # --- programas de mantenimiento: sin la operacion de prueba vuelven a
        # deberse. Uno que una orden de prueba dio por cumplido regresa a
        # pendiente, salvo que la unidad ya tenga otro vivo del mismo plan.
        prog = {"a_pendiente": 0, "sobraban": 0, "desligados": 0}
        cumplidos = cx.execute(
            "SELECT id, unidad_id, plan_id FROM programa_mantenimiento "
            "WHERE estado = 'cumplido' AND orden_servicio_id IS NOT NULL").fetchall()
        for pid, unidad_id, plan_id in cumplidos:
            otro = cx.execute(
                f"SELECT 1 FROM programa_mantenimiento WHERE unidad_id = ? AND plan_id = ? "
                f"AND id != ? AND estado IN ({','.join('?' * len(VIVOS))})",
                (unidad_id, plan_id, pid, *VIVOS)).fetchone()
            if otro:
                cx.execute("DELETE FROM programa_mantenimiento WHERE id = ?", (pid,))
                prog["sobraban"] += 1
            else:
                cx.execute("UPDATE programa_mantenimiento SET estado = 'pendiente', "
                           "orden_servicio_id = NULL, fecha_cumplimiento = NULL "
                           "WHERE id = ?", (pid,))
                prog["a_pendiente"] += 1
        # Las citas se van: lo agendado vuelve a pendiente y la agenda de las
        # 06:00 lo acomoda de nuevo.
        prog["a_pendiente"] += cx.execute(
            "UPDATE programa_mantenimiento SET estado = 'pendiente' "
            "WHERE estado IN ('agendado', 'sin_cupo')").rowcount
        prog["desligados"] = cx.execute(
            "UPDATE programa_mantenimiento SET orden_servicio_id = NULL "
            "WHERE orden_servicio_id IS NOT NULL").rowcount

        # --- unidades: el estado, el taller, el km y el poseedor los pusieron
        # las ordenes, jornadas y prestamos de prueba.
        uni = {}
        uni["km_a_cero"] = cx.execute(
            "UPDATE unidad SET km_actual = 0 WHERE km_actual != 0 AND id IN "
            "(SELECT DISTINCT unidad_id FROM jornada)").rowcount if "jornada" in existentes else 0
        uni["a_disponible"] = cx.execute(
            "UPDATE unidad SET estado = 'disponible' "
            "WHERE estado NOT IN ('disponible', 'baja')").rowcount
        uni["fuera_del_taller"] = cx.execute(
            "UPDATE unidad SET taller_actual_id = NULL "
            "WHERE taller_actual_id IS NOT NULL").rowcount
        uni["poseedor_al_titular"] = cx.execute(
            "UPDATE unidad SET poseedor_chofer_id = titular_chofer_id "
            "WHERE poseedor_chofer_id IS NOT titular_chofer_id").rowcount

        # --- casillas: las ocupaciones de prueba se van abajo, y con ellas cada
        # casilla tiene que quedar libre. Esto faltaba: T-01 y T-02 de Alamos
        # quedaron "ocupadas" sin unidad adentro (ver reconciliar_espacios).
        uni["casillas_liberadas"] = (cx.execute(
            "UPDATE espacio SET estado = 'libre' WHERE estado = 'ocupado'").rowcount
            if "espacio" in existentes else 0)

        borrados = {}
        for t in TABLAS:
            if t in existentes:
                borrados[t] = cx.execute(f"DELETE FROM {t}").rowcount
        if "sqlite_sequence" in existentes:
            cx.execute(f"DELETE FROM sqlite_sequence WHERE name IN "
                       f"({','.join('?' * len(TABLAS))})", TABLAS)

        instante = ahora.isoformat()
        _poner_config(cx, CLAVE_ARRANQUE, instante,
                      "Arranque operativo oficial: antes de esto se borro la "
                      "operacion de prueba. reset_produccion.py ya no vuelve a correr.")
        _poner_config(cx, CLAVE_LIBRO_DESDE, instante,
                      "NOM-030 7.1.10: instante en que empezo el libro de bitacora "
                      "electronico.")

        hecho = {"borrados": borrados, "programas": prog, "unidades": uni,
                 "respaldo": respaldo, "evidencias_a": evidencias_a}
        cx.execute(
            "INSERT INTO bitacora_auditoria (usuario_id, accion, entidad_tipo, "
            "datos_despues, fecha) VALUES (NULL, 'arranque_operativo', 'sistema', ?, ?)",
            (json.dumps(hecho, ensure_ascii=False),
             ahora.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")))

        for c in CANDADOS:
            if c[2] in existentes:
                cx.execute(sql_candado(*c))

        nuevas = _fk_rotas(cx) - rotas_antes
        if nuevas:
            raise RuntimeError(f"Quedarian referencias rotas: {sorted(nuevas)[:10]}")
        cx.execute("COMMIT")
        return hecho
    except Exception:
        cx.execute("ROLLBACK")
        raise


def _imprimir(inv, hecho=None, evidencias=0):
    print("\nOperacion que se borra:")
    for titulo, ts in GRUPOS:
        n = sum(inv["tablas"].get(t, {}).get("renglones", 0) for t in ts)
        print(f"  {titulo}: {n}")
        for t in ts:
            d = inv["tablas"].get(t)
            if d and d["renglones"]:
                print(f"      {t:24} {d['renglones']:6}   {d['fechas']}")
    print(f"  Fotos en disco: {evidencias} (se mueven a otra carpeta, no se borran)")
    if inv["ordenes_por"]:
        print("\nOrdenes de servicio abiertas por:")
        for quien, n in inv["ordenes_por"]:
            print(f"      {quien}: {n}")
    if hecho:
        print("\nUnidades devueltas a su estado sin operacion:", hecho["unidades"])
        print("Programas de mantenimiento:", hecho["programas"])
    if inv["tecnicos_de_prueba"] or inv["unidades_de_prueba"]:
        print("\nATENCION: en los catalogos hay datos inventados por el sembrado y "
              "este script NO los toca:")
        if inv["tecnicos_de_prueba"]:
            print("      tecnicos:", ", ".join(inv["tecnicos_de_prueba"]))
        if inv["unidades_de_prueba"]:
            print("      unidades:", ", ".join(inv["unidades_de_prueba"]))


def _contar_fotos(raiz: pathlib.Path) -> int:
    return sum(1 for p in raiz.rglob("*") if p.is_file()) if raiz.exists() else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ejecutar", action="store_true",
                    help="borrar de verdad (sin esto solo simula)")
    ap.add_argument("--confirmo", default="",
                    help=f"escribir {PALABRA} para confirmar --ejecutar")
    args = ap.parse_args(argv)

    ruta = _ruta_base()
    if not os.path.exists(ruta):
        sys.exit(f"No existe la base {ruta}")
    cx = sqlite3.connect(ruta, isolation_level=None, timeout=30)
    ya = _config(cx, CLAVE_ARRANQUE)
    if ya:
        print(f"El arranque operativo ya se hizo ({ya}). Desde entonces los registros "
              f"son reales y la NOM-030 no permite borrarlos. No se hace nada.")
        return 1
    from .core.database import SessionLocal
    from .jobs import hay_demo_sembrado
    with SessionLocal() as db:
        if hay_demo_sembrado(db):
            print("La base trae el demo sembrado. Primero: "
                  "python -m app.sembrar_demo --deshacer")
            return 1

    raiz = _raiz_evidencias()
    fotos = _contar_fotos(raiz)
    inv = inventario(cx)
    ahora = ahora_utc()
    sello = ahora.strftime("%Y%m%d-%H%M%S")
    evidencias_a = str(raiz.parent / f"{raiz.name}.antes-arranque-{sello}")

    if not args.ejecutar:
        # Todo el camino, pero sobre una copia: si algo fallara, falla aqui.
        cx.close()
        with tempfile.TemporaryDirectory() as tmp:
            copia = os.path.join(tmp, "simulacro.db")
            _copiar(ruta, copia)
            cc = sqlite3.connect(copia, isolation_level=None)
            try:
                hecho = purgar(cc, ahora, "(simulacro)", evidencias_a)
                folio = cc.execute("SELECT count(*) FROM orden_servicio").fetchone()[0] + 1
                candados = cc.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger' "
                                      "AND name IN (%s)" % ",".join("'%s'" % c[0] for c in CANDADOS)
                                      ).fetchone()[0]
            finally:
                cc.close()
        _imprimir(inv, hecho, fotos)
        print(f"\nSIMULACRO sobre una copia: salio bien. Candados puestos: {candados}. "
              f"Primera orden nueva: OS-{ahora.year}-{folio:05d}.")
        print("La base real NO se toco. Para hacerlo de verdad:\n"
              f"  python -m app.reset_produccion --ejecutar --confirmo {PALABRA}")
        return 0

    if args.confirmo != PALABRA:
        print(f"Para borrar hay que agregar --confirmo {PALABRA}. No se hizo nada.")
        return 1

    respaldo = f"{ruta}.antes-arranque-{sello}"
    _copiar(ruta, respaldo)
    print(f"Respaldo: {respaldo}")
    hecho = purgar(cx, ahora, respaldo, evidencias_a if fotos else None)
    cx.close()
    if fotos:
        shutil.move(str(raiz), evidencias_a)
        raiz.mkdir(parents=True, exist_ok=True)
        print(f"Fotos movidas a: {evidencias_a}")
    _imprimir(inv, hecho, fotos)
    print(f"\nARRANQUE OPERATIVO hecho ({ahora.isoformat()}). Los folios empiezan en 00001. "
          f"Este script ya no vuelve a correr.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
