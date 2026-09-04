"""Carga los datos reales que entrego Baja Gas, para probar con volumen de verdad.

Todo sale de la carpeta `datos/` del repositorio, no de Downloads: asi el
proyecto se puede clonar y levantar en otra maquina sin pedirle archivos a
nadie. Se puede apuntar a otra carpeta con la variable DATOS_REALES.

Fuentes:
  INFO CHOFERES 2026 ACTUAL.xlsx  -> sucursales, supervisores, choferes, unidades
                                     asignadas y personal de taller
  REQUIS 2026 *.xlsx              -> las tres primeras hojas del libro que usa
                                     el capturista todos los dias:
                                       MATERIALES  refacciones CON su codigo de
                                                   SAP, existencia y costo
                                       UNIDAD      la flota con equipo SAP, VIN,
                                                   ano, CECO, CEGE y ubicacion
                                       EMPLEADO    codigo -> nombre
  CODIGOS TALLER.xlsx             -> respaldo del codigo de SAP (ya casi no hace
                                     falta: MATERIALES lo trae en la misma fila)

POR QUE EL LIBRO DE REQUISICIONES Y NO LOS CSV. `partes.csv` y `vehiculos.csv`
eran exportaciones sueltas que envejecian por su cuenta. El libro REQUIS es la
fuente que el capturista consulta a diario, asi que el catalogo del sistema y el
suyo no pueden discrepar -- y si discrepan, se nota el mismo dia.

Los correos y contrasenas son GENERADOS: los empleados reales no tienen cuenta
todavia. Se usa el numero de empleado como identidad para que sea reproducible.

Se ejecuta con:  python -m app.importador
"""
import hashlib
import os
import re
import unicodedata
from datetime import date, datetime, timedelta

import openpyxl

from sqlalchemy.orm import Session

from . import models as m
from .core.security import hash_password

PASSWORD_PRUEBA = "bajagas2026"

# backend/app/importador.py -> ../../datos
CARPETA_DATOS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "datos")

# La sucursal del Excel -> la clave de planta del catalogo (app/seed.py).
SUCURSAL_A_PLANTA = {
    "ALAMOS": "ALAMOS", "TECATE": "TECATE", "ROSARITO": "ROSARITO",
    "CARRANZA": "CARRANZA", "VALLEREDONDO": "VALLEREDONDO",
    "GUAYCURA": "GUAYCURA", "LIBERTAD": "LIBERTAD",
}
# Sucursales sin taller propio: a donde va su unidad si se vara.
TALLER_SUSTITUTO = {"LIBERTAD": "ALAMOS"}

# El puesto del Excel -> la especialidad del modelo.
PUESTO_A_ESPECIALIDAD = [
    ("CARROCER", "carrocero"), ("SOLDADOR", "carrocero"),
    ("ELECTRIC", "electricista"), ("LLANT", "llantero"),
    ("GRUA", "montacarguista"), ("MECANIC", "mecanico"),
]


def _norm(s) -> str:
    """Mayusculas, sin acentos y sin espacios de mas. Para comparar sucursales."""
    if s is None:
        return ""
    t = unicodedata.normalize("NFKD", str(s))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", "", t).strip().upper()


def _limpiar_texto(s: str) -> str:
    """Las partes vienen con comillas rotas del export: '\"\"\" TAPON 4\"\"\"\"'."""
    t = str(s or "").replace("_x000D_", " ").replace("_x000A_", " ")
    t = re.sub(r'"+', '"', t).strip().strip('"').strip()
    return re.sub(r"\s+", " ", t)


# Codigo pegado al principio del nombre, sin separador, como viene del
# proveedor chino:  "1001.0105Shaft, idle gear"  /  "S00153-SHA01011REAR BUSHING"
# El grupo numerico NO admite letras: si las admite se come el principio de la
# descripcion y guarda "1001.0105SHAFT" como si fuera el numero de parte.
_COD_PEGADO = re.compile(
    r"^([0-9]{3,5}\.[0-9]{3,7}|[A-Z]{1,3}[0-9]{3,6}\-[0-9A-Z]{3,12})")


def _codigo_pegado(nombre: str) -> str | None:
    """Rescata el numero de parte cuando viene pegado a la descripcion.

    Son ~900 refacciones Changan que no casan contra SAP porque su nombre trae
    el codigo incrustado. Rescatarlo hace que el mecanico pueda buscarlas por
    numero en vez de adivinar como se escribio la descripcion.
    """
    mm = _COD_PEGADO.match(nombre.strip().upper())
    return mm.group(1) if mm else None


REQUIS_PATRON = "REQUIS"


def _ruta_requis(carpeta: str):
    """El libro de requisiciones. El nombre trae la version, asi que se busca.

    Sustituye a `partes.csv` y a `vehiculos.csv`: es la MISMA fuente que usa el
    capturista todos los dias, asi que el catalogo del sistema y el suyo no
    pueden discrepar. Los CSV eran exportaciones sueltas que envejecian aparte.
    """
    if not os.path.isdir(carpeta):
        return None
    for n in sorted(os.listdir(carpeta)):
        if n.startswith("~$"):
            continue                      # archivo de bloqueo de Excel
        if REQUIS_PATRON in n.upper() and n.lower().endswith((".xlsx", ".xlsm")):
            return os.path.join(carpeta, n)
    return None


def _leer_materiales(carpeta: str) -> list:
    """Hoja MATERIALES: CODIGO | MATERIAL | DIS | COSTO | GA | CTA | CTA.

    Ventaja sobre `partes.csv`: el codigo de SAP viene EN LA MISMA FILA que el
    nombre. Antes habia que casarlos por texto contra CODIGOS TALLER y fallaba
    en un porcentaje real de los casos.
    """
    ruta = _ruta_requis(carpeta)
    if not ruta:
        return []
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    if "MATERIALES" not in wb.sheetnames:
        return []
    filas = []
    for i, r in enumerate(wb["MATERIALES"].iter_rows(values_only=True)):
        if i == 0 or not r or not r[1]:
            continue                      # encabezado o fila sin nombre
        codigo = str(r[0]).strip() if r[0] is not None else ""
        nombre = _limpiar_texto(r[1])
        if not nombre:
            continue
        # DIS y COSTO traen #DIV/0! y #N/A del propio Excel: se descartan en
        # vez de guardarlos como si fueran numeros.
        def _num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0
        filas.append({
            "codigo": codigo if codigo.isdigit() else "",
            "nombre": nombre,
            "existencia": int(_num(r[2])) if len(r) > 2 else 0,
            "costo": _num(r[3]) if len(r) > 3 else 0,
            "familia": str(r[5]).strip() if len(r) > 5 and r[5] else "",
        })
    wb.close()
    return filas


def _leer_unidades_requis(carpeta: str) -> dict:
    """Hoja UNIDAD: UNIDAD | EQUIPO | MARCA | SERIE | MOD | CECO | CEGE | UBICACION.

    Trae bastante mas que `vehiculos.csv`, que solo daba numero y descripcion:
    aqui vienen el activo de SAP, el VIN, el ano y el centro de gestion, que es
    lo que ata la requisicion a su centro de costo.
    """
    ruta = _ruta_requis(carpeta)
    if not ruta:
        return {}
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    if "UNIDAD" not in wb.sheetnames:
        return {}
    out = {}
    for i, r in enumerate(wb["UNIDAD"].iter_rows(values_only=True)):
        if i == 0 or not r or not r[0]:
            continue
        num = str(r[0]).strip()
        if not num:
            continue

        def _celda(j):
            v = r[j] if len(r) > j else None
            t = str(v).strip() if v is not None else ""
            return "" if t.startswith("#") else t     # #N/A del propio Excel

        anio = _celda(4)
        out[num] = {
            "descripcion": _limpiar_texto(_celda(2)),
            "equipo_sap": _celda(1),
            "vin": _celda(3),
            "anio": int(anio) if anio.isdigit() and 1900 < int(anio) < 2100 else None,
            "ceco": _celda(5),
            "cege": _celda(6),
            "ubicacion": _celda(7),
        }
    wb.close()
    return out


def _leer_codigos_sap(carpeta: str) -> dict:
    """`CODIGOS TALLER.xlsx` -> {nombre en mayusculas: (material, 'sap', almacen)}.

    Es el ancla que pedia contexto-del-proyecto-2 §3 para el dia que se conecte
    SAP. El casado es por NOMBRE porque es el unico campo que comparten las dos
    fuentes, y por eso es parcial: alrededor del 57% del catalogo encuentra su
    codigo. El resto se queda sin el, a la vista, en vez de inventarle uno.

    Nota: el archivo distingue dos almacenes (RF03 'ALM CHANGAN 2' y RF04 'Ref
    Americanas'), los dos en el centro GT01. Se guardan como ubicacion fisica
    dentro del almacen de Alamos y NO como talleres distintos, porque son
    anaqueles de la misma planta. Si resultan ser bodegas separadas, se
    convierten en dos filas de Taller sin tocar el resto del modelo.
    """
    ruta = os.path.join(carpeta, "CODIGOS TALLER.xlsx")
    if not os.path.exists(ruta):
        return {}
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    catalogo: dict = {}
    for i, fila in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # encabezado
        material, texto, _centro, almacen, denominacion = (list(fila) + [None] * 5)[:5]
        if not texto or not material:
            continue
        clave = _limpiar_texto(texto)[:160].rstrip().upper()
        if not clave or clave in catalogo:
            continue  # se queda el primero: el archivo repite materiales
        etiqueta = " · ".join(x for x in (str(almacen or "").strip(),
                                          str(denominacion or "").strip()) if x)
        catalogo[clave] = (str(material).strip(), "sap", etiqueta or None)
    wb.close()
    return catalogo


def _correo_base(num_empleado: str, nombre: str) -> str:
    """El correo que le TOCA a esta persona, sin resolver choques.

    Se separa de `_correo` porque sirve de identidad estable: no depende de
    como se parta el nombre ni de cuantas veces se haya corrido el importador.
    Con el se reconoce a alguien que ya esta en la base.
    """
    base = f"e{num_empleado}" if num_empleado else re.sub(r"[^a-z]", "", nombre.lower())[:12]
    return f"{base or 'sin'}@bajagas.mx"


def _correo(num_empleado: str, nombre: str, usados: set) -> str:
    """El correo definitivo, ya libre. Agrega un numero si el base esta tomado."""
    correo = _correo_base(num_empleado, nombre)
    base = correo.split("@")[0]
    n = 2
    while correo in usados:
        correo = f"{base}{n}@bajagas.mx"
        n += 1
    usados.add(correo)
    return correo


# Palabras que NO son un apellido por si solas: van pegadas al que sigue.
# Sin esto, "GARCIA DE LA CRUZ ROGELIO" se partia como apellidos "Garcia De" y
# nombre "La Cruz Rogelio", y el chofer aparecia en pantalla como
# "La Cruz Rogelio Garcia De".
PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "SAN", "SANTA", "MC", "MAC",
              "VAN", "VON", "DA", "DI", "LE"}


def _dos_apellidos_por_la_izquierda(partes):
    """'GARCIA DE LA CRUZ ROGELIO' -> (['GARCIA','DE','LA','CRUZ'], ['ROGELIO'])."""
    i, apellidos = 0, []
    for _ in range(2):
        grupo = []
        while i < len(partes) - 1 and partes[i].upper() in PARTICULAS:
            grupo.append(partes[i]); i += 1
        if i < len(partes):
            grupo.append(partes[i]); i += 1
        apellidos += grupo
        if i >= len(partes):
            break
    return apellidos, partes[i:]


def _dos_apellidos_por_la_derecha(partes):
    """'CARLOS ANTONIO CALDERON PEREZ' -> (['CALDERON','PEREZ'], ['CARLOS','ANTONIO'])."""
    j = len(partes)
    for _ in range(2):
        if j <= 1:
            break
        j -= 1                                   # el apellido propiamente dicho
        while j > 1 and partes[j - 1].upper() in PARTICULAS:
            j -= 1                               # y las particulas que lo preceden
    return partes[j:], partes[:j]


def _partir_nombre(completo: str, nombre_primero: bool = False):
    """(nombre, apellidos) a partir de como lo escribe el Excel.

    El archivo NO usa un solo orden, y suponer que si fue un error real: los
    supervisores quedaban registrados como "Gomez Francisco Fausto".

      columna CHOFER      "COTA LOPEZ BLAS MAURICIO"   -> APELLIDOS NOMBRE
      columna DESPACHADORES "SALLAS MOLINA, VICTOR"    -> APELLIDOS, NOMBRE
      columna SUPERVISOR  "CARLOS ANTONIO CALDERON PEREZ" -> NOMBRE APELLIDOS

    La coma manda sobre todo lo demas. Sin coma se parte por convencion
    mexicana: dos apellidos --paterno y materno-- y el resto es el nombre. Con
    solo dos palabras se asume un apellido.
    """
    t = re.sub(r"\s+", " ", str(completo or "").strip())
    if "," in t:
        ap, _, no = t.partition(",")
        return no.strip().title() or "-", ap.strip().title() or "-"
    partes = t.split()
    if len(partes) < 3:
        if len(partes) == 2:
            return ((partes[0].title(), partes[1].title()) if nombre_primero
                    else (partes[1].title(), partes[0].title()))
        return (t.title() or "-"), "-"

    if nombre_primero:
        ap, resto = _dos_apellidos_por_la_derecha(partes)
    else:
        ap, resto = _dos_apellidos_por_la_izquierda(partes)
    if not resto:                      # todo resulto apellido: no partir
        return (t.title() or "-"), "-"
    return " ".join(resto).title(), " ".join(ap).title()


def _hojas_flota(wb):
    return [h for h in ["REPARTO", "ESTACIONARIO", "EXPENDIOS", "MODULOS", "FRANQUICIA"]
            if h in wb.sheetnames]


def _cabecera(ws):
    """El encabezado no siempre esta en la fila 1 (en REPARTO esta en la 2)."""
    fila = next(ws.iter_rows(min_row=ws.min_row, max_row=ws.min_row))
    return {_norm(c.value).replace(".", ""): c.column - 1 for c in fila if c.value}, ws.min_row


def importar(db: Session, carpeta: str, con_partes: bool = True) -> dict:

    res = {"plantas": 0, "supervisores": 0, "choferes": 0, "unidades": 0,
           "tecnicos": 0, "piezas": 0, "existencias": 0, "requisiciones": 0,
           "renglones": 0, "avisos": []}

    # Se puede correr sobre una base que ya tiene datos: crea lo que falte y
    # salta lo que ya existe. No hace falta borrar bajagas.db (que ademas suele
    # estar abierta por el servidor).
    from .seed import asegurar_plantas
    hecho = asegurar_plantas(db)
    if hecho.get("adoptado"):
        res["avisos"].append(f"El taller '{hecho['adoptado']}' se adopto como Alamos, "
                             "conservando su plano.")
    plantas = {p.clave: p for p in db.query(m.Planta).all()}
    talleres = {t.planta_id: t for t in db.query(m.Taller).all()}
    if not plantas:
        res["avisos"].append("No se pudieron crear las plantas.")
        return res
    res["plantas"] = len(plantas)

    def taller_de(sucursal_norm):
        clave = SUCURSAL_A_PLANTA.get(sucursal_norm)
        if not clave:
            return None
        clave = TALLER_SUSTITUTO.get(clave, clave)
        pl = plantas.get(clave)
        return talleres.get(pl.id) if pl else None

    roles = {r.nombre: r for r in db.query(m.Rol).all()}
    tipos = {t.nombre: t for t in db.query(m.TipoUnidad).all()}
    usados = {u.email for u in db.query(m.Usuario).all()}

    # ---------------------------------------------------- catalogo de flota --
    descripciones = {}
    # De la hoja UNIDAD del libro de requisiciones, no de `vehiculos.csv`: es la
    # misma tabla que el capturista consulta, y ademas trae VIN, ano y centro de
    # gestion que el CSV no tenia.
    datos_unidad = _leer_unidades_requis(carpeta)
    for num, d in datos_unidad.items():
        descripciones[num] = d["descripcion"]
    if not datos_unidad:
        res["avisos"].append(
            "No se encontro el libro REQUIS en la carpeta: la flota queda sin "
            "marca ni modelo.")

    # Las refacciones y la flota no dependen de este archivo, asi que su
    # ausencia no debe tumbar la importacion entera: se avisa y se sigue con lo
    # que si hay. Antes reventaba con un rastreo de openpyxl que no decia que
    # archivo faltaba.
    ruta_personas = os.path.join(carpeta, "INFO CHOFERES 2026 ACTUAL.xlsx")
    if not os.path.exists(ruta_personas):
        res["avisos"].append(
            f"Falta 'INFO CHOFERES 2026 ACTUAL.xlsx' en {carpeta}: no se importaron "
            "choferes, supervisores ni tecnicos. Las refacciones y la flota si.")
        return _terminar(db, carpeta, res, plantas, talleres, con_partes)

    wb = openpyxl.load_workbook(ruta_personas, data_only=True)

    # ----------------------------------------- supervisores y sus cuadrillas --
    # Las cuadrillas ya creadas se reutilizan: correr el importador dos veces
    # no debe dejar 13 supervisores repetidos.
    cuadrillas = {}
    ya_cuadrillas = {c.nombre: c for c in db.query(m.Cuadrilla).all()}
    for hoja in _hojas_flota(wb):
        ws = wb[hoja]
        cab, hr = _cabecera(ws)
        iS, iSup = cab.get("SUCURSAL"), cab.get("SUPERVISOR")
        if iS is None or iSup is None:
            continue
        for r in ws.iter_rows(min_row=hr + 1, values_only=True):
            if iS >= len(r) or not r[iS] or iSup >= len(r) or not r[iSup]:
                continue
            suc, nom = _norm(r[iS]), re.sub(r"\s+", " ", str(r[iSup]).strip())
            if (suc, nom) in cuadrillas:
                continue
            # La columna SUPERVISOR va al reves que la columna CHOFER: aqui el
            # nombre va primero. Ver _partir_nombre.
            n, a = _partir_nombre(nom, nombre_primero=True)
            clave_cuadrilla = f"{suc.title()} - {a}"

            # El correo NO depende de como se parta el nombre --sale del texto
            # crudo del Excel-- asi que sirve de identidad estable. Con el se
            # reconoce al supervisor que ya existe aunque su cuadrilla se llame
            # como se llamaba antes de corregir el orden del nombre.
            #
            # Se busca con _correo_BASE, no con _correo: _correo resuelve
            # choques agregando un numero, asi que sobre una base que ya tenia
            # a los 13 supervisores devolvia "franciscofau2@bajagas.mx", no
            # encontraba a nadie y los creaba OTRA VEZ. Trece duplicados.
            correo_base = _correo_base("", nom + suc)
            previo = db.query(m.Usuario).filter(m.Usuario.email == correo_base).first()
            if previo:
                if (previo.nombre, previo.apellidos) != (n, a):
                    previo.nombre, previo.apellidos = n, a
                sup_previo = db.query(m.Supervisor).filter_by(usuario_id=previo.id).first()
                cua = (db.query(m.Cuadrilla).filter_by(supervisor_id=previo.id).first()
                       if sup_previo else None)
                if cua:
                    cua.nombre = clave_cuadrilla
                    cuadrillas[(suc, nom)] = cua
                    ya_cuadrillas[clave_cuadrilla] = cua
                    continue

            existente = ya_cuadrillas.get(clave_cuadrilla)
            if existente:
                cuadrillas[(suc, nom)] = existente
                continue
            u = m.Usuario(nombre=n, apellidos=a, email=_correo("", nom + suc, usados),
                          password_hash=hash_password(PASSWORD_PRUEBA))
            db.add(u); db.flush()
            db.add(m.UsuarioRol(usuario_id=u.id, rol_id=roles["supervisor"].id))
            s = m.Supervisor(usuario_id=u.id, zona=suc.title())
            db.add(s); db.flush()
            c = m.Cuadrilla(nombre=clave_cuadrilla, supervisor_id=s.usuario_id)
            db.add(c); db.flush()
            cuadrillas[(suc, nom)] = c
            ya_cuadrillas[clave_cuadrilla] = c
            res["supervisores"] += 1
    db.flush()

    # ------------------------------------------------- unidades y choferes --
    tipo_defecto = tipos.get("reparto") or next(iter(tipos.values()))
    # Lo que ya esta en la base cuenta como visto: correr dos veces no duplica.
    vistos_unidad = {u.num_economico for u in db.query(m.Unidad.num_economico).all()}
    vistos_empleado = set()
    for hoja in _hojas_flota(wb):
        ws = wb[hoja]
        cab, hr = _cabecera(ws)
        iS, iSup = cab.get("SUCURSAL"), cab.get("SUPERVISOR")
        iU, iE, iC = cab.get("UNIDAD"), cab.get("NUMEMPLEADO"), cab.get("CHOFER")
        if iS is None or iU is None:
            continue
        for r in ws.iter_rows(min_row=hr + 1, values_only=True):
            if iS >= len(r) or not r[iS]:
                continue
            suc = _norm(r[iS])
            num = str(r[iU]).strip() if iU < len(r) and r[iU] else None
            if not num or num in vistos_unidad:
                continue
            vistos_unidad.add(num)

            # chofer, si la fila lo trae
            chofer = None
            nom = str(r[iC]).strip() if iC is not None and iC < len(r) and r[iC] else None
            emp = str(r[iE]).strip() if iE is not None and iE < len(r) and r[iE] else None
            if nom and emp and emp not in vistos_empleado:
                vistos_empleado.add(emp)
                n, a = _partir_nombre(nom)
                u = m.Usuario(nombre=n, apellidos=a, email=_correo(emp, nom, usados),
                              password_hash=hash_password(PASSWORD_PRUEBA))
                db.add(u); db.flush()
                db.add(m.UsuarioRol(usuario_id=u.id, rol_id=roles["chofer"].id))
                cua = None
                if iSup is not None and iSup < len(r) and r[iSup]:
                    cua = cuadrillas.get((suc, re.sub(r"\s+", " ", str(r[iSup]).strip())))
                chofer = m.Chofer(usuario_id=u.id, num_licencia=f"LIC-{emp}",
                                  vencimiento_licencia=date.today() + timedelta(days=400),
                                  cuadrilla_id=cua.id if cua else None)
                db.add(chofer); db.flush()
                res["choferes"] += 1

            t = taller_de(suc)
            d = datos_unidad.get(num, {})
            desc = d.get("descripcion") or descripciones.get(num, "")
            marca = desc.split()[0].title() if desc else None
            # El ano viene como columna propia en la hoja UNIDAD. Solo se
            # rasca del texto si la columna no lo trae.
            anio = d.get("anio")
            if not anio:
                mm = re.search(r"\b(19|20)\d{2}\b", desc or "")
                anio = int(mm.group(0)) if mm else None
            db.add(m.Unidad(
                num_economico=num, placas=None, vin=d.get("vin") or None,
                marca=marca, modelo=desc[:60] or None, anio=anio,
                tipo_unidad_id=tipo_defecto.id,
                titular_chofer_id=chofer.usuario_id if chofer else None,
                poseedor_chofer_id=chofer.usuario_id if chofer else None,
                taller_asignado_id=t.id if t else None,
                activo="BLOQUEADA" not in (desc or "").upper()))
            res["unidades"] += 1

    # Los choferes que ya existian no pasan por el bloque de arriba --su unidad
    # ya estaba-- asi que una correccion en como se parte el nombre no les
    # llegaba nunca. Aqui se les pone al dia por numero de empleado, que es su
    # identidad estable.
    res["nombres_corregidos"] = 0
    for hoja in _hojas_flota(wb):
        ws = wb[hoja]
        cab, hr = _cabecera(ws)
        iE, iC = cab.get("NUMEMPLEADO"), cab.get("CHOFER")
        if iE is None or iC is None:
            continue
        for r in ws.iter_rows(min_row=hr + 1, values_only=True):
            if iE >= len(r) or not r[iE] or iC >= len(r) or not r[iC]:
                continue
            emp = str(r[iE]).strip()
            n, a = _partir_nombre(str(r[iC]).strip())
            u = (db.query(m.Usuario)
                 .filter(m.Usuario.email == _correo_base(emp, "")).first())
            if u and (u.nombre, u.apellidos) != (n, a):
                u.nombre, u.apellidos = n, a
                res["nombres_corregidos"] += 1
    db.flush()

    # ----------------------------------------------------- personal de taller --
    if "TALLER" in wb.sheetnames:
        ws = wb["TALLER"]
        cab, hr = _cabecera(ws)
        iUb, iNe = cab.get("UBICACION"), cab.get("NUMEMPLEADO")
        iNom = cab.get("DESPACHADORES") or cab.get("NOMBRE")
        iPue = cab.get("PUESTO")
        ya_tecnicos = {t.num_empleado for t in db.query(m.Tecnico.num_empleado).all()
                       if t.num_empleado}
        for r in ws.iter_rows(min_row=hr + 1, values_only=True):
            if iNom is None or iNom >= len(r) or not r[iNom]:
                continue
            _emp = str(r[iNe]).strip() if iNe is not None and iNe < len(r) and r[iNe] else None
            if _emp and _emp in ya_tecnicos:
                continue
            ub = _norm(r[iUb]) if iUb is not None and iUb < len(r) else ""
            if ub.startswith("VALLE"):
                ub = "VALLEREDONDO"
            t = taller_de(ub)
            puesto = str(r[iPue]).strip() if iPue is not None and iPue < len(r) and r[iPue] else ""
            esp = "mecanico"
            for clave, valor in PUESTO_A_ESPECIALIDAD:
                if clave in _norm(puesto):
                    esp = valor
                    break
            n, a = _partir_nombre(r[iNom])
            emp = str(r[iNe]).strip() if iNe is not None and iNe < len(r) and r[iNe] else None
            # Alamos = ASISTIDO (Erick captura por ellos). Satelites = AUTONOMO.
            modalidad = "ASISTIDO" if ub == "ALAMOS" else "AUTONOMO"
            tec = m.Tecnico(nombre=n, apellidos=a, num_empleado=emp, especialidad=esp,
                            puesto=puesto or None, taller_id=t.id if t else None,
                            modalidad=modalidad)
            db.add(tec); db.flush()
            if modalidad == "AUTONOMO":
                # El autonomo SI usa la app: necesita cuenta (RI-A-18).
                u = m.Usuario(nombre=n, apellidos=a, email=_correo(emp, n + a, usados),
                              password_hash=hash_password(PASSWORD_PRUEBA))
                db.add(u); db.flush()
                tec.usuario_id = u.id
            res["tecnicos"] += 1
    db.flush()

    return _terminar(db, carpeta, res, plantas, talleres, con_partes)


def _terminar(db: Session, carpeta: str, res: dict, plantas: dict, talleres: dict,
              con_partes: bool) -> dict:
    """Refacciones primero, requisiciones despues.

    El orden importa: los renglones de la requisicion se casan por codigo
    contra el catalogo de piezas, asi que el catalogo tiene que existir ya.
    """
    res = _importar_partes(db, carpeta, res, plantas, talleres, con_partes)
    return _importar_requisiciones(db, carpeta, res)


def _importar_partes(db: Session, carpeta: str, res: dict, plantas: dict,
                     talleres: dict, con_partes: bool) -> dict:
    """Refacciones y existencias. Va aparte porque no depende del archivo de
    personas: si ese falta, esto igual se puede cargar."""
    if not con_partes:
        db.commit()
        return res

    alm = talleres.get(plantas["ALAMOS"].id) if "ALAMOS" in plantas else None
    materiales = _leer_materiales(carpeta)
    if not materiales or not alm:
        if not materiales:
            res["avisos"].append(
                f"No se encontro el libro REQUIS con la hoja MATERIALES en {carpeta}.")
        db.commit()
        return res

    # Para el CODIGO ya no hace falta casar por texto: MATERIALES lo trae en la
    # misma fila que el nombre, y ese casado por nombre fallaba en un porcentaje
    # real de los casos --la deuda que anotaba `contexto-del-proyecto-2.md` §3.
    # CODIGOS TALLER se sigue leyendo por una sola cosa que MATERIALES no tiene:
    # en QUE almacen fisico vive la refaccion (RF03, "ALM CHANGAN 2"...).
    catalogo = _leer_codigos_sap(carpeta)
    if not catalogo:
        res["avisos"].append(
            "Falta 'CODIGOS TALLER.xlsx': las refacciones quedan sin ubicacion de almacen.")

    piezas, cantidades = [], {}
    vistos = {n[0].upper() for n in db.query(m.Pieza.nombre).all()}
    base_sku = db.query(m.Pieza).count()
    for i, fila in enumerate(materiales, base_sku + 1):
        nombre = fila["nombre"]
        # Se compara el nombre YA TRUNCADO, que es como queda guardado: si no,
        # los nombres de mas de 160 caracteres se reinsertan en cada corrida
        # porque el completo nunca aparece en la base.
        guardado = nombre[:160].rstrip()
        clave = guardado.upper()
        if not guardado or clave in vistos:
            continue
        vistos.add(clave)
        cantidades[clave] = fila["existencia"]

        codigo = fila["codigo"] or _codigo_pegado(guardado)
        origen = "sap" if fila["codigo"] else ("nombre" if codigo else None)
        piezas.append({"sku": codigo or f"P-{i:06d}", "nombre": guardado,
                       "descripcion": nombre, "codigo_externo": codigo,
                       "origen_codigo": origen, "unidad_medida": "pieza",
                       "precio_referencia": fila["costo"],
                       "stock_actual": 0, "stock_minimo": 0, "activa": True})
    db.bulk_insert_mappings(m.Pieza, piezas)
    db.flush()
    res["piezas"] = len(piezas)
    res["con_codigo_sap"] = sum(1 for p in piezas if p["origen_codigo"] == "sap")
    res["sin_codigo"] = sum(1 for p in piezas if not p["codigo_externo"])

    # La existencia ya NO se inventa. La hoja MATERIALES trae la columna DIS, asi
    # que el buscador contesta "hay 7" porque hay 7, no porque un hash del
    # nombre cayo en el 60%. Cuando el archivo no traia cantidad inventarla era
    # la unica opcion; ahora seria mentirle al administrador que va por la pieza.
    ya = {e.pieza_id for e in db.query(m.Existencia.pieza_id)
          .filter(m.Existencia.taller_id == alm.id).all()}
    existencias = []
    for p in db.query(m.Pieza.id, m.Pieza.nombre).all():
        if p.id in ya:
            continue
        clave = p.nombre.upper()
        _cod, _org, almacen = catalogo.get(clave, (None, None, None))
        existencias.append({"taller_id": alm.id, "pieza_id": p.id,
                            "stock_actual": cantidades.get(clave, 0),
                            "stock_reservado": 0, "stock_minimo": 0,
                            "ubicacion_fisica": almacen})
    db.bulk_insert_mappings(m.Existencia, existencias)
    res["existencias"] = len(existencias)
    res["con_stock"] = sum(1 for e in existencias if e["stock_actual"] > 0)

    db.commit()
    return res


# --------------------------------------------------------------------------- #
# Las requisiciones que ya tecleo el capturista
# --------------------------------------------------------------------------- #
# El libro REQUIS trae, despues de MATERIALES / UNIDAD / EMPLEADO, una hoja por
# cada requisicion capturada: 100 papeles reales de julio y agosto de 2026. Se
# importan para que el modulo del capturista abra con SU trabajo dentro y no
# con una tabla vacia, y para poder medir cuanto teclea al dia.
#
# El formato de las 100 hojas es identico (verificado hoja por hoja):
#   fila  4  B "REQUISICION"  -> folio a la derecha; a partir de la columna M
#                               "UNIDAD:" -> num. economico, equipo SAP, CEGE
#   fila  7  B "FECHA:"       -> fecha del papel; a la derecha la descripcion
#   fila 10  B "EMPLEADO"     -> numero y nombre de quien pidio el material
#   fila 12+ B codigo | E descripcion | Q cantidad, hasta el renglon "AUTORIZO"
FILA_FOLIO, FILA_FECHA, FILA_EMPLEADO = 3, 6, 9   # base 0
COL_ETIQUETA, COL_UNIDAD = 1, 12
COL_CODIGO, COL_DESCRIPCION, COL_CANTIDAD = 1, 4, 16

# Lo que Excel escribe cuando una formula no encuentra nada. Guardarlo seria
# poner "#N/A" como si fuera el numero de una unidad.
BASURA_EXCEL = {"#N/A", "#N/D", "#DIV/0!", "#REF!", "#VALUE!", "#NAME?", "-"}


def _dato(v):
    """El valor limpio, o None si la celda trae un error de Excel."""
    if v is None:
        return None
    t = str(v).strip()
    return None if not t or t.upper() in BASURA_EXCEL else t


def _der(fila, desde):
    """Los valores utiles a la derecha de una columna, en orden."""
    return [_dato(v) for k, v in enumerate(fila) if k > desde and _dato(v)]


def _clave_unidad(t) -> str:
    """"BG-354P" y "BG354P" son la misma unidad: el papel y el catalogo no se
    escriben igual."""
    return re.sub(r"[^A-Z0-9]", "", str(t or "").upper())


def _hojas_requisicion(wb):
    return [h for h in wb.sheetnames if _norm(h).startswith("REQUI")]


def _leer_requisicion(ws):
    filas = [list(r) for r in ws.iter_rows(values_only=True)]
    if len(filas) <= FILA_EMPLEADO:
        return None
    cab = _der(filas[FILA_FOLIO], COL_ETIQUETA)
    if not cab:
        return None
    unidad_cab = _der(filas[FILA_FOLIO], COL_UNIDAD)
    fecha = next((v for v in filas[FILA_FECHA][COL_ETIQUETA + 1:]
                  if isinstance(v, (date, datetime))), None)
    emp = _der(filas[FILA_EMPLEADO], COL_ETIQUETA)

    renglones = []
    for r in filas[FILA_EMPLEADO + 2:]:
        codigo = _dato(r[COL_CODIGO]) if len(r) > COL_CODIGO else None
        if not codigo:
            continue
        if "AUTORIZO" in codigo.upper():
            break                                  # el pie de firmas
        desc = _dato(r[COL_DESCRIPCION]) if len(r) > COL_DESCRIPCION else None
        cant = r[COL_CANTIDAD] if len(r) > COL_CANTIDAD else None
        renglones.append({
            "codigo": codigo[:40],
            "descripcion": (desc or codigo)[:200],
            "cantidad": int(cant) if isinstance(cant, (int, float)) and cant > 0 else 1,
        })

    return {
        "folio": cab[0][:24],
        "unidad": unidad_cab[0] if unidad_cab else None,
        "equipo_sap": unidad_cab[1][:20] if len(unidad_cab) > 1 else None,
        "cege": unidad_cab[2][:10] if len(unidad_cab) > 2 else None,
        "fecha": fecha.date() if isinstance(fecha, datetime) else fecha,
        "num_empleado": emp[0][:30] if emp else None,
        "nombre": emp[1][:120] if len(emp) > 1 else None,
        "renglones": renglones,
    }


def _firma_requisicion(folio, fecha, unidad, renglones) -> tuple:
    """Que hace unica a una requisicion: el papel Y lo que pide.

    Folio + fecha + unidad NO alcanza. En el libro real hay folios reutilizados
    el mismo dia para pedidos distintos, asi que comparar solo el encabezado
    tiraba requisiciones buenas.
    """
    return (str(folio).strip().upper(), fecha, _clave_unidad(unidad),
            tuple(sorted((str(c or "").strip(), int(n or 0)) for c, n in renglones)))


def _importar_requisiciones(db: Session, carpeta: str, res: dict) -> dict:
    res.setdefault("requisiciones", 0)
    res.setdefault("renglones", 0)
    ruta = _ruta_requis(carpeta)
    if not ruta:
        return res

    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hojas = _hojas_requisicion(wb)
    if not hojas:
        wb.close()
        return res

    unidades = {_clave_unidad(u.num_economico): u.id
                for u in db.query(m.Unidad.id, m.Unidad.num_economico).all()
                if u.num_economico}
    tecnicos = {t.num_empleado: (t.id, t.taller_id)
                for t in db.query(m.Tecnico.id, m.Tecnico.num_empleado,
                                  m.Tecnico.taller_id).all() if t.num_empleado}
    talleres_unidad = {u.id: u.taller_asignado_id
                       for u in db.query(m.Unidad.id, m.Unidad.taller_asignado_id).all()}
    piezas = {}
    for pz in db.query(m.Pieza.id, m.Pieza.sku, m.Pieza.codigo_externo).all():
        for c in (pz.codigo_externo, pz.sku):
            if c and c not in piezas:
                piezas[c] = pz.id

    # El capturista de Alamos es quien tecleo todo esto. Si todavia no tiene
    # cuenta, la requisicion se guarda igual pero sin responsable de captura:
    # es un dato faltante, no una razon para perder el documento.
    cap = (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
           .filter(m.Rol.nombre == "capturista").first())

    # La firma incluye LOS MATERIALES, no solo folio+fecha+unidad. Con la llave
    # corta se descartaban tres requisiciones buenas: J331 y J332 se repiten el
    # mismo dia con materiales distintos --el folio se reutilizo-- y solo J299
    # esta de verdad tecleada dos veces.
    # Lo que ya esta en la base (de una corrida anterior) y lo que ya se leyo
    # en ESTA corrida se cuentan aparte. Volver a correr el importador no es un
    # hallazgo; dos hojas identicas dentro del mismo libro si lo son.
    en_base = set()
    for r in db.query(m.Requisicion).all():
        en_base.add(_firma_requisicion(
            r.folio, r.fecha, r.unidad_texto,
            [(x.codigo, x.cantidad) for x in r.renglones]))
    en_libro = set()
    ya_importadas, duplicadas, sin_pieza = 0, 0, 0
    for hoja in hojas:
        d = _leer_requisicion(wb[hoja])
        if not d or not d["folio"] or not d["fecha"] or not d["renglones"]:
            continue
        llave = _firma_requisicion(
            d["folio"], d["fecha"], d["unidad"],
            [(r["codigo"], r["cantidad"]) for r in d["renglones"]])
        if llave in en_libro:
            # Mismo papel, hasta el ultimo renglon, DOS VECES EN EL LIBRO: se
            # tecleo dos veces. Es el unico control que el Excel no puede
            # hacer solo, y es lo que vale la pena reportar.
            duplicadas += 1
            continue
        en_libro.add(llave)
        if llave in en_base:
            ya_importadas += 1              # corrida repetida, no es hallazgo
            continue

        unidad_id = unidades.get(_clave_unidad(d["unidad"])) if d["unidad"] else None
        tec_id, tec_taller = tecnicos.get(d["num_empleado"], (None, None))
        req = m.Requisicion(
            folio=d["folio"], fecha=d["fecha"],
            unidad_id=unidad_id, unidad_texto=d["unidad"],
            equipo_sap=d["equipo_sap"], centro_gestion=d["cege"],
            taller_id=talleres_unidad.get(unidad_id) or tec_taller,
            tecnico_id=tec_id, solicitante_num_empleado=d["num_empleado"],
            solicitante_nombre=d["nombre"],
            capturada_por_usuario_id=cap.id if cap else None,
            estado="capturada", origen="excel")
        db.add(req)
        db.flush()
        for i, r in enumerate(d["renglones"], 1):
            pid = piezas.get(r["codigo"])
            if pid is None:
                sin_pieza += 1
            db.add(m.RenglonRequisicion(
                requisicion_id=req.id, linea=i, pieza_id=pid,
                codigo=r["codigo"], descripcion=r["descripcion"],
                cantidad=r["cantidad"]))
            res["renglones"] += 1
        res["requisiciones"] += 1

    wb.close()

    # Curacion: si una corrida anterior importo el libro antes de que existiera
    # la cuenta del capturista, esas requisiciones quedaron sin responsable.
    # Se les pone ahora en vez de exigir que se borre la base.
    if cap:
        huerfanas = (db.query(m.Requisicion)
                     .filter(m.Requisicion.origen == "excel",
                             m.Requisicion.capturada_por_usuario_id.is_(None))
                     .update({"capturada_por_usuario_id": cap.id},
                             synchronize_session=False))
        if huerfanas:
            res["avisos"].append(
                f"{huerfanas} requisicion(es) importadas antes se quedaron sin "
                f"responsable de captura: ahora quedan a nombre de "
                f"{cap.nombre_completo}.")

    if duplicadas:
        res["avisos"].append(
            f"{duplicadas} requisicion(es) del libro venian tecleadas dos veces "
            "(mismo folio, misma fecha, misma unidad y los mismos materiales): "
            "se guardo una sola.")
    if ya_importadas:
        res["avisos"].append(
            f"{ya_importadas} requisicion(es) del libro ya estaban importadas: "
            "no se volvieron a crear.")
    if sin_pieza:
        res["avisos"].append(
            f"{sin_pieza} renglon(es) de requisicion traen un codigo que no esta "
            "en el catalogo de refacciones: se guardan con su codigo y su texto.")
    db.commit()
    return res


if __name__ == "__main__":  # pragma: no cover
    from .core.database import Base, SessionLocal, engine
    from .core.migraciones import asegurar_indices
    from .seed import (asegurar_roles, asegurar_tipos_servicio,
                       asegurar_usuarios_demo, sembrar)

    carpeta = os.environ.get("DATOS_REALES", CARPETA_DATOS)
    Base.metadata.create_all(bind=engine)
    asegurar_indices(engine)
    s = SessionLocal()
    try:
        asegurar_tipos_servicio(s)   # antes: los planes lo referencian
        sembrar(s)
        # Lo mismo que hace el arranque del servidor. Va ANTES de importar
        # porque las requisiciones se guardan a nombre del capturista, y sobre
        # una base que ya existia `sembrar` se rinde sin crear ni el rol ni la
        # cuenta: las 99 requisiciones quedaban sin responsable de captura.
        asegurar_roles(s)
        asegurar_usuarios_demo(s)
        r = importar(s, carpeta)
        print("Importacion terminada:")
        for k, v in r.items():
            print(f"   {k:<14} {v}")
    finally:
        s.close()
