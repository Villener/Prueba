"""Freno a los intentos de login por fuerza bruta.

Hasta ahora `/api/auth/login` aceptaba intentos sin limite: en la red de la casa
daba lo mismo, pero detras de una URL publica son 335 cuentas con correo
predecible (e<num_empleado>@bajagas.mx) contra las que se puede probar
contrasenas toda la noche sin que nadie se entere.

Se cuenta en memoria del proceso, no en la base. Es a proposito:

  - Un fallo de login no es un dato de negocio; no tiene por que ensuciar la
    base ni sobrevivir a un reinicio.
  - Escribir en disco en cada intento fallido convierte el ataque en una forma
    barata de llenar el disco.

La contrapartida honesta: con varios procesos de uvicorn cada uno lleva su
cuenta, asi que el limite real se multiplica por el numero de procesos. Con un
solo proceso -- que es como corre el contenedor -- es exacto. Si algun dia hace
falta escalar a varios, esto se muda a Redis y no antes.
"""
import threading
import time

# Por CORREO: protege una cuenta concreta de que le adivinen la contrasena.
MAX_POR_CORREO = 8
# Por IP: protege al conjunto de que alguien barra muchas cuentas desde un lado.
MAX_POR_IP = 25
# Ventana y castigo, en segundos.
VENTANA = 15 * 60

_fallos: dict[str, list[float]] = {}
_candado = threading.Lock()


def _vigentes(clave: str, ahora: float) -> list[float]:
    """Los fallos de esa clave que todavia caen dentro de la ventana."""
    recientes = [t for t in _fallos.get(clave, ()) if ahora - t < VENTANA]
    if recientes:
        _fallos[clave] = recientes
    else:
        _fallos.pop(clave, None)
    return recientes


def ip_del_cliente(request) -> str:
    """La IP real del que llama, no la del ultimo salto.

    La peticion llega encadenada: navegador -> Cloudflare -> cloudflared ->
    nginx -> uvicorn. Sin esto, `request.client.host` seria siempre la IP del
    contenedor de nginx y el limite por IP no distinguiria a nadie: el primer
    atacante dejaria fuera a todo el mundo.

    `CF-Connecting-IP` la pone Cloudflare y es la de fiar cuando se entra por el
    tunel. `X-Forwarded-For` es una cadena y su primer elemento es el cliente
    original, pero cualquiera que alcance a nginx directo puede inventarselo:
    sirve de respaldo, no de fuente confiable.
    """
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def segundos_de_espera(correo: str, ip: str) -> int:
    """0 si puede intentar. Si no, cuantos segundos le faltan para reintentar."""
    ahora = time.time()
    with _candado:
        for clave, tope in ((f"correo:{(correo or '').lower()}", MAX_POR_CORREO),
                            (f"ip:{ip}", MAX_POR_IP)):
            recientes = _vigentes(clave, ahora)
            if len(recientes) >= tope:
                # El bloqueo se levanta cuando el fallo mas viejo sale de la
                # ventana, no un rato fijo: asi el que fallo tres veces hace
                # rato no espera lo mismo que el que acaba de fallar ocho.
                return max(1, int(VENTANA - (ahora - min(recientes))))
    return 0


def registrar_fallo(correo: str, ip: str) -> None:
    ahora = time.time()
    with _candado:
        for clave in (f"correo:{(correo or '').lower()}", f"ip:{ip}"):
            _vigentes(clave, ahora)
            _fallos.setdefault(clave, []).append(ahora)


def limpiar(correo: str, ip: str) -> None:
    """Un login bueno borra el historial de esa cuenta y esa IP.

    Sin esto, quien se equivoca de contrasena siete veces y a la octava acierta
    se quedaria a un fallo de quedar bloqueado el resto de la ventana.
    """
    with _candado:
        _fallos.pop(f"correo:{(correo or '').lower()}", None)
        _fallos.pop(f"ip:{ip}", None)
