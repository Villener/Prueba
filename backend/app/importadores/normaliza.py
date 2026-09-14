"""Las reglas para cruzar los Excel de las cuatro areas entre si.

Cada area escribe el mismo numero de unidad de forma distinta, y ese detalle
--que parece cosmetico-- decide si la importacion trae el 64% de los datos o el
98%. Las reglas de aqui salen de medir las 383 unidades de la base contra las
1279 del catalogo maestro, escalon por escalon:

    sin normalizar nada .................. 246 / 383  =  64.2 %
    + castear a texto, trim, mayusculas .. 364 / 383  =  95.0 %
    + quitar guiones, puntos y acentos ... 369 / 383  =  96.3 %
    + alias dirigido de la 'P' ........... 374 / 383  =  97.7 %   <- el techo

EL ESCALON QUE NADIE VE VENIR es el primero, y vale 31 de esos 33 puntos: el
catalogo guarda 797 de sus 1279 unidades como NUMERO ENTERO y la base las tiene
como TEXTO. Sin castear, '1002' != 1002 y el cruce se queda en 64%. No truena,
no avisa: simplemente no cruza, y el resultado sigue pareciendo plausible.

Las nueve que no cruzan ni con todo puesto no son un fallo de la regla: cinco
son basura de demo y cuatro son unidades reales que le faltan al catalogo.
"""
import re
import unicodedata

# Palabras que ocupan la columna de unidad pero NO son una unidad. Vienen de
# celdas donde el area anoto otra cosa: el puesto del ayudante, que el gasto fue
# del taller y no de un vehiculo, o relleno para fijar un rango con nombre.
NO_SON_UNIDAD = {
    "ZPRUEBAUNIDAD",  # fila de prueba que alguien dejo en el catalogo
    "NOBORRAR",       # barrera anti-borrado al pie de la hoja PATIO
    "AYTE",           # 'ayudante': un puesto, no un camion
    "TALLER",         # el gasto es del taller, no de una unidad
    "NA", "N/A", "#N/A",
    "EXTRA",
    "PIPABACKUP",
    "XX",             # relleno de los rangos con nombre de REQUIS
}


def clave_unidad(valor) -> str:
    """El numero de unidad reducido a una clave con la que se puede cruzar.

    Devuelve cadena vacia si la celda no contiene una unidad. Quien llame debe
    tratar el vacio como 'esta fila no habla de un vehiculo', no como error.
    """
    if valor is None:
        return ""

    # PASO 1 - El casteo, que es el que vale. openpyxl devuelve int para las
    # celdas numericas y a veces float (1002.0). str(1002.0) da '1002.0', que no
    # cruza con nada: hay que pasar por int primero.
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    t = str(valor).strip().upper()
    if not t:
        return ""

    # PASO 2 - Fuera los acentos. Aparecen en apodos ('MUÑIZ', 'AZUCENA').
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))

    # PASO 3 - Celdas con dos unidades pegadas: '330/BG108'. Se toma la primera
    # y se pierde la segunda a proposito; son 1 caso en los siete archivos y
    # adivinar cual de las dos vale seria peor que quedarse con la de la
    # izquierda, que es la que el area escribio primero.
    if "/" in t:
        t = t.split("/", 1)[0].strip()

    # PASO 4 - Fuera separadores. 'BG-670' -> 'BG670', 'T 823' -> 'T823',
    # 'RETRO 1' -> 'RETRO1'. Medido: no funde ninguna pareja del catalogo.
    t = re.sub(r"[\s\-\._]", "", t)

    if not t or t in NO_SON_UNIDAD:
        return ""
    return t


# NO se quita el prefijo alfabetico, y hay una prueba concreta de por que: el
# catalogo tiene la unidad '750' (Ford F150 de 1995) y el taller usa 'BG-750'
# (Kenworth 2015). Son dos vehiculos distintos; quitar el 'BG' los funde.
def resolver_unidad(clave: str, catalogo: dict):
    """Busca la clave en el catalogo probando las tres escrituras posibles.

    Devuelve (valor_del_catalogo, clave_encontrada) o (None, None).

    El sufijo 'P' de las pipas se resuelve con un alias DIRIGIDO en vez de
    recortarlo a lo bruto. Los dos dan el mismo 97.7% hoy, pero el recorte tiene
    una bomba de tiempo: el dia que Logistica de de alta una BG433 real, la
    funde en silencio con la BG433P que ya existe. El alias no puede, porque el
    intento (b) solo dispara cuando la forma sin P NO esta en el catalogo.

    Que hoy la P sea solo una variante de escritura esta medido: en las 1277
    claves del catalogo no existe ni una sola pareja X / XP.
    """
    if not clave:
        return None, None

    # (a) tal cual
    if clave in catalogo:
        return catalogo[clave], clave

    # (b) el area la escribio sin la P y el catalogo la tiene con P
    con_p = clave + "P"
    if con_p in catalogo:
        return catalogo[con_p], con_p

    # (c) el area la escribio con P y el catalogo la tiene sin P
    if clave.endswith("P"):
        sin_p = clave[:-1]
        if sin_p in catalogo:
            return catalogo[sin_p], sin_p

    return None, None


def num_empleado(valor):
    """El numero de empleado como entero, o None si la celda no lo trae.

    Hay celdas con el texto 'N/A' escrito a mano y otras con el numero guardado
    como texto. Las dos tienen que sobrevivir sin tumbar la importacion.
    """
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, int):
        return valor if valor > 0 else None
    t = str(valor).strip()
    if not t or not t.isdigit():
        return None
    n = int(t)
    return n if n > 0 else None


def texto(valor) -> str:
    """Texto limpio: sin espacios de sobra, sin dobles espacios internos.

    Casi todas las celdas de texto de los cuatro archivos traen espacios al
    final ('ALAMOS ' y 'ALAMOS' conviven como si fueran dos sucursales).
    """
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\s+", " ", str(valor)).strip()


def nombre_mas_completo(a: str, b: str) -> str:
    """De dos escrituras del mismo nombre, la que conserva mas informacion.

    SAP corta los nombres a exactamente 30 caracteres y les mete una coma
    ('FERREL ARMENTA, LUIS ANTONIO'), asi que la misma persona aparece dos veces
    escrita de dos formas. El numero de empleado es la llave; el nombre no.
    """
    a, b = texto(a), texto(b)
    if not a:
        return b
    if not b:
        return a
    # Un nombre de exactamente 30 caracteres es sospechoso de venir truncado.
    if len(a) == 30 and len(b) != 30:
        return b
    if len(b) == 30 and len(a) != 30:
        return a
    return a if len(a) >= len(b) else b


def anio(valor):
    """El anio modelo, o None. Hay celdas con 0, con 19999 y con 'KENWORT 2018'."""
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, int):
        return valor if 1950 <= valor <= 2100 else None
    encontrados = re.findall(r"(19[5-9]\d|20[0-9]\d)", str(valor))
    return int(encontrados[-1]) if encontrados else None


def placa(valor) -> str:
    """La matricula en mayusculas y sin espacios, o cadena vacia.

    Descarta la basura conocida del catalogo: 'PEN', 'A' y el numero 0. Una
    placa mexicana no baja de 6 caracteres.
    """
    t = texto(valor).upper().replace(" ", "")
    if len(t) < 6 or not any(c.isdigit() for c in t):
        return ""
    return t


def telefono(valor) -> str:
    """Un celular de 10 digitos, o cadena vacia.

    Solo 85 de las 198 filas del directorio traen un numero usable, y una trae
    VEINTE digitos: son dos telefonos pegados en la misma celda. Esa se descarta
    en vez de partirla, porque no hay forma de saber cual de los dos contesta.
    """
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    digitos = re.sub(r"\D", "", str(valor))
    # Con lada de pais: 52 664 374 3849
    if len(digitos) == 12 and digitos.startswith("52"):
        digitos = digitos[2:]
    if len(digitos) == 11 and digitos.startswith("1"):
        digitos = digitos[1:]
    return digitos if len(digitos) == 10 else ""


def turno(valor) -> str:
    """El turno en mayusculas. 'Matutino', 'MATUTINO ' y 'matutino' son uno."""
    t = texto(valor).upper()
    if not t:
        return ""
    t = t.replace(" ", "")
    if "MATUTINO" in t and "VESPERTINO" in t:
        return "MATUTINO-VESPERTINO"
    if "MATUTINO" in t:
        return "MATUTINO"
    if "VESPERTINO" in t:
        return "VESPERTINO"
    if "NOCTURNO" in t:
        return "NOCTURNO"
    return ""


def vin(valor) -> str:
    """El numero de serie del fabricante, o cadena vacia.

    Hay 21 celdas con un espacio metido en medio ('LSCAD13Y 0AE036247') y unas
    cuantas con un solo caracter ('-', '.').
    """
    t = texto(valor).upper().replace(" ", "")
    return t if len(t) >= 10 else ""
