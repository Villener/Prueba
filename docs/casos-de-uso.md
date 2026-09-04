# Diagrama y catálogo de casos de uso — Sistema de Gestión de Flota y Taller (Baja Gas)

**Versión:** 2.0 · **Fecha:** 2026-08-18
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
| 6 | [06-modulo-montacarguista.svg](diagramas/06-modulo-montacarguista.svg) | 8 casos del montacarguista |
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
| **Supervisor** | Vigila una cuadrilla de choferes y sus unidades |
| **Pedro** · *piso y almacén* | Espacios, colas de técnicos, surtido de piezas, captura del trabajo de los mecánicos de Álamos |
| **Víctor** · *agenda* | Programa el mantenimiento preventivo y gestiona las citas |
| **Erick** · *compras y enlace* | Presupuestos, órdenes de compra, y el único puente con el gerente |
| **Pablo** · *operativo* | Cubre a Pedro y a Víctor **por suplencia de perfil**, no con cuenta propia |
| **Mecánico autónomo** | Los 6 de las plantas satélite. Único técnico con acceso al sistema |
| **Jaime Yair** · *capturista de datos* | Teclea las requisiciones de material del taller de Álamos. El puesto viene con ese nombre en la hoja TALLER del Excel del cliente (empleado 13905) |
| **Montacarguista** | Arrastres y traslados entre plantas |
| **Gerente** | Aprueba presupuestos, atiende alertas y avisos, consulta indicadores |

### Secundarios — participan, no inician

**Otro chofer** (recibe una unidad en préstamo) · **Almacén de Álamos** (responde consultas y
surte) · **Proveedor** (piezas en camino) · **Peritos / Aseguradora** (siniestros en vialidad
pública).

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
| CU-CHO-15 | Solicitar arrastre | Chofer, Montacarguista | Must |
| **CU-CHO-16** | **Dar seguimiento al apoyo en camino** | Chofer | Must |
| CU-CHO-17 | Consultar mis avisos de incumplimiento | Chofer | Must |

**`CU-CHO-03` sube de Should a Must.** Con la responsabilidad siguiendo a quien conduce, la
jornada dejó de ser un dato de conveniencia: es la primera rama de `poseedorActual()`.

**Se elimina "Levantar inconformidad".** Con el esquema nuevo, el gerente y Erick hablan con el
chofer en persona — **la conversación es el canal de defensa**. Un trámite paralelo dentro de la
app solo agregaría burocracia a algo que ya se resuelve hablando.

### 3.3 Supervisor — CU-SUP (9)

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-SUP-01 | Consultar mi cuadrilla | Supervisor | Must |
| CU-SUP-02 | Monitorear conductores y unidades en tiempo real | Supervisor | Must |
| CU-SUP-03 | Consultar préstamos activos | Supervisor | Must |
| CU-SUP-04 | Autorizar o vetar un préstamo | Supervisor, Chofer | Should |
| CU-SUP-05 | Consultar estado de la unidad | Supervisor | Must |
| CU-SUP-06 | Atender alerta de unidad varada | Supervisor | Must |
| CU-SUP-07 | Escalar auxilio sin respuesta | Supervisor, Montacarguista, Mecánico autónomo | Should |
| CU-SUP-08 | Consultar cumplimiento de mantenimiento de la cuadrilla | Supervisor | Should |
| **CU-SUP-09** | **Consultar citas de taller de mi cuadrilla** | Supervisor | Should |

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

### 3.5b Administrador — reporte de mantenimiento · CU-ADM-26 a 29

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

Reglas que hace cumplir:

- Una unidad **no puede tener dos formatos abiertos** a la vez. Validado en el controlador y
  con índice único parcial en la base (`uq_reporte_abierto_por_unidad`), porque dos peticiones
  simultáneas pasan la validación al mismo tiempo.
- **No se cierra sin las dos firmas de salida** (Vo. Bo. del jefe de mantenimiento y quien
  recibe la unidad). El error dice cuáles faltan, no «409».
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
| CU-MEC-11 | Enviar unidad a Álamos | Mecánico autónomo, Montacarguista | Must |
| CU-MEC-12 | Emitir formato de salida | Mecánico autónomo | Must |

### 3.7 Montacarguista — CU-MON (8)

| ID | Caso de uso | Actores | Prioridad |
|---|---|---|---|
| CU-MON-01 | Recibir alerta de unidad varada | Montacarguista, Supervisor | Must |
| CU-MON-02 | Aceptar o rechazar el arrastre | Montacarguista | Must |
| CU-MON-03 | Transmitir mi ubicación en tiempo real | Montacarguista, Chofer | Must |
| CU-MON-04 | Registrar llegada al sitio | Montacarguista | Should |
| CU-MON-05 | Cerrar arrastre y registrar taller destino | Montacarguista, Pedro | Must |
| CU-MON-06 | Adjuntar evidencia fotográfica | Montacarguista | Should |
| **CU-MON-07** | **Ejecutar traslado entre plantas** | Montacarguista, Mecánico autónomo | Must |
| CU-MON-08 | Consultar historial de arrastres | Montacarguista | Should |

### 3.8 Gerente — CU-GER (11)

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

**Total: 99 casos de uso.**

---

### 3.10 Automáticos — CU-AUT (7)

| ID | Caso de uso | Regla | Prioridad |
|---|---|---|---|
| CU-AUT-01 | Generar aviso de incumplimiento | RN-05 | Must |
| CU-AUT-02 | Generar alerta de unidad con más de 3 meses parada | RN-08 | Must |
| CU-AUT-03 | Cerrar préstamos vencidos | RN-03 | Must |
| **CU-AUT-04** | **Recalcular la agenda de mantenimiento** | 5 disparadores | Must |
| **CU-AUT-05** | **Enviar avisos de cita a 48 h y 24 h** | — | Must |
| **CU-AUT-06** | **Recalibrar duraciones de servicio** | — | Should |
| **CU-AUT-07** | **Escalar auxilio sin respuesta** | — | Must |

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
