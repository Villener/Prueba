# Sistema de Gestión de Flota y Taller — Baja Gas

Prototipo funcional construido sobre los documentos de análisis que están en [`docs/`](docs/).
**React** en el frontend, **Python (FastAPI)** en el backend. Responsivo: el chofer y el
montacarguista trabajan desde el teléfono, el administrador y el gerente desde escritorio.

> **v1.1** — Los mecánicos **no usan la aplicación**. Son 5 módulos, no 6. El administrador
> captura el trabajo que el mecánico le entrega en papel, y todo dato capturado guarda dos
> responsables: quién lo hizo y quién lo tecleó.

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

| Correo | Rol | Para qué sirve en el demo |
|---|---|---|
| `gerente@bajagas.mx` | Gerente | Tablero, aprobar presupuestos, alertas |
| `admin@bajagas.mx` | Administrador | Espacios, colas de trabajo, captura del mecánico |
| `supervisor@bajagas.mx` | Supervisor | Cuadrilla, préstamos, despacho de apoyo |
| `chofer1@bajagas.mx` | Chofer (Luis) | Titular de la U-101, presta unidades |
| `chofer2@bajagas.mx` | Chofer (Ana) | Recibe unidades prestadas |
| `montacargas@bajagas.mx` | Montacarguista | Arrastres |

Los mecánicos **no tienen cuenta**: están en el catálogo `TECNICO` y se les asigna trabajo, pero
no inician sesión.

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

En *Plano* está el taller tal como viene en el Excel del cliente: 12 zonas, 44 espacios
operativos. El **yonke (45 posiciones)** y el **área de lavado** aparecen atenuados porque no
cuentan para la ocupación; si contaran, el indicador del gerente saldría inflado.

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

---

## Estructura

```
backend/
  app/
    models.py       38 entidades — implementa docs/modelo-er.md
    services.py     reglas de negocio y restricciones RI-01..RI-13
    security.py     JWT, hash de contraseñas, RBAC por rol
    jobs.py         CU-AUT-01..03: penalizaciones, alertas, préstamos vencidos
    seed.py         datos semilla, incluido el plano del taller
    routers/        un archivo por módulo
frontend/
  src/
    api.js          cliente HTTP, sesión y formatos
    App.jsx         ruteo por rol (nav inferior en móvil, lateral en escritorio)
    components/ui.jsx  Card, Tabla, Modal, Badge, useApi, toasts
    pages/          Chofer, Supervisor, Administrador, Montacarguista, Gerente
docs/
  requerimientos.md   88 requerimientos con MoSCoW y roadmap
  modelo-er.md        modelo entidad-relación
  casos-de-uso.md     63 casos de uso
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
| RF-GEN-11 Exportar a PDF/Excel | **No** | La hoja de trabajo usa la impresión del navegador. |
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
