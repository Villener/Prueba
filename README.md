# Sistema de Gestión de Flota y Taller — Baja Gas

Prototipo funcional construido sobre los documentos de análisis que están en [`docs/`](docs/).
**React** en el frontend, **Python (FastAPI)** en el backend. Responsivo: el chofer y el
montacarguista trabajan desde el teléfono, el administrador y el gerente desde escritorio.

> **v1.1** — Los mecánicos **no usan la aplicación**. El administrador captura el trabajo que el
> mecánico le entrega en papel, y todo dato capturado guarda dos responsables: quién lo hizo y
> quién lo tecleó.
>
> **v1.2** — Se agrega el módulo del **capturista de datos**, que es un puesto real del taller de
> Álamos (empleado 13905). Son 6 módulos. Su trabajo diario —el libro `REQUIS`— entra al sistema
> como entidad propia: **99 requisiciones reales con 383 renglones**, importadas del Excel.
>
> **v1.3** — Entra el **REPORTE DE MANTENIMIENTO**: el formato de papel que se llena en la
> pluma de Álamos, con su revisión rápida de 11 puntos, los 10 sistemas del vehículo y las 5
> firmas del pie. Se captura y se imprime tal como está impreso el papel.
>
> El formato **nace con el ingreso** —al aceptar la solicitud— y se queda abierto; el plano es su
> puerta de entrada; y la pantalla de **Órdenes pasa a ser de consulta**, porque pedía las mismas
> cuatro capturas que el formato.
>
> **v1.4** — El plano de Álamos se dibuja como el **croquis del Excel**: las dos filas de cajones
> enfrentadas, el pasillo de circulación en medio, salida y entrada a los lados, y el patio, el
> lavado y el yonke aparte. **Cerrar el formato ES la salida**: se libera el cajón, se cierra la
> orden y la unidad deja de estar en el taller. Una unidad que ya está adentro **no puede pedir
> ingreso**. Y el formato impreso **cabe en una hoja**.
>
> **v1.5** — El croquis se corrige contra lo que hay en el piso: la fosa son **cuatro** lugares, el
> patio son **55** en dos bloques (diez arriba, cuarenta y cinco abajo) y el **yonke no guarda
> vehículos**, guarda piezas y partes. Las puertas quedan fijas a los extremos aunque el croquis
> ruede de lado. Y al asignarle lugar a una unidad, el sistema **te lleva a su formato**.

---

## Cómo correrlo

Necesitas dos terminales.

**1. Backend** (puerto 8000):

```bash
cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --reload --port 8000
```

**2. Frontend** (puerto 5173):

```bash
cd frontend && npm install && npm run dev
```

Abre <http://localhost:5173>. La documentación interactiva de la API queda en
<http://127.0.0.1:8000/docs>.

La base (SQLite, `backend/bajagas.db`) se crea y se siembra sola al arrancar. Para empezar de
cero, borra ese archivo.

### Usuarios de prueba

Todos con la contraseña `demo1234`:

Todas son **personas reales** del Excel del cliente, con su número de empleado. La convención de
correo es la misma para todos:

- con número de empleado → `e<num>@bajagas.mx`
- sin número (los supervisores no lo traen en el Excel) → `<nombre+sucursal, 12 letras>@bajagas.mx`

| Correo | Rol | Persona | Para qué sirve en el demo |
|---|---|---|---|
| `gerente@bajagas.mx` | Gerente | Luis Siscareño | Tablero, aprobar presupuestos, alertas |
| `e925@bajagas.mx` | Administrador | Erick Ávalos | Presupuestos, compras, enlace con gerencia |
| `e10853@bajagas.mx` | Administrador | Pedro Montaño | Espacios, colas de trabajo, almacén |
| `e647@bajagas.mx` | Administrador | Víctor Sallas | Agenda de mantenimiento |
| `e13905@bajagas.mx` | **Capturista** | Jaime Yair Domínguez | Las 99 requisiciones del libro `REQUIS` |
| `ricardoandre@bajagas.mx` | **Supervisor** | Ricardo Andrés Flores | Carranza, la cuadrilla más grande: **55 choferes** |
| `e3145@bajagas.mx` | **Chofer** | Blas Mauricio Cota | Titular de la **1009**, Tecate |
| `e4932@bajagas.mx` | Montacarguista | Rubén Espejo | Arrastres |

**Los 297 choferes y los 13 supervisores tienen cuenta**, no solo los de arriba: los crea el
importador desde `INFO CHOFERES 2026 ACTUAL.xlsx`. Los de la tabla son solo la puerta de entrada
al demo; a cualquier otro se entra con su correo.

Los mecánicos **no tienen cuenta**: están en el catálogo `TECNICO` y se les asigna trabajo, pero
no inician sesión. Por eso existe el capturista.

### Cargar los datos reales

Las cuentas de arriba salen del Excel, así que hay que correr el importador una vez (es
idempotente: correrlo dos veces no duplica nada):

```bash
cd backend && python -m app.importador
```

---

## Recorrido de demostración

Este guion muestra las cuatro reglas de negocio que sostienen el sistema.

### 1. La responsabilidad sigue al poseedor (RN-01)

1. Entra como **Luis** → *Préstamos* → **Prestar unidad** → se la prestas a Ana.
2. Intenta prestarla otra vez: el sistema lo bloquea (**RN-02**, una unidad no puede tener dos
   préstamos activos).
3. Entra como **Ana** → *Préstamos* → **Aceptar**. Aquí, y solo aquí, cambia la responsabilidad.
4. Entra como **Gerente** → **Correr procesos del día** → *Incumplimiento*.
   La penalización aparece **a nombre de Ana**, no de Luis, y marcada como “por préstamo”.

Ese es el problema que el cliente planteó: sin esa distinción, se penaliza al chofer equivocado.

### 2. Peritos antes que arrastre (RN-04)

1. Como **Ana** → *Averías* → **Reportar avería**, marca *Estoy en vialidad pública*.
2. El botón **Solicitar arrastre** queda deshabilitado.
3. **Registrar aviso a peritos** con su folio → el arrastre se habilita.
4. Como **Montacarguista** → aceptar, enviar ubicación, registrar llegada y **cerrar arrastre**
   indicando el taller destino. El cierre genera automáticamente la solicitud de ingreso.

### 3. No se acepta un ingreso sin espacio compatible (RN-06)

Como **Administrador** → *Solicitudes* → **Atender**. El sistema cuenta los espacios libres que
**admiten ese tipo de unidad**: una pipa no cabe en un espacio de reparto. Si no hay, solo puedes
dejarla en cola o rechazarla con motivo.

En *Plano* está el taller dibujado como el croquis del Excel: 12 zonas. **31 bahías de
reparación** —las que sí son capacidad de atención— más la fosa (4), el patio (55) y el área de
lavado (1), que admiten unidad pero aparecen atenuados porque **no cuentan para la ocupación**;
si contaran, el indicador del gerente saldría inflado. El **yonke no tiene cajones**: ahí hay
piezas y partes, no vehículos.

### 4. El presupuesto pasa por el administrador (RN-07 + RN-11)

1. Como **Administrador** → *Órdenes* → **Gestionar cola**: agregas mecánicos, carroceros y
   electricistas *en fila*, los reordenas y capturas el diagnóstico que te entregaron.
2. *Presupuestos* → **Capturar presupuesto**: eliges qué mecánico lo elaboró y qué fecha trae el
   papel. El sistema calcula el **retraso de captura**.
3. **Remitir al gerente** → el gerente aprueba, rechaza o devuelve.
4. Intenta autorizar la orden de compra antes de la aprobación: bloqueado (**RI-07**).
5. Tras la resolución, **Registrar aviso al mecánico**: el aviso es verbal, el sistema solo deja
   constancia con fecha y hora.
6. En *Hoja* imprimes la cola del día para entregarla en papel a los técnicos.

### 5. El capturista teclea un papel, y el sistema ve lo que el Excel no ve

Entra como **Jaime Yair** (`e13905@bajagas.mx`). Abre con **99 requisiciones reales** de julio y
agosto —las que ya tecleó en `REQUIS 2026 2.xlsx`—, no con una tabla vacía.

1. *Requisiciones* → busca **J332**. Salen **cinco**, con cinco unidades y tres fechas distintas:
   el folio se reutiliza en el libro real. Por eso el sistema **avisa** de un folio repetido pero
   no lo prohíbe.
2. Abre cualquiera: cada renglón dice si su código **casó contra el catálogo**. En la importación
   limpia casan 362 de 383 (94.5 %).
3. *Pendientes* → los códigos que el catálogo no reconoce, **ordenados por cuántas veces se
   pidieron**. El primero es `237334` (FILTRO DIESEL CNJ 4T) con **20 pedidos**: no es un error de
   dedo, es una refacción que el taller usa y `MATERIALES` no tiene dada de alta.
4. *Capturar* → teclea un papel. Si repites folio, fecha y unidad, el sistema te enseña la
   anterior y te obliga a decir «sí es otro papel» para guardarlo igual — la misma lógica que el
   sobrecupo de la agenda: duplicar queda como una decisión con dueño.

Lo que el Excel no puede hacer y esto sí: detectar el papel tecleado dos veces (pasó una vez,
`J299`), ligar cada renglón a la pieza del catálogo, y dejar constancia de **quién** tecleó cada
documento.

### 6. El formato de la pluma deja de ser solo papel

El `REPORTE DE MANTENIMIENTO` **no se levanta**: nace solo cuando se le da acceso al vehículo.

1. Como **Blas** (chofer) → *Taller* → **Solicitar ingreso**. Como **Pedro** → *Solicitudes* →
   **Atender**: ahí sale el croquis para elegir la casilla. Al asignarla, el sistema **te lleva
   directo al formato** de esa unidad —ya abierto, ligado a la orden, con sus 11 puntos y sus 10
   sistemas, el poseedor (RN-01) y el kilometraje—. Aceptar el ingreso y empezar el formato son el
   mismo movimiento: dejarlo en la bandeja significaba que alguien tenía que acordarse de ir a
   buscarlo a *Reportes*.
2. *Plano* → toca la casilla donde quedó. Sale **su formato**, **quién la está atendiendo** y
   **qué administrador la colocó ahí**. Cada uno atiende sus vehículos; sin ese dato nadie sabe
   a quién preguntarle.
3. **Abrir el formato** → *Capturar* llena los diez sistemas con lo que el mecánico entregó en
   papel, cada uno con su responsable. Cada renglón guarda quién lo hizo y quién lo tecleó
   (RN-11).
4. **Reasignar** un sistema: exige motivo. Se le atravesó otro trabajo al mecánico, y eso hay que
   poder explicarlo en un mes. Queda en bitácora con el nombre anterior.
5. *Reportes* → **Buscar** por unidad, por rango de fechas y por trabajador. Los tres se
   combinan.
6. **Cerrar y sellar salida** sin firmas: el sistema dice *cuáles* faltan, no «Error 409». Con el
   Vo. Bo. y la firma de quien recibe, se cierra — y ya no se puede reescribir.
7. **Imprimir**: sale la hoja sola, sin menú ni botones, con el logo en la esquina, en tinta
   negra y con los renglones en blanco donde el mecánico escribe a mano.

El **patio** es la sala de espera: admite unidades pero no cuenta como capacidad de atención, así
que estacionar ahí no infla el indicador de ocupación del gerente. Desde el menú de la casilla,
**Mover a otro espacio** lista los cajones libres agrupados por zona —con la sala de espera
marcada— y mueve la unidad ahí mismo.

### 7. Lo que el croquis dejó ver

El plano de Álamos ya no es una lista de zonas: es el dibujo del Excel. Y al dibujarlo salieron a
la luz varios datos que llevaban tiempo mal en la base, porque mientras el plano era una lista
nadie los notaba:

| | Estaba | Es |
|---|---|---|
| Fosa | 1 lugar | **4** |
| Patio | 12 lugares | **55**: diez arriba y cuarenta y cinco abajo |
| Yonke | 45 cajones para vehículos | **ninguno**: ahí hay piezas y partes |

El bloque de 45 del croquis, que estaba etiquetado como yonke, es en realidad **la parte de abajo
del patio**. `asegurar_plano` ahora cuadra el conteo contra `LAYOUT_TALLER` al arrancar: agrega lo
que falta y quita lo que sobra **solo si está libre** —una casilla de más con una unidad adentro se
deja y se reporta, porque borrarla dejaría huérfana una ocupación abierta.

---

## Estructura

Un paquete por área del diagrama de clases, con sus modelos y su controlador juntos.

```
backend/
  app/
    core/           database, security (JWT y RBAC), migraciones, tiempo
    models.py       fachada: reexporta las entidades de modules/
    services.py     reglas de negocio y restricciones RI-01..RI-13
    jobs.py         CU-AUT-*: penalizaciones, alertas, préstamos vencidos
    seed.py         catálogos, plano del taller y cuentas reales
    importador.py   carga datos/*.xlsx: personas, flota, refacciones, requisiciones
    modules/
      organizacion/ Usuario, Rol, Chofer, Supervisor, Técnico + auth
      flota/        Unidad, Préstamo, Jornada + chofer y supervisor
      taller/       Zonas, espacios, ocupación + administrador
      mantenimiento/ Planes, citas, agenda
      ordenes/      Solicitud de ingreso, orden de servicio, traslados,
                    reporte de mantenimiento (el formato de papel)
      piezas/       Pieza, Presupuesto, Compra, Requisición + capturista
      emergencias/  Avería, auxilio, arrastre + montacarguista
      sistema/      Notificaciones, bitácora + gerente
datos/              los .xlsx del cliente, versionados con el proyecto
frontend/
  src/
    core/           api.js (HTTP), sesion.js, tema.js
    ui/             Card, Tabla, Modal, Badge, useApi, toasts, BuscadorPieza
    App.jsx         ruteo por rol (nav inferior en móvil, lateral en escritorio)
    modules/        acceso, chofer, supervisor, administrador, capturista,
                    montacarguista, gerente, sistema
docs/
  requerimientos.md   requerimientos con MoSCoW y roadmap
  modelo-er.md        modelo entidad-relación
  casos-de-uso.md     catálogo de casos de uso
  diagramas/          SVG de casos de uso + index.html para verlos
```

Cada endpoint del backend cita en su docstring el caso de uso que realiza (`CU-CHO-07`,
`CU-ADM-12`, …), y cada pantalla que hace cumplir una regla la explica al usuario en su propio
texto. La trazabilidad documento → código está en `docs/modelo-er.md §11`.

---

## Decisiones técnicas

- **SQLite** por defecto para que el prototipo corra sin instalar nada. El modelo es
  relacional puro; cambiar a PostgreSQL es fijar `DATABASE_URL` — no hay SQL específico de
  SQLite en el código.
- **Autorización en el servidor**, no solo en la interfaz (RNF-04). Cada router declara
  `require_roles(...)`; si un chofer llama a un endpoint del gerente recibe 403 aunque el menú
  no se lo muestre.
- **`TECNICO` con llave primaria propia**, no colgado de `USUARIO`. Los mecánicos no tienen
  cuenta, y crear usuarios ficticios sin contraseña ensuciaría la tabla de usuarios y las
  estadísticas de acceso. Si mañana alguno recibe acceso, se agrega `TECNICO.usuario_id` como FK
  opcional y no hay que rehacer nada.
- **`AUTORIZACION` como entidad**, no como dos columnas en `PRESUPUESTO`: un presupuesto puede
  ir y venir varias veces entre gerente y administrador, y ese historial es lo que permite
  auditar por qué una unidad lleva tres semanas parada.
- **CSS propio, sin framework de UI.** Mobile-first, un solo archivo de tokens, tema claro y
  oscuro automáticos. Los inputs usan 16 px para que iOS no haga zoom al enfocarlos, y los
  botones tienen 44 px de alto para que se puedan tocar con guantes.
- **Las tablas se vuelven tarjetas** por debajo de 640 px (`.stack-mobile`) en vez de hacer
  scroll horizontal.

---

## Qué NO está implementado

Para que quede claro qué falta antes de llamarlo producto:

| Requerimiento | Estado | Nota |
|---|---|---|
| RF-GEN-06 Tiempo real por WebSocket | **No** | Las vistas leen al entrar y al accionar. Para el arrastre esto basta en el demo, pero RNF-02 (≤10 s) exige WebSocket o polling. |
| RF-GEN-09 Modo offline | **No** | La app del chofer necesita service worker y cola de sincronización. |
| RF-GEN-10 Evidencia fotográfica | **Parcial** | `EVIDENCIA` existe en el modelo y se guarda texto; falta la subida de archivos. |
| RF-SUP-06 Mapa de la cuadrilla | **Parcial** | Se muestran coordenadas y enlace a Google Maps; no hay mapa embebido. |
| RF-GEN-11 Exportar a PDF/Excel | **No** | La hoja de trabajo y el reporte usan la impresión del navegador. El reporte está medido para caber en una carta. |
| Los jobs automáticos | **Manual** | Se disparan con el botón del gerente. En producción van en un cron diario. |

Los tres primeros son *Should* en el MoSCoW, no *Must*: el sistema es usable sin ellos.

---

## Verificación hecha

- Flujo completo probado extremo a extremo contra la API: préstamo con transferencia de
  responsabilidad, bloqueo de doble préstamo, avería en vialidad pública con peritaje, arrastre
  completo, aceptación de ingreso con validación de espacio, cola de especialistas, captura de
  diagnóstico y presupuesto, cadena de aprobación y orden de compra.
- **La penalización se emitió contra la poseedora por préstamo, no contra el titular** — que es
  la prueba que importaba.
- RBAC verificado: un chofer recibe 403 al llamar endpoints del gerente.
- Frontend compila sin advertencias y se verificó en 1280×720 y 375×812 sin scroll horizontal.
