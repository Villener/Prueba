"""El padron de unidades activas: el control de GPS de Logistica (CONTROL GPS.xlsx).

POR QUE EXISTE. Hasta el 2026-10-09 el padron era UNIDADES BAJA GAS.xlsx (1,277
filas, ~714 activas). Logistica lo actualizo en su control del proyecto de GPS
y ahi la flota que de verdad opera es mas chica: 429 unidades de reparto,
estacionario, franquicia, expendio, modulos, operaciones y unas pocas de taller,
area comercial y tesoreria. Ademas trae lo que el otro no tenia: el NUMERO DE
PERMISO (CRE) de cada unidad, que pide la bitacora de la NOM-030. Martin decidio
que el sistema trabaje con este y no con el otro, y que las que no vienen aqui
se den de baja.

DE DONDE SALE CADA DATO (el libro trae siete hojas, cuatro ocultas):

  GPS LISTADO        unidad, canal, supervisor, VIN, placas, modelo. La planta
                     sale de su supervisor (hoja PORCENTAJE).
  BASE DE DATOS      la lista de cada supervisor, con el STATUS del GPS. Trae
                     las unidades que todavia esperan su GPS (PENDIENTE), que
                     no estan en GPS LISTADO, y las que Logistica marco BAJA.
  FLOTILLA (oculta)  canal, SUCURSAL y supervisor. Su canal es el que manda.

  Las tres dicen la planta y en 12 unidades no coinciden: gana la que digan
  dos de las tres, y la unidad sale en `a_revisar`.
  PORCENTAJE         la tabla de supervisores con su ZONA y su PERMISO. El
                     permiso va por canal Y planta, no solo por planta:
                     Rosarito reparto es LP/14586 y Rosarito estacionario
                     LP/14792 (sus pipas son de la planta de Alamos).

  Las otras (PENDIENTES FASE, TALLER, Hoja1) son el avance de la instalacion
  y no se leen. El "NUMERO CELULAR" de GPS LISTADO es el chip del GPS, NO el
  celular del chofer: tampoco se lee.

QUE HACE (aplicar):

  - Cada unidad del padron queda ACTIVA, con la planta de su supervisor y el
    permiso de su canal y planta. Las que no estan en la base se crean.
  - Estacionario = pipa y reparto = reparto. Los demas canales (franquicia,
    expendio, modulos...) traen de todo, asi que no tocan el tipo.
  - Las activas que NO vienen en el padron se dan de baja. Siguen en la base y
    el taller las puede seguir recibiendo; si vuelven a aparecer, se reactivan.
  - Cuando las hojas no coinciden en la planta o el canal, se dice en
    `a_revisar`.

QUE NO HACE, A PROPOSITO:

  No pisa placas ni VIN que ya estan. El control de GPS los teclea quien
  instala: hay VIN corridos un renglon (la 2311 trae el de la 2310, la 2312 el
  de la 2311...), VIN de otra unidad y placas con una letra cambiada. El
  catalogo de Logistica que ya entro es mas confiable. Solo se llenan los que
  faltan, si nadie mas los trae, y las diferencias se reportan para revisarlas.

  No renombra unidades: el GPS escribe 'BG-734' y la base 'BG734P'. Se cruzan
  con el mismo alias de la P que ya usaban los demas importadores. Las del
  taller que la base guarda con nombre ('GRUA 718') van en NOMBRES_EN_LA_BASE.

  No crea una unidad que se parece a otra que ya esta ('PLAT 900' y un '900R'
  nuevo): la manda a revisar y no da de baja a la parecida. Crearla partiria
  el historial de un mismo vehiculo en dos.

  La letra BG no se quita nunca: las unidades de solo numero son las viejas, de
  cuando el negocio era de Z Gas, y las BG las que compro despues Baja Gas &
  Oil. La 304 y la BG-304 son dos camiones distintos (ver normaliza).

Se ejecuta con:  python -m app.importadores.padron [carpeta]
"""
import collections
import datetime
import logging
import os
import re
import unicodedata

import openpyxl
from sqlalchemy.orm import Session

from .. import models as m
from . import normaliza as n

log = logging.getLogger(__name__)

ARCHIVO = "CONTROL GPS.xlsx"
HOJA_FLOTILLA = "FLOTILLA"
HOJA_GPS = "GPS LISTADO"
HOJA_BASE = "BASE DE DATOS"
HOJA_PERMISOS = "PORCENTAJE"

# backend/app/importadores/padron.py -> ../../../datos
CARPETA_DATOS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))), "datos")

# La sucursal escrita como sea -> la clave de planta del sistema.
SUCURSAL_A_PLANTA = {
    "ALAMOS": "ALAMOS", "TECATE": "TECATE", "ROSARITO": "ROSARITO",
    "CARRANZA": "CARRANZA", "VALLEREDONDO": "VALLEREDONDO", "VALLE": "VALLEREDONDO",
    "GUAYCURA": "GUAYCURA", "LIBERTAD": "LIBERTAD",
}

# El canal escrito como sea -> uno solo. 'OPERACION' y 'OPERACIONES' son lo
# mismo; 'A. COMERCIAL' y 'A- COMERCIAL' tambien.
CANALES = {
    "REPARTO": "REPARTO", "ESTACIONARIO": "ESTACIONARIO", "FRANQUICIA": "FRANQUICIA",
    "EXPENDIO": "EXPENDIO", "MODULOS": "MODULOS", "MODULO": "MODULOS",
    "OPERACION": "OPERACIONES", "OPERACIONES": "OPERACIONES",
    "ACOMERCIAL": "AREA COMERCIAL", "AREACOMERCIAL": "AREA COMERCIAL",
    "TESORERIA": "TESORERIA", "TALLER": "TALLER",
}
# Solo estos dos canales dicen que vehiculo es. Los demas traen de todo.
CANAL_A_TIPO = {"ESTACIONARIO": "pipa", "REPARTO": "reparto"}
TIPO_POR_OMISION = "utilitario"

# Unidades del taller que la base guarda con su nombre y Logistica solo con el
# numero. Sin esto, el padron crearia un '718' vacio y daria de baja la grua
# que trae su historial. La R de Logistica es la plataforma Raca (la '816R' de
# la base es la 'Plataforma Raca Pikin 1992', igual que las 'PLATAFORMA RACA').
NOMBRES_EN_LA_BASE = {
    "718": "GRUA718",
    "811R": "PLATAFORMARACA811",
    "812R": "PLATAFORMARACA812",
    "815R": "PLATAFORMARACA815",
}

# Un padron con menos que esto no es el padron: es otra hoja, un filtro que se
# quedo puesto o un archivo a medias. Aplicarlo daria de baja a casi toda la
# flota, asi que mejor no se aplica.
MINIMO_DE_UNIDADES = 150


def _plano(v) -> str:
    """Mayusculas, sin acentos y sin nada que no sea letra o numero."""
    t = unicodedata.normalize("NFKD", n.texto(v).upper())
    return "".join(c for c in t if c.isalnum())


def _persona(v) -> str:
    """Un nombre comparable: mayusculas, sin acentos, un solo espacio."""
    t = unicodedata.normalize("NFKD", n.texto(v).upper())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def canal(v) -> str | None:
    return CANALES.get(_plano(v))


def planta(v) -> str | None:
    return SUCURSAL_A_PLANTA.get(_plano(v))


def _clave(v) -> str:
    """La clave de unidad, con las erratas conocidas del control de GPS.

    'GB-304' es la BG-304. 'BGOT-04' y 'BGTO-05' son los tractocamiones que el
    taller escribe 'BGT-04' (Logistica los teclea de tres maneras).
    """
    c = n.clave_unidad(v)
    if re.fullmatch(r"GB\d+[A-Z]?", c):
        c = "BG" + c[2:]
    return re.sub(r"^BG(?:TO|OT)(?=\d)", "BGT", c)


def _corregido(texto) -> str:
    """El nombre con la errata corregida ('BGTO-05' -> 'BGT-05'), que es como lo
    escriben el taller y los demas archivos. Una unidad nueva se crea asi."""
    t = n.texto(texto).upper()
    t = re.sub(r"^GB(?=[\s\-]*\d)", "BG", t)
    t = re.sub(r"^BG[\s\-]*(?:TO|OT)(?=[\s\-]*\d)", "BGT", t)
    return t if n.clave_unidad(t) == _clave(t) else _clave(t)


def _encabezado(filas, *requeridas):
    """(indice de la fila, {nombre: columna}) del primer renglon que trae todas."""
    for i, fila in enumerate(filas[:8]):
        cols = {_plano(v): j for j, v in enumerate(fila) if v is not None}
        if all(r in cols for r in requeridas):
            return i, cols
    return None, None


def _filas(wb, hoja, max_col=20):
    # FLOTILLA trae 16 mil columnas vacias con formato: leer solo las primeras.
    return [r for r in wb[hoja].iter_rows(max_col=max_col, values_only=True)]


def _permisos(wb, avisos):
    """{(canal, planta): permiso} y {(supervisor, canal): planta} de PORCENTAJE.

    La tabla no tiene encabezado para el canal: va en la columna de la izquierda
    del permiso, escrito solo en el primer renglon de cada grupo.
    """
    filas = _filas(wb, HOJA_PERMISOS, 12)
    col_perm = fila_perm = None
    for i, fila in enumerate(filas):
        for j, v in enumerate(fila):
            if _plano(v) == "PERMISO":
                fila_perm, col_perm = i, j
                break
        if col_perm is not None:
            break
    h, cols = _encabezado(filas[max(0, (fila_perm or 0) - 3):], "ZONA", "SUPERVISOR")
    if col_perm is None or cols is None:
        avisos.append("La hoja PORCENTAJE no trae la tabla de permisos: no se puso ninguno.")
        return {}, {}
    c_zona, c_sup, c_canal = cols["ZONA"], cols["SUPERVISOR"], max(0, col_perm - 1)
    permisos, supervisores = {}, {}
    actual = None
    for fila in filas[fila_perm + 1:]:
        if c_canal < len(fila) and fila[c_canal] is not None:
            actual = canal(fila[c_canal]) or actual
        zona = planta(fila[c_zona]) if c_zona < len(fila) else None
        sup = _persona(fila[c_sup]) if c_sup < len(fila) else ""
        if not (zona and actual):
            continue
        perm = n.texto(fila[col_perm]).upper() if col_perm < len(fila) else ""
        if perm:
            previo = permisos.setdefault((actual, zona), perm)
            if previo != perm:
                avisos.append(f"{actual} {zona} trae dos permisos ({previo} y {perm}): "
                              "se usa el primero.")
        if sup:
            supervisores[(sup, actual)] = zona
    return permisos, supervisores


def _base_de_datos(wb, avisos):
    """Las listas de BASE DE DATOS: [(clave, texto, marcada_baja, lista)].

    Cada lista es una columna UNIDAD, con el STATUS y una nota a su derecha,
    bajo el nombre del supervisor. Una columna puede traer varias listas: cada
    una empieza en su renglon UNIDAD y acaba en el nombre del siguiente
    supervisor (lo unico de la columna que no lleva numero). `lista` las
    distingue para saber de que canal y planta son sus unidades.
    """
    if HOJA_BASE not in wb.sheetnames:
        avisos.append("El control de GPS no trae la hoja BASE DE DATOS: no se leyeron las "
                      "unidades pendientes de GPS ni las marcadas BAJA.")
        return []
    filas = _filas(wb, HOJA_BASE, 60)

    def celda(i, j):
        return filas[i][j] if j < len(filas[i]) else None

    ancho = max((len(f) for f in filas), default=0)
    columnas = sorted({j for i in range(len(filas)) for j in range(ancho)
                       if _plano(celda(i, j)) == "UNIDAD"})
    salida = []
    for j in columnas:
        lista = None
        for i in range(len(filas)):
            v = celda(i, j)
            if _plano(v) == "UNIDAD":
                lista = (j, i)
                continue
            if lista is None or v is None:
                continue
            texto = n.texto(v)
            if not any(ch.isdigit() for ch in texto):
                lista = None
                continue
            # La nota va dos columnas a la derecha, salvo que ahi empiece la
            # lista de al lado (dos supervisores traen dos listas pegadas).
            notas = [celda(i, j + 1)] + ([] if j + 2 in columnas else [celda(i, j + 2)])
            c = _clave(v)
            if c:
                salida.append((c, texto, any(_plano(x) == "BAJA" for x in notas), lista))
    return salida


def leer(ruta: str) -> dict:
    """El padron, ya cruzado entre hojas. No toca la base."""
    wb = openpyxl.load_workbook(ruta, data_only=True)
    faltan = [h for h in (HOJA_FLOTILLA, HOJA_GPS, HOJA_PERMISOS) if h not in wb.sheetnames]
    if faltan:
        raise RuntimeError(
            f"Al control de GPS le faltan las hojas {', '.join(faltan)}. Revisa que sea "
            "el archivo correcto (trae FLOTILLA, GPS LISTADO y PORCENTAJE).")
    avisos = []
    permisos, supervisores = _permisos(wb, avisos)

    unidades = {}

    def unidad(clave, texto):
        return unidades.setdefault(clave, {
            "clave": clave, "texto": texto, "canal": None, "planta": None,
            "supervisor": None, "placa": "", "vin": "", "modelo": "", "hojas": [],
            "a_revisar": [],
            # Lo que dice cada hoja (f = FLOTILLA, g = GPS LISTADO), antes de decidir.
            "f_canal": None, "f_planta": None, "g_canal": None, "g_planta": None,
            "g_sup": ""})

    filas = _filas(wb, HOJA_FLOTILLA, 8)
    h, cols = _encabezado(filas, "UNIDAD", "SUCURSAL", "CANAL")
    if h is None:
        raise RuntimeError("La hoja FLOTILLA no trae las columnas UNIDAD, SUCURSAL y CANAL.")
    c_sup = cols.get("SUPERVISOR", cols.get("SUPERVSOR"))
    for fila in filas[h + 1:]:
        c = _clave(fila[cols["UNIDAD"]])
        if not c:
            continue
        u = unidad(c, n.texto(fila[cols["UNIDAD"]]))
        u["f_canal"] = canal(fila[cols["CANAL"]])
        u["f_planta"] = planta(fila[cols["SUCURSAL"]])
        u["supervisor"] = _persona(fila[c_sup]) if c_sup is not None else None
        u["hojas"].append(HOJA_FLOTILLA)

    filas = _filas(wb, HOJA_GPS, 16)
    h, cols = _encabezado(filas, "UNIDAD", "VIN", "CANAL", "SUPERVISOR")
    if h is None:
        raise RuntimeError("La hoja GPS LISTADO no trae las columnas UNIDAD, VIN, CANAL "
                           "y SUPERVISOR.")

    def celda(fila, nombre):
        j = cols.get(nombre)
        return fila[j] if j is not None and j < len(fila) else None

    for fila in filas[h + 1:]:
        c = _clave(celda(fila, "UNIDAD"))
        if not c:
            continue
        u = unidad(c, n.texto(celda(fila, "UNIDAD")))
        u["hojas"].append(HOJA_GPS)
        u["placa"] = n.placa(celda(fila, "PLACAS")).replace("-", "")
        u["vin"] = n.vin(celda(fila, "VIN"))
        u["modelo"] = n.texto(celda(fila, "MODELO"))
        sup = _persona(celda(fila, "SUPERVISOR"))
        u["supervisor"] = sup or u["supervisor"]
        # A veces el canal trae la PLANTA ('CARRANZA', 'tecate'): sirve de planta.
        crudo = celda(fila, "CANAL")
        u["g_canal"] = canal(crudo)
        u["g_planta"] = planta(crudo)
        u["g_sup"] = sup

    # La P de las pipas es solo una forma de escribirla: 'BG-728P' en FLOTILLA y
    # 'BG-728' en GPS LISTADO son la misma unidad. Se juntan con el nombre que
    # trae FLOTILLA.
    for c in [c for c in unidades if c.endswith("P") and c[:-1] in unidades]:
        a, b = unidades[c[:-1]], unidades.pop(c)
        if HOJA_FLOTILLA in b["hojas"] and HOJA_FLOTILLA not in a["hojas"]:
            a["texto"] = b["texto"]
        for k in ("supervisor", "placa", "vin", "modelo", "f_canal", "f_planta",
                  "g_canal", "g_planta", "g_sup"):
            a[k] = a[k] or b[k]
        a["hojas"] += b["hojas"]

    # El canal: manda FLOTILLA. GPS LISTADO trae la BG-813 (un camion de reparto
    # como sus hermanas) como estacionario, y el canal decide si es pipa.
    for u in unidades.values():
        u["canal"] = u["f_canal"] or u["g_canal"]
        u["g_planta"] = (u["g_planta"] or supervisores.get((u["g_sup"], u["canal"]))
                         or supervisores.get((u["g_sup"], u["g_canal"])))
        u["planta"] = u["g_planta"] or u["f_planta"]
        if u["f_canal"] and u["g_canal"] and u["f_canal"] != u["g_canal"]:
            u["a_revisar"].append(f"canal {u['f_canal']} en FLOTILLA y {u['g_canal']} en "
                                  f"GPS LISTADO; se tomo {u['f_canal']}")

    def buscar(c):
        for k in (c, c + "P", c[:-1] if c.endswith("P") else None):
            if k and k in unidades:
                return k
        return None

    # BASE DE DATOS. Las marcadas BAJA salen del padron aunque FLOTILLA las
    # siga trayendo.
    listas = _base_de_datos(wb, avisos)
    marcadas = set()
    for c, texto, baja, _lista in listas:
        if baja:
            marcadas.add(c)
            k = buscar(c)
            if k:
                unidades.pop(k)
            avisos.append(f"{texto} viene marcada BAJA en BASE DE DATOS: no entra al padron.")

    # Cada lista es de un canal y una planta: los que traen la mayoria de sus
    # unidades. Con eso se ubican las que solo vienen ahi (esperan su GPS).
    votos = collections.defaultdict(collections.Counter)
    for c, _texto, _baja, lista in listas:
        k = buscar(c)
        if k:
            votos[lista][(unidades[k]["canal"], unidades[k]["planta"])] += 1
    for c, texto, _baja, lista in listas:
        if c in marcadas or not votos[lista]:
            continue
        k = buscar(c)
        canal_lista, planta_lista = votos[lista].most_common(1)[0][0]
        if k is None:
            k = c
            u = unidad(c, texto)
            u["canal"], u["planta"] = canal_lista, planta_lista
        u = unidades[k]
        if HOJA_BASE not in u["hojas"]:
            u["hojas"].append(HOJA_BASE)
            u["b_planta"] = planta_lista

    # La planta, cuando las hojas no coinciden: la que digan dos de las tres.
    # FLOTILLA esta vieja en 8 (2310-2313, BG-362, BG-363, BG-717, BG-733) y el
    # supervisor de GPS LISTADO en 3 (BG-303, BG-410, BG-700). Si solo hay dos y
    # no coinciden, manda GPS LISTADO, que es la que Logistica tiene al dia.
    for u in unidades.values():
        dicen = [(h, p) for h, p in ((HOJA_GPS, u["g_planta"]), (HOJA_FLOTILLA, u["f_planta"]),
                                     (HOJA_BASE, u.get("b_planta"))) if p]
        if len({p for _h, p in dicen}) < 2:
            continue
        cuenta = collections.Counter(p for _h, p in dicen)
        u["planta"] = max((p for _h, p in dicen), key=lambda p: cuenta[p])
        u["a_revisar"].append("planta " + ", ".join(f"{p} en {h}" for h, p in dicen)
                              + f"; se tomo {u['planta']}")

    # Sin canal (la celda traia la planta) el permiso solo se sabe si en esa
    # planta todos los canales tienen el mismo: Tecate si, Rosarito no.
    por_planta = {}
    for (_canal, pl), perm in permisos.items():
        por_planta.setdefault(pl, set()).add(perm)
    for u in unidades.values():
        u["permiso"] = permisos.get((u["canal"], u["planta"]))
        if not u["permiso"] and not u["canal"] and len(por_planta.get(u["planta"], ())) == 1:
            u["permiso"] = next(iter(por_planta[u["planta"]]))
    wb.close()
    return {"unidades": unidades, "permisos": permisos, "avisos": avisos}


def _asentar_permiso(db, u, antes, despues):
    """El cambio de permiso va al libro de la NOM-030 si la unidad ya tiene uno."""
    from ..modules.bitacora import asientos_reporte as bit
    tiene_libro = (db.query(m.AsientoBitacora.id)
                   .filter(m.AsientoBitacora.unidad_id == u.id).first())
    if tiene_libro:
        bit.asentar_identificacion(db, u, {"permiso_hidrocarburos": antes},
                                   {"permiso_hidrocarburos": despues}, None,
                                   "padrón de Logística")


def _parecidas(clave, existentes, excluidas):
    """Las unidades de la base que podrian ser esta con otro nombre.

    'PLAT 900' o '900 TRACTOR' para un '900R': el mismo numero (de tres cifras
    o mas, para no confundir la '04' con cualquier cosa) junto a una palabra.
    La 'BG900' no cuenta: la BG es otra unidad, no un nombre.
    """
    numeros = re.findall(r"\d+", clave)
    if len(numeros) != 1 or len(numeros[0]) < 3:
        return []
    salida = []
    for u in existentes:
        if u.id in excluidas:
            continue
        partes = re.findall(r"[A-Z]+|\d+", n.texto(u.num_economico).upper())
        if numeros[0] in partes and any(len(p) >= 3 and p.isalpha() for p in partes):
            salida.append(u)
    return salida


def aplicar(db: Session, padron: dict, hoy: datetime.date | None = None) -> dict:
    """Pone la base al dia con el padron. Idempotente: la segunda vez no cambia nada."""
    unidades = padron["unidades"]
    if len(unidades) < MINIMO_DE_UNIDADES:
        raise RuntimeError(
            f"El padron trae solo {len(unidades)} unidades (se esperan cientos). No se "
            "aplico para no dar de baja la flota: revisa que sea el archivo completo.")
    hoy = hoy or datetime.date.today()
    tipos = {t.nombre: t for t in db.query(m.TipoUnidad).all()}
    talleres = {p.clave: p.taller.id for p in db.query(m.Planta).all() if p.taller}

    existentes = db.query(m.Unidad).all()
    # Con la misma clave que el padron, erratas incluidas: si no, una unidad
    # creada como 'BGTO-07' no se reconoce al dia siguiente y se crea otra vez.
    por_clave = {}
    for u in existentes:
        c = _clave(u.num_economico)
        if c:
            por_clave.setdefault(c, u)
    placas = {u.placas: u.id for u in existentes if u.placas}
    vins = {u.vin: u.id for u in existentes if u.vin}

    r = {"padron": len(unidades), "encontradas": 0, "creadas": [], "activadas": [],
         "dadas_de_baja": [], "planta_cambiada": 0, "tipo_corregido": 0,
         "permiso_puesto": 0, "placas_puestas": 0, "vin_puestos": 0,
         "sin_planta": [], "sin_permiso": [], "a_revisar": [],
         "avisos": list(padron.get("avisos", []))}

    cruce = {}
    for c in unidades:
        u, _ = n.resolver_unidad(c, por_clave)
        if u is None and c in NOMBRES_EN_LA_BASE:
            u, _ = n.resolver_unidad(NOMBRES_EN_LA_BASE[c], por_clave)
        cruce[c] = u
    vistas = {u.id for u in cruce.values() if u is not None}

    # Las que no cruzan pero se parecen a una que ya esta: no se crean, y la
    # parecida no se da de baja, hasta que alguien diga si son la misma.
    for c in [c for c, u in cruce.items() if u is None]:
        parecidas = _parecidas(c, existentes, vistas)
        if parecidas:
            del cruce[c]
            vistas.update(u.id for u in parecidas)
            r["a_revisar"].append(
                f"{unidades[c]['texto']}: no esta en la base y se parece a "
                f"{', '.join(u.num_economico for u in parecidas)}; no se creo ni se dio "
                "de baja ninguna")

    for c, u in sorted(cruce.items()):
        fila = unidades[c]
        if u is None:
            tipo = tipos.get(CANAL_A_TIPO.get(fila["canal"], TIPO_POR_OMISION)) \
                or tipos.get(TIPO_POR_OMISION)
            u = m.Unidad(num_economico=_corregido(fila["texto"])[:20], estado="disponible",
                         tipo_unidad_id=tipo.id if tipo else None, origen="padron",
                         activo=True, fecha_alta=hoy)
            db.add(u)
            db.flush()
            por_clave[c] = u
            vistas.add(u.id)
            r["creadas"].append(u.num_economico)
        else:
            r["encontradas"] += 1

        if not u.activo:
            u.activo = True
            u.fecha_baja = None
            r["activadas"].append(u.num_economico)

        t = talleres.get(fila["planta"])
        if t and u.taller_asignado_id != t:
            u.taller_asignado_id = t
            r["planta_cambiada"] += 1
        elif not fila["planta"]:
            r["sin_planta"].append(fila["texto"])

        tipo = tipos.get(CANAL_A_TIPO.get(fila["canal"], ""))
        if tipo and u.tipo_unidad_id != tipo.id:
            u.tipo_unidad_id = tipo.id
            r["tipo_corregido"] += 1

        if fila["permiso"]:
            if (u.permiso_hidrocarburos or "") != fila["permiso"]:
                antes = u.permiso_hidrocarburos
                u.permiso_hidrocarburos = fila["permiso"]
                _asentar_permiso(db, u, antes, fila["permiso"])
                r["permiso_puesto"] += 1
        elif fila["canal"] not in ("TALLER", "AREA COMERCIAL", "TESORERIA"):
            r["sin_permiso"].append(fila["texto"])

        r["a_revisar"] += [f"{u.num_economico}: {x}" for x in fila.get("a_revisar", ())]

        # Placas y VIN: solo los que faltan, y solo si nadie mas los trae.
        for campo, valor, usados, cuenta in (("placas", fila["placa"], placas, "placas_puestas"),
                                             ("vin", fila["vin"], vins, "vin_puestos")):
            if not valor:
                continue
            actual = getattr(u, campo)
            if actual == valor:
                continue
            dueno = usados.get(valor)
            if not actual and dueno in (None, u.id):
                setattr(u, campo, valor)
                usados[valor] = u.id
                r[cuenta] += 1
            else:
                r["a_revisar"].append(f"{u.num_economico}: {campo} {actual or '(vacio)'} "
                                      f"en la base, {valor} en el GPS")
        if fila["modelo"] and not u.modelo:
            u.modelo = fila["modelo"][:60]

    # Las activas que el padron ya no trae: baja. Siguen en la base (historial,
    # requisiciones, el libro de la NOM-030) y el taller las puede recibir.
    for u in existentes:
        if u.activo and u.id not in vistas:
            u.activo = False
            u.fecha_baja = u.fecha_baja or hoy
            r["dadas_de_baja"].append(u.num_economico)

    db.commit()
    # Los conteos arriba (son los que ensenan la consola y la pantalla de
    # Datos) y las listas aparte, en `detalle`, para quien quiera revisarlas.
    listas = ("creadas", "activadas", "dadas_de_baja", "sin_planta", "sin_permiso",
              "a_revisar")
    r["detalle"] = {k: r[k] for k in listas}
    r.update({k: len(r["detalle"][k]) for k in listas})
    return r


def importar(db: Session, carpeta: str = CARPETA_DATOS) -> dict:
    return aplicar(db, leer(os.path.join(carpeta, ARCHIVO)))


if __name__ == "__main__":  # pragma: no cover
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from ..core.database import SessionLocal
    db = SessionLocal()
    try:
        res = importar(db, sys.argv[1] if len(sys.argv) > 1 else CARPETA_DATOS)
        for k, v in res.items():
            print(f"{k:16} {len(v) if isinstance(v, list) else v}")
    finally:
        db.close()
