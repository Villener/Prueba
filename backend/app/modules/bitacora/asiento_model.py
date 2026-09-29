"""Libro de bitacora de mantenimiento de cada unidad (PROY-NOM-030-ASEA-2026).

QUE PIDE LA NORMA Y POR QUE ES UNA TABLA APARTE.
El numeral 7.1.10 permite llevar la bitacora "electronica mediante aplicaciones
de software" si cumple cinco cosas (inciso d): rastreabilidad, usuario y
contrasena, hora/fecha/usuario puestos SOLOS en cada registro, que no se pueda
borrar nada, y que se pueda consultar desde computadora o telefono. Y el inciso
a) dice que los registros no se alteran: una correccion es un registro NUEVO.

El reporte de mantenimiento no cumple eso por si solo: mientras esta abierto,
la captura de actividades y el mecanico SOBREESCRIBEN el texto del renglon, y lo
que decia antes se pierde. Por eso el reporte sigue siendo la hoja que se llena
--la vista del estado actual-- y la constancia vive aqui: cada cosa que se
registra en la hoja deja un ASIENTO que nadie puede editar ni borrar. Si el
texto de un sistema cambia, el asiento viejo sigue ahi y el nuevo lo apunta con
`corrige_a_id`. Asi se cumple 7.1.10 a) sin trabar la captura del dia.

NUMERADO POR UNIDAD. El inspector revisa "los libros de bitacora" de CADA unidad
(9.3.2.2 b) y verifica que cada registro corresponda a la unidad evaluada. El
`numero` es el folio de la pagina en ese libro: el asiento 1, 2, 3... de la
BG-354P. Un hueco en la numeracion se ve a simple vista.

ENCADENADO. Cada asiento guarda el hash del anterior del mismo libro y el suyo
propio. Si alguien edita un asiento directo en la base (fuera de la
aplicacion), la cadena deja de cuadrar desde ese asiento y la pantalla lo dice.
Los candados de la base (core/migraciones.py) impiden el UPDATE y el DELETE; el
hash es lo que permite DEMOSTRAR que no paso.
"""
from sqlalchemy import Column, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ...core.base_model import Base, _now
from ...core.tiempo import UTCDateTime

# Que se asento. El orden es el del ciclo de una estancia en el taller.
TIPOS_ASIENTO = [
    "apertura",      # la unidad entra: identificacion, revision de ingreso, programa
    "actividad",     # lo que hay que hacerle a un sistema / lo que se le hizo
    "reasignacion",  # cambia quien responde por un sistema (con motivo)
    "firma",         # constancia de una firma de tinta del pie del formato
    "evidencia",     # foto del servicio (RN-15)
    "comentarios",   # cambian los comentarios adicionales del formato
    "vinculo",       # a un formato abierto se le liga una orden o un programa
    "identificacion",  # cambian los datos de 7.1.10 c) (permiso, auxiliar...)
    "cierre",        # la unidad sale: resultado global y pendientes
    "correccion",    # corrige un asiento anterior sin tocarlo (7.1.10 a)
    "migracion",     # foto de un formato que existia antes del libro
    # Reservado para la fase del programa por elemento: un incumplimiento
    # encontrado fuera del taller que la norma manda anotar en esta misma
    # bitacora (7.2.3.4, 7.3.2.4, 7.3.1.2 a) 3, 7.2.1.2 c) 10). Existe desde
    # ya porque los asientos no se migran: son inmutables.
    "hallazgo",
]

# De donde viene lo asentado. Hoy todo sale del formato de mantenimiento; los
# demas valores son los que la norma nombra y llegan en la fase siguiente.
ORIGENES = ["formato_mantenimiento", "programa_preventivo", "revision_diaria",
            "ruta", "revision_anual_motriz", "prueba_recipiente"]

# 5.1.14: "Unidad de Distribucion" es el Auto-tanque y/o el Vehiculo de Reparto.
# Las utilitarias y los montacargas no estan obligados a llevar este libro (se
# les lleva igual, porque el taller los atiende, pero el aviso de datos
# faltantes de 7.1.10 c) no aplica). La correspondencia con los tipos de la
# flota es NUESTRA lectura --pipa = Auto-tanque, reparto = Vehiculo de Reparto
# de cilindros-- y esta pendiente de que la confirme el cliente.
TIPOS_UNIDAD_NOM030 = {"pipa": "Auto-tanque", "reparto": "Vehículo de Reparto"}

# 7.1.8 habla de "criterios de aceptacion o rechazo": el resultado de cada
# actividad es si quedo dentro del criterio o no. No hay tercer valor: "a
# medias" es una actividad que todavia no se da por realizada.
RESULTADOS = ["conforme", "no_conforme"]

# Quien registra cuando no hay una persona detras (el arranque del servidor).
REGISTRADO_POR_SISTEMA = "Sistema"


class AsientoBitacora(Base):
    __tablename__ = "bitacora_mantenimiento"
    __table_args__ = (UniqueConstraint("unidad_id", "numero",
                                       name="uq_asiento_por_unidad"),)

    id = Column(Integer, primary_key=True)
    unidad_id = Column(Integer, ForeignKey("unidad.id"), nullable=False, index=True)
    numero = Column(Integer, nullable=False)

    # El numero economico COMO ERA al registrarse. El inspector comprueba que
    # cada registro corresponda a la unidad evaluada (9.3.2.2 b), y el nombre
    # cambia: la limpieza del catalogo renombra BG-439 a BG439P.
    num_economico = Column(String(20), nullable=False)

    reporte_id = Column(Integer, ForeignKey("reporte_mantenimiento.id"), index=True)
    actividad_id = Column(Integer, ForeignKey("actividad_reporte.id"))
    # Para 7.1.9: el programa preventivo que esta visita cumple. El renglon del
    # programa por elemento (7.1.8) llega en la fase siguiente.
    programa_id = Column(Integer, ForeignKey("programa_mantenimiento.id"))
    tipo = Column(String(16), nullable=False)
    origen = Column(String(24), default="formato_mantenimiento", nullable=False)
    # Texto libre y no atado a los diez sistemas del formato: la fase siguiente
    # asienta elementos del recipiente y de la parte motriz que no estan ahi.
    sistema = Column(String(40))

    # Lo que se lee en el libro, en una frase. Los valores completos del momento
    # van en `datos`; esto es para que el inspector no tenga que abrir un JSON.
    descripcion = Column(Text, nullable=False)

    # Los cuatro datos que 7.1.10 pide en cada registro: la fecha en que se
    # llevo a cabo (inicio/termino), el resultado, las acciones requeridas y el
    # personal responsable de ejecutarla.
    resultado = Column(String(12))
    acciones_requeridas = Column(Text)
    responsable_nombre = Column(String(160))
    responsable_tecnico_id = Column(Integer, ForeignKey("tecnico.id"))
    # FECHAS de calendario (7.1.9 habla de fechas). La hora exacta del
    # registro es `registrado_en`; la de entrada y salida del taller va en
    # `datos` de la apertura y del cierre.
    fecha_inicio = Column(Date)
    fecha_termino = Column(Date)

    datos = Column(Text)             # JSON: foto de los valores en ese momento
    corrige_a_id = Column(Integer, ForeignKey("bitacora_mantenimiento.id"))
    motivo = Column(Text)

    # 7.1.10 d) 3: hora, fecha y usuario los pone la aplicacion, no quien
    # captura. El nombre se copia: si manana se corrige un apellido en la
    # cuenta, el libro tiene que seguir diciendo quien firmo ese dia.
    registrado_en = Column(UTCDateTime, default=_now, nullable=False)
    registrado_por_id = Column(Integer, ForeignKey("usuario.id"))
    registrado_por_nombre = Column(String(160), nullable=False)

    hash_anterior = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False)

    unidad = relationship("Unidad")
    reporte = relationship("ReporteMantenimiento")
    corrige_a = relationship("AsientoBitacora", remote_side=[id])
