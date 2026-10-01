"""Modulo Gerente - CU-GER-01 a CU-GER-09."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import models as m
from ... import services as svc
from ...core.database import get_db
from ...schemas import (AlertaOut, IncumplimientoOut, KpiOut, MensajeOut, OrdenServicioOut,
                       PresupuestoOut, ResolucionPresupuestoIn)
from ...core.security import notificar, registrar_bitacora, require_roles
from ...core.tiempo import ahora_utc, dia_operativo

from . import estadisticas, historiales, patios
from .exportar_historial import construir as construir_historial
from .exportar_tablero import construir as construir_tablero

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
    # Y solo unidades activas: una dada de baja no tiene chofer que incumpla.
    incumpliendo = (db.query(func.count(func.distinct(m.Unidad.poseedor_chofer_id)))
                    .select_from(m.ProgramaMantenimiento).join(m.Unidad)
                    .filter(m.ProgramaMantenimiento.estado.in_(["pendiente", "vencido"]),
                            m.ProgramaMantenimiento.fecha_limite < date.today(),
                            m.Unidad.activo.is_(True)).scalar() or 0)
    retrasos = [p.dias_retraso_captura for p in db.query(m.Presupuesto).all()
                if p.dias_retraso_captura is not None]
    # TODOS LOS CONTEOS DE FLOTA VAN SOBRE UNIDADES ACTIVAS, y hasta hoy no era
    # asi. El tablero deci­a 1,367 unidades cuando la operacion trabaja con 628:
    # el resto son bajas que siguen en el padron. El director lo noto en la
    # primera revision -- "son demasiadas unidades para las que estamos usando"
    # -- y tenia razon: un porcentaje de ocupacion o de cumplimiento calculado
    # contra una flota que ya no existe sale sistematicamente bajo, y no por
    # culpa del taller.
    #
    # `unidades_total` conserva su nombre para no romper la pantalla, pero ya
    # cuenta solo las activas. El total del padron se sigue pudiendo ver en los
    # Historiales, que es donde tiene sentido mirar una unidad dada de baja.
    activas = m.Unidad.activo.is_(True)
    return {
        "unidades_total": db.query(func.count(m.Unidad.id)).filter(
            activas).scalar() or 0,
        "unidades_en_taller": db.query(func.count(m.Unidad.id)).filter(
            activas,
            m.Unidad.estado.in_(["en_taller", "en_reparacion"])).scalar() or 0,
        "unidades_en_ruta": db.query(func.count(m.Unidad.id)).filter(
            activas, m.Unidad.estado == "en_ruta").scalar() or 0,
        "unidades_varadas": db.query(func.count(m.Unidad.id)).filter(
            activas,
            m.Unidad.estado.in_(["varada", "en_arrastre"])).scalar() or 0,
        "ocupacion_pct": round(ocupados * 100 / total_esp, 1) if total_esp else 0.0,
        "espacios_ocupados": ocupados, "espacios_totales": total_esp,
        "choferes_incumpliendo": incumpliendo,
        # Lee AvisoIncumplimiento, NO la tabla `penalizacion`. Esa quedo del
        # modelo v1.1 y desde que la penalizacion desaparecio nadie la escribe:
        # el indicador daba 0 siempre aunque hubiera avisos abiertos. Y es el
        # numero que motiva el proyecto (RF-GER-02), asi que mentia justo donde
        # mas importa. Se conserva la clave vieja para no romper la pantalla.
        "avisos_mes": db.query(func.count(m.AvisoIncumplimiento.id)).filter(
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
    # Una unidad dada de baja o bloqueada por Logistica no se le cobra a nadie.
    progs = (db.query(m.ProgramaMantenimiento).join(m.Unidad)
             .filter(m.ProgramaMantenimiento.estado.in_(["pendiente", "vencido"]),
                     m.ProgramaMantenimiento.fecha_limite < date.today(),
                     m.Unidad.activo.is_(True)).all())
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


@router.get("/patios")
def patios_plantas(usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """Las plantas con taller, con cuantas unidades tienen adentro y en flota."""
    return patios.plantas(db)


@router.get("/patios/{taller_id}")
def patio_planta(taller_id: int, usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """Que hay en el patio de esa planta (croquis, ordenes y Excel) y su flota."""
    t = db.get(m.Taller, taller_id)
    if not t:
        raise HTTPException(404, "Taller no encontrado")
    return patios.patio(db, t)


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


@router.get("/incumplimientos-acumulados")
def incumplimientos_acumulados(usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """El HISTORICO por chofer: avisos acumulados, sin atender y amonestaciones.

    Son tres numeros distintos y conviene no confundirlos, porque la pantalla los
    ponia juntos bajo la palabra "penalizaciones" y se leian como uno:

      acumulados   -> todas las veces que el chofer ha faltado a una cita
                      confirmada. Es historia; no baja nunca.
      sin_atender  -> de esas, las que nadie ha cerrado todavia. Es lo accionable.
      amonestadas  -> de esas, las que una persona convirtio en acto formal
                      (RN-14). Puede ser menos que los avisos: no toda falta se
                      amonesta, y eso es a proposito.

    "Penalizacion" era la palabra de la v1.1, y su tabla ya nadie la escribe --
    hoy tiene cero filas en produccion. Se deja de usar en la interfaz para que
    no conviva con "aviso" y "amonestacion" significando lo mismo.
    """
    filas = (db.query(m.AvisoIncumplimiento.chofer_id,
                      func.count(m.AvisoIncumplimiento.id))
             .group_by(m.AvisoIncumplimiento.chofer_id).all())
    out = []
    for cid, n in filas:
        abiertos = (db.query(func.count(m.AvisoIncumplimiento.id))
                    .filter(m.AvisoIncumplimiento.chofer_id == cid,
                            m.AvisoIncumplimiento.estado == "abierto").scalar() or 0)
        amonestadas = (db.query(func.count(m.Amonestacion.id))
                       .filter(m.Amonestacion.chofer_id == cid,
                               m.Amonestacion.estado != "anulada").scalar() or 0)
        out.append({"chofer_id": cid, "chofer": svc.nombre_chofer(db, cid),
                    "amonestadas": amonestadas,
                    "total": n, "abiertos": abiertos})
    return sorted(out, key=lambda x: (-x["abiertos"], -x["total"]))


# ------------------------------------------------------ RF-GER-14/15/17/18 -- #
def _rango_por_defecto(gran: str, desde: date | None,
                       hasta: date | None) -> tuple[date, date]:
    """Completa las fechas que no vinieron en la peticion.

    La pantalla del gerente siempre manda las dos: son dos calendarios y el
    navegador no lo deja entrar sin ellas. El defecto es para la primera carga,
    para quien pegue la URL a mano y para el dia que alguien llame al endpoint
    desde otro lado -- y tiene que ser un rango que se pueda VER, no solo uno
    que no truene.

    Por eso la ventana depende de la granularidad, en vez de ser "los ultimos
    12 meses" siempre. Doce meses significan cosas distintas en cada corte: por
    mes son 12 barras que caben en la pantalla; por dia son 365, que pasan el
    limite de lo legible mucho antes de pasar el TOPE_PERIODOS del calculo, y
    el gerente abriria el tablero en un amasijo de rayas verticales y
    concluiria que la pantalla no sirve.

      dia   -> 30 dias. El mes corrido, que es el horizonte con el que se
               trabaja el taller (la meta de preventivos se lee por dia).
      mes   -> 12 meses. Un ano completo, que es lo unico que deja ver
               estacionalidad -- y es la MISMA ventana que ya trae por omision
               la pantalla de estadisticas (cuantos=12), asi que las dos
               pantallas arrancan mostrando el mismo periodo y no parecen
               contradecirse al abrirlas.
      anio  -> 5 anos. El historico util empieza en 2021 (los movimientos de
               taller mas viejos), asi que pedir mas solo agrega barras vacias.
    """
    hasta = hasta or dia_operativo(ahora_utc())
    if desde:
        return desde, hasta
    if gran == "dia":
        return hasta - timedelta(days=29), hasta
    if gran == "anio":
        return date(hasta.year - 4, 1, 1), hasta
    # Once meses hacia atras y no doce: el periodo que contiene a `hasta` ya
    # cuenta como uno, y restar doce devolveria trece barras.
    y, mth = hasta.year, hasta.month - 11
    while mth <= 0:
        y, mth = y - 1, mth + 12
    return date(y, mth, 1), hasta


@router.get("/tablero-rango")
def tablero_por_rango(desde: date | None = None, hasta: date | None = None,
                      granularidad: str = "mes", usuario=Depends(solo_ger),
                      db: Session = Depends(get_db)):
    """CU-GER-12: los cuatro indicadores de las unidades entre dos fechas.

    Es lo que el gerente pidio despues de la junta: marcar del calendario 1 al
    calendario 2, elegir dia, mes o ano, y ver en SU modulo el tiempo promedio
    de reparacion, el porcentaje de citas concretadas, las citas totales y las
    atenciones. Hasta hoy la mitad de esos numeros solo se veian entrando al
    modulo del administrador con otro correo y otra contrasena, y una segunda
    cuenta para mirar tus propios numeros es una cuenta que se presta.

    `desde` y `hasta` se anotan como `date` a proposito: es la anotacion la que
    hace que FastAPI parsee el YYYY-MM-DD de la URL y devuelva un 422 claro
    cuando llega basura. Sin el tipo llegarian como texto y el error reventaria
    mas adentro, en el calculo, donde ya no se sabe de donde vino.
    """
    desde, hasta = _rango_por_defecto(granularidad, desde, hasta)
    return estadisticas.tablero_rango(db, desde, hasta, granularidad)


@router.get("/estadisticas")
def estadisticas_en_el_tiempo(granularidad: str = "mes", cuantos: int = 12,
                              desde: date | None = None, hasta: date | None = None,
                              usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """CU-GER-12: los mismos indicadores por dia, por mes o por ano.

    El tablero de arriba ensena el AHORA. Esto contesta "como vamos", que es
    otra pregunta y la que el cliente pidio en la junta.

    `desde` y `hasta` llegaron despues y son OPCIONALES a proposito: sin ellos
    el endpoint responde exactamente lo que respondia antes --los ultimos
    `cuantos` periodos hacia atras-- porque hay pantalla viva llamandolo asi y
    un cambio de firma la habria dejado con una grafica vacia sin que nadie
    tocara el frontend. Con ellos, el rango son las dos fechas del calendario y
    `cuantos` se ignora, que es lo que necesita el tablero nuevo para que las
    tres graficas de la pantalla hablen del MISMO periodo.
    """
    return estadisticas.serie(db, granularidad, cuantos, hasta=hasta, desde=desde)


@router.get("/cumplimiento-choferes")
def cumplimiento_por_chofer(granularidad: str = "mes", cuantos: int = 6,
                            desde: date | None = None, hasta: date | None = None,
                            usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """CU-GER-14: quien cumple y quien no, cortado por mes o por ano.

    Se mide sobre CITAS CONFIRMADAS. Una unidad a la que el taller nunca le dio
    cita no entra en este calculo: eso mide al taller, no al chofer.

    Los dos parametros de rango se pasan por NOMBRE y no por posicion. En la
    firma de cumplimiento_choferes() `desde` va hasta el final, despues de
    `limite`, y mandarlo en el lugar equivocado no truena: recorta la tabla a
    unos pocos choferes y se lee como si los demas no tuvieran citas.
    """
    return estadisticas.cumplimiento_choferes(db, granularidad, cuantos,
                                              hasta=hasta, desde=desde)


@router.get("/exportar/tablero")
def exportar_tablero_gerente(desde: date | None = None, hasta: date | None = None,
                             granularidad: str = "mes", usuario=Depends(solo_ger),
                             db: Session = Depends(get_db)):
    """El tablero del rango en Excel, para el reporte que sube a direccion.

    Sin este boton lo que pasa es lo de siempre: el gerente teclea a mano en su
    hoja los numeros que ve en la grafica, y a la tercera vez uno no coincide.
    Los cuatro indicadores del archivo salen de la MISMA funcion que pinta la
    pantalla (ver exportar_tablero.py), no de una segunda cuenta.

    El nombre del archivo lo devuelve el constructor y no se arma aqui: si el
    gerente invirtio los calendarios o el rango se recorto por el tope de
    periodos, las fechas que van adentro no son las que el pidio, y un archivo
    que se llama distinto de lo que trae es el que se cita en una junta con el
    rango equivocado.
    """
    desde, hasta = _rango_por_defecto(granularidad, desde, hasta)
    datos, nombre = construir_tablero(db, desde, hasta, granularidad)
    registrar_bitacora(db, usuario.id, "tablero_exportado", "taller", None, nombre)
    db.commit()
    return Response(
        content=datos,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/choferes/{chofer_id}/expediente")
def expediente_chofer(chofer_id: int, usuario=Depends(solo_ger),
                      db: Session = Depends(get_db)):
    """CU-GER-13: el historial acumulado de un chofer.

    Sirve para sostener una amonestacion con historial Y para defender al chofer
    al que el taller nunca le dio cita. Las dos cosas importan.
    """
    return estadisticas.expediente(db, chofer_id)


# ------------------------------------------------- LOS CUATRO HISTORIALES -- #
# El administrador de taller ya asigna unidades a mecanicos en el modulo de
# Reporte de Mantenimiento, pero ese dato se quedaba adentro del formato: para
# saber que le toco a cada mecanico habia que abrir reporte por reporte. El
# gerente pidio verlo desde SU modulo --todos los mecanicos con su historial de
# preventivos y a que unidades fueron-- y de paso el historial de cada unidad,
# de cada chofer y de cada taller, con su Excel.
#
# ESTOS ENDPOINTS NO CALCULAN NADA. Todo vive en historiales.py, que es la capa
# que no sabe de HTTP, y el Excel sale de la MISMA funcion que la pantalla
# (historiales.tabla_para_excel). Es la regla que ya obedecen tablero_rango y
# exportar_tablero, y esta escrita ahi por que: el dia que la pantalla y el
# archivo calculen cada uno por su lado van a discrepar, y el gerente deja de
# creerle a los dos.
#
# EL RANGO POR OMISION SE PIDE CON "mes" y por lo tanto son los ultimos doce
# meses, no los ultimos treinta dias. Un historial no es un tablero: la pregunta
# normal aqui es "a que unidades fue este mecanico", y con una ventana de un mes
# la pantalla abre casi vacia y se lee como que el sistema no tiene datos. Doce
# meses es ademas la MISMA ventana con la que arranca el tablero del gerente, de
# modo que las dos pantallas empiezan hablando del mismo periodo. El espejo de
# esta decision esta en rangoPorDefecto() de GerentePage.jsx; si dejaran de
# coincidir, la pantalla y un enlace pegado a mano sin fechas mostrarian
# periodos distintos y nadie sabria cual de los dos citar.
def _rango_historial(desde: date | None, hasta: date | None) -> tuple[date, date]:
    return _rango_por_defecto("mes", desde, hasta)


@router.get("/historiales/mecanicos")
def historial_de_mecanicos(desde: date | None = None, hasta: date | None = None,
                           tipo: str = "todos", taller_id: int | None = None,
                           usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """Todos los mecanicos con su trabajo en el rango, y a que unidades fueron.

    Se listan TODOS los tecnicos activos, incluidos los que no tienen un solo
    trabajo en el rango. Un mecanico en cero es informacion --puede ser que nadie
    le asigna nada, o que nadie lo captura-- y omitirlo lo esconderia justo
    cuando hay que mirarlo.
    """
    desde, hasta = _rango_historial(desde, hasta)
    return historiales.historial_mecanicos(db, desde, hasta, tipo, taller_id)


@router.get("/historiales/mecanicos/{tecnico_id}")
def historial_de_un_mecanico(tecnico_id: int, desde: date | None = None,
                             hasta: date | None = None, tipo: str = "todos",
                             usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    desde, hasta = _rango_historial(desde, hasta)
    datos = historiales.historial_mecanico(db, tecnico_id, desde, hasta, tipo)
    if datos is None:
        # 404 y no un expediente vacio. Un expediente vacio de un tecnico que no
        # existe se lee como "este mecanico no ha hecho nada", que es una
        # afirmacion sobre una persona y ademas falsa.
        raise HTTPException(404, "Ese mecanico no existe")
    return datos


@router.get("/historiales/unidades")
def historial_de_unidades(desde: date | None = None, hasta: date | None = None,
                          taller_id: int | None = None,
                          solo_con_actividad: bool = True,
                          usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """El historial de la flota en el rango, una linea por unidad.

    `solo_con_actividad` viene en True y es distinto del criterio de los
    mecanicos a proposito: de las 1,367 unidades la enorme mayoria simplemente no
    piso el taller en el rango, y eso es lo normal --es una flota que trabaja--.
    Una tabla donde el 90% de los renglones son ceros esconde el 10% que hay que
    mirar. Se deja el parametro para quien necesite el padron completo.
    """
    desde, hasta = _rango_historial(desde, hasta)
    return historiales.historial_unidades(db, desde, hasta, taller_id,
                                          solo_con_actividad)


@router.get("/historiales/unidades/{unidad_id}")
def historial_de_una_unidad(unidad_id: int, desde: date | None = None,
                            hasta: date | None = None,
                            usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    desde, hasta = _rango_historial(desde, hasta)
    datos = historiales.historial_unidad(db, unidad_id, desde, hasta)
    if datos is None:
        raise HTTPException(404, "Esa unidad no existe")
    return datos


@router.get("/historiales/choferes")
def historial_de_choferes(desde: date | None = None, hasta: date | None = None,
                          usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    desde, hasta = _rango_historial(desde, hasta)
    return historiales.historial_choferes(db, desde, hasta)


@router.get("/historiales/choferes/{chofer_id}")
def historial_de_un_chofer(chofer_id: int, desde: date | None = None,
                           hasta: date | None = None,
                           usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """El expediente acumulado del chofer MAS la linea de tiempo del rango.

    El expediente no se recalcula: historial_chofer() llama a
    estadisticas.expediente(), que es la misma funcion que alimenta el modal de
    la pestana de Indicadores. Dos pantallas del gerente dando porcentajes
    distintos del mismo chofer es como se acaba la confianza en las dos.
    """
    desde, hasta = _rango_historial(desde, hasta)
    datos = historiales.historial_chofer(db, chofer_id, desde, hasta)
    if datos is None:
        raise HTTPException(404, "Ese chofer no existe")
    return datos


@router.get("/historiales/talleres")
def historial_de_talleres(desde: date | None = None, hasta: date | None = None,
                          usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    desde, hasta = _rango_historial(desde, hasta)
    return historiales.historial_talleres(db, desde, hasta)


@router.get("/historiales/talleres/{taller_id}")
def historial_de_un_taller(taller_id: int, desde: date | None = None,
                           hasta: date | None = None,
                           usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    desde, hasta = _rango_historial(desde, hasta)
    datos = historiales.historial_taller(db, taller_id, desde, hasta)
    if datos is None:
        raise HTTPException(404, "Ese taller no existe")
    return datos


@router.get("/exportar/historial/{dimension}")
def exportar_historial(dimension: str, desde: date | None = None,
                       hasta: date | None = None, tipo: str = "todos",
                       taller_id: int | None = None,
                       solo_con_actividad: bool = True,
                       usuario=Depends(solo_ger), db: Session = Depends(get_db)):
    """Cualquiera de los cuatro historiales en Excel, con los MISMOS filtros.

    Que el archivo salga del mismo filtro que tiene puesta la pantalla no es
    comodidad: si el boton exportara un rango fijo, el archivo que el gerente
    lleva a direccion diria otra cosa que la pantalla desde la que lo bajo, y esa
    discrepancia solo se descubre enfrente de direccion.

    La dimension se valida aqui y se contesta 404 en vez de dejar que
    tabla_para_excel() caiga a "mecanicos" por omision: pedir
    /exportar/historial/mecanico (en singular, que es el error de dedo natural) y
    recibir un archivo correcto pero de otra cosa es peor que recibir un error.
    """
    if dimension not in historiales.DIMENSIONES:
        raise HTTPException(404, "No existe el historial '%s'. Son: %s"
                                 % (dimension, ", ".join(historiales.DIMENSIONES)))
    desde, hasta = _rango_historial(desde, hasta)
    datos, nombre = construir_historial(db, dimension, desde, hasta, tipo,
                                        taller_id, solo_con_actividad)
    registrar_bitacora(db, usuario.id, "historial_exportado", "taller", None, nombre)
    db.commit()
    return Response(
        content=datos,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
