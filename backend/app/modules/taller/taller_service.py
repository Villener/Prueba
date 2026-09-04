"""Espacios, ocupacion y ordenes.

Servicio del paquete taller: aqui viven las reglas de negocio y los
serializadores de este dominio. No sabe de HTTP (eso es del _controller) ni
define tablas (eso es del _model).
"""
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import ahora_utc
from ..sistema.comun_service import nombre_chofer, nombre_usuario, siguiente_folio  # noqa: F401


def espacios_libres_compatibles(db: Session, taller_id: int, tipo_unidad_id: int,
                                solo_capacidad: bool = True):
    """RN-06 / RI-04: un espacio solo admite el tipo de unidad para el que fue hecho.

    `solo_capacidad=True` devuelve unicamente bahias de REPARACION, que es lo
    que exige RN-06 para aceptar un ingreso: aceptar una unidad porque hay lugar
    en el patio seria mentirle al chofer, ahi no la van a atender.

    `solo_capacidad=False` incluye tambien los lugares que admiten unidad pero
    no son capacidad -- patio, area de lavado, fosa, yonke. Sirve para colocar a
    mano: una unidad que espera turno o que va a lavado tiene que poder
    estacionarse en algun lado.
    """
    q = (db.query(m.Espacio)
         .join(m.ZonaTaller)
         .filter(m.ZonaTaller.taller_id == taller_id,
                 m.ZonaTaller.admite_unidades.is_(True),
                 m.Espacio.activo.is_(True),
                 m.Espacio.estado == "libre",
                 ((m.Espacio.tipo_unidad_permitido_id == tipo_unidad_id) |
                  (m.Espacio.tipo_unidad_permitido_id.is_(None)))))
    if solo_capacidad:
        q = q.filter(m.ZonaTaller.cuenta_para_ocupacion.is_(True))
    return q.all()

def ocupacion_abierta_de_unidad(db: Session, unidad_id: int):
    return (db.query(m.OcupacionEspacio)
            .filter(m.OcupacionEspacio.unidad_id == unidad_id,
                    m.OcupacionEspacio.fecha_salida.is_(None))
            .first())

def ocupacion_abierta_de_espacio(db: Session, espacio_id: int):
    return (db.query(m.OcupacionEspacio)
            .filter(m.OcupacionEspacio.espacio_id == espacio_id,
                    m.OcupacionEspacio.fecha_salida.is_(None))
            .first())

def solicitud_out(db: Session, s: m.SolicitudIngreso) -> dict:
    libres = 0
    if s.estado in ("pendiente", "en_cola"):
        libres = len(espacios_libres_compatibles(db, s.taller_id, s.unidad.tipo_unidad_id))
    # La orden que nacio de esta solicitud, y el formato que nacio con ella.
    # Es lo que deja encadenar «acepte el ingreso» -> «empiezo el formato» sin
    # que el administrador tenga que ir a buscarlo a otra pantalla.
    orden = (db.query(m.OrdenServicio)
             .filter(m.OrdenServicio.solicitud_id == s.id).first())
    reporte = None
    if orden:
        reporte = (db.query(m.ReporteMantenimiento)
                   .filter(m.ReporteMantenimiento.orden_servicio_id == orden.id).first())
    return {
        "orden_folio": orden.folio if orden else None,
        "reporte_id": reporte.id if reporte else None,
        "reporte_folio": reporte.folio if reporte else None,
        "id": s.id, "unidad": s.unidad.num_economico if s.unidad else "-",
        "chofer": nombre_chofer(db, s.chofer_id) or "-",
        "taller": s.taller.nombre if s.taller else "-",
        "taller_id": s.taller_id,
        "tipo": s.tipo, "descripcion_falla": s.descripcion_falla,
        "urgencia": s.urgencia, "estado": s.estado,
        "fecha_solicitud": s.fecha_solicitud, "motivo_rechazo": s.motivo_rechazo,
        "espacios_libres_compatibles": libres,
    }

def asignacion_out(db: Session, a: m.AsignacionTecnico) -> dict:
    return {
        "id": a.id,
        "tecnico": a.tecnico.nombre_completo if a.tecnico else "-",
        "especialidad": a.especialidad, "orden_en_cola": a.orden_en_cola,
        "estado": a.estado, "diagnostico": a.diagnostico,
        "trabajo_realizado": a.trabajo_realizado,
        "capturado_por": nombre_usuario(db, a.capturado_por_admin_id),
        "fecha_captura": a.fecha_captura,
    }

def orden_out(db: Session, o: m.OrdenServicio) -> dict:
    fin = o.fecha_salida or ahora_utc()
    ocup = ocupacion_abierta_de_unidad(db, o.unidad_id)
    espacio = None
    if ocup:
        e = ocup.espacio
        espacio = f"{e.zona.nombre} {e.numero}" if e else None
    return {
        "id": o.id, "folio": o.folio,
        "unidad": o.unidad.num_economico if o.unidad else "-",
        "taller": o.taller.nombre if o.taller else "-",
        "estado": o.estado, "tipo": o.tipo,
        "fecha_entrada": o.fecha_entrada, "fecha_salida": o.fecha_salida,
        "dias_en_taller": (fin - o.fecha_entrada).days if o.fecha_entrada else 0,
        "espacio": espacio,
        "asignaciones": [asignacion_out(db, a) for a in
                         sorted(o.asignaciones, key=lambda x: x.orden_en_cola)],
    }


# ------------------------------------------- reporte de mantenimiento ------ #
def orden_abierta_de_unidad(db: Session, unidad_id: int):
    return (db.query(m.OrdenServicio)
            .filter(m.OrdenServicio.unidad_id == unidad_id,
                    m.OrdenServicio.fecha_salida.is_(None))
            .first())


def sacar_del_taller(db: Session, orden, admin_id: int, unidad_operativa: bool = True,
                     operacion_a_realizar: str = None):
    """La UNICA salida. Cierra la estancia completa y deja la unidad fuera.

    Antes la salida estaba partida en dos: `emitir_salida` cerraba la orden y
    liberaba el cajon, y `cerrar_reporte` sellaba el formato. Hacer una sin la
    otra dejaba la unidad a medio salir -- el cajon libre pero el formato
    abierto, o al reves -- y en el plano seguia apareciendo dentro del taller.
    Una salida es un solo hecho; aqui ocurre entero o no ocurre.

    `taller_actual_id` se limpia SIEMPRE, salga operativa o no. Que la unidad
    salga descompuesta no significa que siga en el taller: significa que se fue
    sin quedar lista, y eso lo dice `estado`, no `taller_actual_id`. Mientras
    los dos campos decian cosas distintas, el plano y el tablero del gerente no
    coincidian.
    """
    ocup = ocupacion_abierta_de_unidad(db, orden.unidad_id)
    if ocup:
        ocup.fecha_salida = ahora_utc()
        ocup.retirado_por_admin_id = admin_id
        if ocup.espacio:
            ocup.espacio.estado = "libre"

    db.add(m.FormatoSalida(orden_servicio_id=orden.id,
                           entregado_a_chofer_id=orden.chofer_responsable_id,
                           elaborado_por_admin_id=admin_id,
                           operacion_a_realizar=operacion_a_realizar,
                           unidad_operativa=unidad_operativa))

    orden.estado = "cerrada"
    orden.fecha_salida = ahora_utc()
    # `en_reparacion` seria mentira: ya no esta aqui. Si salio sin quedar lista,
    # sale como `varada` -- fuera de servicio y fuera del taller.
    orden.unidad.estado = "disponible" if unidad_operativa else "varada"
    orden.unidad.taller_actual_id = None
    return orden


def reporte_abierto_de_unidad(db: Session, unidad_id: int):
    return (db.query(m.ReporteMantenimiento)
            .filter(m.ReporteMantenimiento.unidad_id == unidad_id,
                    m.ReporteMantenimiento.fecha_salida.is_(None))
            .first())


def crear_reporte_mantenimiento(db: Session, *, unidad, taller_id: int, admin_id: int,
                                orden=None, tipo_servicio="correctivo", origen=None,
                                kilometraje=None, area=None, area_otro=None,
                                chofer_id=None, chofer_nombre=None,
                                supervisor_nombre=None, fecha_entrada=None,
                                nivel_combustible=None, notas_ingreso=None,
                                puntos=(), actividades=()):
    """Levanta el formato con sus 11 puntos y sus 10 sistemas.

    NO hace commit: lo hace quien llama, porque el ingreso al taller crea la
    orden, la ocupacion y el reporte en una sola transaccion. Si el reporte se
    guardara aparte y algo fallara despues, quedaria un formato huerfano de una
    unidad que nunca entro.

    Si la unidad YA trae un formato abierto se devuelve ese y solo se le liga la
    orden. Pasa de verdad: Pedro levanta el papel en la pluma y la solicitud se
    procesa despues. Crear el segundo formato romperia el indice unico y, peor,
    partiria en dos la historia de una misma estancia.
    """
    ya = reporte_abierto_de_unidad(db, unidad.id)
    if ya:
        if orden is not None and ya.orden_servicio_id is None:
            ya.orden_servicio_id = orden.id
        return ya

    # Y tampoco dos formatos para la MISMA orden, aunque el anterior ya este
    # cerrado. `orden_servicio_id` es unico en la base, asi que sin esta guarda
    # el segundo intento no da un error entendible: revienta el flush con una
    # violacion de restriccion a mitad de una transaccion que ya venia cargada.
    if orden is not None:
        de_la_orden = (db.query(m.ReporteMantenimiento)
                       .filter(m.ReporteMantenimiento.orden_servicio_id == orden.id)
                       .first())
        if de_la_orden:
            return de_la_orden

    chofer_id = chofer_id or unidad.poseedor_chofer_id or unidad.titular_chofer_id
    r = m.ReporteMantenimiento(
        folio=siguiente_folio(db, m.ReporteMantenimiento, "RM"),
        orden_servicio_id=orden.id if orden is not None else None,
        unidad_id=unidad.id, taller_id=taller_id,
        tipo_servicio=tipo_servicio, origen=origen,
        kilometraje=kilometraje if kilometraje is not None else unidad.km_actual,
        area=area, area_otro=area_otro if area == "otros" else None,
        chofer_id=chofer_id,
        chofer_nombre=chofer_nombre or nombre_chofer(db, chofer_id),
        supervisor_nombre=supervisor_nombre,
        fecha_entrada=fecha_entrada or ahora_utc(),
        nivel_combustible=nivel_combustible, notas_ingreso=notas_ingreso,
        capturado_por_admin_id=admin_id, fecha_captura=ahora_utc())
    db.add(r)
    db.flush()   # necesitamos el id para colgarle los renglones

    # La hoja SIEMPRE nace completa, aunque el papel venga a medio llenar.
    # Sembrarlos aqui y no en la pantalla evita que un formato viejo se vea
    # distinto al de hoy.
    tecleados = {p.punto: p for p in puntos}
    for clave, _ in m.PUNTOS_REVISION:
        p = tecleados.get(clave)
        db.add(m.PuntoRevision(reporte_id=r.id, punto=clave,
                               estado=p.estado if p else "sin_revisar",
                               observacion=p.observacion if p else None))

    por_sistema = {a.sistema: a for a in actividades}
    for clave, _ in m.SISTEMAS:
        a = por_sistema.get(clave)
        db.add(m.ActividadReporte(
            reporte_id=r.id, sistema=clave,
            a_realizar=a.a_realizar if a else None,
            realizada=a.realizada if a else None,
            tecnico_id=a.tecnico_id if a else None,
            capturado_por_admin_id=admin_id if a else None))
    return r



# El orden de impresion vive en el modelo, no aqui: el papel se lee en un orden
# fijo y la pantalla tiene que salir igual o el que captura se pierde.
_ETIQUETA_PUNTO = dict(m.PUNTOS_REVISION)
_ETIQUETA_SISTEMA = dict(m.SISTEMAS)
_ORDEN_PUNTO = {k: i for i, (k, _) in enumerate(m.PUNTOS_REVISION)}
_ORDEN_SISTEMA = {k: i for i, (k, _) in enumerate(m.SISTEMAS)}
_FIRMA_TEXTO = {k: (etiqueta, quien) for k, etiqueta, quien in m.FIRMAS}
_ORDEN_FIRMA = {k: i for i, (k, _, _) in enumerate(m.FIRMAS)}


def atendido_por(r: m.ReporteMantenimiento) -> list[dict]:
    """Los tecnicos que responden por algun sistema de este formato.

    Es la respuesta a «quien esta atendiendo este vehiculo». No sale de una
    columna: sale de que alguien tiene un sistema asignado. Un tecnico que ya
    entrego su parte sigue apareciendo -- responde por lo que hizo -- pero se
    distingue del que todavia la debe.
    """
    vistos = {}
    for a in r.actividades:
        if not a.tecnico_id or not a.tecnico:
            continue
        e = vistos.setdefault(a.tecnico_id, {
            "tecnico_id": a.tecnico_id, "tecnico": a.tecnico.nombre_completo,
            "especialidad": a.tecnico.especialidad, "sistemas": [], "pendientes": 0,
        })
        e["sistemas"].append(a.sistema)
        if not a.realizada:
            e["pendientes"] += 1
    return list(vistos.values())


def reporte_out(db: Session, r: m.ReporteMantenimiento) -> dict:
    fin = r.fecha_salida or ahora_utc()
    ocup = ocupacion_abierta_de_unidad(db, r.unidad_id)
    espacio = colocado_por = None
    if ocup and ocup.espacio:
        e = ocup.espacio
        espacio = f"{e.zona.nombre} {e.numero}" if e.zona else e.numero
        colocado_por = nombre_usuario(db, ocup.colocado_por_admin_id)
    return {
        "espacio": espacio,
        # Que administrador metio esta unidad a esa casilla. Cada uno atiende
        # sus vehiculos, y sin este dato nadie sabe a quien preguntarle.
        "colocado_por": colocado_por,
        "atendido_por": atendido_por(r),
        "id": r.id, "folio": r.folio,
        "orden_servicio_id": r.orden_servicio_id,
        "orden_folio": r.orden.folio if r.orden else None,
        "unidad_id": r.unidad_id,
        "unidad": r.unidad.num_economico if r.unidad else "-",
        "unidad_placas": r.unidad.placas if r.unidad else None,
        "taller_id": r.taller_id,
        "taller": r.taller.nombre if r.taller else "-",
        "tipo_servicio": r.tipo_servicio, "origen": r.origen,
        "kilometraje": r.kilometraje, "area": r.area, "area_otro": r.area_otro,
        "chofer_id": r.chofer_id,
        # El nombre tecleado manda sobre el de la cuenta: es lo que dice el
        # papel firmado, y el papel es el documento.
        "chofer_nombre": r.chofer_nombre or nombre_chofer(db, r.chofer_id),
        "supervisor_nombre": r.supervisor_nombre,
        "fecha_entrada": r.fecha_entrada, "fecha_salida": r.fecha_salida,
        "horas_en_taller": round((fin - r.fecha_entrada).total_seconds() / 3600, 1)
                           if r.fecha_entrada else 0,
        "nivel_combustible": r.nivel_combustible,
        "notas_ingreso": r.notas_ingreso,
        "comentarios_adicionales": r.comentarios_adicionales,
        "estado": r.estado,
        "capturado_por": nombre_usuario(db, r.capturado_por_admin_id),
        "fecha_captura": r.fecha_captura,
        "firmas_faltantes": r.firmas_faltantes_para_salida(),
        "puntos": [
            {"punto": p.punto, "etiqueta": _ETIQUETA_PUNTO.get(p.punto, p.punto),
             "estado": p.estado, "observacion": p.observacion}
            for p in sorted(r.puntos, key=lambda x: _ORDEN_PUNTO.get(x.punto, 99))
        ],
        "actividades": [
            {"id": a.id, "sistema": a.sistema,
             "etiqueta": _ETIQUETA_SISTEMA.get(a.sistema, a.sistema),
             "a_realizar": a.a_realizar, "realizada": a.realizada,
             "tecnico_id": a.tecnico_id,
             "tecnico": a.tecnico.nombre_completo if a.tecnico else None,
             "fecha_realizada": a.fecha_realizada,
             "capturado_por": nombre_usuario(db, a.capturado_por_admin_id)}
            for a in sorted(r.actividades, key=lambda x: _ORDEN_SISTEMA.get(x.sistema, 99))
        ],
        "firmas": [
            {"rol_firma": f.rol_firma,
             "etiqueta": _FIRMA_TEXTO.get(f.rol_firma, (f.rol_firma, ""))[0],
             "quien": _FIRMA_TEXTO.get(f.rol_firma, ("", ""))[1],
             "nombre": f.nombre, "fecha": f.fecha,
             "registrada_por": nombre_usuario(db, f.registrada_por_admin_id)}
            for f in sorted(r.firmas, key=lambda x: _ORDEN_FIRMA.get(x.rol_firma, 99))
        ],
    }
