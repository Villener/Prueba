# Análisis de `DETALLADO TALLER 2025.xlsx`

**Fecha:** 2026-08-20
**Fuente:** `~/Downloads/DETALLADO TALLER 2025.xlsx` — 8 hojas, entregado por el cliente
**Responde a:** la pregunta abierta #3 de `modelo-clases.md`, `modelo-er.md`,
`procesos.md` y `contexto-del-proyecto.md` — *«¿cuáles son los tipos de servicio
y cuánto duran?»*, el dato que bloquea la agenda automática.

---

## 0. Lo que hay que saber antes de leer el resto

**Este archivo no aparece en ninguno de los documentos del proyecto.** Los docs
solo mencionan `INFO CHOFERES 2026 ACTUAL.xlsx`, `vehiculos.csv` y `partes.csv`.
Este es el registro operativo real del taller de Álamos, con **casi 4 años de
historia** (2022-10-18 → 2026-08-01).

Trae tres cosas que el proyecto daba por perdidas:

1. **Duraciones reales medidas** — 869 reparaciones con fecha de ingreso y de
   cierre. `TipoServicio.duracionEstimadaDias` ya no tiene que ponerse a ojo.
2. **El tablero del gerente ya existe** — la hoja `RESUMEN` lleva 183 cortes
   diarios con los indicadores que la dirección realmente usa.
3. **El plano de Álamos, confirmado** — la hoja `CROQUIS` da exactamente los 31
   espacios operativos que `contexto-del-proyecto.md` §4 declaraba corregidos.

Y **una advertencia que cambia cómo hay que leer los números**: la duración que
se puede medir es **permanencia** (ingreso → reparado), no **ocupación de
espacio**. Incluye la espera por refacciones y por programación. Es exactamente
la distinción que `modelo-er.md` §5 anticipó con
`MEDICION_DURACION.dias_detenida_espera_refacciones`. Vuelvo a esto en §6.

---

## 1. Las 8 hojas

| Hoja | Filas | Qué es | Sirve para |
|---|---:|---|---|
| `RESUMEN` | 31 × 183 | Serie diaria de indicadores, 2022-10 → 2026-08 | CU-GER-01/02/06/09 |
| `PATIO` | 76 | El backlog **de hoy**: 65 unidades esperando | Estado inicial del sistema |
| `REPARADO` | 2,064 | Bitácora diaria de unidades reparadas, 2025-01 → 2026-08 | **Duraciones reales** |
| `IN-OUT` | 85 × 162 | Servicio del día: entra y sale, julio 2026 | El segundo flujo del taller (§3) |
| `ARRASTRES` | 82 | 51 arrastres de junio 2026, por montacarguista | Valida `Arrastre` y `TrasladoUnidad` |
| `Graficos` | 13 | Patio inicio/fin de mes y servicios por mes | — |
| `CROQUIS` | 18 × 41 | El plano físico de Álamos | `ZonaTaller` y `Espacio` |
| `Mecanicos` | 40 | Nómina de técnicos con número de empleado y puesto | `Tecnico` |

### Cómo está armada `REPARADO` — importa para el importador

No es una tabla plana. Es un **log append-only por día**: cada jornada se
insertó un bloque de las unidades que se terminaron ese día, y la fecha de
cierre está sola en la **columna 0 de la primera fila del bloque**. Hay 231
bloques.

```
r1500   [0] 2025-10-21              <- fecha de cierre del bloque
r1501       BG-306  MOTOR SUENA  ...  ingreso=45946
r1502       BG-446  MEDIA REPARACION  ingreso=45944
r1503   ...
```

Tres trampas que hay que resolver al importar:

- **La columna de INGRESO se recorre.** En las primeras ~80 filas está en la
  columna 9; de ahí en adelante en la 10. Hay que probar ambas.
- **La columna de «días» es una fórmula viva** (`HOY() − INGRESO`), no el valor
  congelado del día del cierre. **No sirve como duración** — recalcula cada vez
  que se abre el archivo. La duración hay que calcularla contra la fecha del
  bloque.
- **Las primeras 925 filas no tienen bloque de fecha**: son el volcado inicial
  del backlog de 2022–2024. No tienen fecha de cierre y hay que descartarlas del
  cálculo, no imputarles una.

Con eso salen **869 visitas con duración calculable** (17 negativas descartadas,
5 con la fecha mal capturada — un `2026-11-10` que es posterior a hoy y se
repite también en `IN-OUT`).

---

## 2. Catálogo de tipos de servicio, con duración medida

167 descripciones de falla distintas en texto libre, agrupadas en 16 familias.
La duración es la **mediana de las visitas de un solo trabajo** (`n_solo`) —
las visitas con varias fallas mezcladas inflan el número y se reportan aparte.

| tipo_servicio | crit | n_solo | mediana | p75 | p90 | n_total | IN-OUT/mes |
|---|:--:|---:|---:|---:|---:|---:|---:|
| SERVICIO_PREVENTIVO | 1 | 7 | **8** | 36 | 115 | 72 | **260** |
| FRENOS | 1 | 22 | **3** | 10 | 24 | 122 | 52 |
| CLUTCH | 2 | 35 | **3** | 14 | 45 | 93 | 35 |
| MOTOR | 1 | 224 | **22** | 46 | 116 | 304 | 37 |
| TRANSMISION | 2 | 39 | **11** | 56 | 222 | 65 | 20 |
| ELECTRICO | 1 | 70 | **8** | 25 | 79 | 145 | 99 |
| SUSPENSION_DIRECCION | 1 | 17 | **7** | 15 | 17 | 74 | 12 |
| LLANTAS | 1 | 5 | **10** | 17 | 20 | 17 | 19 |
| ENFRIAMIENTO | 1 | 19 | **5** | 18 | 37 | 50 | 16 |
| COMBUSTIBLE | 1 | 17 | **9** | 20 | 34 | 25 | 15 |
| AIRE_FRENO_NEUMATICO | 1 | 12 | **14** | 66 | 70 | 25 | 14 |
| CARROCERIA | 3 | 8 | **6** | 42 | 62 | 41 | 5 |
| ESCAPE_TURBO | 2 | 5 | **1** | 4 | 50 | 25 | 6 |
| HIDRAULICO | 2 | 4 | **4** | 6 | 6 | 9 | 1 |
| DIAGNOSTICO_REVISION | 2 | 12 | **42** | 112 | 258 | 18 | 5 |
| OTROS | 2 | 73 | **8** | 22 | 50 | 208 | 73 |

**Duración global: mediana 11 días, p75 28, p90 67.**

Tres lecturas que valen más que la tabla:

**MOTOR es el problema.** 304 de 869 visitas (35%) y mediana de 22 días — el
doble de la global, y p90 de 116 días. Es lo que llena el patio y lo que
dispara la alerta de 3 meses.

**`DIAGNOSTICO_REVISION` con mediana de 42 días es un hallazgo, no un tipo de
servicio.** Una unidad que entra «a revisión» se queda seis semanas. Eso no es
duración de trabajo: es una unidad estacionada esperando que alguien la vea.
`modelo-clases.md` §10 propone que la agenda opere en modo degradado con rangos
mientras haya pocas muestras — este es justo el caso donde un promedio miente.

**El p90 es enorme en casi todo.** `TRANSMISION` va de 11 días de mediana a 222
en el p90. La distribución tiene una cola larguísima, así que
`duracionRealPromedio` (que el modelo define como promedio) va a quedar muy por
encima de la realidad típica. **Recomiendo cambiar `duracionRealPromedio` por
mediana**, o guardar ambas — con esta forma de distribución, el promedio no
describe ningún caso real.

---

## 3. El taller tiene DOS flujos, y el modelo solo modela uno

Esto no está en ningún documento y cambia el diseño de la agenda.

| | `IN-OUT` | `PATIO` → `REPARADO` |
|---|---|---|
| Qué es | Servicio del día: entra y sale | Reparación con permanencia |
| Volumen | **~26 unidades por día** | ~45 cierres por mes |
| Duración | El mismo día | Mediana 11 días |
| Trabajo típico | NIVELES (244), AJUSTE FRENOS, LUCES, ROTACIÓN BATERÍAS | MOTOR, TRANSMISIÓN, CLUTCH |
| ¿Ocupa espacio del plano? | No de forma significativa | **Sí, y es lo que satura** |
| Registro | Unidad, falla, técnico, fecha | Ingreso, falla, estatus, partes, área |

**26 servicios al día contra 31 espacios operativos.** Si la agenda calcula
capacidad tratando los dos flujos igual, el taller siempre va a aparecer lleno
y `AgendaMantenimiento.capacidadProyectada()` no va a poder agendar nada.

Lo que esto implica:

1. `TipoServicio` necesita distinguir **servicio de paso** de **reparación con
   estancia**. Sugerencia: un campo `ocupa_espacio` (bool) o
   `duracion_estimada_dias = 0` para los de paso.
2. La capacidad de `IN-OUT` no se mide en espacios, se mide en **técnicos-día**.
   26 servicios/día los hacen ~6 técnicos activos.
3. `NIVELES` es el 38% de todo el trabajo del taller (244 de 645). Es el
   servicio preventivo real de Baja Gas y hoy no existe en ningún catálogo del
   proyecto.

Y un dato para dimensionar el tablero: en julio de 2026 trabajaron **33 técnicos
distintos**, pero tres personas hicieron el 65% del trabajo — Osmar Sánchez
(218), Mauricio Monreal (123) y Ángel Martínez (81).

---

## 4. Contradicciones y huecos contra los documentos

| # | Los docs dicen | El Excel dice | Qué hacer |
|---|---|---|---|
| 1 | **37 técnicos** (hoja TALLER) | **40** en la hoja `Mecanicos` | Reconciliar las dos hojas antes de sembrar |
| 2 | Especialidades: MECANICO, CARROCERO, ELECTRICISTA, LLANTERO | También **SOLDADOR** (1) y un `SUPERVISOR REPARTO` que no es técnico | Agregar `SOLDADOR` al enum; sacar al supervisor del catálogo |
| 3 | **2 montacarguistas** (`CHOFER DE GRUA`) | **3 personas hacen arrastres**: Rubén Espejo (20), José Espinoza (18) y **Ricardo Muñiz (13)** — que no está en la nómina de taller | Preguntar quién es Muñiz: ¿otra área, o externo? |
| 4 | `Unidad` se clasifica en reparto / pipa / utilitario | Aparecen **LECHERÍA, FORÁNEAS, AZUCENA, MINIZETAS, OPERACIONES** | `TipoUnidad` necesita estos valores |
| 5 | Los talleres son Álamos + 5 satélites | `RESUMEN` lleva **«Talleres Externos»** como categoría propia (3 unidades hoy) | El modelo no contempla taller de terceros |
| 6 | `EstadoOrden.ESPERA_REFACCIONES` | `RESUMEN` separa **«Pendientes por Compras»** de **«Refacciones chinas»** | Son dos esperas distintas: una de días, otra de meses |
| 7 | `Arrastre` nace de una avería | **24 de 51 arrastres son «TRASLADO»**, no rescate | Valida `TrasladoUnidad`, pero es el caso mayoritario, no el excepcional |
| 8 | Álamos: 31 espacios operativos + 45 de patio | **Confirmado exacto** por `CROQUIS` | Nada — el dato corregido era el bueno |

Sobre el punto 8, el desglose que da el croquis:

```
Fila superior   REPARTO 1-10 (10) · PIPAS 11-18 (8) · LLANTERA (1)
Fila inferior   ELECTRICOS 1-3 (3) · UTILITARIOS 4-6 (3) · REPARTO 7-12 (6)
                                    ------------------------------------
                                    31 espacios operativos

No operativos   PATIO 1-45 · FOSA · YONKE · OFICINA · AREA LAVADO
                ENTRADA · SALIDA · CONTENEDOR BASURA
```

Queda **un bloque sin etiqueta de 12 casillas** junto al área de lavado, que no
corresponde a ninguna zona documentada. Hay que preguntarlo.

---

## 5. `RESUMEN` — el tablero del gerente ya existe

183 cortes diarios de 2022-10-18 a 2026-08-01. Estos son los indicadores que la
dirección de Baja Gas **ya usa**, y el dashboard del proyecto debería
reproducirlos antes que inventar otros.

**Estado del backlog** (último corte, 2026-07-31):

| Indicador | Hoy |
|---|---:|
| Unidades por ingresar | 32 |
| Pendientes por compras | 16 |
| Proceso de reparación | 11 |
| Refacciones chinas | 1 |
| Talleres externos | 3 |

**Antigüedad — esto es RN-08 ya medido:**

| Rango | Unidades |
|---|---:|
| 1 a 30 días | 28 |
| 31 a 60 | 9 |
| 61 a 90 | 7 |
| **91 a 180** | **7** |
| **181 a 366** | **11** |

**18 unidades llevan más de 90 días.** La alerta de 3 meses (RN-08 / CU-GER-07)
no va a disparar «de vez en cuando»: el día que se encienda el sistema va a
generar 18 alertas de golpe. Hay que decidir qué pasa con el backlog histórico
antes de prender el job, o el gerente recibe 18 notificaciones el primer día y
apaga la función.

También hay desglose por área (REPARTO 27, UTILITARIAS 16, OPERACIONES 10,
PIPAS 8, LECHERÍA 1) y las series «Entrada por Salida» y «Servicios
realizados», que son CU-GER-09.

---

## 6. Lo que este archivo NO resuelve

Hay que decirlo claro para no vender el hallazgo por más de lo que es.

**No da ocupación de espacio, da permanencia.** Los 22 días de MOTOR incluyen
esperar el presupuesto, la autorización del gerente y la pieza. La agenda
necesita saber cuántos días la unidad **ocupa la bahía**, y eso no está en
ningún lado: el Excel no registra cuándo la unidad pasó del patio al espacio.
Con los datos que hay, la agenda puede planear **lead time** (prometerle al
chofer cuándo le devuelven la unidad) pero no **capacidad de bahías**.

Para cerrar ese hueco hacen falta dos fechas que hoy nadie captura: entrada al
espacio y salida del espacio. El modelo ya las tiene —
`OCUPACION_ESPACIO.fecha_entrada` / `fecha_salida` — así que el sistema las va a
generar solo en cuanto Pedro empiece a mover unidades en el plano. **La agenda
puede arrancar con permanencia y recalibrarse con ocupación**, que es
exactamente el mecanismo de `duracionAUsar()`.

**Solo cubre Álamos.** 868 de 869 visitas tienen `AREA = ALAMOS`. Los cinco
talleres satélite no llevan este registro, así que sus duraciones siguen sin
dato. Para ellos hay que arrancar con el estimado a ojo.

**Los tipos son texto libre, no un catálogo.** Las 16 familias las agrupé con
expresiones regulares; el 24% cayó en `OTROS`. Hay que ponerle la lista a Pedro
enfrente y que la corrija — los nombres tienen que ser suyos.

---

## 7. Calidad del dato: mejor de lo esperado

Dos cruces que salieron bien y que valen para el importador:

- **541 de 543 unidades** del Excel del taller existen en `vehiculos.csv`. Las
  dos que no son basura (una celda vacía y un número de serie de fecha). El
  identificador de unidad es una llave de unión limpia.
- **30 de 33 técnicos** de `IN-OUT` casan por apellido con la nómina de
  `Mecanicos`. Los tres que no son nombres de pila sueltos (`BALTAZAR`,
  `ANTONIO`) y una fecha mal pegada en la columna de técnico.

Defectos a manejar:

- 5 filas con fecha de cierre `2026-11-10`, posterior a hoy. Se repite en
  `IN-OUT`, así que es un error sistemático de captura, no ruido aleatorio.
- 2 fechas de bloque con el año sin capturar (`1900-01-10`, `1900-01-12`).
- 17 visitas con duración negativa (cierre anterior al ingreso).
- Marcas de agua en las hojas: filas `NO BORRAR`, `#N/A` de fórmulas rotas.

Todo junto es **menos del 3%** de los registros. Es un archivo llevado con
disciplina durante cuatro años.

---

## 8. Qué hacer con esto, en orden

### Ya implementado (2026-08-20)

- [x] **`TipoServicio` sembrado con las duraciones medidas.** 22 tipos: 16 de
      estancia con su mediana y su p90, y 6 de paso. Vive en
      `backend/app/seed.py` → `asegurar_tipos_servicio()`, idempotente y en
      función aparte de `sembrar()` — que se rinde si la base ya tiene datos,
      así que el catálogo no le habría llegado nunca a una base previa.
- [x] **La mediana manda sobre el promedio.** `TipoServicio` gana
      `duracion_mediana_dias` y `duracion_p90_dias`; `duracion_real_promedio`
      se conserva porque el diagrama de clases la nombra, pero ya no se usa
      para agendar. `duracion_a_usar()` redondea **hacia arriba**: reservar de
      menos suelta la bahía antes de que la unidad salga.
- [x] **Los dos flujos, separados.** Campo `ocupa_espacio`. Un servicio de paso
      devuelve 0 días y no consume bahía. Nace `rango_a_usar()` → `(típico,
      p90)` para proponer rangos en vez de fechas falsas.
- [x] **CU-AUT-06 conectado.** `jobs.recalibrar_duraciones_servicio()` recalcula
      con las órdenes que el sistema va cerrando. Exige **10 muestras propias**
      antes de pisar el dato del Excel: cambiar 224 observaciones por 3 sería un
      retroceso. `OrdenServicio` gana `tipo_servicio_id` para poder atribuir la
      medición — la mayoría de las estancias son correctivas y nunca tuvieron
      cita.

Probado en base nueva y en base previa: las 5 columnas nuevas las agrega
`asegurar_columnas()` sola. **84 rutas y 52 tablas, sin cambios.**

### Pendiente

1. **Llevarle a Pedro la tabla de §2** y que corrija los nombres de las 16
   familias. Es la pregunta que lleva abierta desde la v2.0 y ahora se puede
   hacer con datos enfrente en vez de en abstracto.
2. **Descontar la espera por refacciones.** Hoy `recalibrar_duraciones_servicio`
   mide puerta a puerta, así que arrastra el mismo sesgo que el Excel, solo que
   más chico. Hace falta historiar los cambios de estado de la orden
   (`MEDICION_DURACION.dias_detenida_espera_refacciones` en `modelo-er.md`).
3. **Decidir qué pasa con las 18 unidades de más de 90 días** antes de prender
   el job de RN-08.
4. **Preguntar los 4 puntos abiertos**: quién es Ricardo Muñiz, qué es el bloque
   de 12 casillas, qué son LECHERÍA y MINIZETAS como tipo de unidad, y si
   «talleres externos» debe modelarse.
5. **Endpoints y pantalla de la agenda.** El algoritmo ya está escrito y probado
   (`agenda_service.py` + CU-AUT-04/05, ver `agenda-mantenimiento.md` §9), pero
   corre solo: Víctor no puede verlo ni confirmar una cita. El diseño dice «el
   sistema propone, Víctor confirma» y hoy está la mitad de esa frase.

---

## Anexo — cómo reproducir el análisis

El cálculo central es este. La trampa está en no usar la columna de «días»:

```python
# REPARADO: la fecha de cierre vive sola en la columna 0 de cada bloque
cur = None
for r in filas:
    d = as_date(r[0])
    if d and d.year > 2000:          # descarta las dos fechas sin anio
        cur = d                      # nueva fecha de cierre
        continue
    ingreso = as_date(r[10]) or as_date(r[9])   # la columna se recorre
    if ingreso and cur:
        duracion = (cur - ingreso).days         # NO usar la columna de "dias"
```
