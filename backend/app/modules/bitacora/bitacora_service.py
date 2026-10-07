"""Escribir y leer el libro de bitacora de mantenimiento (NOM-030, 7.1.9 y 7.1.10).

UN SOLO LUGAR ESCRIBE ASIENTOS: `asentar()`. Numera, sella la hora con el reloj
del servidor, copia el nombre de quien registra y encadena el hash. Si cada
controlador armara su asiento a mano, bastaria con que uno olvidara el hash o
tomara la hora del navegador para que el libro dejara de servir como prueba.

NO HACE COMMIT, igual que `crear_reporte_mantenimiento`: el asiento viaja en la
misma transaccion que el cambio que registra. Si el cambio falla, no queda un
asiento de algo que no ocurrio; si el asiento falla, el cambio tampoco entra.
"""
import hashlib
import json
from datetime import date, datetime

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import a_utc, ahora_utc, dia_operativo
from .asiento_model import REGISTRADO_POR_SISTEMA, AsientoBitacora

# El primer asiento de cada libro no tiene anterior: se encadena a sesenta y
# cuatro ceros, el largo de un SHA-256 en hexadecimal.
GENESIS = "0" * 64

# Parametros de `configuracion` con los datos del Regulado que 7.1.10 c) pide
# en cada libro. Viven ahi y no en el codigo porque los da el cliente y pueden
# cambiar (un permiso se renueva) sin desplegar.
CLAVE_RAZON_SOCIAL = "nom030_razon_social"
CLAVE_PERMISO = "nom030_permiso"
# El instante en que nacio el libro electronico. Lo anterior se copia UNA vez
# como `migracion`; lo posterior tiene que traer su asiento de origen.
CLAVE_LIBRO_DESDE = "nom030_libro_desde"


# ------------------------------------------------------------ utilidades ---- #
def _fecha_canonica(v):
    """Una sola forma de escribir fechas, para que el hash no dependa del tipo."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return a_utc(v).isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _json(valor) -> str:
    """JSON estable: mismas llaves en el mismo orden, siempre. El hash depende."""
    return json.dumps(valor, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=_fecha_canonica)


def _contenido(a: AsientoBitacora) -> dict:
    """Lo que el hash protege. TODO lo que el libro muestra entra aqui."""
    return {
        "unidad_id": a.unidad_id, "numero": a.numero, "num_economico": a.num_economico,
        "reporte_id": a.reporte_id, "actividad_id": a.actividad_id,
        "programa_id": a.programa_id, "tipo": a.tipo, "origen": a.origen,
        "sistema": a.sistema, "descripcion": a.descripcion,
        "resultado": a.resultado, "acciones_requeridas": a.acciones_requeridas,
        "responsable_nombre": a.responsable_nombre,
        "responsable_tecnico_id": a.responsable_tecnico_id,
        "fecha_inicio": _fecha_canonica(a.fecha_inicio),
        "fecha_termino": _fecha_canonica(a.fecha_termino),
        "datos": a.datos, "corrige_a_id": a.corrige_a_id, "motivo": a.motivo,
        "registrado_en": _fecha_canonica(a.registrado_en),
        "registrado_por_id": a.registrado_por_id,
        "registrado_por_nombre": a.registrado_por_nombre,
        "hash_anterior": a.hash_anterior,
    }


def calcular_hash(a: AsientoBitacora) -> str:
    return hashlib.sha256(_json(_contenido(a)).encode("utf-8")).hexdigest()


def _ultimo(db: Session, unidad_id: int):
    return (db.query(AsientoBitacora)
            .filter(AsientoBitacora.unidad_id == unidad_id)
            .order_by(AsientoBitacora.numero.desc()).first())


def nombre_de(db: Session, usuario_id) -> str:
    if not usuario_id:
        return REGISTRADO_POR_SISTEMA
    u = db.query(m.Usuario).filter(m.Usuario.id == usuario_id).first()
    return u.nombre_completo if u else REGISTRADO_POR_SISTEMA


def _como_fecha(v):
    """Las columnas de inicio y termino son fechas; un instante se lleva al dia
    de Tijuana, que es el dia del taller."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return dia_operativo(v)
    return v


# ---------------------------------------------------------------- escribir -- #
def bloquear_unidad(db: Session, unidad_id: int) -> None:
    """Toma el candado de escritura de SQLite para el libro de esta unidad.

    Un UPDATE que no cambia nada basta para que SQLite le de a esta transaccion
    el candado de escritura: cualquier otra que quiera escribir espera su turno.
    Los endpoints lo llaman ANTES de leer el renglon que van a cambiar, no solo
    antes de numerar: si dos personas editan el mismo sistema a la vez, la
    segunda tiene que leer lo que dejo la primera, o su cambio se asentaria como
    avance cuando en realidad corrige (7.1.10 a).
    """
    db.execute(text("UPDATE unidad SET id = id WHERE id = :u"), {"u": unidad_id})


def asentar(db: Session, *, unidad_id: int, tipo: str, descripcion: str,
            registrado_por_id=None, reporte_id=None, actividad_id=None,
            programa_id=None, origen="formato_mantenimiento",
            sistema=None, resultado=None, acciones_requeridas=None,
            responsable_nombre=None, responsable_tecnico_id=None,
            fecha_inicio=None, fecha_termino=None, datos=None,
            corrige_a_id=None, motivo=None,
            registrado_por_nombre=None) -> AsientoBitacora:
    """Agrega un asiento al libro de la unidad. No hace commit.

    PRIMERO SE TOMA EL CANDADO, DESPUES SE LEE EL ULTIMO. Los endpoints corren
    en hilos, y dos personas pueden escribir en el libro de la misma unidad a
    la vez (el administrador captura mientras el mecanico da un avance). Si
    las dos leen "el ultimo es el 7" antes de que cualquiera escriba, las dos
    intentan ser el 8. El UPDATE vacio sobre la unidad obliga a SQLite a darle
    a esta transaccion el candado de escritura; la otra espera su turno y lee
    ya el 8. El UNIQUE(unidad_id, numero) queda como ultima defensa.

    El `flush` del final tampoco es opcional: la sesion no hace autoflush, y
    sin el, el segundo asiento de la misma peticion no veria al primero.
    """
    bloquear_unidad(db, unidad_id)
    unidad = db.get(m.Unidad, unidad_id)
    if unidad is None:
        raise ValueError(f"No existe la unidad {unidad_id}: no hay libro donde asentar.")
    anterior = _ultimo(db, unidad_id)
    a = AsientoBitacora(
        unidad_id=unidad_id,
        numero=(anterior.numero + 1) if anterior else 1,
        num_economico=unidad.num_economico,
        reporte_id=reporte_id, actividad_id=actividad_id, programa_id=programa_id,
        tipo=tipo, origen=origen, sistema=sistema, descripcion=descripcion,
        resultado=resultado, acciones_requeridas=acciones_requeridas or None,
        responsable_nombre=responsable_nombre,
        responsable_tecnico_id=responsable_tecnico_id,
        fecha_inicio=_como_fecha(fecha_inicio),
        fecha_termino=_como_fecha(fecha_termino),
        datos=_json(datos) if datos is not None else None,
        corrige_a_id=corrige_a_id, motivo=motivo or None,
        # La hora la pone el servidor, y se pone AQUI y no con el default de la
        # columna: el hash tiene que incluirla, y el default se aplica hasta el
        # INSERT, cuando el hash ya se calculo.
        registrado_en=ahora_utc(),
        registrado_por_id=registrado_por_id,
        registrado_por_nombre=registrado_por_nombre or nombre_de(db, registrado_por_id),
        hash_anterior=anterior.hash if anterior else GENESIS,
    )
    a.hash = calcular_hash(a)
    db.add(a)
    db.flush()
    return a


# ------------------------------------------------------------------ leer ---- #
def verificar(asientos: list) -> dict:
    """Recorre el libro y dice si esta integro, y si no, desde donde.

    Tres cosas pueden romperlo: un hueco en la numeracion (alguien borro un
    asiento), un eslabon que no apunta al anterior (alguien inserto o reordeno)
    o un hash que ya no corresponde al contenido (alguien edito). Las tres se
    detectan aqui, sin confiar en nada de lo que el propio asiento dice de si.

    Lo que la cadena NO puede ver es que falten los ULTIMOS asientos (una base
    restaurada de un respaldo viejo). Para eso el libro impreso lleva en el pie
    el numero y el hash del ultimo: un libro entregado antes sirve de ancla.
    """
    esperado_anterior = GENESIS
    for i, a in enumerate(asientos, start=1):
        if a.numero != i:
            return {"integra": False, "asientos": len(asientos), "falla_en": i,
                    "motivo": f"Falta el asiento {i}: la numeración salta al {a.numero}."}
        if a.hash_anterior != esperado_anterior:
            return {"integra": False, "asientos": len(asientos), "falla_en": a.numero,
                    "motivo": f"El asiento {a.numero} no está encadenado al anterior."}
        if calcular_hash(a) != a.hash:
            return {"integra": False, "asientos": len(asientos), "falla_en": a.numero,
                    "motivo": f"El contenido del asiento {a.numero} cambió después de registrarse."}
        esperado_anterior = a.hash
    return {"integra": True, "asientos": len(asientos), "falla_en": None, "motivo": None}


def verificar_libro(db: Session, unidad_id: int, asientos: list) -> dict:
    """La cadena, y ademas que el libro no le falte a ningun formato.

    La cadena sola dice que lo que HAY no cambio; no puede decir que falte algo
    al final (o todo: un libro vacio es una cadena perfecta). Por eso se cruza
    con los formatos, que viven en otra tabla: cada formato de la unidad tiene
    que tener su apertura (o su transcripcion), y cada formato que se cerro
    con el libro ya vigente, su asiento de cierre.
    """
    v = verificar(asientos)
    if not v["integra"]:
        return v
    desde_txt = parametro(db, CLAVE_LIBRO_DESDE)
    desde = a_utc(datetime.fromisoformat(desde_txt)) if desde_txt else None
    tipos = {}
    for a in asientos:
        if a.reporte_id:
            tipos.setdefault(a.reporte_id, set()).add(a.tipo)
    formatos = (db.query(m.ReporteMantenimiento)
                .filter(m.ReporteMantenimiento.unidad_id == unidad_id)
                .order_by(m.ReporteMantenimiento.fecha_entrada).all())
    for r in formatos:
        t = tipos.get(r.id, set())
        if not t & {"apertura", "migracion"}:
            return {**v, "integra": False, "falla_en": None,
                    "motivo": f"El formato {r.folio} no tiene asiento de apertura en el libro."}
        cerro_con_libro = r.estado == "cerrado" and r.fecha_salida and desde \
            and a_utc(r.fecha_salida) > desde
        if cerro_con_libro and "cierre" not in t:
            return {**v, "integra": False, "falla_en": None,
                    "motivo": f"El formato {r.folio} está cerrado y no tiene asiento de cierre."}
    # LA FIRMA DIBUJADA vive en firma_reporte, fuera de la cadena; su huella si
    # quedo dentro, en el asiento. Si el trazo de hoy ya no da esa huella,
    # alguien cambio el dibujo despues de firmar.
    import hashlib
    import json
    for a in asientos:
        if a.tipo != "firma" or not a.reporte_id or not a.datos:
            continue
        try:
            d = json.loads(a.datos)
        except ValueError:
            continue
        huella = d.get("trazo_sha256")
        if not huella:
            continue
        f = (db.query(m.FirmaReporte)
             .filter(m.FirmaReporte.reporte_id == a.reporte_id,
                     m.FirmaReporte.rol_firma == d.get("rol_firma")).first())
        actual = hashlib.sha256((f.trazo or "").encode()).hexdigest() if f else None
        if actual != huella:
            return {**v, "integra": False, "falla_en": a.numero,
                    "motivo": f"La firma del asiento {a.numero} ({d.get('folio')}) cambió "
                              "después de registrarse."}
    return v


def asientos_de_unidad(db: Session, unidad_id: int) -> list:
    return (db.query(AsientoBitacora)
            .filter(AsientoBitacora.unidad_id == unidad_id)
            .order_by(AsientoBitacora.numero).all())


def ultimo_de_actividad(db: Session, actividad_id: int):
    """El asiento mas reciente de un renglon: al que apunta una correccion."""
    return (db.query(AsientoBitacora)
            .filter(AsientoBitacora.actividad_id == actividad_id)
            .order_by(AsientoBitacora.numero.desc()).first())


def asiento_base_del_reporte(db: Session, reporte_id: int):
    """La apertura (o la copia de migracion) del formato."""
    return (db.query(AsientoBitacora)
            .filter(AsientoBitacora.reporte_id == reporte_id,
                    AsientoBitacora.tipo.in_(("apertura", "migracion")))
            .order_by(AsientoBitacora.numero).first())


def contar_de_reporte(db: Session, reporte_id: int) -> int:
    return (db.query(func.count(AsientoBitacora.id))
            .filter(AsientoBitacora.reporte_id == reporte_id).scalar() or 0)


def parametro(db: Session, clave: str, defecto: str = "") -> str:
    c = db.query(m.Configuracion).filter(m.Configuracion.clave == clave).first()
    return (c.valor or "").strip() if c else defecto


def _identificacion_del_asiento(a: AsientoBitacora):
    """La identificacion (7.1.10 c) COMO ERA al entrar la unidad.

    La cabecera del libro dice la de hoy; si el auxiliar o el permiso cambiaron,
    cada estancia tiene que seguir diciendo la suya, o el libro reescribiria su
    propio pasado.
    """
    if a.tipo not in ("apertura", "migracion") or not a.datos:
        return None
    try:
        ident = json.loads(a.datos).get("identificacion") or {}
    except (ValueError, AttributeError):
        return None
    return {k: ident.get(k) for k in ("razon_social", "permiso", "operadores",
                                      "personal_auxiliar", "num_economico")}


def asiento_out(a: AsientoBitacora) -> dict:
    """Lo que ve la pantalla. `datos` va decodificado; el hash, completo."""
    return {
        "identificacion": _identificacion_del_asiento(a),
        "id": a.id, "numero": a.numero, "num_economico": a.num_economico,
        "reporte_id": a.reporte_id,
        "folio": a.reporte.folio if a.reporte else None,
        "actividad_id": a.actividad_id, "programa_id": a.programa_id,
        "tipo": a.tipo, "origen": a.origen, "sistema": a.sistema,
        "descripcion": a.descripcion, "resultado": a.resultado,
        "acciones_requeridas": a.acciones_requeridas,
        "responsable_nombre": a.responsable_nombre,
        "fecha_inicio": a.fecha_inicio, "fecha_termino": a.fecha_termino,
        "corrige_a_id": a.corrige_a_id,
        "corrige_a_numero": a.corrige_a.numero if a.corrige_a else None,
        "motivo": a.motivo,
        "registrado_en": a.registrado_en,
        "registrado_por_nombre": a.registrado_por_nombre,
        "hash": a.hash,
    }
