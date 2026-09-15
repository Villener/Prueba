# Auditorías de campo a reparto — cómo entran al sistema del taller

**Fecha:** 2026-09-15 · **Fuentes:** `Requerimientos_App_Auditorias_Campo_BajaGas.docx` y
`Formato auditoria campo reparto.docx`, entregados por el cliente.

El cliente pidió cotizar una **app móvil aparte** para que los supervisores auditen a los choferes
de reparto en campo. La instrucción ahora es meterlo en el sistema del taller en vez de construir
una aplicación separada. Este documento dice qué se reusa, qué falta, y las **tres cosas que
chocan** con lo que ya está decidido.

**Estado:** análisis. Nada implementado.

---

## 1. Por qué sí cabe: la mitad ya está escrita

Auditar es de reparto, no de taller — otro proceso y otro ciclo. Pero los **actores son los
mismos**, y al revisar el modelo resultó que varias piezas del formato ya existen:

| Campo del formato en papel | Ya existe en el sistema |
|---|---|
| RUTA | `Chofer.ruta` — `String(24)`, con valores tipo `R-2201` |
| UNIDAD | `Unidad.num_economico` |
| KM / ODOM. | `Unidad.km_actual` |
| CHOFER / SUPERVISOR | Las 435 y 13 cuentas que ya entran al sistema |
| «Licencia vigente / fecha vencimiento» | `Chofer.vencimiento_licencia` |

Ese último renglón es el más interesante. **Es la primera casilla SÍ/NO del formato, y el sistema
ya sabe la respuesta.** Hoy el supervisor le pide la licencia al chofer y la mira; mañana la app
se lo dice antes de que llegue, y de paso puede avisarle a quién se le vence la semana entrante.
Una auditoría que solo transcribe el papel no aporta eso.

Lo mismo con el **poseedor**: RN-01 ya dice que responde quien trae la unidad, no el titular. Una
auditoría levantada contra el titular cuando la unidad iba prestada señala al chofer equivocado —
el sistema ya resuelve eso y una app aparte tendría que reimplementarlo.

Y la pieza grande: **`Evidencia` ya es polimórfica**. `entidad_tipo` + `entidad_id`, con la FK
validada en la aplicación. Colgarle fotos a una auditoría no necesita un modelo nuevo — el mismo
mecanismo que ayer se escribió para las averías sirve tal cual.

---

## 2. Lo que hay que crear

**Modelos nuevos:**

- `Auditoria` — la cabecera: fecha, hora, supervisor, zona, colonia/calle, ruta, unidad, chofer,
  odómetro, folio, hallazgo, acción/compromiso, resultado (`CUMPLE` / `OBSERVACIÓN` / `CRÍTICO`),
  fecha y responsable de seguimiento, las dos firmas.
- `RespuestaAuditoria` — los 18 puntos SÍ/NO de las secciones 1 y 3, como renglones y no como 18
  columnas: el cuestionario va a cambiar y una tabla ancha obliga a migrar la base cada vez.
- `InventarioEnvases` — llenos, vacíos y observación por presentación (10, 20 y 45 kg).
- `Zona` y colonia. No existen: el taller razona por planta y por taller, no por territorio.

**Campos nuevos en `Evidencia`**, que hoy solo guarda archivo, descripción, momento y quién subió:

- `latitud`, `longitud`, `precision_gps`
- `hora_servidor` además de la del dispositivo
- `sin_conexion` — si el equipo estaba sin señal al momento de la toma
- `hash_imagen` — para detectar duplicados
- `url_sellada` — la versión con el sello visible, **conservando la original**

El folio va con formato `AUD-2026-001245`, como lo pidió el cliente.

---

## 3. Los tres choques

### 3.1 La galería no se puede bloquear en un navegador

El requisito más importante del cliente —el que sostiene todo lo demás— dice:

> «La evidencia debe tomarse desde la app; bloquear carga desde galería en la auditoría formal.»

**En web eso no se puede garantizar.** `<input type="file" accept="image/*" capture="environment">`
es una *sugerencia* al navegador, no una restricción: en la mayoría de los Android y en Safari el
usuario puede escoger «Archivos» o «Fotos» de todos modos. Un supervisor que quiera inventar una
auditoría puede subir una foto vieja.

Esto no es un detalle de implementación: es **el punto entero del documento**. Toda la sección 3,
«Controles recomendados para integridad de la evidencia», existe para que la foto no se pueda
falsificar.

Tres caminos, de menor a mayor esfuerzo:

1. **Aceptarlo y compensar.** No se bloquea la galería, pero se hace cara la trampa: GPS con
   precisión obligatoria, hora de servidor, hash para detectar la misma foto repetida, y el sello
   puesto **en el servidor** y no en el cliente. Una foto de galería llegaría sin GPS fresco o con
   coordenadas que no cuadran con la ruta, y eso se puede auditar después. No lo impide; lo deja
   con rastro.
2. **PWA con cámara en vivo.** Se captura con `getUserMedia` y se pinta a un canvas — la imagen
   nunca sale de un selector de archivos. Cierra el hueco casi del todo y sigue siendo web, pero
   es más trabajo y depende de permisos de cámara que en iOS se comportan distinto.
3. **App nativa**, que es lo que el cliente pidió originalmente. Es la única que garantiza el
   requisito tal como está escrito.

**Hay que decidir esto antes de escribir una línea**, porque cambia si esto es un módulo más del
sistema o un proyecto aparte.

### 3.2 El sistema no funciona sin señal, y aquí sí hace falta

`RF-GEN-09` («funcionamiento offline con sincronización diferida») lleva desde la v1.1 como
**Should**, y nunca se implementó. En el taller se podía vivir sin eso: el administrador está
parado frente a un escritorio.

En campo no. El documento lo pone como requisito y con razón: la auditoría se levanta en la
colonia donde el chofer está repartiendo, y ahí hay zonas sin cobertura. Si la app exige conexión,
la auditoría se levanta en papel y volvemos al principio.

Offline de verdad —cola local, sincronización, resolución de conflictos, fotos pesadas esperando
señal— es de las cosas más caras que se pueden pedir. No es un checkbox.

### 3.3 La productividad está declarada fuera de alcance

La sección 4 del formato, «FOTO DE PRODUCTIVIDAD», pide venta acumulada en kg, piezas de 10 y de
45 kg, clientes atendidos, paradas, ventas observadas, prospectos y tiempo improductivo.

Eso contradice dos cosas ya escritas:

- `requerimientos.md` §1 deja **fuera del alcance v1** la facturación de ventas de gas.
- `RF-SUP-11`, «Reportes de productividad por chofer», está marcado **Won't**.

No es lo mismo facturar que registrar lo que el supervisor observó en una visita —son números
tomados a ojo, no contables—, pero es la puerta de entrada. Y la segunda etapa del documento del
cliente pide explícitamente cruzar las auditorías con «kg vendidos y productividad del chofer»,
que ya es el dato real.

**Hay que decirlo ahora**, no cuando alguien pregunte por qué el tablero no cuadra con
contabilidad.

---

## 4. Lo demás que hay que resolver

- **Retención de fotos.** El cliente propone 12–24 meses. Conviene que sea **la misma política**
  que la evidencia del preventivo (RN-15): dos reglas distintas para el mismo servidor es como se
  llena un disco sin que nadie se dé cuenta. Y aplica la misma compresión en el teléfono
  (RF-GEN-15): estas fotos son más y más frecuentes que las del taller.
- **Catálogos SAP.** El documento los pide en segunda etapa para no capturar rutas y unidades a
  mano. Hoy las unidades entran por el importador de Excel; habría que ver si SAP las expone o si
  se sigue importando.
- **Firma digital en pantalla.** El formato cierra con dos firmas. El reporte de mantenimiento ya
  tiene firmas (CU-ADM-28), pero registradas, no dibujadas. Conviene el mismo mecanismo en los dos
  lados.
- **Reincidencias.** El documento pide alertas por reincidencia. Eso se parece mucho a la
  **amonestación** de RN-14, que ya se documentó para el preventivo. Vale la pena que sea el mismo
  expediente del chofer (RF-GER-16) y no dos historiales paralelos.

---

## 5. Preguntas para el cliente

1. **¿Se acepta que la galería no quede bloqueada** si esto vive en el sistema web, a cambio de
   GPS, hora de servidor, hash y sello del lado del servidor? Si la respuesta es no, esto es una
   app aparte y hay que cotizarla como tal.
2. **¿Qué tan seguido se audita?** De ahí sale cuántas fotos al mes y si el servidor actual
   aguanta.
3. **¿La productividad entra o no?** Si entra, hay que reabrir el alcance de la v1.
4. **¿Quién ve las auditorías además del supervisor que la levanta?** ¿El gerente, en el mismo
   tablero donde ya pidió gráficos (RF-GER-15)?
5. **¿La auditoría puede corregirse después de firmada?** El reporte de mantenimiento dice que no:
   un papel firmado editado sin rastro deja de servir como prueba. Debería ser la misma regla.
