"""Modulo Capturista de datos - CU-CAP-01 a CU-CAP-05.

El puesto existe y tiene nombre en el archivo del cliente: en la hoja TALLER de
"INFO CHOFERES 2026 ACTUAL.xlsx", el empleado 13905 aparece como CAPTURISTA DE
DATOS en Alamos. Su trabajo diario es el libro `REQUIS`: por cada papel que le
baja el taller teclea folio, unidad, mecanico y la lista de materiales.

QUE CAMBIA RESPECTO AL EXCEL. Tres cosas que la hoja de calculo no puede hacer:

  1. Avisa cuando el papel ya se tecleo (mismo folio, misma fecha, misma
     unidad). En el libro real eso paso una vez y nadie se entero.
  2. Casa cada codigo contra el catalogo de refacciones, asi que el renglon
     queda ligado a la pieza y no solo a un texto.
  3. Deja constancia de QUIEN tecleo cada documento. En el Excel no hay forma
     de saberlo.

Lo que NO cambia: el folio lo sigue trayendo el papel, y se respeta aunque
venga repetido. Ver `requisicion_model.py`.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import models as m
from ...core.database import get_db
from ...core.security import registrar_bitacora, require_roles
from ...core.tiempo import ahora_utc
from ...schemas import RequisicionIn, RequisicionOut

router = APIRouter(prefix="/api/capturista", tags=["capturista"])
solo_cap = require_roles("capturista")
# El administrador tambien las consulta: es quien arma el presupuesto con esos
# materiales. Solo LEE; capturar es del capturista.
cap_o_admin = require_roles("capturista", "administrador")


def _nombre_usuario(db: Session, usuario_id):
    if not usuario_id:
        return None
    u = db.query(m.Usuario).filter(m.Usuario.id == usuario_id).first()
    return u.nombre_completo if u else None


def _requisicion_out(db: Session, r: m.Requisicion, con_renglones: bool = True) -> dict:
    d = {
        "id": r.id, "folio": r.folio, "fecha": r.fecha,
        "unidad": r.unidad.num_economico if r.unidad else r.unidad_texto,
        "unidad_id": r.unidad_id, "equipo_sap": r.equipo_sap,
        "centro_gestion": r.centro_gestion,
        "solicitante": (r.tecnico.nombre_completo if r.tecnico
                        else r.solicitante_nombre),
        "solicitante_num_empleado": r.solicitante_num_empleado,
        "taller": r.taller.nombre if r.taller else None,
        "estado": r.estado, "origen": r.origen,
        "capturada_por": _nombre_usuario(db, r.capturada_por_usuario_id),
        "fecha_captura": r.fecha_captura,
        "observaciones": r.observaciones,
        "total_renglones": len(r.renglones),
        "total_piezas": r.total_piezas,
        "renglones": [],
    }
    if con_renglones:
        d["renglones"] = [{
            "id": x.id, "linea": x.linea, "pieza_id": x.pieza_id,
            "codigo": x.codigo, "descripcion": x.descripcion,
            "cantidad": x.cantidad, "en_catalogo": x.pieza_id is not None,
        } for x in sorted(r.renglones, key=lambda y: y.linea)]
    return d


# ---------------------------------------------------------------- CU-CAP-01 -- #
@router.get("/resumen")
def resumen(usuario=Depends(solo_cap), db: Session = Depends(get_db)):
    """Lo tecleado, para que el puesto pueda medirse.

    `sin_casar` es el numero que importa vigilar: cada renglon ahi es un codigo
    del papel que el catalogo no reconoce, y son los que despues aparecen como
    "no hay" cuando en realidad si hay, con otro nombre.
    """
    hoy = date.today()
    mes = hoy.replace(day=1)
    total = db.query(func.count(m.Requisicion.id)).scalar() or 0
    del_mes = (db.query(func.count(m.Requisicion.id))
               .filter(m.Requisicion.fecha >= mes).scalar() or 0)
    de_hoy = (db.query(func.count(m.Requisicion.id))
              .filter(m.Requisicion.fecha == hoy).scalar() or 0)
    renglones = db.query(func.count(m.RenglonRequisicion.id)).scalar() or 0
    sin_casar = (db.query(func.count(m.RenglonRequisicion.id))
                 .filter(m.RenglonRequisicion.pieza_id.is_(None)).scalar() or 0)
    ultima = (db.query(m.Requisicion)
              .order_by(m.Requisicion.fecha.desc(), m.Requisicion.id.desc()).first())
    return {
        "requisiciones": total, "del_mes": del_mes, "de_hoy": de_hoy,
        "renglones": renglones, "sin_casar": sin_casar,
        "pct_casado": round(100 * (renglones - sin_casar) / renglones, 1) if renglones else 0,
        "ultima_fecha": ultima.fecha if ultima else None,
        "ultimo_folio": ultima.folio if ultima else None,
    }


# ---------------------------------------------------------------- CU-CAP-02 -- #
@router.get("/requisiciones", response_model=list[RequisicionOut])
def requisiciones(q: str = "", desde: date | None = None, hasta: date | None = None,
                  limite: int = 50, usuario=Depends(cap_o_admin),
                  db: Session = Depends(get_db)):
    """Las requisiciones tecleadas, de la mas reciente a la mas vieja.

    Se busca por folio, por unidad y por el nombre de quien pidio el material:
    son las tres formas en que llega la pregunta ("la de la 2154", "la J332",
    "la que pidio Ponce").
    """
    consulta = db.query(m.Requisicion)
    termino = (q or "").strip()
    if termino:
        patron = f"%{termino.lower()}%"
        consulta = consulta.filter(
            func.lower(m.Requisicion.folio).like(patron)
            | func.lower(func.coalesce(m.Requisicion.unidad_texto, "")).like(patron)
            | func.lower(func.coalesce(m.Requisicion.solicitante_nombre, "")).like(patron))
    if desde:
        consulta = consulta.filter(m.Requisicion.fecha >= desde)
    if hasta:
        consulta = consulta.filter(m.Requisicion.fecha <= hasta)
    rs = (consulta.order_by(m.Requisicion.fecha.desc(), m.Requisicion.id.desc())
          .limit(max(1, min(limite, 200))).all())
    # Sin renglones: la lista muestra cuantos hay, no cuales. Traerlos todos
    # serian cientos de filas que nadie mira hasta abrir el documento.
    return [_requisicion_out(db, r, con_renglones=False) for r in rs]


@router.get("/requisiciones/{req_id}", response_model=RequisicionOut)
def requisicion(req_id: int, usuario=Depends(cap_o_admin), db: Session = Depends(get_db)):
    r = db.query(m.Requisicion).filter(m.Requisicion.id == req_id).first()
    if not r:
        raise HTTPException(404, "Requisicion no encontrada")
    return _requisicion_out(db, r)


# ---------------------------------------------------------------- CU-CAP-03 -- #
@router.post("/requisiciones", response_model=RequisicionOut, status_code=201)
def capturar(datos: RequisicionIn, usuario=Depends(solo_cap),
             db: Session = Depends(get_db)):
    """Teclear un papel.

    El folio repetido NO es error: en el libro real hay diez folios reutilizados
    para requisiciones distintas, algunos el mismo dia. Por eso esto AVISA en
    vez de prohibir: si el folio, la fecha y la unidad coinciden con algo ya
    capturado se responde 409 con el id del documento anterior, y el capturista
    decide. Para insistir manda `forzar`, igual que el sobrecupo de la agenda:
    duplicar queda como una decision con dueno, no como un descuido.
    """
    unidad = None
    if datos.unidad_id:
        unidad = db.query(m.Unidad).filter(m.Unidad.id == datos.unidad_id).first()
        if not unidad:
            raise HTTPException(404, "La unidad no existe en el catalogo")
    texto_unidad = datos.unidad_texto or (unidad.num_economico if unidad else None)

    repetida = (db.query(m.Requisicion)
                .filter(m.Requisicion.folio == datos.folio,
                        m.Requisicion.fecha == datos.fecha,
                        m.Requisicion.unidad_texto == texto_unidad).first())
    if repetida and not datos.forzar:
        raise HTTPException(409, {
            "mensaje": f"La requisicion {datos.folio} de esa fecha y esa unidad ya "
                       "estaba capturada.",
            "requisicion_id": repetida.id,
            "sugerencia": "Abrela para compararla. Si de verdad son dos papeles "
                          "distintos con el mismo folio --pasa en el libro--, "
                          "vuelve a guardar marcando que si es otro papel.",
        })

    tecnico = None
    if datos.tecnico_id:
        tecnico = db.query(m.Tecnico).filter(m.Tecnico.id == datos.tecnico_id).first()
        if not tecnico:
            raise HTTPException(404, "El mecanico no existe en el catalogo")

    r = m.Requisicion(
        folio=datos.folio.strip(), fecha=datos.fecha,
        unidad_id=unidad.id if unidad else None, unidad_texto=texto_unidad,
        equipo_sap=datos.equipo_sap, centro_gestion=datos.centro_gestion,
        taller_id=(unidad.taller_asignado_id if unidad else None)
                  or (tecnico.taller_id if tecnico else None),
        tecnico_id=tecnico.id if tecnico else None,
        solicitante_num_empleado=datos.solicitante_num_empleado
                                 or (tecnico.num_empleado if tecnico else None),
        solicitante_nombre=datos.solicitante_nombre
                           or (tecnico.nombre_completo if tecnico else None),
        # RN-11: quien lo hizo y quien lo tecleo son dos personas distintas y
        # las dos quedan escritas.
        capturada_por_usuario_id=usuario.id, fecha_captura=ahora_utc(),
        estado="capturada", origen="app", observaciones=datos.observaciones)
    db.add(r)
    db.flush()

    for i, ren in enumerate(datos.renglones, 1):
        pieza = None
        if ren.pieza_id:
            pieza = db.query(m.Pieza).filter(m.Pieza.id == ren.pieza_id).first()
        elif ren.codigo:
            # Se intenta casar por codigo aunque la pantalla no haya elegido
            # pieza: el capturista teclea del papel, y el papel trae el codigo.
            pieza = (db.query(m.Pieza)
                     .filter((m.Pieza.codigo_externo == ren.codigo.strip())
                             | (m.Pieza.sku == ren.codigo.strip())).first())
        db.add(m.RenglonRequisicion(
            requisicion_id=r.id, linea=i, pieza_id=pieza.id if pieza else None,
            codigo=(ren.codigo or (pieza.codigo_externo if pieza else None)),
            descripcion=ren.descripcion.strip(),
            cantidad=ren.cantidad,
            costo_unitario=pieza.precio_referencia if pieza else None))

    registrar_bitacora(db, usuario.id, "requisicion_capturada", "requisicion", r.id,
                       f"folio={r.folio} unidad={texto_unidad or '-'} "
                       f"renglones={len(datos.renglones)}")
    db.commit()
    db.refresh(r)
    return _requisicion_out(db, r)


# ---------------------------------------------------------------- CU-CAP-04 -- #
@router.get("/unidades")
def unidades(q: str = "", limite: int = 10, usuario=Depends(solo_cap),
             db: Session = Depends(get_db)):
    """Buscador de unidad por numero economico.

    Busca sin guiones ni espacios porque el papel escribe "BG-354P" y el
    catalogo "BG354P". Sin esto, la mitad de las unidades del libro no casan.
    """
    termino = (q or "").strip()
    if len(termino) < 1:
        return []
    plano = "".join(c for c in termino.upper() if c.isalnum())
    patron = f"%{plano}%"
    # SQLite no tiene una funcion para quitar caracteres arbitrarios, asi que
    # se filtra amplio por LIKE y se afina en Python. Son ~700 unidades: cabe.
    candidatas = (db.query(m.Unidad)
                  .filter(m.Unidad.num_economico.isnot(None))
                  .order_by(m.Unidad.num_economico).all())
    out = []
    for u in candidatas:
        clave = "".join(c for c in u.num_economico.upper() if c.isalnum())
        if plano in clave:
            out.append({"id": u.id, "num_economico": u.num_economico,
                        "marca": u.marca, "modelo": u.modelo, "anio": u.anio,
                        "vin": u.vin, "estado": u.estado, "activo": u.activo,
                        "exacto": clave == plano})
        if len(out) >= max(1, min(limite, 50)) and any(x["exacto"] for x in out):
            break
    out.sort(key=lambda x: (not x["exacto"], len(x["num_economico"])))
    return out[: max(1, min(limite, 50))]


@router.get("/mecanicos")
def mecanicos(usuario=Depends(solo_cap), db: Session = Depends(get_db)):
    """Quien puede aparecer como solicitante del papel.

    Son TECNICO, no USUARIO: los mecanicos de Alamos no tienen cuenta (v1.1).
    Justamente por eso alguien tiene que teclear por ellos.
    """
    return [{"id": t.id, "nombre": t.nombre_completo, "num_empleado": t.num_empleado,
             "especialidad": t.especialidad, "puesto": t.puesto}
            for t in (db.query(m.Tecnico).filter(m.Tecnico.activo.is_(True))
                      .order_by(m.Tecnico.apellidos).all())]


# ---------------------------------------------------------------- CU-CAP-05 -- #
@router.get("/pendientes-de-catalogo")
def pendientes_de_catalogo(limite: int = 50, usuario=Depends(solo_cap),
                           db: Session = Depends(get_db)):
    """Los codigos tecleados que el catalogo no reconoce, del mas repetido al menos.

    Es la lista de trabajo para arreglar el catalogo: un codigo que aparece en
    ocho requisiciones y no existe en MATERIALES es un alta que falta, no un
    error de dedo.
    """
    filas = (db.query(m.RenglonRequisicion.codigo,
                      func.count(m.RenglonRequisicion.id).label("veces"),
                      func.min(m.RenglonRequisicion.descripcion).label("desc"))
             .filter(m.RenglonRequisicion.pieza_id.is_(None),
                     m.RenglonRequisicion.codigo.isnot(None))
             .group_by(m.RenglonRequisicion.codigo)
             .order_by(func.count(m.RenglonRequisicion.id).desc())
             .limit(max(1, min(limite, 200))).all())
    return [{"codigo": f.codigo, "veces": f.veces, "descripcion": f.desc} for f in filas]
