"""Datos de DEMOSTRACION para el tablero del gerente. No es parte del sistema.

POR QUE EXISTE ESTE ARCHIVO.

Las cuatro graficas que el gerente pidio --tiempo promedio de reparacion, tasa
de citas concretadas, citas totales y atenciones a citas-- se alimentan de
CitaTaller y de OrdenServicio. La base de produccion importada tiene hoy 1,367
unidades y 1,918 movimientos de taller, pero solo DOS citas, las dos en estado
"confirmada" y las dos el mismo dia, y 22 ordenes cerradas de las cuales 20
entraron y salieron el mismo dia.

Con eso, tres de las cuatro graficas salen en blanco y la cuarta es una raya:
no porque el calculo falle, sino porque ese dato todavia no se captura. En una
demostracion eso se lee como "el tablero esta roto", que es justo la conclusion
equivocada.

Este script siembra citas y ordenes con forma para poder ENSENAR el tablero. No
toca ninguna regla de negocio, no se ejecuta solo y no lo importa nadie.

QUE SE PUEDE DESHACER Y COMO. Todo lo que escribe queda marcado en el propio
dato, no en un archivo aparte que se pueda perder:

    citas           origen_agenda = "demo"   (la columna no la lee nadie mas;
                                              agenda_service solo la escribe)
    ordenes         folio empieza con "DEMO-"
    avisos          cuelgan de una cita demo por cita_id
    asignaciones    cuelgan de una orden demo por orden_servicio_id

Asi que `--deshacer` los encuentra y los borra aunque se haya reiniciado la
maquina, se haya copiado la base o se haya perdido este archivo.

USO, parado en backend/ y con el entorno virtual activo:

    python -m app.sembrar_demo              siembra
    python -m app.sembrar_demo --estado     dice que hay sembrado
    python -m app.sembrar_demo --deshacer   lo borra todo

ADVERTENCIA: despues de sembrar, los numeros del tablero YA NO son los reales.
Para volver a la foto de produccion hay que correr --deshacer.
"""
import argparse
import datetime
import random
import sys

from .core.database import SessionLocal
from .core.tiempo import TZ_OPERACION, a_utc
from . import models as m
from .jobs import MARCA_CITA_DEMO, PREFIJO_FOLIO_DEMO

# Marcas de origen. Son la unica forma de saber que fila puso este script, y por
# eso van en el dato y no en un manifiesto: un archivo JSON al lado se pierde en
# la primera copia de la base y entonces lo sembrado ya no se distingue de lo
# capturado, que es como una demo acaba contaminando produccion para siempre.
# Se definen en jobs.py, que es quien se niega a correr si las encuentra: este
# archivo no viaja a produccion y aquel si.
MARCA_CITA = MARCA_CITA_DEMO
PREFIJO_FOLIO = PREFIJO_FOLIO_DEMO

MESES_ATRAS = 18

# La semilla es fija a proposito: dos corridas dan el mismo tablero. Si cada
# ejecucion inventara numeros distintos, una cifra que el gerente anoto en una
# junta no volveria a aparecer en la siguiente y el tablero perderia toda
# credibilidad justo por un detalle de la demostracion.
SEMILLA = 20260921

# El cumplimiento mensual no es plano ni es una recta: sube, cae y se recupera.
# Una serie plana no deja ver que la grafica funciona --se ve igual que un valor
# fijo escrito a mano-- y una recta perfecta se nota falsa a simple vista. Estos
# son los porcentajes objetivo de citas cumplidas, del mes mas viejo al mas
# reciente, y se recorren ciclicamente si el rango pide mas meses.
FORMA_CUMPLIMIENTO = [0.72, 0.78, 0.81, 0.76, 0.84, 0.88,
                      0.91, 0.86, 0.69, 0.74, 0.83, 0.89,
                      0.93, 0.90, 0.85, 0.79, 0.87, 0.92]

# Lo que queda escrito en la columna "QUE SE HIZO" del detalle por mecanico.
# Son frases del taller y no un "trabajo realizado 1, 2, 3": esa columna es la
# que el gerente lee cuando pregunta por un renglon concreto, y un relleno
# numerado delata el dato sembrado en el primer vistazo de una junta.
TRABAJOS_REALIZADOS = [
    "Se cambio aceite y filtros, se reviso nivel de refrigerante",
    "Ajuste de frenos delanteros y cambio de balatas",
    "Se reemplazo la bomba de agua y se purgo el sistema",
    "Cambio de llantas traseras y balanceo",
    "Se solto el clutch, se ajusto y se probo en marcha",
    "Revision de suspension, se cambiaron bujes",
    "Se atendio fuga de aceite en el carter",
    "Cambio de bateria y revision del alternador",
    "Se reparo instalacion electrica de luces traseras",
    "Afinacion mayor, se cambiaron bujias y cables",
    "Se soldo el soporte del tanque y se pinto",
    "Ajuste de direccion y alineacion",
]


def _primer_dia(hoy: datetime.date, atras: int) -> datetime.date:
    """El primer dia del mes que queda `atras` meses antes del de `hoy`."""
    y, mes = hoy.year, hoy.month - atras
    while mes <= 0:
        y, mes = y - 1, mes + 12
    return datetime.date(y, mes, 1)


def _meses(hoy: datetime.date) -> list:
    """Los (anio, mes) del rango a sembrar, del mas viejo al mas reciente."""
    fuera = []
    f = _primer_dia(hoy, MESES_ATRAS - 1)
    while (f.year, f.month) <= (hoy.year, hoy.month):
        fuera.append((f.year, f.month))
        f = _primer_dia(f, -1) if f.month < 12 else datetime.date(f.year + 1, 1, 1)
    return fuera


def _dias_del_mes(anio: int, mes: int, hoy: datetime.date) -> list:
    """Los dias habiles del mes, sin pasarse de hoy.

    Se excluye el domingo porque el taller no recibe: una grafica diaria con
    citas en domingo delata de inmediato que el dato es inventado.

    Y se corta en `hoy` porque una cita CUMPLIDA con fecha futura es una
    contradiccion. El mes en curso tiene que quedar a medias: es exactamente lo
    que el tablero pinta apagado como "periodo en curso", y si se llenara el mes
    completo esa parte de la pantalla nunca se podria mostrar.
    """
    fuera = []
    d = datetime.date(anio, mes, 1)
    while d.month == mes and d <= hoy:
        if d.weekday() != 6:
            fuera.append(d)
        d += datetime.timedelta(days=1)
    return fuera


def _instante(dia: datetime.date, hora: int, minuto: int) -> datetime.datetime:
    """Un momento del dia operativo de Tijuana, guardado en UTC.

    Se arma en Tijuana y se convierte, no al reves. Una orden cerrada a las
    17:30 del 30 de septiembre en el taller es 00:30 del 1 de octubre en UTC:
    si se escribiera la hora directamente como UTC, dia_operativo() la mandaria
    al mes siguiente y la orden desapareceria de septiembre en el tablero.
    """
    local = datetime.datetime(dia.year, dia.month, dia.day, hora, minuto,
                              tzinfo=TZ_OPERACION)
    return a_utc(local)


def _candidatas(db):
    """Unidades con chofer, que son las que el tablero puede atribuir.

    Se piden con chofer a proposito: el cumplimiento por chofer y el expediente
    resuelven el responsable por el poseedor de la unidad, y una cita sobre una
    unidad sin chofer no aparece en ninguna de esas dos pantallas. Sembrar ahi
    seria sembrar filas que nadie ve.
    """
    return (db.query(m.Unidad)
            .filter((m.Unidad.poseedor_chofer_id.isnot(None))
                    | (m.Unidad.titular_chofer_id.isnot(None))).all())


def _ids_ordenes(db) -> list:
    """Los ids de las ordenes sembradas. De aqui cuelgan las asignaciones."""
    return [o.id for o in db.query(m.OrdenServicio)
            .filter(m.OrdenServicio.folio.like(PREFIJO_FOLIO + "%")).all()]


def _contar(db) -> dict:
    citas = (db.query(m.CitaTaller)
             .filter(m.CitaTaller.origen_agenda == MARCA_CITA).count())
    ids_orden = _ids_ordenes(db)
    ids = [c.id for c in db.query(m.CitaTaller)
           .filter(m.CitaTaller.origen_agenda == MARCA_CITA).all()]
    avisos = (db.query(m.AvisoIncumplimiento)
              .filter(m.AvisoIncumplimiento.cita_id.in_(ids)).count() if ids else 0)
    # La asignacion no lleva marca propia: se reconoce por la orden de la que
    # cuelga. Es suficiente y no hace falta inventarle una columna, porque una
    # asignacion sin su orden no existe -- la FK es obligatoria.
    asignaciones = (db.query(m.AsignacionTecnico)
                    .filter(m.AsignacionTecnico.orden_servicio_id.in_(ids_orden))
                    .count() if ids_orden else 0)
    return {"citas": citas, "ordenes": len(ids_orden), "avisos": avisos,
            "asignaciones": asignaciones}


def deshacer(db) -> dict:
    """Borra lo sembrado y NADA mas. El orden importa: los avisos primero."""
    antes = _contar(db)
    ids = [c.id for c in db.query(m.CitaTaller)
           .filter(m.CitaTaller.origen_agenda == MARCA_CITA).all()]
    if ids:
        (db.query(m.AvisoIncumplimiento)
         .filter(m.AvisoIncumplimiento.cita_id.in_(ids))
         .delete(synchronize_session=False))
    (db.query(m.CitaTaller)
     .filter(m.CitaTaller.origen_agenda == MARCA_CITA)
     .delete(synchronize_session=False))

    # LAS ASIGNACIONES ANTES QUE SUS ORDENES, y el orden aqui no es cosmetico.
    # SQLite no aplica las llaves foraneas por omision, asi que borrar la orden
    # primero no falla: deja la asignacion apuntando a una orden que ya no
    # existe. Esa fila huerfana sobrevive al --deshacer, y como se reconoce por
    # su orden y la orden ya no esta, no hay forma de volver a encontrarla. Se
    # queda para siempre contando en la tabla de asignaciones de datos reales.
    ids_orden = _ids_ordenes(db)
    if ids_orden:
        (db.query(m.AsignacionTecnico)
         .filter(m.AsignacionTecnico.orden_servicio_id.in_(ids_orden))
         .delete(synchronize_session=False))
    (db.query(m.OrdenServicio)
     .filter(m.OrdenServicio.folio.like(PREFIJO_FOLIO + "%"))
     .delete(synchronize_session=False))
    db.commit()
    return antes


def sembrar(db, hoy: datetime.date | None = None) -> dict:
    hoy = hoy or datetime.date.today()
    azar = random.Random(SEMILLA)

    unidades = _candidatas(db)
    if not unidades:
        raise SystemExit(
            "No hay una sola unidad con chofer asignado. Sin eso las citas no se\n"
            "pueden atribuir a nadie y el cumplimiento por chofer saldria vacio.\n"
            "Revisa que la importacion de flota y personal haya corrido.")

    talleres = [t.id for t in db.query(m.Taller).all()]
    tipos = [t.id for t in db.query(m.TipoServicio).all()]
    if not talleres:
        raise SystemExit("No hay talleres cargados: no hay donde citar.")

    # Los tecnicos de cada taller, para poder asignarles el trabajo. Se agrupan
    # por su ADSCRIPCION y no se mezclan: el ASISTIDO de Alamos no va a Tecate
    # --no usa la app siquiera, Erick captura lo suyo en papel-- y el AUTONOMO
    # esta solo en su planta con su vehiculo de servicio. Cruzarlos sembraria un
    # viaje que nadie hizo.
    tecnicos_de: dict = {}
    for t in db.query(m.Tecnico).filter(m.Tecnico.activo.is_(True)).all():
        if t.taller_id:
            tecnicos_de.setdefault(t.taller_id, []).append(t)
    for lista in tecnicos_de.values():
        azar.shuffle(lista)
    if not tecnicos_de:
        raise SystemExit(
            "No hay un solo tecnico activo con taller asignado. Sin eso las\n"
            "ordenes se siembran sin mecanico y el historial por mecanico sale\n"
            "vacio, que es justo lo que esto viene a llenar.")

    # LAS ORDENES SE REPARTEN SEGUN DONDE ESTA LA GENTE, no en partes iguales
    # entre los seis talleres. Alamos tiene 36 de los 42 tecnicos y las satelites
    # uno o dos cada una: repartiendo parejo, el autonomo de Tecate salia con
    # setenta ordenes en dieciocho meses y los treinta y seis de Alamos con dos
    # cada uno. Las dos cifras son falsas y la primera es ademas una acusacion
    # de que la satelite esta desbordada.
    rueda_talleres = []
    for tid, lista in tecnicos_de.items():
        rueda_talleres += [tid] * len(lista)

    # Se siembra sobre una copia barajada y se va rotando, en vez de sortear una
    # unidad cada vez. Sorteando, unas pocas unidades acaparan las citas por
    # puro azar y la tabla de cumplimiento por chofer sale con tres nombres:
    # rotando, el reparto se ve como una flota de verdad.
    rueda = [u for u in unidades]
    azar.shuffle(rueda)
    cursor = 0

    citas_creadas = avisos_creados = ordenes_creadas = asignaciones_creadas = 0
    folio = 1

    for i, (anio, mes) in enumerate(_meses(hoy)):
        dias = _dias_del_mes(anio, mes, hoy)
        if not dias:
            continue
        objetivo = FORMA_CUMPLIMIENTO[i % len(FORMA_CUMPLIMIENTO)]

        # Entre 48 y 72 citas al mes. La meta acordada con el area es de 5 a 7
        # preventivos por dia (RN-12), asi que este volumen es el que hace que
        # la grafica se parezca a lo que el taller deberia estar haciendo.
        cuantas = azar.randint(48, 72)
        for _ in range(cuantas):
            unidad = rueda[cursor % len(rueda)]
            cursor += 1
            dia = azar.choice(dias)

            sorteo = azar.random()
            if sorteo < objetivo:
                estado = "cumplida"
            elif sorteo < objetivo + (1 - objetivo) * 0.72:
                estado = "no_asistio"
            elif sorteo < objetivo + (1 - objetivo) * 0.88:
                estado = "confirmada"      # sin desenlace todavia
            else:
                estado = "cancelada"       # no cuenta como compromiso vivo

            cita = m.CitaTaller(
                taller_id=azar.choice(talleres),
                unidad_id=unidad.id,
                tipo_servicio_id=azar.choice(tipos) if tipos else None,
                fecha_cita=dia,
                duracion_estimada_dias=azar.choice([1, 1, 1, 2, 3]),
                estado=estado,
                veces_reprogramada=0,
                origen_agenda=MARCA_CITA,
                fecha_confirmacion_taller=_instante(dia, 8, 0),
            )
            db.add(cita)
            db.flush()               # hace falta el id para colgarle el aviso
            citas_creadas += 1

            if estado == "no_asistio":
                # La falta se atribuye por el AVISO, no por la cita: asi lo lee
                # cumplimiento_choferes() y asi lo escribe el job nocturno. Sin
                # el aviso, la falta existe pero no tiene responsable y la
                # pantalla de incumplimiento la ignora --que es justo el caso
                # que el codigo de estadisticas.py descarta a proposito.
                chofer = unidad.poseedor_chofer_id or unidad.titular_chofer_id
                db.add(m.AvisoIncumplimiento(
                    cita_id=cita.id,
                    unidad_id=unidad.id,
                    chofer_id=chofer,
                    # jornada|prestamo|titularidad son los tres que escribe
                    # jobs.py; aqui siempre es titularidad porque no se siembran
                    # jornadas ni prestamos que pudieran sostener otro origen.
                    fundamento_poseedor="titularidad",
                    fecha_generacion=dia + datetime.timedelta(days=1),
                    dias_atraso=azar.randint(1, 9),
                    estado=azar.choice(["abierto", "abierto", "atendido"]),
                    veces_recordado=azar.randint(0, 3),
                ))
                avisos_creados += 1

        # Ordenes de servicio cerradas: son las que dan el tiempo promedio de
        # reparacion. Las duraciones van sesgadas a lo corto porque asi es el
        # taller de verdad --la mayoria sale el mismo dia o al siguiente-- pero
        # con cola larga, que es lo que hace util al indicador: el promedio sin
        # las estancias largas no le dice nada a nadie.
        for _ in range(azar.randint(18, 30)):
            unidad = rueda[cursor % len(rueda)]
            cursor += 1
            salida = azar.choice(dias)
            dura = azar.choice([0, 0, 0, 1, 1, 1, 2, 2, 3, 4, 5, 7, 9, 12, 18])
            entrada = salida - datetime.timedelta(days=dura)
            taller = azar.choice(rueda_talleres)
            orden = m.OrdenServicio(
                folio="%sOS-%06d" % (PREFIJO_FOLIO, folio),
                unidad_id=unidad.id,
                taller_id=taller,
                tipo_servicio_id=azar.choice(tipos) if tipos else None,
                chofer_responsable_id=(unidad.poseedor_chofer_id
                                       or unidad.titular_chofer_id),
                # 8:30 de la manana en Tijuana entra, 16:45 sale. Las horas
                # importan: una orden de cero dias con entrada y salida a la
                # misma hora exacta se ve sembrada, y una que salga despues de
                # las 17:00 cruza a UTC del dia siguiente.
                fecha_entrada=_instante(entrada, 8, 30),
                fecha_salida=_instante(salida, 16, 45),
                estado="cerrada",
                tipo=azar.choice(["preventivo", "correctivo", "correctivo"]),
            )
            db.add(orden)
            db.flush()               # hace falta el id para colgarle el tecnico
            folio += 1
            ordenes_creadas += 1

            # QUIEN LA ATENDIO. Sin esto la orden existe pero no tiene mecanico,
            # y el historial por mecanico --que es lo que el gerente pidio- sale
            # con veinticinco de sus cuarenta y dos tecnicos en cero.
            #
            # Se toman del MISMO taller de la orden y rotando la lista en vez de
            # sorteando: sorteando, unos pocos acaparan por puro azar y la
            # pantalla saldria con tres nombres arriba y el resto en cero, que es
            # exactamente la lectura equivocada que esto viene a corregir.
            del_taller = tecnicos_de.get(taller) or []
            cuantos = min(len(del_taller), azar.choice([1, 1, 2, 2, 3]))
            for n in range(cuantos):
                tec = del_taller[(cursor + n) % len(del_taller)]
                db.add(m.AsignacionTecnico(
                    orden_servicio_id=orden.id,
                    tecnico_id=tec.id,
                    # La especialidad se copia del tecnico y no se inventa: es la
                    # que la pantalla muestra en la columna SISTEMA del detalle,
                    # y un carrocero apareciendo como "mecanico" en su propio
                    # renglon se lee como un error de captura.
                    especialidad=tec.especialidad,
                    orden_en_cola=n + 1,
                    # La orden esta CERRADA, asi que su trabajo esta terminado.
                    # Dejar una asignacion en_espera colgando de una orden
                    # cerrada seria un estado que no puede existir, y es el tipo
                    # de contradiccion que alguien encuentra en una demostracion.
                    estado="terminada",
                    fecha_asignacion=_instante(entrada, 9, 0),
                    fecha_inicio=_instante(entrada, 9, 30),
                    fecha_fin=_instante(salida, 16, 30),
                    trabajo_realizado=azar.choice(TRABAJOS_REALIZADOS),
                ))
                asignaciones_creadas += 1

    db.commit()
    return {"citas": citas_creadas, "avisos": avisos_creados,
            "ordenes": ordenes_creadas, "asignaciones": asignaciones_creadas,
            "desde": "%04d-%02d" % _meses(hoy)[0], "hasta": "%04d-%02d" % _meses(hoy)[-1]}


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Siembra o retira los datos de demostracion del tablero del gerente.")
    p.add_argument("--deshacer", action="store_true",
                   help="borra todo lo sembrado y deja la base como estaba")
    p.add_argument("--estado", action="store_true",
                   help="dice cuantas filas de demostracion hay ahora mismo")
    args = p.parse_args(argv)

    db = SessionLocal()
    try:
        if args.estado:
            c = _contar(db)
            print("Datos de demostracion en la base:")
            print("  citas        : %d" % c["citas"])
            print("  avisos       : %d" % c["avisos"])
            print("  ordenes      : %d" % c["ordenes"])
            print("  asignaciones : %d" % c["asignaciones"])
            if not any(c.values()):
                print("\nNada sembrado: el tablero esta mostrando datos reales.")
            return 0

        if args.deshacer:
            antes = deshacer(db)
            print("Retirado: %d citas, %d avisos, %d ordenes y %d asignaciones "
                  "de demostracion."
                  % (antes["citas"], antes["avisos"], antes["ordenes"],
                     antes["asignaciones"]))
            print("El tablero vuelve a mostrar solo datos reales.")
            return 0

        ya = _contar(db)
        if any(ya.values()):
            print("Ya hay datos de demostracion sembrados (%d citas, %d ordenes)."
                  % (ya["citas"], ya["ordenes"]))
            print("Corre primero:  python -m app.sembrar_demo --deshacer")
            return 1

        r = sembrar(db)
        print("Sembrado de %s a %s:" % (r["desde"], r["hasta"]))
        print("  %d citas" % r["citas"])
        print("  %d avisos de incumplimiento (uno por falta)" % r["avisos"])
        print("  %d ordenes de servicio cerradas" % r["ordenes"])
        print("  %d asignaciones de mecanico sobre esas ordenes" % r["asignaciones"])
        print("\nOJO: el tablero ya NO esta mostrando los numeros reales.")
        print("Para volver atras:  python -m app.sembrar_demo --deshacer")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
