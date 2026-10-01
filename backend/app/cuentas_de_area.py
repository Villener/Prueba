"""Crea las cuentas de carga de datos: una por area, con contrasena al azar.

Cada area (Logistica, Almacen, Compras, Taller) sube sus Excel desde su propia
cuenta, que solo ve la pantalla de carga y solo puede subir lo suyo (ver
modules/sistema/cargas_service.py). El administrador puede subir todo con la
suya.

USO, dentro del contenedor de la API:

    python -m app.cuentas_de_area          # dice que cuentas faltan
    python -m app.cuentas_de_area --si     # las crea

Con --si escribe /datos/credenciales-areas.csv (nombre, correo, roles,
password: las mismas columnas que credenciales.csv) y NO imprime ninguna
contrasena: la salida de una terminal acaba pegada en un chat. Las cuentas que
ya existen no se tocan.
"""
import argparse
import csv
import sys

from . import models as m
from .core.database import SessionLocal
from .core.security import hash_password
from .modules.sistema.cargas_service import AREAS, ROL_DE_AREA
from .rotar_passwords import generar

NOMBRE_AREA = {"logistica": "Logística", "almacen": "Almacén", "compras": "Compras",
               "taller": "Taller"}


def correo(area: str) -> str:
    return f"{ROL_DE_AREA[area]}@bajagas.mx"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Crea las cuentas de carga de datos por area.")
    p.add_argument("--si", action="store_true", help="crearlas de verdad")
    p.add_argument("--csv", default="/datos/credenciales-areas.csv")
    args = p.parse_args(argv)

    with SessionLocal() as db:
        roles = {r.nombre: r for r in db.query(m.Rol).all()}
        faltan = [a for a in AREAS
                  if not db.query(m.Usuario).filter_by(email=correo(a)).first()]
        sin_rol = [ROL_DE_AREA[a] for a in faltan if ROL_DE_AREA[a] not in roles]
        if sin_rol:
            print("Faltan los roles %s: reinicia la api para que los cree." % ", ".join(sin_rol))
            return 1
        if not faltan:
            print("Las cuatro cuentas ya existen. No se hizo nada.")
            return 0
        print("Cuentas por crear: " + ", ".join(correo(a) for a in faltan))
        if not args.si:
            print("Para crearlas agrega --si.")
            return 0

        filas = []
        for a in faltan:
            clave = generar()
            u = m.Usuario(nombre="Carga de datos", apellidos=NOMBRE_AREA[a], email=correo(a),
                          password_hash=hash_password(clave))
            db.add(u)
            db.flush()
            db.add(m.UsuarioRol(usuario_id=u.id, rol_id=roles[ROL_DE_AREA[a]].id))
            filas.append({"nombre": f"Carga de datos {NOMBRE_AREA[a]}", "correo": correo(a),
                          "roles": ROL_DE_AREA[a], "password": clave})
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["nombre", "correo", "roles", "password"])
            w.writeheader()
            w.writerows(filas)
        db.commit()
        print(f"Creadas {len(filas)} cuentas. Contrasenas en {args.csv} (no se imprimen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
