"""Modulo Agenda - CU-ADM-13 a CU-ADM-16. El perfil de Victor.

Va en controller propio y no dentro de administrador_controller porque son
dos personas distintas con permisos distintos: Victor agenda y no autoriza
compras, Erick compra y no mueve la agenda. Hoy comparten el rol tecnico
`administrador` -- los cuatro perfiles del diagrama todavia no estan separados
en ROLES-- pero la frontera del modulo ya queda dibujada donde va a ir.

LA REGLA QUE SOSTIENE TODO ESTO:

    ProgramaMantenimiento.fecha_limite  viene del plan.  NUNCA se mueve.
    CitaTaller.fecha_cita               la asigna la agenda.  SI se mueve.

Por eso el chofer solo incumple si falto a una cita CONFIRMADA. Si el taller
nunca pudo darsela, el problema es de capacidad y sale por /sin-cupo, que es
otra lista y otro responsable.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ... import models as m
from ...core.database import get_db
from ...core.security import notificar, registrar_bitacora, require_roles
from ...core.tiempo import ahora_utc
from ...schemas import (CapacidadOut, CitaOut, MensajeOut, RecalculoOut,
                        ReprogramarIn, SinCupoOut)
from ..flota.flota_service import poseedor_actual
from . import agenda_service as agenda

router = APIRouter(prefix="/api/agenda", tags=["agenda"])
solo_agenda = require_roles("administrador")
agenda_o_gerente = require_roles("administrador", "gerente")


def _cita(db: Session, cita_id: int) -> m.CitaTaller:
    c = db.query(m.CitaTaller).filter(m.CitaTaller.id == cita_id).first()
    if not c:
        raise HTTPException(404, "La cita no existe")
    return c


# ---------------------------------------------------------------- CU-ADM-14 -- #
@router.get("/citas", response_model=list[CitaOut])
def listar_citas(taller_id: int | None = None, estado: str | None = None,
                 desde: date | None = None, hasta: date | None = None,
                 usuario=Depends(agenda_o_gerente), db: Session = Depends(get_db)):
    """Las citas de la agenda, ordenadas como las ordena el algoritmo.

    El orden es por `score_prioridad` y no por fecha a proposito: es el mismo
    con el que la cola decidio, asi que la pantalla ensena exactamente lo que
    el sistema penso. Si se ordenara por fecha, Victor no podria ver por que
    una unidad quedo antes que otra.
    """
    q = db.query(m.CitaTaller)
    if taller_id:
        q = q.filter(m.CitaTaller.taller_id == taller_id)
    if estado:
        q = q.filter(m.CitaTaller.estado == estado)
    else:
        q = q.filter(m.CitaTaller.estado.in_(agenda.ESTADOS_VIVOS))
    if desde:
        q = q.filter(m.CitaTaller.fecha_cita >= desde)
    if hasta:
        q = q.filter(m.CitaTaller.fecha_cita <= hasta)
    citas = q.order_by(m.CitaTaller.score_prioridad, m.CitaTaller.fecha_cita).all()
    return [agenda.cita_out(db, c) for c in citas]


# ---------------------------------------------------------------- CU-AUT-04 -- #
@router.post("/recalcular", response_model=RecalculoOut)
def recalcular(taller_id: int | None = None, usuario=Depends(solo_agenda),
               db: Session = Depends(get_db)):
    """Vuelve a repartir los programas pendientes sobre la capacidad real.

    Es el mismo calculo del job diario, expuesto para poder dispararlo a mano
    cuando Pedro acaba de liberar un espacio (disparador D1) o cuando Erick
    registra la ETA de unas piezas (D3) y la agenda ya puede planear sobre esa
    fecha. Solo mueve citas `propuesta` y confirmadas con mas de 48 h.
    """
    talleres = (db.query(m.Taller).filter(m.Taller.id == taller_id).all() if taller_id
                else db.query(m.Taller).filter(m.Taller.activo.is_(True)).all())
    if not talleres:
        raise HTTPException(404, "No hay taller que recalcular")
    total = {"propuestas": 0, "movidas": 0, "sin_cupo": 0}
    for t in talleres:
        r = agenda.recalcular(db, t)
        for k in total:
            total[k] += r[k]
    registrar_bitacora(db, usuario.id, "agenda_recalculada", "taller", taller_id,
                       datos_despues=str(total))
    db.commit()
    return total


# ---------------------------------------------------------------- CU-ADM-14 -- #
@router.post("/citas/{cita_id}/confirmar", response_model=CitaOut)
def confirmar(cita_id: int, usuario=Depends(solo_agenda), db: Session = Depends(get_db)):
    """Victor confirma la cita que el sistema propuso.

    A partir de aqui la cita deja de ser una propuesta y se vuelve un
    compromiso con el chofer: el recalculo ya no la mueve sola a menos de 48 h.
    Por eso se avisa al poseedor en el mismo acto -- confirmar sin avisar
    dejaria al chofer comprometido sin saberlo.
    """
    c = _cita(db, cita_id)
    if c.estado in ("cumplida", "no_asistio", "cancelada"):
        raise HTTPException(409, f"La cita ya esta {c.estado} y no se puede confirmar")

    c.estado = "confirmada"
    c.fecha_confirmacion_taller = ahora_utc()
    c.agendada_por_usuario_id = usuario.id

    poseedor_id = poseedor_actual(db, c.unidad) if c.unidad else None
    if poseedor_id:
        notificar(db, poseedor_id, "Tienes cita de taller",
                  f"Unidad {c.unidad.num_economico} en {c.taller.nombre} el "
                  f"{c.fecha_cita}. Confirma que te vas a presentar.",
                  "cita", entidad_tipo="cita_taller", entidad_id=c.id)
    registrar_bitacora(db, usuario.id, "cita_confirmada", "cita_taller", c.id)
    db.commit()
    db.refresh(c)
    return agenda.cita_out(db, c)


# ---------------------------------------------------------------- CU-ADM-15 -- #
@router.post("/citas/{cita_id}/reprogramar", response_model=CitaOut)
def reprogramar(cita_id: int, datos: ReprogramarIn, usuario=Depends(solo_agenda),
                db: Session = Depends(get_db)):
    """Mueve una cita a mano, incluso dentro de las 48 h.

    El recalculo automatico NO puede tocar una cita confirmada a menos de 48 h:
    al chofer que ya viene en camino no se le mueve la cita, porque a la tercera
    vez deja de mirar la app. Pero Victor SI puede, y eso es exactamente
    CU-ADM-15: la excepcion existe, tiene dueno y queda registrada como
    `requirio_autorizacion`.
    """
    c = _cita(db, cita_id)
    if c.estado in ("cumplida", "no_asistio", "cancelada"):
        raise HTTPException(409, f"La cita ya esta {c.estado} y no se puede mover")
    if datos.fecha_nueva < ahora_utc().date():
        raise HTTPException(400, "No se puede agendar en una fecha que ya paso")
    if not agenda.opera(c.taller, datos.fecha_nueva):
        raise HTTPException(400, f"{c.taller.nombre} no opera el {datos.fecha_nueva}")

    # El algoritmo automatico jamas coloca una cita donde no cabe; el movimiento
    # manual se lo saltaba entero. Se rechaza por omision y se puede forzar,
    # igual que la regla de las 48 h: la excepcion existe, tiene dueno y queda
    # registrada. Una agenda que cede a cualquier clic no es una agenda.
    faltantes = agenda.dias_sin_cupo(db, c, datos.fecha_nueva)
    if faltantes and not datos.forzar:
        dias = ", ".join(str(d) for d, _ in faltantes)
        raise HTTPException(409, {
            "mensaje": f"No hay espacio de {c.unidad.tipo.nombre} el {dias}. "
                       "Si aun asi la quieres meter, confirma el sobrecupo.",
            "dias_sin_cupo": [str(d) for d, _ in faltantes],
            "puede_forzar": True,
        })

    anterior = c.fecha_cita
    a_menos_de_48h = not agenda._movible(c)
    sobrecupo = bool(faltantes)

    db.add(m.Reprogramacion(
        cita_id=c.id, fecha_anterior=anterior, fecha_nueva=datos.fecha_nueva,
        motivo=datos.motivo, automatica=False,
        # Las dos excepciones que puede autorizar Victor van al mismo campo:
        # lo que importa auditar es que la movio a mano saltandose una regla.
        requirio_autorizacion=a_menos_de_48h or sobrecupo, usuario_id=usuario.id))

    c.fecha_cita = datos.fecha_nueva
    c.veces_reprogramada = (c.veces_reprogramada or 0) + 1
    # Vuelve a "reprogramada": el chofer tiene que confirmar la fecha nueva.
    # Dejarla en "confirmada" daria por bueno un compromiso que el chofer
    # todavia no acepto.
    c.estado = "reprogramada"
    c.fecha_confirmacion_chofer = None

    poseedor_id = poseedor_actual(db, c.unidad) if c.unidad else None
    if poseedor_id:
        notificar(db, poseedor_id, "Se movio tu cita de taller",
                  f"Unidad {c.unidad.num_economico}: pasa del {anterior} al "
                  f"{datos.fecha_nueva}. Confirma la fecha nueva.",
                  "cita", entidad_tipo="cita_taller", entidad_id=c.id)
    registrar_bitacora(db, usuario.id,
                       "cita_reprogramada_con_sobrecupo" if sobrecupo else "cita_reprogramada",
                       "cita_taller", c.id,
                       datos_antes=str(anterior), datos_despues=str(datos.fecha_nueva))
    db.commit()
    db.refresh(c)
    return agenda.cita_out(db, c)


@router.post("/citas/{cita_id}/cancelar", response_model=MensajeOut)
def cancelar(cita_id: int, motivo: str = "", usuario=Depends(solo_agenda),
             db: Session = Depends(get_db)):
    """Cancela la cita y devuelve el programa a la cola.

    El programa vuelve a `pendiente`, NO se cancela: la fecha limite sigue
    corriendo y la unidad sigue necesitando su servicio. Cancelar la cita no
    cancela la obligacion tecnica.
    """
    c = _cita(db, cita_id)
    c.estado = "cancelada"
    if c.programa_mantenimiento_id:
        prog = db.query(m.ProgramaMantenimiento).filter(
            m.ProgramaMantenimiento.id == c.programa_mantenimiento_id).first()
        if prog and prog.estado == "agendado":
            prog.estado = "pendiente"
    registrar_bitacora(db, usuario.id, "cita_cancelada", "cita_taller", c.id,
                       datos_despues=motivo)
    db.commit()
    return {"ok": True, "mensaje": "Cita cancelada. El programa vuelve a la cola."}


# ---------------------------------------------------------------- CU-ADM-16 -- #
@router.get("/sin-cupo", response_model=list[SinCupoOut])
def sin_cupo(taller_id: int | None = None, usuario=Depends(agenda_o_gerente),
             db: Session = Depends(get_db)):
    """Unidades que no alcanzan cita antes de su fecha limite.

    Esta lista existe separada del tablero de incumplimientos porque responde a
    otra pregunta y tiene otro responsable: aqui el que no dio abasto es el
    TALLER, no el chofer. Mezclarlas seria volver al defecto que este diseno
    vino a corregir.
    """
    taller = (db.query(m.Taller).filter(m.Taller.id == taller_id).first()
              if taller_id else None)
    hoy = ahora_utc().date()
    salida = []
    for p, cita in agenda.detectar_sin_cupo(db, taller):
        plan = p.plan
        t_id = agenda.taller_de(db, p.unidad)
        t = db.query(m.Taller).filter(m.Taller.id == t_id).first()
        # Si hay cita, el retraso se mide contra ELLA: es la fecha en la que la
        # unidad va a entrar de verdad. Si no hay, contra hoy, porque el reloj
        # del limite sigue corriendo mientras nadie le da cupo.
        referencia = cita.fecha_cita if cita else hoy
        salida.append({
            "programa_id": p.id,
            "unidad": p.unidad.num_economico if p.unidad else "-",
            "servicio": plan.tipo_servicio.nombre if plan and plan.tipo_servicio else "-",
            "fecha_limite": p.fecha_limite,
            "dias_vencido": (referencia - p.fecha_limite).days,
            "taller": t.nombre if t else "-",
        })
    salida.sort(key=lambda x: -x["dias_vencido"])
    return salida


@router.get("/capacidad", response_model=CapacidadOut)
def capacidad(taller_id: int, tipo_unidad_id: int, dias: int = 30,
              usuario=Depends(agenda_o_gerente), db: Session = Depends(get_db)):
    """Cupo libre dia por dia, para pintar el calendario.

    Se pide el tipo de unidad porque la capacidad NUNCA es global: el taller
    puede estar lleno de pipas y tener libres los espacios de reparto. Decir
    "el taller esta lleno" a secas es lo que hace fallar el calculo.
    """
    taller = db.query(m.Taller).filter(m.Taller.id == taller_id).first()
    if not taller:
        raise HTTPException(404, "El taller no existe")
    tipo = db.query(m.TipoUnidad).filter(m.TipoUnidad.id == tipo_unidad_id).first()
    if not tipo:
        raise HTTPException(404, "El tipo de unidad no existe")

    hoy = ahora_utc().date()
    from datetime import timedelta
    dias_out = []
    for i in range(max(1, min(dias, agenda.HORIZONTE_DIAS * 2))):
        d = hoy + timedelta(days=i)
        opera = agenda.opera(taller, d)
        dias_out.append({
            "fecha": d, "opera": opera,
            "libres": agenda.capacidad_libre(db, taller, d, tipo.id) if opera else 0,
        })
    return {"taller": taller.nombre, "tipo_unidad": tipo.nombre,
            "horizonte_dias": len(dias_out), "dias": dias_out}
