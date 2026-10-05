"""Avisos al celular (Web Push), el mismo aviso de notificar() pero en el telefono.

Como llega un aviso:
  1. notificar() guarda la Notificacion (la campana de la app) y, si esa persona
     tiene celulares suscritos, deja el aviso ENCOLADO en la sesion de la base.
  2. Cuando la transaccion se confirma (after_commit) se mandan en un hilo
     aparte. Antes no: si la operacion se deshace, el aviso no debe salir, y
     esperar a Google o a Apple dentro de la peticion haria lenta la pantalla.
  3. El servicio del fabricante (Google, Apple, Mozilla, Microsoft) lo entrega
     al telefono aunque la app este cerrada; ahi lo pinta frontend/public/sw.js.

Las claves VAPID identifican a ESTE servidor ante esos servicios. Se generan
solas la primera vez y viven junto a la base (en produccion /datos/vapid.json,
dentro del volumen): no van en el .env ni en el repositorio, que es publico.
Si se pierden, los celulares ya suscritos dejan de recibir hasta que la app
vuelva a abrirse en ellos, que se suscribe de nuevo con la clave nueva.
"""
import base64
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from sqlalchemy import event
from sqlalchemy.orm import Session

from ...core.tiempo import ahora_utc
from .notificacion_model import SuscripcionPush

log = logging.getLogger("bajagas")

# Quien opera el servidor, para los servicios de avisos. Apple rechaza el envio
# si no es un mailto: o https: bien formado.
CONTACTO = os.getenv("PUSH_CONTACTO", "mailto:taller@bajagas.mx")
# Cuanto guarda el servicio un aviso si el telefono esta apagado o sin senal.
TTL = 2 * 24 * 3600
# Con mas de estos avisos para la misma persona en una sola operacion (la carga
# nocturna, por ejemplo) se manda UNO que los resume, no una rafaga.
TOPE_RAFAGA = 3
# Fallos seguidos antes de dar por muerta una suscripcion que no contesta 404/410.
TOPE_FALLOS = 10
MAX_POR_USUARIO = 10
URL_AVISOS = "/#/notificaciones"

# A donde puede mandar el servidor. El endpoint lo escribe el navegador del
# usuario, o sea que cualquiera con cuenta podria registrar uno que apunte a la
# red interna (http://api:8000, 169.254.169.254...) y usar al servidor de
# mensajero. Solo se aceptan los servicios de avisos reales, por nombre exacto.
# Microsoft reparte entre muchos servidores (wns2-bn3p, wns2-by3p...): a ese se
# le acepta cualquier subdominio.
HOSTS_PERMITIDOS = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
SUFIJOS_PERMITIDOS = (".notify.windows.com",)
_HOST_LIMPIO = re.compile(r"[a-z0-9.-]+")

# Las pruebas lo apagan para mandar en el mismo hilo y poder revisar el resultado.
EN_SEGUNDO_PLANO = True
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="push")
_PENDIENTES = "push_pendientes"


# --------------------------------------------------------------------------- #
# Claves VAPID
# --------------------------------------------------------------------------- #
def archivo_claves() -> str:
    if os.getenv("VAPID_ARCHIVO"):
        return os.environ["VAPID_ARCHIVO"]
    from ...core.database import BASE_DIR, DATABASE_URL
    ruta = DATABASE_URL.split("sqlite:///", 1)[1] if DATABASE_URL.startswith("sqlite:///") else ""
    carpeta = os.path.dirname(ruta) if ruta and ruta != ":memory:" else BASE_DIR
    return os.path.join(carpeta or BASE_DIR, "vapid.json")


_claves = None
_candado = threading.Lock()


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def claves() -> dict:
    """{"privada": PEM, "publica": base64url del punto sin comprimir (65 bytes)}."""
    global _claves
    with _candado:
        if _claves:
            return _claves
        ruta = archivo_claves()
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                _claves = json.load(f)
            return _claves
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        llave = ec.generate_private_key(ec.SECP256R1())
        privada = llave.private_bytes(serialization.Encoding.PEM,
                                      serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()).decode()
        publica = _b64url(llave.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        # Se crea ya con permisos de solo-dueno: la privada firma como el servidor.
        try:
            fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # La API y la carga nocturna son procesos distintos: si el otro la
            # acaba de crear, se usa la suya. Dos claves = suscripciones rotas.
            with open(ruta, encoding="utf-8") as f:
                _claves = json.load(f)
            return _claves
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"privada": privada, "publica": publica}, f)
        log.info("push: claves VAPID nuevas en %s", ruta)
        _claves = {"privada": privada, "publica": publica}
        return _claves


def _vapid():
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid
    return Vapid(serialization.load_pem_private_key(claves()["privada"].encode(), password=None))


# --------------------------------------------------------------------------- #
# Suscripciones
# --------------------------------------------------------------------------- #
def endpoint_valido(endpoint: str) -> bool:
    """Se revisa con DOS lectores de URL y tienen que coincidir: el de Python
    (urlparse) y el que de verdad usa el envio (urllib3, debajo de requests).
    Con uno solo, "https://atacante.mx\\.googleapis.com/x" pasaba: urlparse ve
    un host que termina en googleapis.com y urllib3 se conecta a atacante.mx.
    Por eso tambien fuera la diagonal invertida y cualquier espacio."""
    if not endpoint or any(c in endpoint for c in "\\ \t\r\n"):
        return False
    try:
        from urllib3.util import parse_url
        a, b = urlparse(endpoint), parse_url(endpoint)
    except Exception:
        return False
    host = (a.hostname or "").lower()
    if host != (b.host or "").lower() or not _HOST_LIMPIO.fullmatch(host):
        return False
    if a.scheme != "https" or b.scheme != "https" or a.username or a.password or b.auth:
        return False
    if a.port not in (None, 443) or b.port not in (None, 443):
        return False
    return host in HOSTS_PERMITIDOS or host.endswith(SUFIJOS_PERMITIDOS)


def guardar_suscripcion(db: Session, usuario_id: int, endpoint: str, p256dh: str, auth: str,
                        dispositivo: str = "") -> SuscripcionPush:
    """Alta o cambio de dueno. No hace commit."""
    s = db.query(SuscripcionPush).filter_by(endpoint=endpoint).first()
    if s is None:
        s = SuscripcionPush(endpoint=endpoint)
        db.add(s)
    s.usuario_id = usuario_id
    s.p256dh, s.auth = p256dh, auth
    s.dispositivo = (dispositivo or "")[:200]
    s.fallos = 0
    db.flush()
    # Tope por persona: los navegadores reinstalados dejan suscripciones viejas
    # que ya nadie va a borrar. Se quedan las mas recientes.
    sobrantes = (db.query(SuscripcionPush).filter_by(usuario_id=usuario_id)
                 .order_by(SuscripcionPush.id.desc()).offset(MAX_POR_USUARIO).all())
    for v in sobrantes:
        db.delete(v)
    return s


# --------------------------------------------------------------------------- #
# Envio
# --------------------------------------------------------------------------- #
def _datos(titulo, mensaje, entidad_tipo=None, entidad_id=None, url=URL_AVISOS):
    mensaje = (mensaje or "").strip()
    if len(mensaje) > 240:
        mensaje = mensaje[:237].rstrip() + "..."
    d = {"titulo": (titulo or "Baja Gas")[:120], "mensaje": mensaje, "url": url}
    if entidad_tipo and entidad_id:
        # Mismo asunto, mismo aviso: el telefono reemplaza el anterior en vez
        # de apilar cinco sobre la misma cita.
        d["tag"] = f"{entidad_tipo}-{entidad_id}"
    return d


def enviar(sub: dict, datos: dict):
    """Manda UN aviso a UNA suscripcion. Devuelve None si salio, o el codigo
    HTTP del rechazo (0 si ni siquiera hubo respuesta)."""
    import requests
    from pywebpush import WebPushException, webpush
    # Sin redirecciones: un servicio de avisos de verdad nunca redirige, y
    # seguirlas dejaria al servidor pegarle a donde la respuesta diga.
    sesion = requests.Session()
    sesion.max_redirects = 0
    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"],
                               "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
            data=json.dumps(datos, ensure_ascii=False),
            vapid_private_key=_vapid(),
            # Diccionario NUEVO cada vez: webpush le escribe `aud` con el host
            # del endpoint, y reusarlo mandaria a Apple un permiso hecho para Google.
            vapid_claims={"sub": CONTACTO},
            ttl=TTL, timeout=10,
            requests_session=sesion,
        )
        return None
    except WebPushException as e:
        codigo = getattr(e.response, "status_code", 0) or 0
        log.warning("push: rechazo %s de %s", codigo, urlparse(sub["endpoint"]).hostname)
        return codigo
    except Exception as e:  # sin red, DNS, timeout, redireccion
        log.warning("push: no salio hacia %s: %s", urlparse(sub["endpoint"]).hostname, e)
        return 0
    finally:
        sesion.close()


def _registrar(db: Session, resultados):
    """Anota el resultado de cada envio y borra las suscripciones muertas."""
    ahora = ahora_utc()
    for sub_id, codigo in resultados:
        s = db.get(SuscripcionPush, sub_id)
        if s is None:
            continue
        if codigo is None:
            s.ultimo_envio, s.fallos = ahora, 0
        elif codigo in (404, 410):
            # El navegador se desinstalo o el usuario quito el permiso.
            db.delete(s)
        else:
            s.fallos = (s.fallos or 0) + 1
            if s.fallos >= TOPE_FALLOS:
                db.delete(s)


def enviar_a_usuario(db: Session, usuario_id: int, datos: dict) -> dict:
    """Envio inmediato, en el mismo hilo (el boton de prueba). Hace commit."""
    subs = db.query(SuscripcionPush).filter_by(usuario_id=usuario_id).all()
    resultados = [(s.id, enviar(_como_dict(s), datos)) for s in subs]
    _registrar(db, resultados)
    db.commit()
    return {"dispositivos": len(subs),
            "enviados": sum(1 for _, c in resultados if c is None),
            "fallidos": sum(1 for _, c in resultados if c is not None)}


# El boton de prueba hace una peticion a internet por celular: con un tope por
# persona no se puede usar para martillar al servidor ni a los servicios.
ESPERA_PRUEBA_S = 15
_ultima_prueba = {}


def prueba_permitida(usuario_id: int) -> bool:
    ahora = time.monotonic()
    with _candado:
        if ahora - _ultima_prueba.get(usuario_id, -ESPERA_PRUEBA_S) < ESPERA_PRUEBA_S:
            return False
        _ultima_prueba[usuario_id] = ahora
        return True


def _como_dict(s: SuscripcionPush) -> dict:
    return {"id": s.id, "endpoint": s.endpoint, "p256dh": s.p256dh, "auth": s.auth}


def encolar(db: Session, usuario_id: int, titulo: str, mensaje: str = "",
            entidad_tipo: str = None, entidad_id: int = None):
    """Lo llama notificar(). Nunca rompe la operacion que avisa: si algo falla
    aqui, el aviso se queda solo en la campana de la app."""
    try:
        from ...models import Usuario
        # Solo cuentas activas. Dar de baja a alguien es ponerle activo=False:
        # deja de poder entrar, y sus avisos tampoco le pueden seguir llegando
        # al celular (avisos de choques, incumplimientos, presupuestos...).
        subs = (db.query(SuscripcionPush)
                .join(Usuario, Usuario.id == SuscripcionPush.usuario_id)
                .filter(SuscripcionPush.usuario_id == usuario_id, Usuario.activo.is_(True))
                .all())
        if not subs:
            return
        db.info.setdefault(_PENDIENTES, []).append({
            "usuario_id": usuario_id,
            "subs": [_como_dict(s) for s in subs],
            "datos": _datos(titulo, mensaje, entidad_tipo, entidad_id),
        })
    except Exception:
        log.exception("push: no se pudo encolar el aviso de usuario %s", usuario_id)


def _agrupar(lote: list) -> list:
    """Un aviso por persona cuando le llegan demasiados de golpe."""
    por_usuario = {}
    for item in lote:
        por_usuario.setdefault(item["usuario_id"], []).append(item)
    salida = []
    for items in por_usuario.values():
        if len(items) <= TOPE_RAFAGA:
            salida.extend(items)
            continue
        titulos = [i["datos"]["titulo"] for i in items]
        resumen = "; ".join(titulos[:2]) + f" y {len(titulos) - 2} mas."
        salida.append({"usuario_id": items[0]["usuario_id"], "subs": items[-1]["subs"],
                       "datos": _datos(f"Tienes {len(items)} avisos nuevos", resumen)})
    return salida


def _despachar(bind, lote: list):
    try:
        resultados = []
        for item in _agrupar(lote):
            for sub in item["subs"]:
                resultados.append((sub["id"], enviar(sub, item["datos"])))
        with Session(bind=bind) as db:
            _registrar(db, resultados)
            db.commit()
    except Exception:
        log.exception("push: fallo el despacho de %s avisos", len(lote))


@event.listens_for(Session, "after_commit")
def _al_confirmar(session):
    lote = session.info.pop(_PENDIENTES, None)
    if not lote:
        return
    bind = session.get_bind()
    if EN_SEGUNDO_PLANO:
        _pool.submit(_despachar, bind, lote)
    else:
        _despachar(bind, lote)


@event.listens_for(Session, "after_rollback")
def _al_deshacer(session):
    # Lo que se deshizo no se avisa.
    session.info.pop(_PENDIENTES, None)
