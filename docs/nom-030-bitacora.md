# El reporte de mantenimiento como bitácora electrónica (PROY-NOM-030-ASEA-2026)

**Versión:** 1.0 · **Fecha:** 2026-09-28
**Norma:** PROY-NOM-030-ASEA-2026, *Distribución de Gas Licuado de Petróleo por medio de
Auto-tanque y Vehículo de Reparto*. Es un **proyecto**: cuando se publique como definitiva entra
en vigor 180 días después; mientras tanto rige la NOM-EM-007-ASEA-2025.
**Alcance de esta fase:** el reporte de mantenimiento y su libro de bitácora (7.1.9 y 7.1.10).

---

## 1. Qué pide la norma y dónde se ve en la aplicación

La norma deja llevar la bitácora «electrónica mediante aplicaciones de software» (7.1.10) si
cumple lo de abajo. Cada renglón dice qué lo cumple y dónde lo puede ver un inspector.

| Numeral | Qué pide | Cómo lo cumple el sistema | Dónde se ve |
|---|---|---|---|
| 7.1.9 | Registrar fecha de **inicio y término** de cada actividad | Obligatorias al dar un sistema por realizado (administrador y mecánico). Se declaran; no son la hora de captura | Hoja del reporte → Actividades; libro de la unidad |
| 7.1.10 | Cada registro: fecha, **resultado**, **acciones requeridas**, **personal responsable** | Obligatorios al dar un sistema por realizado. Resultado = conforme / no conforme. Responsable = técnico del catálogo o externo | Hoja del reporte; libro |
| 7.1.10 a) | No se alteran; la corrección es un **registro nuevo** | Cada cambio deja un asiento que no se edita. Si cambia un dato ya escrito, el asiento nuevo dice a cuál corrige y qué decía antes. Un formato **cerrado** se corrige con «Registrar corrección» | Libro (asientos «Corrección», «corrige el asiento N») |
| 7.1.10 b) | Fácil acceso para el **Operador** y el personal de mantenimiento | El chofer lo abre desde *Mi unidad*; el administrador desde la hoja; el mecánico desde *Mi trabajo*; supervisor y gerente desde sus pantallas | Botón «Libro de bitácora» |
| 7.1.10 c) | Permiso, razón social, número económico, operadores y personal auxiliar | Cabecera del libro. Permiso y razón social se capturan una vez (y por unidad si alguna opera con otro permiso) | Libro → cabecera; «Datos de identificación» |
| 7.1.10 d) 1 | Rastreabilidad | Asientos numerados por unidad (1, 2, 3…), ligados al formato, al renglón y al asiento que corrigen | Libro |
| 7.1.10 d) 2 | Usuario y contraseña | El inicio de sesión de la aplicación | — |
| 7.1.10 d) 3 | Hora, fecha y usuario **automáticos** | Los pone el servidor al registrar; el nombre se copia para que no cambie después | Cada asiento: «28/09/2026, 09:17:51 · Erick Avalos Gomez» |
| 7.1.10 d) 4 | Guardar todo y **no permitir eliminar** | Disparadores en la base de datos que rechazan editar o borrar asientos, y borrar formatos. Además, una cadena de huellas (SHA-256) que demuestra que nada cambió | Libro → «Libro íntegro» |
| 7.1.10 d) 5 | Disponible en computadora o **móvil** | Es la misma aplicación web; el libro se lee en teléfono y se imprime | — |
| 7.1.10 e) f) | Conservación | Nada se borra, así que se conserva de sobra | — |

### Reglas que el sistema hace cumplir (y que salieron de la revisión del 28-sep)

- **Un preventivo no se cierra sin al menos una actividad realizada**: sin eso el libro diría
  «conforme» sin un solo trabajo que demuestre el programa (7.1.9).
- **Las fechas caben en la estancia**: ni futuras, ni al revés, ni anteriores al día en que la
  unidad entró al taller; y la salida no puede ser anterior al término del último trabajo.
- **Un «no conforme» tiene que decir qué acciones requiere** («Ninguna» no se acepta).
- **Sin nada realizado no hay resultado**: si se borra lo realizado, se van con él el resultado,
  las fechas y las acciones.
- **Cambiar el permiso, la razón social o el personal auxiliar deja un asiento** en el libro, y
  cada entrada al taller sigue mostrando los datos que tenía ese día («Al entrar: …»).
- **El sello «Libro íntegro» también revisa que ningún formato de la unidad se haya quedado sin su
  asiento de apertura o de cierre**: un libro vaciado ya no pasa por íntegro.
- **Los dos registros viejos por asignación** (`/asignaciones/{id}/diagnostico` y `/avance`)
  escribían trabajo fuera del libro y ninguna pantalla los usaba: ahora contestan 410.

## 2. Lo que conviene saber antes de enseñarlo

- **Los formatos anteriores al 28 de septiembre de 2026** se transcribieron una sola vez al libro.
  Aparecen aparte, como «Registros anteriores a la bitácora electrónica», porque se capturaron sin
  inicio, término ni resultado por actividad. **No sirven como evidencia de 7.1.9.**
- **El número de permiso NO está capturado.** El libro lo marca en rojo en cada pipa y cada
  vehículo de reparto hasta que se capture en «Datos de identificación». No se inventó.
- **Supuesto por confirmar:** tomamos *pipa* = Auto-tanque y *reparto* = Vehículo de Reparto
  (5.1.14). Las utilitarias y los montacargas llevan libro igual, pero sin el aviso de datos
  faltantes, porque la norma no se los pide.
- **Contraseñas:** 7.1.10 d) 2 solo vale si cada quien entra con la suya. Antes de presentarlo,
  confirmar que ninguna cuenta de administrador, mecánico, supervisor o gerente conserve la
  contraseña de prueba.
- **Límite de la cadena de huellas:** detecta cualquier asiento editado o borrado desde la
  aplicación o a mano en la base, **salvo** que alguien con acceso directo al archivo de la base
  quite los candados, edite y vuelva a calcular todas las huellas. Contra eso, el ancla es el libro
  impreso: lleva en el pie el número y la huella del último asiento. La mejora siguiente es firmar
  las huellas con una llave que viva fuera de la base (en el servidor), para que tener la base no
  baste.

## 3. Lo que falta de la norma (fases siguientes)

| Numeral | Qué es | Por qué importa |
|---|---|---|
| 7.1.8 | **Programa de mantenimiento** por elemento, sistema y dispositivo, con criterios de aceptación y personal competente | Sin él, 7.1.9 no se demuestra completo: la Tabla 8 los evalúa juntos |
| Apéndice B, 7.2.3, 7.3.2 | Revisión anual de la **parte motriz** | Sus incumplimientos se anotan en esta misma bitácora (el tipo de asiento «hallazgo» ya existe) |
| Apéndice A, 7.3.1.2 | **Revisión visual diaria** del chofer | Idem |
| 7.2.2, Tabla 5 | Recipiente, válvulas, accesorios del auto-tanque; elementos del vehículo de reparto | El formato de hoy solo tiene los 10 sistemas del vehículo |
| 6.5 | **Expediente de integridad** por unidad (documentos firmados y escaneados) | Documento aparte del libro |

## 4. Dónde está en el código

- `backend/app/modules/bitacora/` — el libro: modelo, servicio que numera y encadena, textos de
  cada asiento y la consulta.
- `backend/app/core/migraciones.py` → `CANDADOS` — los disparadores de la base.
- `backend/app/modules/taller/administrador_controller.py` → `_validar_cierre`, `_sellar_cierre`,
  `corregir_reporte`.
- `frontend/src/modules/sistema/BitacoraUnidadPage.jsx` — la página del libro.
- `backend/pruebas/prueba_bitacora.py` — 27 casos (`.venv/Scripts/python.exe pruebas/prueba_bitacora.py`).
