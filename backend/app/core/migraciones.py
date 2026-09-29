"""Ajustes de esquema que `create_all` no aplica solo.

`Base.metadata.create_all()` crea las tablas que faltan, pero NO agrega indices
nuevos a tablas que ya existen. Sin esto, quien ya tenia una base de datos se
quedaria sin los candados de integridad y el defecto del vehiculo duplicado
seguiria vivo en su maquina aunque el codigo ya este corregido.

La sintaxis de indice unico parcial es la misma en SQLite (3.8+) y en
PostgreSQL (9.5+), asi que un solo SQL sirve para los dos.
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

log = logging.getLogger(__name__)


def _default_sql(col):
    """Convierte el default del modelo en un literal SQL, o None si no hay.

    Se ignoran los defaults que son funciones de Python (como el reloj del
    sistema): esos no se pueden escribir en un ALTER TABLE.
    """
    if col.server_default is not None:
        return None  # ya viaja dentro del DDL que compila SQLAlchemy
    d = col.default
    if d is None or getattr(d, "is_callable", False) or not getattr(d, "is_scalar", False):
        return None
    v = d.arg
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return None


def asegurar_columnas(engine, metadata) -> list[str]:
    """Agrega las columnas que el modelo tiene y la base todavia no.

    `create_all()` crea TABLAS que faltan, pero nunca toca una tabla que ya
    existe. Al migrar a v2.0 se agregaron columnas (taller.planta_id,
    unidad.taller_asignado_id, tecnico.modalidad...) y sin esto una base previa
    empieza a responder error 500 en cuanto se consulta cualquiera de ellas.

    Solo se agregan columnas NUEVAS y nulables o con default. No se renombra ni
    se borra nada: eso necesita una migracion pensada, no un arranque.
    """
    hechos = []
    insp = inspect(engine)
    tablas_reales = set(insp.get_table_names())

    with engine.begin() as cx:
        for tabla in metadata.sorted_tables:
            if tabla.name not in tablas_reales:
                continue  # create_all ya la creo completa
            existentes = {c["name"] for c in insp.get_columns(tabla.name)}
            for col in tabla.columns:
                if col.name in existentes or col.primary_key:
                    continue
                literal = _default_sql(col)
                if not col.nullable and literal is None:
                    hechos.append(f"~ {tabla.name}.{col.name}: obligatoria y sin valor por "
                                  "defecto; se omite (requiere migracion manual)")
                    continue

                ddl = CreateColumn(col).compile(engine).string
                # La FK no se puede declarar en un ADD COLUMN de SQLite.
                ddl = ddl.split(" REFERENCES ")[0]
                # `default=` de SQLAlchemy se aplica en Python, NO llega al SQL:
                # sin un DEFAULT explicito, agregar una columna NOT NULL a una
                # tabla con filas falla siempre.
                if literal is not None and "DEFAULT" not in ddl.upper():
                    ddl = f"{ddl} DEFAULT {literal}"
                try:
                    cx.execute(text(f"ALTER TABLE {tabla.name} ADD COLUMN {ddl}"))
                    hechos.append(f"+ {tabla.name}.{col.name}")
                except Exception as e:  # pragma: no cover
                    hechos.append(f"! {tabla.name}.{col.name}: {e}")
    for h in hechos:
        log.info(h)
    return hechos

# (nombre, SQL de creacion, SQL que cuenta los conflictos que lo impedirian)
INDICES = [
    (
        "uq_orden_abierta_por_unidad",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_orden_abierta_por_unidad "
        "ON orden_servicio (unidad_id) WHERE fecha_salida IS NULL",
        "SELECT COUNT(*) FROM (SELECT unidad_id FROM orden_servicio "
        "WHERE fecha_salida IS NULL GROUP BY unidad_id HAVING COUNT(*) > 1) x",
        "hay unidades con mas de una orden de servicio abierta",
    ),
    (
        "uq_ocupacion_abierta_por_unidad",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_ocupacion_abierta_por_unidad "
        "ON ocupacion_espacio (unidad_id) WHERE fecha_salida IS NULL",
        "SELECT COUNT(*) FROM (SELECT unidad_id FROM ocupacion_espacio "
        "WHERE fecha_salida IS NULL GROUP BY unidad_id HAVING COUNT(*) > 1) x",
        "hay unidades ocupando mas de un espacio",
    ),
    (
        "uq_ocupacion_abierta_por_espacio",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_ocupacion_abierta_por_espacio "
        "ON ocupacion_espacio (espacio_id) WHERE fecha_salida IS NULL",
        "SELECT COUNT(*) FROM (SELECT espacio_id FROM ocupacion_espacio "
        "WHERE fecha_salida IS NULL GROUP BY espacio_id HAVING COUNT(*) > 1) x",
        "hay espacios con mas de una unidad adentro",
    ),
]


def asegurar_indices(engine) -> list[str]:
    """Crea los candados que falten. Devuelve la lista de avisos.

    Nunca tumba el arranque: si la base ya trae datos que violan el candado,
    lo reporta con el motivo y sigue. Es preferible arrancar con un aviso claro
    que negarse a arrancar sin explicar por que.
    """
    avisos = []
    with engine.begin() as cx:
        for nombre, crear, contar, motivo in INDICES:
            try:
                conflictos = cx.execute(text(contar)).scalar() or 0
            except Exception:
                # La tabla todavia no existe (base recien creada); create_all
                # ya la habra hecho con su indice.
                continue
            if conflictos:
                aviso = (f"No se pudo crear {nombre}: {motivo} "
                         f"({conflictos} caso[s]). Corrige esos registros y reinicia.")
                log.warning(aviso)
                avisos.append(aviso)
                continue
            try:
                cx.execute(text(crear))
            except Exception as e:  # pragma: no cover
                aviso = f"No se pudo crear {nombre}: {e}"
                log.warning(aviso)
                avisos.append(aviso)
    return avisos


# --------------------------------------------------------------------------- #
# Renombres deliberados
# --------------------------------------------------------------------------- #
# El cliente corrigio el vocabulario el 2026-09-14: al grupo de CHOFERES se le
# dice PLANTILLA, no cuadrilla. Renombrar en el modelo no basta: `create_all`
# habria creado una tabla `plantilla` vacia al lado de la `cuadrilla` con los
# datos adentro, y el supervisor abriria su pantalla sin un solo chofer.
#
# Por eso esto corre ANTES de create_all, y por eso es un renombre y no un
# "crear y copiar": renombrar conserva los ids, y los ids son lo que apunta
# chofer.plantilla_id.
RENOMBRES_TABLA = [("cuadrilla", "plantilla")]
RENOMBRES_COLUMNA = [("chofer", "cuadrilla_id", "plantilla_id")]


def asegurar_renombres(engine) -> list[str]:
    """Aplica los renombres de tabla y columna que el modelo ya da por hechos.

    Idempotente: si el renombre ya ocurrio, no hace nada. En una base recien
    creada tampoco hace nada, porque no existe el nombre viejo.
    """
    hechos = []
    insp = inspect(engine)
    tablas = set(insp.get_table_names())

    with engine.begin() as cx:
        for viejo, nuevo in RENOMBRES_TABLA:
            if viejo in tablas and nuevo not in tablas:
                cx.execute(text(f"ALTER TABLE {viejo} RENAME TO {nuevo}"))
                hechos.append(f"tabla {viejo} -> {nuevo}")
            elif viejo in tablas and nuevo in tablas:
                # Las dos existen: alguien arranco con el modelo nuevo antes de
                # migrar y create_all creo la vacia. No se adivina cual conservar.
                hechos.append(
                    f"ATENCION: existen '{viejo}' y '{nuevo}' a la vez. "
                    f"Revisa cual tiene los datos antes de borrar la otra.")

        tablas = set(inspect(engine).get_table_names())
        for tabla, viejo, nuevo in RENOMBRES_COLUMNA:
            if tabla not in tablas:
                continue
            cols = {c["name"] for c in inspect(engine).get_columns(tabla)}
            if viejo in cols and nuevo not in cols:
                cx.execute(text(f"ALTER TABLE {tabla} RENAME COLUMN {viejo} TO {nuevo}"))
                hechos.append(f"columna {tabla}.{viejo} -> {nuevo}")

    for h in hechos:
        log.info("renombre: %s", h)
    return hechos


# --------------------------------------------------------------------------- #
# Candados de la bitacora (PROY-NOM-030-ASEA-2026, numeral 7.1.10)
# --------------------------------------------------------------------------- #
# La norma pide dos cosas que el codigo por si solo no puede prometer: que los
# registros "no sean alterados" (inciso a) y que la aplicacion "no permita que
# sean eliminados" (inciso d, punto 4). Los controladores ya se niegan a tocar
# un reporte cerrado, pero eso vale solo para quien pase por ellos: un script,
# un importador o un arreglo a mano en la consola pasan de largo.
#
# Estos disparadores ponen el candado EN LA BASE. Cualquier UPDATE o DELETE que
# los viole se aborta con el motivo, venga de donde venga. Es el mismo criterio
# que los indices unicos de arriba: la validacion da el mensaje, el candado
# hace que el defecto sea imposible.
#
# Solo SQLite, que es lo que corre en produccion (/datos/bajagas.db). En
# PostgreSQL la sintaxis de disparadores es otra; si algun dia se migra, se
# avisa en el arranque para que no se pierdan en silencio.
_MSG_NO_SE_ALTERA = ("NOM-030 7.1.10: un registro de bitacora no se altera; "
                     "la correccion es un registro nuevo")
_MSG_NO_SE_BORRA = "NOM-030 7.1.10: los registros de bitacora no se eliminan"
_MSG_CERRADO = ("NOM-030 7.1.10: el formato ya esta cerrado; la correccion es "
                "un registro nuevo en la bitacora")


# Los renglones no saben si su formato esta cerrado: se le pregunta al padre.
# OLD para editar o borrar un renglon que ya existe; NEW para uno que se quiere
# AGREGAR (una firma nueva en un formato ya cerrado cambiaria la hoja impresa
# sin tocar ningun renglon existente).
_DE_REPORTE_CERRADO = ("(SELECT estado FROM reporte_mantenimiento "
                       "WHERE id = OLD.reporte_id) = 'cerrado'")
_A_REPORTE_CERRADO = ("(SELECT estado FROM reporte_mantenimiento "
                      "WHERE id = NEW.reporte_id) = 'cerrado'")


CANDADOS = [
    # El libro de mantenimiento: ni se edita ni se borra, nunca.
    ("bitacora_mant_no_se_altera", "UPDATE", "bitacora_mantenimiento", None, _MSG_NO_SE_ALTERA),
    ("bitacora_mant_no_se_borra", "DELETE", "bitacora_mantenimiento", None, _MSG_NO_SE_BORRA),
    # La bitacora de auditoria (RF-GEN-04) siempre se dijo inmutable; ahora lo es.
    ("auditoria_no_se_altera", "UPDATE", "bitacora_auditoria", None, _MSG_NO_SE_ALTERA),
    ("auditoria_no_se_borra", "DELETE", "bitacora_auditoria", None, _MSG_NO_SE_BORRA),
    # El formato y sus renglones: no se borran, y cerrados no se editan.
    ("reporte_no_se_borra", "DELETE", "reporte_mantenimiento", None, _MSG_NO_SE_BORRA),
    ("reporte_cerrado_no_se_altera", "UPDATE", "reporte_mantenimiento",
     "OLD.estado = 'cerrado'", _MSG_CERRADO),
    ("actividad_no_se_borra", "DELETE", "actividad_reporte", None, _MSG_NO_SE_BORRA),
    ("actividad_cerrada_no_se_altera", "UPDATE", "actividad_reporte",
     _DE_REPORTE_CERRADO, _MSG_CERRADO),
    ("firma_no_se_borra", "DELETE", "firma_reporte", None, _MSG_NO_SE_BORRA),
    ("firma_cerrada_no_se_altera", "UPDATE", "firma_reporte",
     _DE_REPORTE_CERRADO, _MSG_CERRADO),
    ("punto_no_se_borra", "DELETE", "punto_revision", None, _MSG_NO_SE_BORRA),
    ("punto_cerrado_no_se_altera", "UPDATE", "punto_revision",
     _DE_REPORTE_CERRADO, _MSG_CERRADO),
    ("actividad_cerrada_no_se_agrega", "INSERT", "actividad_reporte",
     _A_REPORTE_CERRADO, _MSG_CERRADO),
    ("firma_cerrada_no_se_agrega", "INSERT", "firma_reporte",
     _A_REPORTE_CERRADO, _MSG_CERRADO),
    ("punto_cerrado_no_se_agrega", "INSERT", "punto_revision",
     _A_REPORTE_CERRADO, _MSG_CERRADO),
]


def asegurar_candados_bitacora(engine) -> list[str]:
    """Crea los disparadores que falten. Idempotente (IF NOT EXISTS)."""
    if engine.dialect.name != "sqlite":
        aviso = (f"Los candados de la bitacora NOM-030 solo existen para SQLite; esta base "
                 f"es {engine.dialect.name}. Los registros quedan protegidos solo por el codigo.")
        log.warning(aviso)
        return [aviso]
    # Cada candado en su propia transaccion y su propio try, como los indices:
    # uno que falle se reporta fuerte y los demas se crean igual. Nunca tumba
    # el arranque -- una API caida no protege ningun registro.
    hechos = []
    tablas = set(inspect(engine).get_table_names())
    for nombre, evento, tabla, cuando, mensaje in CANDADOS:
        if tabla not in tablas:
            continue
        condicion = f" WHEN {cuando}" if cuando else ""
        try:
            with engine.begin() as cx:
                existe = cx.execute(text(
                    "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = :n"),
                    {"n": nombre}).first()
                if existe:
                    continue
                cx.execute(text(
                    f"CREATE TRIGGER IF NOT EXISTS {nombre} BEFORE {evento} ON {tabla}"
                    f"{condicion} BEGIN SELECT RAISE(ABORT, '{mensaje}'); END"))
            hechos.append(f"candado {nombre}")
        except Exception as e:  # pragma: no cover
            aviso = f"ATENCION: no se pudo crear el candado {nombre}: {e}"
            log.error(aviso)
            hechos.append(aviso)
    for h in hechos:
        log.info(h)
    return hechos
