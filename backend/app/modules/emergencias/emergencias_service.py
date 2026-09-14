"""Averias, peritaje y arrastre.

Servicio del paquete emergencias: aqui viven las reglas de negocio y los
serializadores de este dominio. No sabe de HTTP (eso es del _controller) ni
define tablas (eso es del _model).
"""
import math
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import models as m
from ...core.tiempo import ahora_utc
from ..sistema.comun_service import nombre_chofer, nombre_usuario, siguiente_folio  # noqa: F401


def puede_solicitar_arrastre(reporte: m.ReporteAveria) -> bool:
    """RN-04: en vialidad publica, primero peritos."""
    if not reporte.en_vialidad_publica:
        return True
    return reporte.peritaje is not None and bool(reporte.peritaje.folio_peritos)


# ---------------------------------------------------------- serializadores -- #

def averia_out(db: Session, r: m.ReporteAveria) -> dict:
    return {
        "id": r.id, "folio": r.folio,
        "unidad": r.unidad.num_economico if r.unidad else "-",
        "chofer": nombre_chofer(db, r.chofer_id) or "-",
        "fecha_hora": r.fecha_hora, "latitud": r.latitud, "longitud": r.longitud,
        "descripcion_falla": r.descripcion_falla,
        "en_vialidad_publica": r.en_vialidad_publica, "estado": r.estado,
        "tiene_peritaje": r.peritaje is not None,
        "folio_peritos": r.peritaje.folio_peritos if r.peritaje else None,
        "puede_solicitar_arrastre": puede_solicitar_arrastre(r),
        "arrastre_id": r.arrastre.id if r.arrastre else None,
        "arrastre_estado": r.arrastre.estado if r.arrastre else None,
        "fotos": fotos_de(db, "reporte_averia", r.id),
        "desenlace": r.desenlace,
        "desenlace_texto": DESENLACES.get(r.desenlace) if r.desenlace else None,
        "despachado_por": nombre_usuario(db, r.despachado_por_usuario_id)
                          if r.despachado_por_usuario_id else None,
        "fecha_despacho": r.fecha_despacho,
        "nota_despacho": r.nota_despacho,
    }

def arrastre_out(db: Session, a: m.Arrastre) -> dict:
    ult = (db.query(m.UbicacionArrastre)
           .filter(m.UbicacionArrastre.arrastre_id == a.id)
           .order_by(m.UbicacionArrastre.capturado_en.desc()).first())
    return {
        "id": a.id, "folio": a.folio,
        "unidad": a.unidad.num_economico if a.unidad else "-",
        "chofer_responsable": nombre_chofer(db, a.chofer_responsable_id),
        "chofer_grua": nombre_usuario(db, a.chofer_grua_id),
        "taller_destino": a.taller_destino.nombre if a.taller_destino else None,
        "estado": a.estado, "fecha_solicitud": a.fecha_solicitud,
        "fecha_finalizacion": a.fecha_finalizacion,
        "latitud_origen": a.reporte.latitud if a.reporte else None,
        "longitud_origen": a.reporte.longitud if a.reporte else None,
        "ultima_lat": ult.latitud if ult else None,
        "ultima_lng": ult.longitud if ult else None,
        "ultima_actualizacion": ult.capturado_en if ult else None,
    }


# --------------------------------------------------------------- despacho -- #
# CU-ADM-30: el administrador de taller decide que apoyo sale. Antes esto lo
# hacia el supervisor y tenia SOLO dos salidas --mecanico o grua--, cuando en la
# operacion real son cuatro. La que faltaba es la mas frecuente: la llamada en
# la que el chofer resuelve solo.

DESENLACES = {
    "telefono": "Se resolvio por telefono",
    "llantero": "Se envio llantero",
    "mecanico": "Se envio mecanico a sitio",
    "grua":     "Se solicito arrastre",
}

# Un arrastre en cualquiera de estos estados ocupa a su chofer de grua.
ARRASTRE_OCUPA = ("solicitado", "aceptado", "en_ruta", "en_sitio")


def km_entre(lat1, lon1, lat2, lon2) -> float | None:
    """Distancia en linea recta. Devuelve None si falta cualquier coordenada.

    En linea recta y no por carretera a proposito: los seis talleres ya tienen
    latitud y longitud en la base, asi que esto no cuesta nada ni depende de un
    servicio de terceros. Para contestar "a que taller le toca" alcanza de
    sobra; si algun dia importa el minuto exacto habra que pagar rutas de
    verdad, y entonces solo cambia esta funcion.
    """
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def _unidades_en_patio(db: Session) -> set:
    """Ids de unidad que ahora mismo estan dentro de un taller."""
    return {x[0] for x in db.query(m.MovimientoTaller.unidad_id)
            .filter(m.MovimientoTaller.sigue_adentro.is_(True)).all() if x[0]}


def gruas_disponibles(db: Session) -> list:
    """Quien puede salir a arrastrar, DEDUCIDO de lo que ya paso.

    No hay casilla de "estoy disponible" y es deliberado: una casilla que se
    teclea a mano siempre acaba mintiendo --la columna Tecnico.disponible esta
    en true para los 42 tecnicos porque nadie la ha tocado nunca--. Aqui la
    respuesta sale de hechos registrados: un arrastre abierto y el patio del
    taller. Eso no se puede olvidar de actualizar.

    Se devuelven TODOS, ocupados incluidos, con el motivo. Una lista que
    esconde a los ocupados obliga a Pablo a preguntar por radio quien falta.
    """
    en_patio = _unidades_en_patio(db)
    out = []
    for cg in db.query(m.ChoferGrua).all():
        u = db.query(m.Usuario).filter(m.Usuario.id == cg.usuario_id).first()
        if not u or not u.activo:
            continue
        abierto = (db.query(m.Arrastre)
                   .filter(m.Arrastre.chofer_grua_id == cg.usuario_id,
                           m.Arrastre.estado.in_(ARRASTRE_OCUPA)).first())
        grua = (db.query(m.Unidad).filter(m.Unidad.id == cg.unidad_grua_id).first()
                if cg.unidad_grua_id else None)

        motivo = None
        if not cg.en_servicio:
            motivo = "No esta en servicio"
        elif abierto:
            motivo = f"Ocupado en el arrastre {abierto.folio}"
        elif grua is not None and grua.id in en_patio:
            motivo = f"Su grua ({grua.num_economico}) esta en el taller"

        out.append({
            "usuario_id": cg.usuario_id,
            "nombre": nombre_usuario(db, cg.usuario_id),
            "telefono": u.telefono,
            "grua": grua.num_economico if grua else None,
            # Se dice explicitamente cuando no se sabe que grua maneja: sin ese
            # dato no se puede cruzar contra el patio, y callarlo haria pasar
            # por "libre" a alguien cuya grua podria estar desarmada.
            "grua_desconocida": cg.unidad_grua_id is None,
            "libre": motivo is None,
            "motivo": motivo,
        })
    return sorted(out, key=lambda x: (not x["libre"], x["nombre"] or ""))


def apoyo_cercano(db: Session, lat: float | None, lon: float | None) -> list:
    """Tecnicos que pueden salir a sitio, del mas cerca al mas lejos.

    Solo los AUTONOMO. Los 34 tecnicos de Alamos son ASISTIDO: no usan la
    aplicacion y no salen a carretera, asi que ofrecerlos como opcion seria
    ofrecer a alguien que no va a ir. La distancia es de su TALLER al punto de
    la averia, porque es de donde salen.
    """
    en_patio = _unidades_en_patio(db)
    out = []
    q = (db.query(m.Tecnico)
         .filter(m.Tecnico.activo.is_(True),
                 m.Tecnico.especialidad.in_(("mecanico", "llantero", "electricista",
                                             "carrocero"))))
    for t in q.all():
        taller = t.taller
        km = km_entre(lat, lon, taller.latitud, taller.longitud) if taller else None
        vehiculo = (db.query(m.Unidad).filter(m.Unidad.id == t.unidad_servicio_id).first()
                    if t.unidad_servicio_id else None)
        out.append({
            "id": t.id,
            "nombre": f"{t.nombre} {t.apellidos}".strip(),
            "especialidad": t.especialidad,
            "modalidad": t.modalidad,
            "taller": taller.nombre if taller else None,
            "telefono": t.telefono,
            "km": km,
            "sale_a_carretera": t.modalidad == "AUTONOMO",
            "vehiculo_en_taller": bool(vehiculo and vehiculo.id in en_patio),
        })
    # Primero los que si salen, luego por cercania. Los que no tienen
    # coordenadas van al final en vez de colarse como si estuvieran a 0 km.
    return sorted(out, key=lambda x: (not x["sale_a_carretera"],
                                      x["km"] if x["km"] is not None else 9e9,
                                      x["nombre"]))


def fotos_de(db: Session, entidad_tipo: str, entidad_id: int) -> list:
    """Las fotos de una entidad, listas para pintar.

    Vive aqui y no en el controller porque la misma lista la necesitan el
    chofer que subio la foto y el administrador que decide el apoyo viendola.
    """
    from .evidencia_controller import evidencia_out
    evs = (db.query(m.Evidencia)
           .filter(m.Evidencia.entidad_tipo == entidad_tipo,
                   m.Evidencia.entidad_id == entidad_id,
                   m.Evidencia.url_archivo != "")
           .order_by(m.Evidencia.fecha).all())
    return [evidencia_out(db, e) for e in evs]
