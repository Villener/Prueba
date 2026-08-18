"""Procesos automaticos - CU-AUT-01 a CU-AUT-03.

Actor: "Programador de tareas" (el reloj del sistema). Un caso de uso sin actor
esta mal formado; estos tres los dispara el tiempo, no una persona.
"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from . import models as m
from . import services as svc
from .security import notificar


def _config(db: Session, clave: str, defecto: int) -> int:
    c = db.query(m.Configuracion).filter(m.Configuracion.clave == clave).first()
    try:
        return int(c.valor) if c else defecto
    except (TypeError, ValueError):
        return defecto


def generar_penalizaciones(db: Session) -> int:
    """CU-AUT-01 / RN-05.

    La penalizacion se emite contra el POSEEDOR de la unidad a la fecha limite
    (RN-01, RI-09), no contra el titular. Es la regla que sostiene todo el modulo.
    """
    tolerancia = _config(db, "dias_tolerancia_penalizacion", 0)
    limite = date.today() - timedelta(days=tolerancia)
    creadas = 0

    vencidos = (db.query(m.ProgramaMantenimiento)
                .filter(m.ProgramaMantenimiento.estado == "pendiente",
                        m.ProgramaMantenimiento.fecha_limite < limite).all())
    for p in vencidos:
        p.estado = "vencido"
        ya = (db.query(m.Penalizacion)
              .filter(m.Penalizacion.programa_mantenimiento_id == p.id).first())
        if ya:
            continue
        poseedor = svc.poseedor_actual(db, p.unidad)
        if not poseedor:
            continue
        dias = (date.today() - p.fecha_limite).days
        prest = svc.prestamo_activo(db, p.unidad_id)
        nota = " (poseedor por prestamo activo)" if prest and prest.estado == "activo" else ""
        db.add(m.Penalizacion(
            chofer_id=poseedor, unidad_id=p.unidad_id, programa_mantenimiento_id=p.id,
            motivo=f"No ingreso la unidad {p.unidad.num_economico} al taller para "
                   f"'{p.plan.nombre if p.plan else 'mantenimiento'}' "
                   f"(limite {p.fecha_limite}){nota}",
            dias_atraso=dias, estado="aplicada"))
        notificar(db, poseedor, "Penalizacion aplicada",
                  f"Unidad {p.unidad.num_economico}: mantenimiento vencido hace {dias} dias. "
                  "Puedes levantar una inconformidad desde tu modulo.",
                  "penalizacion", "programa_mantenimiento", p.id)
        creadas += 1

    db.commit()
    return creadas


def generar_alertas_unidades_paradas(db: Session) -> int:
    """CU-AUT-02 / RN-08: alerta recurrente hasta que se atienda."""
    meses = _config(db, "meses_unidad_parada", 3)
    corte = datetime.utcnow() - timedelta(days=30 * meses)
    nuevas = 0

    ordenes = (db.query(m.OrdenServicio)
               .filter(m.OrdenServicio.estado != "cerrada",
                       m.OrdenServicio.fecha_entrada < corte).all())
    gerentes = (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
                .filter(m.Rol.nombre == "gerente").all())

    for o in ordenes:
        alerta = (db.query(m.AlertaGerencia)
                  .filter(m.AlertaGerencia.tipo == "unidad_parada_3_meses",
                          m.AlertaGerencia.unidad_id == o.unidad_id,
                          m.AlertaGerencia.atendida.is_(False)).first())
        dias = (datetime.utcnow() - o.fecha_entrada).days
        detalle = (f"Unidad {o.unidad.num_economico} lleva {dias} dias en "
                   f"{o.taller.nombre if o.taller else 'taller'} (orden {o.folio})")
        if alerta:
            # Reincide: vuelve a notificar mientras no se atienda.
            alerta.veces_notificada += 1
            alerta.ultima_notificacion = datetime.utcnow()
            alerta.detalle = detalle
        else:
            alerta = m.AlertaGerencia(tipo="unidad_parada_3_meses", unidad_id=o.unidad_id,
                                      detalle=detalle)
            db.add(alerta)
            nuevas += 1
        for g in gerentes:
            notificar(db, g.id, "Unidad parada mas de 3 meses", detalle, "alerta")

    db.commit()
    return nuevas


def cerrar_prestamos_vencidos(db: Session) -> int:
    """CU-AUT-03 / RN-03: al vencer, la responsabilidad vuelve al titular."""
    cerrados = 0
    vencidos = (db.query(m.PrestamoUnidad)
                .filter(m.PrestamoUnidad.estado == "activo",
                        m.PrestamoUnidad.fecha_fin_prevista < date.today()).all())
    for p in vencidos:
        p.estado = "vencido"
        p.fecha_fin_real = datetime.utcnow()
        p.unidad.poseedor_chofer_id = p.chofer_presta_id
        notificar(db, p.chofer_presta_id, "Prestamo vencido",
                  f"La unidad {p.unidad.num_economico} regreso a tu responsabilidad "
                  "por vencimiento del prestamo (RN-03).", "prestamo")
        notificar(db, p.chofer_recibe_id, "Prestamo vencido",
                  f"Ya no eres responsable de la unidad {p.unidad.num_economico}.", "prestamo")
        cerrados += 1
    db.commit()
    return cerrados


def correr_todos(db: Session) -> dict:
    return {
        "penalizaciones_generadas": generar_penalizaciones(db),
        "alertas_nuevas": generar_alertas_unidades_paradas(db),
        "prestamos_cerrados": cerrar_prestamos_vencidos(db),
    }
