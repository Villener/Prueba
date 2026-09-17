"""Modulo Perito - nota 9 de la junta del 2026-09-14.

EDGAR ES DE LA CASA, y eso es lo que cambia el flujo.

`requerimientos.md` lo tenia como actor EXTERNO --"peritos / aseguradora"-- y
con eso la unica forma de registrar un peritaje era que el chofer teclease,
despues, el folio que un tercero le habia dado. Asi seguia siendo hasta hoy:
`POST /chofer/averias/{id}/peritaje` es del chofer.

Siendo interno, el orden se invierte: se le AVISA desde el sistema y el levanta
el peritaje DENTRO. El folio deja de ser un dato de segunda mano.

El endpoint del chofer NO se quita. La aseguradora sigue siendo externa y hay
casos donde llega su ajustador primero; quitarlo dejaria esos casos sin forma de
registrarse. Pero cuando lo levanta Edgar queda a su nombre, que es la
diferencia que importa cuando alguien pregunta quien dijo que la unidad se podia
mover.

LO QUE ESTE MODULO NO RESUELVE, y hay que preguntarle al cliente (pregunta
abierta #15): si Edgar es el UNICO perito y no contesta de madrugada, el
arrastre se queda bloqueado por RN-04 sin salida. Hace falta un suplente o una
regla de escalamiento. Aqui se deja visible --la bandeja ordena por antiguedad y
marca las que llevan horas-- pero visible no es resuelto.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import models as m
from ... import services as svc
from ...core.database import get_db
from ...core.security import notificar, registrar_bitacora, require_roles
from ...core.tiempo import ahora_utc
from ...schemas import PeritajeIn
from . import emergencias_service as emsvc

router = APIRouter(prefix="/api/perito", tags=["perito"])
solo_perito = require_roles("perito")

# A partir de aqui, una unidad esperando peritaje se marca como urgente. No es
# un umbral tecnico: es que una unidad parada en la calle cuesta dinero y
# estorba, y a las dos horas ya es un problema de otro tipo.
HORAS_URGENTE = 2


def _horas_esperando(r: m.ReporteAveria) -> float | None:
    if not r.fecha_hora:
        return None
    ref = r.fecha_hora
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=datetime.timezone.utc)
    return round((ahora_utc() - ref).total_seconds() / 3600, 1)


@router.get("/pendientes")
def pendientes(db: Session = Depends(get_db), usuario=Depends(solo_perito)):
    """La bandeja de Edgar: lo que espera peritaje para poder moverse.

    Solo entra lo que de verdad lo necesita:
      - todo CHOQUE sin peritaje, haya sido donde haya sido (RN-16);
      - las AVERIAS en vialidad publica sin peritaje (RN-04).

    Una averia en el patio de un cliente no aparece aqui, y esta bien: no hay
    nada que peritar y llenarle la bandeja de casos que no le tocan es como se
    deja de mirar la bandeja.
    """
    fuera = []
    for r in (db.query(m.ReporteAveria)
              .filter(m.ReporteAveria.estado.notin_(["cerrado", "cancelado"])).all()):
        if r.peritaje is not None:
            continue
        if not (r.tipo == "choque" or r.en_vialidad_publica):
            continue
        horas = _horas_esperando(r)
        fuera.append({
            "id": r.id, "folio": r.folio, "tipo": r.tipo,
            "unidad": r.unidad.num_economico if r.unidad else "-",
            "chofer": emsvc.nombre_chofer(db, r.chofer_id) or "-",
            "fecha_hora": r.fecha_hora,
            "latitud": r.latitud, "longitud": r.longitud,
            "direccion_referencia": r.direccion_referencia,
            "descripcion": r.descripcion_falla,
            "en_vialidad_publica": r.en_vialidad_publica,
            "horas_esperando": horas,
            "urgente": bool(horas is not None and horas >= HORAS_URGENTE),
            "hay_lesionados": bool(r.detalle_choque and r.detalle_choque.hay_lesionados),
            "cuantos_terceros": (r.detalle_choque.cuantos_terceros
                                 if r.detalle_choque else None),
            "fotos": emsvc.fotos_de(db, "reporte_averia", r.id),
            # Es lo que este peritaje va a desbloquear. Sin decirlo, el perito no
            # sabe que su firma es lo unico que detiene a la unidad.
            "bloquea_movimiento": not emsvc.puede_solicitar_arrastre(r),
        })
    # Lo mas viejo primero: es lo que lleva mas tiempo detenido.
    fuera.sort(key=lambda x: (not x["urgente"], -(x["horas_esperando"] or 0)))
    return fuera


@router.post("/{reporte_id}/peritaje")
def levantar_peritaje(reporte_id: int, datos: PeritajeIn,
                      db: Session = Depends(get_db), usuario=Depends(solo_perito)):
    """Edgar levanta el peritaje DENTRO del sistema, y queda a su nombre.

    Esto desbloquea el movimiento de la unidad: es la llave de RN-04 y de RN-16.
    """
    r = db.query(m.ReporteAveria).filter(m.ReporteAveria.id == reporte_id).first()
    if not r:
        raise HTTPException(404, "No existe ese reporte.")
    if r.peritaje:
        raise HTTPException(409, "Ese reporte ya tiene peritaje registrado.")
    if not (datos.folio_peritos or "").strip():
        raise HTTPException(400, "El folio del peritaje es lo que desbloquea la unidad; "
                                 "sin el, no sirve de nada.")

    db.add(m.ReportePeritaje(
        reporte_averia_id=r.id,
        folio_peritos=datos.folio_peritos.strip(),
        aseguradora=datos.aseguradora,
        # Se guarda quien lo levanto, no lo que alguien dijo que se llamaba.
        nombre_perito=usuario.nombre_completo,
        hora_llegada_perito=ahora_utc(),
        observaciones=datos.observaciones))
    if r.estado == "esperando_peritos":
        r.estado = "en_atencion"
    db.flush()

    detalle = (f"Unidad {r.unidad.num_economico if r.unidad else '-'}: peritaje levantado "
               f"por {usuario.nombre_completo}, folio {datos.folio_peritos}. "
               "La unidad ya se puede mover.")
    # Al chofer que esta parado junto a la unidad, y a quien tiene que despachar.
    notificar(db, r.chofer_id, "Peritaje listo", detalle,
              "averia", "reporte_averia", r.id)
    if r.supervisor_notificado_id:
        notificar(db, r.supervisor_notificado_id, "Peritaje listo", detalle,
                  "averia", "reporte_averia", r.id)
    for u in (db.query(m.Usuario).join(m.UsuarioRol).join(m.Rol)
              .filter(m.Rol.nombre == "administrador").all()):
        notificar(db, u.id, "Peritaje listo", detalle, "averia", "reporte_averia", r.id)

    registrar_bitacora(db, usuario.id, "levantar_peritaje", "reporte_averia", r.id,
                       f"folio {datos.folio_peritos}")
    db.commit()
    db.refresh(r)
    return svc.averia_out(db, r)


@router.get("/historial")
def historial(dias: int = 90, db: Session = Depends(get_db),
              usuario=Depends(solo_perito)):
    """Los peritajes que ya levanto, para poder consultarse a si mismo."""
    dias = max(1, min(dias, 730))
    desde = ahora_utc() - datetime.timedelta(days=dias)
    fuera = []
    for p in db.query(m.ReportePeritaje).all():
        ref = p.hora_llegada_perito or p.hora_aviso
        if ref and ref.tzinfo is None:
            ref = ref.replace(tzinfo=datetime.timezone.utc)
        if ref and ref < desde:
            continue
        r = p.reporte if hasattr(p, "reporte") else None
        rep = r or (db.query(m.ReporteAveria)
                    .filter(m.ReporteAveria.id == p.reporte_averia_id).first())
        fuera.append({
            "id": p.id, "folio_peritos": p.folio_peritos,
            "aseguradora": p.aseguradora, "nombre_perito": p.nombre_perito,
            "cuando": ref, "observaciones": p.observaciones,
            "reporte_folio": rep.folio if rep else None,
            "tipo": rep.tipo if rep else None,
            "unidad": rep.unidad.num_economico if rep and rep.unidad else None,
        })
    fuera.sort(key=lambda x: (x["cuando"] is None, x["cuando"]), reverse=True)
    return fuera
