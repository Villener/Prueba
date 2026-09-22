"""El Excel de los cuatro historiales del gerente.

POR QUE ESTE ARCHIVO ES TAN CORTO, que es lo primero que llama la atencion al
abrirlo. Porque no calcula nada. Pide la tabla ya armada a
historiales.tabla_para_excel(), pinta los encabezados y escribe las filas. Ni un
numero del archivo se vuelve a sacar aqui.

Esa regla ya esta escrita con todas sus letras en exportar_tablero.py y en
taller/exportar_resumen.py, y viene de un problema real del area: hoy tienen una
hoja Graficos que no cuadra con su hoja RESUMEN porque los numeros se copian de
una a otra a mano, y llevan meses sin notarlo. El dia que la pantalla del gerente
y este archivo calculen cada uno por su lado van a discrepar, y cuando eso pasa
el gerente deja de creerle a los dos -- no al que esta mal, a los dos.

EL FORMATO SE IMPORTA, NO SE COPIA. Los colores, las fuentes y los bordes salen
de taller/exportar_resumen.py igual que hace exportar_tablero.py. Son tres
archivos que la misma persona va a tener abiertos al mismo tiempo, y si cada uno
tuviera sus constantes bastaria con que alguien cambiara un azul en un lado para
que dejaran de parecer del mismo sistema.

LOS None SE ESCRIBEN COMO CELDA VACIA Y NO COMO CERO. openpyxl deja la celda en
blanco cuando se le pasa None, que es exactamente lo que tiene que quedar donde
no hubo base para calcular: sin ordenes cerradas no hay dias promedio, y sin
citas con desenlace no hay porcentaje de cumplimiento. Quien abra el archivo va a
graficar esa columna, y un cero inventado dentro de una grafica es
indistinguible de una medicion real.

EL RANGO VA ADENTRO DEL ARCHIVO Y NO SOLO EN EL NOMBRE. El .xlsx se reenvia por
correo y se lee meses despues, cuando ya nadie se acuerda de que fechas se
marcaron en la pantalla; un archivo sin su periodo escrito es el que termina
citado en una junta como si fuera del mes en curso.
"""
import datetime
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from . import historiales
# Los estilos se importan del Excel del taller en vez de copiarse. Ver la nota
# de arriba.
from ..taller.exportar_resumen import (_anchos, _borde,  # noqa: E402
                                       _encabezados, _hoja_titulo)

_sub = Font(name="Calibri", size=10, color="4A5A66")
_nota = Font(name="Calibri", size=9, italic=True, color="6B7A80")
_aviso = Font(name="Calibri", size=10, bold=True, color="8A4B08")

# Cuanto puede crecer y encoger una columna. El ancho se calcula del contenido
# real porque las cuatro dimensiones tienen columnas muy distintas --"TALLER"
# son doce letras y la lista de UNIDADES de un mecanico puede pasar de ochenta--
# pero sin tope una sola celda larga deja una columna que no cabe en la pantalla
# y obliga a rodar de lado para leer el resto del renglon.
_ANCHO_MIN = 10
_ANCHO_MAX = 42

# Singular y plural de cada dimension. Van escritos los dos en vez de pegarle
# una "(s)" al final: el archivo se abre en juntas y un "1 mecánico(s)" hace ver
# descuidada toda la hoja justo cuando esta proyectada. Ademas en espanol no
# basta con la s -- "unidad" hace "unidades".
_NOMBRES_DIMENSION = {"mecanicos": ("mecánico", "mecánicos"),
                      "unidades": ("unidad", "unidades"),
                      "choferes": ("chofer", "choferes"),
                      "talleres": ("taller", "talleres")}


def _ancho_de(encabezado: str, valores: list) -> int:
    """El ancho de una columna, medido sobre lo que de verdad lleva adentro.

    Se miran los primeros 200 renglones y no todos: con 500 filas la diferencia
    de ancho es de un caracter y recorrerlas enteras cuatro veces por archivo no
    la vale. El encabezado siempre entra en la cuenta porque es el que se lee
    primero y es el que no se puede cortar.
    """
    largos = [len(str(v)) for v in valores[:200] if v is not None]
    largos.append(len(encabezado))
    return max(_ANCHO_MIN, min(_ANCHO_MAX, max(largos) + 2))


def _pie(ws, fila: int, texto: str, fuente: Font, columnas: int,
         alto: int = 3) -> int:
    """Un parrafo de pie combinado en varias celdas, que es como se lee entero.

    Sin el merge el texto se corta en la primera columna y lo demas queda
    invisible detras de la celda de al lado: la nota que explica por que hay
    celdas vacias es justo la que nadie llegaria a leer.
    """
    c = ws.cell(row=fila, column=1, value=texto)
    c.font = fuente
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=fila, start_column=1,
                   end_row=fila + alto, end_column=max(columnas, 2))
    return fila + alto + 2


def _hoja_detalle(wb, detalle: dict, tabla: dict):
    """La segunda hoja: un renglon por hecho.

    VA EN EL MISMO ARCHIVO Y NO EN UNA DESCARGA APARTE. El gerente baja esto
    para llevarlo a una junta, y en una junta la pregunta que sigue al numero es
    siempre la misma --"a ver, ¿cuales?"--. Dos archivos separados se contestan
    abriendo el otro, buscandolo en Descargas y comprobando que sea del mismo
    rango; dos hojas se contestan con un clic en la pestana de abajo.

    EL ENCABEZADO REPITE EL RANGO. Parece redundante teniendolo en la primera
    hoja, pero esta es la que alguien va a copiar y pegar en un correo, y un
    bloque de renglones sin su periodo se lee como si fuera de siempre.
    """
    ws = wb.create_sheet(detalle["hoja"])
    encabezados = detalle["encabezados"]
    filas = detalle["filas"]
    columnas = len(encabezados)

    _anchos(ws, [_ancho_de(e, [f[i] for f in filas])
                 for i, e in enumerate(encabezados)])

    fila = _hoja_titulo(ws, detalle["titulo"], columnas)
    ws.cell(row=fila, column=1,
            value="Del %s al %s · %d renglón%s"
                  % (tabla["desde"], tabla["hasta"], len(filas),
                     "" if len(filas) == 1 else "es")).font = _sub
    fila += 2

    primera = _encabezados(ws, fila, encabezados)
    for f in filas:
        ws.append(list(f))

    ws.auto_filter.ref = "A%d:%s%d" % (fila, get_column_letter(columnas),
                                       max(ws.max_row, primera))
    for renglon in ws.iter_rows(min_row=primera, max_row=ws.max_row,
                                max_col=columnas):
        for i, celda in enumerate(renglon):
            celda.border = _borde
            formato = detalle["formatos"][i]
            if formato:
                celda.number_format = formato

    fila = max(ws.max_row, primera) + 2
    if detalle.get("aviso"):
        fila = _pie(ws, fila, detalle["aviso"], _aviso, columnas, alto=1)
    _pie(ws, fila, detalle["nota"], _nota, columnas, alto=4)


def construir(db: Session, dimension: str, desde: datetime.date,
              hasta: datetime.date, tipo: str = "todos",
              taller_id: int | None = None, solo_con_actividad: bool = True,
              hoy: datetime.date | None = None) -> tuple[bytes, str]:
    """Devuelve (.xlsx listo para descargar, nombre del archivo).

    El nombre lo decide tabla_para_excel() y aqui solo se pasa hacia arriba. Es a
    proposito: ahi es donde se sabe que rango se uso DE VERDAD --si el gerente
    invirtio los calendarios, _rango() los corrigio-- y un archivo que se llama
    distinto de lo que trae adentro es el que acaba citado con el rango
    equivocado. Es la misma razon por la que exportar_tablero.construir()
    tampoco arma el nombre en el controlador.
    """
    hoy = hoy or datetime.date.today()
    tabla = historiales.tabla_para_excel(db, dimension, desde, hasta, tipo,
                                         taller_id, solo_con_actividad)

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(tabla["dimension"].upper())

    encabezados = tabla["encabezados"]
    filas = tabla["filas"]
    columnas = len(encabezados)
    detalle = tabla.get("detalle")

    _anchos(ws, [_ancho_de(e, [f[i] for f in filas])
                 for i, e in enumerate(encabezados)])

    fila = _hoja_titulo(ws, tabla["titulo"], columnas)

    # El renglon que dice de que periodo habla la hoja. Va tambien el filtro de
    # tipo y el de taller cuando estan puestos: un archivo que solo trae los
    # preventivos y no lo dice se lee como si el taller no hubiera hecho un solo
    # correctivo en seis meses.
    partes = ["Del %s al %s" % (tabla["desde"], tabla["hasta"])]
    if tabla.get("tipo") in ("preventivo", "correctivo"):
        partes.append("solo %ss" % tabla["tipo"])
    if tabla.get("taller"):
        # El NOMBRE del taller y no su id. Un "taller 3" en el encabezado de una
        # hoja que se reenvia por correo no lo puede resolver nadie que no tenga
        # la base delante, y el que la recibe la lee como si fuera de toda la
        # operacion.
        partes.append("taller %s" % tabla["taller"])
    if tabla.get("total") is not None:
        uno, varios = _NOMBRES_DIMENSION[tabla["dimension"]]
        # Los dos numeros y no solo uno. Cuando el listado se recorto por el tope
        # de filas, "383 en total, 383 en la hoja" y "500 en total, 500 en la
        # hoja" se leen distinto de un vistazo, y el segundo caso es el que hay
        # que poder detectar sin bajar hasta el aviso del pie.
        partes.append("%d %s en total, %d en la hoja"
                      % (tabla["total"], uno if tabla["total"] == 1 else varios,
                         len(filas)))
    partes.append("generado el %s" % hoy.isoformat())
    ws.cell(row=fila, column=1, value=" · ".join(partes)).font = _sub
    fila += 2

    primera = _encabezados(ws, fila, encabezados)
    for f in filas:
        # Los None van tal cual: openpyxl deja la celda VACIA. Ver la nota de
        # arriba -- convertirlos a 0 aqui seria inventar una medicion justo en
        # la columna que alguien va a graficar.
        ws.append(list(f))

    # El autofiltro se pone SIEMPRE, incluso con la tabla vacia: es lo que
    # convierte la hoja en algo que el gerente puede ordenar por "TRABAJOS" o
    # filtrar por taller sin pedirle nada al sistema, que es la mitad de la
    # razon por la que pidio el Excel y no un PDF.
    ws.auto_filter.ref = "A%d:%s%d" % (fila, get_column_letter(columnas),
                                       max(ws.max_row, primera))
    for renglon in ws.iter_rows(min_row=primera, max_row=ws.max_row,
                                max_col=columnas):
        for i, celda in enumerate(renglon):
            celda.border = _borde
            formato = tabla["formatos"][i]
            if formato:
                celda.number_format = formato

    fila = max(ws.max_row, primera) + 2
    if tabla.get("aviso"):
        # El aviso de recorte tiene que ir TAMBIEN en el archivo. En la pantalla
        # se ve una vez y se cierra; aqui, sin el, una lista cortada en silencio
        # se lee como "esto es todo lo que hay", y el gerente concluye que la
        # flota es mas chica de lo que es.
        fila = _pie(ws, fila, tabla["aviso"], _aviso, columnas, alto=1)
    _pie(ws, fila, tabla["nota"], _nota, columnas, alto=4)

    if detalle:
        _hoja_detalle(wb, detalle, tabla)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue(), tabla["nombre_archivo"]
