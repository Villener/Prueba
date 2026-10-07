"""Pruebas de la firma dibujada (bitacora/asientos_reporte.validar_trazo).

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_firma.py     (Windows)
"""
import hashlib
import os
import sys
import traceback

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import HTTPException                           # noqa: E402
from pydantic import ValidationError                        # noqa: E402

from app import schemas as sc                               # noqa: E402
from app.modules.bitacora.asientos_reporte import validar_trazo  # noqa: E402

CASOS = []
ZIGZAG = "M 20 150 " + " ".join(f"L {40 + 40 * k} {60 if k % 2 else 150}" for k in range(13))


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


def rechaza(trazo, texto):
    try:
        validar_trazo(trazo)
    except HTTPException as e:
        assert e.status_code == 422 and texto in e.detail, e.detail
        return
    raise AssertionError(f"acepto {trazo[:40]!r}")


@caso("una firma completa pasa, limpia de espacios y con su huella")
def _():
    t, h = validar_trazo("  " + ZIGZAG.replace(" ", "   ") + "\n")
    assert t == ZIGZAG
    assert h == hashlib.sha256(ZIGZAG.encode()).hexdigest()


@caso("un toque o una rayita no son firma")
def _():
    rechaza("M 100 100", "muy corta")
    rechaza("M 100 100 L 101 101", "muy corta")
    rechaza("M 10 10 L 60 10", "muy corta")


@caso("solo se aceptan M y L dentro del lienzo: nada de otros comandos SVG")
def _():
    rechaza('M 0 0 L 10 10"/><script>alert(1)</script>', "No se pudo leer")
    rechaza("M 0 0 C 10 10 20 20 30 30 " + ZIGZAG, "No se pudo leer")
    rechaza("M 0 0 L 9999 10 " + ZIGZAG, "No se pudo leer")
    rechaza("M 0 L 10 10 " + ZIGZAG, "No se pudo leer")
    rechaza("", "No se pudo leer")


@caso("el formulario ya no acepta una firma sin dibujo")
def _():
    try:
        sc.FirmaReporteIn(rol_firma="recibe_salida", nombre="Fulano Tal")
    except ValidationError:
        return
    raise AssertionError("acepto la firma sin trazo")


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
