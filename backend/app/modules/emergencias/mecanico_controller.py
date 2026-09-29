"""Modulo Mecanico autonomo - CU-MEC-01 a 12.

SOLO LOS SEIS DE LAS PLANTAS SATELITE. De los 42 tecnicos del catalogo, estos
seis son los unicos con cuenta de usuario, y la razon esta en el cambio de
alcance de la v2.0: los mecanicos de Alamos NO usan la aplicacion --entregan su
trabajo en papel y Pedro lo captura-- porque tienen un administrador al lado. En
Tecate, Rosarito, Guaycura, Carranza y Valle Redondo no hay nadie que capture,
asi que el mecanico es el unico que puede.

Sus seis cuentas existian en produccion desde el importador, con contrasena
valida y SIN ROL: podian autenticarse y no les tocaba ningun modulo, asi que
entraban y veian la aplicacion vacia sin saber por que. Una cuenta que autentica
y no lleva a ninguna parte es peor que una que no existe, porque el usuario cree
que el sistema esta roto. Este modulo es lo que le faltaba a esas cuentas.

LO QUE ESTE MODULO NO INVENTA. Toda la maquinaria ya estaba en los modelos
--SolicitudPieza, OrdenAuxilio con su difusion y sus respuestas, TrasladoUnidad,
ActividadReporte-- porque el diseño la contemplo desde la v2.0. Lo que no
existia era la puerta para entrar a usarla.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import models as m
from ...core.database import get_db
from ...core.security import notificar, registrar_bitacora, require_roles
from ...core.tiempo import ahora_utc, dia_operativo
from ...schemas import AvanceActividadIn
from ..bitacora import asientos_reporte as bit
from ..bitacora import bitacora_service as bs
from ..sistema import comun_service as comun
from ..sistema.comun_service import nombre_usuario, siguiente_folio
from . import emergencias_service as emsvc

router = APIRouter(prefix="/api/mecanico", tags=["mecanico autonomo"])
solo_mec = require_roles("mecanico")

SISTEMAS_ABIERTOS = ("abierto",)
# Los de ESTADOS_AUXILIO en los que ya no hay nada que hacer.
CERRADOS = ("resuelta", "escalada_a_arrastre", "cancelada")


def _tecnico(db: Session, usuario_id: int) -> m.Tecnico:
    """El tecnico detras de la cuenta. Sin el, no hay a quien asignarle nada."""
    t = db.query(m.Tecnico).filter(m.Tecnico.usuario_id == usuario_id).first()
    if not t:
        raise HTTPException(403, "Tu cuenta no esta ligada a ningun tecnico del catalogo. "
                                 "Avisale al administrador: sin esa liga no se te puede "
                                 "asignar trabajo ni piezas.")
    return t


# --------------------------------------------------------------- CU-MEC-01 -- #
@router.get("/cola")
def mi_cola(db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """Los sistemas del vehiculo que me toca atender, en formatos abiertos.

    Es la cola de trabajo del papel: una fila por sistema, con lo que hay que
    hacerle y lo que ya se le hizo. Lo pendiente va primero -- lo terminado se
    queda abajo para poder consultarlo, no para estorbar.
    """
    t = _tecnico(db, usuario.id)
    filas = []
    for a in (db.query(m.ActividadReporte)
              .filter(m.ActividadReporte.tecnico_id == t.id).all()):
        r = a.reporte
        if not r or r.estado not in SISTEMAS_ABIERTOS:
            continue
        u = db.query(m.Unidad).filter(m.Unidad.id == r.unidad_id).first()
        filas.append({
            "actividad_id": a.id,
            "reporte_id": r.id, "folio": r.folio,
            "unidad": u.num_economico if u else "-",
            "unidad_id": r.unidad_id,
            "tipo_servicio": r.tipo_servicio,
            "sistema": a.sistema,
            "a_realizar": a.a_realizar,
            "realizada": a.realizada,
            # Terminado es tener FECHA, no tener texto. Un avance a medias
            # --"balatas puestas, faltan discos"-- llena `realizada` y deja la
            # fecha en blanco a proposito; contarlo como terminado le habria
            # escondido al mecanico el trabajo que le falta.
            "terminada": bool(a.fecha_realizada),
            "fecha_realizada": a.fecha_realizada,
            "fecha_entrada": r.fecha_entrada,
            # NOM-030: lo que ya capturo, para proponerlo al terminar.
            "fecha_inicio": a.fecha_inicio, "fecha_termino": a.fecha_termino,
            "resultado": a.resultado, "acciones_requeridas": a.acciones_requeridas,
        })
    filas.sort(key=lambda x: (x["terminada"], x["fecha_entrada"] or datetime.datetime.min))
    return filas


def _mi_actividad(db: Session, actividad_id: int, usuario_id: int) -> m.ActividadReporte:
    t = _tecnico(db, usuario_id)
    a = (db.query(m.ActividadReporte)
         .filter(m.ActividadReporte.id == actividad_id).first())
    if not a:
        raise HTTPException(404, "No existe ese renglon de trabajo.")
    if a.tecnico_id != t.id:
        raise HTTPException(403, "Ese sistema no te fue asignado.")
    if a.reporte and a.reporte.estado != "abierto":
        raise HTTPException(409, "El formato ya esta cerrado: un papel firmado no se "
                                 "reescribe. Para corregir se levanta otro.")
    return a


def _mi_actividad_bloqueada(db: Session, actividad_id: int, usuario_id: int):
    """El renglon, releido DESPUES de tomar el candado del libro de la unidad.

    Si el administrador lo cambio mientras el mecanico escribia, se compara
    contra lo que dejo el administrador: asi el cambio del mecanico queda
    asentado como correccion de lo anterior, y no como si no hubiera nada.
    """
    a = _mi_actividad(db, actividad_id, usuario_id)
    bs.bloquear_unidad(db, a.reporte.unidad_id)
    db.refresh(a)
    db.refresh(a.reporte)
    return _mi_actividad(db, actividad_id, usuario_id)


# --------------------------------------------------------------- CU-MEC-02 -- #
@router.post("/actividades/{actividad_id}/diagnostico")
def registrar_diagnostico(actividad_id: int, texto: str,
                          db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """Lo que encontro que hay que hacerle. Va en la columna "a realizar".

    Se separa del avance (CU-MEC-06) a proposito: en el papel son dos columnas
    una frente a otra, y esa comparacion --lo pedido contra lo entregado-- es
    justo lo que el supervisor firma. Si se escribieran en el mismo campo, no
    quedaria con que comparar.
    """
    if not (texto or "").strip():
        raise HTTPException(400, "Escribe el diagnostico.")
    a = _mi_actividad_bloqueada(db, actividad_id, usuario.id)
    antes = bit.foto_actividad(db, a)
    a.a_realizar = texto.strip()
    bit.asentar_actividad(db, a.reporte, a, antes, usuario.id)
    registrar_bitacora(db, usuario.id, "diagnostico_mecanico", "actividad_reporte",
                       a.id, f"sistema {a.sistema}")
    db.commit()
    return {"actividad_id": a.id, "a_realizar": a.a_realizar}


# --------------------------------------------------------------- CU-MEC-06 -- #
@router.post("/actividades/{actividad_id}/avance")
def registrar_avance(actividad_id: int, texto: str, terminada: bool = False,
                     datos: AvanceActividadIn | None = None,
                     db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """Lo que se le hizo. Con `terminada` se sella la fecha.

    El avance se puede escribir varias veces --una reparacion tarda-- pero la
    fecha se pone solo cuando el mecanico dice que termino. Sin esa distincion,
    el reporte no sabe si un texto es un avance o el cierre.

    UNA VEZ SELLADA, LA FECHA NO SE BORRA. Antes la linea era
    `a.fecha_realizada = ahora_utc() if terminada else None`, y ese `else None`
    era incondicional: un segundo avance sobre un sistema ya terminado --y el
    valor por omision de `terminada` es False-- lo destermaba en silencio,
    cambiando la cola, el formato de salida y la bitacora sin que nadie lo
    pidiera. Ahora un sistema terminado se rechaza, por la misma razon que un
    formato cerrado: lo que ya se entrego no se reescribe sin que se sepa.

    NOM-030 7.1.9 y 7.1.10: al TERMINAR, el registro tiene que traer inicio,
    termino, resultado y acciones requeridas (el responsable es el mismo
    mecanico: el sistema ya esta a su nombre). Viajan en el cuerpo JSON y no
    en la URL, porque las acciones son texto libre y la URL queda en el log.
    Las fechas se DECLARAN: la pantalla propone hoy, pero el trabajo pudo
    empezar antier.
    """
    if not (texto or "").strip():
        raise HTTPException(400, "Escribe el avance.")
    a = _mi_actividad_bloqueada(db, actividad_id, usuario.id)
    if a.fecha_realizada:
        raise HTTPException(409, {
            "mensaje": "Ese sistema ya lo diste por terminado y la fecha quedo sellada. "
                       "Si te equivocaste, pidele al administrador del taller que lo "
                       "reabra: asi queda por escrito quien lo reabrio y cuando.",
            "ya_terminada": True,
            "terminada_el": a.fecha_realizada.isoformat(),
        })
    antes = bit.foto_actividad(db, a)
    datos = datos or AvanceActividadIn()
    hoy = dia_operativo(ahora_utc())
    if datos.fecha_inicio is not None:
        a.fecha_inicio = datos.fecha_inicio
    if terminada:
        a.fecha_termino = datos.fecha_termino or a.fecha_termino
        a.resultado = datos.resultado or a.resultado
        a.acciones_requeridas = (datos.acciones_requeridas or "").strip() or a.acciones_requeridas
    error = bit.error_de_fechas(a, a.reporte, hoy)
    if error:
        raise HTTPException(422, error[0].upper() + error[1:] + ".")

    a.realizada = texto.strip()
    if terminada:
        falta = bit.faltantes_para_realizada(a)
        if falta:
            raise HTTPException(422, {
                "mensaje": "Para darlo por terminado la NOM-030 pide: " + ", ".join(falta) + ".",
                "falta": falta,
            })
        a.fecha_realizada = ahora_utc()
    bit.asentar_actividad(db, a.reporte, a, antes, usuario.id)
    registrar_bitacora(db, usuario.id,
                       "termino_mecanico" if terminada else "avance_mecanico",
                       "actividad_reporte", a.id, f"sistema {a.sistema}")
    db.commit()
    return {"actividad_id": a.id, "realizada": a.realizada,
            "terminada": bool(a.fecha_realizada)}


# --------------------------------------------------------------- CU-MEC-03 -- #
# La consulta de existencia NO vive aqui: es `GET /api/admin/piezas`, que ya
# calcula el disponible real leyendo `Existencia` del almacen central.
#
# Aqui hubo un buscador propio que leia `Pieza.stock_actual`, y ese campo no lo
# escribe nadie: el importador deja la existencia en `Existencia`. Habria
# contestado "no hay" de las 18,233 piezas del catalogo y el mecanico habria
# pedido cosas que si estan en Alamos. Se borro y el rol `mecanico` se agrego a
# los permitidos de ese endpoint, igual que ya estaba el capturista.

# --------------------------------------------------------------- CU-MEC-04 -- #
@router.post("/piezas/solicitar", status_code=201)
def solicitar_pieza(cantidad: int = 1, pieza_id: int | None = None,
                    descripcion_libre: str | None = None,
                    justificacion: str | None = None,
                    reporte_id: int | None = None,
                    db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """Pide una pieza al almacen de Alamos. La evalua Erick (CU-ADM-20).

    Se acepta `descripcion_libre` para lo que NO esta en catalogo: en una planta
    satelite la pieza que hace falta muchas veces no tiene SKU, y obligar a
    escoger del catalogo significaria que la solicitud no se levanta y el
    mecanico acabe hablando por telefono -- que es lo que este modulo viene a
    dejar por escrito.
    """
    t = _tecnico(db, usuario.id)
    if cantidad < 1:
        raise HTTPException(400, "La cantidad tiene que ser al menos 1.")
    if not pieza_id and not (descripcion_libre or "").strip():
        raise HTTPException(400, "Escoge una pieza del catalogo o describe la que "
                                 "necesitas si no aparece.")
    if pieza_id and not db.query(m.Pieza).filter(m.Pieza.id == pieza_id).first():
        raise HTTPException(404, "Esa pieza no existe en el catalogo.")
    if not t.taller_id:
        raise HTTPException(409, "Tu ficha de tecnico no tiene taller asignado, "
                                 "y la solicitud tiene que salir de algun lado.")

    s = m.SolicitudPieza(
        folio=siguiente_folio(db, m.SolicitudPieza, "SPZ"),
        tecnico_id=t.id, taller_id=t.taller_id,
        orden_servicio_id=None, pieza_id=pieza_id,
        descripcion_libre=(descripcion_libre or "").strip() or None,
        cantidad=cantidad, justificacion=justificacion, estado="enviada")
    db.add(s)
    db.flush()

    pieza = (db.query(m.Pieza).filter(m.Pieza.id == pieza_id).first()
             if pieza_id else None)
    que = pieza.nombre if pieza else s.descripcion_libre
    detalle = (f"{t.nombre} {t.apellidos} pide {cantidad} x {que}"
               + (f" - {justificacion}" if justificacion else ""))
    for u in (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
              .filter(m.Rol.nombre == "administrador").all()):
        notificar(db, u.id, "Solicitud de pieza", detalle,
                  "pieza", "solicitud_pieza", s.id)
    registrar_bitacora(db, usuario.id, "solicitar_pieza", "solicitud_pieza", s.id, detalle)
    db.commit()
    return {"id": s.id, "folio": s.folio, "estado": s.estado}


# --------------------------------------------------------------- CU-MEC-05 -- #
@router.get("/piezas/solicitudes")
def mis_solicitudes(db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """En que va cada pieza que pedi, y su fecha estimada de llegada."""
    t = _tecnico(db, usuario.id)
    fuera = []
    for s in (db.query(m.SolicitudPieza)
              .filter(m.SolicitudPieza.tecnico_id == t.id)
              .order_by(m.SolicitudPieza.fecha_solicitud.desc()).all()):
        pieza = (db.query(m.Pieza).filter(m.Pieza.id == s.pieza_id).first()
                 if s.pieza_id else None)
        fuera.append({
            "id": s.id, "folio": s.folio,
            "pieza": pieza.nombre if pieza else s.descripcion_libre,
            "del_catalogo": bool(s.pieza_id),
            "cantidad": s.cantidad, "estado": s.estado,
            "fecha_solicitud": s.fecha_solicitud,
            "fecha_estimada_llegada": s.fecha_estimada_llegada,
            "fecha_surtido": s.fecha_surtido,
            "motivo_rechazo": s.motivo_rechazo,
            "evaluada_por": (nombre_usuario(db, s.evaluada_por_usuario_id)
                             if s.evaluada_por_usuario_id else None),
        })
    return fuera


# ------------------------------------------------------------ CU-MEC-07/08 -- #
@router.get("/auxilios")
def auxilios_difundidos(db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """Los auxilios que me difundieron y los que ya acepte.

    El auxilio se DIFUNDE a todos los autonomos disponibles y el primero que
    acepta lo gana. Aqui se ven los dos: los que todavia estan en disputa y el
    que ya es mio.
    """
    t = _tecnico(db, usuario.id)
    fuera = []
    difundidos = {d.orden_auxilio_id: d for d in
                  db.query(m.DifusionAuxilio)
                  .filter(m.DifusionAuxilio.tecnico_id == t.id).all()}
    ya_respondi = {r.orden_auxilio_id for r in
                   db.query(m.RespuestaAuxilio)
                   .filter(m.RespuestaAuxilio.tecnico_id == t.id).all()}
    for oid, dif in difundidos.items():
        o = db.query(m.OrdenAuxilio).filter(m.OrdenAuxilio.id == oid).first()
        if not o or o.estado in CERRADOS:
            continue
        r = (db.query(m.ReporteAveria)
             .filter(m.ReporteAveria.id == o.reporte_averia_id).first())
        mio = o.tecnico_acepta_id == t.id
        # Si otro ya lo tomo, deja de ser accionable pero se dice -- que
        # desaparezca sin explicacion parece que se perdio el aviso.
        tomado_por_otro = bool(o.tecnico_acepta_id) and not mio
        fuera.append({
            "orden_id": o.id, "folio": o.folio, "estado": o.estado,
            "notificado_en": dif.notificado_en,
            "distancia_km_estimada": dif.distancia_km_estimada,
            "mio": mio, "tomado_por_otro": tomado_por_otro,
            "ya_respondi": oid in ya_respondi,
            "unidad": r.unidad.num_economico if r and r.unidad else "-",
            "tipo": r.tipo if r else None,
            "descripcion": r.descripcion_falla if r else None,
            "latitud": r.latitud if r else None,
            "longitud": r.longitud if r else None,
            "direccion_referencia": r.direccion_referencia if r else None,
            "chofer": emsvc.nombre_chofer(db, r.chofer_id) if r else None,
        })
    fuera.sort(key=lambda x: (x["tomado_por_otro"], not x["mio"],
                              x["distancia_km_estimada"] or 9999))
    return fuera


@router.post("/auxilios/{orden_id}/responder")
def responder_auxilio(orden_id: int, acepto: bool, motivo: str | None = None,
                      db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """CU-MEC-08: lo tomo o lo paso. El primero que acepta lo gana.

    LA CARRERA SE RESUELVE EN LA BASE, no en Python. Dos mecanicos pueden
    apretar "acepto" en el mismo segundo; si se leyera el estado, se decidiera y
    luego se escribiera, los dos ganarian. El UPDATE condicional
    --`WHERE tecnico_acepta_id IS NULL`-- hace que solo uno cambie una fila, y el
    otro se entera por el conteo.

    El RECHAZO tambien se guarda, con su motivo. Es lo que permite al supervisor
    escalar cuando nadie puede (CU-SUP-07): sin las negativas escritas, "nadie
    contesto" y "todos dijeron que no" se ven igual.
    """
    t = _tecnico(db, usuario.id)
    o = db.query(m.OrdenAuxilio).filter(m.OrdenAuxilio.id == orden_id).first()
    if not o:
        raise HTTPException(404, "No existe esa orden de auxilio.")
    if not (db.query(m.DifusionAuxilio)
            .filter(m.DifusionAuxilio.orden_auxilio_id == o.id,
                    m.DifusionAuxilio.tecnico_id == t.id).first()):
        raise HTTPException(403, "Ese auxilio no se te difundio.")
    if (db.query(m.RespuestaAuxilio)
            .filter(m.RespuestaAuxilio.orden_auxilio_id == o.id,
                    m.RespuestaAuxilio.tecnico_id == t.id).first()):
        raise HTTPException(409, "Ya respondiste a ese auxilio.")

    db.add(m.RespuestaAuxilio(orden_auxilio_id=o.id, tecnico_id=t.id,
                              puede_atender=acepto,
                              motivo_negativa=(motivo or "").strip() or None))
    if not acepto:
        db.commit()
        return {"orden_id": o.id, "tomado": False, "estado": o.estado}

    tomadas = (db.query(m.OrdenAuxilio)
               .filter(m.OrdenAuxilio.id == o.id,
                       m.OrdenAuxilio.tecnico_acepta_id.is_(None))
               .update({"tecnico_acepta_id": t.id,
                        "fecha_aceptacion": ahora_utc(),
                        "estado": "aceptada"}, synchronize_session=False))
    db.commit()
    if not tomadas:
        db.refresh(o)
        raise HTTPException(409, "Otro mecanico lo tomo primero. Tu respuesta queda "
                                 "registrada, pero el auxilio ya tiene quien lo atienda.")

    db.refresh(o)
    r = db.query(m.ReporteAveria).filter(m.ReporteAveria.id == o.reporte_averia_id).first()
    if r:
        notificar(db, r.chofer_id, "Ya hay mecanico en camino",
                  f"{t.nombre} {t.apellidos} acepto tu auxilio.",
                  "auxilio", "orden_auxilio", o.id)
        if r.supervisor_notificado_id:
            notificar(db, r.supervisor_notificado_id, "Auxilio aceptado",
                      f"{t.nombre} {t.apellidos} va a la unidad "
                      f"{r.unidad.num_economico if r.unidad else '-'}.",
                      "auxilio", "orden_auxilio", o.id)
    registrar_bitacora(db, usuario.id, "aceptar_auxilio", "orden_auxilio", o.id)
    db.commit()
    return {"orden_id": o.id, "tomado": True, "estado": o.estado}


# --------------------------------------------------------------- CU-MEC-09 -- #
@router.post("/auxilios/{orden_id}/ubicacion")
def transmitir_ubicacion(orden_id: int, latitud: float, longitud: float,
                         db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """Mi posicion, para que el chofer sepa que vengo y por donde.

    Se guarda la ULTIMA, no el historial: al chofer parado en la carretera le
    sirve saber donde viene el mecanico ahora, no por donde paso. El historial
    completo solo existe para el arrastre, donde se necesita como prueba.
    """
    t = _tecnico(db, usuario.id)
    # Una coordenada imposible es peor que ninguna: manda al chofer a mirar un
    # punto que no existe en vez de decirle que no se sabe donde viene.
    if not (-90 <= latitud <= 90) or not (-180 <= longitud <= 180):
        raise HTTPException(400, "Esa ubicacion no es valida. Si el telefono no da "
                                 "senal de GPS, no mandes nada: es mejor que el chofer "
                                 "sepa que no se sabe, que verte en otro continente.")
    o = db.query(m.OrdenAuxilio).filter(m.OrdenAuxilio.id == orden_id).first()
    if not o:
        raise HTTPException(404, "No existe esa orden de auxilio.")
    if o.tecnico_acepta_id != t.id:
        raise HTTPException(403, "Ese auxilio no es tuyo.")
    o.latitud = latitud
    o.longitud = longitud
    o.ubicacion_en = ahora_utc()
    if o.estado == "aceptada":
        o.estado = "en_ruta"
    db.commit()
    return {"orden_id": o.id, "estado": o.estado,
            "latitud": o.latitud, "longitud": o.longitud}


# --------------------------------------------------------------- CU-MEC-10 -- #
@router.post("/auxilios/{orden_id}/cerrar")
def cerrar_auxilio(orden_id: int, resuelto_en_sitio: bool, nota: str | None = None,
                   db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """Se arreglo en el sitio, o no.

    La diferencia manda: si se resolvio, la unidad sigue su ruta y ahi se acaba.
    Si no, alguien tiene que mandar grua --CU-MEC-11-- y el reporte se queda
    abierto. Cerrar sin decir cual de las dos fue deja a la unidad en el limbo.
    """
    t = _tecnico(db, usuario.id)
    o = db.query(m.OrdenAuxilio).filter(m.OrdenAuxilio.id == orden_id).first()
    if not o:
        raise HTTPException(404, "No existe esa orden de auxilio.")
    if o.tecnico_acepta_id != t.id:
        raise HTTPException(403, "Ese auxilio no es tuyo.")
    if o.estado in CERRADOS:
        raise HTTPException(409, "Ese auxilio ya estaba cerrado.")

    o.fecha_llegada = o.fecha_llegada or ahora_utc()
    o.fecha_cierre = ahora_utc()
    o.resuelto_en_sitio = resuelto_en_sitio
    o.estado = "resuelta" if resuelto_en_sitio else "escalada_a_arrastre"

    r = db.query(m.ReporteAveria).filter(m.ReporteAveria.id == o.reporte_averia_id).first()
    if r and resuelto_en_sitio:
        r.estado = "cerrado"
        # El desenlace NO SE PISA, solo se rellena si viene vacio.
        #
        # El desenlace guarda la DECISION del despacho, no quien acabo yendo.
        # Escribir "mecanico" siempre convertia cada llantero resuelto en sitio
        # en un mecanico en el corte del mes -- y pasa de verdad, porque la
        # difusion no filtra por oficio y cualquier autonomo puede tomar una
        # orden de llantero.
        #
        # Se rellena, en vez de no tocarlo nunca, porque hoy `despachar` es el
        # unico que levanta ordenes de auxilio y siempre deja desenlace; el dia
        # que el chofer pueda pedir auxilio directo (CU-CHO-14) la orden nacera
        # sin el, y entonces esta linea es la que evita que el corte pierda el
        # caso.
        if not r.desenlace:
            r.desenlace = "mecanico"
    elif r:
        # NO SE PUDO: hay que DESTRABAR la averia, no solo anotarlo.
        #
        # Aqui habia un callejon sin salida. `despachar` bloquea con 409 si la
        # averia ya trae desenlace --"ya se despacho como 'mecanico'"-- asi que
        # el mecanico decia "hace falta grua" y el administrador no podia
        # mandarla: la unidad se quedaba tirada sin ninguna salida.
        #
        # Se limpia el desenlace y vuelve a "abierto", o sea que vuelve a la
        # cola de despacho. No se pierde nada de lo ocurrido: la ORDEN DE
        # AUXILIO queda con su estado `escalada_a_arrastre`, su hora de cierre y
        # quien fue, que es el historial de que si se intento primero con
        # mecanico.
        r.desenlace = None
        r.estado = "abierto"
        r.despachado_por_usuario_id = None
        r.fecha_despacho = None
    detalle = ((f"{t.nombre} {t.apellidos} resolvio el auxilio en sitio."
                if resuelto_en_sitio
                else f"{t.nombre} {t.apellidos} NO pudo resolverlo en sitio: hace falta grua. "
                     "La averia volvio a la cola de despacho.")
               + (f" {nota}" if nota else ""))
    if r:
        notificar(db, r.chofer_id, "Auxilio cerrado", detalle,
                  "auxilio", "orden_auxilio", o.id)
        if r.supervisor_notificado_id:
            notificar(db, r.supervisor_notificado_id,
                      "Auxilio resuelto" if resuelto_en_sitio else "Hace falta grua",
                      detalle, "auxilio", "orden_auxilio", o.id)
    if not resuelto_en_sitio:
        # Quien despacha es el administrador, asi que es a quien le toca el
        # siguiente movimiento. Avisarle solo al supervisor dejaria la unidad
        # esperando a que alguien se asomara a la pantalla.
        for u in (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
                  .filter(m.Rol.nombre == "administrador").all()):
            notificar(db, u.id, "Hace falta grua", detalle,
                      "averia", "reporte_averia", r.id if r else None)
    registrar_bitacora(db, usuario.id, "cerrar_auxilio", "orden_auxilio", o.id, detalle)
    db.commit()
    return {"orden_id": o.id, "estado": o.estado,
            "resuelto_en_sitio": o.resuelto_en_sitio,
            "vuelve_a_despacho": not resuelto_en_sitio}


# --------------------------------------------------------------- CU-MEC-11 -- #
@router.post("/traslados", status_code=201)
def enviar_a_alamos(unidad_id: int, motivo: str, requiere_grua: bool = True,
                    db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    """Pide mandar la unidad a Alamos. Lo autoriza Erick (CU-ADM-25).

    El mecanico de la planta satelite NO decide el traslado: lo PIDE. Mover una
    unidad entre plantas ocupa una grua y un cajon en Alamos, y esa capacidad no
    es suya. Por eso nace en "solicitado" y no en "autorizado".
    """
    t = _tecnico(db, usuario.id)
    if not (motivo or "").strip():
        raise HTTPException(400, "Escribe por que hay que mandarla a Alamos.")
    if not t.taller_id:
        raise HTTPException(409, "Tu ficha de tecnico no tiene taller de origen.")
    unidad = db.query(m.Unidad).filter(m.Unidad.id == unidad_id).first()
    if not unidad:
        raise HTTPException(404, "Esa unidad no existe.")

    alamos = (db.query(m.Taller)
              .filter(func.upper(m.Taller.nombre).like("%ALAMOS%")).first())
    if not alamos:
        raise HTTPException(409, "No encuentro el taller de Alamos en el catalogo.")
    if alamos.id == t.taller_id:
        raise HTTPException(409, "Ya estas en Alamos: no hay nada que trasladar.")

    tr = m.TrasladoUnidad(unidad_id=unidad.id, taller_origen_id=t.taller_id,
                          taller_destino_id=alamos.id,
                          solicitado_por_tecnico_id=t.id,
                          motivo=motivo.strip(), requiere_grua=requiere_grua,
                          estado="solicitado")
    db.add(tr)
    db.flush()
    detalle = (f"{t.nombre} {t.apellidos} pide trasladar la unidad "
               f"{unidad.num_economico} a Alamos: {motivo.strip()}")
    for u in (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
              .filter(m.Rol.nombre == "administrador").all()):
        notificar(db, u.id, "Traslado por autorizar", detalle,
                  "traslado", "traslado_unidad", tr.id)
    registrar_bitacora(db, usuario.id, "solicitar_traslado", "traslado_unidad",
                       tr.id, detalle)
    db.commit()
    return {"id": tr.id, "estado": tr.estado, "requiere_grua": tr.requiere_grua}


@router.get("/traslados")
def mis_traslados(db: Session = Depends(get_db), usuario=Depends(solo_mec)):
    t = _tecnico(db, usuario.id)
    fuera = []
    for tr in (db.query(m.TrasladoUnidad)
               .filter(m.TrasladoUnidad.solicitado_por_tecnico_id == t.id)
               .order_by(m.TrasladoUnidad.fecha_solicitud.desc()).all()):
        u = db.query(m.Unidad).filter(m.Unidad.id == tr.unidad_id).first()
        fuera.append({
            "id": tr.id, "unidad": u.num_economico if u else "-",
            "motivo": tr.motivo, "estado": tr.estado,
            "requiere_grua": tr.requiere_grua,
            "fecha_solicitud": tr.fecha_solicitud,
            "motivo_rechazo": tr.motivo_rechazo,
            "autorizado_por": (nombre_usuario(db, tr.autorizado_por_usuario_id)
                               if tr.autorizado_por_usuario_id else None),
        })
    return fuera


# --------------------------------------------------------------- CU-MEC-12 -- #
@router.get("/unidades")
def buscar_unidades(q: str = "", limite: int = 8, db: Session = Depends(get_db),
                    usuario=Depends(solo_mec)):
    """Para nombrar la unidad al pedir un traslado. Mismo buscador que los demas."""
    _tecnico(db, usuario.id)
    return comun.buscar_unidades(db, q, limite)


@router.get("/reportes/{reporte_id}/salida")
def formato_de_salida(reporte_id: int, db: Session = Depends(get_db),
                      usuario=Depends(solo_mec)):
    """El formato para imprimir y firmar al entregar la unidad.

    Es de LECTURA. El mecanico autonomo no cierra el formato --eso es CU-ADM-29,
    con sus dos firmas de salida-- pero si necesita el papel para entregarlo. Se
    le muestra solo si tiene trabajo en el, que es lo que le da derecho a verlo.
    """
    t = _tecnico(db, usuario.id)
    r = (db.query(m.ReporteMantenimiento)
         .filter(m.ReporteMantenimiento.id == reporte_id).first())
    if not r:
        raise HTTPException(404, "No existe ese formato.")
    mias = [a for a in r.actividades if a.tecnico_id == t.id]
    if not mias:
        raise HTTPException(403, "No tienes trabajo asignado en ese formato.")
    u = db.query(m.Unidad).filter(m.Unidad.id == r.unidad_id).first()
    tal = db.query(m.Taller).filter(m.Taller.id == r.taller_id).first()
    return {
        "reporte_id": r.id, "folio": r.folio, "estado": r.estado,
        "unidad": u.num_economico if u else "-",
        "taller": tal.nombre if tal else None,
        "tipo_servicio": r.tipo_servicio,
        "kilometraje": r.kilometraje,
        "fecha_entrada": r.fecha_entrada, "fecha_salida": r.fecha_salida,
        "chofer_nombre": r.chofer_nombre,
        "mis_actividades": [{
            "sistema": a.sistema, "a_realizar": a.a_realizar,
            "realizada": a.realizada, "terminada": bool(a.fecha_realizada),
        } for a in mias],
        "todas_mis_actividades_terminadas": all(a.fecha_realizada for a in mias),
        # Quien lo cierra es el administrador: el mecanico entrega, no sella.
        "lo_cierra": "El administrador del taller, con las dos firmas de salida.",
    }
