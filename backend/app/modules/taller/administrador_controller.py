"""Modulo Administrador de taller - CU-ADM-01 a CU-ADM-16 y CU-ADM-26 a 29.

v1.1: absorbe la captura del trabajo del mecanico (CU-ADM-11 a 16), porque los
mecanicos no usan la aplicacion. Todo dato capturado guarda doble responsable (RN-11).

v1.3: el REPORTE DE MANTENIMIENTO (CU-ADM-26 a 29), el formato de papel que se
llena en la pluma de Alamos. Ver modules/ordenes/reporte_model.py.
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ... import models as m
from ... import services as svc
from ...core.database import get_db
from ...schemas import (ActividadesIn, AsignacionTecnicoIn, AsignacionTecnicoOut, AvanceIn,
                       CapturaDiagnosticoIn, CatalogoReporteOut, CierreReporteIn,
                       FirmaReporteIn, FormatoSalidaIn, MensajeOut, OrdenServicioOut,
                       PresupuestoIn, PresupuestoOut, ReasignacionIn,
                       ReporteMantenimientoIn, ReporteMantenimientoOut,
                       ResolucionSolicitudIn, SolicitudOut, TallerOut,
                       ApoyoOut, AveriaOut, DespachoIn)
from ...core.security import notificar, registrar_bitacora, require_roles
from ...core.tiempo import TZ_OPERACION, a_utc, ahora_utc
from .exportar_resumen import construir as construir_resumen
from .indicadores import calcular as calcular_indicadores

router = APIRouter(prefix="/api/admin", tags=["administrador"])
solo_admin = require_roles("administrador")


# ---------------------------------------------------------------- CU-ADM-01 -- #
@router.get("/solicitudes", response_model=list[SolicitudOut])
def bandeja(estado: str | None = None, usuario=Depends(solo_admin),
            db: Session = Depends(get_db)):
    q = db.query(m.SolicitudIngreso)
    if estado:
        q = q.filter(m.SolicitudIngreso.estado == estado)
    orden = {"critica": 0, "alta": 1, "media": 2, "baja": 3}
    ss = q.order_by(m.SolicitudIngreso.fecha_solicitud.desc()).all()
    ss.sort(key=lambda s: (orden.get(s.urgencia, 9), s.fecha_solicitud))
    return [svc.solicitud_out(db, s) for s in ss]


@router.post("/solicitudes/{sol_id}/resolver", response_model=SolicitudOut)
def resolver_solicitud(sol_id: int, datos: ResolucionSolicitudIn, usuario=Depends(solo_admin),
                       db: Session = Depends(get_db)):
    """CU-ADM-01 con «include» CU-ADM-02: nunca se decide sin verificar espacios (RN-06)."""
    s = db.query(m.SolicitudIngreso).filter(m.SolicitudIngreso.id == sol_id).first()
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    if s.estado not in ("pendiente", "en_cola"):
        raise HTTPException(409, f"La solicitud ya esta '{s.estado}'")

    s.atendida_por_admin_id = usuario.id
    s.fecha_respuesta = ahora_utc()

    if not datos.aceptar:
        if datos.dejar_en_cola:
            s.estado = "en_cola"
            notificar(db, s.chofer_id, "Solicitud en cola",
                      f"No hay espacio libre compatible. Unidad {s.unidad.num_economico} "
                      "queda en cola.", "solicitud", "solicitud_ingreso", s.id)
        else:
            if not datos.motivo_rechazo:
                raise HTTPException(400, "RN-06: el rechazo exige motivo")
            s.estado = "rechazada"
            s.motivo_rechazo = datos.motivo_rechazo
            notificar(db, s.chofer_id, "Solicitud rechazada", datos.motivo_rechazo,
                      "solicitud", "solicitud_ingreso", s.id)
        db.commit()
        db.refresh(s)
        return svc.solicitud_out(db, s)

    # --- aceptar: la unidad no puede estar ya adentro (RI-D-32 / RI-B-23) ---
    # Hay un solo vehiculo fisico: si el chofer mando varias solicitudes y se
    # aceptan dos, la unidad quedaria en dos espacios a la vez. El indice unico
    # parcial lo impide en la base; esto lo impide antes, con un mensaje util.
    abierta = (db.query(m.OrdenServicio)
               .filter(m.OrdenServicio.unidad_id == s.unidad_id,
                       m.OrdenServicio.fecha_salida.is_(None))
               .first())
    if abierta:
        taller_nombre = abierta.taller.nombre if abierta.taller else "otro taller"
        raise HTTPException(
            409,
            f"La unidad {s.unidad.num_economico} ya esta en el taller de {taller_nombre} "
            f"con la orden {abierta.folio}. Cierrala antes de aceptar otro ingreso.")

    # --- verificar espacio compatible (RN-06 / RI-04) ---
    libres = svc.espacios_libres_compatibles(db, s.taller_id, s.unidad.tipo_unidad_id)
    if not libres:
        raise HTTPException(409, "RN-06: no hay espacio libre compatible con el tipo de unidad. "
                                 "Deja la solicitud en cola o rechazala con motivo.")
    espacio = None
    if datos.espacio_id:
        espacio = next((e for e in libres if e.id == datos.espacio_id), None)
        if not espacio:
            raise HTTPException(409, "Ese espacio no esta libre o no admite este tipo de unidad")
    else:
        espacio = libres[0]

    orden = m.OrdenServicio(folio=svc.siguiente_folio(db, m.OrdenServicio, "OS"),
                            unidad_id=s.unidad_id, taller_id=s.taller_id, solicitud_id=s.id,
                            chofer_responsable_id=s.chofer_id, tipo=s.tipo,
                            km_entrada=s.unidad.km_actual, abierta_por_admin_id=usuario.id)
    db.add(orden)
    db.flush()

    db.add(m.OcupacionEspacio(espacio_id=espacio.id, unidad_id=s.unidad_id,
                              orden_servicio_id=orden.id, colocado_por_admin_id=usuario.id))
    espacio.estado = "ocupado"
    s.unidad.estado = "en_taller"
    s.unidad.taller_actual_id = s.taller_id
    s.estado = "aceptada"

    # Las demas solicitudes vivas de la MISMA unidad ya no tienen sentido: el
    # vehiculo acaba de entrar. Se cierran solas para que ningun otro
    # administrador las acepte por segunda vez.
    hermanas = (db.query(m.SolicitudIngreso)
                .filter(m.SolicitudIngreso.unidad_id == s.unidad_id,
                        m.SolicitudIngreso.id != s.id,
                        m.SolicitudIngreso.estado.in_(("pendiente", "en_cola")))
                .all())
    for otra in hermanas:
        otra.estado = "rechazada"
        otra.motivo_rechazo = (f"La unidad ingreso por la solicitud #{s.id} "
                               f"(orden {orden.folio}). Solicitud duplicada.")
        otra.atendida_por_admin_id = usuario.id
        otra.fecha_respuesta = ahora_utc()
    if hermanas:
        notificar(db, s.chofer_id, "Solicitudes duplicadas cerradas",
                  f"Tu unidad {s.unidad.num_economico} ya entro al taller. "
                  f"Se cerraron {len(hermanas)} solicitud(es) repetida(s).",
                  "solicitud", "unidad", s.unidad_id)

    # Si el ingreso corresponde a un mantenimiento pendiente, se marca cumplido.
    prog = (db.query(m.ProgramaMantenimiento)
            .filter(m.ProgramaMantenimiento.unidad_id == s.unidad_id,
                    m.ProgramaMantenimiento.estado == "pendiente")
            .order_by(m.ProgramaMantenimiento.fecha_limite).first())
    if prog and s.tipo == "preventivo":
        prog.estado = "cumplido"
        prog.fecha_cumplimiento = ahora_utc()
        prog.orden_servicio_id = orden.id

    # CU-ADM-26: el formato nace AQUI, cuando se le da acceso al vehiculo, y se
    # queda abierto. Antes habia que acordarse de levantarlo a mano y el papel
    # existia siempre pero el registro no: quedaban unidades adentro del taller
    # sin formato, que es justo lo que el formato existe para evitar.
    reporte = svc.crear_reporte_mantenimiento(
        db, unidad=s.unidad, taller_id=s.taller_id, admin_id=usuario.id, orden=orden,
        tipo_servicio="preventivo" if s.tipo == "preventivo" else "correctivo",
        origen=s.taller.nombre if s.taller else None,
        chofer_id=s.chofer_id, notas_ingreso=s.descripcion_falla)

    notificar(db, s.chofer_id, "Solicitud aceptada",
              f"Unidad {s.unidad.num_economico} en {espacio.zona.nombre} {espacio.numero}. "
              f"Orden {orden.folio}", "solicitud", "orden_servicio", orden.id)
    registrar_bitacora(db, usuario.id, "solicitud_aceptada", "solicitud_ingreso", s.id,
                       f"orden={orden.folio} espacio={espacio.id} reporte={reporte.folio}")
    db.commit()
    db.refresh(s)
    return svc.solicitud_out(db, s)


# ------------------------------------------------------------- CU-ADM-02/03 -- #
@router.get("/taller/{taller_id}", response_model=TallerOut)
def plano_taller(taller_id: int, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    t = db.query(m.Taller).filter(m.Taller.id == taller_id).first()
    if not t:
        raise HTTPException(404, "Taller no encontrado")
    zonas, total, ocupados = [], 0, 0
    for z in sorted(t.zonas, key=lambda x: x.orden):
        esp = []
        for e in sorted(z.espacios, key=lambda x: (len(x.numero), x.numero)):
            ocup = svc.ocupacion_abierta_de_espacio(db, e.id)
            dias = (ahora_utc() - ocup.fecha_entrada).days if ocup else None
            esp.append({
                "id": e.id, "numero": e.numero, "zona": z.nombre, "estado": e.estado,
                "tipo_permitido": e.tipo_permitido.nombre if e.tipo_permitido else None,
                "unidad": ocup.unidad.num_economico if ocup else None,
                "orden_servicio_id": ocup.orden_servicio_id if ocup else None,
                "dias_ocupado": dias, "pos_x": e.pos_x, "pos_y": e.pos_y,
            })
            if z.cuenta_para_ocupacion:
                total += 1
                if e.estado == "ocupado":
                    ocupados += 1
        zonas.append({"id": z.id, "nombre": z.nombre, "proposito": z.proposito,
                      "cuenta_para_ocupacion": z.cuenta_para_ocupacion, "espacios": esp})
    return {"id": t.id, "nombre": t.nombre, "direccion": t.direccion, "zonas": zonas,
            "total_operativos": total, "ocupados": ocupados, "libres": total - ocupados}


@router.get("/talleres")
def talleres(usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    return [{"id": t.id, "nombre": t.nombre} for t in db.query(m.Taller).all()]


# ---------------------------------------------------------------- CU-ADM-04 -- #
@router.post("/espacios/{espacio_id}/retirar", response_model=MensajeOut)
def retirar_unidad(espacio_id: int, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    ocup = svc.ocupacion_abierta_de_espacio(db, espacio_id)
    if not ocup:
        raise HTTPException(404, "Ese espacio no tiene una unidad")
    ocup.fecha_salida = ahora_utc()
    ocup.retirado_por_admin_id = usuario.id
    ocup.espacio.estado = "libre"
    registrar_bitacora(db, usuario.id, "unidad_retirada_de_espacio", "espacio", espacio_id)
    db.commit()
    return {"mensaje": "Unidad retirada del espacio"}


@router.post("/espacios/{espacio_id}/mover/{orden_id}", response_model=MensajeOut)
def mover_unidad(espacio_id: int, orden_id: int, usuario=Depends(solo_admin),
                 db: Session = Depends(get_db)):
    """Mueve la unidad de una orden abierta a otro espacio (RI-02, RI-03, RI-04)."""
    orden = db.query(m.OrdenServicio).filter(m.OrdenServicio.id == orden_id).first()
    espacio = db.query(m.Espacio).filter(m.Espacio.id == espacio_id).first()
    if not orden or not espacio:
        raise HTTPException(404, "Orden o espacio no encontrado")
    if espacio.estado != "libre":
        raise HTTPException(409, "El espacio destino esta ocupado")
    if (espacio.tipo_unidad_permitido_id
            and espacio.tipo_unidad_permitido_id != orden.unidad.tipo_unidad_id):
        raise HTTPException(409, "RI-04: ese espacio no admite este tipo de unidad")
    actual = svc.ocupacion_abierta_de_unidad(db, orden.unidad_id)
    if actual:
        actual.fecha_salida = ahora_utc()
        actual.retirado_por_admin_id = usuario.id
        actual.espacio.estado = "libre"
    db.add(m.OcupacionEspacio(espacio_id=espacio.id, unidad_id=orden.unidad_id,
                              orden_servicio_id=orden.id, colocado_por_admin_id=usuario.id))
    espacio.estado = "ocupado"
    db.commit()
    return {"mensaje": f"Unidad movida a {espacio.zona.nombre} {espacio.numero}"}


# ------------------------------------------------------------- CU-ADM-05/06 -- #
@router.get("/ordenes", response_model=list[OrdenServicioOut])
def ordenes(abiertas: bool = True, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    q = db.query(m.OrdenServicio)
    if abiertas:
        q = q.filter(m.OrdenServicio.estado != "cerrada")
    return [svc.orden_out(db, o) for o in
            q.order_by(m.OrdenServicio.fecha_entrada.desc()).all()]


@router.get("/ordenes/{orden_id}", response_model=OrdenServicioOut)
def orden(orden_id: int, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    o = db.query(m.OrdenServicio).filter(m.OrdenServicio.id == orden_id).first()
    if not o:
        raise HTTPException(404, "Orden no encontrada")
    return svc.orden_out(db, o)


@router.post("/ordenes/{orden_id}/asignar", response_model=AsignacionTecnicoOut, status_code=201)
def asignar_tecnico(orden_id: int, datos: AsignacionTecnicoIn, usuario=Depends(solo_admin),
                    db: Session = Depends(get_db)):
    """CU-ADM-05: la fila de especialistas, como procesos esperando."""
    o = db.query(m.OrdenServicio).filter(m.OrdenServicio.id == orden_id).first()
    t = db.query(m.Tecnico).filter(m.Tecnico.id == datos.tecnico_id).first()
    if not o or not t:
        raise HTTPException(404, "Orden o tecnico no encontrado")
    ultimo = max([a.orden_en_cola for a in o.asignaciones], default=0)
    a = m.AsignacionTecnico(orden_servicio_id=o.id, tecnico_id=t.id,
                            especialidad=datos.especialidad or t.especialidad,
                            orden_en_cola=ultimo + 1, asignado_por_admin_id=usuario.id)
    db.add(a)
    if o.estado == "abierta":
        o.estado = "diagnostico"
    db.commit()
    db.refresh(a)
    return svc.asignacion_out(db, a)


@router.post("/asignaciones/{asig_id}/mover", response_model=MensajeOut)
def reordenar_cola(asig_id: int, direccion: str, usuario=Depends(solo_admin),
                   db: Session = Depends(get_db)):
    """CU-ADM-06 «extend» de CU-ADM-05."""
    a = db.query(m.AsignacionTecnico).filter(m.AsignacionTecnico.id == asig_id).first()
    if not a:
        raise HTTPException(404, "Asignacion no encontrada")
    delta = -1 if direccion == "arriba" else 1
    vecino = (db.query(m.AsignacionTecnico)
              .filter(m.AsignacionTecnico.orden_servicio_id == a.orden_servicio_id,
                      m.AsignacionTecnico.orden_en_cola == a.orden_en_cola + delta).first())
    if not vecino:
        raise HTTPException(409, "No se puede mover mas en esa direccion")
    a.orden_en_cola, vecino.orden_en_cola = vecino.orden_en_cola, a.orden_en_cola
    db.commit()
    return {"mensaje": "Cola reordenada"}


# ------------------------------------------------------ CU-ADM-11/14 (v1.1) -- #
@router.post("/asignaciones/{asig_id}/diagnostico", response_model=AsignacionTecnicoOut)
def capturar_diagnostico(asig_id: int, datos: CapturaDiagnosticoIn, usuario=Depends(solo_admin),
                         db: Session = Depends(get_db)):
    """CU-ADM-11: el administrador teclea lo que el mecanico le entrego (RN-11)."""
    a = db.query(m.AsignacionTecnico).filter(m.AsignacionTecnico.id == asig_id).first()
    if not a:
        raise HTTPException(404, "Asignacion no encontrada")
    a.diagnostico = datos.diagnostico
    a.capturado_por_admin_id = usuario.id
    a.fecha_captura = ahora_utc()
    registrar_bitacora(db, usuario.id, "diagnostico_capturado", "asignacion_tecnico", a.id,
                       f"tecnico={a.tecnico.nombre_completo}")
    db.commit()
    db.refresh(a)
    return svc.asignacion_out(db, a)


@router.post("/asignaciones/{asig_id}/avance", response_model=AsignacionTecnicoOut)
def registrar_avance(asig_id: int, datos: AvanceIn, usuario=Depends(solo_admin),
                     db: Session = Depends(get_db)):
    """CU-ADM-14: inicio, avance y termino de la reparacion."""
    a = db.query(m.AsignacionTecnico).filter(m.AsignacionTecnico.id == asig_id).first()
    if not a:
        raise HTTPException(404, "Asignacion no encontrada")
    if datos.estado == "en_proceso" and not a.fecha_inicio:
        a.fecha_inicio = ahora_utc()
        a.orden.estado = "en_reparacion"
        a.orden.unidad.estado = "en_reparacion"
    if datos.estado == "terminada":
        a.fecha_fin = ahora_utc()
    a.estado = datos.estado
    if datos.trabajo_realizado:
        a.trabajo_realizado = datos.trabajo_realizado
    a.capturado_por_admin_id = usuario.id
    a.fecha_captura = ahora_utc()
    if all(x.estado == "terminada" for x in a.orden.asignaciones):
        a.orden.estado = "terminada"
    db.commit()
    db.refresh(a)
    return svc.asignacion_out(db, a)


# ---------------------------------------------------------------- CU-ADM-15 -- #
# ------------------------------------------------------------- CU-ADM-15b -- #
# ------------------------------------------------------------- CU-ADM-15c -- #
def _nombre_taller(db: Session, taller_id: int | None) -> str | None:
    """El id que manda la pantalla -> el nombre con el que el area etiqueta sus
    movimientos. Se resuelve aqui y no en el cliente: el resto de la aplicacion
    habla de talleres por id, y dejar que el navegador mande un nombre libre
    invitaria a que un cambio de mayusculas rompiera el filtro en silencio."""
    if not taller_id:
        return None
    t = db.query(m.Taller).filter(m.Taller.id == taller_id).first()
    return t.nombre if t else None


@router.get("/indicadores")
def indicadores(taller_id: int | None = None, usuario=Depends(solo_admin),
                db: Session = Depends(get_db)):
    """Los numeros del taller para las graficas de pantalla.

    Salen de la MISMA funcion que arma el Excel. Es a proposito: el area tiene
    hoy una hoja Graficos que no cuadra con su hoja RESUMEN --de donde deberia
    salir-- porque los cuatro indicadores se copian a mano de una a otra.
    """
    return calcular_indicadores(db, _nombre_taller(db, taller_id))


@router.get("/exportar/resumen")
def exportar_resumen(taller_id: int | None = None, usuario=Depends(solo_admin),
                     db: Session = Depends(get_db)):
    """El Excel del taller, con las secciones que el area ya conoce.

    Sustituye el RESUMEN.xlsx que hoy se lleva a mano. Los totales salen como
    formula y los conteos se calculan de los movimientos, asi que no puede
    repetirse el error de dedo que tenian: al 27 de agosto su hoja decia 3 y 4
    en refacciones chinas y talleres externos, y su propia hoja PATIO decia 4 y
    3. El total cuadraba, y por eso nadie lo vio.
    """
    datos = construir_resumen(db, _nombre_taller(db, taller_id))
    nombre = f"Resumen taller {date.today():%Y-%m-%d}.xlsx"
    registrar_bitacora(db, usuario.id, "resumen_exportado", "taller", None, nombre)
    db.commit()
    return Response(
        content=datos,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/hoja-de-trabajo/{taller_id}")
def hoja_de_trabajo(taller_id: int, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """CU-ADM-15: la cola del dia para imprimir y entregar a los tecnicos en papel.

    Nace del cambio v1.1: sin app, el mecanico necesita su cola en fisico.
    """
    ordenes = (db.query(m.OrdenServicio)
               .filter(m.OrdenServicio.taller_id == taller_id,
                       m.OrdenServicio.estado.notin_(["cerrada", "terminada"])).all())
    por_tecnico = {}
    for o in ordenes:
        ocup = svc.ocupacion_abierta_de_unidad(db, o.unidad_id)
        espacio = (f"{ocup.espacio.zona.nombre} {ocup.espacio.numero}") if ocup else "-"
        for a in sorted(o.asignaciones, key=lambda x: x.orden_en_cola):
            if a.estado == "terminada":
                continue
            key = a.tecnico.nombre_completo if a.tecnico else "Sin asignar"
            por_tecnico.setdefault(key, {
                "tecnico": key,
                "especialidad": a.tecnico.especialidad if a.tecnico else "-",
                "trabajos": []})
            por_tecnico[key]["trabajos"].append({
                "orden": o.folio, "unidad": o.unidad.num_economico, "espacio": espacio,
                "posicion": a.orden_en_cola, "estado": a.estado,
                "diagnostico": a.diagnostico,
            })
    t = db.query(m.Taller).filter(m.Taller.id == taller_id).first()
    # El nombre del taller va en la respuesta porque la hoja IMPRESA tiene que
    # decir de donde es: en el piso circulan seis hojas parecidas.
    return {"taller_id": taller_id, "taller": t.nombre if t else "-",
            "generado": ahora_utc(), "tecnicos": list(por_tecnico.values())}


# --------------------------------------------------- CU-ADM-12/13 (v1.1) ---- #
@router.post("/presupuestos", response_model=PresupuestoOut, status_code=201)
def capturar_presupuesto(datos: PresupuestoIn, usuario=Depends(solo_admin),
                         db: Session = Depends(get_db)):
    """CU-ADM-12 con «include» CU-ADM-13.

    El mecanico lo elabora en papel; el administrador lo captura. Quedan los dos
    responsables (RN-11) y la diferencia de fechas mide el retraso de captura.
    """
    o = db.query(m.OrdenServicio).filter(
        m.OrdenServicio.id == datos.orden_servicio_id).first()
    t = db.query(m.Tecnico).filter(m.Tecnico.id == datos.tecnico_elaboro_id).first()
    if not o or not t:
        raise HTTPException(404, "Orden o tecnico no encontrado")
    if datos.fecha_elaboracion > ahora_utc().date():
        raise HTTPException(400, "RI-11: la fecha del papel no puede ser futura")

    p = m.Presupuesto(folio=svc.siguiente_folio(db, m.Presupuesto, "PRE"),
                      orden_servicio_id=o.id, tecnico_elaboro_id=t.id,
                      capturado_por_admin_id=usuario.id,
                      fecha_elaboracion=datos.fecha_elaboracion,
                      folio_papel=datos.folio_papel,
                      costo_mano_obra=datos.costo_mano_obra, diagnostico=datos.diagnostico,
                      dias_estimados_reparacion=datos.dias_estimados_reparacion,
                      estado="capturado")
    db.add(p)
    db.flush()

    subtotal = 0.0
    for d in datos.detalles:
        importe = float(d.cantidad) * float(d.precio_unitario)
        subtotal += importe
        db.add(m.DetallePresupuesto(presupuesto_id=p.id, pieza_id=d.pieza_id,
                                    descripcion_libre=d.descripcion_libre,
                                    cantidad=d.cantidad, precio_unitario=d.precio_unitario,
                                    importe=importe,
                                    disponible_en_almacen=d.disponible_en_almacen))
    p.subtotal_piezas = subtotal
    p.total = subtotal + float(datos.costo_mano_obra or 0)
    o.estado = "espera_presupuesto"
    registrar_bitacora(db, usuario.id, "presupuesto_capturado", "presupuesto", p.id,
                       f"tecnico={t.nombre_completo} total={p.total}")
    db.commit()
    db.refresh(p)
    return svc.presupuesto_out(db, p)


# ---------------------------------------------------------------- CU-ADM-07 -- #
@router.post("/presupuestos/{pre_id}/remitir", response_model=PresupuestoOut)
def remitir_al_gerente(pre_id: int, comentario: str = "", usuario=Depends(solo_admin),
                       db: Session = Depends(get_db)):
    """RN-07: el presupuesto solo llega al gerente pasando por el administrador."""
    p = db.query(m.Presupuesto).filter(m.Presupuesto.id == pre_id).first()
    if not p:
        raise HTTPException(404, "Presupuesto no encontrado")
    if p.estado not in ("capturado", "devuelto"):
        raise HTTPException(409, f"El presupuesto esta en estado '{p.estado}'")
    p.estado = "enviado_gerente"
    db.add(m.Autorizacion(presupuesto_id=p.id, usuario_id=usuario.id, nivel="administrador",
                          resultado="remitido", comentario=comentario))
    for g in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
            m.Rol.nombre == "gerente").all():
        notificar(db, g.id, "Presupuesto por autorizar",
                  f"{p.folio} - unidad {p.orden.unidad.num_economico} - $ {float(p.total):,.2f}",
                  "presupuesto", "presupuesto", p.id)
    db.commit()
    db.refresh(p)
    return svc.presupuesto_out(db, p)


@router.get("/presupuestos", response_model=list[PresupuestoOut])
def presupuestos(estado: str | None = None, usuario=Depends(solo_admin),
                 db: Session = Depends(get_db)):
    q = db.query(m.Presupuesto)
    if estado:
        q = q.filter(m.Presupuesto.estado == estado)
    return [svc.presupuesto_out(db, p) for p in
            q.order_by(m.Presupuesto.fecha_captura.desc()).all()]


# ---------------------------------------------------------------- CU-ADM-16 -- #
@router.post("/presupuestos/{pre_id}/avisar-tecnico", response_model=MensajeOut)
def avisar_al_tecnico(pre_id: int, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """CU-ADM-16: el aviso es verbal; el sistema solo deja constancia de que se dio."""
    p = db.query(m.Presupuesto).filter(m.Presupuesto.id == pre_id).first()
    if not p:
        raise HTTPException(404, "Presupuesto no encontrado")
    if p.estado not in ("aprobado", "rechazado", "devuelto"):
        raise HTTPException(409, "Todavia no hay resolucion que comunicar")
    p.fecha_aviso_al_tecnico = ahora_utc()
    registrar_bitacora(db, usuario.id, "aviso_verbal_al_tecnico", "presupuesto", p.id,
                       f"tecnico={p.tecnico.nombre_completo} resultado={p.estado}")
    db.commit()
    return {"mensaje": f"Constancia registrada: se aviso a {p.tecnico.nombre_completo}"}


# ---------------------------------------------------------------- CU-ADM-08 -- #
@router.post("/presupuestos/{pre_id}/orden-compra", response_model=MensajeOut)
def autorizar_orden_compra(pre_id: int, proveedor_id: int | None = None,
                           dias_entrega: int = 5, usuario=Depends(solo_admin),
                           db: Session = Depends(get_db)):
    """RI-07: no hay orden de compra sin presupuesto aprobado por gerencia."""
    from datetime import timedelta
    p = db.query(m.Presupuesto).filter(m.Presupuesto.id == pre_id).first()
    if not p:
        raise HTTPException(404, "Presupuesto no encontrado")
    if p.estado != "aprobado":
        raise HTTPException(409, "RI-07: el presupuesto debe estar aprobado por el gerente")
    oc = m.OrdenCompra(folio=svc.siguiente_folio(db, m.OrdenCompra, "OC"), presupuesto_id=p.id,
                       proveedor_id=proveedor_id, autorizada_por_admin_id=usuario.id,
                       estado="en_transito", total=p.subtotal_piezas,
                       fecha_estimada_llegada=(ahora_utc().date() +
                                               timedelta(days=dias_entrega)))
    db.add(oc)
    p.orden.estado = "espera_refacciones"
    registrar_bitacora(db, usuario.id, "orden_compra_autorizada", "orden_compra", None)
    db.commit()
    return {"mensaje": f"Orden de compra {oc.folio} autorizada"}


@router.get("/ordenes-compra")
def ordenes_compra(usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    out = []
    for oc in db.query(m.OrdenCompra).order_by(m.OrdenCompra.fecha_emision.desc()).all():
        out.append({"id": oc.id, "folio": oc.folio, "estado": oc.estado,
                    "unidad": oc.presupuesto.orden.unidad.num_economico,
                    "total": float(oc.total or 0),
                    "fecha_estimada_llegada": oc.fecha_estimada_llegada,
                    "proveedor": oc.proveedor.nombre if oc.proveedor else None})
    return out


@router.post("/ordenes-compra/{oc_id}/recibir", response_model=MensajeOut)
def recibir_orden_compra(oc_id: int, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    oc = db.query(m.OrdenCompra).filter(m.OrdenCompra.id == oc_id).first()
    if not oc:
        raise HTTPException(404, "Orden de compra no encontrada")
    oc.estado = "recibida"
    oc.fecha_recepcion = ahora_utc()
    oc.presupuesto.orden.estado = "en_reparacion"
    db.commit()
    return {"mensaje": "Piezas recibidas"}


# ---------------------------------------------------------------- CU-ADM-10 -- #
@router.post("/ordenes/{orden_id}/salida", response_model=MensajeOut)
def emitir_salida(orden_id: int, datos: FormatoSalidaIn, usuario=Depends(solo_admin),
                  db: Session = Depends(get_db)):
    o = db.query(m.OrdenServicio).filter(m.OrdenServicio.id == orden_id).first()
    if not o:
        raise HTTPException(404, "Orden no encontrada")
    if o.estado == "cerrada":
        raise HTTPException(409, "La orden ya esta cerrada")

    # La salida por el formato es la que usa la pantalla (CU-ADM-29). Esta
    # entrada se conserva para las ordenes que no tienen formato -- las
    # anteriores a v1.3 -- y hace exactamente lo mismo, por el mismo servicio.
    reporte = svc.reporte_abierto_de_unidad(db, o.unidad_id)
    if reporte:
        faltan = reporte.firmas_faltantes_para_salida()
        if faltan:
            etiquetas = {k: e for k, e, _ in m.FIRMAS}
            raise HTTPException(409, {
                "mensaje": f"El formato {reporte.folio} no puede cerrarse: faltan "
                           + ", ".join(etiquetas.get(x, x) for x in faltan),
                "reporte_id": reporte.id, "firmas_faltantes": faltan,
            })
        reporte.fecha_salida = ahora_utc()
        reporte.estado = "cerrado"
        reporte.cerrado_por_admin_id = usuario.id

    svc.sacar_del_taller(db, o, usuario.id,
                         unidad_operativa=datos.unidad_operativa,
                         operacion_a_realizar=datos.operacion_a_realizar)
    notificar(db, o.chofer_responsable_id, "Unidad lista",
              f"{o.unidad.num_economico} sale del taller. Orden {o.folio}", "salida")
    registrar_bitacora(db, usuario.id, "formato_salida_emitido", "orden_servicio", o.id)
    db.commit()
    return {"mensaje": f"Salida emitida para la orden {o.folio}"}


# ======================================================================== #
# CU-ADM-26 a 29 - REPORTE DE MANTENIMIENTO
#
# El formato de papel que hoy se llena a mano en la pluma de Alamos. Aqui se
# teclea igual que se lee: datos de la unidad, revision rapida, los diez
# sistemas y las cinco firmas.
#
# Regla de la pantalla: NUNCA reordenar ni renombrar los campos respecto al
# papel. Quien captura tiene la hoja al lado y va copiando de arriba a abajo;
# un orden distinto convierte una captura de dos minutos en una busqueda.
# ======================================================================== #

# `catalogo` va ANTES que `/reportes/{reporte_id}`: si se declara despues,
# FastAPI intenta convertir "catalogo" a int y responde 422 en vez de servirlo.
@router.get("/reportes/catalogo", response_model=CatalogoReporteOut)
def catalogo_reporte(usuario=Depends(solo_admin)):
    """Los catalogos del formato. La pantalla no los lleva escritos."""
    return {
        "sistemas": [{"clave": k, "etiqueta": e} for k, e in m.SISTEMAS],
        "puntos": [{"clave": k, "etiqueta": e} for k, e in m.PUNTOS_REVISION],
        "firmas": [{"clave": k, "etiqueta": e, "quien": q} for k, e, q in m.FIRMAS],
        "areas": m.AREAS,
        "niveles_combustible": m.NIVELES_COMBUSTIBLE,
        "estados_punto": m.ESTADOS_PUNTO,
        "tipos_servicio": m.TIPOS_SERVICIO,
    }


def _inicio_dia_utc(dia: date, mas_un_dia: bool = False) -> datetime:
    """Las 00:00 de ese dia EN TIJUANA, expresadas en UTC.

    Una fecha de calendario no tiene hora ni zona; convertirla asumiendo UTC
    corre el corte siete u ocho horas y se pierde media tarde de cada dia.
    """
    d = dia + timedelta(days=1) if mas_un_dia else dia
    local = datetime(d.year, d.month, d.day, tzinfo=TZ_OPERACION)
    return a_utc(local)


def _reporte_o_404(db: Session, reporte_id: int) -> m.ReporteMantenimiento:
    r = (db.query(m.ReporteMantenimiento)
         .filter(m.ReporteMantenimiento.id == reporte_id).first())
    if not r:
        raise HTTPException(404, "Reporte no encontrado")
    return r


def _exigir_abierto(r: m.ReporteMantenimiento):
    """Un reporte cerrado ya se archivo con firmas: no se reescribe.

    Corregir un formato firmado sin dejar rastro es lo que hace que un papel
    deje de servir como prueba. Si hay que corregirlo, se levanta otro.
    """
    if r.estado == "cerrado":
        raise HTTPException(409, f"El reporte {r.folio} ya esta cerrado. "
                                 "Para corregirlo hay que levantar uno nuevo.")


# ---------------------------------------------------------------- CU-ADM-26 -- #
@router.post("/reportes", response_model=ReporteMantenimientoOut, status_code=201)
def abrir_reporte(datos: ReporteMantenimientoIn, usuario=Depends(solo_admin),
                  db: Session = Depends(get_db)):
    """Levanta el formato a mano, para la unidad que entra SIN solicitud previa.

    El camino normal ya no pasa por aqui: al aceptar el ingreso (CU-ADM-01) el
    formato se crea solo. Esto queda para lo que entra por la pluma sin haber
    pedido cita -- un arrastre que llego de madrugada, una unidad que el chofer
    dejo y se fue.
    """
    unidad = db.query(m.Unidad).filter(m.Unidad.id == datos.unidad_id).first()
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    if not db.query(m.Taller).filter(m.Taller.id == datos.taller_id).first():
        raise HTTPException(404, "Taller no encontrado")

    # Una unidad, un formato abierto. Dos formatos vivos para el mismo vehiculo
    # es como se pierde el rastro de en cual quedaron las firmas.
    abierto = svc.reporte_abierto_de_unidad(db, unidad.id)
    if abierto:
        raise HTTPException(409, {
            "mensaje": f"La unidad {unidad.num_economico} ya tiene el reporte "
                       f"{abierto.folio} abierto. Cierralo antes de levantar otro.",
            "reporte_id": abierto.id, "folio": abierto.folio,
        })

    orden = None
    if datos.orden_servicio_id:
        orden = (db.query(m.OrdenServicio)
                 .filter(m.OrdenServicio.id == datos.orden_servicio_id).first())
        if not orden:
            raise HTTPException(404, "Orden de servicio no encontrada")
        if orden.unidad_id != unidad.id:
            raise HTTPException(409, f"La orden {orden.folio} es de otra unidad.")
        ya = (db.query(m.ReporteMantenimiento)
              .filter(m.ReporteMantenimiento.orden_servicio_id == orden.id).first())
        if ya:
            raise HTTPException(409, f"La orden {orden.folio} ya tiene el reporte {ya.folio}.")

    r = svc.crear_reporte_mantenimiento(
        db, unidad=unidad, taller_id=datos.taller_id, admin_id=usuario.id, orden=orden,
        tipo_servicio=datos.tipo_servicio, origen=datos.origen,
        kilometraje=datos.kilometraje, area=datos.area, area_otro=datos.area_otro,
        chofer_id=datos.chofer_id, chofer_nombre=datos.chofer_nombre,
        supervisor_nombre=datos.supervisor_nombre, fecha_entrada=datos.fecha_entrada,
        nivel_combustible=datos.nivel_combustible, notas_ingreso=datos.notas_ingreso,
        puntos=datos.puntos, actividades=datos.actividades)

    registrar_bitacora(db, usuario.id, "reporte_mantenimiento_abierto",
                       "reporte_mantenimiento", r.id,
                       datos_despues=f"unidad={unidad.num_economico} folio={r.folio}")
    db.commit()
    db.refresh(r)
    return svc.reporte_out(db, r)


@router.get("/reportes", response_model=list[ReporteMantenimientoOut])
def reportes(estado: str | None = None, taller_id: int | None = None,
             unidad_id: int | None = None, q: str = "",
             desde: date | None = None, hasta: date | None = None,
             tecnico_id: int | None = None, limite: int = 50,
             usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """Buscador de formatos: por unidad o folio, por fecha y por trabajador.

    Los tres filtros se combinan (Y, no O). Buscar «todos los formatos donde
    aparezca Ramon en agosto» es una sola pregunta, no tres busquedas que el
    administrador tenga que cruzar a mano.
    """
    cons = db.query(m.ReporteMantenimiento)
    if estado:
        cons = cons.filter(m.ReporteMantenimiento.estado == estado)
    if taller_id:
        cons = cons.filter(m.ReporteMantenimiento.taller_id == taller_id)
    if unidad_id:
        cons = cons.filter(m.ReporteMantenimiento.unidad_id == unidad_id)

    termino = (q or "").strip().upper()
    if termino:
        # Sin guiones ni espacios: el papel escribe «BG-354P» y el catalogo
        # «BG354P». Se busca por las dos formas y tambien por folio, porque el
        # administrador tiene el papel en la mano y lo que trae impreso es el
        # folio, no el numero economico.
        plano = "".join(c for c in termino if c.isalnum())
        cons = (cons.join(m.Unidad, m.ReporteMantenimiento.unidad_id == m.Unidad.id)
                .filter(m.Unidad.num_economico.ilike(f"%{plano}%")
                        | m.Unidad.num_economico.ilike(f"%{termino}%")
                        | m.ReporteMantenimiento.folio.ilike(f"%{termino}%")))

    # El corte del dia se hace en Tijuana, no en UTC: a las 17:30 del 18 en
    # Tijuana ya son las 00:30 del 19 en UTC, y ese formato pertenece al 18.
    # Filtrar en UTC dejaria fuera media tarde de cada dia.
    if desde:
        cons = cons.filter(m.ReporteMantenimiento.fecha_entrada >= _inicio_dia_utc(desde))
    if hasta:
        cons = cons.filter(m.ReporteMantenimiento.fecha_entrada < _inicio_dia_utc(hasta, mas_un_dia=True))

    if tecnico_id:
        # «Todos los formatos donde aparezca este trabajador»: los que tienen
        # al menos un sistema a su nombre.
        sub = (db.query(m.ActividadReporte.reporte_id)
               .filter(m.ActividadReporte.tecnico_id == tecnico_id).subquery())
        cons = cons.filter(m.ReporteMantenimiento.id.in_(sub))

    cons = cons.order_by(m.ReporteMantenimiento.fecha_entrada.desc())
    return [svc.reporte_out(db, r) for r in cons.limit(max(1, min(limite, 200))).all()]


@router.get("/reportes/{reporte_id}", response_model=ReporteMantenimientoOut)
def reporte(reporte_id: int, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    return svc.reporte_out(db, _reporte_o_404(db, reporte_id))


# ---------------------------------------------------------------- CU-ADM-27 -- #
@router.post("/reportes/{reporte_id}/actividades", response_model=ReporteMantenimientoOut)
def capturar_actividades(reporte_id: int, datos: ActividadesIn,
                         usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """Teclea la tabla central: lo que hay que hacer y lo que ya se hizo.

    Igual que el diagnostico (CU-ADM-11), el mecanico no lo teclea: escribe en
    el papel y el administrador lo captura. Por eso cada renglon guarda quien
    lo hizo (`tecnico_id`) y quien lo tecleo (RN-11).
    """
    r = _reporte_o_404(db, reporte_id)
    _exigir_abierto(r)

    por_sistema = {a.sistema: a for a in r.actividades}
    validos = {k for k, _ in m.SISTEMAS}
    for entrada in datos.actividades:
        if entrada.sistema not in validos:
            raise HTTPException(422, f"Sistema desconocido: {entrada.sistema}")
        a = por_sistema.get(entrada.sistema)
        if not a:   # un formato viejo al que le falte un renglon
            a = m.ActividadReporte(reporte_id=r.id, sistema=entrada.sistema)
            db.add(a)
        a.a_realizar = entrada.a_realizar
        a.realizada = entrada.realizada
        if entrada.tecnico_id is not None:
            if not db.query(m.Tecnico).filter(m.Tecnico.id == entrada.tecnico_id).first():
                raise HTTPException(404, f"Tecnico {entrada.tecnico_id} no encontrado")
        a.tecnico_id = entrada.tecnico_id
        # La fecha marca cuando quedo HECHO el trabajo, no cuando se tecleo.
        # Se sella al aparecer texto en "realizada" y no se vuelve a mover.
        if entrada.realizada and not a.fecha_realizada:
            a.fecha_realizada = ahora_utc()
        if not entrada.realizada:
            a.fecha_realizada = None
        a.capturado_por_admin_id = usuario.id

    if datos.comentarios_adicionales is not None:
        r.comentarios_adicionales = datos.comentarios_adicionales

    registrar_bitacora(db, usuario.id, "reporte_actividades_capturadas",
                       "reporte_mantenimiento", r.id)
    db.commit()
    db.refresh(r)
    return svc.reporte_out(db, r)


# ---------------------------------------------------------------- CU-ADM-30 -- #
@router.post("/reportes/{reporte_id}/reasignar", response_model=ReporteMantenimientoOut)
def reasignar_sistema(reporte_id: int, datos: ReasignacionIn,
                      usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """Cambia quien responde por un sistema, dejando constancia de por que.

    Reasignar no es corregir un dato mal tecleado: es que a alguien se le
    atravesó otro trabajo. Sin el motivo y el nombre anterior, dentro de un mes
    nadie puede explicar por que el formato dice un tecnico y el mecanico
    recuerda otro. Por eso el motivo es obligatorio y el cambio se asienta en
    bitacora con el valor ANTERIOR, no solo con el nuevo.
    """
    r = _reporte_o_404(db, reporte_id)
    _exigir_abierto(r)

    a = next((x for x in r.actividades if x.sistema == datos.sistema), None)
    if not a:
        raise HTTPException(404, f"El formato no tiene el sistema '{datos.sistema}'")

    nuevo = None
    if datos.tecnico_id is not None:
        nuevo = db.query(m.Tecnico).filter(m.Tecnico.id == datos.tecnico_id,
                                           m.Tecnico.activo.is_(True)).first()
        if not nuevo:
            raise HTTPException(404, f"Tecnico {datos.tecnico_id} no encontrado o inactivo")
        if nuevo.id == a.tecnico_id:
            raise HTTPException(409, f"{nuevo.nombre_completo} ya responde por ese sistema.")

    antes = a.tecnico.nombre_completo if a.tecnico else "sin asignar"
    a.tecnico_id = nuevo.id if nuevo else None
    a.capturado_por_admin_id = usuario.id

    registrar_bitacora(
        db, usuario.id, "reporte_sistema_reasignado", "reporte_mantenimiento", r.id,
        datos_antes=f"{datos.sistema}={antes}",
        datos_despues=f"{datos.sistema}={nuevo.nombre_completo if nuevo else 'sin asignar'} "
                      f"motivo={datos.motivo}")
    db.commit()
    db.refresh(r)
    return svc.reporte_out(db, r)


# ---------------------------------------------------------------- CU-ADM-28 -- #
@router.post("/reportes/{reporte_id}/firmar", response_model=ReporteMantenimientoOut)
def registrar_firma(reporte_id: int, datos: FirmaReporteIn,
                    usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """Deja constancia de una firma que YA esta en el papel.

    El sistema no firma nada: la firma es de tinta. Esto registra que alguien
    la vio, quien la dio y cuando -- que es lo que permite explicar despues por
    que una unidad se quedo parada esperando un Vo. Bo.
    """
    r = _reporte_o_404(db, reporte_id)
    _exigir_abierto(r)

    f = next((x for x in r.firmas if x.rol_firma == datos.rol_firma), None)
    if f and f.nombre:
        raise HTTPException(409, f"Esa firma ya se registro a nombre de {f.nombre}.")
    if datos.usuario_id and not db.query(m.Usuario).filter(
            m.Usuario.id == datos.usuario_id).first():
        raise HTTPException(404, "Usuario no encontrado")
    if not f:
        f = m.FirmaReporte(reporte_id=r.id, rol_firma=datos.rol_firma)
        db.add(f)
    f.nombre = datos.nombre.strip()
    f.usuario_id = datos.usuario_id
    f.fecha = ahora_utc()
    f.registrada_por_admin_id = usuario.id

    registrar_bitacora(db, usuario.id, "reporte_firma_registrada",
                       "reporte_mantenimiento", r.id,
                       datos_despues=f"{datos.rol_firma}={f.nombre}")
    db.commit()
    db.refresh(r)
    return svc.reporte_out(db, r)


# ---------------------------------------------------------------- CU-ADM-29 -- #
@router.post("/reportes/{reporte_id}/cerrar", response_model=ReporteMantenimientoOut)
def cerrar_reporte(reporte_id: int, datos: CierreReporteIn,
                   usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """Sella la SALIDA del formato. Es lo ultimo que se llena en el papel."""
    r = _reporte_o_404(db, reporte_id)
    _exigir_abierto(r)

    faltantes = r.firmas_faltantes_para_salida()
    if faltantes:
        # Detalle estructurado: la pantalla puede decir CUALES faltan en vez de
        # mostrar "Error 409" y dejar al usuario adivinando.
        etiquetas = {k: e for k, e, _ in m.FIRMAS}
        raise HTTPException(409, {
            "mensaje": "Faltan firmas para poder cerrar el reporte: "
                       + ", ".join(etiquetas.get(x, x) for x in faltantes),
            "firmas_faltantes": faltantes,
        })

    salida = datos.fecha_salida or ahora_utc()
    if r.fecha_entrada and salida < r.fecha_entrada:
        raise HTTPException(422, "La salida no puede ser anterior a la entrada.")

    if datos.comentarios_adicionales is not None:
        r.comentarios_adicionales = datos.comentarios_adicionales
    r.fecha_salida = salida
    r.estado = "cerrado"
    r.cerrado_por_admin_id = usuario.id

    # Cerrar el formato ES la salida: se cierra la orden, se libera el cajon y
    # la unidad deja de estar en el taller. Antes esto vivia en un boton aparte
    # de la pantalla de Ordenes; hacer uno sin el otro dejaba la unidad a medio
    # salir y en el plano seguia apareciendo adentro.
    orden = r.orden or svc.orden_abierta_de_unidad(db, r.unidad_id)
    espacio_liberado = None
    if orden and orden.fecha_salida is None:
        ocup = svc.ocupacion_abierta_de_unidad(db, r.unidad_id)
        if ocup and ocup.espacio:
            e = ocup.espacio
            espacio_liberado = f"{e.zona.nombre} {e.numero}" if e.zona else e.numero
        svc.sacar_del_taller(db, orden, usuario.id,
                             unidad_operativa=datos.unidad_operativa,
                             operacion_a_realizar=datos.operacion_a_realizar)
        registrar_bitacora(db, usuario.id, "formato_salida_emitido",
                           "orden_servicio", orden.id,
                           datos_despues=f"reporte={r.folio} espacio={espacio_liberado}")

    notificar(db, r.chofer_id, "Unidad lista",
              f"{r.unidad.num_economico} sale del taller. Formato {r.folio}", "salida",
              "reporte_mantenimiento", r.id)
    registrar_bitacora(db, usuario.id, "reporte_mantenimiento_cerrado",
                       "reporte_mantenimiento", r.id)
    db.commit()
    db.refresh(r)
    return svc.reporte_out(db, r)


@router.get("/unidades")
def buscar_unidades(q: str = "", limite: int = 10, usuario=Depends(solo_admin),
                    db: Session = Depends(get_db)):
    """Buscador de unidad por numero economico, para llenar el formato.

    Busca sin guiones ni espacios porque el papel escribe "BG-354P" y el
    catalogo "BG354P". Devuelve el poseedor porque es el nombre que va en la
    raya de "NOMBRE DEL CHOFER" (RN-01), no el del titular.
    """
    plano = "".join(c for c in (q or "").upper() if c.isalnum())
    if not plano:
        return []
    candidatas = (db.query(m.Unidad)
                  .filter(m.Unidad.num_economico.isnot(None),
                          m.Unidad.activo.is_(True))
                  .order_by(m.Unidad.num_economico).all())
    tope = max(1, min(limite, 50))
    out = []
    for u in candidatas:
        clave = "".join(c for c in u.num_economico.upper() if c.isalnum())
        if plano not in clave:
            continue
        chofer_id = u.poseedor_chofer_id or u.titular_chofer_id
        out.append({
            "id": u.id, "num_economico": u.num_economico, "placas": u.placas,
            "marca": u.marca, "modelo": u.modelo, "anio": u.anio,
            "estado": u.estado, "km_actual": u.km_actual,
            "chofer_id": chofer_id, "chofer": svc.nombre_chofer(db, chofer_id),
            "taller_id": u.taller_actual_id or u.taller_asignado_id,
            "exacto": clave == plano,
        })
    out.sort(key=lambda x: (not x["exacto"], len(x["num_economico"])))
    return out[:tope]


@router.get("/tecnicos")
def tecnicos(usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """Catalogo de tecnicos: existen en el sistema pero NO tienen cuenta (v1.1)."""
    return [{"id": t.id, "nombre": t.nombre_completo, "especialidad": t.especialidad,
             "telefono": t.telefono, "disponible": t.disponible}
            for t in db.query(m.Tecnico).filter(m.Tecnico.activo.is_(True)).all()]


# --------------------------------------------- buscador con comodines (*) -- #
# Compras y almacen buscan en el Excel de MATERIALES con asteriscos: teclean
# unos trozos del nombre y el * se encarga de lo que va en medio, asi que
# "JUE*EM*G*7000" encuentra "JUEGO EMPAQUE GMC 7000". Es como esta acostumbrada
# a buscar esa gente, y sin esto hay que acertarle a una subcadena corrida
# --"empaque gmc"-- que casi nunca se recuerda en el orden exacto.
def _patron_busqueda(termino: str) -> tuple[str, bool]:
    """Traduce lo tecleado a un patron de LIKE. Devuelve (patron, con_comodin).

    SIN asterisco no cambia nada: subcadena suelta, la busqueda de siempre.
    CON asterisco, cada * es "lo que sea" y lo tecleado ancla por el principio,
    que es como se comporta el buscador del Excel.
    """
    t = termino.lower()
    # % y _ ya son comodines del propio LIKE, asi que se escapan: si no,
    # teclear "10%" traeria medio catalogo en vez de las piezas que dicen 10%.
    # La barra va PRIMERO en la tupla: si se escapara al final, volveria a
    # escapar las barras que acaban de meter los otros dos.
    for ch in ("\\", "%", "_"):
        t = t.replace(ch, "\\" + ch)
    if "*" not in termino:
        return f"%{t}%", False
    patron = t.replace("*", "%")
    # Cola libre: "JUE*7000" tambien tiene que encontrar
    # "JUEGO EMPAQUE GMC 7000 REFORZADO", no solo el que termina en 7000.
    if not patron.endswith("%"):
        patron += "%"
    return patron, True


@router.get("/piezas")
def piezas(q: str = "", taller_id: int | None = None, limite: int = 30,
           usuario=Depends(require_roles("administrador", "capturista")),
           db: Session = Depends(get_db)):
    """CU-ADM-11: buscador del almacen con respuesta inmediata.

    El catalogo trae mas de 18 mil refacciones: devolverlas todas no sirve de
    nada.

    Se busca por NOMBRE y por CODIGO. Antes era solo por nombre porque apenas el
    5% del catalogo traia numero de parte; con `CODIGOS TALLER.xlsx` casado
    contra el catalogo, el 57% ya tiene su codigo de material de SAP, asi que el
    mecanico que llega con el numero en la mano puede teclearlo directo.

    Cuando el termino parece un codigo, las coincidencias por codigo van
    PRIMERO: quien busca "231208" quiere esa pieza, no las que mencionan ese
    numero en su descripcion.

    La respuesta dice de una vez `hay` y `disponible`, que es lo unico que el
    administrador necesita saber para contestarle al mecanico.

    El CAPTURISTA lee este mismo buscador --teclea del papel el codigo de cada
    material-- y por eso el rol esta permitido aqui. Es el unico endpoint de
    /admin que comparte: solo consulta el catalogo, no mueve nada.
    """
    termino = (q or "").strip()
    # Los asteriscos no son letras: un "*" suelto pediria el catalogo entero.
    if len(termino.replace("*", "")) < 2:
        return {"termino": termino, "total": 0, "resultados": [],
                "aviso": "Escribe al menos 2 letras para buscar."}

    # El almacen vive en la planta central salvo que se pida otro.
    if taller_id is None:
        central = (db.query(m.Taller).join(m.Planta)
                   .filter(m.Planta.es_central.is_(True)).first())
        taller_id = central.id if central else None

    patron, con_comodin = _patron_busqueda(termino)
    base = (db.query(m.Pieza)
            .filter(m.Pieza.activa.is_(True),
                    func.lower(m.Pieza.nombre).like(patron, escape="\\")
                    | func.lower(func.coalesce(m.Pieza.codigo_externo, "")).like(patron, escape="\\")
                    | func.lower(m.Pieza.sku).like(patron, escape="\\")))
    total = base.count()

    # Primero se resuelve QUE filas se devuelven (las de nombre mas corto son
    # las mas parecidas al termino) y solo despues se buscan SUS existencias.
    # Si se consultan con un orden distinto al que se devuelve, los stocks
    # quedan pegados a la pieza equivocada.
    #
    # `case` pone arriba lo que caso por codigo: es una coincidencia mucho mas
    # fuerte que aparecer en medio de una descripcion.
    prioridad = case(
        (func.lower(func.coalesce(m.Pieza.codigo_externo, "")) == termino.lower(), 0),
        (func.lower(func.coalesce(m.Pieza.codigo_externo, "")).like(patron, escape="\\"), 1),
        else_=2)
    encontradas = (base.order_by(prioridad, func.length(m.Pieza.nombre))
                   .limit(limite).all())

    existencias = {}
    if taller_id and encontradas:
        for e in (db.query(m.Existencia)
                  .filter(m.Existencia.taller_id == taller_id,
                          m.Existencia.pieza_id.in_([p.id for p in encontradas])).all()):
            existencias[e.pieza_id] = e

    resultados = []
    for p in encontradas:
        e = existencias.get(p.id)
        disp = e.disponible if e else 0
        resultados.append({
            "id": p.id, "sku": p.sku, "nombre": p.nombre,
            "codigo": p.codigo_externo,
            # El administrador necesita saber si el codigo es de SAP o si se
            # rescato del propio nombre: no valen lo mismo para hacer un pedido.
            "codigo_es_sap": p.origen_codigo == "sap",
            "hay": disp > 0,
            "disponible": disp,
            "stock_actual": e.stock_actual if e else 0,
            "reservado": e.stock_reservado if e else 0,
            "ubicacion": e.ubicacion_fisica if e else None,
            "precio_referencia": float(p.precio_referencia or 0),
        })

    con_stock = sum(1 for r in resultados if r["hay"])
    return {
        "termino": termino,
        # Para que la pantalla pueda decir que el * si se tomo en cuenta: si no,
        # una busqueda con comodines que no encuentra nada parece una falla del
        # buscador y no una busqueda demasiado estrecha.
        "comodin": con_comodin,
        "total": total,
        "mostrando": len(resultados),
        "con_existencia": con_stock,
        "resultados": resultados,
        "aviso": (None if total else
                  (f"Ninguna refaccion casa con el patron '{termino}'. "
                   f"Cada * es lo que sea: prueba con menos trozos."
                   if con_comodin else
                   f"No hay ninguna refaccion que diga '{termino}'.")),
    }


# ---------------------------------------------------- CU-ADM-04: menu del plano -- #
@router.get("/espacios/{espacio_id}")
def detalle_espacio(espacio_id: int, usuario=Depends(solo_admin),
                    db: Session = Depends(get_db)):
    """Lo que necesita el menu que se despliega al tocar una casilla del plano."""
    esp = db.query(m.Espacio).filter(m.Espacio.id == espacio_id).first()
    if not esp:
        raise HTTPException(404, "Espacio no encontrado")

    ocup = svc.ocupacion_abierta_de_espacio(db, espacio_id)
    zona = esp.zona
    datos = {
        "id": esp.id, "numero": esp.numero,
        "zona": zona.nombre if zona else None,
        "taller_id": zona.taller_id if zona else None,
        "cuenta_para_ocupacion": bool(zona.cuenta_para_ocupacion) if zona else False,
        # El patio, la fosa y el area de lavado admiten unidades pero no son
        # capacidad de atencion: son la sala de espera antes del quirofano.
        # La pantalla necesita distinguirlas para no decirle al administrador
        # que ahi «se esta atendiendo» una unidad que solo esta esperando turno.
        "es_sala_espera": bool(zona and zona.admite_unidades
                               and not zona.cuenta_para_ocupacion),
        "estado": esp.estado,
        "tipo_permitido_id": esp.tipo_unidad_permitido_id,
        "ocupado_por": None,
        "candidatas": [],
    }

    if ocup:
        u = ocup.unidad
        reporte = svc.reporte_abierto_de_unidad(db, u.id)
        datos["ocupado_por"] = {
            "unidad_id": u.id, "num_economico": u.num_economico,
            "marca": u.marca, "modelo": u.modelo,
            "orden_id": ocup.orden_servicio_id,
            "desde": ocup.fecha_entrada,
            # Quien metio esta unidad aqui. Cada administrador atiende sus
            # vehiculos; sin este dato nadie sabe a quien preguntarle por el.
            "colocado_por": svc.nombre_usuario(db, ocup.colocado_por_admin_id),
        }
        # CU-ADM-26: al tocar la casilla sale el formato abierto de esa unidad.
        # Es la puerta natural: el administrador esta viendo el vehiculo, no
        # buscando un folio.
        datos["reporte"] = None if not reporte else {
            "id": reporte.id, "folio": reporte.folio, "estado": reporte.estado,
            "tipo_servicio": reporte.tipo_servicio,
            "chofer_nombre": reporte.chofer_nombre,
            "firmas_faltantes": reporte.firmas_faltantes_para_salida(),
            # Quien esta atendiendo AHORA este vehiculo.
            "atendido_por": svc.atendido_por(reporte),
        }
        datos["acciones"] = ["retirar", "mover"]
        return datos

    # Espacio libre: que unidades pueden entrar aqui. Solo las que ya tienen
    # orden abierta en este taller y no estan colocadas en otro cajon.
    datos["acciones"] = ["colocar"]
    if zona:
        ordenes = (db.query(m.OrdenServicio)
                   .filter(m.OrdenServicio.taller_id == zona.taller_id,
                           m.OrdenServicio.fecha_salida.is_(None)).all())
        for o in ordenes:
            if esp.tipo_unidad_permitido_id and \
                    esp.tipo_unidad_permitido_id != o.unidad.tipo_unidad_id:
                continue          # RI-04: el cajon no admite ese tipo de unidad
            if svc.ocupacion_abierta_de_unidad(db, o.unidad_id):
                continue          # ya esta en otro espacio
            datos["candidatas"].append({
                "orden_id": o.id, "folio": o.folio,
                "unidad_id": o.unidad_id,
                "num_economico": o.unidad.num_economico,
                "marca": o.unidad.marca, "modelo": o.unidad.modelo,
            })
    return datos


@router.post("/espacios/{espacio_id}/colocar/{orden_id}", response_model=MensajeOut)
def colocar_unidad(espacio_id: int, orden_id: int, usuario=Depends(solo_admin),
                   db: Session = Depends(get_db)):
    """Mete una unidad con orden abierta en un espacio libre (CU-ADM-04)."""
    return mover_unidad(espacio_id, orden_id, usuario, db)


# =========================================================================== #
# CU-ADM-31 - Despacho de auxilio en carretera
#
# Antes esto vivia en el supervisor y era una COMPUERTA: la unidad varada
# esperaba a que el supervisor validara para que alguien decidiera el apoyo.
# Pablo pidio quitarse ese paso de encima, y el diagnostico es correcto: el
# supervisor no aporta informacion que el administrador no tenga, solo tiempo.
#
# Lo que NO se quita es el aviso: el supervisor recibe la misma notificacion al
# mismo tiempo, para enterarse de que su chofer esta parado. Deja de ser un
# permiso y pasa a ser una copia.
#
# Y una compuerta si se queda: RN-04. Si la unidad esta en vialidad publica hay
# que registrar el aviso a peritos antes del arrastre. Eso no es lentitud
# administrativa, es la aseguradora.
# =========================================================================== #

@router.get("/averias", response_model=list[AveriaOut])
def averias_abiertas(historial: bool = False, usuario=Depends(solo_admin),
                     db: Session = Depends(get_db)):
    """CU-ADM-31. Por omision solo lo que sigue sin resolverse."""
    q = db.query(m.ReporteAveria)
    if not historial:
        q = q.filter(m.ReporteAveria.estado != "cerrado")
    rs = q.order_by(m.ReporteAveria.fecha_hora.desc()).limit(200).all()
    return [svc.averia_out(db, r) for r in rs]


@router.get("/averias/{averia_id}/apoyo", response_model=ApoyoOut)
def apoyo_para(averia_id: int, usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """Quien puede ir, ordenado por cercania al punto donde quedo la unidad.

    Va en una sola llamada --tecnicos, gruas y talleres-- porque las tres se
    miran a la vez para tomar una decision. Partirlo en tres endpoints haria
    que la pantalla pintara por pedazos justo cuando hay prisa.
    """
    r = db.query(m.ReporteAveria).filter(m.ReporteAveria.id == averia_id).first()
    if not r:
        raise HTTPException(404, "Reporte no encontrado")

    talleres = []
    for t in db.query(m.Taller).filter(m.Taller.activo.is_(True)).all():
        talleres.append({"id": t.id, "nombre": t.nombre,
                         "km": svc.km_entre(r.latitud, r.longitud, t.latitud, t.longitud)})
    talleres.sort(key=lambda x: x["km"] if x["km"] is not None else 9e9)

    return {"tecnicos": svc.apoyo_cercano(db, r.latitud, r.longitud),
            "gruas": svc.gruas_disponibles(db),
            "talleres": talleres}


@router.post("/averias/{averia_id}/despachar", response_model=AveriaOut)
def despachar(averia_id: int, datos: DespachoIn, usuario=Depends(solo_admin),
              db: Session = Depends(get_db)):
    """CU-ADM-31. Cuatro salidas, no dos.

    La que faltaba es `telefono`, y es la mas frecuente: el administrador marca,
    el chofer mueve algo el mismo y la unidad sigue su ruta. Sin registrarla, el
    corte del mes decia "40 averias, 12 arrastres" y de las otras 28 no quedaba
    ningun rastro de que habia pasado.
    """
    r = db.query(m.ReporteAveria).filter(m.ReporteAveria.id == averia_id).first()
    if not r:
        raise HTTPException(404, "Reporte no encontrado")
    if datos.tipo not in svc.DESENLACES:
        raise HTTPException(400, f"Desenlace desconocido: {datos.tipo}")
    if r.desenlace:
        raise HTTPException(409, f"Esta averia ya se despacho como '{r.desenlace}'")

    # El supervisor del chofer se entera SIEMPRE, decida lo que decida el
    # administrador. Es el aviso que sustituye a la autorizacion que se quito.
    ch = db.query(m.Chofer).filter(m.Chofer.usuario_id == r.chofer_id).first()
    sup_id = ch.plantilla.supervisor_id if ch and ch.plantilla else None
    unidad = r.unidad.num_economico if r.unidad else "-"
    mensaje = ""

    if datos.tipo == "telefono":
        # No sale nadie: se cierra en el acto. Es el unico desenlace que no
        # genera trabajo para nadie mas, y por eso mismo el que se perdia.
        r.estado = "cerrado"
        mensaje = f"Averia de la unidad {unidad} resuelta por telefono"

    elif datos.tipo in ("mecanico", "llantero"):
        if not datos.tecnico_id:
            raise HTTPException(400, "Indica que tecnico va a sitio")
        t = db.query(m.Tecnico).filter(m.Tecnico.id == datos.tecnico_id).first()
        if not t:
            raise HTTPException(404, "Tecnico no encontrado")
        if t.modalidad != "AUTONOMO":
            # No es capricho: los 34 tecnicos de Alamos son ASISTIDO, no usan la
            # aplicacion y no salen a carretera. Dejar elegirlos seria despachar
            # a alguien que no va a ir, y la unidad se quedaria esperando.
            raise HTTPException(409,
                                f"{t.nombre} {t.apellidos} es ASISTIDO: trabaja dentro del "
                                "taller y no sale a carretera. Elige un tecnico autonomo.")
        r.estado = "en_atencion"
        notificar(db, r.chofer_id, "Apoyo en camino",
                  f"Va {t.nombre} {t.apellidos} ({t.telefono or 'sin telefono'}) a tu ubicacion",
                  "averia", "reporte_averia", r.id)
        mensaje = f"{t.nombre} {t.apellidos} enviado a la unidad {unidad}"

    else:  # grua
        if not svc.puede_solicitar_arrastre(r):
            raise HTTPException(
                409, "RN-04: la unidad esta en vialidad publica. Primero tiene que registrarse "
                     "el aviso a peritos con su folio; hasta entonces no se habilita el "
                     "arrastre. No es un tramite interno: sin peritaje la aseguradora puede "
                     "no cubrir el siniestro.")
        if r.arrastre:
            raise HTTPException(409, f"Ya existe el arrastre {r.arrastre.folio} para esta averia")

        a = m.Arrastre(folio=svc.siguiente_folio(db, m.Arrastre, "ARR"),
                       reporte_averia_id=r.id, unidad_arrastrada_id=r.unidad_id,
                       chofer_responsable_id=r.chofer_id,
                       taller_destino_id=datos.taller_destino_id,
                       estado="solicitado")
        db.add(a)
        r.requiere_arrastre = True
        db.flush()

        if datos.chofer_grua_id:
            # Asignado a uno solo: se le avisa unicamente a el. El administrador
            # ya sabe quien esta libre porque la pantalla se lo calculo.
            a.chofer_grua_id = datos.chofer_grua_id
            detalle = f"Unidad {unidad}. {r.descripcion_falla or ''}".strip()
            notificar(db, datos.chofer_grua_id, "Arrastre asignado", detalle,
                      "arrastre", "arrastre", a.id)
            quien = svc.nombre_usuario(db, datos.chofer_grua_id)
            mensaje = f"Arrastre {a.folio} asignado a {quien}"
        else:
            # Sin asignar: se difunde y lo toma el primero que pueda. Sirve
            # cuando ninguno aparece libre o cuando corre mucha prisa.
            for mo in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
                    m.Rol.nombre == "chofer_grua").all():
                notificar(db, mo.id, "Nuevo arrastre solicitado",
                          f"Unidad {unidad}", "arrastre", "arrastre", a.id)
            mensaje = f"Arrastre {a.folio} difundido a los choferes de grua"
        r.estado = "en_atencion"

    r.desenlace = datos.tipo
    r.despachado_por_usuario_id = usuario.id
    r.fecha_despacho = ahora_utc()
    r.nota_despacho = datos.nota

    if sup_id:
        notificar(db, sup_id, "Se despacho apoyo a tu chofer",
                  f"{unidad}: {svc.DESENLACES[datos.tipo].lower()}. Lo decidio el "
                  "administrador de taller.", "averia", "reporte_averia", r.id)
    registrar_bitacora(db, usuario.id, f"averia_despachada_{datos.tipo}",
                       "reporte_averia", r.id, datos_despues=mensaje)
    db.commit()
    db.refresh(r)
    return svc.averia_out(db, r)


@router.get("/arrastres")
def registro_arrastres(usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """El registro que faltaba: que arrastres se han hecho y como van.

    Los datos ya estaban en la tabla desde siempre; lo que no habia era por
    donde verlos.
    """
    out = []
    for a in db.query(m.Arrastre).order_by(m.Arrastre.fecha_solicitud.desc()).limit(300).all():
        d = svc.arrastre_out(db, a)
        if a.fecha_solicitud:
            fin = a.fecha_finalizacion or ahora_utc()
            d["dias_abierto"] = (fin - a.fecha_solicitud).days
        else:
            d["dias_abierto"] = None
        d["descripcion_falla"] = a.reporte.descripcion_falla if a.reporte else None
        out.append(d)
    return out
