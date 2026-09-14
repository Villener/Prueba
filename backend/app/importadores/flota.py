"""Carga el catalogo maestro de la flota: UNIDADES BAJA GAS.xlsx.

Es el unico de los siete archivos que liga el numero de unidad con su PLACA y
con su VIN. Ningun otro los tiene, asi que no hay segunda opinion posible: si
esto no entra, el reporte de mantenimiento seguira imprimiendo las placas en
blanco --que es justo lo que se veia hoy: 4 placas en 383 unidades, y las cuatro
inventadas por la semilla de demo--.

CORRE DESPUES DE limpieza.py. Si no, las cuatro parejas duplicadas de la base
reciben cada una su mitad del catalogo y quedan seis escrituras del mismo
camion.

QUE NO HACE, A PROPOSITO:

  No borra unidades que el catalogo no traiga. El taller trabaja con 271
  vehiculos que Logistica nunca dio de alta --remolques, retros, apodos como
  'MALIBU'-- y son el 12% del historial. Se quedan donde estan.

  No pisa una placa que ya este puesta en otra unidad. Hay 5 grupos de placa
  repetida en el propio catalogo; el grave es BG4791A, que aparece en BG433P
  (activa) y en BG457P (inactiva). Meter esa placa en las dos revuelve el
  historial de una unidad muerta con el de una viva. Se pone en la primera y la
  segunda se reporta para que Logistica lo resuelva.

Se ejecuta con:  python -m app.importadores.flota
"""
import logging
import os

import openpyxl
from sqlalchemy.orm import Session

from .. import models as m
from . import normaliza as n

log = logging.getLogger(__name__)

ARCHIVO = "UNIDADES BAJA GAS.xlsx"
HOJA = "Catalogo Unidades"

# backend/app/importadores/flota.py -> ../../../datos
CARPETA_DATOS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))), "datos")

# El canal comercial del catalogo -> el tipo de unidad del sistema, que es lo
# que decide en que cajon del taller cabe. Se compara por SUBCADENA y en
# mayusculas sin acentos porque el catalogo escribe el mismo canal de hasta
# cuatro formas: 'Utilitario', 'Utilitario ', 'Utilitaria', 'Utilitaria '.
CANAL_A_TIPO = [
    ("MONTACARG", "montacargas"),
    ("ESTACIONARIO", "pipa"),      # las pipas de gas son el canal estacionario
    ("REPARTO", "reparto"),
    ("UTILITARI", "utilitario"),
]
TIPO_POR_OMISION = "utilitario"

# La sucursal del catalogo -> la clave de planta del sistema.
SUCURSAL_A_PLANTA = {
    "ALAMOS": "ALAMOS", "TECATE": "TECATE", "ROSARITO": "ROSARITO",
    "CARRANZA": "CARRANZA", "VALLEREDONDO": "VALLEREDONDO",
    "GUAYCURA": "GUAYCURA", "LIBERTAD": "LIBERTAD",
}
# Sucursales sin taller propio: a donde va la unidad si se vara.
TALLER_SUSTITUTO = {"LIBERTAD": "ALAMOS"}


def _tipo_de(canal: str) -> str:
    c = n.clave_unidad(canal) or n.texto(canal).upper()
    for aguja, tipo in CANAL_A_TIPO:
        if aguja in c:
            return tipo
    return TIPO_POR_OMISION


def _leer_catalogo(carpeta: str) -> dict:
    """Lee la hoja y devuelve {clave_normalizada: fila}. La ultima gana."""
    ruta = os.path.join(carpeta, ARCHIVO)
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    ws = wb[HOJA]
    filas = ws.iter_rows(values_only=True)

    cabecera = [n.texto(c).upper() for c in next(filas)]
    # Se mapea por NOMBRE de columna, nunca por posicion. El area ya movio
    # columnas dos veces en ocho dias; un importador posicional se traeria una
    # columna por otra sin dar un solo error.
    col = {nombre: i for i, nombre in enumerate(cabecera)}
    faltan = [c for c in ("UNIDAD", "MATRICULA", "ESTATUS", "SUCURSAL") if c not in col]
    if faltan:
        raise RuntimeError(
            f"A {ARCHIVO} le faltan columnas: {', '.join(faltan)}. "
            "Alguien las renombro o las borro; revisa el archivo antes de importar.")

    def val(fila, nombre):
        i = col.get(nombre)
        return fila[i] if i is not None and i < len(fila) else None

    catalogo, descartadas = {}, 0
    for fila in filas:
        if not any(v is not None for v in fila):
            continue
        clave = n.clave_unidad(val(fila, "UNIDAD"))
        if not clave:
            descartadas += 1
            continue
        catalogo[clave] = {
            "clave": clave,
            "texto": n.texto(val(fila, "UNIDAD")),
            "placa": n.placa(val(fila, "MATRICULA")),
            "vin": n.vin(val(fila, "S_FABRICANTE")),
            "modelo": n.texto(val(fila, "MODELO")),
            "anio": n.anio(val(fila, "AÑO")) or n.anio(val(fila, "MODELO")),
            "canal": n.texto(val(fila, "CANAL_UNIDAD")),
            "sucursal": n.texto(val(fila, "SUCURSAL")).upper().replace(" ", ""),
            "activa": n.texto(val(fila, "ESTATUS")).upper().startswith("ACTIV"),
        }
    wb.close()
    return catalogo, descartadas


def importar(db: Session, carpeta: str = CARPETA_DATOS) -> dict:
    catalogo, descartadas = _leer_catalogo(carpeta)

    tipos = {t.nombre: t.id for t in db.query(m.TipoUnidad).all()}
    plantas = {p.clave: p.id for p in db.query(m.Planta).all()}
    talleres = {t.planta_id: t.id for t in db.query(m.Taller).all()}

    def taller_de(sucursal: str):
        clave = SUCURSAL_A_PLANTA.get(sucursal)
        if clave is None:
            return None
        clave = TALLER_SUSTITUTO.get(clave, clave)
        return talleres.get(plantas.get(clave))

    # Placas y VIN que YA estan tomados, para no chocar contra el indice unico.
    placas_usadas = {u.placas: u.num_economico
                     for u in db.query(m.Unidad).filter(m.Unidad.placas.isnot(None))}
    vins_usados = {u.vin: u.num_economico
                   for u in db.query(m.Unidad).filter(m.Unidad.vin.isnot(None))}

    existentes = db.query(m.Unidad).all()
    por_clave = {}
    for u in existentes:
        c = n.clave_unidad(u.num_economico)
        if c:
            por_clave.setdefault(c, u)
    nombres_usados = {u.num_economico for u in existentes}

    r = {"catalogo": len(catalogo), "descartadas_del_excel": descartadas,
         "actualizadas": 0, "creadas": 0, "placas_puestas": 0, "vin_puestos": 0,
         "renombradas": 0, "sin_taller": 0, "solo_en_taller": 0,
         "placas_en_conflicto": [], "vin_en_conflicto": []}

    def aplicar(u: m.Unidad, fila: dict, es_nueva: bool):
        if fila["placa"]:
            dueno = placas_usadas.get(fila["placa"])
            if dueno is None:
                u.placas = fila["placa"]
                placas_usadas[fila["placa"]] = u.num_economico
                r["placas_puestas"] += 1
            elif dueno != u.num_economico:
                r["placas_en_conflicto"].append(
                    f"{fila['placa']} la traen {dueno} y {fila['texto']}")
        if fila["vin"]:
            dueno = vins_usados.get(fila["vin"])
            if dueno is None:
                u.vin = fila["vin"]
                vins_usados[fila["vin"]] = u.num_economico
                r["vin_puestos"] += 1
            elif dueno != u.num_economico:
                r["vin_en_conflicto"].append(
                    f"{fila['vin']} lo traen {dueno} y {fila['texto']}")

        # El modelo del catalogo revuelve marca, modelo, capacidad y anio en una
        # sola cadena ('CNJ 4T 2019'). Se guarda tal cual en `modelo` y no se
        # intenta partir: 255 escrituras distintas para unos 30 modelos reales,
        # y adivinar donde acaba la marca inventa datos que nadie escribio.
        if fila["modelo"] and not u.modelo:
            u.modelo = fila["modelo"][:60]
        if fila["anio"] and not u.anio:
            u.anio = fila["anio"]

        taller = taller_de(fila["sucursal"])
        if taller:
            u.taller_asignado_id = taller
        elif es_nueva:
            r["sin_taller"] += 1

        # El estatus del catalogo manda sobre `activo`, salvo en las unidades de
        # demo que la limpieza ya apago a proposito.
        if u.num_economico not in ("U-101", "U-102", "U-201", "U-301"):
            u.activo = fila["activa"]

    for clave, fila in catalogo.items():
        u, encontrada = n.resolver_unidad(clave, por_clave)
        if u is not None:
            # Se unifica la escritura con la del catalogo, que es contra quien
            # van a cruzar los demas archivos. Solo si el nombre esta libre.
            if u.num_economico != fila["texto"] and fila["texto"] not in nombres_usados:
                nombres_usados.discard(u.num_economico)
                nombres_usados.add(fila["texto"])
                u.num_economico = fila["texto"]
                r["renombradas"] += 1
            aplicar(u, fila, es_nueva=False)
            r["actualizadas"] += 1
        else:
            nombre = fila["texto"]
            if nombre in nombres_usados:
                continue  # otra fila del catalogo ya ocupo ese nombre
            u = m.Unidad(
                num_economico=nombre,
                tipo_unidad_id=tipos.get(_tipo_de(fila["canal"]), tipos[TIPO_POR_OMISION]),
                estado="disponible",
            )
            db.add(u)
            nombres_usados.add(nombre)
            por_clave[clave] = u
            aplicar(u, fila, es_nueva=True)
            r["creadas"] += 1

    # Las que el taller usa y Logistica nunca dio de alta. No se tocan, pero se
    # cuentan: es el 12% del historial y alguien tiene que darlas de alta.
    for clave, u in por_clave.items():
        if isinstance(u, m.Unidad) and n.resolver_unidad(clave, catalogo)[0] is None:
            r["solo_en_taller"] += 1

    db.commit()
    return r


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from ..core.database import SessionLocal

    db = SessionLocal()
    try:
        antes = db.query(m.Unidad).count()
        r = importar(db)
        despues = db.query(m.Unidad).count()
        print(f"catalogo leido        : {r['catalogo']} unidades "
              f"({r['descartadas_del_excel']} filas descartadas por no ser unidad)")
        print(f"unidades en la base   : {antes} -> {despues}")
        print(f"  actualizadas        : {r['actualizadas']}")
        print(f"  creadas             : {r['creadas']}")
        print(f"  renombradas         : {r['renombradas']} (se unifico la escritura)")
        print(f"placas puestas        : {r['placas_puestas']}")
        print(f"VIN puestos           : {r['vin_puestos']}")
        print(f"sin taller asignable  : {r['sin_taller']}")
        print(f"solo viven en taller  : {r['solo_en_taller']} (Logistica no las dio de alta)")
        for titulo, casos in (("PLACAS EN CONFLICTO", r["placas_en_conflicto"]),
                              ("VIN EN CONFLICTO", r["vin_en_conflicto"])):
            if casos:
                print(f"\n{titulo} ({len(casos)}):")
                for c in casos:
                    print(f"  - {c}")
    finally:
        db.close()
