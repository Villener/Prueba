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
