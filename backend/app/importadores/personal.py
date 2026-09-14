"""Completa el padron de personal: telefonos, turnos y rutas.

El importador viejo ya trajo a 335 personas de INFO CHOFERES, pero se quedo
corto en tres cosas que ahora hacen falta:

  TELEFONOS   Hoy la base tiene CERO. Sin telefono no hay forma de avisarle a
              un chofer que le toca taller, asi que el mantenimiento trimestral
              no se puede operar aunque el sistema lo calcule perfecto. Los
              unicos que existen en los siete archivos estan en la hoja
              'NUMEROS DE CELULAR ' de CHOFERES LAN ESTACIONARIO, y son 85.

  TURNO       Decide que un chofer pueda ir al taller sin dejar su ruta sola.
              Vive en tres hojas distintas y ninguna lo tenia guardado.

  RUTA        Para repartir el horario: dos choferes de la misma ruta no pueden
              ir el mismo dia.

Ademas trae a los AYUDANTES, que solo existen en CHOFERES LAN: no manejan
unidad y por eso INFO CHOFERES no los lista, pero son personal y cuentan.

DOS TRAMPAS DE ESTE ARCHIVO, y las dos ya costaron tiempo:

  Los nombres de hoja traen espacios de sobra: 'RUTAS  TOTALES' lleva DOS
  espacios en medio y 'NUMEROS DE CELULAR ' lleva uno al final. Buscarlas por
  su nombre literal falla; se buscan normalizadas.

  El encabezado de 'NUMEROS DE CELULAR ' esta en la FILA 3, no en la 1, y su
  primera columna esta vacia.

Se ejecuta con:  python -m app.importadores.personal
"""
import logging
import os
import re
import unicodedata

import openpyxl
from sqlalchemy.orm import Session

from .. import models as m
from ..core.security import hash_password
from ..importador import PASSWORD_PRUEBA, _correo_base, _partir_nombre
from . import normaliza as n

log = logging.getLogger(__name__)

CARPETA_DATOS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))), "datos")

ARCHIVO_LAN = "CHOFERES LAN ESTACIONARIO 1.xlsx"
ARCHIVO_INFO = "INFO CHOFERES 2026 ACTUAL.xlsx"
HOJAS_CON_UNIDAD = ["REPARTO", "ESTACIONARIO", "EXPENDIOS", "MODULOS", "FRANQUICIA"]


def _cn(s) -> str:
    """Nombre de hoja o de columna reducido a algo comparable.

    'No.emp', 'No.Emp' y 'NUM. EMPLEADO ' tienen que poder encontrarse igual.
    """
    t = unicodedata.normalize("NFKD", str(s or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", t.upper())


def _hoja(wb, *nombres):
    """La hoja cuyo nombre normalizado coincida. None si no esta."""
    buscados = {_cn(x) for x in nombres}
    for h in wb.sheetnames:
        if _cn(h) in buscados:
            return wb[h]
    return None


def _mapa_columnas(fila) -> dict:
    return {_cn(v): i for i, v in enumerate(fila) if _cn(v)}


def _val(fila, col: dict, *nombres):
    for nombre in nombres:
        i = col.get(_cn(nombre))
        if i is not None and i < len(fila):
            return fila[i]
    return None


def _sumar(gente: dict, num: int, **datos):
    """Acumula lo que sepamos de una persona sin pisar lo que ya tenia.

    El numero de empleado es la llave; el nombre NO. La misma persona aparece
    escrita de dos formas --SAP corta a 30 caracteres y mete una coma-- asi que
    del nombre se conserva la version mas completa, no la ultima leida.
    """
    r = gente.setdefault(num, {"num": num, "nombre": "", "telefono": "",
                               "turno": "", "ruta": "", "perfil": "",
                               "unidad": "", "supervisor": ""})
    if datos.get("nombre"):
        r["nombre"] = n.nombre_mas_completo(r["nombre"], datos["nombre"])
    for campo in ("telefono", "turno", "ruta", "perfil", "unidad", "supervisor"):
        if not r[campo] and datos.get(campo):
            r[campo] = datos[campo]


def _leer(carpeta: str) -> dict:
    gente = {}

    # ------------------------------------------------- CHOFERES LAN (Logistica)
    ruta = os.path.join(carpeta, ARCHIVO_LAN)
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)

    ws = _hoja(wb, "RUTAS TOTALES")
    if ws is not None:
        filas = list(ws.iter_rows(values_only=True))
        col = _mapa_columnas(filas[0])
        for fila in filas[1:]:
            num = n.num_empleado(_val(fila, col, "No.emp", "Noemp"))
            if not num:
                continue
            _sumar(gente, num,
                   nombre=n.texto(_val(fila, col, "Chofer")),
                   turno=n.turno(_val(fila, col, "Turno")),
                   ruta=n.texto(_val(fila, col, "Ruta")),
                   unidad=n.clave_unidad(_val(fila, col, "Unidad")),
                   supervisor=n.texto(_val(fila, col, "Sup")))

    ws = _hoja(wb, "NUMEROS DE CELULAR")
    if ws is not None:
        filas = list(ws.iter_rows(values_only=True))
        # El encabezado esta en la fila 3 (indice 2), no en la 1.
        col = _mapa_columnas(filas[2])
        for fila in filas[3:]:
            num = n.num_empleado(_val(fila, col, "No.Emp", "NoEmp"))
            if not num:
                continue
            perfil = n.texto(_val(fila, col, "Perfil")).lower()
            _sumar(gente, num,
                   nombre=n.texto(_val(fila, col, "Nombre Chofer")),
                   telefono=n.telefono(_val(fila, col, "Telefono")),
                   turno=n.turno(_val(fila, col, "Turno")),
                   unidad=n.clave_unidad(_val(fila, col, "Unidad")),
                   supervisor=n.texto(_val(fila, col, "Supervisor")),
                   perfil="ayudante" if perfil.startswith("ayud") else
                          ("chofer" if perfil else ""))
    wb.close()

    # -------------------------------------------------- INFO CHOFERES (turnos)
    ruta = os.path.join(carpeta, ARCHIVO_INFO)
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    for nombre_hoja in HOJAS_CON_UNIDAD:
        ws = _hoja(wb, nombre_hoja)
        if ws is None:
            continue
        filas = list(ws.iter_rows(values_only=True))
        # Encabezado en la fila 2 (indice 1) en todas estas hojas.
        col = _mapa_columnas(filas[1])
        for fila in filas[2:]:
            num = n.num_empleado(_val(fila, col, "NUM. EMPLEADO", "NUMEMPLEADO"))
            if not num:
                continue
            _sumar(gente, num,
                   nombre=n.texto(_val(fila, col, "CHOFER")),
                   turno=n.turno(_val(fila, col, "TURNO")),
                   unidad=n.clave_unidad(_val(fila, col, "UNIDAD")),
                   supervisor=n.texto(_val(fila, col, "SUPERVISOR")))
    wb.close()
    return gente


def importar(db: Session, carpeta: str = CARPETA_DATOS) -> dict:
    gente = _leer(carpeta)

    rol_chofer = db.query(m.Rol).filter(m.Rol.nombre == "chofer").first()
    por_correo = {u.email: u for u in db.query(m.Usuario).all()}

    r = {"personas_en_los_excel": len(gente), "creadas": 0,
         "telefonos_puestos": 0, "turnos_puestos": 0, "rutas_puestas": 0,
         "ayudantes": 0, "sin_telefono": 0, "sin_turno": 0}

    for num, datos in sorted(gente.items()):
        correo = _correo_base(str(num), datos["nombre"])
        u = por_correo.get(correo)

        if u is None:
            if not datos["nombre"]:
                continue  # ni nombre ni cuenta: no hay persona que dar de alta
            nombre, apellidos = _partir_nombre(datos["nombre"])
            u = m.Usuario(nombre=nombre, apellidos=apellidos, email=correo,
                          password_hash=hash_password(PASSWORD_PRUEBA), activo=True)
            db.add(u)
            db.flush()
            por_correo[correo] = u
            if rol_chofer:
                db.add(m.UsuarioRol(usuario_id=u.id, rol_id=rol_chofer.id))
            r["creadas"] += 1

        # El telefono solo se pone si la persona no tiene uno de verdad. El
        # '664-000-0000' es relleno que puso la semilla, no un numero.
        if datos["telefono"]:
            actual = (u.telefono or "").strip()
            if not actual or actual == "664-000-0000":
                u.telefono = datos["telefono"]
                r["telefonos_puestos"] += 1
        else:
            r["sin_telefono"] += 1

        ch = db.get(m.Chofer, u.id)
        if ch is None:
            ch = m.Chofer(usuario_id=u.id, disponible=True)
            db.add(ch)
            db.flush()

        if datos["turno"] and not ch.turno:
            ch.turno = datos["turno"]
            r["turnos_puestos"] += 1
        elif not datos["turno"]:
            r["sin_turno"] += 1
        if datos["ruta"] and not ch.ruta:
            ch.ruta = datos["ruta"]
            r["rutas_puestas"] += 1
        if datos["perfil"] and not ch.perfil:
            ch.perfil = datos["perfil"]
            if datos["perfil"] == "ayudante":
                r["ayudantes"] += 1

    db.commit()
    return r


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from ..core.database import SessionLocal

    db = SessionLocal()
    try:
        antes_u = db.query(m.Usuario).count()
        antes_c = db.query(m.Chofer).count()
        r = importar(db)
        print(f"personas en los Excel : {r['personas_en_los_excel']}")
        print(f"usuarios              : {antes_u} -> {db.query(m.Usuario).count()}"
              f"  ({r['creadas']} nuevas)")
        print(f"choferes              : {antes_c} -> {db.query(m.Chofer).count()}")
        print(f"telefonos puestos     : {r['telefonos_puestos']}")
        print(f"turnos puestos        : {r['turnos_puestos']}")
        print(f"rutas puestas         : {r['rutas_puestas']}")
        print(f"marcados como ayudante: {r['ayudantes']}")
        print(f"sin telefono en ningun archivo: {r['sin_telefono']}")
    finally:
        db.close()
