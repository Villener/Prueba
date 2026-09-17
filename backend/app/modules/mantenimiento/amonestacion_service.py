"""RN-14: emitir, consultar e inconformarse de una amonestacion.

TODA la justicia de la regla ya vive en el AVISO, y por eso la amonestacion
cuelga de el en vez de calcularse aparte. `generar_avisos_incumplimiento()` solo
crea un aviso cuando:

  - hubo una cita CONFIRMADA (o reprogramada), no una que el taller nunca dio;
  - la unidad NO se presento;
  - y apunta al POSEEDOR de ese dia, con el fundamento de por que era el (RN-01).

Al exigir un aviso para poder amonestar, las tres condiciones se heredan
gratis. Si manana cambia la definicion de incumplimiento, cambia en un solo
lugar y la amonestacion sigue siendo justa sin tocar este archivo.

QUIEN FIRMA. El sistema propone (CU-AUT-08), una persona emite (CU-SUP-10). El
cliente todavia no confirma si firma el supervisor, Erick o el gerente
--pregunta abierta #13-- asi que por ahora pueden los tres y queda registrado
cual de ellos fue. Cuando lo decida, se aprieta aqui.
"""
import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ... import models as m
from ...core.security import notificar, registrar_bitacora
from ...core.tiempo import ahora_utc

# Quien puede firmar hoy. Deliberadamente ancho hasta que el cliente responda.
ROLES_QUE_FIRMAN = {"supervisor", "administrador", "gerente"}


def _chofer_de_plantilla(db: Session, chofer_id: int, supervisor_id: int) -> bool:
    """El chofer cuelga de la plantilla de ese supervisor."""
    ch = db.query(m.Chofer).filter(m.Chofer.usuario_id == chofer_id).first()
    if not ch or not ch.plantilla_id:
        return False
    pl = db.query(m.Plantilla).filter(m.Plantilla.id == ch.plantilla_id).first()
    return bool(pl and pl.supervisor_id == supervisor_id)


def _nombre(db: Session, usuario_id) -> str | None:
    if not usuario_id:
        return None
    u = db.query(m.Usuario).filter(m.Usuario.id == usuario_id).first()
    return u.nombre_completo if u else None


def salida(db: Session, a: m.Amonestacion) -> dict:
    """Lo que ve quien la consulta. Incluye SIEMPRE de que falta salio."""
    av = a.aviso
    cita = None
    if av and av.cita_id:
        c = db.query(m.CitaTaller).filter(m.CitaTaller.id == av.cita_id).first()
        if c:
            cita = {"id": c.id, "fecha": c.fecha_cita.isoformat() if c.fecha_cita else None,
                    "estado": c.estado}
    unidad = None
    if av and av.unidad_id:
        u = db.query(m.Unidad).filter(m.Unidad.id == av.unidad_id).first()
        unidad = u.num_economico if u else None
    return {
        "id": a.id,
        "chofer_id": a.chofer_id,
        "chofer": _nombre(db, a.chofer_id),
        "consecutivo": a.consecutivo,
        "motivo": a.motivo,
        "nota": a.nota,
        "estado": a.estado,
        "fecha_emision": a.fecha_emision.isoformat() if a.fecha_emision else None,
        "emitida_por": _nombre(db, a.emitida_por_usuario_id),
        "inconformidad": a.inconformidad,
        "fecha_inconformidad": (a.fecha_inconformidad.isoformat()
                                if a.fecha_inconformidad else None),
        "resolucion": a.resolucion,
        "resuelta_por": _nombre(db, a.resuelta_por_usuario_id),
        # El fundamento viaja con la amonestacion: sin esto, defenderse o
        # sostenerla obliga a ir a buscar la cita a otra pantalla.
        "aviso_id": a.aviso_id,
        "unidad": unidad,
        "cita": cita,
        "fundamento_poseedor": av.fundamento_poseedor if av else None,
        "dias_atraso": av.dias_atraso if av else None,
    }


def candidatas(db: Session, supervisor_id: int | None = None) -> list:
    """CU-AUT-08: las faltas que YA tienen aviso y todavia no tienen amonestacion.

    Esto es lo que el sistema "propone". No sanciona nada: arma la lista con el
    expediente listo para que una persona decida.
    """
    con_amonestacion = {a.aviso_id for a in db.query(m.Amonestacion).all()}
    q = (db.query(m.AvisoIncumplimiento)
         .filter(m.AvisoIncumplimiento.estado != "anulado"))
    fuera = []
    for av in q.all():
        if av.id in con_amonestacion:
            continue
        if supervisor_id and not _chofer_de_plantilla(db, av.chofer_id, supervisor_id):
            continue
        unidad = db.query(m.Unidad).filter(m.Unidad.id == av.unidad_id).first()
        previas = (db.query(m.Amonestacion)
                   .filter(m.Amonestacion.chofer_id == av.chofer_id,
                           m.Amonestacion.estado != "anulada").count())
        fuera.append({
            "aviso_id": av.id,
            "chofer_id": av.chofer_id,
            "chofer": _nombre(db, av.chofer_id),
            "unidad": unidad.num_economico if unidad else None,
            "fecha_falta": av.fecha_generacion.isoformat() if av.fecha_generacion else None,
            "dias_atraso": av.dias_atraso,
            "fundamento_poseedor": av.fundamento_poseedor,
            # Para que quien firma sepa si es la primera o la cuarta ANTES de firmar.
            "amonestaciones_previas": previas,
            "seria_la": previas + 1,
        })
    fuera.sort(key=lambda x: (x["fecha_falta"] or ""), reverse=True)
    return fuera


def emitir(db: Session, aviso_id: int, usuario_id: int, nota: str | None = None,
           supervisor_id: int | None = None) -> m.Amonestacion:
    """Firma la amonestacion sobre un aviso existente."""
    av = (db.query(m.AvisoIncumplimiento)
          .filter(m.AvisoIncumplimiento.id == aviso_id).first())
    if not av:
        raise HTTPException(404, "No existe ese aviso de incumplimiento. Sin aviso "
                                 "no hay amonestacion: el aviso es la prueba de que "
                                 "hubo una cita confirmada y el chofer no se presento.")
    if av.estado == "anulado":
        raise HTTPException(409, "Ese aviso esta anulado. No se puede amonestar sobre "
                                 "una falta que ya se dio por no ocurrida.")
    ya = (db.query(m.Amonestacion)
          .filter(m.Amonestacion.aviso_id == aviso_id).first())
    if ya:
        raise HTTPException(409, f"Esa falta ya tiene la amonestacion #{ya.id}. "
                                 "Una falta, una amonestacion.")
    if supervisor_id and not _chofer_de_plantilla(db, av.chofer_id, supervisor_id):
        raise HTTPException(403, "Ese chofer no es de tu plantilla.")

    previas = (db.query(m.Amonestacion)
               .filter(m.Amonestacion.chofer_id == av.chofer_id,
                       m.Amonestacion.estado != "anulada").count())
    unidad = db.query(m.Unidad).filter(m.Unidad.id == av.unidad_id).first()
    motivo = (f"No se presento a su cita de taller del "
              f"{av.fecha_generacion.isoformat() if av.fecha_generacion else 's/f'}"
              f" con la unidad {unidad.num_economico if unidad else 's/u'}.")

    a = m.Amonestacion(aviso_id=av.id, chofer_id=av.chofer_id,
                       consecutivo=previas + 1, motivo=motivo, nota=nota,
                       emitida_por_usuario_id=usuario_id, estado="emitida")
    db.add(a)
    db.flush()

    # El chofer se entera por el sistema, no por el pasillo (RF-CHO-15).
    notificar(db, av.chofer_id, f"Amonestacion #{a.consecutivo}",
              motivo + " Si no estas de acuerdo, puedes inconformarte desde aqui.",
              "amonestacion", "amonestacion", a.id)
    registrar_bitacora(db, usuario_id, "emitir_amonestacion", "amonestacion", a.id,
                       f"chofer {av.chofer_id}, aviso {av.id}, consecutivo {a.consecutivo}")
    db.commit()
    return a


def inconformarse(db: Session, amonestacion_id: int, chofer_id: int,
                  texto: str) -> m.Amonestacion:
    """RF-CHO-16: el chofer deja por escrito por que no esta de acuerdo."""
    a = (db.query(m.Amonestacion)
         .filter(m.Amonestacion.id == amonestacion_id).first())
    if not a:
        raise HTTPException(404, "No existe esa amonestacion.")
    if a.chofer_id != chofer_id:
        raise HTTPException(403, "Esa amonestacion no es tuya.")
    if a.estado in ("ratificada", "anulada"):
        raise HTTPException(409, "Esa amonestacion ya se resolvio; la inconformidad "
                                 "tenia que llegar antes.")
    if a.estado == "inconforme":
        raise HTTPException(409, "Ya te inconformaste de esa amonestacion.")
    if not (texto or "").strip():
        raise HTTPException(400, "Escribe por que no estas de acuerdo.")

    a.inconformidad = texto.strip()
    a.fecha_inconformidad = ahora_utc()
    a.estado = "inconforme"

    quien = _nombre(db, a.emitida_por_usuario_id)
    if a.emitida_por_usuario_id:
        notificar(db, a.emitida_por_usuario_id, "Inconformidad de un chofer",
                  f"{_nombre(db, chofer_id)} se inconformo de la amonestacion "
                  f"#{a.consecutivo}.", "amonestacion", "amonestacion", a.id)
    registrar_bitacora(db, chofer_id, "inconformarse_amonestacion", "amonestacion",
                       a.id, f"emitida por {quien}")
    db.commit()
    return a


def resolver(db: Session, amonestacion_id: int, usuario_id: int, ratifica: bool,
             texto: str | None = None) -> m.Amonestacion:
    """Cierra la inconformidad: o la sostiene, o la deja sin efecto.

    Anular NO borra el renglon. El expediente tiene que poder contar que hubo
    una amonestacion y que se echo para atras -- si desapareciera, el chofer
    perderia la prueba de que reclamo y le dieron la razon.
    """
    a = (db.query(m.Amonestacion)
         .filter(m.Amonestacion.id == amonestacion_id).first())
    if not a:
        raise HTTPException(404, "No existe esa amonestacion.")
    if a.estado in ("ratificada", "anulada"):
        raise HTTPException(409, "Esa amonestacion ya estaba resuelta.")
    if a.emitida_por_usuario_id == usuario_id and a.estado == "inconforme":
        # No lo impide -- hoy el cliente no dice quien revisa -- pero queda
        # escrito que reviso su propia decision.
        registrar_bitacora(db, usuario_id, "resolver_amonestacion_propia",
                           "amonestacion", a.id, "reviso su propia amonestacion")

    a.estado = "ratificada" if ratifica else "anulada"
    a.resolucion = (texto or "").strip() or None
    a.resuelta_por_usuario_id = usuario_id
    a.fecha_resolucion = ahora_utc()

    notificar(db, a.chofer_id,
              "Se resolvio tu inconformidad" if a.inconformidad else "Amonestacion resuelta",
              f"La amonestacion #{a.consecutivo} quedo {a.estado}."
              + (f" {a.resolucion}" if a.resolucion else ""),
              "amonestacion", "amonestacion", a.id)
    registrar_bitacora(db, usuario_id, "resolver_amonestacion", "amonestacion", a.id,
                       a.estado)
    db.commit()
    return a


def historial(db: Session, chofer_id: int) -> dict:
    """El expediente del chofer: lo que sostiene una amonestacion y lo que lo defiende."""
    todas = (db.query(m.Amonestacion)
             .filter(m.Amonestacion.chofer_id == chofer_id)
             .order_by(m.Amonestacion.fecha_emision.desc()).all())
    vigentes = [a for a in todas if a.estado != "anulada"]
    por_anio: dict = {}
    for a in vigentes:
        if a.fecha_emision:
            k = str(a.fecha_emision.year)
            por_anio[k] = por_anio.get(k, 0) + 1
    return {
        "chofer_id": chofer_id,
        "chofer": _nombre(db, chofer_id),
        "total": len(todas),
        "vigentes": len(vigentes),
        "anuladas": len(todas) - len(vigentes),
        "por_anio": [{"anio": k, "cuantas": v} for k, v in sorted(por_anio.items())],
        "amonestaciones": [salida(db, a) for a in todas],
    }
