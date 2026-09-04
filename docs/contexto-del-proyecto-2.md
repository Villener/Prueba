# Contexto del proyecto — parte 2: SAP, almacén y sincronización

**Continúa:** [contexto-del-proyecto.md](contexto-del-proyecto.md)
**Fecha:** 2026-08-20

Esta parte cubre tres cosas que la primera no tocaba y que cambian decisiones de
diseño, no solo de integración:

1. **Baja Gas ya tiene sistemas**: SAP y Excel. Almacén tiene el suyo.
2. El plan por etapas para llegar a los datos reales.
3. Que la **web responda a lo que se hace desde el móvil**.

---

## 1. La duda que estaba bien tenida

> *"No me convence que el almacén esté aquí cuando el real está en SAP."*

**Tienes razón, y el problema es más grande que la integración.** Tal como está,
`Existencia` se comporta como si este sistema fuera el dueño del inventario:
tiene `stock_actual`, lo puede modificar, y el importador lo llena. Eso está mal
en cuanto SAP entre en escena, porque habría **dos sistemas afirmando cuánto hay
de una pieza** y ninguno con autoridad sobre el otro.

La regla que hay que fijar antes de escribir una línea más de almacén:

> **Un dato tiene un solo dueño. Los demás lo leen.**

### Quién es dueño de qué

| Dato | Sistema de registro | Este sistema |
|---|---|---|
| Existencia de refacciones | **SAP / sistema de almacén** | Lo **lee**, lo muestra, marca la hora del corte |
| Catálogo de piezas | **SAP** | Lo lee |
| Órdenes de compra | **SAP** (probablemente) | Lo lee; a lo más registra la solicitud |
| Reserva de una pieza para una orden | **Este sistema** | Es suya: SAP no sabe de órdenes de taller |
| Unidades, choferes, supervisores | RH / operaciones (Excel hoy) | Lo lee |
| **Ocupación de espacios del taller** | **Este sistema** | **Suyo** |
| **Citas, avisos, préstamos, jornadas** | **Este sistema** | **Suyos** |
| **Arrastres y auxilios** | **Este sistema** | **Suyos** |

Lo que este sistema aporta es **lo que ningún otro sistema de Baja Gas modela**:
el taller como espacio físico, la responsabilidad de la unidad, y el
cumplimiento del mantenimiento. Eso nadie se lo disputa. El inventario sí, y por
eso conviene soltarlo.

### Qué cambia en el modelo

`Existencia` deja de ser un registro propio y pasa a ser un **espejo**:

```python
class Existencia(Base, TimestampMixin):
    # --- lo que viene de afuera: NUNCA se escribe desde la app ---
    stock_actual      = Column(Integer)      # lo que dijo SAP/Excel
    origen            = Column(String(16))   # 'excel' | 'sap' | 'manual'
    sincronizado_en   = Column(UTCDateTime)  # el corte al que corresponde
    sincronizacion_id = Column(Integer, ForeignKey("sincronizacion_almacen.id"))

    # --- lo nuestro: SAP no sabe que existe ---
    stock_reservado   = Column(Integer, default=0)
    ubicacion_fisica  = Column(String(60))
```

Tres consecuencias que hay que respetar:

1. **La app nunca decrementa `stock_actual`.** Si el mecánico toma una pieza, se
   registra una reserva y un movimiento **nuestro**; el descuento real lo hace
   almacén en su sistema y llega en el siguiente corte.
2. **Cada pantalla que muestre existencia debe decir de cuándo es.** No basta
   con "Hay 7": tiene que decir *"Hay 7 — según almacén, hace 3 horas"*. Sin esa
   marca, un dato viejo se lee como si fuera de ahora, y eso es peor que no
   tenerlo.
3. **Si el corte tiene más de N horas, el buscador lo advierte.** El
   administrador debe poder distinguir "no hay" de "no sé".

Nueva tabla, para saber de dónde salió cada número:

```python
class SincronizacionAlmacen(Base):
    """Una corrida de carga. Sin esto no se puede auditar un dato raro."""
    id                = Column(Integer, primary_key=True)
    origen            = Column(String(16))    # excel | sap
    archivo           = Column(String(240))   # nombre y hash del archivo
    fecha_corte       = Column(UTCDateTime)   # a qué momento corresponde el dato
    ejecutada_en      = Column(UTCDateTime)
    piezas_leidas     = Column(Integer)
    piezas_actualizadas = Column(Integer)
    ejecutada_por_usuario_id = Column(Integer, ForeignKey("usuario.id"))
    notas             = Column(Text)
```

---

## 2. El plan por etapas

El cliente ya lo tiene claro y es el orden correcto. Lo escribo con lo que cada
etapa exige y lo que **no** hay que hacer todavía.

| Etapa | Fuente | Estado | Para qué sirve |
|---|---|---|---|
| **0** | Excel **desactualizado** (`partes.csv`, el que ya está) | **Hecho** | Probar con volumen real: 18,196 piezas, no 6 de demo |
| **1** | Excel **real** de almacén, cargado a mano | Siguiente | Que el administrador vea existencias que sí corresponden |
| **2** | Excel real, cargado **solo** (carpeta vigilada o subida programada) | Después | Quitar el paso manual |
| **3** | **SAP** | Cuando se pueda | Que el dato sea del momento, no de un corte |

**Una advertencia que conviene tener por escrito:** conseguir acceso a SAP en una
empresa **no es un problema técnico, es político**. Requiere que alguien de
sistemas te dé credenciales, un usuario de servicio y un endpoint, y eso suele
tardar meses o simplemente no pasar en un proyecto de practicante. **Diseña
asumiendo que el Excel va a ser la interfaz durante mucho tiempo**, y que SAP es
un adaptador más que se enchufa el día que llegue. Si el sistema depende de SAP
para funcionar, se queda parado esperando un permiso.

---

## 3. El adaptador: la pieza que hace que el cambio no duela

Todo lo de afuera entra por **una sola puerta**. El resto del sistema nunca sabe
si el dato vino de un Excel o de SAP.

```
app/modules/piezas/
├── almacen_adapter.py          ← la interfaz (clase abstracta)
├── excel_almacen_adapter.py    ← lee la hoja de almacén
├── sap_almacen_adapter.py      ← el día que haya acceso
└── almacen_service.py          ← el resto del sistema habla SOLO con esto
```

```python
class AlmacenAdapter(ABC):
    """Puerta única al inventario de Baja Gas.

    Quien consulte existencias habla con esta interfaz, nunca con el Excel ni
    con SAP. Cambiar de fuente es cambiar la implementación que se inyecta;
    ninguna pantalla ni servicio se entera.
    """

    @abstractmethod
    def leer_existencias(self) -> Iterable[ExistenciaExterna]:
        """Todas las piezas con su cantidad, tal como las reporta la fuente."""

    @abstractmethod
    def fecha_corte(self) -> datetime:
        """A qué momento corresponde este dato. NO es la hora de la carga."""

    @abstractmethod
    def identidad(self) -> str:
        """'excel:almacen_2026-08.xlsx#a1b2c3' o 'sap:MARD@PRD'."""
```

`ExistenciaExterna` es un objeto plano —código, nombre, cantidad, unidad,
ubicación— y **es el contrato**. Si SAP trae quince campos más, el adaptador los
descarta ahí y no contamina el resto del sistema. Esto es una *capa
anticorrupción*: el vocabulario de SAP se queda en la frontera.

**Lo que hay que resolver en la etapa 1, no antes:** cómo casar la pieza del
Excel de almacén con la pieza que ya está en la base. El catálogo actual salió
de `partes.csv` y **solo el 5% trae código**. Si el Excel de almacén sí trae
código de material de SAP, ese es el ancla y hay que guardarlo en
`Pieza.codigo_externo`. Si no lo trae, el casado será por nombre normalizado y
va a fallar en un porcentaje real de los casos — hay que preverlo con una
pantalla de "piezas sin casar" en vez de fingir que casaron todas.

---

## 4. Que la web responda a lo que se hace desde el móvil

Esto **no es sincronización de datos**: la app móvil y la web pegan al **mismo
backend y la misma base**. El dato ya es uno solo. Lo que falta es que la web se
entere de que cambió sin que el usuario recargue.

### El diseño mínimo que funciona

```
móvil  --POST /api/...-->  backend  --escribe-->  base
                              |
                              +--publica evento--> WebSocket --> web abierta
                                                                    |
                                                          useApi().recargar()
```

Encaja bien con lo que ya está construido: **todas las pantallas usan `useApi`,
que ya tiene `recargar()`**. No hay que reescribir pantallas: basta con que el
hook escuche.

```python
# backend: app/core/eventos.py
async def publicar(tipo: str, taller_id: int | None = None, **datos):
    """Avisa 'algo cambió', NO manda el dato.

    Se manda solo el aviso a propósito: si viajara el dato habría que
    resolver permisos por canal y versiones. Que el cliente vuelva a pedir
    por la API ya autenticada es más simple y no puede filtrar nada.
    """
```

```js
// frontend: core/eventos.js
//   Se suscribe una vez y avisa a los hooks interesados.
//   Si el socket se cae, cae a consulta periódica: nunca se queda mudo.
```

### Reglas que evitan que esto se vuelva un problema

- **El evento no lleva el dato, solo el aviso.** `{tipo:"espacio_cambio",
  taller_id:3}`. El cliente decide si le interesa y vuelve a pedir por la API,
  donde sus permisos ya se validan. Mandar el dato por el socket obligaría a
  filtrar por rol en el canal, y ahí es donde se filtra información.
- **Canales por ámbito, no uno global.** Un administrador de Tecate no tiene por
  qué despertar cada vez que se mueve un coche en Álamos.
- **Respaldo obligatorio.** Si el socket se cae —y se va a caer, sobre todo en
  el móvil— las pantallas críticas siguen refrescando cada N segundos. Un
  tablero que se quedó congelado sin avisar es peor que uno que tarda.
- **Rebote.** Si llegan diez eventos en dos segundos, se recarga una vez.

### Lo que NO hay que construir

**No hace falta sincronización bidireccional ni resolución de conflictos**, y es
importante no caer en eso: como la base es una sola, no hay dos versiones que
casar. El único caso con conflicto real es el **modo offline del móvil** (el
chofer que reporta una avería sin señal), y ahí ya está la respuesta:
`clave_idempotencia` en `ReporteAveria`, para que el reenvío no duplique.

---

## 5. Más perfiles seed antes de los datos reales

El plan del cliente —poblar perfiles para gestionar con las hojas de Excel antes
de conectar lo real— es correcto. Lo que ya se puede sembrar hoy con
`python -m app.importador`:

| Perfil | Cuántos | De dónde salen |
|---|---:|---|
| Supervisores | 13 | hojas de flota |
| Choferes | 297 | hojas de flota |
| Mecánicos asistidos (Álamos) | 31 | hoja TALLER, sin cuenta |
| Mecánicos autónomos (satélites) | 6 | hoja TALLER, con cuenta |

**Lo que falta sembrar y hay que agregar:**

- **Los cuatro administradores por su nombre**: Erick, Pedro, Víctor y Pablo,
  cada uno con su perfil real (`ADMIN_COMPRAS`, `ADMIN_PISO`, `ADMIN_AGENDA`,
  `ADMIN_OPERATIVO`), no un `admin@bajagas.mx` genérico.
- **El o los gerentes**, incluido el que menciona el cliente (ver §6).
- **Los montacarguistas**, que hoy son un usuario de demo. En la hoja TALLER hay
  dos personas con puesto `CHOFER DE GRUA`: esos son.

---

## 6. La duda de jerarquía que hay que aclarar

El cliente mencionó *"las hojas de Excel reales de almacén de otro gerente
arriba de los supervisores"*. **Eso admite dos lecturas y cambia el modelo:**

- **(a)** Hay **otro gerente distinto** del que ya modelamos —por ejemplo un
  gerente de operaciones dueño del almacén, además del de mantenimiento—. En ese
  caso hay **dos puestos gerenciales** y hay que decidir cuál aprueba
  presupuestos, porque hoy el modelo asume uno solo.
- **(b)** Es el **mismo gerente**, y solo se está describiendo que está por
  encima de los supervisores en el organigrama.

**No lo resolví por mi cuenta porque cambia quién autoriza el gasto**, que es la
regla RN-07 y una de las que más se apoyan en el modelo. Hay que preguntarlo
antes de sembrar perfiles gerenciales.

Si resulta ser (a), el modelo lo aguanta sin cambios de esquema:
`USUARIO_ROL` con ámbito por planta y `LimiteAutorizacion` por rol ya permiten
dos gerentes con alcances distintos.

---

## 7. Riesgos de esta etapa

| Riesgo | Por qué importa | Mitigación |
|---|---|---|
| **Nunca llega el acceso a SAP** | Es lo más probable | Que el Excel sea un adaptador de primera, no un parche temporal |
| **El dato de almacén se muestra sin fecha** | Un stock de ayer leído como de hoy manda a un mecánico por una pieza que no está | `sincronizado_en` visible en cada resultado |
| **Las piezas no casan entre fuentes** | El 5% del catálogo trae código | `codigo_externo` + pantalla de "sin casar", nunca casado silencioso |
| **Dos sistemas descontando stock** | Descuadre imposible de auditar | La app **nunca** escribe `stock_actual` |
| **El socket cae y nadie se entera** | Tablero congelado que parece vivo | Respaldo por consulta periódica + marca de "última actualización" |
| **Los datos viejos se confunden con reales** | Estás experimentando con un corte desactualizado a propósito | Marcar el origen en la interfaz mientras dure la etapa 0 |

---

## 8. Orden sugerido para lo que viene

1. **Marcar el origen y la fecha del dato de almacén** — es chico y evita que
   alguien tome una decisión con un número viejo. Se puede hacer hoy.
2. **Sembrar los perfiles que faltan**: los cuatro administradores por nombre,
   los montacarguistas reales, y el o los gerentes según §6.
3. **Extraer el `AlmacenAdapter`** con la implementación de Excel. Sin esto,
   cada etapa siguiente es una cirugía.
4. **WebSocket + `useApi` escuchando** — habilita el requisito de que la web
   responda al móvil, y es prerrequisito para que la app nativa se sienta viva.
5. **Recién entonces**, la app nativa en Expo.

La agenda automática (`agenda-mantenimiento.md`) sigue bloqueada por el catálogo
de tipos de servicio con sus duraciones. No depende de nada de este documento y
puede avanzar en paralelo en cuanto llegue ese dato.

---

## 9. Preguntas abiertas de esta parte

1. **¿El gerente del almacén es otro puesto o el mismo?** (§6) — bloquea sembrar
   perfiles gerenciales.
2. **¿El Excel real de almacén trae código de material de SAP?** Define si el
   casado de piezas es confiable o aproximado.
3. **¿Cada cuánto se actualiza ese Excel?** Determina si "hace 3 horas" o "hace
   una semana" es lo normal, y con eso el umbral del aviso de dato viejo.
4. **¿Alguien de sistemas ya dijo algo sobre SAP?** Si la respuesta es "ni
   preguntes", eso ahorra diseñar para un escenario que no va a pasar.
5. **¿El almacén es solo de Álamos o cada planta tiene el suyo?** El modelo ya
   soporta varios (`Existencia` es por taller), pero el importador asume uno.
