"""Que asiento deja cada cosa que le pasa a un reporte de mantenimiento.

Los controladores del administrador y del mecanico llaman aqui; ninguno arma el
texto del libro por su cuenta. Asi el mismo hecho --"se capturo lo realizado en
frenos"-- se lee igual en el libro venga de quien venga.
"""
import hashlib
import re
from datetime import date, datetime

from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import a_tijuana, dia_operativo
from ..sistema.comun_service import nombre_chofer
from . import bitacora_service as bs
from .asiento_model import TIPOS_UNIDAD_NOM030

_ETIQUETA_SISTEMA = dict(m.SISTEMAS)
_ORDEN_SISTEMA = {k: i for i, (k, _) in enumerate(m.SISTEMAS)}
_ETIQUETA_PUNTO = dict(m.PUNTOS_REVISION)
_FIRMA_TEXTO = {k: (etiqueta, quien) for k, etiqueta, quien in m.FIRMAS}
_ETIQUETA_RESULTADO = {"conforme": "conforme", "no_conforme": "NO conforme"}

# Los campos de un renglon que el libro sigue. `fecha_realizada` va aparte: es
# el sello de "terminado" y se reporta como tal, no como un dato capturado.
CAMPOS_ACTIVIDAD = ["a_realizar", "realizada", "tecnico_id", "responsable_externo",
                    "resultado", "acciones_requeridas", "fecha_inicio", "fecha_termino"]
_NOMBRE_CAMPO = {
    "a_realizar": "a realizar", "realizada": "realizada",
    "tecnico_id": "responsable", "responsable_externo": "responsable externo",
    "resultado": "resultado", "acciones_requeridas": "acciones requeridas",
    "fecha_inicio": "inicio", "fecha_termino": "término",
}

# Lo que 7.1.9 y 7.1.10 piden en el registro de una actividad realizada. Se
# valida en los dos caminos que dan una actividad por hecha (administrador y
# mecanico) y otra vez al cerrar el formato.
REQUISITOS_REALIZADA = {
    "fecha_inicio": "fecha de inicio",
    "fecha_termino": "fecha de término",
    "resultado": "resultado",
    "acciones_requeridas": "acciones requeridas",
    "responsable": "responsable",
}


def _hora(v) -> str:
    """Fecha (y hora, si la tiene) de Tijuana para el texto del libro."""
    if not v:
        return "—"
    if isinstance(v, str):
        v = datetime.fromisoformat(v) if "T" in v else date.fromisoformat(v)
    if isinstance(v, datetime):
        return a_tijuana(v).strftime("%d/%m/%Y %H:%M")
    return v.strftime("%d/%m/%Y")


def _corto(texto, n=160) -> str:
    t = " ".join((texto or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def nombre_tecnico(db: Session, tecnico_id):
    if not tecnico_id:
        return None
    t = db.query(m.Tecnico).filter(m.Tecnico.id == tecnico_id).first()
    return t.nombre_completo if t else None


def responsable_de(db: Session, a: m.ActividadReporte):
    """El personal responsable (7.1.10): el tecnico del catalogo o el externo."""
    if a.tecnico_id:
        return nombre_tecnico(db, a.tecnico_id)
    externo = (a.responsable_externo or "").strip()
    return f"{externo} (externo)" if externo else None


# Lo que NO es una accion. Un "no conforme" que no requiere nada se contradice:
# si no cumple, algo hay que hacerle.
SIN_ACCIONES = {"ninguna", "ninguno", "nada", "n/a", "na", "-", "--", "no aplica"}


def faltantes_para_realizada(a: m.ActividadReporte) -> list[str]:
    """Que le falta a un renglon realizado para cumplir 7.1.9 y 7.1.10."""
    falta = []
    if not a.fecha_inicio:
        falta.append(REQUISITOS_REALIZADA["fecha_inicio"])
    if not a.fecha_termino:
        falta.append(REQUISITOS_REALIZADA["fecha_termino"])
    if a.resultado not in ("conforme", "no_conforme"):
        falta.append(REQUISITOS_REALIZADA["resultado"])
    acciones = (a.acciones_requeridas or "").strip()
    if not acciones:
        falta.append(REQUISITOS_REALIZADA["acciones_requeridas"])
    elif a.resultado == "no_conforme" and acciones.lower() in SIN_ACCIONES:
        falta.append("acciones requeridas (un no conforme requiere alguna)")
    if not a.tecnico_id and not (a.responsable_externo or "").strip():
        falta.append(REQUISITOS_REALIZADA["responsable"])
    return falta


def error_de_fechas(a: m.ActividadReporte, r: m.ReporteMantenimiento, hoy) -> str | None:
    """Las fechas declaradas tienen que caber en la estancia.

    Se declaran --el trabajo pudo hacerse ayer y capturarse hoy-- pero no pueden
    ser del futuro, ir al reves, ni ser anteriores al dia en que la unidad entro
    al taller: un trabajo hecho antes de que la unidad llegara no se hizo en esta
    estancia, y el libro quedaria contradiciendose (9.3.2.2 a, congruencia).
    """
    entrada = dia_operativo(r.fecha_entrada) if r.fecha_entrada else None
    for fecha, nombre in ((a.fecha_inicio, "inicio"), (a.fecha_termino, "termino")):
        if not fecha:
            continue
        if fecha > hoy:
            return f"la fecha de {nombre} es futura"
        if entrada and fecha < entrada:
            return (f"la fecha de {nombre} ({fecha:%d/%m/%Y}) es anterior a la entrada "
                    f"al taller ({entrada:%d/%m/%Y})")
    if a.fecha_inicio and a.fecha_termino and a.fecha_inicio > a.fecha_termino:
        return "el inicio es posterior al termino"
    return None


# ------------------------------------------------------ identificacion ------ #
def identificacion(db: Session, unidad: m.Unidad) -> dict:
    """Lo que 7.1.10 c) pide que traiga cada libro, y 6.5.2 a) cada expediente.

    Operadores: el titular y, si es otro, quien la trae hoy (RN-01). Los dos
    responden por la unidad frente a la norma.
    """
    operadores = []
    for chofer_id in (unidad.titular_chofer_id, unidad.poseedor_chofer_id):
        n = nombre_chofer(db, chofer_id)
        if n and n not in operadores:
            operadores.append(n)
    propio_permiso = (unidad.permiso_hidrocarburos or "").strip()
    propia_razon = (unidad.razon_social_regulado or "").strip()
    tipo = unidad.tipo.nombre if unidad.tipo else None
    return {
        "razon_social": propia_razon or bs.parametro(db, bs.CLAVE_RAZON_SOCIAL),
        "razon_social_propia": bool(propia_razon),
        "permiso": propio_permiso or bs.parametro(db, bs.CLAVE_PERMISO),
        "permiso_propio": bool(propio_permiso),
        "es_unidad_distribucion": tipo in TIPOS_UNIDAD_NOM030,
        "clase_nom030": TIPOS_UNIDAD_NOM030.get(tipo),
        "unidad_id": unidad.id,
        "num_economico": unidad.num_economico,
        "tipo_unidad": tipo,
        "marca": unidad.marca, "modelo": unidad.modelo, "anio": unidad.anio,
        "serie": unidad.vin, "placas": unidad.placas,
        "operadores": operadores,
        "personal_auxiliar": (unidad.personal_auxiliar or "").strip() or None,
    }


# ------------------------------------------------------------- fotos -------- #
def foto_actividad(db: Session, a: m.ActividadReporte) -> dict:
    return {
        "a_realizar": a.a_realizar or None, "realizada": a.realizada or None,
        "tecnico_id": a.tecnico_id, "tecnico": nombre_tecnico(db, a.tecnico_id),
        "responsable_externo": (a.responsable_externo or "").strip() or None,
        "resultado": a.resultado or None,
        "acciones_requeridas": a.acciones_requeridas or None,
        "fecha_inicio": bs._fecha_canonica(a.fecha_inicio),
        "fecha_termino": bs._fecha_canonica(a.fecha_termino),
        "fecha_realizada": bs._fecha_canonica(a.fecha_realizada),
    }


def foto_reporte(db: Session, r: m.ReporteMantenimiento, *, con_ids: bool = False) -> dict:
    """El formato completo tal como esta en este instante.

    `con_ids` guarda, junto a cada nombre de cuenta, el id de esa cuenta. Lo usa
    la migracion: el nombre se resuelve HOY, y una cuenta pudo cambiar de dueño
    (reconciliar_cuentas renombra conservando el id). Con el id queda claro de
    que cuenta se trata aunque el nombre cambie.
    """
    foto = {
        "folio": r.folio, "estado": r.estado, "tipo_servicio": r.tipo_servicio,
        "orden_folio": r.orden.folio if r.orden else None,
        "taller": r.taller.nombre if r.taller else None,
        "origen": r.origen, "kilometraje": r.kilometraje,
        "area": r.area, "area_otro": r.area_otro,
        "nivel_combustible": r.nivel_combustible,
        "chofer_nombre": r.chofer_nombre or nombre_chofer(db, r.chofer_id),
        "supervisor_nombre": r.supervisor_nombre,
        "fecha_entrada": bs._fecha_canonica(r.fecha_entrada),
        "fecha_salida": bs._fecha_canonica(r.fecha_salida),
        "notas_ingreso": r.notas_ingreso,
        "comentarios_adicionales": r.comentarios_adicionales,
        "capturado_por": bs.nombre_de(db, r.capturado_por_admin_id)
                         if r.capturado_por_admin_id else None,
        "fecha_captura": bs._fecha_canonica(r.fecha_captura),
        "cerrado_por": bs.nombre_de(db, r.cerrado_por_admin_id)
                       if r.cerrado_por_admin_id else None,
        "puntos": [{"punto": p.punto, "estado": p.estado, "observacion": p.observacion}
                   for p in r.puntos],
        "actividades": {a.sistema: foto_actividad(db, a) for a in r.actividades},
        "firmas": [{"rol_firma": f.rol_firma, "nombre": f.nombre,
                    "fecha": bs._fecha_canonica(f.fecha),
                    "registrada_por": bs.nombre_de(db, f.registrada_por_admin_id)
                                      if f.registrada_por_admin_id else None}
                   for f in r.firmas if f.nombre],
    }
    if con_ids:
        foto["ids_de_cuenta"] = {
            "capturado_por_admin_id": r.capturado_por_admin_id,
            "cerrado_por_admin_id": r.cerrado_por_admin_id,
            "firmas": {f.rol_firma: f.registrada_por_admin_id for f in r.firmas if f.nombre},
            "actividades": {a.sistema: a.capturado_por_admin_id for a in r.actividades
                            if a.capturado_por_admin_id},
        }
    return foto


def _programa_del_reporte(db: Session, r: m.ReporteMantenimiento):
    """El programa preventivo que esta visita cumple, si lo hay (7.1.9)."""
    if not r.orden_servicio_id:
        return None
    p = (db.query(m.ProgramaMantenimiento)
         .filter(m.ProgramaMantenimiento.orden_servicio_id == r.orden_servicio_id).first())
    if not p:
        return None
    return {
        "programa_id": p.id,
        "plan": p.plan.nombre if p.plan else None,
        "fecha_programada": bs._fecha_canonica(p.fecha_programada),
        "fecha_limite": bs._fecha_canonica(p.fecha_limite),
    }


def _resumen_revision(r: m.ReporteMantenimiento) -> str:
    cuenta = {"bien": 0, "mal": 0, "no_aplica": 0, "sin_revisar": 0}
    malos = []
    for p in r.puntos:
        cuenta[p.estado] = cuenta.get(p.estado, 0) + 1
        if p.estado == "mal":
            txt = _ETIQUETA_PUNTO.get(p.punto, p.punto)
            malos.append(f"{txt} ({_corto(p.observacion, 60)})" if p.observacion else txt)
    partes = [f"{cuenta['bien']} bien", f"{cuenta['mal']} mal"]
    if cuenta["no_aplica"]:
        partes.append(f"{cuenta['no_aplica']} no aplica")
    partes.append(f"{cuenta['sin_revisar']} sin revisar")
    txt = "Revisión de ingreso: " + ", ".join(partes) + "."
    if malos:
        txt += " Mal: " + "; ".join(malos) + "."
    return txt


# ------------------------------------------------------------ asientos ------ #
def asentar_apertura(db: Session, r: m.ReporteMantenimiento, usuario_id,
                     registrado_por_nombre=None) -> None:
    # Lo que la misma transaccion ya cambio (el programa ligado a la orden, los
    # renglones recien agregados) tiene que estar en la base antes de leerlo:
    # la sesion no hace autoflush.
    db.flush()
    unidad = r.unidad or db.get(m.Unidad, r.unidad_id)
    programa = _programa_del_reporte(db, r)
    taller = r.taller.nombre if r.taller else "taller"
    km = f"{r.kilometraje:,} km" if r.kilometraje else "kilometraje sin capturar"
    desc = (f"Entra a {taller} con el formato {r.folio} "
            f"({'preventivo' if r.tipo_servicio == 'preventivo' else 'correctivo'}), {km}. "
            + _resumen_revision(r))
    if programa:
        desc += f" Cumple el programa preventivo «{programa['plan'] or 'sin nombre'}»."
    if r.notas_ingreso:
        desc += f" Notas: {_corto(r.notas_ingreso)}"
    bs.asentar(
        db, unidad_id=r.unidad_id, reporte_id=r.id, tipo="apertura", descripcion=desc,
        registrado_por_id=usuario_id, registrado_por_nombre=registrado_por_nombre,
        programa_id=programa["programa_id"] if programa else None,
        fecha_inicio=r.fecha_entrada,
        datos={"reporte": foto_reporte(db, r), "identificacion": identificacion(db, unidad),
               "programa": programa})


def asentar_actividad(db: Session, r: m.ReporteMantenimiento, a: m.ActividadReporte,
                      antes: dict, usuario_id, tipo: str = "actividad",
                      motivo: str | None = None):
    """Un asiento si el renglon cambio; nada si quedo igual.

    Si cambia un valor que YA estaba escrito, no es avance: es una correccion,
    y el asiento apunta al que corrige (7.1.10 a). Llenar lo que estaba vacio
    --poner lo realizado junto a lo que habia que hacer-- es avance y no apunta
    a nadie.
    """
    db.flush()
    despues = foto_actividad(db, a)
    cambios = [c for c in CAMPOS_ACTIVIDAD if antes.get(c) != despues.get(c)]
    reabierto = bool(antes.get("fecha_realizada")) and not despues.get("fecha_realizada")
    # Dar un sistema por terminado es un hecho en si, aunque ningun texto
    # cambie: el avance ya estaba escrito y ahora se sella como entregado.
    terminado = not antes.get("fecha_realizada") and bool(despues.get("fecha_realizada"))
    if not cambios and not reabierto and not terminado:
        return None

    corrige = [c for c in cambios if antes.get(c) not in (None, "")]
    if reabierto:
        corrige.append("fecha_realizada")
    previo = bs.ultimo_de_actividad(db, a.id) or bs.asiento_base_del_reporte(db, r.id)

    etiqueta = _ETIQUETA_SISTEMA.get(a.sistema, a.sistema)
    partes = []
    for c in cambios:
        v = despues.get(c)
        if c == "tecnico_id":
            partes.append(f"responsable: {despues.get('tecnico') or 'sin asignar'}")
        elif c == "resultado":
            partes.append(f"resultado: {_ETIQUETA_RESULTADO.get(v, 'sin resultado')}")
        elif c in ("fecha_inicio", "fecha_termino"):
            partes.append(f"{_NOMBRE_CAMPO[c]}: {_hora(v)}")
        else:
            partes.append(f"{_NOMBRE_CAMPO[c]}: «{_corto(v)}»" if v
                          else f"{_NOMBRE_CAMPO[c]}: (vacío)")
    if reabierto:
        partes.append("se reabre: deja de estar terminado")
    if terminado:
        partes.append("se da por terminado")
    desc = f"{etiqueta} — " + "; ".join(partes) + "."
    if corrige and previo:
        antes_txt = []
        for c in corrige:
            if c == "tecnico_id":
                antes_txt.append(f"responsable {antes.get('tecnico') or 'sin asignar'}")
            elif c == "fecha_realizada":
                antes_txt.append("estaba terminado")
            elif c == "resultado":
                antes_txt.append(f"resultado {_ETIQUETA_RESULTADO.get(antes.get(c), '—')}")
            elif c in ("fecha_inicio", "fecha_termino"):
                antes_txt.append(f"{_NOMBRE_CAMPO[c]} {_hora(antes.get(c))}")
            else:
                antes_txt.append(f"{_NOMBRE_CAMPO[c]} «{_corto(antes.get(c), 80)}»")
        desc = (f"Corrige el asiento {previo.numero}. " + desc
                + " Antes: " + "; ".join(antes_txt) + ".")
    if motivo:
        desc += f" Motivo: {_corto(motivo)}"

    return bs.asentar(
        db, unidad_id=r.unidad_id, reporte_id=r.id, actividad_id=a.id, tipo=tipo,
        sistema=a.sistema, descripcion=desc, registrado_por_id=usuario_id,
        resultado=a.resultado or None, acciones_requeridas=a.acciones_requeridas,
        responsable_nombre=responsable_de(db, a), responsable_tecnico_id=a.tecnico_id,
        fecha_inicio=a.fecha_inicio, fecha_termino=a.fecha_termino,
        datos={"folio": r.folio, "sistema": a.sistema, "cambios": cambios,
               "antes": antes, "despues": despues},
        corrige_a_id=previo.id if (corrige and previo) else None, motivo=motivo)


def asentar_comentarios(db: Session, r: m.ReporteMantenimiento, antes, usuario_id):
    """Los comentarios adicionales tambien son parte del registro (7.1.10 a)."""
    despues = r.comentarios_adicionales or None
    if (antes or None) == despues:
        return None
    previo = (db.query(m.AsientoBitacora)
              .filter(m.AsientoBitacora.reporte_id == r.id,
                      m.AsientoBitacora.tipo == "comentarios")
              .order_by(m.AsientoBitacora.numero.desc()).first())
    desc = (f"Comentarios adicionales del formato {r.folio}: "
            + (f"«{_corto(despues)}»" if despues else "(se dejan vacíos)") + ".")
    if antes:
        desc += f" Antes decían «{_corto(antes, 80)}»."
    return bs.asentar(
        db, unidad_id=r.unidad_id, reporte_id=r.id, tipo="comentarios",
        descripcion=desc, registrado_por_id=usuario_id,
        corrige_a_id=previo.id if (antes and previo) else None,
        datos={"folio": r.folio, "antes": antes, "despues": despues})


# El lienzo de la firma en la pantalla. El trazo llega en estas coordenadas.
LIENZO_FIRMA = (600, 200)
_TRAZO_OK = re.compile(r"^[ML0-9 .\-]+$")
_TRAZO_TOKEN = re.compile(r"[ML]|-?\d+(?:\.\d+)?")
# Lo minimo para que sea una firma y no un toque accidental o una raya: puntos
# capturados y largo del trazo, en unidades del lienzo (600 de ancho).
FIRMA_MIN_PUNTOS = 8
FIRMA_MIN_TINTA = 150


def validar_trazo(trazo: str) -> tuple[str, str]:
    """Revisa el trazo de una firma dibujada. Devuelve (trazo limpio, huella).

    Solo se aceptan caminos "M x y L x y ..." dentro del lienzo: nada de otros
    comandos SVG, que es como se colaria algo que no es una firma al imprimirla.
    """
    from fastapi import HTTPException
    t = " ".join((trazo or "").split())
    if not t or not _TRAZO_OK.match(t):
        raise HTTPException(422, "No se pudo leer la firma. Borrala y vuelve a dibujarla.")
    tokens = _TRAZO_TOKEN.findall(t)
    w, h = LIENZO_FIRMA
    puntos, tinta, previo, i = 0, 0.0, None, 0
    try:
        while i < len(tokens):
            cmd = tokens[i]
            if cmd not in ("M", "L"):
                raise ValueError
            x, y = float(tokens[i + 1]), float(tokens[i + 2])
            i += 3
            if not (-2 <= x <= w + 2 and -2 <= y <= h + 2):
                raise ValueError
            if cmd == "L" and previo:
                tinta += ((x - previo[0]) ** 2 + (y - previo[1]) ** 2) ** 0.5
            previo = (x, y)
            puntos += 1
    except (ValueError, IndexError):
        raise HTTPException(422, "No se pudo leer la firma. Borrala y vuelve a dibujarla.")
    if puntos < FIRMA_MIN_PUNTOS or tinta < FIRMA_MIN_TINTA:
        raise HTTPException(422, "La firma esta muy corta: dibujala completa, como en el papel.")
    return t, hashlib.sha256(t.encode()).hexdigest()


def asentar_firma(db: Session, r: m.ReporteMantenimiento, f: m.FirmaReporte, usuario_id):
    etiqueta, quien = _FIRMA_TEXTO.get(f.rol_firma, (f.rol_firma, ""))
    como = (f"Firma dibujada en la pantalla (huella {f.trazo_sha256[:12]})."
            if f.trazo_sha256 else "Se registra la firma de tinta que consta en el formato.")
    bs.asentar(
        db, unidad_id=r.unidad_id, reporte_id=r.id, tipo="firma",
        descripcion=f"{etiqueta} ({quien}): firmó {f.nombre}. {como}",
        registrado_por_id=usuario_id,
        datos={"folio": r.folio, "rol_firma": f.rol_firma, "nombre": f.nombre,
               "usuario_id": f.usuario_id, "trazo_sha256": f.trazo_sha256})


def huella_archivo(ruta) -> str | None:
    """SHA-256 del archivo tal como quedo en disco.

    La foto vive fuera de la base, donde la cadena de hash no llega. Con su
    huella dentro del asiento, sustituir el archivo en el disco deja de pasar
    desapercibido: basta recalcularla y compararla.
    """
    try:
        h = hashlib.sha256()
        with open(ruta, "rb") as fh:
            for bloque in iter(lambda: fh.read(65536), b""):
                h.update(bloque)
        return h.hexdigest()
    except OSError:
        return None


def asentar_evidencia(db: Session, r: m.ReporteMantenimiento, ev, usuario_id,
                      sha256: str | None = None, ruta_archivo=None):
    """La huella es la de los bytes que se RECIBIERON (la calcula `guardar()`),
    no la del archivo que haya en el disco: si en el disco hubiera otra cosa con
    ese nombre, el libro certificaria justo la sustitucion."""
    txt = f"Se agrega evidencia fotográfica del servicio (foto {ev.id})."
    if ev.descripcion:
        txt += f" {_corto(ev.descripcion)}"
    huella = sha256 or (huella_archivo(ruta_archivo) if ruta_archivo else None)
    bs.asentar(db, unidad_id=r.unidad_id, reporte_id=r.id, tipo="evidencia",
               descripcion=txt, registrado_por_id=usuario_id,
               datos={"folio": r.folio, "evidencia_id": ev.id,
                      "url_archivo": ev.url_archivo, "descripcion": ev.descripcion,
                      "sha256": huella})


def asentar_cierre(db: Session, r: m.ReporteMantenimiento, usuario_id,
                   unidad_operativa: bool, operacion_a_realizar=None):
    """La salida. Resume lo que quedo pendiente: eso SON las acciones requeridas.

    7.3.1.2 a) 3 y 7.2.1.2 c) 10: una unidad con un defecto no se opera hasta
    corregirlo. Si sale NO operativa, el asiento lo dice con todas sus letras.

    Se llama con el formato YA marcado como cerrado y sin tocar ningun renglon:
    los candados de la base rechazan cualquier escritura a los renglones de un
    formato cerrado, y este asiento solo lee.
    """
    pendientes = []
    for a in sorted(r.actividades, key=lambda x: _ORDEN_SISTEMA.get(x.sistema, 99)):
        etiqueta = _ETIQUETA_SISTEMA.get(a.sistema, a.sistema)
        if a.a_realizar and not a.realizada:
            pendientes.append(f"{etiqueta}: {_corto(a.a_realizar, 80)} (sin realizar)")
        elif a.resultado == "no_conforme":
            extra = f": {_corto(a.acciones_requeridas, 80)}" if a.acciones_requeridas else ""
            pendientes.append(f"{etiqueta}: no conforme{extra}")
    estado = "operativa" if unidad_operativa else "NO operativa: no se opera hasta corregir"
    desc = (f"Sale del taller {estado}. Formato {r.folio} cerrado; "
            f"estancia del {_hora(r.fecha_entrada)} al {_hora(r.fecha_salida)}.")
    if pendientes:
        desc += f" Quedan {len(pendientes)} pendiente(s)."
    programa = _programa_del_reporte(db, r)
    bs.asentar(
        db, unidad_id=r.unidad_id, reporte_id=r.id, tipo="cierre", descripcion=desc,
        registrado_por_id=usuario_id,
        programa_id=programa["programa_id"] if programa else None,
        resultado="conforme" if unidad_operativa else "no_conforme",
        acciones_requeridas="\n".join(pendientes) or "Ninguna",
        fecha_inicio=r.fecha_entrada, fecha_termino=r.fecha_salida,
        datos={"reporte": foto_reporte(db, r), "unidad_operativa": unidad_operativa,
               "operacion_a_realizar": operacion_a_realizar, "programa": programa})


def asentar_vinculo(db: Session, r: m.ReporteMantenimiento, orden, usuario_id,
                    registrado_por_nombre=None):
    """A un formato ya abierto se le liga la orden (y con ella, quiza, un programa).

    Pasa cuando la unidad entro por la pluma con formato a mano y DESPUES se
    acepta su solicitud. Sin este asiento, el cierre apareceria cumpliendo un
    programa preventivo que ninguna parte del libro dice cuando se ligo.
    """
    db.flush()
    programa = _programa_del_reporte(db, r)
    desc = f"Se liga la orden {orden.folio} al formato {r.folio}."
    if programa:
        desc += f" Con ella, el formato cumple el programa preventivo «{programa['plan'] or 'sin nombre'}»."
    bs.asentar(db, unidad_id=r.unidad_id, reporte_id=r.id, tipo="vinculo",
               descripcion=desc, registrado_por_id=usuario_id,
               registrado_por_nombre=registrado_por_nombre,
               programa_id=programa["programa_id"] if programa else None,
               datos={"folio": r.folio, "orden_folio": orden.folio, "programa": programa})


def asentar_identificacion(db: Session, unidad: m.Unidad, antes: dict, despues: dict,
                           usuario_id, alcance: str):
    """7.1.10 c): cambian los datos que identifican el libro. Queda asentado.

    La cabecera del libro muestra los de hoy; este asiento dice desde cuando y
    que decian antes, para que nadie lea la cabecera de hoy como la de ayer.
    """
    etiquetas = {"razon_social": "razón social", "permiso": "permiso",
                 "personal_auxiliar": "personal auxiliar",
                 "permiso_hidrocarburos": "permiso propio",
                 "razon_social_regulado": "razón social propia"}
    partes = [f"{etiquetas.get(k, k)}: «{antes.get(k) or '—'}» → «{despues.get(k) or '—'}»"
              for k in despues if (antes.get(k) or None) != (despues.get(k) or None)]
    if not partes:
        return None
    return bs.asentar(
        db, unidad_id=unidad.id, tipo="identificacion",
        descripcion=f"Cambian los datos de identificación ({alcance}): " + "; ".join(partes) + ".",
        registrado_por_id=usuario_id,
        datos={"alcance": alcance, "antes": antes, "despues": despues})


def asentar_correccion(db: Session, r: m.ReporteMantenimiento, corregido, texto: str,
                       motivo: str, usuario_id):
    """7.1.10 a): el formato cerrado no se toca; se asienta lo que debio decir."""
    cuerpo = texto.strip()
    if cuerpo[-1:] not in ".!?":
        cuerpo += "."
    if corregido is not None:
        desc = f"Corrige el asiento {corregido.numero}: {cuerpo}"
    else:
        desc = f"Aclaración al formato {r.folio}: {cuerpo}"
    desc += f" Motivo: {motivo.strip()}"
    return bs.asentar(
        db, unidad_id=r.unidad_id, reporte_id=r.id, tipo="correccion",
        sistema=corregido.sistema if corregido is not None else None,
        actividad_id=corregido.actividad_id if corregido is not None else None,
        descripcion=desc, registrado_por_id=usuario_id,
        corrige_a_id=corregido.id if corregido is not None else None,
        motivo=motivo.strip(),
        datos={"folio": r.folio, "texto": texto.strip(),
               "asiento_corregido": corregido.numero if corregido is not None else None})


def asentar_migracion(db: Session, r: m.ReporteMantenimiento, libro_desde):
    """La copia de un formato que ya existia cuando nacio el libro.

    NO se inventan fechas ni autores: el asiento lo registra el Sistema, con la
    hora de hoy, y dice que es una copia. Las fechas del formato van como lo que
    son --lo que el formato dice-- dentro de la descripcion y de `datos`. Estos
    formatos se editaron antes de que existiera el libro, asi que no traen
    inicio, termino ni resultado por actividad: la pantalla los separa y NO los
    cuenta como evidencia de 7.1.9.
    """
    unidad = r.unidad or db.get(m.Unidad, r.unidad_id)
    capturo = bs.nombre_de(db, r.capturado_por_admin_id) if r.capturado_por_admin_id else None
    desc = (f"Formato {r.folio} ({r.tipo_servicio}, {r.estado}) capturado antes de "
            f"existir este libro; se transcribe tal como estaba. Entrada {_hora(r.fecha_entrada)}"
            + (f", salida {_hora(r.fecha_salida)}" if r.fecha_salida else ", sigue en el taller")
            + (f"; cuenta que lo capturó: {capturo}." if capturo else ".")
            + " Los nombres de cuenta se resolvieron al transcribir.")
    bs.asentar(
        db, unidad_id=r.unidad_id, reporte_id=r.id, tipo="migracion", descripcion=desc,
        registrado_por_id=None,
        registrado_por_nombre=f"{bs.REGISTRADO_POR_SISTEMA} (transcripción)",
        fecha_inicio=r.fecha_entrada, fecha_termino=r.fecha_salida,
        datos={"reporte": foto_reporte(db, r, con_ids=True),
               "identificacion": identificacion(db, unidad),
               "libro_desde": bs._fecha_canonica(libro_desde)})
