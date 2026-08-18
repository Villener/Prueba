"""Datos semilla. El taller reproduce el plano en Excel que entrego el cliente.

Zonas y numeracion tomadas del plano (docs/modelo-er.md §9). La numeracion se
repite entre zonas: hay un "1" en REPARTO, otro en ELECTRICOS y otro en el patio.
Por eso la unicidad es (zona, numero) y no global.
"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from . import models as m
from .database import Base, SessionLocal, engine
from .security import hash_password

# (nombre, proposito, cuenta_para_ocupacion, tipo_permitido, [numeros], fila)
LAYOUT_TALLER = [
    ("REPARTO NORTE",   "operativa",     True,  "reparto",    [str(i) for i in range(1, 11)],  0),
    ("PIPAS",           "operativa",     True,  "pipa",       [str(i) for i in range(11, 19)], 0),
    ("LLANTERA",        "especialidad",  True,  None,         ["L1"],                          0),
    ("ELECTRICOS",      "especialidad",  True,  None,         ["1", "2", "3"],                 2),
    ("UTILITARIOS",     "operativa",     True,  "utilitario", ["4", "5", "6"],                 2),
    ("REPARTO SUR",     "operativa",     True,  "reparto",    [str(i) for i in range(7, 13)],  2),
    ("FOSA",            "especialidad",  True,  None,         ["F1"],                          2),
    ("PATIO",           "operativa",     True,  None,         [str(i) for i in range(1, 13)],  1),
    ("AREA LAVADO",     "apoyo",         False, None,         ["W1"],                          1),
    ("YONKE",           "almacenaje",    False, None,         [str(i) for i in range(1, 46)],  3),
    ("OFICINA",         "no_operativa",  False, None,         [],                              4),
    ("CONTENEDOR BASURA", "no_operativa", False, None,        [],                              4),
]

USUARIOS_DEMO = [
    # (nombre, apellidos, email, rol, password)
    ("Martin",   "Lopez Elizalde", "gerente@bajagas.mx",       "gerente",        "demo1234"),
    ("Rosa",     "Medina Cruz",    "admin@bajagas.mx",         "administrador",  "demo1234"),
    ("Javier",   "Ontiveros Paz",  "supervisor@bajagas.mx",    "supervisor",     "demo1234"),
    ("Luis",     "Barrera Soto",   "chofer1@bajagas.mx",       "chofer",         "demo1234"),
    ("Ana",      "Villalobos Rey", "chofer2@bajagas.mx",       "chofer",         "demo1234"),
    ("Pedro",    "Nunez Salas",    "chofer3@bajagas.mx",       "chofer",         "demo1234"),
    ("Ivan",     "Cordero Diaz",   "montacargas@bajagas.mx",   "montacarguista", "demo1234"),
]

# Los tecnicos NO son usuarios: no tienen correo ni contrasena (v1.1).
TECNICOS_DEMO = [
    ("Ramon", "Aguilar Mena",   "T-001", "mecanico"),
    ("Sergio", "Beltran Ruiz",  "T-002", "mecanico"),
    ("Hugo", "Carrillo Lopez",  "T-003", "carrocero"),
    ("Elias", "Duarte Fuentes", "T-004", "electricista"),
    ("Nestor", "Esparza Rios",  "T-005", "llantero"),
]


def sembrar(db: Session):
    if db.query(m.Rol).count() > 0:
        return "La base ya tenia datos; no se volvio a sembrar."

    # ------------------------------------------------------------- roles ---- #
    roles = {}
    for nombre in ["chofer", "supervisor", "administrador", "montacarguista", "gerente"]:
        r = m.Rol(nombre=nombre, descripcion=f"Modulo {nombre}")
        db.add(r)
        roles[nombre] = r
    db.flush()

    # ------------------------------------------------------- tipos unidad --- #
    tipos = {}
    for nombre in ["reparto", "pipa", "utilitario", "montacargas"]:
        t = m.TipoUnidad(nombre=nombre, descripcion=f"Unidad tipo {nombre}")
        db.add(t)
        tipos[nombre] = t
    db.flush()

    # ---------------------------------------------------------- usuarios ---- #
    usuarios = {}
    for nombre, apellidos, email, rol, pwd in USUARIOS_DEMO:
        u = m.Usuario(nombre=nombre, apellidos=apellidos, email=email,
                      telefono="664-000-0000", password_hash=hash_password(pwd))
        db.add(u)
        db.flush()
        db.add(m.UsuarioRol(usuario_id=u.id, rol_id=roles[rol].id))
        usuarios[email] = (u, rol)
    db.flush()

    sup = m.Supervisor(usuario_id=usuarios["supervisor@bajagas.mx"][0].id, zona="Tijuana Centro")
    db.add(sup)
    db.flush()
    cuadrilla = m.Cuadrilla(nombre="Cuadrilla Centro", supervisor_id=sup.usuario_id)
    db.add(cuadrilla)
    db.flush()

    choferes = []
    for email in ["chofer1@bajagas.mx", "chofer2@bajagas.mx", "chofer3@bajagas.mx"]:
        u = usuarios[email][0]
        c = m.Chofer(usuario_id=u.id, num_licencia=f"LIC-{u.id:04d}", tipo_licencia="E",
                     vencimiento_licencia=date.today() + timedelta(days=365),
                     cuadrilla_id=cuadrilla.id)
        db.add(c)
        choferes.append(c)
    db.flush()

    # ------------------------------------------------------------ taller ---- #
    taller = m.Taller(nombre="Taller Central Tijuana", direccion="Blvd. Insurgentes 1200",
                      latitud=32.5149, longitud=-117.0382)
    db.add(taller)
    db.flush()

    for orden, (nombre, proposito, cuenta, tipo_perm, numeros, fila) in enumerate(LAYOUT_TALLER):
        z = m.ZonaTaller(taller_id=taller.id, nombre=nombre, proposito=proposito,
                         capacidad=len(numeros), cuenta_para_ocupacion=cuenta, orden=orden)
        db.add(z)
        db.flush()
        for i, num in enumerate(numeros):
            db.add(m.Espacio(zona_id=z.id, numero=num,
                             tipo_unidad_permitido_id=tipos[tipo_perm].id if tipo_perm else None,
                             pos_x=i, pos_y=fila))
    db.flush()

    # ---------------------------------------------------------- tecnicos ---- #
    tecnicos = []
    for nombre, apellidos, num, esp in TECNICOS_DEMO:
        t = m.Tecnico(nombre=nombre, apellidos=apellidos, num_empleado=num, especialidad=esp,
                      taller_id=taller.id, telefono="664-111-2233")
        db.add(t)
        tecnicos.append(t)
    db.flush()

    # ----------------------------------------------------------- unidades --- #
    unidades = []
    datos_unidades = [
        ("U-101", "AB-123-CD", "reparto", "Isuzu", "NPR", 2021, 148_500),
        ("U-102", "AB-456-CD", "reparto", "Isuzu", "NPR", 2020, 210_300),
        ("U-201", "PP-789-AA", "pipa", "Kenworth", "T370", 2019, 305_800),
        ("U-301", "UT-321-BB", "utilitario", "Nissan", "NP300", 2022, 61_200),
    ]
    for i, (eco, placas, tipo, marca, modelo, anio, km) in enumerate(datos_unidades):
        titular = choferes[i].usuario_id if i < len(choferes) else None
        u = m.Unidad(num_economico=eco, placas=placas, vin=f"VIN{eco}0000000",
                     marca=marca, modelo=modelo, anio=anio, tipo_unidad_id=tipos[tipo].id,
                     titular_chofer_id=titular, poseedor_chofer_id=titular,
                     km_actual=km, fecha_alta=date(anio, 1, 15))
        db.add(u)
        unidades.append(u)
    db.flush()

    mont = m.Montacarguista(usuario_id=usuarios["montacargas@bajagas.mx"][0].id,
                            licencia_especial="ME-9911")
    db.add(mont)

    # ------------------------------------------------------ mantenimiento --- #
    planes = {}
    for tipo_nombre, dias, km in [("reparto", 90, 10_000), ("pipa", 60, 8_000),
                                  ("utilitario", 120, 12_000)]:
        p = m.PlanMantenimiento(tipo_unidad_id=tipos[tipo_nombre].id,
                                nombre=f"Servicio preventivo {tipo_nombre}",
                                periodicidad_dias=dias, periodicidad_km=km,
                                descripcion="Aceite, filtros, frenos, suspension")
        db.add(p)
        planes[tipo_nombre] = p
    db.flush()

    # U-101 con mantenimiento VENCIDO: dispara penalizacion al correr el job.
    # U-102 por vencer, U-201 al corriente. Asi el demo muestra los tres casos.
    desfases = [-12, 5, 40, 75]
    for u, desfase in zip(unidades, desfases):
        plan = planes.get(u.tipo.nombre)
        if not plan:
            continue
        db.add(m.ProgramaMantenimiento(
            unidad_id=u.id, plan_id=plan.id,
            fecha_programada=date.today() + timedelta(days=desfase),
            km_programado=u.km_actual + 5_000,
            fecha_limite=date.today() + timedelta(days=desfase), estado="pendiente"))

    # ------------------------------------------------------------ piezas ---- #
    for sku, nombre, precio, stock in [
            ("FLT-001", "Filtro de aceite", 320, 24),
            ("FLT-002", "Filtro de aire", 480, 12),
            ("BAL-010", "Balatas delanteras (juego)", 1850, 6),
            ("AMO-020", "Amortiguador trasero", 2400, 4),
            ("BAT-030", "Bateria 12V 900CCA", 3900, 3),
            ("LLA-040", "Llanta 11R22.5", 5600, 8)]:
        db.add(m.Pieza(sku=sku, nombre=nombre, precio_referencia=precio, stock_actual=stock,
                       stock_minimo=2))

    db.add(m.Proveedor(nombre="Refaccionaria del Pacifico", rfc="RPA010101AAA",
                       contacto="Marisol Ibarra", telefono="664-555-1010"))

    # -------------------------------------------------------- parametros ---- #
    for clave, valor, desc in [
            ("meses_unidad_parada", "3", "RN-08: meses para alertar unidad parada"),
            ("dias_tolerancia_penalizacion", "0", "RN-05: dias de gracia antes de penalizar"),
            ("horas_max_captura", "2", "Ventana acordada para capturar el trabajo del mecanico")]:
        db.add(m.Configuracion(clave=clave, valor=valor, descripcion=desc))

    db.commit()
    return "Datos semilla creados."


def inicializar():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        return sembrar(db)
    finally:
        db.close()


if __name__ == "__main__":
    print(inicializar())
