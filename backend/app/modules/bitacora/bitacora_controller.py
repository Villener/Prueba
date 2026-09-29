"""Consulta del libro de bitacora de cada unidad (PROY-NOM-030-ASEA-2026, 7.1.10).

QUIEN LO VE, Y POR QUE ESTOS. El inciso b) pide que el libro este "disponible
en un lugar de facil acceso tanto para el Operador de la Unidad de Distribucion
como para el personal responsable del mantenimiento":
  - el Operador es el chofer: ve el libro de la unidad que trae o de la que es
    titular, y solo esa;
  - el personal responsable del mantenimiento es el administrador y el jefe de
    mantenimiento de cada taller, y los mecanicos autonomos de las plantas
    satelite. Los mecanicos de Alamos no tienen cuenta a proposito (RI-A-18):
    consultan el libro por medio de su administrador o impreso;
  - el supervisor y el gerente responden por la flota y lo consultan igual.
El inciso d) 5 pide que este disponible "en cualquier momento en un equipo de
computo o dispositivos moviles": es esta misma aplicacion web.

SOLO LECTURA. Aqui no se escribe ningun asiento. Los asientos los deja quien
cambia el formato (modules/bitacora/asientos_reporte.py); lo unico que se
escribe aqui son los datos de identificacion de 7.1.10 c), y esos van a la
bitacora de auditoria con su valor anterior.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ... import models as m
from ...core.database import get_db
from ...core.security import registrar_bitacora, require_roles
from . import asientos_reporte as bit
from . import bitacora_service as bs

router = APIRouter(prefix="/api/bitacora", tags=["bitacora NOM-030"])

lectores = require_roles("administrador", "gerente", "supervisor", "mecanico", "chofer")
# Quien puede fijar los datos del Regulado y de la unidad. No el supervisor ni
# el chofer: el permiso y la razon social son datos legales de la empresa.
editores = require_roles("administrador", "gerente")


def _unidades_del_chofer(db: Session, usuario_id: int) -> list:
    """Las unidades cuyo libro puede ver un chofer: la que trae y de la que es titular.

    No se usa `_mi_unidad` del modulo del chofer: esa devuelve SOLO la que trae,
    y el titular que presto su unidad sigue siendo su Operador frente a la
    norma. Con aquella, el titular se quedaba sin libro.
    """
    return (db.query(m.Unidad)
            .filter((m.Unidad.poseedor_chofer_id == usuario_id)
                    | (m.Unidad.titular_chofer_id == usuario_id))
            .order_by(m.Unidad.num_economico).all())


def _puede_ver(db: Session, usuario, unidad: m.Unidad) -> bool:
    roles = set(usuario.lista_roles)
    if roles & {"administrador", "gerente", "supervisor", "mecanico"}:
        return True
    return usuario.id in (unidad.poseedor_chofer_id, unidad.titular_chofer_id)


def libro(db: Session, unidad: m.Unidad) -> dict:
    """El libro completo de una unidad, listo para la pantalla o la impresion."""
    asientos = bs.asientos_de_unidad(db, unidad.id)
    ident = bit.identificacion(db, unidad)
    integridad = bs.verificar_libro(db, unidad.id, asientos)
    desde = bs.parametro(db, bs.CLAVE_LIBRO_DESDE) or None
    faltan = []
    if ident["es_unidad_distribucion"]:
        if not ident["permiso"]:
            faltan.append("número de permiso")
        if not ident["razon_social"]:
            faltan.append("razón social")
        if not ident["operadores"]:
            faltan.append("operadores")
        if not ident["personal_auxiliar"]:
            faltan.append("personal auxiliar")
    ultimo = asientos[-1] if asientos else None
    return {
        "cabecera": ident,
        # 7.1.10 c) solo obliga a las Unidades de Distribucion (5.1.14). A una
        # utilitaria no se le pinta en rojo lo que la norma no le pide.
        "faltan_datos_nom030": faltan,
        "libro_desde": desde,
        "integridad": integridad,
        # El ancla del libro impreso: con el numero y el hash del ultimo asiento
        # en el pie, un libro entregado antes demuestra si despues se quito algo.
        "ultimo": {"numero": ultimo.numero, "hash": ultimo.hash,
                   "registrado_en": ultimo.registrado_en} if ultimo else None,
        "asientos": [bs.asiento_out(a) for a in asientos],
    }


# ------------------------------------------------------------------ leer ---- #
@router.get("/unidad/{unidad_id}")
def libro_de_unidad(unidad_id: int, usuario=Depends(lectores),
                    db: Session = Depends(get_db)):
    u = db.get(m.Unidad, unidad_id)
    if not u:
        raise HTTPException(404, "Unidad no encontrada")
    if not _puede_ver(db, usuario, u):
        raise HTTPException(403, "Solo puedes consultar el libro de la unidad que traes "
                                 "o de la que eres titular.")
    return libro(db, u)


@router.get("/mis-unidades")
def mis_unidades(usuario=Depends(require_roles("chofer")), db: Session = Depends(get_db)):
    """Las unidades del chofer con libro que consultar (la que trae y la suya)."""
    return [{"id": u.id, "num_economico": u.num_economico,
             "la_traigo": u.poseedor_chofer_id == usuario.id
                          or (u.poseedor_chofer_id is None and u.titular_chofer_id == usuario.id),
             "soy_titular": u.titular_chofer_id == usuario.id}
            for u in _unidades_del_chofer(db, usuario.id)]


@router.get("/ayudantes")
def ayudantes(usuario=Depends(editores), db: Session = Depends(get_db)):
    """Nombres del personal con perfil 'ayudante' (5.1.11 Personal Auxiliar).

    Son SUGERENCIAS para el campo de personal auxiliar, no una lista cerrada:
    el ayudante puede ser un eventual que no esta en los Excel de Logistica.
    """
    filas = (db.query(m.Usuario)
             .join(m.Chofer, m.Chofer.usuario_id == m.Usuario.id)
             .filter(m.Chofer.perfil == "ayudante", m.Usuario.activo.is_(True))
             .order_by(m.Usuario.nombre, m.Usuario.apellidos).all())
    return [u.nombre_completo for u in filas]


# ------------------------------------------------ identificacion 7.1.10 c) -- #
class ReguladoIn(BaseModel):
    razon_social: str = Field(min_length=3, max_length=200)
    permiso: str = Field(default="", max_length=80)


class IdentificacionUnidadIn(BaseModel):
    """Lo que se captura por unidad. Vacio = usar el dato general."""
    personal_auxiliar: str | None = Field(default=None, max_length=200)
    permiso_hidrocarburos: str | None = Field(default=None, max_length=80)
    razon_social_regulado: str | None = Field(default=None, max_length=200)


def _guardar_parametro(db: Session, clave: str, valor: str, descripcion: str):
    c = db.query(m.Configuracion).filter(m.Configuracion.clave == clave).first()
    if c is None:
        c = m.Configuracion(clave=clave, valor=valor, descripcion=descripcion,
                            tipo_dato="texto")
        db.add(c)
    else:
        c.valor = valor


@router.get("/regulado")
def regulado(usuario=Depends(lectores), db: Session = Depends(get_db)):
    return {"razon_social": bs.parametro(db, bs.CLAVE_RAZON_SOCIAL),
            "permiso": bs.parametro(db, bs.CLAVE_PERMISO)}


@router.post("/regulado")
def fijar_regulado(datos: ReguladoIn, usuario=Depends(editores),
                   db: Session = Depends(get_db)):
    """El dato general. Cambiarlo no reescribe ningun asiento: cada apertura ya
    guardo en su foto el permiso y la razon social que tenia ESE dia."""
    previo = {"razon_social": bs.parametro(db, bs.CLAVE_RAZON_SOCIAL),
              "permiso": bs.parametro(db, bs.CLAVE_PERMISO)}
    nuevo = {"razon_social": datos.razon_social.strip(), "permiso": datos.permiso.strip()}
    antes = f"razon_social={previo['razon_social']!r} permiso={previo['permiso']!r}"
    _guardar_parametro(db, bs.CLAVE_RAZON_SOCIAL, nuevo["razon_social"],
                       "NOM-030 7.1.10 c): denominacion o razon social del Regulado")
    _guardar_parametro(db, bs.CLAVE_PERMISO, nuevo["permiso"],
                       "NOM-030 7.1.10 c): numero de permiso del Sector Hidrocarburos")
    # El cambio se asienta en cada libro que ya existe y que usa el dato
    # general (las unidades con permiso o razon social propios no cambian). Un
    # libro que todavia no existe no tiene pasado que aclarar: su primera
    # apertura ya guardara el dato nuevo.
    if previo != nuevo:
        con_libro = {uid for (uid,) in db.query(m.AsientoBitacora.unidad_id).distinct()}
        for u in db.query(m.Unidad).filter(m.Unidad.id.in_(con_libro)).all() if con_libro else []:
            antes_u = {k: v for k, v in previo.items()
                       if not (k == "permiso" and (u.permiso_hidrocarburos or "").strip())
                       and not (k == "razon_social" and (u.razon_social_regulado or "").strip())}
            despues_u = {k: nuevo[k] for k in antes_u}
            bit.asentar_identificacion(db, u, antes_u, despues_u, usuario.id, "datos generales")
    registrar_bitacora(db, usuario.id, "nom030_regulado", "configuracion", None,
                       datos_antes=antes,
                       datos_despues=f"razon_social={datos.razon_social.strip()!r} "
                                     f"permiso={datos.permiso.strip()!r}")
    db.commit()
    return regulado(usuario, db)


@router.post("/unidad/{unidad_id}/identificacion")
def fijar_identificacion(unidad_id: int, datos: IdentificacionUnidadIn,
                         usuario=Depends(editores), db: Session = Depends(get_db)):
    u = db.get(m.Unidad, unidad_id)
    if not u:
        raise HTTPException(404, "Unidad no encontrada")
    campos = ("personal_auxiliar", "permiso_hidrocarburos", "razon_social_regulado")
    bs.bloquear_unidad(db, u.id)
    antes = {c: getattr(u, c) for c in campos}
    for c in campos:
        v = getattr(datos, c)
        setattr(u, c, (v or "").strip() or None)
    despues = {c: getattr(u, c) for c in campos}
    if antes != despues:
        registrar_bitacora(db, usuario.id, "nom030_identificacion_unidad", "unidad", u.id,
                           datos_antes=repr(antes), datos_despues=repr(despues))
        # En el libro, no solo en la auditoria: la cabecera dice los datos de
        # hoy, y este asiento dice desde cuando y que decia antes (7.1.10 a).
        db.flush()
        bit.asentar_identificacion(db, u, antes, despues, usuario.id, "de esta unidad")
    db.commit()
    return libro(db, u)
