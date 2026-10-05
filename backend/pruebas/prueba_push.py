"""Pruebas de los avisos al celular (sistema/push_service.py y push_controller.py).

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_push.py     (Windows)

La ultima prueba levanta un servidor local que hace de Google/Apple: recibe el
aviso tal como saldria a internet y lo descifra con la llave del "telefono".
"""
import base64
import http.server
import json
import os
import sys
import tempfile
import threading
import traceback

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["DATABASE_URL"] = "sqlite://"
TMP = tempfile.mkdtemp(prefix="push-")
os.environ["VAPID_ARCHIVO"] = os.path.join(TMP, "vapid.json")

from fastapi import HTTPException                           # noqa: E402
from sqlalchemy import create_engine                        # noqa: E402
from sqlalchemy.orm import sessionmaker                     # noqa: E402
from sqlalchemy.pool import StaticPool                      # noqa: E402

from app import models as m                                 # noqa: E402
from app.core.database import Base                          # noqa: E402
from app.core.security import notificar                     # noqa: E402
from app.modules.sistema import push_controller as pc       # noqa: E402
from app.modules.sistema import push_service as svc         # noqa: E402

svc.EN_SEGUNDO_PLANO = False
ENVIAR_REAL = svc.enviar
CASOS = []

FCM = "https://fcm.googleapis.com/fcm/send/abc123"
APPLE = "https://web.push.apple.com/QGx1"


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


def escenario():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng, autoflush=False)()
    gente = []
    for i in (1, 2):
        u = m.Usuario(nombre=f"Persona{i}", apellidos="X", email=f"p{i}@bajagas.mx", password_hash="x")
        db.add(u)
        gente.append(u)
    db.commit()
    return db, gente


def suscribe(db, u, endpoint=FCM):
    svc.guardar_suscripcion(db, u.id, endpoint, "B" * 87, "A" * 22, "Android Chrome")
    db.commit()


class Cartero:
    """Reemplaza el envio real y anota que habria salido."""
    def __init__(self, codigo=None):
        self.codigo, self.salidos = codigo, []

    def __call__(self, sub, datos):
        self.salidos.append((sub["endpoint"], datos))
        return self.codigo

    def __enter__(self):
        svc.enviar = self
        return self

    def __exit__(self, *a):
        svc.enviar = ENVIAR_REAL


@caso("las claves VAPID se crean una vez, en su archivo, y se reusan")
def _():
    svc._claves = None
    if os.path.exists(os.environ["VAPID_ARCHIVO"]):
        os.remove(os.environ["VAPID_ARCHIVO"])
    a = svc.claves()
    assert os.path.exists(os.environ["VAPID_ARCHIVO"])
    crudo = base64.urlsafe_b64decode(a["publica"] + "==")
    assert len(crudo) == 65 and crudo[0] == 4, len(crudo)
    svc._claves = None
    assert svc.claves() == a, "genero otra clave en vez de leer el archivo"


@caso("solo acepta servicios de avisos reales por https (nada de red interna)")
def _():
    buenos = [FCM, APPLE, "https://updates.push.services.mozilla.com/wpush/v2/x",
              "https://wns2-by3p.notify.windows.com/w/?token=x"]
    malos = ["http://fcm.googleapis.com/x", "https://api:8000/api/auth/me",
             "https://169.254.169.254/latest", "https://evilgoogleapis.com/x",
             "https://fcm.googleapis.com.evil.mx/x", "https://user:pw@fcm.googleapis.com/x",
             "https://fcm.googleapis.com:8443/x", "javascript:alert(1)", "",
             # La que se colaba: urlparse ve googleapis.com, urllib3 se va a atacante.mx.
             r"https://atacante.mx\.googleapis.com/x", r"https://atacante.mx\@fcm.googleapis.com/x",
             "https://evil.mx#@fcm.googleapis.com/x", "https://fcm.googleapis.com./x",
             "https://[::1]/x", "https://fcm.googleapis.com /x", "https://android.googleapis.com/x"]
    for e in buenos:
        assert svc.endpoint_valido(e), e
    for e in malos:
        assert not svc.endpoint_valido(e), e


@caso("una cuenta dada de baja ya no recibe avisos en el celular")
def _():
    db, (a, _b) = escenario()
    suscribe(db, a)
    a.activo = False
    db.commit()
    with Cartero() as c:
        notificar(db, a.id, "Choque reportado", "HAY LESIONADOS")
        db.commit()
    assert c.salidos == [], c.salidos


@caso("el mismo celular con otra cuenta cambia de dueno, no se duplica")
def _():
    db, (a, b) = escenario()
    suscribe(db, a)
    suscribe(db, b)
    filas = db.query(m.SuscripcionPush).all()
    assert len(filas) == 1 and filas[0].usuario_id == b.id


@caso("tope de celulares por persona: se quedan los mas recientes")
def _():
    db, (a, _b) = escenario()
    for i in range(svc.MAX_POR_USUARIO + 3):
        suscribe(db, a, f"{FCM}{i}")
    filas = db.query(m.SuscripcionPush).filter_by(usuario_id=a.id).all()
    assert len(filas) == svc.MAX_POR_USUARIO
    assert f"{FCM}{svc.MAX_POR_USUARIO + 2}" in {f.endpoint for f in filas}


@caso("sin celular suscrito, notificar no encola nada")
def _():
    db, (a, _b) = escenario()
    with Cartero() as c:
        notificar(db, a.id, "Tu cita", "Manana 9:00")
        assert not db.info.get(svc._PENDIENTES)
        db.commit()
    assert c.salidos == []
    assert db.query(m.Notificacion).count() == 1


@caso("el aviso sale despues del commit, con titulo, texto y a donde abrir")
def _():
    db, (a, b) = escenario()
    suscribe(db, a)
    with Cartero() as c:
        notificar(db, a.id, "Cita confirmada", "Lunes 9:00 en Alamos", entidad_tipo="cita", entidad_id=7)
        notificar(db, b.id, "Para otra persona sin celular")
        assert c.salidos == [], "salio antes del commit"
        db.commit()
    assert len(c.salidos) == 1, c.salidos
    endpoint, datos = c.salidos[0]
    assert endpoint == FCM
    assert datos == {"titulo": "Cita confirmada", "mensaje": "Lunes 9:00 en Alamos",
                     "url": "/#/notificaciones", "tag": "cita-7"}, datos


@caso("si la operacion se deshace, no se avisa")
def _():
    db, (a, _b) = escenario()
    suscribe(db, a)
    with Cartero() as c:
        notificar(db, a.id, "Esto no paso")
        db.rollback()
        db.commit()
    assert c.salidos == []


@caso("una rafaga para la misma persona llega como un solo aviso que la resume")
def _():
    db, (a, _b) = escenario()
    suscribe(db, a)
    with Cartero() as c:
        for i in range(5):
            notificar(db, a.id, f"Aviso {i}")
        db.commit()
    assert len(c.salidos) == 1, c.salidos
    datos = c.salidos[0][1]
    assert datos["titulo"] == "Tienes 5 avisos nuevos"
    assert "Aviso 0" in datos["mensaje"] and "3 mas" in datos["mensaje"]


@caso("un mensaje largo se recorta para caber en el aviso")
def _():
    d = svc._datos("T", "x" * 1000)
    assert len(d["mensaje"]) == 240 and d["mensaje"].endswith("...")


@caso("410: el celular ya no existe y su suscripcion se borra; 500 solo cuenta el fallo")
def _():
    db, (a, b) = escenario()
    suscribe(db, a, FCM)
    suscribe(db, b, APPLE)
    with Cartero(codigo=410):
        notificar(db, a.id, "x")
        db.commit()
    assert db.query(m.SuscripcionPush).filter_by(usuario_id=a.id).count() == 0
    with Cartero(codigo=500):
        notificar(db, b.id, "x")
        db.commit()
    s = db.query(m.SuscripcionPush).filter_by(usuario_id=b.id).one()
    db.refresh(s)
    assert s.fallos == 1
    with Cartero(codigo=None):
        notificar(db, b.id, "x")
        db.commit()
    db.refresh(s)
    assert s.fallos == 0 and s.ultimo_envio is not None


@caso("el controller rechaza endpoints ajenos y solo deja quitar los propios")
def _():
    db, (a, b) = escenario()

    class Req:
        headers = {"user-agent": "Prueba"}
    try:
        pc.suscribir(pc.SuscripcionIn(endpoint="http://127.0.0.1:8000/api",
                                      keys=pc.Llaves(p256dh="B" * 87, auth="A" * 22)),
                     Req(), usuario=a, db=db)
    except HTTPException as e:
        assert e.status_code == 422
    else:
        raise AssertionError("acepto un endpoint interno")
    r = pc.suscribir(pc.SuscripcionIn(endpoint=FCM, keys=pc.Llaves(p256dh="B" * 87, auth="A" * 22)),
                     Req(), usuario=a, db=db)
    assert r == {"dispositivos": 1}
    assert pc.revisar(pc.QuitarIn(endpoint=FCM), usuario=a, db=db) == {"registrada": True}
    assert pc.revisar(pc.QuitarIn(endpoint=FCM), usuario=b, db=db) == {"registrada": False}
    assert pc.quitar(pc.QuitarIn(endpoint=FCM), usuario=b, db=db) == {"quitadas": 0}
    assert pc.quitar(pc.QuitarIn(endpoint=FCM), usuario=a, db=db) == {"quitadas": 1}
    try:
        pc.prueba(usuario=a, db=db)
    except HTTPException as e:
        assert e.status_code == 409
    else:
        raise AssertionError("mando prueba sin celular")


@caso("dos registros del mismo celular a la vez: el segundo actualiza, no truena")
def _():
    db, (a, _b) = escenario()
    suscribe(db, a)

    class Req:
        headers = {"user-agent": "Prueba"}
    real = svc.guardar_suscripcion
    llamadas = []

    def adelantado(db_, *args, **kw):
        # La primera vez se comporta como la peticion que no vio la fila que
        # la otra acababa de insertar: inserta otra con el mismo endpoint.
        llamadas.append(1)
        if len(llamadas) == 1:
            db_.add(m.SuscripcionPush(usuario_id=a.id, endpoint=FCM, p256dh="C" * 87, auth="D" * 22))
            return None
        return real(db_, *args, **kw)
    svc.guardar_suscripcion = adelantado
    try:
        r = pc.suscribir(pc.SuscripcionIn(endpoint=FCM, keys=pc.Llaves(p256dh="E" * 87, auth="F" * 22)),
                         Req(), usuario=a, db=db)
    finally:
        svc.guardar_suscripcion = real
    assert r == {"dispositivos": 1} and len(llamadas) == 2, (r, llamadas)
    assert db.query(m.SuscripcionPush).one().p256dh == "E" * 87


@caso("el boton de prueba no se puede martillar")
def _():
    db, (a, _b) = escenario()
    suscribe(db, a)
    svc._ultima_prueba.clear()
    with Cartero():
        assert pc.prueba(usuario=a, db=db)["enviados"] == 1
        try:
            pc.prueba(usuario=a, db=db)
        except HTTPException as e:
            assert e.status_code == 429
        else:
            raise AssertionError("dejo mandar dos pruebas seguidas")


@caso("no sigue redirecciones: un 307 hacia la red interna no se obedece")
def _():
    golpes = []

    class Redirige(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            golpes.append(self.path)
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/interno")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Redirige)
    hilo = threading.Thread(target=lambda: [srv.handle_request() for _ in range(2)], daemon=True)
    hilo.start()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    tel = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    sub = {"endpoint": f"http://127.0.0.1:{srv.server_port}/push",
           "p256dh": base64.urlsafe_b64encode(tel).rstrip(b"=").decode(),
           "auth": base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()}
    codigo = ENVIAR_REAL(sub, svc._datos("x", "y"))
    hilo.join(2)
    srv.server_close()
    assert codigo is not None, "conto la redireccion como entregado"
    assert golpes == ["/push"], golpes


@caso("de punta a punta: el 'telefono' descifra el aviso y la firma es del servidor")
def _():
    import http_ece
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    recibido = {}

    class Servicio(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            recibido["cuerpo"] = self.rfile.read(int(self.headers["Content-Length"]))
            recibido["cabeceras"] = dict(self.headers)
            self.send_response(201)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Servicio)
    hilo = threading.Thread(target=srv.handle_request, daemon=True)
    hilo.start()
    endpoint = f"http://127.0.0.1:{srv.server_port}/push/xyz"

    # Lo que haria el telefono al suscribirse: su par de llaves y su secreto.
    tel = ec.generate_private_key(ec.SECP256R1())
    p256dh = base64.urlsafe_b64encode(tel.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).rstrip(b"=").decode()
    secreto = os.urandom(16)
    auth = base64.urlsafe_b64encode(secreto).rstrip(b"=").decode()

    datos = svc._datos("Cita confirmada", "Lunes 9:00 en Alamos, bahia 3")
    codigo = ENVIAR_REAL({"endpoint": endpoint, "p256dh": p256dh, "auth": auth}, datos)
    hilo.join(5)
    srv.server_close()
    assert codigo is None, codigo

    claro = http_ece.decrypt(recibido["cuerpo"], private_key=tel, auth_secret=secreto,
                             version="aes128gcm")
    assert json.loads(claro.decode()) == datos

    cab = {k.lower(): v for k, v in recibido["cabeceras"].items()}
    assert cab["content-encoding"] == "aes128gcm"
    assert int(cab["ttl"]) == svc.TTL
    esquema, resto = cab["authorization"].split(" ", 1)
    partes = dict(p.strip().split("=", 1) for p in resto.split(","))
    assert esquema == "vapid" and partes["k"] == svc.claves()["publica"]
    enc, carga, firma = partes["t"].split(".")
    pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731
    reclamos = json.loads(pad(carga))
    assert reclamos["aud"] == f"http://127.0.0.1:{srv.server_port}", reclamos
    assert reclamos["sub"] == svc.CONTACTO
    crudo = pad(firma)
    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pad(svc.claves()["publica"]))
    pub.verify(encode_dss_signature(int.from_bytes(crudo[:32], "big"), int.from_bytes(crudo[32:], "big")),
               f"{enc}.{carga}".encode(), ec.ECDSA(hashes.SHA256()))


if __name__ == "__main__":
    ok = fallo = 0
    for i, (nombre, fn) in enumerate(CASOS, 1):
        try:
            fn()
            ok += 1
            print(f"  OK   {i:2d}. {nombre}")
        except Exception:
            fallo += 1
            print(f"  FALLA {i:2d}. {nombre}")
            traceback.print_exc()
    print(f"\n{ok} pasaron, {fallo} fallaron, de {len(CASOS)} casos")
    sys.exit(1 if fallo else 0)
