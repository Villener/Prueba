# Diseño de la agenda automática de mantenimiento

**Versión:** 1.0 · **Fecha:** 2026-08-15
**Resuelve:** las dudas sobre P3 y P4 en [procesos.md](procesos.md) — cuándo y cómo se recalcula
la agenda cuando el taller está lleno.
**Dueño del proceso:** Víctor (Programador de mantenimiento).

---

## 1. El error que hay que evitar antes de programar nada

La idea de "si el taller está lleno, se posterga un día más" es correcta como intuición, pero si
se implementa tal cual produce un sistema en el que **nadie confía**, por tres razones:

1. Si la fecha se mueve sola, el chofer que ya venía en camino se encuentra con que su cita
   cambió. A la tercera vez deja de mirar la app.
2. Si mover la cita también mueve la fecha límite, el mantenimiento se puede posponer para
   siempre y el sistema pierde su razón de existir.
3. "El taller está lleno" no es una sola cosa: el taller puede estar lleno **de pipas** y tener
   espacios de reparto libres.

La solución a los tres problemas es la misma: **separar dos fechas que hoy están confundidas.**

| Concepto | Campo | ¿Se mueve? | Quién manda |
|---|---|---|---|
| **Fecha límite de mantenimiento** | `PROGRAMA_MANTENIMIENTO.fecha_limite` | **Nunca** | El plan (días / km). Es el compromiso técnico. |
| **Cita de taller** | `CITA_TALLER.fecha_cita` | Sí | La capacidad real del taller |

Con esa separación, la regla de la penalización se vuelve trivial y justa:

> **El chofer solo incumple si faltó a una cita confirmada.**
> Si el taller no pudo darle cita antes de la fecha límite, **el incumplimiento es del taller**, no
> del chofer, y el sistema lo debe reportar como tal.

Eso resuelve el problema que señalé en P3/P4: hoy el sistema castigaría al chofer por un problema
de capacidad que no es suyo.

---

## 2. Entidades nuevas

```mermaid
erDiagram
    TIPO_SERVICIO ||--o{ CITA_TALLER : "define duracion y espacio"
    PROGRAMA_MANTENIMIENTO ||--o| CITA_TALLER : "se agenda como"
    SOLICITUD_INGRESO ||--o| CITA_TALLER : "se agenda como"
    TALLER ||--o{ CITA_TALLER : "recibe"
    UNIDAD ||--o{ CITA_TALLER : "es citada en"
    CITA_TALLER ||--o{ REPROGRAMACION : "acumula"
    ORDEN_COMPRA ||--o{ ORDEN_SERVICIO : "libera espacio al llegar"

    TIPO_SERVICIO {
        int id PK
        string nombre "afinacion|aceite|frenos|llantas|correctivo_mayor|carroceria"
        int duracion_estimada_dias
        int tipo_espacio_requerido FK
        int criticidad "1=seguridad 2=preventivo 3=estetico"
        bool requiere_fosa
    }
    CITA_TALLER {
        int id PK
        int taller_id FK
        int unidad_id FK
        int programa_mantenimiento_id FK
        int solicitud_id FK
        int tipo_servicio_id FK
        date fecha_cita
        date fecha_limite_origen "copiada del programa - NO se mueve"
        int duracion_estimada_dias
        string estado "propuesta|confirmada|reprogramada|cumplida|no_asistio|cancelada"
        int veces_reprogramada
        int score_prioridad "calculado, se guarda para poder auditar el orden"
        int agendada_por_usuario_id FK
        datetime fecha_confirmacion
    }
    REPROGRAMACION {
        int id PK
        int cita_id FK
        date fecha_anterior
        date fecha_nueva
        string motivo "sin_espacio|unidad_atorada|urgencia_desplaza|solicitud_chofer"
        bool automatica
        bool aviso_enviado
        int usuario_id FK
        datetime fecha
    }
```

Y **dos campos nuevos** en entidades que ya existen:

| Entidad | Campo | Para qué |
|---|---|---|
| `ORDEN_SERVICIO` | `fecha_salida_estimada` | Sin esto no se puede proyectar cuándo se libera un espacio |
| `UNIDAD` | `prioridad_operativa` | Desempate: una pipa parada cuesta más que un utilitario parado |

---

## 3. Cuándo se recalcula la agenda

Tu propuesta —recalcular cuando el administrador saca un vehículo— es **correcta pero
incompleta**. Ese es el evento en que aparece capacidad nueva, pero la capacidad también
*desaparece*, y las necesidades también cambian. Son **cinco disparadores**:

| # | Evento | Qué provoca | Quién lo genera |
|---|---|---|---|
| **D1** | **Se libera un espacio** (sale un vehículo) | Aparece capacidad → jala hacia adelante las citas pendientes | Pedro / Pablo |
| **D2** | **Se ocupa un espacio no previsto** (llega un arrastre, una urgencia) | Se consume capacidad → empuja hacia atrás las citas propuestas | Pedro / Pablo |
| **D3** | **Cambia la fecha estimada de salida** de una unidad en reparación | Es el disparador que **más se olvida**: una unidad atorada esperando piezas bloquea su espacio y recorre toda la agenda | Erick (al registrar la ETA de las piezas) |
| **D4** | **Entra una necesidad nueva** (vence una ventana, se acepta una solicitud) | Se inserta en la cola según su prioridad | Víctor / el job diario |
| **D5** | **Job diario al abrir el taller** | Red de seguridad: recalcula todo y detecta citas que ya no caben antes de su fecha límite | Programador de tareas |

**D3 es el importante.** Aquí se conecta con P7: cuando Erick registra que las piezas llegan el
día 20, el sistema ya sabe que ese espacio se libera alrededor del 21 y puede agendar sobre esa
fecha. Sin ese dato, la agenda planea a ciegas.

**Mientras una unidad esté en `espera_refacciones` sin ETA de piezas, su espacio se considera
ocupado por tiempo indefinido.** Es pesimista a propósito: es preferible agendar de menos que
citar a un chofer para un espacio que no existirá.

---

## 4. Cómo se calcula

### 4.1 Capacidad — por tipo de espacio, nunca global

```
capacidad_libre(dia D, tipo T) =
      espacios_activos(T)
    − ocupados_hoy(T) que aún no tienen fecha_salida_estimada ≤ D
    − citas_confirmadas(T) que se traslapan con D
```

El traslape importa porque un servicio dura varios días: una afinación de 2 días que empieza el
lunes ocupa lunes y martes.

**Las zonas del plano que no cuentan** (yonke, área de lavado, oficina, contenedor de basura) ya
están marcadas con `ZONA_TALLER.cuenta_para_ocupacion = false`. Sin esa bandera la agenda creería
que hay 45 espacios más de los que hay.

### 4.2 El algoritmo

Es una **cola con prioridad** asignada a capacidad día por día. No hace falta nada más sofisticado
y conviene que no lo sea: un algoritmo que nadie entiende es un algoritmo en el que nadie confía.

```
para cada dia D desde hoy hasta hoy + 30:
    para cada tipo de espacio T:
        libres = capacidad_libre(D, T)
        cola   = citas pendientes de tipo T, ordenadas por prioridad
        mientras libres > 0 y cola no vacia:
            cita = cola.siguiente()
            si cita.duracion cabe antes de que el espacio se vuelva a necesitar:
                asignar cita a D
                libres -= 1
    las citas que no cupieron pasan al dia siguiente
```

**Horizonte de 30 días.** Más allá de eso el sistema no propone fecha: muestra "sin fecha
disponible" y **alerta a Víctor y al gerente**, porque eso ya no es un problema de agenda, es un
problema de capacidad del taller. Planear a 6 meses con datos que cambian a diario es inventar
certidumbre.

### 4.3 La prioridad de la cola

Ordenamiento **lexicográfico**, no una fórmula con pesos. Se compara el primer criterio; si hay
empate, el segundo; y así:

| # | Criterio | Orden | Por qué |
|---|---|---|---|
| 1 | **Criticidad del servicio** | seguridad → preventivo → estético | Frenos antes que hojalatería, siempre |
| 2 | **Días respecto a la fecha límite** | ascendente (los negativos primero) | Lo ya vencido va primero |
| 3 | **Veces reprogramada** | descendente | **Anti-inanición**, ver abajo |
| 4 | **Prioridad operativa de la unidad** | pipa → reparto → utilitario | Una pipa parada cuesta más |
| 5 | **Fecha de solicitud** | ascendente | FIFO como último desempate |

**Por qué lexicográfico y no una suma ponderada.** Con pesos (`0.4×criticidad + 0.3×atraso + …`)
tendrías que justificar de dónde salió cada número, y cuando alguien reclame por qué su unidad
quedó atrás no vas a poder explicarlo. Con orden lexicográfico la respuesta siempre es una frase:
*"tu unidad quedó después porque la otra tiene un servicio de seguridad"*. Se guarda
`score_prioridad` para poder auditar el orden después.

**El criterio 3 no es opcional.** Sin él, una unidad de baja prioridad que se aplaza una vez se
aplaza para siempre: cada día llegan casos más urgentes y nunca alcanza turno. Es el problema de
inanición clásico de las colas por prioridad. Contarle las reprogramaciones y usarlas para subirla
es lo que garantiza que toda unidad acabe entrando.

---

## 5. Estabilidad: qué se puede mover y qué no

Esta es la regla que decide si el sistema se usa o se abandona.

| Estado de la cita | ¿El recálculo la mueve? |
|---|---|
| `propuesta` (aún no confirmada) | **Sí**, libremente |
| `confirmada` con más de 48 h de anticipación | **Sí**, pero **notificando** al chofer y al supervisor |
| `confirmada` a menos de 48 h | **No automáticamente.** Requiere que Víctor lo autorice y avise |
| `cumplida`, `no_asistio` | Nunca |

**El sistema propone, Víctor confirma.** El recálculo automático genera citas en estado
`propuesta`; Víctor las revisa y confirma. A partir de ahí la cita es un compromiso con el chofer
y ya no se mueve sola.

Sí hay un caso de movimiento automático de una cita confirmada: cuando entra una **urgencia de
seguridad** que desplaza a un preventivo. En ese caso se registra en `REPROGRAMACION` con motivo
`urgencia_desplaza`, se avisa al chofer y al supervisor, y **la cita desplazada sube al tope de la
cola** por el criterio 3.

---

## 6. Cómo queda la penalización con esto

Con el diseño que propusiste (avisar al gerente y al administrador, ellos hablan en persona, y al
final marcan como atendido), el flujo queda así:

| Situación | ¿Hay incumplimiento? | Qué hace el sistema |
|---|---|---|
| El sistema no encontró cita antes de la fecha límite | **No es del chofer** | Alerta a Víctor y al gerente: **problema de capacidad del taller** |
| Se le dio cita y el chofer no se presentó | **Sí** | Avisa a gerente y a Erick para que hablen con él |
| El chofer canceló su cita sin reagendar | **Sí** | Igual que el anterior |
| Se reprogramó por decisión del taller | **No** | Solo registra; el reloj de la fecha límite sigue corriendo pero no genera falta |

Nota importante: la alerta se emite contra el **poseedor** de la unidad en la fecha de la cita, no
contra el titular. Si la unidad estaba prestada, el que faltó fue el receptor.

---

## 7. Lo que puede salir mal

| Riesgo | Mitigación |
|---|---|
| La agenda se recalcula tantas veces que las fechas bailan | Solo se mueven las citas `propuesta`; las confirmadas requieren aviso |
| Todo se marca como "urgente" y la prioridad deja de servir | La criticidad la define el `TIPO_SERVICIO` del catálogo, no quien captura |
| Las duraciones estimadas están mal y la agenda se desfasa | Comparar `duracion_estimada` contra la real y ajustar el catálogo cada mes |
| Un espacio bloqueado por reparación de infraestructura | `ESPACIO.estado = bloqueado` ya lo contempla; sale del cálculo |
| El taller nunca alcanza a cubrir la demanda | El horizonte de 30 días lo hace visible como alerta de capacidad, no como retrasos individuales |

---

## 8. Lo que falta definir

1. **¿Cuántos días dura cada tipo de servicio?** Sin el catálogo `TIPO_SERVICIO` cargado con
   duraciones reales, la agenda no puede calcular nada. Es el primer dato que hay que levantar
   con Pedro.
2. **¿Cuál es la prioridad operativa entre unidades?** Propuse pipa > reparto > utilitario. Hay
   que confirmarlo con el gerente.
3. **¿Cuánta anticipación mínima merece un chofer?** Propuse 48 h. Puede ser 24 h si la operación
   es más flexible.
4. **¿Quién cubre a Víctor cuando no está?** Pablo cubre a Pedro, pero la agenda no tiene
   suplente asignado.
5. **¿Se puede agendar en sábado?** El cálculo de capacidad necesita saber qué días opera el
   taller.

---

## 9. Estado de la implementación — 2026-08-20

**Implementado** en `backend/app/modules/mantenimiento/agenda_service.py` y en los jobs
`recalcular_agenda()` (CU-AUT-04, disparador D5) y `avisar_citas_proximas()` (CU-AUT-05).

| Del diseño | Estado |
|---|---|
| Las dos fechas separadas, `fecha_limite` inmutable | Hecho, y probado: el test falla si `fecha_limite_origen` deja de coincidir con el programa |
| Capacidad por tipo de espacio, nunca global | Hecho — con una corrección, ver abajo |
| Zonas con `cuenta_para_ocupacion = false` fuera del cálculo | Hecho. Álamos: **79 espacios en el plano, 31 que cuentan** |
| Cola con prioridad lexicográfica, 5 criterios | Hecho, con `score_prioridad` guardado para auditar |
| Anti-inanición (criterio 3) | Hecho |
| Horizonte de 30 días y `detectar_sin_cupo()` | Hecho, y avisa a gerencia como **problema de capacidad**, no de chofer |
| Estabilidad: `propuesta` libre, confirmada >48 h con aviso, <48 h intocable | Hecho en `_movible()` |
| Sábado sí, domingo no, por taller | Hecho vía `Taller.opera_sabado` |
| D3: proyectar cuándo se libera un espacio | `OrdenServicio.fecha_salida_estimada`. Sin ETA, el espacio se considera ocupado **indefinidamente** |

### Lo que el diseño no había previsto: los espacios compartidos

El §4.1 propone `capacidad = espacios(T) − ocupados − citas(T)`. Con el plano real de Álamos eso
da un número **equivocado en las dos direcciones**, porque hay dos clases de espacio:

- **Dedicados** — los 8 de PIPAS solo admiten pipas.
- **Genéricos** — ELECTRICOS y LLANTERA no declaran tipo, así que sirven para cualquiera.

Los genéricos son un pozo común. Contar solo las citas del mismo tipo **sobreestima** la capacidad
(ignora que un reparto ya se llevó un genérico); contarlas todas la **subestima** (un reparto que
cabe en sus propios espacios no le quita nada a una pipa). En la primera versión las dos cuentas
no coincidían y el taller quedaba con 2 de 12 lugares desperdiciados por día.

Se resuelve en dos pasos, que es como lo entendería Pedro:

> **1.** Cada tipo agota primero **sus** espacios dedicados.
> **2.** Lo que le sobre a cada tipo pelea por el **pozo común**.

Con eso el reparto satura exacto. Probado con 40 pipas contra 12 lugares y un servicio de 5 días:

```
2026-08-20 Thu  12      bloques de 5 dias habiles,
2026-08-26 Wed  12      sin domingos, sin exceder
2026-09-01 Tue  12      la capacidad, sin perder
2026-09-07 Mon   4      ningun programa
```

### Preguntas que la implementación ya no bloquea, pero siguen abiertas

La #1 quedó resuelta: el catálogo `TipoServicio` está cargado con duraciones **medidas**
(ver [analisis-detallado-taller.md](analisis-detallado-taller.md)). Siguen abiertas la #2
(prioridad operativa: sembrada como pipa > reparto > utilitario, **a confirmar con el gerente**),
la #3, la #4 y la #5 (`opera_sabado` está en `true` para todos los talleres, **a confirmar**).

### Endpoints y pantallas — 2026-08-24

Ya está la frase completa: **el sistema propone, Víctor confirma, el chofer acepta.**

| Endpoint | Caso de uso | Quién |
|---|---|---|
| `GET /api/agenda/citas` | CU-ADM-14 | Víctor · Gerente |
| `POST /api/agenda/recalcular` | CU-AUT-04 (D1 y D3 a mano) | Víctor |
| `POST /api/agenda/citas/{id}/confirmar` | CU-ADM-14 | Víctor |
| `POST /api/agenda/citas/{id}/reprogramar` | CU-ADM-15 | Víctor |
| `POST /api/agenda/citas/{id}/cancelar` | — | Víctor |
| `GET /api/agenda/sin-cupo` | CU-ADM-16 | Víctor · Gerente |
| `GET /api/agenda/capacidad` | — | Víctor · Gerente |
| `GET /api/chofer/citas` | CU-CHO-07 | Chofer |
| `POST /api/chofer/citas/{id}/confirmar` | CU-CHO-07 | Chofer |

**84 → 93 rutas.** Pantallas: `AgendaPage.jsx` (pestaña Agenda del administrador) y el bloque
«Tus citas de taller» en la pestaña Taller del chofer.

Tres decisiones de la pantalla que vale la pena defender:

- **La lista va en el orden de la cola, no por fecha.** Es el mismo `score_prioridad` con el que
  el algoritmo decidió, así que Víctor puede ver *por qué* una unidad quedó antes que otra. Si se
  ordenara por fecha tendría que confiar a ciegas.
- **La holgura se muestra siempre**, al lado de la cita: días entre la cita y el límite técnico.
  En rojo cuando es negativa. Es el dato que distingue «la agenda está cumpliendo» de «el taller
  ya no da abasto», y sin él las dos se ven igual.
- **Al chofer no se le enseña `estado`.** Para el sistema `confirmada` significa que confirmó el
  *taller*, pero al chofer le leía como «ya quedó» justo al lado de un botón que le pedía
  confirmar. Ve «Pendiente» o «✓ Ya confirmaste», que es lo que le toca a él.

### Dos defectos que aparecieron al probarlo corriendo

**1. La fecha se mostraba un día antes.** `new Date('2026-08-24')` se interpreta como medianoche
UTC y al pintarla en Tijuana retrocedía al 23. Afectaba a toda fecha sin hora — `fecha_cita`,
`fecha_limite`, `fecha_fin_prevista` del préstamo, la ETA de las piezas — no solo a la agenda.
Corregido en `core/api.js`: una fecha de calendario se formatea **sin** convertir de zona, porque
el 24 de agosto es el 24 de agosto en todas partes. La conversión se queda para los instantes.

**2. Los planes viejos quedaron sin tipo de servicio.** `asegurar_columnas` agrega la columna pero
no la rellena, así que en una base previa la agenda caía al valor por omisión —un día, criticidad
media— justo la adivinanza que el catálogo medido vino a eliminar. Se rellena en
`asegurar_tipos_servicio()`, y `recalcular()` repara además las citas que ya existían.

### El movimiento manual también respeta la capacidad — 2026-08-24

Al construir el modal apareció un hueco serio: **el algoritmo automático cuida la capacidad con
detalle y un clic de Víctor se la saltaba entera.** Comprobado con el taller lleno: mover una cita
a un día con **cero espacios libres** devolvía 200 y la cita quedaba ahí. Una agenda que se respeta
a sí misma pero cede a cualquier clic no es una agenda, es una sugerencia.

Se resolvió con el mismo patrón que la regla de las 48 h — **se rechaza por omisión, se puede
forzar, y queda registrado que se forzó**:

| | |
|---|---|
| Sin `forzar` | `409` con los días que no caben y `puede_forzar: true` |
| Con `forzar: true` | Se acepta, `Reprogramacion.requirio_autorizacion = true` |
| Bitácora | `cita_reprogramada_con_sobrecupo`, con la fecha anterior y la nueva |

Se revisa el **tramo completo**, no solo el primer día: un servicio de tres días que arranca el
lunes también necesita martes y miércoles. Y `capacidad_libre()` acepta `excluir_cita_id`, porque
una cita no debe estorbarse a sí misma al moverse.

**El calendario de cupo** ya está en el modal de mover: 30 casillas, cada una con los espacios que
quedan **para ese tipo de unidad** —la capacidad nunca es global— y el domingo rayado igual que las
zonas que no cuentan en el plano. Antes Víctor elegía la fecha a ciegas.

Dos arreglos generales que salieron de aquí:

- **`core/api.js` perdía los detalles estructurados.** Solo entendía `detail` como texto o lista,
  así que un `409` con objeto se mostraba como «Error 409» y el usuario se quedaba sin saber qué
  hacer. Ahora el objeto viaja en `err.datos` y el mensaje sale del propio servidor.
- El calendario **no pide capacidad si falta el taller o el tipo**, en vez de mandar un 422 y
  dejar la caja vacía sin explicación.

### Lo que sigue faltando

Los cuatro perfiles de administrador siguen compartiendo el rol técnico `administrador`, así que
hoy **Erick podría entrar a la agenda de Víctor**. Es justo lo que `casos-de-uso.md` §2 dice que no
debe pasar —*«Víctor no autoriza órdenes de compra y Erick no mueve vehículos de espacio»*— y es
la separación de funciones que un sistema de control existe para hacer visible. La frontera del
módulo ya está donde va a ir; falta separar los roles en `ROLES` y en `USUARIO_ROL`.
