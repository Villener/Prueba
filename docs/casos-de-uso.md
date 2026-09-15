# Diagrama y catálogo de casos de uso — Sistema de Gestión de Flota y Taller (Baja Gas)

**Versión:** 2.2 · **Fecha:** 2026-09-15
**Deriva de:** [modelo-clases.md](modelo-clases.md) v2.0
**Relacionados:** [modelo-er.md](modelo-er.md) · [procesos.md](procesos.md) · [agenda-mantenimiento.md](agenda-mantenimiento.md) · [requerimientos.md](requerimientos.md)

> **v2.0 — Cinco cambios que reordenan el mapa completo.**
> 1. **Vuelve el módulo Mecánico**, pero solo para los **autónomos** de las plantas satélite. Los
>    de Álamos siguen sin app.
> 2. **El administrador se parte en dos diagramas** porque son cuatro personas con permisos
>    distintos, no un rol con cuatro cuentas.
> 3. **El preventivo ya no lo solicita el chofer**: lo agenda Víctor y el chofer confirma.
> 4. **El auxilio en carretera se difunde** a todos los mecánicos autónomos y el primero que
>    acepta lo gana.
> 5. **Desaparece "penalización"**: el sistema emite un aviso de incumplimiento que gerente y
>    Erick cierran a mano.
>
> De 63 casos de uso a **94**.

> **v2.1 (2026-09-14) — siete casos de uso que salieron de la junta con el cliente.**
> CU-CHO-18 (choque, procedimiento aparte de la avería), CU-SUP-10 (amonestación),
> CU-ADM-31 (evidencia fotográfica del preventivo), CU-GER-12/13/14 (gráficos, historial por
> chofer, cumplimiento por mes y año) y CU-AUT-08 (amonestación automática). **De 99 a 106.**
> Además, «cuadrilla» se parte en **plantilla** (choferes) y **flotilla** (unidades), y el
> **perito Edgar** entra como actor primario interno. Detalle en
> [`junta-2026-09-14.md`](junta-2026-09-14.md).
>
> **Ojo con el punto 5 de arriba.** La v2.0 quitó la penalización y dejó la conversación como
> único canal: «gerente y Erick hablan con el chofer». El cliente ahora pide una **amonestación**,
> que es un acto formal y va al expediente. No es volver atrás del todo —la amonestación se emite
> *después* de esa conversación, no en lugar de ella—, pero sí reabre la pregunta de si el chofer
> necesita un canal de defensa dentro de la app. Pregunta abierta #13 de `requerimientos.md`.

> **v2.2 (2026-09-15) — módulo propuesto de auditorías de campo a reparto.**
> 12 casos CU-AUD en §3.11 más CU-AUT-09, que **se cuentan aparte de los 106**: el módulo no está
> aprobado. Sale de los dos documentos que entregó el cliente, y depende de una pregunta que
> todavía no tiene respuesta — si la evidencia fotográfica puede vivir en web, donde **la galería
> no se puede bloquear**. Análisis en [`auditorias-de-campo.md`](auditorias-de-campo.md), modelo de
> datos en el Paquete I de [`modelo-er-mermaid.md`](modelo-er-mermaid.md).

---

## 1. Diagramas

En `docs/diagramas/` como SVG. Para verlos todos juntos, abre
[`docs/diagramas/index.html`](diagramas/index.html) en el navegador.

| # | Archivo | Contenido |
|---|---|---|
| 0 | [00-contexto-general.svg](diagramas/00-contexto-general.svg) | Los 6 módulos, sus actores y las 6 plantas |
| 1 | [01-modulo-chofer.svg](diagramas/01-modulo-chofer.svg) | 17 casos del chofer |
| 2 | [02-modulo-supervisor.svg](diagramas/02-modulo-supervisor.svg) | 9 casos del supervisor |
| 3 | [03-modulo-administrador-taller.svg](diagramas/03-modulo-administrador-taller.svg) | 16 casos — **Pedro** (piso y almacén) y **Víctor** (agenda) |
| 4 | [04-modulo-administrador-compras.svg](diagramas/04-modulo-administrador-compras.svg) | 9 casos — **Erick** (compras y enlace con gerencia) |
| 5 | [05-modulo-mecanico-autonomo.svg](diagramas/05-modulo-mecanico-autonomo.svg) | 12 casos — **nuevo módulo** |
| 6 | [06-modulo-chofer-grua.svg](diagramas/06-modulo-chofer-grua.svg) | 8 casos del chofer de grúa |
| 7 | [07-modulo-gerente.svg](diagramas/07-modulo-gerente.svg) | 11 casos del gerente |

**Por qué el administrador ocupa dos diagramas.** Erick, Pedro, Víctor y Pablo no hacen lo mismo y
**no deben poder hacer lo mismo**: Víctor no autoriza órdenes de compra y Erick no mueve vehículos
de espacio. Dibujarlos como un solo actor "Administrador" escondería la separación de funciones,
que es justo lo que un sistema de control debe hacer visible.

**Convención de líneas:** continua = el actor **opera el sistema**; punteada = participa en el
proceso pero **no toca la aplicación**. Solo los mecánicos, carroceros y electricistas **de
Álamos** están en el segundo grupo.

---

## 2. Actores

### Primarios — inician casos de uso

| Actor | Descripción |
|---|---|
| **Chofer** | Opera la unidad y responde por ella mientras la conduce |
| **Supervisor** | Vigila una **plantilla** de choferes y la **flotilla** de unidades que esa plantilla trae. No son la misma lista ni del mismo tamaño |
| **Pedro** · *piso y almacén* | Espacios, colas de técnicos, surtido de piezas, captura del trabajo de los mecánicos de Álamos |
| **Víctor** · *agenda* | Programa el mantenimiento preventivo y gestiona las citas |
| **Erick** · *compras y enlace* | Presupuestos, órdenes de compra, y el único puente con el gerente |
| **Pablo** · *operativo* | Cubre a Pedro y a Víctor **por suplencia de perfil**, no con cuenta propia |
| **Mecánico autónomo** | Los 6 de las plantas satélite. Único técnico con acceso al sistema |
| **Jaime Yair** · *capturista de datos* | Teclea las requisiciones de material del taller de Álamos. El puesto viene con ese nombre en la hoja TALLER del Excel del cliente (empleado 13905) |
| **Chofer de grúa** | Arrastres y traslados entre plantas |
| **Gerente** · *Luis Tiscareño* | Aprueba presupuestos, atiende alertas y avisos, consulta indicadores |
| **Edgar** · *perito* | Levanta el peritaje de choques y siniestros en vialidad. Es del **sindicato**, pero trabaja para Baja Gas: **actor interno, con cuenta propia**. Sin su peritaje, la unidad accidentada no se mueve (RN-04, RN-16) |

### Secundarios — participan, no inician

**Otro chofer** (recibe una unidad en préstamo) · **Almacén de Álamos** (responde consultas y
surte) · **Proveedor** (piezas en camino) · **Aseguradora** (atiende el siniestro después del
peritaje de Edgar).

> **Corrección (2026-09-14).** «Peritos / Aseguradora» estaba como un solo actor externo. Son dos:
> **Edgar es de la casa** y sube a actor primario —se le avisa desde el sistema y levanta el
> peritaje dentro—, mientras que la aseguradora sigue siendo externa y entra después.

### «business worker» — participa en el proceso, no usa el sistema

**Mecánico, carrocero y electricista de Álamos.** Entregan diagnóstico, presupuesto y avance en
papel; Erick y Pedro los capturan. Reciben su cola de trabajo impresa.

> Se dibujan con línea punteada porque borrarlos escondería de dónde vienen los datos y haría que
> "capturar presupuesto" pareciera inventado por el administrador. Si tu profesor exige UML
> estricto de sistema, quítalos del diagrama y déjalos como nota: el contenido no cambia.

### Temporal

**Programador de tareas.** El reloj del sistema. Dispara los 7 casos automáticos.

---

## 3. Catálogo

### 3.1 Comunes — CU-GEN (5)

| ID | Caso de uso | Actor | Prioridad |
|---|---|---|---|
| CU-GEN-01 | Iniciar sesión | Usuario del sistema | Must |
| CU-GEN-02 | Recibir notificaciones | Usuario del sistema | Must |
| CU-GEN-03 | Administrar catálogos (usuarios, unidades, plantas, espacios, piezas, tipos de servicio) | Erick, Gerente | Must |
| CU-GEN-04 | Consultar bitácora de auditoría | Gerente | Must |
| **CU-GEN-05** | **Asumir suplencia de un perfil** | Pablo, Erick, Pedro | Must |

`CU-GEN-05` es nuevo y resuelve lo que confirmaste: a Víctor lo cubren Pablo, Erick o Pedro. Se le
da el rol con fecha de fin. **Sin cuentas compartidas.**

### 3.2 Chofer — CU-CHO (17)

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-CHO-01 | Consultar mi unidad y su estado técnico | Chofer | Must |
| CU-CHO-02 | Consultar mi plan de mantenimiento | Chofer | Must |
| CU-CHO-03 | Registrar jornada | Chofer | Must |
| CU-CHO-04 | Ejecutar checklist pre-operacional | Chofer | Should |
| CU-CHO-05 | Solicitar ingreso a taller *(correctivo)* | Chofer, Pedro | Must |
| CU-CHO-06 | Consultar estatus de la solicitud | Chofer | Must |
| **CU-CHO-07** | **Confirmar mi cita de taller** | Chofer, Víctor | Must |
| CU-CHO-08 | Prestar unidad | Chofer | Must |
| CU-CHO-09 | Recibir unidad prestada | Otro chofer | Must |
| CU-CHO-10 | Devolver unidad y cerrar préstamo | Chofer | Must |
| CU-CHO-11 | Reportar avería en ruta | Chofer, Supervisor | Must |
| CU-CHO-12 | Registrar aviso a peritos | Chofer, Peritos | Must |
| CU-CHO-13 | Compartir ubicación en tiempo real | Chofer | Must |
| **CU-CHO-14** | **Solicitar auxilio mecánico** | Chofer, Mecánico autónomo | Must |
| CU-CHO-15 | Solicitar arrastre | Chofer, Chofer de grúa | Must |
| **CU-CHO-16** | **Dar seguimiento al apoyo en camino** | Chofer | Must |
| CU-CHO-17 | Consultar mis avisos de incumplimiento **y mis amonestaciones** | Chofer | Must |
| **CU-CHO-18** | **Reportar un choque** | Chofer, Edgar (perito), Supervisor | Must |

**`CU-CHO-03` sube de Should a Must.** Con la responsabilidad siguiendo a quien conduce, la
jornada dejó de ser un dato de conveniencia: es la primera rama de `poseedorActual()`.

**Se elimina "Levantar inconformidad".** Con el esquema nuevo, el gerente y Erick hablan con el
chofer en persona — **la conversación es el canal de defensa**. Un trámite paralelo dentro de la
app solo agregaría burocracia a algo que ya se resuelve hablando.

**`CU-CHO-18` es nuevo y no es una variante de `CU-CHO-12`.** Chocar y quedarse tirado son dos
procedimientos distintos (RN-16). En la avería la unidad falla sola, llega grúa o mecánico, y solo
se bloquea el arrastre si fue en vialidad pública. En el choque hay impacto y casi siempre un
tercero: se avisa a **Edgar**, se levanta parte de accidente con daños y terceros, la unidad **no
se mueve** hasta que haya peritaje, y termina en carrocería con un deducible de por medio.
Hoy los dos caben en el mismo formulario, así que un choque se acaba describiendo en el campo
«falla» y el gerente no puede ni contar cuántos hubo en el año.

### 3.3 Supervisor — CU-SUP (10)

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-SUP-01 | Consultar mi plantilla y mi flotilla | Supervisor | Must |
| CU-SUP-02 | Monitorear conductores y unidades en tiempo real | Supervisor | Must |
| CU-SUP-03 | Consultar préstamos activos | Supervisor | Must |
| CU-SUP-04 | Autorizar o vetar un préstamo | Supervisor, Chofer | Should |
| CU-SUP-05 | Consultar estado de la unidad | Supervisor | Must |
| CU-SUP-06 | Atender alerta de unidad varada | Supervisor | Must |
| CU-SUP-07 | Escalar auxilio sin respuesta | Supervisor, Chofer de grúa, Mecánico autónomo | Should |
| CU-SUP-08 | Consultar cumplimiento de mantenimiento de la plantilla | Supervisor | Should |
| **CU-SUP-09** | **Consultar citas de taller de mi plantilla** | Supervisor | Should |
| **CU-SUP-10** | **Emitir y consultar amonestaciones de mi plantilla** | Supervisor, Chofer, Gerente | Must |

**`CU-SUP-10` solo se puede disparar sobre una cita confirmada e incumplida.** Si el taller nunca
dio cita, o si no hubo cupo antes de la fecha límite, el sistema **no deja emitir la amonestación**
— y la meta de 5 a 7 preventivos al día (RN-12) es la que lo prueba. Se aplica al **poseedor** de
la unidad, no al titular. **Pendiente:** confirmar con el cliente si la firma el supervisor, Erick
o el gerente, y qué pasa a la segunda.

### 3.4 Administrador — taller y agenda · CU-ADM-01 a 16

**Pedro** · piso y almacén:

| ID | Caso de uso | Prioridad |
|---|---|---|
| CU-ADM-01 | Atender solicitud de ingreso al taller | Must |
| CU-ADM-02 | Verificar disponibilidad de espacios | Must |
| CU-ADM-03 | Gestionar espacios del taller | Must |
| CU-ADM-04 | Colocar o retirar unidad de un espacio | Must |
| CU-ADM-05 | Asignar cola de especialistas al vehículo | Must |
| CU-ADM-06 | Reordenar la cola de trabajo | Should |
| CU-ADM-07 | Emitir hoja de trabajo en papel | Must |
| CU-ADM-08 | Capturar diagnóstico del mecánico | Must |
| CU-ADM-09 | Registrar avance y término de la reparación | Must |
| CU-ADM-10 | Emitir formato de salida | Must |
| **CU-ADM-11** | **Consultar existencia en almacén** | Must |
| **CU-ADM-12** | **Surtir pieza de almacén** | Must |

**Víctor** · agenda:

| ID | Caso de uso | Prioridad |
|---|---|---|
| **CU-ADM-13** | **Agendar mantenimiento preventivo** | Must |
| **CU-ADM-14** | **Confirmar cita propuesta por el sistema** | Must |
| **CU-ADM-15** | **Autorizar reprogramación a menos de 48 h** | Must |
| **CU-ADM-16** | **Atender alerta de capacidad sin cupo** | Must |

`CU-ADM-07` a `CU-ADM-09` **existen únicamente por los mecánicos de Álamos**. Los autónomos
capturan lo suyo.

> **v1.3 — la captura del piso se unifica en el formato.** `CU-ADM-05/06` (cola de especialistas),
> `CU-ADM-08` (diagnóstico), `CU-ADM-09` (avance) y `CU-ADM-10` (formato de salida) pedían **lo
> mismo** que el reporte de mantenimiento: quién atiende, qué hay que hacerle, qué se le hizo y
> cuándo sale. Cuatro capturas duplicadas, con dos resultados que podían no coincidir.
>
> La pantalla de Órdenes queda de **consulta**: folio, estado, días en taller y el enlace con
> presupuestos y órdenes de compra, que es lo que el formato no cubre y de lo que dependen Erick
> y el gerente. `AsignacionTecnico` y `FormatoSalida` **siguen en el modelo** —hay órdenes viejas
> capturadas así y el historial del gerente las lee— pero ya no se editan desde ahí.
>
> La orden es el expediente administrativo de la estancia; el formato es el papel del piso. Se
> cruzan, no se duplican.

### 3.5 Administrador — compras y enlace · CU-ADM-17 a 25 (**Erick**)

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-ADM-17 | Capturar presupuesto del mecánico | Erick, Mecánico asistido | Must |
| CU-ADM-18 | Registrar piezas faltantes | Erick | Must |
| CU-ADM-19 | Remitir presupuesto al gerente | Erick, Gerente | Must |
| **CU-ADM-20** | **Evaluar solicitud de pieza del mecánico autónomo** | Erick, Mecánico autónomo | Must |
| CU-ADM-21 | Autorizar orden de compra de piezas | Erick, Almacén | Must |
| CU-ADM-22 | Dar seguimiento a piezas en camino | Erick, Proveedor | Should |
| CU-ADM-23 | Registrar aviso al mecánico del resultado | Erick, Mecánico asistido | Must |
| **CU-ADM-24** | **Atender aviso de incumplimiento** | Erick, Gerente, Chofer | Must |
| **CU-ADM-25** | **Autorizar traslado de unidad a Álamos** | Erick, Mecánico autónomo | Must |

> **RN-13 (v1.4).** Una unidad que **ya está en el taller no puede pedir ingreso**, y no puede
> tener dos solicitudes vivas a la vez. Antes se dejaba levantar la solicitud y el bloqueo aparecía
> hasta que el administrador intentaba aceptarla: el chofer esperaba respuesta a algo que nunca se
> iba a poder aceptar, y la bandeja se llenaba de solicitudes muertas. El «no» tiene que llegar al
> crearla, con el folio de la orden que la tiene adentro.

### 3.5b Administrador — reporte de mantenimiento · CU-ADM-26 a 31

El formato de papel que hoy se llena a mano en la pluma de Álamos: revisión rápida de 11
puntos, los 10 sistemas del vehículo y las 5 firmas del pie. Es **la entrada** de la unidad,
no la reparación: se levanta cuando cruza la pluma, antes de que exista orden, espacio o
diagnóstico.

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| **CU-ADM-26** | **Levantar el reporte al recibir la unidad** | Pedro, Chofer | Must |
| **CU-ADM-27** | **Capturar actividades por sistema del vehículo** | Pedro, Mecánico asistido | Must |
| **CU-ADM-28** | **Registrar firma del formato** | Pedro | Must |
| **CU-ADM-29** | **Cerrar el formato y sellar la salida** | Pedro | Must |
| **CU-ADM-30** | **Reasignar el responsable de un sistema** | Pedro | Must |
| **CU-ADM-31** | **Adjuntar la evidencia fotográfica del preventivo** | Pedro, Mecánico asistido | Must |

Reglas que hace cumplir:

- Una unidad **no puede tener dos formatos abiertos** a la vez. Validado en el controlador y
  con índice único parcial en la base (`uq_reporte_abierto_por_unidad`), porque dos peticiones
  simultáneas pasan la validación al mismo tiempo.
- **No se cierra sin las dos firmas de salida** (Vo. Bo. del jefe de mantenimiento y quien
  recibe la unidad). El error dice cuáles faltan, no «409».
- **Un preventivo no se cierra sin foto (RN-15, v2.1).** La firma prueba que alguien cerró el
  formato; la foto prueba que el trabajo se hizo. La evidencia se **comprime en el teléfono antes
  de subirse** —imagen redimensionada, no el original de la cámara—: con 5 a 7 preventivos al día
  y varias fotos cada uno, el original acumula cientos de MB al mes en un servidor que ya está
  pagado. **Pendiente:** qué fotos exactamente (¿pieza vieja, pieza nueva, odómetro?) y cuántas
  por servicio; sin una lista, cada quien sube lo que se le ocurre y la evidencia no compara nada.
- Un formato **cerrado no se reescribe**. Para corregirlo se levanta otro: un papel firmado
  que se edita sin dejar rastro deja de servir como prueba.
- La **revisión rápida se captura solo al ingresar**: es el estado en que se recibió la unidad.
- RN-11: cada actividad guarda **quién la hizo** (el técnico) y **quién la tecleó** (el admin).
- **Cerrar el formato ES la salida (v1.4).** Cierra la orden, libera el cajón y saca la unidad del
  taller, todo en la misma transacción. Antes eran dos botones en dos pantallas: hacer uno sin el
  otro dejaba la unidad a medio salir —el cajón libre pero el formato abierto, o al revés— y en el
  plano seguía apareciendo adentro. `taller_actual_id` se limpia **salga operativa o no**: que una
  unidad salga descompuesta no significa que siga en el taller, y eso lo dice `estado`.
- **El formato impreso cabe en UNA hoja.** Medido en el peor caso (los diez sistemas con texto en
  las dos columnas y las cinco firmas): 861 px de los 996 útiles de una carta. Si se parte en dos,
  la segunda hoja se despega y el formato deja de servir como documento.
- **Reasignar exige motivo.** Reasignar no es corregir un dato mal tecleado: es que a alguien se
  le atravesó otro trabajo. Sin el motivo son indistinguibles, y solo la primera hay que poder
  explicarla. El cambio se asienta en bitácora con el nombre **anterior**, no solo con el nuevo.

**Cambio de alcance (v1.3).** El formato ya **no se levanta a mano** como camino normal: nace en
`CU-ADM-01`, al aceptar el ingreso, y se queda abierto. Antes había que acordarse, y el papel
existía siempre pero el registro no: quedaban unidades adentro del taller sin formato — justo lo
que el formato existe para evitar. «Levantar a mano» sobrevive para lo que entra por la pluma sin
haber pedido cita (un arrastre de madrugada).

**Puerta de entrada.** Al tocar una casilla ocupada del plano (`CU-ADM-04`) sale el formato de esa
unidad, quién la está atendiendo y qué administrador la colocó ahí. El administrador está parado
frente al vehículo, no buscando un folio.

**Buscador.** `CU-ADM-26` incluye buscar formatos por unidad o folio, por rango de fechas y por
trabajador que aparezca en ellos. Los tres criterios se combinan: «los formatos de Ramón en
agosto» es una pregunta, no tres búsquedas que alguien tenga que cruzar de memoria.

### 3.6 Mecánico autónomo — CU-MEC (12) · **módulo nuevo**

Solo los seis de las plantas satélite: Tecate, Rosarito, Guaycura (2), Carranza y Valle Redondo.

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-MEC-01 | Consultar mi cola de trabajo | Mecánico autónomo | Must |
| CU-MEC-02 | Registrar diagnóstico de la unidad | Mecánico autónomo | Must |
| CU-MEC-03 | Consultar existencia de pieza | Mecánico autónomo, Almacén | Must |
| CU-MEC-04 | Solicitar pieza al almacén de Álamos | Mecánico autónomo | Must |
| CU-MEC-05 | Consultar estatus de mi solicitud de pieza | Mecánico autónomo, Erick | Must |
| CU-MEC-06 | Registrar avance y término de la reparación | Mecánico autónomo | Must |
| CU-MEC-07 | Recibir orden de auxilio difundida | Mecánico autónomo | Must |
| CU-MEC-08 | Aceptar o rechazar el auxilio | Mecánico autónomo | Must |
| CU-MEC-09 | Transmitir mi ubicación al chofer | Mecánico autónomo, Chofer | Must |
| CU-MEC-10 | Cerrar auxilio en sitio | Mecánico autónomo | Must |
| CU-MEC-11 | Enviar unidad a Álamos | Mecánico autónomo, Chofer de grúa | Must |
| CU-MEC-12 | Emitir formato de salida | Mecánico autónomo | Must |

### 3.7 Chofer de grúa — CU-MON (8)

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-MON-01 | Recibir alerta de unidad varada | Chofer de grúa, Supervisor | Must |
| CU-MON-02 | Aceptar o rechazar el arrastre | Chofer de grúa | Must |
| CU-MON-03 | Transmitir mi ubicación en tiempo real | Chofer de grúa, Chofer | Must |
| CU-MON-04 | Registrar llegada al sitio | Chofer de grúa | Should |
| CU-MON-05 | Cerrar arrastre y registrar taller destino | Chofer de grúa, Pedro | Must |
| CU-MON-06 | Adjuntar evidencia fotográfica | Chofer de grúa | Should |
| **CU-MON-07** | **Ejecutar traslado entre plantas** | Chofer de grúa, Mecánico autónomo | Must |
| CU-MON-08 | Consultar historial de arrastres | Chofer de grúa | Should |

### 3.8 Gerente — CU-GER (14)

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-GER-01 | Consultar dashboard general | Gerente | Must |
| CU-GER-02 | Consultar incumplimiento de mantenimiento preventivo | Gerente | Must |
| CU-GER-03 | Consultar ocupación de los talleres en tiempo real | Gerente | Must |
| CU-GER-04 | Consultar historial de taller | Gerente | Must |
| CU-GER-05 | Consultar piezas en camino por unidad | Gerente | Must |
| CU-GER-06 | Consultar tiempo de permanencia por unidad | Gerente | Must |
| CU-GER-07 | Atender alerta de unidad con más de 3 meses parada | Gerente, Programador | Must |
| CU-GER-08 | Aprobar o rechazar presupuesto | Gerente, Erick | Must |
| CU-GER-09 | Consultar unidades atendidas por periodo | Gerente | Must |
| **CU-GER-10** | **Atender aviso de incumplimiento** | Gerente, Erick, Chofer | Must |
| **CU-GER-11** | **Comparar desempeño entre plantas** | Gerente | Should |
| **CU-GER-12** | **Consultar las estadísticas por día, mes y año, en gráficos** | Gerente | Must |
| **CU-GER-13** | **Consultar el historial acumulado de un chofer** | Gerente | Must |
| **CU-GER-14** | **Consultar el cumplimiento por chofer, por mes y por año** | Gerente | Must |

**Los tres son la misma petición vista desde ángulos distintos** y conviene no partirlos en tres
pantallas sueltas. El gerente pidió dos cosas: que **todo** el tablero tenga un eje de tiempo —día,
mes, año, no solo el ahora— y que se lea **en gráficos**, no en tablas. `CU-GER-13` es el
expediente del chofer, el equivalente al de la unidad: citas confirmadas contra cumplidas,
amonestaciones, préstamos recibidos, averías y choques. Sirve para sostener una amonestación **y
para defender** al chofer al que el taller nunca le dio cita.

Encima va la meta de RN-12: la tendencia de preventivos por día contra la banda de 5 a 7, con los
días por debajo del piso marcados. Es el indicador que dice si el incumplimiento fue del chofer o
del taller.

> **Lo que hay que resolver antes de dibujar el primer gráfico.** Esto pide **datos agregados
> históricos**, no el estado actual. La base guarda hoy el presente de cada unidad; para una serie
> por mes y por año hay que decidir si se agrega al vuelo sobre la bitácora o si se materializan
> cortes periódicos. Es una decisión de modelo, no de interfaz.

### 3.9 Capturista de datos — CU-CAP (5) · **módulo nuevo**

El puesto ya existe y no lo inventamos: en la hoja `TALLER` de
`INFO CHOFERES 2026 ACTUAL.xlsx`, el empleado **13905 — DOMÍNGUEZ SÁNCHEZ, JAIME YAIR** aparece
con el puesto **CAPTURISTA DE DATOS**. Su herramienta de hoy es el libro `REQUIS 2026 2.xlsx`:
una hoja de Excel por cada papel que le baja el taller.

| ID | Caso de uso | Qué aporta sobre el Excel | Prioridad |
|---|---|---|---|
| CU-CAP-01 | Consultar el resumen de lo capturado | El Excel no se puede medir a sí mismo | Should |
| CU-CAP-02 | Buscar una requisición por folio, unidad o solicitante | Hoy se busca hoja por hoja entre 100 | Must |
| CU-CAP-03 | Capturar una requisición | Avisa si el papel ya se tecleó; guarda quién lo tecleó | Must |
| CU-CAP-04 | Buscar la unidad por número económico | Casa «BG-354P» con «BG354P» | Must |
| CU-CAP-05 | Revisar los códigos que el catálogo no reconoce | En el Excel no se ven: quedan como texto suelto | Should |

**Total: 106 casos de uso** (99 + los 7 de la junta del 2026-09-14).

Más **13 propuestos** y no aprobados del módulo de auditorías de campo: los 12 CU-AUD de §3.11
y CU-AUT-09. Se cuentan aparte a propósito — el módulo depende de una respuesta del cliente
(ver [`auditorias-de-campo.md`](auditorias-de-campo.md)).

---

### 3.10 Automáticos — CU-AUT (9)

| ID | Caso de uso | Regla | Prioridad |
|---|---|---|---|
| CU-AUT-01 | Generar aviso de incumplimiento | RN-05 | Must |
| CU-AUT-02 | Generar alerta de unidad con más de 3 meses parada | RN-08 | Must |
| CU-AUT-03 | Cerrar préstamos vencidos | RN-03 | Must |
| **CU-AUT-04** | **Recalcular la agenda de mantenimiento** | 5 disparadores | Must |
| **CU-AUT-05** | **Enviar avisos de cita a 48 h y 24 h** | — | Must |
| **CU-AUT-06** | **Recalibrar duraciones de servicio** | — | Should |
| **CU-AUT-07** | **Escalar auxilio sin respuesta** | — | Must |
| **CU-AUT-08** | **Proponer la amonestación por cita confirmada incumplida** | RN-14 | Must |
| **CU-AUT-09** | **Alertar por reincidencia en auditorías de campo** | RN-14, CU-AUD-12 | Should |

**`CU-AUT-08` propone, no sanciona.** El reloj detecta que la cita confirmada pasó sin que la
unidad entrara y arma la amonestación con todo lo que hace falta para sostenerla: la cita, el
**poseedor** de ese día y el historial del chofer. Quien la emite es una persona (`CU-SUP-10`).
Una sanción que sale sola de un `cron` es la que nadie puede explicar cuando el chofer reclama —y
según RN-14 hay casos en que **no debe existir**: si el taller nunca dio cita, o si no hubo cupo
antes de la fecha límite, el problema es del taller.

---

### 3.11 Auditorías de campo a reparto — CU-AUD (12) · **módulo propuesto**

> **No está aprobado todavía.** Sale de los dos documentos que entregó el cliente; el análisis, los
> tres choques con el alcance actual y las cinco preguntas abiertas están en
> [`auditorias-de-campo.md`](auditorias-de-campo.md). El modelo de datos es el Paquete I de
> [`modelo-er-mermaid.md`](modelo-er-mermaid.md).

Auditar es de **reparto**, no de taller: el supervisor sale a la colonia donde el chofer está
repartiendo y documenta lo que ve. Entra aquí porque los actores son los mismos —los 13
supervisores y los 435 choferes ya tienen cuenta— y porque el sistema ya sabe la mitad de lo que
el formato pregunta.

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-AUD-01 | Levantar una auditoría de campo | Supervisor, Chofer | Must |
| CU-AUD-02 | Capturar evidencia fotográfica con GPS, hora y sello | Supervisor | Must |
| CU-AUD-03 | Contestar control operativo y seguridad (10 puntos) | Supervisor | Must |
| CU-AUD-04 | Contestar ejecución comercial en campo (8 puntos) | Supervisor | Must |
| CU-AUD-05 | Registrar el inventario de envases 10/20/45 kg | Supervisor | Must |
| CU-AUD-06 | Registrar la observación de productividad | Supervisor | **Condicionado** |
| CU-AUD-07 | Registrar hallazgo, compromiso y resultado | Supervisor | Must |
| CU-AUD-08 | Firmar y cerrar la auditoría | Supervisor, Chofer | Must |
| CU-AUD-09 | Sincronizar las auditorías levantadas sin conexión | Supervisor, Programador | Must |
| CU-AUD-10 | Consultar y filtrar auditorías | Supervisor, Gerente | Must |
| CU-AUD-11 | Exportar el reporte de auditorías | Gerente | Should |
| CU-AUD-12 | Consultar el historial de auditorías de un chofer | Gerente, Supervisor | Must |

**`CU-AUD-01` no arranca en blanco.** Al escoger al chofer, el sistema ya trae su ruta
(`Chofer.ruta`), la unidad que trae hoy —el **poseedor**, no el titular (RN-01)— y el odómetro
(`Unidad.km_actual`). Y contesta solo la primera casilla del formato: «licencia vigente» sale de
`Chofer.vencimiento_licencia`. Hoy el supervisor le pide la licencia al chofer y la mira; una
auditoría que solo transcribe el papel no aporta eso.

**`CU-AUD-02` es el caso de uso que decide el proyecto.** El cliente pidió que la foto se tome
desde la app y que **no** se pueda subir de la galería. En un navegador eso no se puede garantizar
—`capture` es una sugerencia, no una restricción— así que de la respuesta del cliente depende si
este módulo vive aquí o es una app aparte. Mientras tanto, el caso de uso asume el camino de
compensar: GPS con precisión obligatoria (RN-18), hora de servidor cuando hay señal, hash para
detectar la misma foto repetida, y el sello puesto **en el servidor**, no en el cliente. Un sello
que dibuja el teléfono lo puede dibujar cualquiera.

**`CU-AUD-06` está condicionado a propósito.** Pide kg vendidos y piezas de 10 y 45 kg, y eso está
declarado fuera de alcance en `requerimientos.md` §1 y como Won't en RF-SUP-11. Se diseñó en su
propia tabla para que, si el cliente confirma que no entra, se borre una tabla en vez de
desenredar ocho columnas de la cabecera.

**`CU-AUD-09` es lo más caro del módulo y no se ve.** En el taller se podía vivir sin offline —el
administrador está frente a un escritorio—. En campo no: la auditoría se levanta donde hay zonas
sin cobertura, y si la app exige conexión, se levanta en papel y volvimos al principio. Cola
local, reintentos, fotos pesadas esperando señal y una regla de qué pasa si la misma auditoría se
sincroniza dos veces (de ahí el `UNIQUE(auditoria_id, punto_id)` del Paquete I).

**`CU-AUD-08` cierra y congela.** Una auditoría firmada no se reescribe, igual que el formato de
mantenimiento en CU-ADM-29. Para corregir se levanta otra.

**`CU-AUD-12` no es una pantalla nueva.** Es el mismo expediente del chofer de RF-GER-16, con las
auditorías dentro. Dos historiales paralelos del mismo chofer —uno de mantenimiento y otro de
reparto— es como se pierden las reincidencias.

---

## 4. Relaciones «include» y «extend»

- **«include»** = el caso base **siempre** ejecuta al incluido. Obligatorio.
- **«extend»** = ocurre **solo bajo una condición**. Opcional.

| Origen | → | Destino | Tipo | Condición |
|---|---|---|---|---|
| CU-CHO-03 Registrar jornada | → | CU-CHO-04 Checklist | «include» | No se abre jornada sin checklist |
| CU-CHO-11 Reportar avería | → | CU-CHO-13 Compartir ubicación | «include» | La ubicación es parte del reporte |
| CU-CHO-11 | → | CU-CHO-12 Aviso a peritos | «extend» | **Solo en vialidad pública** (RN-04) |
| CU-CHO-11 | → | CU-CHO-14 Solicitar auxilio mecánico | «extend» | Si la falla puede resolverse en sitio |
| CU-CHO-11 | → | CU-CHO-15 Solicitar arrastre | «extend» | Si la unidad no puede moverse |
| CU-ADM-01 Atender solicitud | → | CU-ADM-02 Verificar espacios | «include» | Nunca se decide sin revisar (RN-06) |
| CU-ADM-05 Asignar cola | → | CU-ADM-06 Reordenar | «extend» | Solo si cambia la prioridad |
| CU-ADM-17 Capturar presupuesto | → | CU-ADM-18 Registrar piezas faltantes | «include» | No hay presupuesto sin desglose |
| CU-MEC-04 Solicitar pieza | → | CU-MEC-03 Consultar existencia | «include» | Nunca se pide sin consultar antes |
| CU-MEC-08 Aceptar auxilio | → | CU-MEC-09 Transmitir ubicación | «include» | El chofer debe poder verlo venir |
| CU-MON-05 Cerrar arrastre | → | CU-MON-06 Adjuntar evidencia | «include» | Protege contra reclamos de daño |
| CU-SUP-06 Atender alerta | → | CU-SUP-07 Escalar | «extend» | Solo si nadie aceptó la difusión |

---

## 5. Los tres mecanismos nuevos, explicados

### CU-CHO-14 + CU-MEC-07/08 — el auxilio se difunde, no se asigna

El chofer marca su ubicación y **la orden va a todos los mecánicos autónomos disponibles**,
ordenados por distancia a su planta. Cada uno decide según su zona y su carga; **el primero que
acepta la gana** y los demás dejan de verla.

Dos detalles que hay que resolver al programarlo:

1. **Condición de carrera.** Dos aceptan a la vez. Se resuelve con `UPDATE ... WHERE estado =
   'difundida'`, no comprobando antes y escribiendo después.
2. **Que nadie acepte.** Pasados N minutos entra `CU-AUT-07` y luego `CU-SUP-07`.

Y se guarda **quién dijo que no y por qué** (`RESPUESTA_AUXILIO`). Sin eso, un silencio de 20
minutos no se puede distinguir de "todos ocupados", "la unidad está lejos de todos" o "nadie abrió
la app".

### CU-MEC-03/04/05 — la pieza

```
Mecánico → consulta existencia en el almacén de Álamos
   ├── HAY   → se surte y se envía a la planta
   └── NO HAY → solicitud → Erick evalúa
                    ├── aprueba → orden de compra → en tránsito → recibida
                    └── rechaza → con motivo
```

`CU-MEC-05` responde justo lo que pediste: **si ya llegó, si está en proceso, o cuándo llega.**

### CU-ADM-13/14/15 + CU-CHO-07 — la agenda invierte quién empieza

Antes el chofer solicitaba el ingreso preventivo. Ahora **Víctor agenda y el chofer confirma**.
Eso saca el conflicto de interés del camino crítico: el chofer ya no puede "olvidar" pedir taller,
porque no depende de él.

`CU-CHO-05` sobrevive **solo para el correctivo** — se descompuso algo y hay que entrar.

---

## 6. Lo que hay que poder defender

1. **"Prestar unidad" y "Recibir unidad prestada" son dos casos, no uno.** Los inician actores
   distintos y el préstamo no surte efecto hasta que el receptor acepta. Unirlos escondería el
   momento exacto en que cambia la responsabilidad.

2. **"Registrar aviso a peritos" es «extend», no «include».** Solo aplica en vialidad pública. Si
   fuera «include», obligarías a llamar peritos cuando la unidad se descompone en el patio.

3. **Los cuatro administradores son cuatro actores.** Con permisos distintos, no un rol con cuatro
   cuentas. Pablo no aparece con casos propios porque **cubre por suplencia de perfil**
   (`CU-GEN-05`), que es un mecanismo distinto de tener sus propios permisos.

4. **El mecánico aparece dos veces y de dos formas.** Autónomo con línea continua (opera el
   sistema), asistido con línea punteada (no lo toca). Es la misma profesión con dos relaciones
   distintas con el software, y el diagrama tiene que mostrarlo.

5. **Los casos automáticos tienen actor.** Un caso de uso sin actor está mal formado; por eso el
   Programador de tareas.

6. **"Consultar dashboard" no incluye a los otros consultar-*.** Es una vista agregada, no una
   composición. Nueve flechas «include» ahí serían ruido, no información.

---

## 7. Qué cambió respecto de la v1.1

| Cambio | Efecto |
|---|---|
| Vuelve el módulo Mecánico (solo autónomos) | +12 casos, y `CU-SUP-09` de la v1.1 desaparece porque ya no hace falta que el supervisor registre el envío del mecánico |
| Multi-planta | `CU-GER-03` pasa a plural, aparece `CU-GER-11` |
| Agenda automática | +4 de Víctor, +1 del chofer, +3 automáticos |
| Almacén consultable | +2 de Pedro, +3 del mecánico |
| Traslado entre plantas | `CU-MEC-11`, `CU-MON-07`, `CU-ADM-25` |
| Aviso en vez de penalización | `CU-ADM-24`, `CU-GER-10`; se elimina "Levantar inconformidad" |
| Suplencia de perfil | `CU-GEN-05` |

---

## 8. Preguntas abiertas que cambian el diagrama

1. **¿El mecánico autónomo elabora presupuesto o solo pide piezas?** Hoy solo pide piezas. Si
   además presupuesta mano de obra, entra al flujo de `CU-ADM-19` → `CU-GER-08` y le tocan dos
   casos más.
2. **¿Puede ocupar y liberar los espacios de su propio taller?** Hoy no: eso es de Pedro, como
   pediste. Sería un caso más en el módulo 5.
3. **¿El préstamo requiere visto bueno del supervisor?** Si no, `CU-SUP-04` desaparece.
4. **¿Hay monto máximo que Erick apruebe sin gerente?** Sería `CU-ADM-26 Aprobar presupuesto menor`
   y un flujo alterno en la cadena.
5. **¿Un mecánico autónomo puede atender una unidad de otra planta varada en su zona?** El modelo
   lo permite (la difusión va a todos). Confirmar que operativamente está bien.
