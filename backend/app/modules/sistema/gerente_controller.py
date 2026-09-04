"""Modulo Gerente - CU-GER-01 a CU-GER-09."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import models as m
from ... import services as svc
from ...core.database import get_db
from ...schemas import (AlertaOut, IncumplimientoOut, KpiOut, MensajeOut, OrdenServicioOut,
                       PresupuestoOut, ResolucionPresupuestoIn)
from ...core.security import notificar, registrar_bitacora, require_roles
from ...core.tiempo import ahora_utc

router = APIRouter(prefix="/api/gerente", tags=["gerente"])
solo_ger = require_roles("gerente")


# ---------------------------------------------------------------- CU-GER-01 -- #
@router.get("/kpis", response_model=KpiOut)
def kpis(dias: int = 30, usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    desde = ahora_utc() - timedelta(days=dias)
    total_esp = (db.query(func.count(m.Espacio.id)).join(m.ZonaTaller)
                 .filter(m.ZonaTaller.cuenta_para_ocupacion.is_(True),
                         m.Espacio.activo.is_(True)).scalar() or 0)
    ocupados = (db.query(func.count(m.Espacio.id)).join(m.ZonaTaller)
                .filter(m.ZonaTaller.cuenta_para_ocupacion.is_(True),
                        m.Espacio.estado == "ocupado").scalar() or 0)
    # Incluye 'vencido': el job nocturno cambia el estado al penalizar, y si solo
    # se mirara 'pendiente' el indicador caeria a cero justo despues de penalizar.
    incumpliendo = (db.query(func.count(func.distinct(m.Unidad.poseedor_chofer_id)))
                    .select_from(m.ProgramaMantenimiento).join(m.Unidad)
                    .filter(m.ProgramaMantenimiento.estado.in_(["pendiente", "vencido"]),
                            m.ProgramaMantenimiento.fecha_limite < date.today()).scalar() or 0)
    retrasos = [p.dias_retraso_captura for p in db.query(m.Presupuesto).all()
                if p.dias_retraso_captura is not None]
    return {
        "unidades_total": db.query(func.count(m.Unidad.id)).scalar() or 0,
        "unidades_en_taller": db.query(func.count(m.Unidad.id)).filter(
            m.Unidad.estado.in_(["en_taller", "en_reparacion"])).scalar() or 0,
        "unidades_en_ruta": db.query(func.count(m.Unidad.id)).filter(
            m.Unidad.estado == "en_ruta").scalar() or 0,
        "unidades_varadas": db.query(func.count(m.Unidad.id)).filter(
            m.Unidad.estado.in_(["varada", "en_arrastre"])).scalar() or 0,
        "ocupacion_pct": round(ocupados * 100 / total_esp, 1) if total_esp else 0.0,
        "espacios_ocupados": ocupados, "espacios_totales": total_esp,
        "choferes_incumpliendo": incumpliendo,
        # Lee AvisoIncumplimiento, NO la tabla `penalizacion`. Esa quedo del
        # modelo v1.1 y desde que la penalizacion desaparecio nadie la escribe:
        # el indicador daba 0 siempre aunque hubiera avisos abiertos. Y es el
        # numero que motiva el proyecto (RF-GER-02), asi que mentia justo donde
        # mas importa. Se conserva la clave vieja para no romper la pantalla.
        "penalizaciones_mes": db.query(func.count(m.AvisoIncumplimiento.id)).filter(
            m.AvisoIncumplimiento.fecha_generacion >= desde.date()).scalar() or 0,
        "avisos_incumplimiento_mes": db.query(func.count(m.AvisoIncumplimiento.id)).filter(
            m.AvisoIncumplimiento.fecha_generacion >= desde.date()).scalar() or 0,
        "presupuestos_pendientes": db.query(func.count(m.Presupuesto.id)).filter(
            m.Presupuesto.estado == "enviado_gerente").scalar() or 0,
        "piezas_en_camino": db.query(func.count(m.OrdenCompra.id)).filter(
            m.OrdenCompra.estado.in_(["solicitada", "confirmada", "en_transito"])).scalar() or 0,
        "alertas_abiertas": db.query(func.count(m.AlertaGerencia.id)).filter(
            m.AlertaGerencia.atendida.is_(False)).scalar() or 0,
        "unidades_atendidas_periodo": db.query(func.count(m.OrdenServicio.id)).filter(
            m.OrdenServicio.fecha_salida >= desde).scalar() or 0,
        "retraso_captura_promedio": round(sum(retrasos) / len(retrasos), 1) if retrasos else None,
    }


# ---------------------------------------------------------------- CU-GER-02 -- #
@router.get("/incumplimiento", response_model=list[IncumplimientoOut])
def incumplimiento(usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """Choferes que no estan siguiendo el mantenimiento preventivo.

    Se reporta al POSEEDOR actual (RN-01), y se marca si lo es por un prestamo:
    esa distincion es la que evita culpar al titular equivocado.
    """
    out = []
    progs = (db.query(m.ProgramaMantenimiento)
             .filter(m.ProgramaMantenimiento.estado.in_(["pendiente", "vencido"]),
                     m.ProgramaMantenimiento.fecha_limite < date.today()).all())
    for p in progs:
        u = p.unidad
        poseedor = svc.poseedor_actual(db, u)
        prest = svc.prestamo_activo(db, u.id)
        out.append({
            "chofer": svc.nombre_chofer(db, poseedor) or "sin asignar",
            "chofer_id": poseedor or 0,
            "unidad": u.num_economico,
            "plan": p.plan.nombre if p.plan else "-",
            "fecha_limite": p.fecha_limite,
            "dias_atraso": (date.today() - p.fecha_limite).days,
            "es_poseedor_por_prestamo": bool(prest and prest.estado == "activo"),
        })
    return sorted(out, key=lambda x: -x["dias_atraso"])


# ------------------------------------------------------------- CU-GER-03/06 -- #
@router.get("/ocupacion")
def ocupacion(usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """Ocupacion por taller. Solo cuentan las zonas operativas: el yonke y el
    area de lavado quedan fuera o el indicador saldria inflado."""
    out = []
    for t in db.query(m.Taller).all():
        total = ocupados = 0
        zonas = []
        for z in t.zonas:
            if not z.cuenta_para_ocupacion:
                continue
            tz = len([e for e in z.espacios if e.activo])
            oz = len([e for e in z.espacios if e.estado == "ocupado"])
            total += tz
            ocupados += oz
            zonas.append({"zona": z.nombre, "total": tz, "ocupados": oz})
        out.append({"taller_id": t.id, "taller": t.nombre, "total": total,
                    "ocupados": ocupados, "libres": total - ocupados,
                    "pct": round(ocupados * 100 / total, 1) if total else 0, "zonas": zonas})
    return out


@router.get("/permanencia", response_model=list[OrdenServicioOut])
def permanencia(usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    ordenes = (db.query(m.OrdenServicio).filter(m.OrdenServicio.estado != "cerrada").all())
    res = [svc.orden_out(db, o) for o in ordenes]
    return sorted(res, key=lambda x: -x["dias_en_taller"])


# ---------------------------------------------------------------- CU-GER-04 -- #
@router.get("/historial", response_model=list[OrdenServicioOut])
def historial(dias: int = 90, usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    desde = ahora_utc() - timedelta(days=dias)
    ordenes = (db.query(m.OrdenServicio)
               .filter(m.OrdenServicio.fecha_entrada >= desde)
               .order_by(m.OrdenServicio.fecha_entrada.desc()).all())
    return [svc.orden_out(db, o) for o in ordenes]


# ---------------------------------------------------------------- CU-GER-05 -- #
@router.get("/piezas-en-camino")
def piezas_en_camino(usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    out = []
    for oc in (db.query(m.OrdenCompra)
               .filter(m.OrdenCompra.estado.in_(["solicitada", "confirmada", "en_transito"]))
               .all()):
        dias = ((oc.fecha_estimada_llegada - date.today()).days
                if oc.fecha_estimada_llegada else None)
        out.append({
            "folio": oc.folio, "unidad": oc.presupuesto.orden.unidad.num_economico,
            "orden": oc.presupuesto.orden.folio, "estado": oc.estado,
            "total": float(oc.total or 0),
            "fecha_estimada_llegada": oc.fecha_estimada_llegada,
            "dias_para_llegar": dias, "retrasada": dias is not None and dias < 0,
            "proveedor": oc.proveedor.nombre if oc.proveedor else None,
            "piezas": [d.pieza.nombre if d.pieza else d.descripcion_libre
                       for d in oc.presupuesto.detalles],
        })
    return out


# ---------------------------------------------------------------- CU-GER-07 -- #
@router.get("/alertas", response_model=list[AlertaOut])
def alertas(incluir_atendidas: bool = False, usuario=Depends(solo_ger),
            db: Session = Depends(get_db)):
    q = db.query(m.AlertaGerencia)
    if not incluir_atendidas:
        q = q.filter(m.AlertaGerencia.atendida.is_(False))
    return [{"id": a.id, "tipo": a.tipo,
             "unidad": a.unidad.num_economico if a.unidad else None,
             "detalle": a.detalle, "fecha_generacion": a.fecha_generacion,
             "veces_notificada": a.veces_notificada, "atendida": a.atendida}
            for a in q.order_by(m.AlertaGerencia.veces_notificada.desc()).all()]


@router.post("/alertas/{alerta_id}/atender", response_model=MensajeOut)
def atender_alerta(alerta_id: int, nota: str = "", usuario=Depends(solo_ger),
                   db: Session = Depends(get_db)):
    """RN-08: la alerta se reenvia hasta que alguien la atiende."""
    a = db.query(m.AlertaGerencia).filter(m.AlertaGerencia.id == alerta_id).first()
    if not a:
        raise HTTPException(404, "Alerta no encontrada")
    a.atendida = True
    a.fecha_atencion = ahora_utc()
    a.atendida_por_usuario_id = usuario.id
    a.detalle = f"{a.detalle or ''}\n[atendida] {nota}"
    registrar_bitacora(db, usuario.id, "alerta_atendida", "alerta_gerencia", a.id, nota)
    db.commit()
    return {"mensaje": "Alerta atendida"}


# ---------------------------------------------------------------- CU-GER-08 -- #
@router.get("/presupuestos", response_model=list[PresupuestoOut])
def presupuestos(pendientes: bool = True, usuario=Depends(solo_ger),
                 db: Session = Depends(get_db)):
    q = db.query(m.Presupuesto)
    if pendientes:
        q = q.filter(m.Presupuesto.estado == "enviado_gerente")
    return [svc.presupuesto_out(db, p) for p in
            q.order_by(m.Presupuesto.fecha_captura.desc()).all()]


@router.post("/presupuestos/{pre_id}/resolver", response_model=PresupuestoOut)
def resolver_presupuesto(pre_id: int, datos: ResolucionPresupuestoIn, usuario=Depends(solo_ger),
                         db: Session = Depends(get_db)):
    """RN-07: solo el gerente aprueba o rechaza."""
    p = db.query(m.Presupuesto).filter(m.Presupuesto.id == pre_id).first()
    if not p:
        raise HTTPException(404, "Presupuesto no encontrado")
    if p.estado != "enviado_gerente":
        raise HTTPException(409, f"El presupuesto esta en estado '{p.estado}'")
    p.estado = datos.resultado
    db.add(m.Autorizacion(presupuesto_id=p.id, usuario_id=usuario.id, nivel="gerente",
                          resultado=datos.resultado, comentario=datos.comentario))
    for admin in db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol).filter(
            m.Rol.nombre == "administrador").all():
        notificar(db, admin.id, f"Presupuesto {datos.resultado}",
                  f"{p.folio} - {datos.comentario or ''}. Recuerda avisar al mecanico "
                  f"{p.tecnico.nombre_completo} y registrar la constancia (CU-ADM-16).",
                  "presupuesto", "presupuesto", p.id)
    registrar_bitacora(db, usuario.id, f"presupuesto_{datos.resultado}", "presupuesto", p.id,
                       datos.comentario)
    db.commit()
    db.refresh(p)
    return svc.presupuesto_out(db, p)


# ---------------------------------------------------------------- CU-GER-09 -- #
@router.get("/atendidas")
def unidades_atendidas(dias: int = 30, usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    desde = ahora_utc() - timedelta(days=dias)
    ordenes = (db.query(m.OrdenServicio)
               .filter(m.OrdenServicio.fecha_salida >= desde).all())
    por_tipo, por_taller = {}, {}
    dias_totales = []
    for o in ordenes:
        por_tipo[o.tipo] = por_tipo.get(o.tipo, 0) + 1
        nombre = o.taller.nombre if o.taller else "-"
        por_taller[nombre] = por_taller.get(nombre, 0) + 1
        if o.fecha_salida and o.fecha_entrada:
            dias_totales.append((o.fecha_salida - o.fecha_entrada).days)
    return {
        "periodo_dias": dias, "total": len(ordenes),
        "por_tipo": por_tipo, "por_taller": por_taller,
        "dias_promedio": round(sum(dias_totales) / len(dias_totales), 1) if dias_totales else 0,
    }


@router.get("/penalizaciones")
def ranking_avisos(usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """Cuantos avisos acumula cada chofer y cuantos siguen sin atender.

    NO es un ranking de castigos: el sistema solo avisa y la conversacion la
    tienen el gerente y Erick en persona. Por eso `abiertos` va aparte del
    total -- lo accionable es lo que nadie ha cerrado.

    Leia `Penalizacion`, tabla de la v1.1 que ya nadie escribe: la lista salia
    vacia siempre.
    """
    filas = (db.query(m.AvisoIncumplimiento.chofer_id,
                      func.count(m.AvisoIncumplimiento.id))
             .group_by(m.AvisoIncumplimiento.chofer_id).all())
    out = []
    for cid, n in filas:
        abiertos = (db.query(func.count(m.AvisoIncumplimiento.id))
                    .filter(m.AvisoIncumplimiento.chofer_id == cid,
                            m.AvisoIncumplimiento.estado == "abierto").scalar() or 0)
        out.append({"chofer_id": cid, "chofer": svc.nombre_chofer(db, cid),
                    "total": n, "abiertos": abiertos})
    return sorted(out, key=lambda x: (-x["abiertos"], -x["total"]))
