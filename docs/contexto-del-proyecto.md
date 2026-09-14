# Contexto del proyecto — lo que no está en los otros documentos

**Para:** quien retome este proyecto en una sesión nueva.
**Fecha:** 2026-08-20
**Continúa en:** [contexto-del-proyecto-2.md](contexto-del-proyecto-2.md) — SAP,
el almacén y la sincronización web ↔ móvil. **Léelo también**: cambia quién es
dueño del dato de existencias.

Los demás documentos (`requerimientos`, `modelo-clases`, `modelo-er`,
`casos-de-uso`, `procesos`, `agenda-mantenimiento`, `arquitectura`) describen el
**diseño**. Este describe **el negocio real, las personas, y el estado del
código** — cosas que se dijeron en conversación y que no se deducen leyendo un
diagrama.

**Léelo antes de tocar nada.** Varias decisiones aquí contradicen lo que parece
obvio desde el código.

---

## 1. Qué es esto

Baja Gas distribuye gas LP en Baja California. **379 unidades, 350 choferes,
7 sucursales.** El sistema administra la flota y los talleres.

**El problema que lo origina:** los choferes ganan por comisión sobre ventas, así
que meter la unidad al taller les cuesta dinero y tienden a posponerlo. La
dirección no tiene forma de ver quién está incumpliendo ni de exigirlo. Todo lo
demás del sistema existe alrededor de eso.

Martín es estudiante de software en UABC y practicante en Baja Gas. **Trabaja en
español, corrige directo, y prefiere un paso a la vez.** Cuando algo esté mal
dicho, dilo sin rodeos: lo agradece más que la diplomacia.

---

## 2. Las personas reales y sus peculiaridades

Esto es lo más importante del documento. **No son roles genéricos: son personas
con nombre, y sus manías definen el diseño.**

### Los cuatro "administradores" no son un rol, son cuatro puestos

Modelarlos como un solo rol fue un error que ya se corrigió. Cada uno tiene
permisos distintos y **no deben poder hacer lo del otro**:

| Persona | Qué hace exactamente |
|---|---|
| **Erick** | Arma los Excel con los formatos de papel, se comunica con el gerente, manda las órdenes de compra. Es el **único enlace con gerencia**. En los datos reales aparece como `AVALOS GOMEZ, ERICK — SUP. DE MANT AUTOMOTRIZ`. |
| **Pedro** | Administra el taller: mete y saca vehículos de los espacios. Busca las piezas en el almacén; **si no hay, le avisa a Erick**. |
| **Víctor** | Agenda el mantenimiento preventivo. |
| **Pablo** | Cosas varias del área operativa; **cubre a Pedro** cuando no está. |

**Suplencias confirmadas por el cliente:** a Víctor lo cubren Pablo, Erick o
Pedro. A Pedro lo cubre Pablo. **A Erick no lo cubre nadie** — es el riesgo
abierto más grande de la operación, y está señalado en `procesos.md`.

### Los mecánicos son de DOS tipos, y es la distinción que sostiene el modelo v2.0

| | **Asistido** (Álamos) | **Autónomo** (satélites) |
|---|---|---|
| Cuántos | 31 | 6 |
| ¿Usa la app? | **No** | **Sí** |
| Quién captura su trabajo | Erick, en papel | Él mismo |
| Vehículo de servicio | No | **Sí** |
| Pide piezas | Vía Pedro/Erick | **Directo al almacén de Álamos** |

El autónomo está **solo en su planta**: por eso necesita cuenta, sale a auxiliar
unidades varadas con su propio vehículo, y puede **mandar la unidad a Álamos con
grúa** cuando no la puede reparar.

En la base: `Tecnico.modalidad` = `AUTONOMO` | `ASISTIDO`, y `Tecnico.usuario_id`
es **obligatorio para el autónomo y debe ser NULL para el asistido**. Los
asistidos no tienen login por diseño; crearles usuarios ficticios ensuciaría la
tabla de usuarios y las estadísticas de acceso.

Los seis autónomos reales, de la hoja TALLER del Excel: Carranza, Guaycura,
Rosarito, Tecate y **dos** en Valle Redondo (uno es carrocero).

### Chofer

- **Titular** ≠ **poseedor**. La unidad está asignada a alguien, pero responde
  quien la trae hoy.
- Se prestan las unidades entre ellos (vacaciones, incapacidad). El préstamo
  **transfiere la responsabilidad**, pero solo cuando el receptor **acepta** —
  un préstamo apenas *solicitado* no mueve nada.
- Regla que el cliente precisó después: **la responsabilidad sigue a quien está
  conduciendo en ese momento**. Por eso la prelación es
  `jornada abierta > préstamo aceptado > titular`, y la jornada gana: si el
  titular prestó la unidad pero hoy la maneja él, hoy responde él.

### Supervisor

Tiene una cuadrilla. Pidió expresamente poder ver **cuál conductor se retrasó en
el mantenimiento mientras tenía la unidad a su cargo** — por eso
`AvisoIncumplimiento` guarda `fundamento_poseedor` (jornada / préstamo /
titularidad) con la FK correspondiente.

### Chofer de grúa

Hace los arrastres. **Al cerrar el arrastre, el "chofer responsable" que se
registra es el poseedor de la unidad, NUNCA el chofer de grúa.** Si eso se
modela mal, la responsabilidad se transfiere sin que nadie lo decidiera y se
rompe la regla que sostiene todo el sistema.

### Gerente

Aprueba o rechaza presupuestos. **No hay penalización automática** (ver §3).

---

## 3. Reglas que solo existen porque el cliente las dijo

Ninguna de estas se deduce del código ni de un diagrama. Si alguien las
"simplifica" por no entenderlas, rompe el sistema.

**La penalización NO existe.** El cliente lo decidió así: el sistema solo
**avisa** al gerente y a Erick; ellos hablan con el chofer **en persona** y
después marcan el caso como atendido. No hay monto, no hay descuento, no hay
trámite de inconformidad. En la interfaz **no debe llamarse "penalización"** —
es un *aviso de incumplimiento*. Nombrarlo mal genera la expectativa de un
castigo que el sistema no aplica.

**La fecha límite no se mueve; la cita sí.** `fecha_limite` viene del plan de
mantenimiento y es inmutable. `fecha_cita` la asigna la agenda según capacidad.
El chofer **solo incumple si faltó a una cita confirmada**; si el taller nunca
pudo dársela, el problema es de capacidad del taller, no del chofer. Esto
resolvió un choque real: antes el sistema castigaba al chofer por falta de
espacio.

**En vialidad pública, peritos antes que mecánico.** El sistema bloquea la
solicitud de arrastre o auxilio hasta que se capture el folio del peritaje. No
puede *verificar* el folio —la llamada es por teléfono, fuera del sistema— pero
sí deja constancia de que se exigió, que es lo que protege a la empresa.

**Los talleres se llaman como su planta.** No "Taller Central Tijuana": Álamos,
Tecate, Rosarito, Carranza, Valle Redondo, Guaycura.

**Cada unidad tiene un taller asignado** al que va primero si se vara. Si ahí no
la pueden reparar, se traslada a **Álamos** (la central).

**Duraciones de servicio: no se conocen.** El cliente no sabe cuánto tarda cada
tipo de servicio. Por eso `TipoServicio` arranca con un estimado a ojo y el
sistema **mide** la duración real de cada orden cerrada para recalibrarse.
Mientras haya pocas muestras, la agenda propone **rangos**, no fechas exactas.

**Avisos de reprogramación: 48 h y 24 h.** Y sí se agenda **sábado**.

---

## 4. Los talleres, con los números corregidos

El plano de Álamos venía de un Excel y **lo leí mal la primera vez**. Corregido
por el cliente:

| Zona | Espacios | ¿Cuenta para capacidad? |
|---|---:|---|
| Reparto norte | 10 | Sí |
| Pipas | 8 | Sí |
| Reparto sur | 6 | Sí |
| Eléctricos | 3 | Sí |
| Utilitarios | 3 | Sí |
| Llantera | 1 | Sí |
| **Patio** | **45** | **No** — es estacionamiento de espera |
| **Fosa** | **1** | **No** |
| **Yonke** | **1** | No |
| Área lavado, oficina, basura | — | No |

**Capacidad operativa de Álamos: 31.** Antes el sistema creía que eran 44 y el
yonke le sumaba 45 espacios fantasma.

**Satélites — el cliente dijo "déjalos así", no preguntar de nuevo:**
Tecate 3 · Rosarito 3 · Carranza 2 · Valle Redondo 2 · Guaycura 4.

### La discrepancia de las sucursales

El cliente pidió "5 talleres" pero **sus propios datos** muestran 7 sucursales.
Resuelto así:

- **6 talleres**: Álamos (central) + Tecate, Rosarito, Carranza, Valle Redondo,
  **Guaycura**. Guaycura entró porque tiene 53 unidades y un mecánico propio en
  la hoja TALLER; dejarlo fuera era un olvido.
- **Libertad** (14 unidades) es sucursal **sin taller**: sus unidades se atienden
  en Álamos.

---

## 5. Estado real del código

### Funciona y está probado

| | |
|---|---|
| Backend | FastAPI, **84 rutas**, **52 tablas** |
| Frontend | React + Vite, build limpio, 6 roles |
| Modelo v2.0 | las 12 entidades nuevas creadas y en uso |
| 6 plantas | sembradas, con capacidades correctas |
| Datos reales | importador funcionando e **idempotente** |
| Estructura | backend por dominio, frontend por rol (ver `arquitectura.md`) |

### A medias

- **La agenda automática está diseñada pero NO implementada.** `CitaTaller`,
  `Reprogramacion` y `TipoServicio` existen como tablas; el algoritmo de
  `agenda-mantenimiento.md` no está escrito. Los jobs actuales solo generan
  avisos, alertas de 3 meses y cierre de préstamos.
- **`OrdenAuxilio`, `SolicitudPieza` y `TrasladoUnidad` existen como tablas** y
  el buscador de almacén ya consulta `Existencia`, pero **no hay endpoints ni
  pantallas** para la difusión del auxilio ni para el traslado entre plantas.
- **No hay módulo Mecánico en la interfaz**, aunque el modelo ya lo soporta.

### No empezado

- **App nativa (Expo).** El cliente la quiere para chofer, administrador de
  taller y chofer de grúa, **contra la misma base de datos**.
- **Notificaciones push** (FCM) y **ubicación en segundo plano**.
- **Compartir ubicación por WhatsApp** con ruta trazada.
- **Perfil de usuario** para todos los roles.
- **Alta y baja de cuentas** jerárquica (gerente y administrador).

---

## 6. Cómo correrlo

Dos terminales.

```bash
cd backend && python -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Cargar los datos reales (los archivos están en `~/Downloads`):

```bash
cd backend && DATOS_REALES=~/Downloads python -m app.importador
```

**Es idempotente**: se puede correr varias veces sin duplicar, y **no hace falta
borrar `bajagas.db`** (el servidor la tiene abierta y el borrado falla).

**Contraseñas:** todas las cuentas nacen con `bajagas2026`, con correo
`e<num_empleado>@bajagas.mx`. Tras correr `rotar_passwords` cada una tiene la
suya y quedan en `credenciales.csv`, que es la única copia.

---

## 7. Los archivos de datos reales

Están en `~/Downloads`, los entregó el cliente:

| Archivo | Qué trae |
|---|---|
| `INFO CHOFERES 2026 ACTUAL.xlsx` | 8 hojas. Las de flota (REPARTO, ESTACIONARIO, EXPENDIOS, MODULOS, FRANQUICIA) dan 379 unidades y 350 choferes. La hoja **TALLER** da los 37 técnicos con su ubicación y puesto. |
| `vehiculos.csv` | 1,043 unidades del catálogo histórico (13 marcadas como chatarra) |
| `partes.csv` | 18,233 refacciones |

**Trampas de estos archivos, ya resueltas en el importador:**

- **El encabezado NO está en la fila 1** en varias hojas (en REPARTO está en la
  2). Hay que usar `ws.min_row`.
- **Solo el 5% de las partes trae código.** El resto es texto libre → **el
  buscador debe buscar por texto, no por SKU**.
- Las partes vienen con **comillas rotas** del export (`""" TAPON 4"""""`) y con
  `_x000D_` incrustado, que es el salto de línea que Excel escapa.
- 53 choferes no entran porque sus filas no traen número de empleado; sin
  identidad no se puede crear una cuenta reproducible.

**Ojo:** los dos Excel del **Gasoducto Rosarito–Tijuana** (`Formato de
reporte.xlsx`, `Nomination Baja Gas GRO.xlsx`) que aparecieron en una sesión
**no son de este proyecto**. Son del sistema de medición y nominación de gas. No
comparten ninguna entidad con el taller. Están modelados aparte en el Anexo A de
`modelo-er.md` y **no deben integrarse**.

---

## 8. Trampas descubiertas (no las repitas)

**`create_all()` no toca las tablas que ya existen.** Ni les agrega columnas
nuevas ni índices. Una base previa empieza a dar **error 500** después de
cualquier cambio de modelo. Por eso existe `core/migraciones.py`, que corre al
arrancar. Y dentro de eso: **el `default=` de SQLAlchemy se aplica en Python y
nunca llega al SQL**, así que un `ADD COLUMN ... NOT NULL` falla siempre si no se
emite un `DEFAULT` explícito.

**`datetime.utcnow()` devuelve UTC sin marca de zona.** Fue la causa del bug de
"la hora sale corrida". La regla ahora: **la base y la API hablan UTC, la
pantalla habla Tijuana**, y la conversión ocurre en un solo lugar
(`core/tiempo.py` y `core/api.js`). Nunca un offset fijo: Baja California cambia
de UTC−7 a UTC−8 dos veces al año. Para cortes de día usa `dia_operativo()`, no
la fecha UTC.

**El vehículo se duplicaba** al aceptar dos solicitudes de la misma unidad.
Arreglado en tres capas: validación en el servicio con mensaje útil, auto-cierre
de las solicitudes hermanas, y **tres índices únicos parciales** en la base.

**Idempotencia del importador:** tuvo tres fugas, las tres ya cerradas. La más
sutil: un nombre de pieza de **exactamente 160 caracteres** —el largo de la
columna— que al truncarse dejaba un espacio final que la limpieza volvía a
quitar, y las claves dejaban de coincidir.

**Del entorno de trabajo:**
- `bajagas.db` está **bloqueada** mientras el servidor corre: no la borres, usa
  el importador idempotente.
- Los heredocs de bash **se rompen** con comillas dentro del contenido Python.
  Escribe el script a archivo con la herramienta de escritura y ejecútalo.
- El panel del navegador a veces **no compositea** y las capturas fallan. En ese
  caso verifica con `javascript_tool` leyendo estilos computados y estado del
  DOM: es igual de concluyente.
- El build de Vite **no atrapa un componente indefinido en JSX** — eso solo
  revienta corriendo. Hay que probar en el navegador, no solo compilar.

---

## 9. Historial de cambios de alcance

El proyecto dio varias vueltas. Saberlas evita "corregir" hacia atrás:

| Momento | Cambio |
|---|---|
| v1.0 | 6 módulos, mecánico incluido, un solo taller |
| v1.1 | **Fuera el módulo Mecánico**: no usan la app; Erick captura su trabajo |
| v2.0 | **Vuelve el mecánico, pero solo el de las satélites**: están solos y nadie captura por ellos. Aparecen las 6 plantas, la agenda automática, el aviso en vez de la penalización |

**El código estuvo en v1.1 mientras los documentos ya iban en v2.0.** Eso ya se
migró, pero si encuentras algo raro, probablemente sea un resto de esa época:
busca `Penalizacion` (obsoleta, sustituida por `AvisoIncumplimiento`) o el uso
de `poseedor_chofer_id` como si fuera la verdad — **es solo un caché**; la
verdad la da `poseedor_actual()`.

---

## 10. Diseño visual

La identidad es **"sala de control industrial"**: azul acero (`#0E5F8F`) sobre
blanco de equipo pintado, tipografía de señalización (Bahnschrift), esquinas
casi rectas, reglas finas. Los medidores de nivel del tablero del gerente son el
gesto propio: leen como tanques, que es lo que Baja Gas mueve.

**El tema oscuro es una opción, no el predeterminado.** El cliente lo pidió
explícitamente: arranca en blanco **aunque el sistema operativo esté en oscuro**,
y el usuario lo enciende con el interruptor. No usar `prefers-color-scheme`.

Maqueta de referencia: `docs/mockups/tablero-gerente.html`.

---

## 11. Preguntas abiertas

1. **¿El mecánico autónomo elabora presupuesto o solo pide piezas?** Hoy solo
   pide piezas. Si presupuesta mano de obra, entra al flujo del gerente.
2. **¿Puede ocupar y liberar los espacios de su propio taller?** Hoy no: eso es
   de Pedro, como pidió el cliente. Pero Pedro estaría asignando espacios de seis
   talleres que no ve, y el único presente en Tecate es el mecánico de Tecate.
3. **¿Cuáles son los tipos de servicio más comunes y cuánto duran?** Sin este
   catálogo la agenda no puede calcular nada. Es el dato que más falta.
4. **¿Cuántos espacios tiene cada taller satélite realmente?** Los números
   actuales los puso el cliente a ojo.
5. **¿Quién cubre a Erick?**
6. **¿Hay monto máximo que Erick apruebe sin gerente?** `LimiteAutorizacion` ya
   está lista para recibirlo.
7. **¿Es piloto real o proyecto escolar?** El cliente dijo **piloto real en Baja
   Gas**, lo que obliga a: aviso de privacidad firmado por la ubicación
   (LFPDPPP), HTTPS —el GPS y el push no funcionan sin él—, PostgreSQL en vez de
   SQLite, y respaldo diario probado.

---

## 12. Lo siguiente, en orden sugerido

1. **Implementar la agenda** (`agenda-mantenimiento.md`) — está diseñada al
   detalle y es el corazón del sistema. Bloqueada por la pregunta 3.
2. **Endpoints y pantallas del auxilio difundido y el traslado** — las tablas ya
   existen.
3. **Módulo Mecánico en la interfaz.**
4. **Perfiles y alta/baja jerárquica de cuentas.**
5. **App nativa en Expo** para chofer, administrador y chofer de grúa.

Para la app nativa, lo ya decidido: **Expo/React Native**, teléfonos **Android de
la empresa** (sin Play Store, sin Apple), **FCM** para push, ubicación en segundo
plano **solo mientras hay arrastre o avería abierta** (no todo el día), y
WhatsApp con un enlace de Google Maps que ya trae la ruta trazada
(`https://www.google.com/maps/dir/?api=1&origin=…&destination=…`).
