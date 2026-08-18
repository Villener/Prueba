"""Modulo Administrador de taller - CU-ADM-01 a CU-ADM-16.

v1.1: absorbe la captura del trabajo del mecanico (CU-ADM-11 a 16), porque los
mecanicos no usan la aplicacion. Todo dato capturado guarda doble responsable (RN-11).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models as m
from .. import services as svc
from ..database import get_db
from ..schemas import (AsignacionTecnicoIn, AsignacionTecnicoOut, AvanceIn,
                       CapturaDiagnosticoIn, FormatoSalidaIn, MensajeOut, OrdenServicioOut,
                       PresupuestoIn, PresupuestoOut, ResolucionSolicitudIn, SolicitudOut,
                       TallerOut)
from ..security import notificar, registrar_bitacora, require_roles

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
    s.fecha_respuesta = datetime.utcnow()

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

    # --- aceptar: verificar espacio compatible (RN-06 / RI-04) ---
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

    # Si el ingreso corresponde a un mantenimiento pendiente, se marca cumplido.
    prog = (db.query(m.ProgramaMantenimiento)
            .filter(m.ProgramaMantenimiento.unidad_id == s.unidad_id,
                    m.ProgramaMantenimiento.estado == "pendiente")
            .order_by(m.ProgramaMantenimiento.fecha_limite).first())
    if prog and s.tipo == "preventivo":
        prog.estado = "cumplido"
        prog.fecha_cumplimiento = datetime.utcnow()
        prog.orden_servicio_id = orden.id

    notificar(db, s.chofer_id, "Solicitud aceptada",
              f"Unidad {s.unidad.num_economico} en {espacio.zona.nombre} {espacio.numero}. "
              f"Orden {orden.folio}", "solicitud", "orden_servicio", orden.id)
    registrar_bitacora(db, usuario.id, "solicitud_aceptada", "solicitud_ingreso", s.id,
                       f"orden={orden.folio} espacio={espacio.id}")
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
            dias = (datetime.utcnow() - ocup.fecha_entrada).days if ocup else None
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
    ocup.fecha_salida = datetime.utcnow()
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
        actual.fecha_salida = datetime.utcnow()
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
    a.fecha_captura = datetime.utcnow()
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
        a.fecha_inicio = datetime.utcnow()
        a.orden.estado = "en_reparacion"
        a.orden.unidad.estado = "en_reparacion"
    if datos.estado == "terminada":
        a.fecha_fin = datetime.utcnow()
    a.estado = datos.estado
    if datos.trabajo_realizado:
        a.trabajo_realizado = datos.trabajo_realizado
    a.capturado_por_admin_id = usuario.id
    a.fecha_captura = datetime.utcnow()
    if all(x.estado == "terminada" for x in a.orden.asignaciones):
        a.orden.estado = "terminada"
    db.commit()
    db.refresh(a)
    return svc.asignacion_out(db, a)


# ---------------------------------------------------------------- CU-ADM-15 -- #
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
    return {"taller_id": taller_id, "generado": datetime.utcnow(),
            "tecnicos": list(por_tecnico.values())}


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
    if datos.fecha_elaboracion > datetime.utcnow().date():
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
    p.fecha_aviso_al_tecnico = datetime.utcnow()
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
                       fecha_estimada_llegada=(datetime.utcnow().date() +
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
    oc.fecha_recepcion = datetime.utcnow()
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
    db.add(m.FormatoSalida(orden_servicio_id=o.id, km_salida=datos.km_salida,
                           entregado_a_chofer_id=o.chofer_responsable_id,
                           elaborado_por_admin_id=usuario.id,
                           trabajos_realizados=datos.trabajos_realizados,
                           observaciones=datos.observaciones,
                           unidad_operativa=datos.unidad_operativa))
    ocup = svc.ocupacion_abierta_de_unidad(db, o.unidad_id)
    if ocup:
        ocup.fecha_salida = datetime.utcnow()
        ocup.retirado_por_admin_id = usuario.id
        ocup.espacio.estado = "libre"
    o.estado = "cerrada"
    o.fecha_salida = datetime.utcnow()
    o.km_salida = datos.km_salida
    o.unidad.estado = "disponible" if datos.unidad_operativa else "en_taller"
    o.unidad.taller_actual_id = None if datos.unidad_operativa else o.taller_id
    o.unidad.km_actual = datos.km_salida
    notificar(db, o.chofer_responsable_id, "Unidad lista",
              f"{o.unidad.num_economico} sale del taller. Orden {o.folio}", "salida")
    registrar_bitacora(db, usuario.id, "formato_salida_emitido", "orden_servicio", o.id)
    db.commit()
    return {"mensaje": f"Salida emitida para la orden {o.folio}"}


@router.get("/tecnicos")
def tecnicos(usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    """Catalogo de tecnicos: existen en el sistema pero NO tienen cuenta (v1.1)."""
    return [{"id": t.id, "nombre": t.nombre_completo, "especialidad": t.especialidad,
             "telefono": t.telefono, "disponible": t.disponible}
            for t in db.query(m.Tecnico).filter(m.Tecnico.activo.is_(True)).all()]


@router.get("/piezas")
def piezas(usuario=Depends(solo_admin), db: Session = Depends(get_db)):
    return [{"id": p.id, "sku": p.sku, "nombre": p.nombre,
             "precio_referencia": float(p.precio_referencia or 0),
             "stock_actual": p.stock_actual}
            for p in db.query(m.Pieza).filter(m.Pieza.activa.is_(True)).all()]
