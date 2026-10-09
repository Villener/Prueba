"""Pruebas de la carga de Excel desde la pantalla (modules/sistema/cargas_*).

El motor que lee los Excel (importadores/sincronizar.py) necesita los archivos
reales de las areas, que no van en el repositorio. Aqui se cambia por uno falso
que anota con que carpeta lo llamaron y contesta un informe armado a mano: lo que
se prueba es lo NUEVO -- quien puede subir que, que el archivo ocupe el lugar
correcto, que la base real no se toque al revisar, que un error regrese el
archivo anterior, y las cuentas por area --. Los importadores tienen sus propias
pruebas de idempotencia.

    cd backend
    .venv/Scripts/python.exe pruebas/prueba_cargas.py     (Windows)
"""
import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import time
import traceback

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
_BASE = os.path.join(tempfile.mkdtemp(prefix="cargas-prueba-"), "base.db")
os.environ["DATABASE_URL"] = "sqlite:///" + _BASE.replace("\\", "/")

from fastapi import HTTPException                           # noqa: E402
from openpyxl import Workbook                               # noqa: E402

from app import cuentas_de_area                             # noqa: E402
from app import models as m                                 # noqa: E402
from app.core.database import Base, SessionLocal, engine    # noqa: E402
from app.core.security import registrar_bitacora            # noqa: E402
from app.modules.sistema import cargas_controller as cc     # noqa: E402
from app.modules.sistema import cargas_service as cs        # noqa: E402
from app.seed import asegurar_roles                         # noqa: E402

Base.metadata.create_all(engine)
with SessionLocal() as _db:
    asegurar_roles(_db)

CASOS = []


def caso(nombre):
    def deco(fn):
        CASOS.append((nombre, fn))
        return fn
    return deco


def excel(texto="hola") -> bytes:
    wb = Workbook()
    wb.active["A1"] = texto
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class Motor:
    """Hace las veces de sincronizar.sincronizar."""

    def __init__(self, error_en=None, cambios=None):
        self.llamadas = []
        self.error_en = error_en
        self.cambios = cambios or {"unidad": {"nuevas": 0, "borradas": 0, "cambiadas": 3,
                                              "_muestra": []}}

    def __call__(self, carpeta, simular=False):
        archivos = {n: open(os.path.join(carpeta, n), "rb").read()
                    for n in os.listdir(carpeta) if n.endswith(cs.EXTENSIONES)}
        self.llamadas.append({"carpeta": carpeta, "simular": simular, "archivos": archivos})
        pasos = [{"paso": p, "que": "", "estado": "error" if p == self.error_en else "ok",
                  "motivo": "ValueError: hoja equivocada" if p == self.error_en else None}
                 for p in ("base", "limpieza", "personal", "taller", "padron")]
        inf = {"pasos": pasos, "cambios": json.loads(json.dumps(self.cambios)),
               "ejemplos": {}, "cuentas_nuevas": []}
        if not simular:
            inf["respaldo"] = "/datos/bajagas.db.antes-sincronizar-hoy"
            with open(os.path.join(carpeta, "ultima-sincronizacion.json"), "w") as f:
                json.dump({"fin": "ahora", "pasos": pasos}, f)
        return inf


@contextlib.contextmanager
def motor(**kw):
    original = cs.sincronizar.sincronizar
    falso = Motor(**kw)
    cs.sincronizar.sincronizar = falso
    try:
        yield falso
    finally:
        cs.sincronizar.sincronizar = original


def carpeta_con(**archivos) -> str:
    d = tempfile.mkdtemp(prefix="areas-")
    for nombre, contenido in archivos.items():
        with open(os.path.join(d, nombre), "wb") as f:
            f.write(contenido)
    return d


ADMIN = ["administrador"]
ALMACEN = ["datos_almacen"]
LOGISTICA = ["datos_logistica"]


def espera_error(fn, status):
    try:
        fn()
    except cs.ErrorCarga as e:
        assert e.status == status, f"se esperaba {status}, llego {e.status}: {e}"
        return str(e)
    raise AssertionError(f"se esperaba ErrorCarga {status} y no hubo error")


@caso("cada area ve solo lo suyo; el administrador todo; los demas nada")
def _():
    assert set(cs.tipos_permitidos(ADMIN)) == set(cs.TIPOS)
    assert cs.tipos_permitidos(ALMACEN) == ["codigos"]
    assert cs.tipos_permitidos(["datos_compras"]) == ["requisiciones"]
    assert cs.tipos_permitidos(["datos_taller"]) == ["resumen"]
    assert set(cs.tipos_permitidos(LOGISTICA)) == {"unidades", "choferes", "choferes_lan"}
    assert cs.tipos_permitidos(["chofer", "gerente"]) == []


@caso("rechaza lo que no es un Excel antes de gastar un simulacro")
def _():
    espera_error(lambda: cs.validar_excel("datos.csv", b"a,b"), 422)
    espera_error(lambda: cs.validar_excel("datos.xlsx", b"no soy un zip"), 422)
    espera_error(lambda: cs.validar_excel("datos.xlsx", b"PK\x03\x04basura"), 422)
    espera_error(lambda: cs.validar_excel("g.xlsx", b"PK" + b"0" * (cs.TOPE_BYTES + 1)), 413)
    assert cs.validar_excel("bien.xlsx", excel()) == ["Sheet"]


@caso("revisar no toca la carpeta real y prueba con el archivo nuevo en su lugar")
def _():
    viejo, nuevo = excel("viejo"), excel("nuevo")
    areas = carpeta_con(**{"CONTROL GPS.xlsx": viejo, "RESUMEN.xlsx": excel("resumen")})
    with motor() as mt:
        r = cs.simular(areas, "unidades", "Control gps actualizado 16.7.26.xlsx", nuevo, 7)
    assert r["puede_aplicar"] and r["archivo"] == "CONTROL GPS.xlsx"
    llam = mt.llamadas[0]
    assert llam["simular"] is True
    assert llam["carpeta"] != areas, "el simulacro corrio sobre la carpeta real"
    assert llam["archivos"]["CONTROL GPS.xlsx"] == nuevo
    assert "RESUMEN.xlsx" in llam["archivos"], "faltan los archivos de las otras areas"
    assert open(os.path.join(areas, "CONTROL GPS.xlsx"), "rb").read() == viejo
    assert not os.path.exists(llam["carpeta"]), "la carpeta de prueba no se borro"


@caso("REQUIS: el libro viejo, con cualquier nombre, sale del lugar del nuevo")
def _():
    areas = carpeta_con(**{"REQUIS 2026 2 (1).xlsx": excel("viejo"), "~$REQUIS.xlsx": b"x"})
    with motor() as mt:
        r = cs.simular(areas, "requisiciones", "Requis semana 40.xlsm", excel("nuevo"), 1)
    assert r["archivo"] == "REQUIS.xlsm"
    assert sorted(mt.llamadas[0]["archivos"]) == ["REQUIS.xlsm"]


@caso("aplicar: el viejo va a historial, el nuevo a su lugar, y se sincroniza de verdad")
def _():
    viejo, nuevo = excel("viejo"), excel("nuevo")
    areas = carpeta_con(**{"RESUMEN.xlsx": viejo})
    with motor() as mt:
        r = cs.simular(areas, "resumen", "resumen.xlsx", nuevo, 1)
        time.sleep(0.01)
        a = cs.aplicar(areas, r["carga_id"], ["datos_taller"])
    assert mt.llamadas[-1]["simular"] is False and mt.llamadas[-1]["carpeta"] == areas
    assert open(os.path.join(areas, "RESUMEN.xlsx"), "rb").read() == nuevo
    hist = os.listdir(os.path.join(areas, "historial"))
    assert len(hist) == 1 and "--resumen--RESUMEN.xlsx" in hist[0]
    assert open(os.path.join(areas, "historial", hist[0]), "rb").read() == viejo
    assert a["asiento"]["tipo"] == "resumen" and a["asiento"]["original"] == "resumen.xlsx"
    assert "_muestra" not in json.dumps(a["asiento"])
    espera_error(lambda: cs.aplicar(areas, r["carga_id"], ADMIN), 409)


@caso("una area no puede aplicar lo que reviso otra")
def _():
    areas = carpeta_con()
    with motor():
        r = cs.simular(areas, "unidades", "u.xlsx", excel(), 1)
        espera_error(lambda: cs.aplicar(areas, r["carga_id"], ALMACEN), 403)
        espera_error(lambda: cs.aplicar(areas, "../../etc", ADMIN), 404)
        espera_error(lambda: cs.aplicar(areas, "20260101-000000-abcdef", ADMIN), 404)


@caso("si algo sincronizo despues de revisar, pide revisar otra vez")
def _():
    areas = carpeta_con()
    with motor():
        r = cs.simular(areas, "codigos", "c.xlsx", excel(), 1)
        ultima = os.path.join(areas, "ultima-sincronizacion.json")
        with open(ultima, "w") as f:
            f.write("{}")
        futuro = time.time() + 5
        os.utime(ultima, (futuro, futuro))
        espera_error(lambda: cs.aplicar(areas, r["carga_id"], ALMACEN), 409)
    assert not os.path.exists(os.path.join(areas, "CODIGOS TALLER.xlsx"))


@caso("si la revision encontro error en su paso, no deja aplicar")
def _():
    areas = carpeta_con()
    with motor(error_en="taller"):
        r = cs.simular(areas, "resumen", "r.xlsx", excel(), 1)
        assert not r["puede_aplicar"] and "taller" in r["motivo"]
        espera_error(lambda: cs.aplicar(areas, r["carga_id"], ADMIN), 422)
    with motor(error_en="taller"):
        r = cs.simular(areas, "unidades", "u.xlsx", excel(), 1)
    assert r["puede_aplicar"], "el error de OTRA area no debe frenar esta carga"


@caso("si al aplicar de verdad falla su paso, regresa el archivo anterior")
def _():
    viejo = excel("viejo")
    areas = carpeta_con(**{"CONTROL GPS.xlsx": viejo})
    with motor() as mt:
        r = cs.simular(areas, "unidades", "u.xlsx", excel("nuevo"), 1)
    with motor(error_en="padron"):
        msg = espera_error(lambda: cs.aplicar(areas, r["carga_id"], LOGISTICA), 422)
    assert "anterior" in msg
    assert open(os.path.join(areas, "CONTROL GPS.xlsx"), "rb").read() == viejo
    assert os.listdir(os.path.join(areas, "historial")) == []


@caso("avisa cuando el archivo borraria filas o cambiaria muchas")
def _():
    cambios = {"unidad": {"nuevas": 0, "borradas": 0, "cambiadas": 700, "_muestra": []},
               "pieza": {"nuevas": 2, "borradas": 4, "cambiadas": 1, "_muestra": []},
               "chofer": {"nuevas": 1, "borradas": 0, "cambiadas": 3, "_muestra": []}}
    with motor(cambios=cambios):
        r = cs.simular(carpeta_con(), "unidades", "u.xlsx", excel(), 1)
    assert {(a["tabla"], a["tipo"]) for a in r["alertas"]} == {("unidad", "cambiadas"),
                                                              ("pieza", "borradas")}


@caso("el historial guarda los ultimos 15 de cada tipo")
def _():
    h = carpeta_con(**{f"20260101-0000{i:02d}--resumen--RESUMEN.xlsx": b"x" for i in range(20)},
                    **{"20260101-000000--codigos--CODIGOS TALLER.xlsx": b"y"})
    cs._podar_historial(h, "resumen")
    quedan = sorted(os.listdir(h))
    assert len([n for n in quedan if "--resumen--" in n]) == 15
    assert "20260101-000019--resumen--RESUMEN.xlsx" in quedan
    assert "20260101-000000--codigos--CODIGOS TALLER.xlsx" in quedan


class Persona:
    def __init__(self, id_, roles):
        self.id, self.lista_roles = id_, roles


@caso("el historial de la pantalla solo ensena las cargas de tu area")
def _():
    os.environ["CARPETA_AREAS"] = carpeta_con()
    with SessionLocal() as db:
        u = m.Usuario(nombre="Ana", apellidos="Logistica", email="ana@x.mx", password_hash="x")
        db.add(u)
        db.flush()
        for tipo in ("unidades", "codigos"):
            registrar_bitacora(db, u.id, cc.ACCION, "archivo_area", None,
                               datos_despues=json.dumps({"tipo": tipo, "original": tipo,
                                                         "cambios": {"t": {"nuevas": 1}}}))
        db.commit()
        r = cc.estado(usuario=Persona(u.id, LOGISTICA), db=db)
        assert [h["tipo"] for h in r["historial"]] == ["unidades"]
        assert r["historial"][0]["quien"] == "Ana Logistica"
        assert {a["tipo"] for a in r["archivos"]} == {"unidades", "choferes", "choferes_lan"}
        r = cc.estado(usuario=Persona(u.id, ADMIN), db=db)
        assert len(r["historial"]) == 2


@caso("el endpoint niega subir un archivo de otra area")
def _():
    class Subido:
        filename = "u.xlsx"
        file = io.BytesIO(excel())
    try:
        cc.simular("unidades", archivo=Subido(), usuario=Persona(1, ALMACEN))
    except HTTPException as e:
        assert e.status_code == 403
    else:
        raise AssertionError("dejo subir unidades a almacen")


@caso("cuentas por area: se crean una vez, sin imprimir contrasenas")
def _():
    ruta = os.path.join(tempfile.mkdtemp(), "cred.csv")
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        assert cuentas_de_area.main(["--csv", ruta]) == 0       # sin --si: nada
        assert not os.path.exists(ruta)
        assert cuentas_de_area.main(["--si", "--csv", ruta]) == 0
        assert cuentas_de_area.main(["--si", "--csv", ruta + "2"]) == 0
    with open(ruta, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 4 and not os.path.exists(ruta + "2")
    for fila in filas:
        assert fila["password"] not in salida.getvalue(), "imprimio una contrasena"
    with SessionLocal() as db:
        u = db.query(m.Usuario).filter_by(email="datos_almacen@bajagas.mx").one()
        assert u.lista_roles == ["datos_almacen"]
        assert cs.tipos_permitidos(u.lista_roles) == ["codigos"]


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
