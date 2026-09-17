"""Datos semilla. El taller reproduce el plano en Excel que entrego el cliente.

Zonas y numeracion tomadas del plano (docs/modelo-er.md §9). La numeracion se
repite entre zonas: hay un "1" en REPARTO, otro en ELECTRICOS y otro en el patio.
Por eso la unicidad es (zona, numero) y no global.
"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from . import models as m
from .core.database import Base, SessionLocal, engine
from .core.security import hash_password

# (nombre, proposito, cuenta_para_ocupacion, tipo_permitido, [numeros], fila)

# Las 6 plantas con taller + LIBERTAD, que es sucursal pero NO tiene taller:
# sus unidades se asignan a Alamos. Datos tomados de "INFO CHOFERES 2026".
# (clave, nombre, es_central, tiene_taller, lat, lng)
PLANTAS = [
    ("ALAMOS",        "Alamos",        True,  True,  32.5149, -117.0382),
    ("TECATE",        "Tecate",        False, True,  32.5665, -116.6270),
    ("ROSARITO",      "Rosarito",      False, True,  32.3617, -117.0553),
    ("CARRANZA",      "Carranza",      False, True,  32.5027, -116.9600),
    ("VALLEREDONDO",  "Valle Redondo", False, True,  32.4406, -116.8500),
    ("GUAYCURA",      "Guaycura",      False, True,  32.4700, -116.9800),
    ("LIBERTAD",      "Libertad",      False, False, 32.5300, -116.9700),
]

# Los talleres satelite son chicos. Numeros a confirmar con cada planta.
ESPACIOS_SATELITE = {
    "TECATE": 3, "ROSARITO": 3, "CARRANZA": 2, "VALLEREDONDO": 2, "GUAYCURA": 4,
}

# A donde va una unidad de una sucursal SIN taller.
TALLER_POR_DEFECTO = {"LIBERTAD": "ALAMOS"}

# (nombre, proposito, cuenta_para_ocupacion, tipo_permitido, [numeros], fila)
# NUMERACION POR FILA, no por zona. En el croquis del cliente los numeros
# corren de corrido a lo largo de cada fila -- 1 a 18 arriba pasando de REPARTO
# a PIPAS sin reiniciar, 1 a 12 abajo -- porque asi es como alguien parado en el
# patio se orienta: "esta en la T-14", no "esta en la tercera de pipas".
#
#   T = fila superior (Top)    I = fila inferior
#   L = llantera   F = fosa   P = patio   W = lavado   Y = yonke
#
# La zona sigue existiendo y define QUE tipo de unidad cabe; lo que cambia es
# como se lee la etiqueta.
#
# (nombre, proposito, admite_unidades, cuenta_para_ocupacion, tipo, [numeros], fila)
LAYOUT_TALLER = [
    ("REPARTO NORTE",   "operativa",     True,  True,  "reparto",
     ["T-%02d" % i for i in range(1, 11)],   0),
    ("PIPAS",           "operativa",     True,  True,  "pipa",
     ["T-%02d" % i for i in range(11, 19)],  0),
    ("LLANTERA",        "especialidad",  True,  True,  None,         ["L-01"],  0),
    ("ELECTRICOS",      "especialidad",  True,  True,  None,
     ["I-%02d" % i for i in range(1, 4)],    2),
    ("UTILITARIOS",     "operativa",     True,  True,  "utilitario",
     ["I-%02d" % i for i in range(4, 7)],    2),
    ("REPARTO SUR",     "operativa",     True,  True,  "reparto",
     ["I-%02d" % i for i in range(7, 13)],   2),

    # --- admiten unidad pero NO son capacidad de reparacion --------------- #
    # La fosa: caben CUATRO. Se revisa por debajo y la unidad sale, no es una
    # bahia donde se queda dias, por eso no cuenta para la ocupacion.
    ("FOSA",            "especialidad",  True,  False, None,
     ["F-%02d" % i for i in range(1, 5)],    2),
    # El patio guarda unidades que ESPERAN turno o que ya salieron de taller.
    # Son 55 lugares en DOS bloques, como en el croquis: diez arriba, junto al
    # contenedor y el area de lavado, y cuarenta y cinco abajo. Es un solo
    # patio -- una unidad estacionada en el P-40 esta en el patio igual que una
    # en el P-03 -- asi que es una zona con dos bloques de dibujo, no dos zonas.
    ("PATIO",           "apoyo",         True,  False, None,
     ["P-%02d" % i for i in range(1, 56)],   1),
    ("AREA LAVADO",     "apoyo",         True,  False, None,         ["W-01"],  1),

    # --- no admiten unidad: existen en el croquis para orientarse ---------- #
    # El yonke NO guarda vehiculos: guarda piezas y partes. Tenerlo con 45
    # cajones hacia creer que ahi cabia una unidad, y el bloque de 45 del
    # croquis es en realidad la parte de abajo del PATIO.
    ("YONKE",           "almacenaje",    False, False, None,         [],        3),
    ("OFICINA",         "no_operativa",  False, False, None,         [],        4),
    ("CONTENEDOR BASURA", "no_operativa", False, False, None,        [],        4),
]

# PERSONAS REALES, con su numero de empleado real. Antes esta lista eran
# nombres inventados -- "Luis Barrera Soto", "Ana Villalobos Rey" -- que no
# existen en ningun archivo del cliente. Peor todavia: parecian reales, asi que
# nadie los cuestionaba al ver una pantalla.
#
# De donde sale cada uno:
#   925    AVALOS GOMEZ, ERICK          INFO CHOFERES/TALLER "SUP. DE MANT AUTOMOTRIZ"
#   10853  MONTAÑO LOPEZ, PEDRO         INFO CHOFERES/TALLER "MECANICO"
#   647    SALLAS MOLINA, VICTOR        INFO CHOFERES/TALLER "MECANICO AUTOMOTRIZ"
#   11807  REYES PABLO ARTURO           REQUIS 2026/EMPLEADO
#   4932   ESPEJO HERNANDEZ, RUBEN      INFO CHOFERES/TALLER "CHOFER DE GRUA"
#   13624  ESPINOZA HERRERA, JOSE R.    INFO CHOFERES/TALLER "CHOFER DE GRUA"
#   13924  MUÑIZ ESTRADA, RICARDO D.    INFO CHOFERES/TALLER "CHOFER GRUA"
#
# El correo sigue la MISMA convencion que usa el importador para la gente que
# saca del Excel -- e<num_empleado>@bajagas.mx -- para que no convivan dos
# formas de nombrar a la misma persona.
#
# Los CHOFERES no van aqui: el importador crea los 297 reales desde las hojas
# de flota. Sembrar choferes de mentira encima seria volver al problema.
#
# (nombre, apellidos, num_empleado, rol, password)
USUARIOS_REALES = [
    # PENDIENTE: Luis Tiscareno es el gerente y NO aparece en ningun archivo
    # entregado --ni en la hoja EMPLEADO de REQUIS, que son los 100 del taller,
    # ni en INFO CHOFERES--. El nombre es real; falta su numero de empleado.
    # Mientras tanto entra por gerente@bajagas.mx.
    ("Luis",   "Tiscareno",              None,   "gerente",        "bajagas2026"),
    ("Erick",  "Avalos Gomez",           925,    "administrador",  "bajagas2026"),
    ("Pedro",  "Montano Lopez",          10853,  "administrador",  "bajagas2026"),
    ("Victor", "Sallas Molina",          647,    "administrador",  "bajagas2026"),
    ("Pablo",  "Reyes Arturo",           11807,  "administrador",  "bajagas2026"),
    # CAPTURISTA DE DATOS de Alamos, hoja TALLER de "INFO CHOFERES 2026".
    # Es quien teclea el libro REQUIS todos los dias; el puesto viene escrito
    # con ese nombre en el archivo, no es una etiqueta que inventamos.
    ("Jaime Yair", "Dominguez Sanchez",  13905,  "capturista",     "bajagas2026"),
    ("Ruben",  "Espejo Hernandez",       4932,   "chofer_grua",    "bajagas2026"),
    ("Jose",   "Espinoza Herrera",       13624,  "chofer_grua",    "bajagas2026"),
    ("Ricardo", "Muniz Estrada",         13924,  "chofer_grua",    "bajagas2026"),
]


# Un rol por modulo de la aplicacion. El servidor los revalida en cada
# endpoint (RNF-04); esta lista es solo el catalogo que se siembra.
# "perito" entra con RN-16: un choque le avisa al perito desde el sistema, y
# sin el rol ese aviso no le llegaba a nadie. Edgar es del sindicato pero
# trabaja para Baja Gas -- actor INTERNO, con cuenta propia (nota 9 de la junta
# del 2026-09-14). Falta darle de alta su usuario; el rol ya existe para que el
# dia que se cree, el aviso funcione solo.
ROLES_DEL_SISTEMA = ["chofer", "supervisor", "administrador", "chofer_grua",
                     "gerente", "capturista", "perito"]

# La misma que usa el importador para la gente que saca del Excel.
PASSWORD_REAL = "bajagas2026"


def _correo(num_empleado, rol):
    """Misma convencion que el importador: e<num>@bajagas.mx.

    Quien todavia no tiene numero cae al correo por rol, y eso mismo sirve de
    senal de que falta el dato.
    """
    return f"e{num_empleado}@bajagas.mx" if num_empleado else f"{rol}@bajagas.mx"


# Lo que consume el resto del archivo. Se arma desde USUARIOS_REALES.
USUARIOS_DEMO = [(n, a, _correo(num, rol), rol, pwd)
                 for n, a, num, rol, pwd in USUARIOS_REALES]

# Los tecnicos NO son usuarios: no tienen correo ni contrasena (v1.1).
TECNICOS_DEMO = [
    ("Ramon", "Aguilar Mena",   "T-001", "mecanico"),
    ("Sergio", "Beltran Ruiz",  "T-002", "mecanico"),
    ("Hugo", "Carrillo Lopez",  "T-003", "carrocero"),
    ("Elias", "Duarte Fuentes", "T-004", "electricista"),
    ("Nestor", "Esparza Rios",  "T-005", "llantero"),
]

# --------------------------------------------------------------------------- #
# Tipos de servicio -- MEDIDOS, no puestos a ojo.
#
# Salen de "DETALLADO TALLER 2025.xlsx", el registro real del taller de Alamos.
# El analisis completo esta en docs/analisis-detallado-taller.md; aqui va el
# resultado. Dos bloques porque el taller tiene DOS flujos distintos y meterlos
# en la misma cuenta rompe el calculo de capacidad (ver TipoServicio).
#
#   ESTANCIA -> 869 reparaciones cerradas entre 2025-01 y 2026-08. La duracion
#               es la MEDIANA de las visitas de un solo trabajo; el p90 marca
#               la cola, que es enorme y es lo que hace inutil el promedio.
#   PASO     -> 645 servicios de julio 2026 que entran y salen el mismo dia.
#               Ahi `muestras` es cuantas veces se observo, no una duracion.
#
# ADVERTENCIA que hay que respetar al leer estos numeros: lo medido es
# PERMANENCIA (ingreso -> reparado), no ocupacion de bahia. Incluye la espera
# por refacciones y por autorizacion. Sirve para prometerle una fecha al chofer;
# para capacidad de espacios habra que esperar a que OcupacionEspacio acumule
# historia propia y entonces `recalibrar()` corrige solo.
#
# Los nombres son provisionales: hay que ponerselos enfrente a Pedro para que
# los corrija. El 24% de las fallas cayo en "Otros", asi que falta detalle.
# (nombre, criticidad, mediana, p90, muestras, requiere_fosa)
TIPOS_SERVICIO_ESTANCIA = [
    ("Motor",                    1,  22, 116, 224, True),
    ("Sistema electrico",        1,   8,  79,  70, False),
    ("Otros",                    2,   8,  50,  73, False),
    ("Transmision",              2,  11, 222,  39, True),
    ("Clutch",                   2,   3,  45,  35, False),
    ("Frenos",                   1,   3,  24,  22, False),
    ("Enfriamiento",             1,   5,  37,  19, False),
    ("Suspension y direccion",   1,   7,  17,  17, True),
    ("Combustible",              1,   9,  34,  17, False),
    ("Aire y freno neumatico",   1,  14,  70,  12, False),
    ("Diagnostico / revision",   2,  42, 258,  12, False),
    ("Carroceria",               3,   6,  62,   8, False),
    ("Servicio preventivo",      1,   8, 115,   7, False),
    ("Escape y turbo",           2,   1,  50,   5, False),
    ("Llantas",                  1,  10,  20,   5, False),
    ("Hidraulico",               2,   4,   6,   4, False),
]

# (nombre, criticidad, veces observado en un mes)
TIPOS_SERVICIO_PASO = [
    ("Niveles",                  1, 244),
    ("Ajuste de frenos",         1,  31),
    ("Luces",                    1,  26),
    ("Rotacion de baterias",     1,  26),
    ("Cambio de llantas",        1,  13),
    ("Ajuste de clutch",         2,  13),
]


def asegurar_tipos_servicio(db: Session) -> dict:
    """Carga el catalogo de servicios si falta. Se puede correr N veces.

    Va aparte de `sembrar()` a proposito: `sembrar()` se rinde entero si la
    base ya tiene roles, y este catalogo tiene que poder llegarle tambien a una
    base que ya existia. Mismo patron que `asegurar_plantas()`.

    No pisa lo que ya este cargado. Si Pedro corrigio un nombre o una duracion
    a mano, un reinicio del servidor no debe borrarle la correccion.
    """
    hecho = {"creados": 0, "existentes": 0}
    for nombre, crit, mediana, p90, muestras, fosa in TIPOS_SERVICIO_ESTANCIA:
        if db.query(m.TipoServicio).filter_by(nombre=nombre).first():
            hecho["existentes"] += 1
            continue
        db.add(m.TipoServicio(
            nombre=nombre, criticidad=crit,
            # El estimado inicial ES la mediana medida: no hay razon para
            # arrancar con una adivinanza teniendo el dato real.
            duracion_estimada_dias=mediana,
            duracion_mediana_dias=float(mediana),
            duracion_p90_dias=p90,
            muestras_medidas=muestras,
            ocupa_espacio=True,
            origen_duracion="medido:REPARADO 2025-2026",
            requiere_fosa=fosa))
        hecho["creados"] += 1

    for nombre, crit, veces in TIPOS_SERVICIO_PASO:
        if db.query(m.TipoServicio).filter_by(nombre=nombre).first():
            hecho["existentes"] += 1
            continue
        db.add(m.TipoServicio(
            nombre=nombre, criticidad=crit,
            duracion_estimada_dias=0,
            duracion_mediana_dias=0.0,
            duracion_p90_dias=0,
            muestras_medidas=veces,
            ocupa_espacio=False,
            origen_duracion="medido:IN-OUT 2026-07",
            requiere_fosa=False))
        hecho["creados"] += 1

    db.flush()

    # Los planes que existian ANTES de que el catalogo existiera se quedaron con
    # tipo_servicio_id en NULL: `asegurar_columnas` agrega la columna pero no la
    # rellena. Sin esto la agenda no sabe cuanto dura ni que tan critico es lo
    # que va a agendar, y cae al valor por omision -- un dia, criticidad media --
    # que es justo la adivinanza que el catalogo medido vino a eliminar.
    preventivo = db.query(m.TipoServicio).filter_by(nombre="Servicio preventivo").first()
    if preventivo:
        huerfanos = (db.query(m.PlanMantenimiento)
                     .filter(m.PlanMantenimiento.tipo_servicio_id.is_(None)).all())
        for p in huerfanos:
            p.tipo_servicio_id = preventivo.id
        hecho["planes_enlazados"] = len(huerfanos)

    db.commit()
    return hecho


# Que zonas admiten una unidad aunque no sean capacidad de reparacion, y con
# que prefijo se etiquetan sus casillas. Es la tabla que usa la migracion para
# arreglar una base que ya existia.
ZONAS_ESTACIONAMIENTO = {"FOSA": "F", "PATIO": "P", "AREA LAVADO": "W"}
# El yonke esta aqui y no en ZONAS_ESTACIONAMIENTO porque ahi solo hay piezas
# y partes: no se estaciona un vehiculo en el yonke.
ZONAS_SIN_UNIDADES = {"OFICINA", "CONTENEDOR BASURA", "YONKE"}
PREFIJO_POR_ZONA = {
    "REPARTO NORTE": "T", "PIPAS": "T", "LLANTERA": "L",
    "ELECTRICOS": "I", "UTILITARIOS": "I", "REPARTO SUR": "I", "TALLER": "T",
    **ZONAS_ESTACIONAMIENTO,
}


# Las cuentas inventadas que llegaron a existir, y a quien corresponden de
# verdad. Se RECONCILIAN en vez de crear una segunda: si se agregara `e925@`
# junto al viejo `erick@`, habria dos Ericks y el trabajo hecho con el primero
# quedaria colgado de una cuenta fantasma.
#   correo viejo  ->  correo real (None = no corresponde a nadie, se desactiva)
RECONCILIAR = {
    "gerente@bajagas.mx":      "gerente@bajagas.mx",   # se queda; cambia la persona
    "erick@bajagas.mx":        "e925@bajagas.mx",
    "pedro@bajagas.mx":        "e10853@bajagas.mx",
    "victor@bajagas.mx":       "e647@bajagas.mx",
    "pablo@bajagas.mx":        "e11807@bajagas.mx",
    "montacargas@bajagas.mx":  "e4932@bajagas.mx",
    "montacargas2@bajagas.mx": "e13624@bajagas.mx",
    "admin@bajagas.mx":        None,                   # generico, no es nadie
    "supervisor@bajagas.mx":   None,
    "supervisor2@bajagas.mx":  None,
    "chofer1@bajagas.mx":      None,
    "chofer2@bajagas.mx":      None,
    "chofer3@bajagas.mx":      None,
    "chofer4@bajagas.mx":      None,
    "chofer5@bajagas.mx":      None,
    "chofer6@bajagas.mx":      None,
    "chofer7@bajagas.mx":      None,
}


def reconciliar_cuentas(db: Session) -> dict:
    """Convierte las cuentas inventadas en las reales. Idempotente.

    NO borra usuarios: hay bitacora, notificaciones y citas colgando de ellos, y
    borrarlos dejaria huerfano ese historial. Los que no corresponden a nadie se
    desactivan --dejan de poder entrar-- y los que si, se renombran al correo y
    nombre reales conservando su id y todo lo que hicieron.
    """
    hecho = {"renombradas": 0, "desactivadas": 0}
    real_por_correo = {c: (n, a, num, rol)
                       for (n, a, num, rol, _), c in
                       ((r, _correo(r[2], r[3])) for r in USUARIOS_REALES)}

    for viejo, nuevo in RECONCILIAR.items():
        u = db.query(m.Usuario).filter(m.Usuario.email == viejo).first()
        if not u:
            continue
        if nuevo is None:
            if u.activo:
                u.activo = False
                hecho["desactivadas"] += 1
            continue
        datos = real_por_correo.get(nuevo)
        if not datos:
            continue
        # Si el correo real ya lo tiene OTRO usuario, este viejo sobra.
        choque = db.query(m.Usuario).filter(m.Usuario.email == nuevo,
                                            m.Usuario.id != u.id).first()
        if choque:
            u.activo = False
            hecho["desactivadas"] += 1
            continue
        nombre, apellidos, _num, _rol = datos
        cambio_correo = u.email != nuevo
        if cambio_correo or u.nombre != nombre or u.apellidos != apellidos:
            u.email, u.nombre, u.apellidos = nuevo, nombre, apellidos
            u.activo = True
            if cambio_correo:
                # SOLO cuando cambia el CORREO. La cuenta vieja se creo con la
                # clave de demo; si se le mueve el correo sin reponerla, queda
                # con correo nuevo y clave vieja y no entra.
                #
                # Corregir la ortografia de un apellido NO es razon para esto, y
                # que lo fuera costo caro: el 2026-09-15 se corrigio Siscareno
                # por Tiscareno en USUARIOS_REALES, y el siguiente arranque le
                # devolvio al GERENTE la clave publicada en este archivo. Nadie
                # se entero hasta que el gerente no pudo entrar con la suya.
                u.password_hash = hash_password(PASSWORD_REAL)
                hecho["claves_repuestas"] = hecho.get("claves_repuestas", 0) + 1
            hecho["renombradas"] += 1
    db.commit()
    return hecho


def asegurar_roles(db: Session) -> dict:
    """Crea los roles que falten. Se puede correr N veces.

    Hace falta aparte de `sembrar()` porque sembrar se rinde entero si la base
    ya tiene roles. Sin esto, un rol nuevo --capturista-- no le llegaba nunca a
    una base existente, y su cuenta se saltaba en silencio en
    `asegurar_usuarios_demo` porque el rol no estaba en el catalogo.
    """
    hecho = {"creados": 0, "existentes": 0}

    ya = {r.nombre for r in db.query(m.Rol).all()}
    for nombre in ROLES_DEL_SISTEMA:
        if nombre in ya:
            hecho["existentes"] += 1
            continue
        db.add(m.Rol(nombre=nombre, descripcion=f"Modulo {nombre}"))
        hecho["creados"] += 1
    db.commit()
    return hecho


def asegurar_usuarios_demo(db: Session) -> dict:
    """Crea las cuentas de prueba que falten. Se puede correr N veces.

    Va aparte de `sembrar()` por la misma razon que el catalogo de servicios:
    `sembrar()` se rinde entero si la base ya tiene roles, asi que agregar una
    cuenta nueva no le llegaba nunca a una base existente. Es justo lo que paso
    al ampliar el elenco de prueba.

    Solo AGREGA. No toca contrasenas ni roles de quien ya existe: si alguien
    cambio algo a mano, se respeta.
    """
    hecho = {"usuarios": 0, "choferes": 0, "choferes_grua": 0}
    roles = {r.nombre: r for r in db.query(m.Rol).all()}
    if not roles:
        return hecho          # base vacia: de esto se encarga sembrar()

    plantilla = db.query(m.Plantilla).first()
    for nombre, apellidos, email, rol, pwd in USUARIOS_DEMO:
        if db.query(m.Usuario).filter(m.Usuario.email == email).first():
            continue
        if rol not in roles:
            continue
        u = m.Usuario(nombre=nombre, apellidos=apellidos, email=email,
                      telefono="664-000-0000", password_hash=hash_password(pwd))
        db.add(u)
        db.flush()
        db.add(m.UsuarioRol(usuario_id=u.id, rol_id=roles[rol].id))
        hecho["usuarios"] += 1

        # El perfil que cuelga del usuario segun su rol. Sin el, un chofer
        # nuevo entra al sistema pero no tiene unidad ni aparece en plantilla.
        if rol == "chofer":
            db.add(m.Chofer(usuario_id=u.id, num_licencia=f"LIC-{u.id:04d}",
                            tipo_licencia="E",
                            vencimiento_licencia=date.today() + timedelta(days=365),
                            plantilla_id=plantilla.id if plantilla else None))
            hecho["choferes"] += 1
        elif rol == "chofer_grua":
            db.add(m.ChoferGrua(usuario_id=u.id, licencia_especial=f"ME-{u.id:04d}"))
            hecho["choferes_grua"] += 1
    db.commit()
    return hecho


def asegurar_plano(db: Session) -> dict:
    """Pone al dia el plano de una base que ya existia. Idempotente.

    Hace dos cosas que `create_all` y el sembrado no pueden:

    1. **Rellena `admite_unidades`.** La columna nace en `true` por defecto, asi
       que sin esto la oficina y el contenedor de basura quedarian aceptando
       unidades. Se deduce del nombre de la zona.

    2. **Renombra las casillas al patron por fila** -- T-01, I-07, P-03 -- que
       es como se orienta quien esta parado en el patio. Solo toca las que
       siguen con la numeracion vieja (un "1" pelon que se repite en cuatro
       zonas y no le dice nada a nadie).

    3. **Cuadra CUANTAS casillas tiene cada zona de Alamos** contra
       `LAYOUT_TALLER`, que es el croquis del cliente. Una base previa traia el
       patio con 45 lugares y el yonke con 1 -- cruzados respecto al Excel, que
       dice 12 y 45. Mientras el plano era una lista de zonas nadie lo noto; al
       dibujar el croquis salta a la vista.

       Se agrega lo que falta y se quita lo que sobra SOLO si esta libre. Una
       casilla de mas con una unidad adentro se deja y se reporta: borrarla
       dejaria huerfana una ocupacion abierta, que es peor que el desfase.
    """
    hecho = {"zonas_ajustadas": 0, "espacios_renombrados": 0,
             "casillas_agregadas": 0, "casillas_retiradas": 0, "no_se_pudo": []}
    for z in db.query(m.ZonaTaller).all():
        nombre = (z.nombre or "").upper()

        admite = nombre not in ZONAS_SIN_UNIDADES
        if bool(z.admite_unidades) != admite:
            z.admite_unidades = admite
            hecho["zonas_ajustadas"] += 1

        prefijo = PREFIJO_POR_ZONA.get(nombre)
        if not prefijo:
            continue
        for e in z.espacios:
            # Ya tiene el patron nuevo: no se toca.
            if e.numero and "-" in e.numero:
                continue
            base = "".join(ch for ch in (e.numero or "") if ch.isdigit())
            if not base:
                continue
            nuevo = "%s-%02d" % (prefijo, int(base))
            # La unicidad es (zona, numero): si ya existe, se deja como estaba
            # en vez de reventar el arranque.
            if any(o.numero == nuevo for o in z.espacios if o.id != e.id):
                continue
            e.numero = nuevo
            hecho["espacios_renombrados"] += 1

    # --- 3. el conteo del croquis, solo en el taller central --------------- #
    central = db.query(m.Taller).filter(m.Taller.tipo == "CENTRAL").first()
    if central:
        tipos = {x.nombre: x for x in db.query(m.TipoUnidad).all()}
        zonas = {(z.nombre or "").upper(): z
                 for z in db.query(m.ZonaTaller)
                 .filter(m.ZonaTaller.taller_id == central.id).all()}
        for zn, _prop, _adm, _cta, tperm, numeros, fila in LAYOUT_TALLER:
            z = zonas.get(zn.upper())
            # OJO: se sigue aunque `numeros` este vacio. Una lista vacia no es
            # "no se sabe", es "esta zona NO tiene cajones" -- el yonke guarda
            # piezas, no vehiculos. Saltarla aqui dejaba sus 45 casillas viejas
            # intactas y el croquis seguia ofreciendo estacionar en el yonke.
            if not z:
                continue
            actuales = {e.numero: e for e in z.espacios}
            for i, num in enumerate(numeros):
                if num in actuales:
                    continue
                db.add(m.Espacio(zona_id=z.id, numero=num, pos_x=i, pos_y=fila,
                                 tipo_unidad_permitido_id=(tipos[tperm].id
                                                           if tperm and tperm in tipos
                                                           else None)))
                hecho["casillas_agregadas"] += 1
            for num, e in actuales.items():
                if num in numeros:
                    continue
                ocupada = (db.query(m.OcupacionEspacio)
                           .filter(m.OcupacionEspacio.espacio_id == e.id,
                                   m.OcupacionEspacio.fecha_salida.is_(None)).first())
                if ocupada or e.estado != "libre":
                    hecho["no_se_pudo"].append(f"{zn} {num}: ocupada")
                    continue
                db.delete(e)
                hecho["casillas_retiradas"] += 1
            z.capacidad = len(numeros)

    db.commit()
    return hecho


def asegurar_plantas(db: Session) -> dict:
    """Crea las plantas y sus talleres si faltan. Se puede correr N veces.

    Sirve para migrar una base que ya existia: el prototipo v1.1 tenia un solo
    taller sin planta. Ese taller ES Alamos, asi que se adopta en vez de crear
    uno nuevo, y con eso se conserva su plano (zonas y espacios ya cargados).
    """
    creadas = {"plantas": 0, "talleres": 0, "espacios": 0, "adoptado": None}

    for clave, nombre, central, con_taller, lat, lng in PLANTAS:
        pl = db.query(m.Planta).filter(m.Planta.clave == clave).first()
        if not pl:
            pl = m.Planta(clave=clave, nombre=nombre, es_central=central,
                          tiene_taller=con_taller, latitud=lat, longitud=lng,
                          direccion=f"Planta {nombre}, Baja California")
            db.add(pl)
            db.flush()
            creadas["plantas"] += 1
        if not con_taller:
            continue

        t = db.query(m.Taller).filter(m.Taller.planta_id == pl.id).first()
        if not t and central:
            # El taller huerfano del prototipo v1.1 es Alamos: se adopta con
            # todo y su plano en vez de duplicarlo.
            t = (db.query(m.Taller)
                 .filter(m.Taller.planta_id.is_(None))
                 .order_by(m.Taller.id).first())
            if t:
                creadas["adoptado"] = t.nombre
                t.planta_id = pl.id
                t.nombre = nombre
        if not t:
            t = m.Taller(planta_id=pl.id, nombre=nombre, direccion=pl.direccion,
                         latitud=lat, longitud=lng)
            db.add(t)
            db.flush()
            creadas["talleres"] += 1
        t.tipo = "CENTRAL" if central else "SATELITE"

        # Zonas y espacios: solo si el taller no tiene ninguno todavia.
        if db.query(m.ZonaTaller).filter(m.ZonaTaller.taller_id == t.id).count():
            continue
        if central:
            tipos = {x.nombre: x for x in db.query(m.TipoUnidad).all()}
            for orden, (zn, prop, admite, cuenta, tperm, numeros, fila) in enumerate(LAYOUT_TALLER):
                z = m.ZonaTaller(taller_id=t.id, nombre=zn, proposito=prop,
                                 capacidad=len(numeros), admite_unidades=admite,
                                 cuenta_para_ocupacion=cuenta, orden=orden)
                db.add(z)
                db.flush()
                for i, num in enumerate(numeros):
                    db.add(m.Espacio(zona_id=z.id, numero=num, pos_x=i, pos_y=fila,
                                     tipo_unidad_permitido_id=(tipos[tperm].id
                                                               if tperm and tperm in tipos
                                                               else None)))
                    creadas["espacios"] += 1
        else:
            n = ESPACIOS_SATELITE.get(clave, 2)
            z = m.ZonaTaller(taller_id=t.id, nombre="TALLER", proposito="operativa",
                             capacidad=n, cuenta_para_ocupacion=True, orden=0)
            db.add(z)
            db.flush()
            for i in range(1, n + 1):
                db.add(m.Espacio(zona_id=z.id, numero="T-%02d" % i, pos_x=i - 1, pos_y=0))
                creadas["espacios"] += 1

    db.commit()
    return creadas


def sembrar(db: Session):
    if db.query(m.Rol).count() > 0:
        return "La base ya tenia datos; no se volvio a sembrar."

    # ------------------------------------------------------------- roles ---- #
    roles = {}
    for nombre in ROLES_DEL_SISTEMA:
        r = m.Rol(nombre=nombre, descripcion=f"Modulo {nombre}")
        db.add(r)
        roles[nombre] = r
    db.flush()

    # ------------------------------------------------------- tipos unidad --- #
    tipos = {}
    # La prioridad operativa es el desempate #4 de la cola de la agenda: una
    # pipa parada cuesta mas que un utilitario parado. Menor = entra antes.
    # Propuesta en agenda-mantenimiento.md §4.3, PENDIENTE de confirmar con el
    # gerente -- es un juicio de negocio, no una decision tecnica.
    for nombre, prioridad in [("pipa", 1), ("reparto", 2), ("utilitario", 3),
                              ("montacargas", 4)]:
        t = m.TipoUnidad(nombre=nombre, descripcion=f"Unidad tipo {nombre}",
                         prioridad_operativa=prioridad)
        db.add(t)
        tipos[nombre] = t
    db.flush()

    # ---------------------------------------------------------- usuarios ---- #
    usuarios = {}
    for nombre, apellidos, email, rol, pwd in USUARIOS_DEMO:
        u = m.Usuario(nombre=nombre, apellidos=apellidos, email=email,
                      telefono="664-000-0000", password_hash=hash_password(pwd))
        db.add(u)
        db.flush()
        db.add(m.UsuarioRol(usuario_id=u.id, rol_id=roles[rol].id))
        usuarios[email] = (u, rol)
    db.flush()

    # Por ROL, no por correo fijo: los correos ahora salen del numero de
    # empleado real y cambian con la persona.
    def _primero(rol):
        return next((u for u, r in usuarios.values() if r == rol), None)

    plantilla = None
    u_sup = _primero("supervisor")
    if u_sup:
        sup = m.Supervisor(usuario_id=u_sup.id, zona="Tijuana Centro")
        db.add(sup)
        db.flush()
        plantilla = m.Plantilla(nombre="Plantilla Centro", supervisor_id=sup.usuario_id)
        db.add(plantilla)
        db.flush()

    # Los CHOFERES ya no se siembran: los 297 reales los crea el importador
    # desde las hojas de flota, con su numero de empleado y su unidad. Inventar
    # choferes encima fue lo que produjo a "Luis Barrera Soto" y compania.
    choferes = [c for c in db.query(m.Chofer).all()]

    # --------------------------------------------- plantas y talleres (v2.0) -- #
    # El taller toma el nombre de su planta. LIBERTAD es sucursal pero NO tiene
    # taller: sus unidades se atienden en Alamos (confirmado con el cliente).
    plantas_creadas, talleres = {}, {}
    for clave, nombre, central, con_taller, lat, lng in PLANTAS:
        pl = m.Planta(clave=clave, nombre=nombre, es_central=central,
                      tiene_taller=con_taller, latitud=lat, longitud=lng,
                      direccion=f"Planta {nombre}, Baja California")
        db.add(pl)
        db.flush()
        plantas_creadas[clave] = pl
        if not con_taller:
            continue
        t = m.Taller(planta_id=pl.id, nombre=nombre,
                     tipo="CENTRAL" if central else "SATELITE",
                     direccion=pl.direccion, latitud=lat, longitud=lng)
        db.add(t)
        db.flush()
        talleres[clave] = t

    taller = talleres["ALAMOS"]  # el central: conserva el plano completo

    # El plano detallado (del Excel) es el de Alamos.
    for orden, (nombre, proposito, admite, cuenta, tipo_perm, numeros, fila) in enumerate(LAYOUT_TALLER):
        z = m.ZonaTaller(taller_id=taller.id, nombre=nombre, proposito=proposito,
                         capacidad=len(numeros), admite_unidades=admite,
                         cuenta_para_ocupacion=cuenta, orden=orden)
        db.add(z)
        db.flush()
        for i, num in enumerate(numeros):
            db.add(m.Espacio(zona_id=z.id, numero=num,
                             tipo_unidad_permitido_id=tipos[tipo_perm].id if tipo_perm else None,
                             pos_x=i, pos_y=fila))

    # Las satelites son chicas: una sola zona operativa con sus cajones.
    for clave, n_espacios in ESPACIOS_SATELITE.items():
        ts = talleres[clave]
        z = m.ZonaTaller(taller_id=ts.id, nombre="TALLER", proposito="operativa",
                         capacidad=n_espacios, cuenta_para_ocupacion=True, orden=0)
        db.add(z)
        db.flush()
        for i in range(1, n_espacios + 1):  # mismo patron: T-01, T-02...
            db.add(m.Espacio(zona_id=z.id, numero="T-%02d" % i, pos_x=i - 1, pos_y=0))
    db.flush()

    # ---------------------------------------------------------- tecnicos ---- #
    tecnicos = []
    for nombre, apellidos, num, esp in TECNICOS_DEMO:
        t = m.Tecnico(nombre=nombre, apellidos=apellidos, num_empleado=num, especialidad=esp,
                      taller_id=taller.id, telefono="664-111-2233")
        db.add(t)
        tecnicos.append(t)
    db.flush()

    # ----------------------------------------------------------- unidades --- #
    unidades = []
    # Suficientes para que el plano, la agenda y la cola de trabajo tengan algo
    # que ensenar. Los nombres y marcas imitan los del catalogo real.
    datos_unidades = [
        ("U-101", "AB-123-CD", "reparto",    "Isuzu",     "NPR",      2021, 148_500),
        ("U-102", "AB-456-CD", "reparto",    "Isuzu",     "NPR",      2020, 210_300),
        ("U-103", "AB-789-CD", "reparto",    "CNJ",       "4T",       2020, 132_700),
        ("U-104", "AB-012-CD", "reparto",    "CNJ",       "4T",       2019, 198_400),
        ("U-105", "AB-345-CD", "reparto",    "Changan",   "SC1021",   2018, 240_100),
        ("U-106", "AB-678-CD", "reparto",    "CNJ",       "2T",       2021,  92_600),
        ("U-201", "PP-789-AA", "pipa",       "Kenworth",  "T370",     2019, 305_800),
        ("U-202", "PP-012-AA", "pipa",       "CNJ",       "7T",       2019, 288_300),
        ("U-203", "PP-345-AA", "pipa",       "Freightliner", "M2",    2017, 412_900),
        ("U-204", "PP-678-AA", "pipa",       "CNJ",       "7T",       2020, 176_500),
        ("U-301", "UT-321-BB", "utilitario", "Nissan",    "NP300",    2022,  61_200),
        ("U-302", "UT-654-BB", "utilitario", "Chevrolet", "Spark",    2017, 154_800),
        ("U-303", "UT-987-BB", "utilitario", "Chevrolet", "Beat",     2018, 121_300),
        ("U-304", "UT-210-BB", "utilitario", "Nissan",    "NP300",    2019, 187_600),
    ]
    for i, (eco, placas, tipo, marca, modelo, anio, km) in enumerate(datos_unidades):
        titular = choferes[i].usuario_id if i < len(choferes) else None
        u = m.Unidad(num_economico=eco, placas=placas, vin=f"VIN{eco}0000000",
                     marca=marca, modelo=modelo, anio=anio, tipo_unidad_id=tipos[tipo].id,
                     titular_chofer_id=titular, poseedor_chofer_id=titular,
                     km_actual=km, fecha_alta=date(anio, 1, 15))
        db.add(u)
        unidades.append(u)
    db.flush()

    # Los tres choferes de grua reales, no uno de mentira.
    for u, rol in usuarios.values():
        if rol == "chofer_grua":
            db.add(m.ChoferGrua(usuario_id=u.id,
                                    licencia_especial=f"ME-{u.id:04d}"))

    # ------------------------------------------------------ mantenimiento --- #
    # El plan apunta al tipo de servicio: de ahi saca la agenda la duracion y
    # la criticidad con las que ordena su cola.
    preventivo = db.query(m.TipoServicio).filter_by(nombre="Servicio preventivo").first()
    planes = {}
    for tipo_nombre, dias, km in [("reparto", 90, 10_000), ("pipa", 60, 8_000),
                                  ("utilitario", 120, 12_000)]:
        p = m.PlanMantenimiento(tipo_unidad_id=tipos[tipo_nombre].id,
                                nombre=f"Servicio preventivo {tipo_nombre}",
                                tipo_servicio_id=preventivo.id if preventivo else None,
                                periodicidad_dias=dias, periodicidad_km=km,
                                descripcion="Aceite, filtros, frenos, suspension")
        db.add(p)
        planes[tipo_nombre] = p
    db.flush()

    # U-101 con mantenimiento VENCIDO: dispara penalizacion al correr el job.
    # U-102 por vencer, U-201 al corriente. Asi el demo muestra los tres casos.
    desfases = [-12, 5, 40, 75]
    for u, desfase in zip(unidades, desfases):
        plan = planes.get(u.tipo.nombre)
        if not plan:
            continue
        db.add(m.ProgramaMantenimiento(
            unidad_id=u.id, plan_id=plan.id,
            fecha_programada=date.today() + timedelta(days=desfase),
            km_programado=u.km_actual + 5_000,
            fecha_limite=date.today() + timedelta(days=desfase), estado="pendiente"))

    # ------------------------------------------------------------ piezas ---- #
    for sku, nombre, precio, stock in [
            ("FLT-001", "Filtro de aceite", 320, 24),
            ("FLT-002", "Filtro de aire", 480, 12),
            ("BAL-010", "Balatas delanteras (juego)", 1850, 6),
            ("AMO-020", "Amortiguador trasero", 2400, 4),
            ("BAT-030", "Bateria 12V 900CCA", 3900, 3),
            ("LLA-040", "Llanta 11R22.5", 5600, 8)]:
        db.add(m.Pieza(sku=sku, nombre=nombre, precio_referencia=precio, stock_actual=stock,
                       stock_minimo=2))

    db.add(m.Proveedor(nombre="Refaccionaria del Pacifico", rfc="RPA010101AAA",
                       contacto="Marisol Ibarra", telefono="664-555-1010"))

    # -------------------------------------------------------- parametros ---- #
    for clave, valor, desc in [
            ("meses_unidad_parada", "3", "RN-08: meses para alertar unidad parada"),
            ("dias_tolerancia_penalizacion", "0", "RN-05: dias de gracia antes de penalizar"),
            ("horas_max_captura", "2", "Ventana acordada para capturar el trabajo del mecanico")]:
        db.add(m.Configuracion(clave=clave, valor=valor, descripcion=desc))

    db.commit()
    return "Datos semilla creados."


def asegurar_reportes_de_ordenes_abiertas(db: Session) -> str:
    """Le levanta el formato a las unidades que YA estaban adentro.

    Desde v1.3 el reporte nace al aceptar el ingreso, pero las ordenes abiertas
    de antes no tienen ninguno. Sin esto, Pedro toca cualquier casilla ocupada y
    le sale «esta unidad no tiene formato» para todo el taller -- que es justo
    lo contrario de para lo que sirve la pantalla.

    Es idempotente y solo mira ordenes SIN salida: correrlo dos veces no crea
    nada, y una orden ya cerrada no necesita formato retroactivo.
    """
    from . import services as svc

    abiertas = (db.query(m.OrdenServicio)
                .filter(m.OrdenServicio.fecha_salida.is_(None)).all())
    if not abiertas:
        return "sin ordenes abiertas"

    # Quien lo "capturo": el administrador que abrio la orden. Inventar un
    # usuario para esto ensuciaria la trazabilidad; si la orden no lo trae, el
    # campo se queda vacio y el formato dice la verdad -- que nadie lo tecleo.
    creados = cerradas = 0
    for o in abiertas:
        de_la_orden = (db.query(m.ReporteMantenimiento)
                       .filter(m.ReporteMantenimiento.orden_servicio_id == o.id).first())
        if de_la_orden and de_la_orden.estado == "cerrado":
            # SALIDA A MEDIAS. Hasta v1.3 cerrar el formato y cerrar la orden
            # eran dos botones distintos: quien hacia solo el primero dejaba la
            # unidad con el formato sellado pero la orden viva, y en el plano
            # seguia apareciendo dentro del taller. Ahora es un solo acto; aqui
            # se terminan de cerrar las que quedaron partidas.
            svc.sacar_del_taller(db, o, de_la_orden.cerrado_por_admin_id,
                                 unidad_operativa=True,
                                 operacion_a_realizar="Salida completada al migrar a v1.3")
            o.fecha_salida = de_la_orden.fecha_salida or o.fecha_salida
            cerradas += 1
            continue
        if de_la_orden or svc.reporte_abierto_de_unidad(db, o.unidad_id):
            continue
        svc.crear_reporte_mantenimiento(
            db, unidad=o.unidad, taller_id=o.taller_id,
            admin_id=o.abierta_por_admin_id, orden=o,
            tipo_servicio="preventivo" if o.tipo == "preventivo" else "correctivo",
            origen=o.taller.nombre if o.taller else None,
            chofer_id=o.chofer_responsable_id,
            kilometraje=o.km_entrada,
            fecha_entrada=o.fecha_entrada,
            notas_ingreso="Formato generado al migrar a v1.3 para una orden que "
                          "ya estaba abierta. La revision de ingreso no se capturo.")
        creados += 1
    db.commit()
    return (f"{creados} formato(s) creado(s) para ordenes abiertas; "
            f"{cerradas} salida(s) a medias completada(s)")


def inicializar():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        return sembrar(db)
    finally:
        db.close()


if __name__ == "__main__":
    print(inicializar())


# --------------------------------------------------------------------------- #
# Parametros de operacion
# --------------------------------------------------------------------------- #
# Mismo patron que asegurar_tipos_servicio(): `sembrar()` se rinde entero si la
# base ya tiene datos, asi que los parametros NUEVOS nunca le llegarian a una
# base que ya existia -- y el indicador de la meta leeria su valor por omision
# en vez del que el cliente acordo.
PARAMETROS = [
    ("meta_preventivos_min", "5",
     "RN-12: piso de unidades en preventivo por dia. Por debajo, incumple el TALLER"),
    ("meta_preventivos_max", "7",
     "RN-12: techo de unidades en preventivo por dia"),
]


def asegurar_parametros(db: Session) -> dict:
    """Agrega los parametros que falten. No pisa los que ya tienen valor.

    Si el cliente cambio la meta a mano, un reinicio no debe devolverla a 5-7.
    """
    hecho = {"creados": 0, "existentes": 0}
    for clave, valor, desc in PARAMETROS:
        if db.query(m.Configuracion).filter_by(clave=clave).first():
            hecho["existentes"] += 1
            continue
        db.add(m.Configuracion(clave=clave, valor=valor, descripcion=desc))
        hecho["creados"] += 1
    if hecho["creados"]:
        db.commit()
    return hecho
