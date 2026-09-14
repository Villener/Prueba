"""Le pone una contrasena distinta y aleatoria a cada cuenta.

POR QUE HACE FALTA. Las 335 cuentas comparten la contrasena `bajagas2026`, que
esta escrita en seed.py, en importador.py, en el README y hasta la pintaba la
pantalla de login. En la red de la casa era comodo; con una URL publica es una
sola contrasena para toda la plantilla, y esta publicada.

QUE HACE. Genera una contrasena por usuario, la guarda hasheada con bcrypt (lo
mismo que hace el alta normal) y escribe un CSV con las claves en claro para que
puedas repartirlas. El CSV es lo unico que las tiene: si lo pierdes hay que
volver a rotar, no hay forma de recuperarlas.

USO
    docker compose exec api python -m app.rotar_passwords --si
    docker compose cp api:/datos/credenciales.csv ./credenciales.csv

Sin `--si` no hace nada: solo dice a cuantas cuentas les tocaria.

    --solo-staff   rota unicamente las cuentas que no son chofer ni supervisor
                   (gerente, administradores, capturista, choferes de grua).
                   Los 300+ choferes se quedan como estan.
    --choferes N   cuantos choferes de muestra se imprimen en pantalla (3 por
                   omision). Con 0 no se imprime ninguno. No cambia a quien se
                   le rota la clave: eso lo decide --solo-staff.
"""
import argparse
import csv
import secrets
import sys

from .core.database import SessionLocal
from .core.security import hash_password
from . import models as m

# Alfabeto sin caracteres que se confunden al dictarlos por telefono:
# nada de l/I/1, ni O/0. Que alguien no pueda entrar porque leyo una ele donde
# habia un uno es un problema de soporte, no de seguridad.
ALFABETO = "abcdefghijkmnpqrstuvwxyzACDEFGHJKLMNPQRSTUVWXYZ23456789"
ROLES_STAFF = {"gerente", "administrador", "capturista", "chofer_grua"}


def generar() -> str:
    """12 caracteres en tres grupos: se dictan y se teclean sin pelearse."""
    bruto = "".join(secrets.choice(ALFABETO) for _ in range(12))
    return f"{bruto[:4]}-{bruto[4:8]}-{bruto[8:]}"


def _muestra_de_choferes(db, claves: dict, cuantos: int) -> list:
    """Unos pocos choferes para poder probar, no los 297.

    Van primero los que traen unidad asignada: con un chofer sin unidad la
    pantalla que mas se usa abre vacia y la prueba no dice nada. El
    `is_(None)` en el order_by es lo que los empuja arriba (False antes que
    True); si no alcanzan, la misma consulta completa con los que haya.
    """
    if cuantos <= 0 or not claves:
        return []

    filas = (db.query(m.Usuario, m.Unidad)
             .join(m.Chofer, m.Chofer.usuario_id == m.Usuario.id)
             .outerjoin(m.Unidad, m.Unidad.poseedor_chofer_id == m.Usuario.id)
             .filter(m.Usuario.id.in_(claves))
             .order_by(m.Unidad.num_economico.is_(None), m.Unidad.num_economico)
             .limit(cuantos * 2).all())

    # Un chofer puede traer mas de una unidad y salir repetido: se queda con la
    # primera, que por el orden de arriba es la que si tiene numero economico.
    salida, vistos = [], set()
    for u, unidad in filas:
        if u.id in vistos:
            continue
        vistos.add(u.id)
        salida.append((u, unidad.num_economico if unidad else None))
        if len(salida) == cuantos:
            break
    return salida


def main() -> int:
    p = argparse.ArgumentParser(description="Rota las contrasenas de todas las cuentas.")
    p.add_argument("--si", action="store_true",
                   help="confirma la rotacion (sin esto solo se simula)")
    p.add_argument("--solo-staff", action="store_true",
                   help="solo las cuentas de oficina, no los choferes")
    p.add_argument("--choferes", type=int, default=3, metavar="N",
                   help="cuantos choferes de muestra imprimir (0 = ninguno)")
    p.add_argument("--csv", default="/datos/credenciales.csv",
                   help="donde dejar las contrasenas en claro")
    args = p.parse_args()

    db = SessionLocal()
    try:
        usuarios = db.query(m.Usuario).filter(m.Usuario.activo.is_(True)).all()
        if args.solo_staff:
            usuarios = [u for u in usuarios if ROLES_STAFF & set(u.lista_roles)]

        if not args.si:
            print(f"SIMULACRO: se les cambiaria la contrasena a {len(usuarios)} cuenta(s).")
            print("Cuando estes listo, vuelve a correrlo con  --si")
            return 0

        filas = []
        # La clave en claro solo vive aqui y en el CSV: para poder imprimir la
        # muestra de choferes hace falta poder volver del usuario a su clave.
        clave_por_usuario = {}
        for u in usuarios:
            clave = generar()
            u.password_hash = hash_password(clave)
            clave_por_usuario[u.id] = clave
            filas.append({
                "nombre": u.nombre_completo,
                "correo": u.email,
                "roles": ",".join(u.lista_roles),
                "password": clave,
            })
        db.commit()

        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["nombre", "correo", "roles", "password"])
            w.writeheader()
            w.writerows(filas)

        print(f"Rotadas {len(filas)} contrasenas. CSV -> {args.csv}")
        print()
        # En pantalla solo el personal de oficina: son las cuentas que de verdad
        # vas a repartir. Volcar 300 choferes aqui solo llena la terminal.
        staff = [f for f in filas if ROLES_STAFF & set(f["roles"].split(","))]
        if staff:
            print("Cuentas de oficina:")
            ancho = max(len(f["correo"]) for f in staff)
            for f in sorted(staff, key=lambda x: x["roles"]):
                print(f"  {f['correo']:<{ancho}}  {f['password']}   {f['nombre']} ({f['roles']})")

        # Y una muestra de choferes. Sin al menos un par de cuentas de chofer no
        # se puede probar la pantalla que mas se usa, y buscarlas a mano en un
        # CSV de 300 renglones cada vez es perder el tiempo.
        muestra = _muestra_de_choferes(db, clave_por_usuario, args.choferes)
        if muestra:
            total = sum(1 for f in filas if "chofer" in f["roles"].split(","))
            print()
            print(f"Choferes de muestra ({len(muestra)} de {total}):")
            ancho = max(len(u.email) for u, _ in muestra)
            for u, unidad in muestra:
                donde = f"unidad {unidad}" if unidad else "sin unidad asignada"
                print(f"  {u.email:<{ancho}}  {clave_por_usuario[u.id]}   "
                      f"{u.nombre_completo} ({donde})")
        elif args.choferes > 0 and args.solo_staff:
            print()
            print("Sin choferes: --solo-staff no les toca la contrasena.")
        print()
        print("El CSV es la unica copia de estas claves. Guardalo fuera del repositorio.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
