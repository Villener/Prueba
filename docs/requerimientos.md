# Especificación de Requerimientos — Sistema de Gestión de Flota y Taller (Baja Gas)

**Versión:** 1.3 · **Fecha:** 2026-09-15 · **Autor:** Ingeniería de Requerimientos

> **v1.3 (2026-09-15).** Entran **RN-17** y **RN-18**, las dos del módulo **propuesto** de
> auditorías de campo a reparto: la evidencia no se edita y el sello lo pone el servidor (RN-17),
> y no se guarda una auditoría sin GPS ni con precisión peor que el umbral (RN-18). Van marcadas
> como propuestas porque el módulo **no está aprobado**: depende de si la evidencia puede vivir en
> web, donde la galería no se puede bloquear. Análisis en `auditorias-de-campo.md`, casos de uso
> en §3.11 de `casos-de-uso.md`, modelo de datos en el Paquete I de `modelo-er-mermaid.md`.

> **v1.2 (2026-09-14).** Incorpora las diez notas de la junta con el cliente: renombre de
> cuadrilla a **plantilla**/**flotilla**, el gerente es **Luis Tiscareño**, meta de **5 a 7
> preventivos por día** (RN-12), **amonestación** al chofer que incumple (RN-14), **evidencia
> fotográfica** obligatoria y ligera (RN-15, RF-GEN-15), **choque y avería** como procedimientos
> distintos (RN-16), el **perito Edgar** como actor interno, y el tablero del gerente con
> **estadísticas por día/mes/año y gráficos** (RF-GER-14 a 18). Trazabilidad nota por nota en
> `junta-2026-09-14.md`. **Nada de esto está implementado todavía.**

---

## 1. Propósito y alcance

Sistema web/móvil para administrar el ciclo de vida operativo de las unidades de reparto de gas:
asignación de vehículos a choferes, préstamos temporales, cumplimiento de mantenimiento
preventivo, solicitudes e ingreso a taller, arrastres (grúa), presupuestos de
reparación y tablero directivo.

**Dentro del alcance:** los **5 módulos por rol** (Chofer, Supervisor, Administrador,
Chofer de grúa, Gerente), geolocalización en tiempo real, flujo de presupuestos y órdenes de
compra, indicadores de gerencia.

> **Cambio de alcance (2026-08-13).** El cliente confirmó que **los mecánicos no usarán la
> aplicación**. El módulo Mecánico se elimina. Su trabajo no desaparece del sistema: el
> **administrador de taller captura** el diagnóstico, el presupuesto y el avance de la reparación
> a partir de lo que el mecánico le entrega en papel o de viva voz. Los mecánicos siguen
> existiendo como **catálogo asignable** a la cola de trabajo, pero sin cuenta de usuario.
> Consecuencias detalladas en §5.6.

**Fuera del alcance (v1):** facturación de ventas de gas, nómina/pago de comisiones,
integración contable, telemetría del medidor de gas.

---

## 2. Actores

| Actor | Descripción | Interés principal |
|---|---|---|
| Chofer | Opera y es responsable técnico de una unidad | Vender sin perder tiempo; reportar fallas |
| Supervisor | Tiene una **plantilla** de choferes y la **flotilla** que esa plantilla trae | Visibilidad de quién conduce qué y dónde |
| Administrador de taller | Gestiona espacios, cuadrillas técnicas y compras | Maximizar rotación de bahías |
| Chofer de grúa | Realiza arrastres de unidades varadas | Recibir y cerrar arrastres |
| Mecánico *(trabajador del negocio, **no usuario**)* | Diagnostica, presupuesta y repara. No opera el sistema: entrega su trabajo al administrador, que lo captura | Piezas y autorización a tiempo |
| Gerente — **Luis Tiscareño** | Dirección | Cumplimiento de mantenimiento, ocupación, costos |
| Almacén *(actor secundario)* | Surte piezas | Órdenes de compra autorizadas |
| **Perito — Edgar** *(actor **interno**)* | Levanta el peritaje de choques y siniestros en vialidad. Es del sindicato, pero **trabaja para Baja Gas**: tiene cuenta propia y lo que registra queda a su nombre | Dejar el peritaje levantado para que la unidad se pueda mover |
| Aseguradora *(actor externo)* | Atiende el siniestro después del peritaje | Parte de accidente y deducible |

> **Corrección (2026-09-14).** «Cuadrilla» era una sola palabra para dos cosas. El cliente usa
> **plantilla** para el grupo de **choferes** y **flotilla** para el grupo de **unidades**. No
> coinciden: 55 choferes de plantilla no son 55 unidades de flotilla, porque hay préstamos,
> unidades en taller y choferes sin unidad. La **cuadrilla técnica** del administrador —mecánicos,
> carroceros, electricistas— no es ninguna de las dos y se queda sin nombre nuevo: pregunta
> abierta #11.
>
> Y el perito dejó de ser un actor externo: **Edgar es de la casa**. Detalle en
> `junta-2026-09-14.md`.

---

## 3. Glosario

- **Unidad:** vehículo de reparto.
- **Titular:** chofer al que está asignada permanentemente la unidad.
- **Poseedor:** chofer que tiene la unidad ahora (titular o quien la recibió en préstamo).
- **Préstamo:** cesión temporal de la unidad con transferencia de responsabilidad.
- **Espacio / bahía:** posición física del taller donde entra una unidad.
- **Arrastre:** traslado de una unidad varada mediante grúa.
- **Ventana de mantenimiento:** rango de fecha/km en el que la unidad debe ingresar a taller.
- **Unidad parada:** unidad inmovilizada en taller sin avance de reparación.
- **Plantilla:** grupo de **choferes** a cargo de un supervisor. Antes se decía «cuadrilla».
- **Flotilla:** grupo de **unidades** que trae esa plantilla. No es del mismo tamaño que la
  plantilla ni cambia con ella.
- **Amonestación:** acto administrativo documentado contra el chofer que faltó a una cita
  **confirmada**. Va a su expediente; no es un descuento (RN-14).
- **Avería / quedarse tirado:** la unidad falla sola y queda inmovilizada. Se atiende con grúa o
  mecánico.
- **Choque / siniestro:** hay impacto, casi siempre con un tercero. **Procedimiento distinto** al
  de la avería: exige peritaje antes de mover la unidad y termina en carrocería, no en mecánica
  (RN-16).
- **Evidencia del preventivo:** fotos que prueban que el servicio se hizo, comprimidas en el
  teléfono antes de subirse (RN-15).

---

## 4. Reglas de negocio

| ID | Regla | Prioridad |
|---|---|---|
| RN-01 | La responsabilidad técnica de la unidad recae **siempre en el poseedor actual**, no en el titular. Durante un préstamo activo, todas las obligaciones y penalizaciones aplican al chofer que la recibió. | Must |
| RN-02 | Una unidad tiene **un solo poseedor activo** a la vez. No se puede prestar una unidad que ya está prestada ni una que está en taller. | Must |
| RN-03 | El préstamo es **temporal y con fecha de fin**; al vencer, la responsabilidad vuelve automáticamente al titular salvo prórroga. | Must |
| RN-04 | Si una unidad se vara **en vialidad pública**, el orden obligatorio de aviso es: **1) peritos, 2) mecánico/chofer de grúa**. El sistema no permite solicitar apoyo mecánico sin registrar antes el reporte a peritos (o marcarlo como no aplica con justificación). **Desde 2026-09-14:** el perito es **interno** (Edgar), así que el aviso sale del propio sistema y el peritaje se levanta dentro, no se teclea después. | Must |
| RN-05 | Si el poseedor no ingresa la unidad al taller dentro de la ventana de mantenimiento, se genera una **penalización** registrada a su nombre. La forma concreta de esa penalización es la **amonestación** de RN-14. | Must |
| RN-06 | No se acepta un ingreso a taller si **no hay espacio disponible**; la solicitud queda en cola o se rechaza con motivo. | Must |
| RN-07 | Flujo de presupuesto: **Mecánico (papel) → Administrador (captura) → Gerente**. Solo el Gerente aprueba o rechaza. Ninguna pieza se compra sin presupuesto aprobado. El presupuesto entra al sistema por captura del administrador, no por el mecánico. | Must |
| RN-11 | Todo dato originado por un mecánico (diagnóstico, presupuesto, avance) queda registrado con **dos responsables**: el técnico que lo elaboró y el administrador que lo capturó. | Must |
| RN-08 | Una unidad con **más de 3 meses** en taller genera alerta al Gerente, **recurrente hasta ser atendida**. | Must |
| RN-09 | La orden de compra la autoriza el Administrador contra almacén, **solo sobre presupuesto ya aprobado** por Gerencia. | Should |
| RN-10 | La ubicación del chofer se comparte **solo durante jornada activa o emergencia**, nunca fuera de horario. | Should |
| RN-12 | La **meta de mantenimiento preventivo es de 5 a 7 unidades por día**. No es solo un techo de capacidad: es también un piso. Un día por debajo de 5 se reporta como incumplimiento **del taller**, y si el taller lleva semanas por debajo de la meta, el incumplimiento de los choferes deja de serles imputable — no hubo cupo para todos. | Must |
| RN-14 | El chofer que falta a una cita **confirmada** recibe una **amonestación**: administrativa y documentada, al expediente, **no económica**. Se aplica al **poseedor** de la unidad (RN-01), nunca al titular por algo que ocurrió durante un préstamo. Si el taller nunca dio cita, o no hubo cupo antes de la fecha límite, **no hay amonestación**. El chofer la puede ver y se puede inconformar. | Must |
| RN-15 | Un servicio preventivo **no se cierra sin evidencia fotográfica**. La firma prueba que alguien cerró el formato; la foto prueba que el trabajo se hizo. La evidencia se **comprime en el teléfono antes de subirse** (RF-GEN-15): se guarda la imagen redimensionada, nunca el original de la cámara. | Must |
| RN-16 | **Choque y avería son dos procedimientos distintos**, no dos variantes del mismo. El choque exige peritaje **siempre** —no solo en vialidad pública—, bloquea el movimiento de la unidad hasta tenerlo, levanta parte de accidente con daños y terceros, y termina en carrocería con deducible de por medio. La avería solo bloquea en vialidad pública, levanta reporte de falla y termina en mecánica. | Must |
| RN-17 | **La evidencia de una auditoría de campo no se puede editar después de guardada**: ni la hora, ni la ubicación, ni la foto. Se conserva **la imagen original** además de la sellada, y el sello lo pone el **servidor**, no el teléfono — un sello que dibuja el cliente lo puede dibujar cualquiera. *Propuesto, módulo de auditorías (§ `auditorias-de-campo.md`).* | Must |
| RN-18 | Una auditoría **no se guarda sin GPS activo**, y se rechaza si la **precisión supera el umbral** configurado (el cliente propone 30–50 m). La precisión se guarda junto con las coordenadas: una dirección escrita a mano no prueba dónde se levantó nada. *Propuesto, módulo de auditorías.* | Must |

---

## 5. Requerimientos funcionales

Prioridad MoSCoW: **M** = Must (sin esto no hay sistema), **S** = Should (importante, no bloqueante),
**C** = Could (deseable), **W** = Won't (fuera de esta versión, registrado para el futuro).

### 5.1 Transversales (RF-GEN)

| ID | Requerimiento | MoSCoW | Justificación |
|---|---|---|---|
| RF-GEN-01 | Autenticación de usuarios con credenciales individuales | M | Todo el sistema depende de saber quién actúa |
| RF-GEN-02 | Control de acceso por rol (RBAC) con los 5 módulos | M | Cada rol ve y hace cosas distintas |
| RF-GEN-03 | CRUD de catálogos: usuarios, unidades, talleres, espacios, piezas | M | Datos maestros del sistema |
| RF-GEN-04 | Bitácora de auditoría inmutable de acciones críticas (préstamos, aprobaciones, entradas/salidas) | M | Las penalizaciones y responsabilidades deben ser demostrables |
| RF-GEN-05 | Notificaciones push/in-app por rol y evento | M | El flujo completo es reactivo a eventos |
| RF-GEN-06 | Actualización en tiempo real de estados y ubicaciones (WebSocket) | M | Supervisión y arrastre lo exigen |
| RF-GEN-07 | Máquina de estados de la unidad: `Disponible → En ruta → Varada → En arrastre → En taller → En reparación → Lista → Disponible` | M | Es el núcleo del modelo de datos |
| RF-GEN-08 | Historial completo por unidad (expediente del vehículo) | S | Base del historial de taller de gerencia |
| RF-GEN-09 | Funcionamiento offline con sincronización diferida en la app del chofer | S | Hay zonas sin cobertura en ruta |
| RF-GEN-10 | Carga de evidencia fotográfica en reportes | **M** | Respalda daños y estados. **Sube a Must (2026-09-14):** RN-15 hace la foto obligatoria para cerrar un preventivo |
| RF-GEN-11 | Exportación de reportes a PDF/Excel | C | Útil para dirección, no bloqueante |
| RF-GEN-12 | Multi-taller (varios talleres con su propio administrador) | C | Ya está implícito en "determinado taller" |
| RF-GEN-13 | App móvil nativa | W | Con web responsiva basta en v1 |
| RF-GEN-14 | Integración con nómina para descontar penalizaciones | W | Fuera de alcance. RN-14 confirma que la consecuencia es administrativa, no económica: esto ya no hace falta |
| RF-GEN-15 | **Comprimir la evidencia fotográfica en el cliente antes de subirla**: redimensionar al lado largo acordado, convertir a formato moderno y apuntar a ~200 KB por foto. El original de la cámara nunca sube | M | El «formato ligero» es el requisito, no un detalle: 5 a 7 preventivos al día con varias fotos cada uno son cientos de MB al mes en un servidor que ya está pagado |

### 5.2 Módulo Chofer (RF-CHO)

| ID | Requerimiento | MoSCoW | Justificación |
|---|---|---|---|
| RF-CHO-01 | Ver la unidad asignada y su estado técnico actual | M | Punto de entrada del módulo |
| RF-CHO-02 | Ver la ventana de mantenimiento preventivo pendiente (fecha/km) | M | Sin esto no se puede exigir cumplimiento |
| RF-CHO-03 | Enviar solicitud de ingreso a taller mediante formulario (unidad, taller, falla, urgencia) | M | Requerimiento explícito |
| RF-CHO-04 | Consultar el estatus de su solicitud (pendiente / aceptada / rechazada / en cola) | M | Cierra el ciclo de la solicitud |
| RF-CHO-05 | **Prestar** su unidad a otro chofer indicando motivo (vacaciones, incapacidad) y fecha de retorno | M | Requerimiento explícito |
| RF-CHO-06 | **Recibir/aceptar** una unidad prestada; la aceptación transfiere la responsabilidad (RN-01) | M | Requerimiento explícito |
| RF-CHO-07 | Devolver la unidad y cerrar el préstamo, devolviendo la responsabilidad al titular | M | Cierre del ciclo de préstamo |
| RF-CHO-08 | Reportar avería/varada compartiendo su ubicación, quedando **visible** para supervisor, chofer de grúa y mecánico | M | Requerimiento explícito |
| RF-CHO-09 | Al reportar varada en vialidad pública, el sistema **obliga primero el aviso a peritos** y captura el folio; hasta entonces no habilita la solicitud de mecánico (RN-04) | M | Requerimiento explícito y de riesgo legal |
| RF-CHO-10 | Ver la ubicación en tiempo real del chofer de grúa que aceptó su arrastre | M | Requerimiento explícito |
| RF-CHO-11 | Recibir aviso de penalización aplicada, con motivo y fecha | M | Debido proceso de RN-05 |
| RF-CHO-12 | Recibir recordatorios previos al vencimiento de la ventana de mantenimiento | S | Reduce incumplimiento; evita disputas |
| RF-CHO-13 | Checklist de inspección pre-operacional al inicio de jornada | S | Detecta fallas antes de la ruta |
| RF-CHO-14 | Registrar entrada/salida de jornada (inicio y fin de conducción) | S | Alimenta el "quién está conduciendo" del supervisor |
| RF-CHO-15 | Ver su historial de penalizaciones, **amonestaciones** y cumplimiento | **S** | Transparencia. **Sube de C a S (2026-09-14):** con RN-14 de por medio, un chofer no puede enterarse de su amonestación por el pasillo |
| RF-CHO-16 | Levantar inconformidad sobre una penalización o amonestación | **S** | **Sube de C a S (2026-09-14):** si la amonestación va al expediente, tiene que haber a dónde reclamar |
| RF-CHO-17 | Cálculo de comisiones del chofer | W | Fuera de alcance |
| RF-CHO-18 | **Reportar un choque por un flujo propio, distinto del de avería** (RN-16): captura de daños, terceros involucrados, aviso automático al perito interno y bloqueo del movimiento de la unidad hasta que exista peritaje | M | Hoy un choque se describe en el campo «falla» de una avería. Los procedimientos son distintos y el gerente no puede ni contar cuántos choques hubo |

### 5.3 Módulo Supervisor (RF-SUP)

| ID | Requerimiento | MoSCoW | Justificación |
|---|---|---|---|
| RF-SUP-01 | Ver su **plantilla** asignada de choferes y la **flotilla** que trae | M | Base del módulo. Renombrado el 2026-09-14: son dos listas, no una |
| RF-SUP-02 | Ver en tiempo real qué chofer está conduciendo, con qué unidad, y quién no está conduciendo | M | Requerimiento explícito |
| RF-SUP-03 | Ver los préstamos activos: quién prestó qué unidad a quién y hasta cuándo | M | Requerimiento explícito |
| RF-SUP-04 | Ver si una unidad está en taller o repartiendo en la ciudad | M | Requerimiento explícito |
| RF-SUP-05 | Ver alertas de unidades varadas que requieren chofer de grúa o mecánico | M | Requerimiento explícito |
| RF-SUP-06 | Mapa con ubicación de las unidades de su flotilla | S | Hace usable RF-SUP-02/04 |
| RF-SUP-07 | Autorizar o vetar un préstamo de su plantilla | S | Control de abusos; el enunciado no lo exige |
| RF-SUP-08 | Ver el estado de cumplimiento de mantenimiento, penalizaciones y amonestaciones de su plantilla | S | Le permite corregir antes de que escale a gerencia |
| RF-SUP-09 | Escalar/despachar apoyo a una unidad varada y **registrar el envío del mecánico a sitio** | S | Redundancia si el chofer de grúa no responde. Absorbe RF-MEC-07: como el mecánico no tiene app, el supervisor deja la constancia |
| RF-SUP-10 | Reasignar unidad entre choferes de la plantilla | C | Caso menos frecuente que el préstamo |
| RF-SUP-11 | Reportes de productividad por chofer | W | Fuera de alcance |
| RF-SUP-12 | **Emitir y consultar amonestaciones de su plantilla** (RN-14), con el motivo, la cita incumplida que la originó y quién la firmó | M | Sin un lugar donde emitirla, la amonestación se queda en una conversación y no sostiene nada. **Pendiente:** confirmar si la firma el supervisor, Erick o el gerente (pregunta abierta #13) |

### 5.4 Módulo Administrador de taller (RF-ADM)

| ID | Requerimiento | MoSCoW | Justificación |
|---|---|---|---|
| RF-ADM-01 | Bandeja de solicitudes de ingreso al taller | M | Requerimiento explícito |
| RF-ADM-02 | Ver disponibilidad de espacios del taller antes de decidir | M | Requerimiento explícito (RN-06) |
| RF-ADM-03 | Aceptar o rechazar una solicitud de ingreso, con motivo en el rechazo | M | Requerimiento explícito |
| RF-ADM-04 | Gestionar los espacios del taller: alta, baja, estado (libre/ocupado/bloqueado) | M | Requerimiento explícito |
| RF-ADM-05 | Meter y sacar vehículos de cada espacio | M | Requerimiento explícito |
| RF-ADM-06 | Asignar a un vehículo mecánicos, carroceros y electricistas **en fila/cola**, como procesos en espera | M | Requerimiento explícito |
| RF-ADM-07 | Reordenar la cola de especialistas de un vehículo (prioridad) | S | Se deriva del anterior; da valor real |
| RF-ADM-08 | Llenar y emitir el formulario de salida del vehículo | M | Requerimiento explícito |
| RF-ADM-09 | Capturar el presupuesto que entrega el mecánico y remitirlo al gerente | M | Requerimiento explícito (RN-07). **Reasignado**: antes lo elaboraba el mecánico en el sistema |
| RF-ADM-10 | Autorizar órdenes de compra de piezas contra almacén, ligadas a la unidad | M | Requerimiento explícito |
| RF-ADM-11 | Dar seguimiento a las piezas en camino (estatus y fecha estimada) | S | Alimenta el dashboard del gerente |
| RF-ADM-12 | Ver tiempo de permanencia de cada unidad en su taller | S | Insumo de gerencia y de su propia gestión |
| RF-ADM-15 | **Capturar el diagnóstico** que entrega el mecánico, ligado a la orden de servicio y al técnico que lo hizo | M | **Reasignado desde RF-MEC-02**; sin esto no hay base para el presupuesto |
| RF-ADM-16 | **Capturar las piezas faltantes** detectadas por el mecánico | M | **Reasignado desde RF-MEC-03** |
| RF-ADM-17 | **Registrar inicio, avance y término** de la reparación por técnico | M | **Reasignado desde RF-MEC-06**; alimenta ocupación y tiempos del gerente |
| RF-ADM-18 | Emitir/imprimir la **hoja de trabajo** del día para entregarla a los técnicos en papel | M | Sin app, el mecánico necesita su cola en físico. Requerimiento **nuevo** que nace del cambio |
| RF-ADM-23 | **Adjuntar la evidencia fotográfica del servicio preventivo y no dejar cerrar el formato sin ella** (RN-15), ligada a la actividad concreta que se ejecutó | M | La firma prueba que alguien cerró el formato; la foto prueba que el trabajo se hizo. **Pendiente:** qué fotos y cuántas por servicio (pregunta abierta #14) |
| RF-ADM-24 | **Ver el avance del día contra la meta de 5 a 7 preventivos** (RN-12): cuántos van, cuántos faltan y qué citas quedan por delante | M | Una meta que nadie ve durante el día no se cumple, se reporta al final |
| RF-ADM-19 | Registrar la **notificación al mecánico** del resultado del presupuesto (aprobado/rechazado) | S | **Reasignado desde RF-MEC-05**; el aviso es verbal, el sistema solo deja constancia |
| RF-ADM-20 | Consultar el expediente/historial de reparaciones de la unidad para consulta del mecánico | S | **Reasignado desde RF-MEC-08** |
| RF-ADM-21 | Adjuntar la foto o el escaneo del presupuesto en papel firmado por el mecánico | S | Respalda RN-11 ante una disputa de costos |
| RF-ADM-13 | Vista tipo tablero (kanban) del taller por espacio | C | Usabilidad, no funcionalidad nueva |
| RF-ADM-22 | Presupuestos a partir de plantillas de mano de obra y refacciones | C | **Reasignado desde RF-MEC-09**; acelera la captura, que ahora es cuello de botella |
| RF-ADM-14 | Programación automática/óptima de cargas de trabajo | W | Complejidad alta, poco valor en v1 |

> **Advertencia de carga de trabajo.** El administrador pasa de 14 a **24 requerimientos**. Todo
> lo que antes capturaba el mecánico ahora lo teclea él, y es la misma persona que atiende
> solicitudes de ingreso y mueve unidades entre espacios. Es el **cuello de botella del diseño**:
> si el taller tiene mucha rotación, un solo administrador no da abasto. Vale la pena validar con
> el cliente cuántos administradores hay por taller antes de cerrar la Fase 2.

### 5.5 Módulo Chofer de grúa (RF-MON)

| ID | Requerimiento | MoSCoW | Justificación |
|---|---|---|---|
| RF-MON-01 | Recibir la alerta de unidad varada con la ubicación reportada por el chofer | M | Requerimiento explícito |
| RF-MON-02 | Aceptar (o rechazar) un arrastre | M | Requerimiento explícito |
| RF-MON-03 | Compartir su ubicación en tiempo real con el chofer del arrastre aceptado | M | Requerimiento explícito |
| RF-MON-04 | Cerrar el arrastre registrando: taller destino, unidad, chofer responsable, fecha/hora | M | Requerimiento explícito |
| RF-MON-05 | Ver el detalle de la falla y datos de contacto del chofer | S | Necesario en la práctica |
| RF-MON-06 | Historial de arrastres realizados | S | Trazabilidad y control |
| RF-MON-07 | Evidencia fotográfica al recoger y al entregar la unidad | S | Protege contra reclamos de daño |
| RF-MON-08 | Navegación/ruta hacia la unidad varada | C | Se puede resolver con mapa externo |
| RF-MON-09 | Asignación automática del chofer de grúa más cercano | C | Optimización posterior |

### 5.6 Módulo Mecánico — **ELIMINADO** (trazabilidad del cambio)

El cliente confirmó que los mecánicos **no usarán la aplicación**. El módulo se elimina y sus
requerimientos se reasignan o se descartan. Se conserva esta tabla para no perder la trazabilidad:
un requerimiento que desaparece sin dejar constancia reaparece más tarde como "algo que se nos
olvidó".

| ID original | Requerimiento | Destino | Nuevo ID |
|---|---|---|---|
| RF-MEC-01 | Ver su cola de trabajo | **Sustituido**: se imprime en papel | RF-ADM-18 |
| RF-MEC-02 | Registrar diagnóstico | **Reasignado** al administrador | RF-ADM-15 |
| RF-MEC-03 | Listar piezas faltantes | **Reasignado** al administrador | RF-ADM-16 |
| RF-MEC-04 | Elaborar y enviar presupuesto | **Reasignado**: lo elabora en papel, el admin lo captura | RF-ADM-09 |
| RF-MEC-05 | Ver resultado del presupuesto | **Reasignado**: aviso verbal, el sistema deja constancia | RF-ADM-19 |
| RF-MEC-06 | Registrar avance y término | **Reasignado** al administrador | RF-ADM-17 |
| RF-MEC-07 | Atender auxilio mecánico en sitio | **Reasignado** al supervisor, que registra el despacho | RF-SUP-09 |
| RF-MEC-08 | Ver expediente de la unidad | **Reasignado**: el admin lo consulta y se lo muestra | RF-ADM-20 |
| RF-MEC-09 | Plantillas de presupuesto | **Reasignado** al administrador | RF-ADM-22 |
| RF-MEC-10 | Catálogo de tiempos estándar | **Descartado** (ya era Won't) | — |

**Lo que sí se conserva del mecánico en el sistema:**

| ID | Requerimiento | MoSCoW | Justificación |
|---|---|---|---|
| RF-TEC-01 | Catálogo de técnicos (mecánicos, carroceros, electricistas, llanteros) **sin cuenta de usuario** | M | RF-ADM-06 necesita a quién asignar la cola |
| RF-TEC-02 | Registrar disponibilidad y taller de adscripción de cada técnico | M | Sin esto no se puede armar la fila de trabajo |
| RF-TEC-03 | Reporte de carga de trabajo por técnico | C | Insumo futuro de gerencia |

**Riesgo que introduce este cambio.** La calidad del dato depende ahora de que el administrador
capture a tiempo. Si captura al final del día, los indicadores del gerente (ocupación, tiempos,
piezas en camino) van con retraso y **RF-GER-03 deja de ser "en tiempo real"** en la práctica. Es
un riesgo de proceso, no de software, y hay que decírselo al cliente.

### 5.7 Módulo Gerente (RF-GER)

| ID | Requerimiento | MoSCoW | Justificación |
|---|---|---|---|
| RF-GER-01 | Dashboard consolidado de flota y talleres | M | Requerimiento explícito |
| RF-GER-02 | Indicador de choferes que **no están siguiendo el mantenimiento preventivo**, con su unidad y días de atraso | M | Requerimiento explícito y motivo del proyecto |
| RF-GER-03 | Ocupación del taller en tiempo real (espacios usados/libres) | M | Requerimiento explícito |
| RF-GER-04 | Historial del taller (unidades atendidas, entradas y salidas) | M | Requerimiento explícito |
| RF-GER-05 | Ver las piezas en camino por unidad | M | Requerimiento explícito |
| RF-GER-06 | Ver cuánto tiempo lleva cada unidad en taller | M | Requerimiento explícito |
| RF-GER-07 | Alerta recurrente de unidades con **más de 3 meses** paradas, hasta que se atiendan (RN-08) | M | Requerimiento explícito |
| RF-GER-08 | Cantidad de unidades atendidas en un periodo configurable | M | Requerimiento explícito |
| RF-GER-09 | Aprobar o rechazar presupuestos remitidos por el administrador | M | Requerimiento explícito (RN-07) |
| RF-GER-10 | Ver ranking/histórico de penalizaciones y **amonestaciones** por chofer y por supervisor | S | Da consecuencia real a RN-05 y RN-14 |
| RF-GER-11 | Costo acumulado de mantenimiento por unidad | S | Decisión de reemplazo de flota |
| RF-GER-14 | **Ver todas las estadísticas del tablero por día, por mes y por año**, con selector de periodo, no solo el estado actual | M | RF-GER-08 daba «un periodo configurable» suelto. El cliente pidió un eje de tiempo de verdad sobre los mismos indicadores |
| RF-GER-15 | **Presentar la información en gráficos**, no solo en tablas y números: tendencia de preventivos contra la meta, cumplimiento por mes, ocupación a lo largo del año | M | Petición directa del gerente. Un tablero directivo que solo tiene tablas obliga a leerlo; con gráficos se entiende de un vistazo, que es para lo que existe |
| RF-GER-16 | **Historial acumulado por chofer**: citas confirmadas contra cumplidas, amonestaciones, préstamos recibidos, averías y choques reportados | M | Es el expediente del chofer, el equivalente al de la unidad (RF-GEN-08). Sirve para sostener una amonestación **y para defender** al chofer al que el taller nunca le dio cita |
| RF-GER-17 | **Estadístico de cumplimiento por chofer, cortado por mes y por año** | M | Petición directa: sin el corte por periodo no se distingue al que falló una vez del que falla siempre |
| RF-GER-18 | **Seguimiento de la meta de 5 a 7 preventivos por día** (RN-12), con los días por debajo del piso marcados | M | Es el indicador que dice si el incumplimiento es del chofer o del taller |
| RF-GER-12 | Comparativo entre talleres | C | Solo aplica con multi-taller |
| RF-GER-13 | Predicción de fallas / mantenimiento predictivo | W | Requiere histórico que aún no existe |

> **Lo que esto pide por debajo.** RF-GER-14 a RF-GER-18 no son cinco pantallas: son **datos
> agregados históricos**. La base guarda hoy el presente de cada unidad; para una serie por mes y
> por año hay que decidir si se agrega al vuelo sobre la bitácora o si se materializan cortes
> periódicos. Es una decisión de modelo, y conviene tomarla antes de dibujar el primer gráfico.

---

## 6. Requerimientos no funcionales

| ID | Requerimiento | MoSCoW |
|---|---|---|
| RNF-01 | Interfaz web responsiva, usable desde celular por chofer y chofer de grúa | M |
| RNF-02 | Latencia de actualización de ubicación ≤ 10 s en arrastre activo | M |
| RNF-03 | Autenticación con contraseña cifrada (hash) y sesión con expiración | M |
| RNF-04 | Autorización estricta por rol en el servidor, no solo en la interfaz | M |
| RNF-05 | Trazabilidad: toda transferencia de responsabilidad y aprobación queda con usuario, fecha y hora | M |
| RNF-06 | Respaldo diario de la base de datos | M |
| RNF-07 | Disponibilidad ≥ 99% en horario operativo | S |
| RNF-08 | Soportar 100 usuarios concurrentes sin degradación perceptible | S |
| RNF-09 | Tiempo de respuesta < 2 s en el 95% de las pantallas | S |
| RNF-10 | Datos de ubicación tratados conforme a la LFPDPPP: captura solo en jornada/emergencia y retención limitada (RN-10) | S |
| RNF-11 | Documentación técnica y manual por rol | S |
| RNF-12 | Bilingüe (español/inglés) | W |

---

## 7. Cómo ejecutar el proyecto con MoSCoW

### 7.1 El método en corto

MoSCoW clasifica cada requerimiento por **obligación de entrega**, no por gusto:

- **Must have** — si falta uno solo, la entrega **no sirve**. Es el criterio duro: pregúntate
  *"¿el sistema es inútil sin esto?"*. Si la respuesta es "no, pero sería feo", no es Must.
- **Should have** — importante y doloroso de omitir, pero existe un rodeo manual temporal.
- **Could have** — mejora real, se hace **solo si sobra tiempo**. Es el amortiguador.
- **Won't have (this time)** — decidido explícitamente fuera de esta versión. Se documenta para
  que nadie lo meta por la puerta trasera.

**Regla de reparto recomendada por iteración:** Must ≤ **60%** del esfuerzo estimado, Should ~20%,
Could ~20%. Ese 40% no-Must es el colchón que absorbe imprevistos sin que la entrega falle. Si
todo es Must, no hay priorización: hay una lista de deseos.

**Regla de oro:** MoSCoW se aplica **por entrega**, no una sola vez al proyecto. Un *Could* de la
Fase 1 puede ser *Must* en la Fase 3.

### 7.2 Distribución de esta especificación

| Prioridad | Cantidad | Qué contiene |
|---|---|---|
| Must | 62 | Núcleo: roles, unidad, préstamo con responsabilidad, taller y espacios, arrastre, captura de presupuestos, dashboard. **Desde v1.2:** evidencia fotográfica, amonestación, choque como flujo propio y las estadísticas del gerente |
| Should | 22 | Mapas, offline, historiales, penalizaciones detalladas, constancias de aviso al mecánico, inconformidad del chofer |
| Could | 9 | Kanban, exportaciones, optimizaciones, plantillas de presupuesto |
| Won't (v1) | 6 | Nómina, comisiones, app nativa, predictivo |
| **Total** | **99** | |

Tras eliminar el módulo Mecánico el total había bajado de 91 a 88: se descartaron 3 (cola de
trabajo en pantalla, catálogo de tiempos estándar y la app del mecánico como tal) y se reasignaron
7 al administrador y 1 al supervisor. El esfuerzo **no bajó en la misma proporción**: la captura
sigue existiendo, solo cambió de manos.

**La junta del 2026-09-14 sumó 10 requerimientos, todos Must**, y movió tres de prioridad
(RF-GEN-10 de Should a Must; RF-CHO-15 y RF-CHO-16 de Could a Should). Los diez caen casi todos en
dos lugares: el **tablero del gerente** —5 requerimientos que además piden datos agregados
históricos que hoy la base no guarda— y el **administrador de taller**, que ya era el cuello de
botella del diseño. **Conviene revisar la hoja de ruta de §7.3 antes de comprometer fechas.**

> Las cifras de la tabla son el conteo real de filas de §5 al día de hoy, no las de la v1.1: ahí
> los números eran aproximados y ya no cuadraban con el documento.

### 7.3 Hoja de ruta por incrementos

Cada fase termina con algo **demostrable y usable**, no con "media base de datos".

**Fase 0 — Cimientos (1–2 semanas)**
Modelo de datos, autenticación, RBAC, catálogos.
Entregables: RF-GEN-01 a 03, 07, RNF-03, RNF-04.
Criterio de salida: los 5 roles entran al sistema y cada uno ve un menú distinto; el catálogo de
técnicos (RF-TEC-01) existe aunque los técnicos no tengan cuenta.

**Fase 1 — MVP: responsabilidad de la unidad (3–4 semanas)**
El corazón del problema de negocio: quién responde por cada unidad y quién no cumple.
Entregables: RF-CHO-01, 02, 05, 06, 07, 11 · RF-SUP-01 a 04 · RN-01, RN-02, RN-03, RN-05 ·
RF-GEN-04, 05.
Criterio de salida: se presta una unidad, la responsabilidad se transfiere, el supervisor lo ve
y el incumplimiento genera penalización automática.

**Fase 2 — Taller (3–4 semanas)**
Entregables: RF-CHO-03, 04 · RF-ADM-01 a 06, 08, 15, 17, 18 · RF-TEC-01, 02 · RN-06, RN-11.
Criterio de salida: el chofer solicita ingreso, el administrador lo acepta según espacios, coloca
la unidad en una bahía con su cola de especialistas, **imprime la hoja de trabajo del día**,
captura el diagnóstico y el avance que le entregan los técnicos, y emite la salida.

**Fase 3 — Emergencias y arrastre (2–3 semanas)**
Entregables: RF-CHO-08, 09, 10 · RF-MON-01 a 04 · RF-SUP-05 · RF-GEN-06 · RN-04 · RNF-02.
Criterio de salida: unidad varada en vialidad → aviso a peritos con folio → alerta al
chofer de grúa → seguimiento en tiempo real → cierre con taller destino registrado.

**Fase 4 — Presupuestos y compras (2 semanas)**
Entregables: RF-ADM-09, 10, 11, 16, 19, 21 · RF-GER-09 · RN-07, RN-09, RN-11.
Criterio de salida: el administrador captura el presupuesto que le entregó el mecánico en papel,
lo remite al gerente, este aprueba, y el sistema habilita la orden de compra. Queda registrado
qué técnico lo elaboró y qué administrador lo capturó.

**Fase 5 — Dashboard gerencial (2 semanas)**
Entregables: RF-GER-01 a 08 · RN-08 · RF-GEN-08.
Criterio de salida: el gerente ve incumplimiento, ocupación, tiempos, piezas en camino y recibe
la alerta de los 3 meses.

**Fase 6 — Endurecimiento**
Should y Could pendientes según tiempo restante: mapas, offline, evidencias, exportaciones.

### 7.4 Gobierno de la priorización

1. **Ninguna prioridad se cambia en solitario.** Subir algo a Must exige bajar otra cosa: el
   esfuerzo Must de la fase no puede crecer.
2. **Re-priorizar al inicio de cada fase**, con el gerente y un supervisor presentes.
3. **Criterio de aceptación por requerimiento** antes de programarlo; sin criterio, no entra al
   sprint.
4. **Los Won't se registran**, no se discuten cada semana.
5. **Trazabilidad:** cada historia de usuario debe apuntar a un ID de este documento; código sin
   ID asociado es alcance no autorizado.

---

## 8. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Resistencia de los choferes (el sistema los penaliza) | Alto | Involucrarlos en el diseño; recordatorios previos (RF-CHO-12) y derecho de inconformidad (RF-CHO-16) |
| Falta de cobertura celular en ruta | Alto | Modo offline (RF-GEN-09) y confirmación diferida |
| Privacidad de la ubicación de los choferes | Medio-legal | RN-10, RNF-10, aviso de privacidad firmado |
| Dependencia de terceros (peritos, almacén) fuera del sistema | Medio | Registrar folios/estatus manualmente, no automatizar lo que no se controla |
| Alcance creciente hacia comisiones y nómina | Medio | Está declarado Won't |
| **El administrador se vuelve cuello de botella** al absorber la captura del mecánico | **Alto** | Validar cuántos administradores hay por taller; plantillas de captura (RF-ADM-22); hoja de trabajo impresa (RF-ADM-18) |
| **Retraso en la captura**: si el admin teclea al final del día, los indicadores "en tiempo real" del gerente no lo son | **Alto** | Acordar una ventana máxima de captura (ej. 2 h) y medirla; marcar en el dashboard la antigüedad del dato |
| **Datos de segunda mano**: el admin captura lo que entendió del mecánico | Medio | RN-11 (doble responsable) y RF-ADM-21 (foto del presupuesto firmado) |

---

## 9. Preguntas abiertas (a confirmar con el cliente)

1. ¿La penalización es económica, administrativa o solo un registro? ¿Quién la aplica y quién la puede cancelar?
2. ¿La ventana de mantenimiento se define por kilometraje, por fecha, o por ambos?
3. ¿El préstamo requiere autorización del supervisor o basta el acuerdo entre choferes? (afecta RF-SUP-07)
4. ¿Cuántos talleres y cuántos espacios por taller?
5. ¿"Más de 3 meses parada" se cuenta desde el ingreso al taller o desde que se detiene la reparación?
6. ¿Existe un monto de presupuesto por debajo del cual el administrador puede aprobar sin el gerente?
7. ¿El chofer de grúa es empleado interno o proveedor externo?
8. **¿Cuántos administradores hay por taller?** De esto depende si la captura del trabajo del mecánico es viable o si el sistema se atora en la Fase 2.
9. **¿En cuánto tiempo debe capturar el administrador** lo que le entrega el mecánico? Sin un acuerdo explícito, el "tiempo real" del gerente es ficción.
10. **¿Los carroceros y electricistas tampoco usarán la app?** Se asumió que no, igual que los mecánicos. Si alguno sí la usa, hay que reponerle su módulo.

**Abiertas desde la junta del 2026-09-14** (detalle en `junta-2026-09-14.md`):

11. **¿Cómo se le dice al grupo de técnicos** —mecánicos, carroceros, electricistas—, si no son plantilla (choferes) ni flotilla (unidades)? Por ahora se quedó «cuadrilla técnica», que es justo la palabra que el cliente ya no usa.
12. **La meta de 5 a 7 preventivos al día, ¿es por taller o de toda la operación?** Álamos es el taller grande, pero hay plantas satélite. De la respuesta depende contra qué se mide RF-GER-18.
13. **¿Quién firma la amonestación** —el supervisor, Erick o el gerente— y **qué pasa a la segunda o la tercera**? Sin escalamiento definido, la amonestación es un registro sin consecuencia.
14. **¿Qué fotos validan un preventivo y cuántas por servicio?** ¿La pieza vieja, la nueva, el odómetro? Sin una lista, cada quien sube lo que se le ocurre y la evidencia no sirve para comparar.
15. **¿Edgar es el único perito?** Si lo es y no contesta de madrugada, RN-04 deja el arrastre bloqueado sin salida. Hace falta un suplente o una regla de escalamiento.
16. **¿El historial acumulado por chofer (RF-GER-16) lo puede ver también su supervisor**, o solo el gerente? Afecta el alcance de RF-SUP-08.

> **Nota de vocabulario.** «Plantilla» ahora significa **grupo de choferes**, pero RF-ADM-22 ya
> usaba «plantillas» para las **machotes de presupuesto**. Son dos cosas distintas con la misma
> palabra: al implementar, no se llamen igual en el código.

---

## 10. Sugerencia técnica (prototipo Node.js)

- **Backend:** Node.js + Express, PostgreSQL (el dominio es fuertemente relacional: unidad,
  préstamo, espacio, presupuesto).
- **Tiempo real:** Socket.IO para ubicación de arrastre y estados de taller.
- **Frontend:** web responsiva (React o vistas del lado del servidor para el prototipo).
- **Autorización:** middleware por rol + verificación de propiedad del recurso.
- **Tareas programadas:** job diario que evalúa ventanas de mantenimiento vencidas (RN-05) y
  unidades con más de 3 meses (RN-08).
