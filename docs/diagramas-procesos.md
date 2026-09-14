# Diagramas de los procesos de negocio

**Versión:** 1.0 · **Fecha:** 2026-08-21
**Deriva de:** [procesos.md](procesos.md) §4 — un diagrama por cada uno de los 12 procesos.
**Relacionados:** [casos-de-uso.md](casos-de-uso.md) v2.0 · [modelo-clases.md](modelo-clases.md) v2.0

---

## Cómo leerlos

Son **diagramas de secuencia**, no de actividad. La elección no es estética: `procesos.md` §1
define un proceso por sus **traspasos entre roles** — *«el punto donde los procesos se rompen»* —
y en una secuencia cada traspaso es una flecha con emisor, receptor y nombre. Un diagrama de
actividad muestra el orden de los pasos pero difumina de quién es cada uno, que es justo el dato
que este análisis necesita.

| Convención | Significa |
|---|---|
| `Sistema` | El software. Equivale al **⚙** de las tablas de `procesos.md` §4 |
| Flecha continua `->>` | Acción que alguien inicia |
| Flecha punteada `-->>` | Respuesta, notificación o retorno |
| Bloque `alt` | Caminos excluyentes: pasa uno **o** el otro |
| Bloque `opt` | Paso condicional: puede no ocurrir |
| Bloque `loop` | Se repite |
| Recuadro sombreado | **Donde el proceso se rompe.** El riesgo que señala `procesos.md` |
| Actor con *(papel)* | Participa pero **no toca el sistema** |

**Los cuatro administradores van por su nombre** — Erick, Pedro, Víctor y Pablo — porque no hacen
lo mismo y no deben poder hacer lo mismo. Dibujarlos como un solo «Administrador» escondería la
separación de funciones, que es lo que un sistema de control debe hacer visible.

> **Aviso de versión.** `procesos.md` está en v1.1 y `casos-de-uso.md` en v2.0. Donde las dos
> discrepan, estos diagramas siguen a la **v2.0**, que es lo que el código implementa. Las tres
> diferencias están marcadas en el diagrama correspondiente y listadas al final en §13.

---

## P1 — Préstamo y transferencia de responsabilidad

**Disparador:** el titular se va de vacaciones o se incapacita.
**Dueño:** Chofer titular · **Traspasos:** 3 · **Casos de uso:** CU-CHO-08, CU-CHO-09, CU-SUP-04, CU-AUT-03

```mermaid
sequenceDiagram
    autonumber
    actor T as Chofer titular
    participant S as Sistema
    actor Sup as Supervisor
    actor R as Chofer receptor

    T->>S: Registra préstamo (receptor, motivo, fecha de retorno)
    S-->>Sup: Notifica la solicitud
    S-->>R: Notifica la solicitud

    rect rgb(253, 235, 235)
        Note over T,R: LA VENTANA PELIGROSA. El préstamo está solicitado pero no aceptado:<br/>la responsabilidad SIGUE SIENDO DEL TITULAR y eso debe verse en pantalla.<br/>Es el momento exacto que un chofer usaría para decir "ya la había prestado".
    end

    opt Si la operación exige visto bueno
        Sup->>S: Autoriza o veta el préstamo
    end

    R->>S: Acepta la unidad
    Note over S: AQUÍ cambia el poseedor.<br/>poseedorActual() pasa a devolver al receptor.
    S-->>T: Confirma que ya no responde por la unidad

    loop Job diario (CU-AUT-03)
        S->>S: ¿Venció la fecha de retorno?
    end
    S-->>T: La unidad regresó a tu responsabilidad
    S-->>R: Ya no eres responsable
```

---

## P2 — Operación diaria y supervisión de flota

**Disparador:** inicio de turno.
**Dueño:** Supervisor · **Traspasos:** 2 · **Casos de uso:** CU-CHO-03, CU-CHO-04, CU-SUP-01, CU-SUP-02, CU-SUP-05

```mermaid
sequenceDiagram
    autonumber
    actor C as Chofer
    participant S as Sistema
    actor Sup as Supervisor

    C->>S: Abre jornada
    Note over C,S: «include» CU-CHO-04: no se abre jornada sin checklist
    C->>S: Ejecuta el checklist pre-operacional
    S-->>Sup: El chofer aparece como "conduciendo" con su unidad

    loop Mientras la jornada esté abierta
        C->>S: Envía su ubicación
        Sup->>S: Consulta mapa, cuadrilla y estado de cada unidad
    end

    C->>S: Cierra jornada (km final)

    rect rgb(253, 235, 235)
        Note over C,Sup: DONDE SE ROMPE. Todo el módulo del supervisor depende de que el chofer<br/>ABRA la jornada, y es un dato autodeclarado. Sin telemetría, el chofer que no<br/>la abre desaparece del tablero — y es justo el que más querrías vigilar.<br/>Para resistirlo hay que atarla a algo que él no controle: odómetro al cargar,<br/>marcaje en planta o telemetría de la unidad.
    end
```

---

## P3 — Mantenimiento preventivo programado

**Disparador:** se cumple la fecha o el kilometraje del plan.
**Dueño:** Víctor (agenda) · **Traspasos:** 3 · **Casos de uso:** CU-ADM-13, CU-CHO-07, CU-AUT-04, CU-AUT-05

> **v2.0 — se invirtió quién empieza.** Antes el chofer solicitaba el ingreso preventivo. Ahora
> **Víctor agenda y el chofer confirma**, lo que saca el conflicto de interés del camino crítico.

```mermaid
sequenceDiagram
    autonumber
    participant P as Programador de tareas
    participant S as Sistema
    actor V as Víctor · agenda
    actor C as Chofer poseedor
    actor Sup as Supervisor
    actor G as Gerente

    P->>S: Job diario: ¿venció alguna ventana de mantenimiento?
    S->>S: Genera el programa con su fecha límite (INMUTABLE)
    S->>S: CU-AUT-04 · La agenda propone cita según capacidad real

    alt Hay cupo antes de la fecha límite
        S-->>V: Cita propuesta
        V->>S: Confirma la cita
        S-->>C: CU-AUT-05 · Aviso a 48 h
        S-->>Sup: Aviso a 48 h
        S-->>C: CU-AUT-05 · Aviso a 24 h
        C->>S: Confirma que se presentará
        Note over C,S: A partir de aquí es un compromiso.<br/>La cita ya no se mueve sola.
        C->>S: Se presenta → entra a P4
    else No hay cupo antes de la fecha límite
        rect rgb(255, 247, 224)
            S-->>V: Alerta de CAPACIDAD DEL TALLER
            S-->>G: Alerta de CAPACIDAD DEL TALLER
            Note over V,G: NO es incumplimiento del chofer. Si el taller nunca pudo darle<br/>cita, el problema es del taller y va a otro tablero.<br/>Antes el sistema lo castigaba por algo que no era suyo.
        end
    end

    opt El chofer faltó a una cita CONFIRMADA
        S->>S: Genera aviso de incumplimiento → entra a P10
    end
```

---

## P4 — Ingreso a taller: solicitud y admisión

**Disparador:** el chofer solicita entrar *(correctivo)* o llega a su cita *(preventivo)*.
**Dueño:** Pedro (piso) · **Traspasos:** 4 · **Casos de uso:** CU-CHO-05, CU-CHO-06, CU-ADM-01, CU-ADM-02, CU-ADM-04

```mermaid
sequenceDiagram
    autonumber
    actor C as Chofer
    participant S as Sistema
    actor Pe as Pedro · piso
    actor Sup as Supervisor

    C->>S: Envía solicitud de ingreso (unidad, taller, falla, urgencia)
    S-->>Pe: Aparece en la bandeja de solicitudes

    Note over Pe,S: «include» CU-ADM-02: nunca se decide sin revisar (RN-06)
    Pe->>S: Consulta espacios libres COMPATIBLES con el tipo de unidad
    S-->>Pe: Lista de espacios que admiten esa unidad

    alt Hay espacio compatible
        Pe->>S: Acepta con fecha
        S-->>C: Solicitud aceptada
        C->>Pe: Se presenta físicamente en la fecha asignada
        Pe->>S: Coloca la unidad en un espacio
        S-->>Sup: La unidad cambia a estado "en taller"
    else No hay espacio
        Pe->>S: Deja en cola o rechaza con motivo
        S-->>C: Estatus de la solicitud (CU-CHO-06)
    end

    rect rgb(255, 247, 224)
        Note over Pe,S: LO QUE HAY QUE CUIDAR. La capacidad se cuenta POR TIPO DE ESPACIO,<br/>no en total. El taller puede estar lleno de pipas y tener libres los de reparto.<br/>Decir "el taller está lleno" a secas es lo que haría fallar el cálculo.
    end
```

---

## P5 — Reparación en taller

**Disparador:** la unidad queda colocada en un espacio.
**Dueño:** Pedro (cola) y Erick (captura) · **Traspasos:** **6** · **Casos de uso:** CU-ADM-05 a CU-ADM-10, CU-MEC-01/02/06

> **v2.0 — hay dos caminos y no se parecen.** El mecánico de Álamos no usa la app; el de las
> plantas satélite sí. `procesos.md` v1.1 solo describe el primero.

```mermaid
sequenceDiagram
    autonumber
    actor Pe as Pedro · piso
    participant S as Sistema
    actor MA as Mecánico Álamos (papel)
    actor E as Erick · captura
    actor MS as Mecánico autónomo
    actor C as Chofer

    Pe->>S: Asigna la cola de especialistas (mecánico, carrocero, electricista)

    alt Mecánico ASISTIDO — Álamos, 31 personas sin app
        Pe->>S: CU-ADM-07 · Emite la hoja de trabajo
        S-->>Pe: Hoja imprimible
        Pe->>MA: Entrega la hoja EN PAPEL
        MA->>E: Devuelve el diagnóstico ESCRITO
        E->>S: CU-ADM-08 · Captura el diagnóstico
        MA->>E: Reporta avance y término (verbal)
        E->>S: CU-ADM-09 · Registra el avance
    else Mecánico AUTÓNOMO — satélites, 6 personas con app
        MS->>S: CU-MEC-01 · Consulta su cola de trabajo
        MS->>S: CU-MEC-02 · Registra el diagnóstico él mismo
        MS->>S: CU-MEC-06 · Registra avance y término
        Note over MS,S: Nadie captura por él: está solo en su planta.<br/>Por eso Diagnostico.capturadoPor queda en NULL.
    end

    opt Faltan piezas
        S->>S: Entra a P6 (presupuesto) o P7 (surtido)
    end

    Pe->>S: CU-ADM-10 · Emite el formato de salida
    S-->>C: Unidad lista, con firma

    rect rgb(253, 235, 235)
        Note over Pe,C: DONDE SE ROMPE. Seis traspasos, cuatro EN PAPEL en la rama asistida.<br/>Dos consecuencias que hay que decir en voz alta:<br/>1. La ocupación "en tiempo real" del gerente (CU-GER-03) NO es en tiempo real:<br/>tiene el retraso de lo que tarde Erick en teclear.<br/>2. Si Erick falta, el taller entero deja de reportar. No tiene suplente.
    end
```

---

## P6 — Presupuesto y autorización del gasto

**Disparador:** el mecánico detecta que faltan piezas.
**Dueño:** Erick · **Traspasos:** **6** · **Casos de uso:** CU-ADM-17, CU-ADM-18, CU-ADM-19, CU-GER-08

```mermaid
sequenceDiagram
    autonumber
    actor M as Mecánico (papel)
    actor E as Erick · compras
    participant S as Sistema
    actor G as Gerente

    M->>E: Entrega el presupuesto y la lista de piezas EN PAPEL
    E->>S: CU-ADM-17 · Captura el presupuesto
    Note over E,S: «include» CU-ADM-18: no hay presupuesto sin desglose de piezas
    E->>S: Captura las piezas faltantes
    E->>S: CU-ADM-19 · Remite al gerente
    S-->>G: Presupuesto pendiente de autorización

    alt Aprueba
        G->>S: CU-GER-08 · Aprueba
        S-->>E: Notifica el resultado
        E->>M: Le avisa (verbal) · CU-ADM-23
        S->>S: Habilita la orden de compra → entra a P7
    else Rechaza
        G->>S: Rechaza con comentario
        S-->>E: Notifica el resultado
        E->>M: Le avisa (verbal)
    else Devuelve con comentarios
        rect rgb(253, 235, 235)
            G->>S: Devuelve pidiendo correcciones
            S-->>E: Notifica
            E->>M: Le pide corregir (verbal/papel)
            Note over M,G: DONDE SE ROMPE. El ciclo completo se repite, incluidos los DOS<br/>traspasos en papel. Cada vuelta son días de unidad parada, y las unidades<br/>paradas más de 3 meses casi siempre se explican por vueltas acumuladas aquí.<br/>Por eso AUTORIZACION es un historial y no dos columnas: para poder<br/>demostrar dónde se fue el tiempo.
        end
    end
```

---

## P7 — Compra y abasto de piezas

**Disparador:** presupuesto aprobado, o el mecánico satélite pide una pieza.
**Dueño:** Erick · **Traspasos:** 5 · **Casos de uso:** CU-ADM-20, CU-ADM-21, CU-ADM-22, CU-MEC-03/04/05, CU-GER-05

```mermaid
sequenceDiagram
    autonumber
    actor MS as Mecánico autónomo
    participant S as Sistema
    actor Pe as Pedro · almacén
    actor E as Erick · compras
    actor Al as Almacén de Álamos
    actor Pr as Proveedor (fuera del sistema)
    actor G as Gerente

    Note over MS,S: «include» CU-MEC-03: nunca se pide sin consultar antes
    MS->>S: Consulta existencia de la pieza
    S-->>MS: Hay / No hay, y de cuándo es el dato

    alt HAY existencia
        MS->>S: CU-MEC-04 · Solicita la pieza
        S->>S: Reserva el stock (evita que dos la pidan)
        Pe->>Al: Solicita el surtido
        Al-->>Pe: Entrega la pieza
        Pe->>S: CU-ADM-12 · Registra el surtido
        S-->>MS: Enviada a tu planta
    else NO hay existencia
        MS->>S: Levanta la solicitud con justificación
        S-->>E: CU-ADM-20 · Solicitud por evaluar
        alt Erick aprueba
            E->>S: CU-ADM-21 · Autoriza la orden de compra
            E->>Pr: Coloca el pedido FUERA DEL SISTEMA
            Pr-->>E: Confirma fecha estimada
            E->>S: CU-ADM-22 · Registra la ETA
            Note over E,S: Esta fecha es el disparador D3 de la agenda:<br/>sin ella el sistema no sabe cuándo se libera el espacio.
            S-->>G: Aparece como "piezas en camino" (CU-GER-05)
            Pr-->>E: Entrega
            E->>S: Registra la recepción
            S-->>MS: CU-MEC-05 · Tu pieza llegó
        else Erick rechaza
            E->>S: Rechaza con motivo
            S-->>MS: Rechazada, y por qué
        end
    end

    rect rgb(253, 235, 235)
        Note over E,G: DONDE SE ROMPE. El proveedor NO está en el sistema. El indicador<br/>de "piezas en camino" que ve el gerente vale exactamente lo que valga la<br/>disciplina de Erick para actualizarlo: es un dato de segunda mano<br/>presentado como si fuera de primera.
    end
```

---

## P8 — Atención de avería en ruta

**Disparador:** la unidad se detiene fuera de las instalaciones.
**Dueño:** Chofer poseedor · **Traspasos:** 4 · **Casos de uso:** CU-CHO-11 a CU-CHO-16, CU-MEC-07/08/09, CU-SUP-06/07

> **v2.0 — el auxilio se difunde, no se asigna.** Es el mecanismo más original del sistema.

```mermaid
sequenceDiagram
    autonumber
    actor C as Chofer poseedor
    participant S as Sistema
    actor Per as Peritos (teléfono)
    actor Sup as Supervisor
    actor M1 as Mecánico autónomo A
    actor M2 as Mecánico autónomo B
    actor Mon as Chofer de grúa

    C->>S: CU-CHO-11 · Reporta la avería
    Note over C,S: «include» CU-CHO-13: la ubicación es parte del reporte
    S-->>Sup: Alerta de unidad varada, visible en el mapa

    alt En vialidad pública (RN-04)
        rect rgb(255, 247, 224)
            C->>Per: Llama a peritos FUERA DEL SISTEMA
            Per-->>C: Entrega folio de peritaje
            C->>S: CU-CHO-12 · Captura el folio
            Note over C,S: El sistema EXIGE el folio pero no lo puede VERIFICAR:<br/>la llamada ocurre por teléfono. Lo que sí logra es dejar<br/>constancia de que se exigió, que es lo que protege a la empresa.<br/>Hasta aquí no se habilita pedir auxilio ni grúa.
        end
    end

    alt La falla se puede resolver en sitio
        C->>S: CU-CHO-14 · Solicita auxilio mecánico
        par Difusión a todos los autónomos disponibles
            S-->>M1: Orden de auxilio (ordenada por distancia)
        and
            S-->>M2: Orden de auxilio (ordenada por distancia)
        end
        M1->>S: Acepta
        M2->>S: Acepta (llega tarde)
        rect rgb(232, 240, 254)
            Note over S,M2: CONDICIÓN DE CARRERA. Se resuelve con<br/>UPDATE ... WHERE estado = 'difundida', no comprobando<br/>antes y escribiendo después. El primero la gana,<br/>y al segundo le responde que ya fue tomada.
        end
        S-->>M2: Ya fue tomada
        S-->>C: CU-CHO-16 · Va en camino, aquí lo ves
        M1->>S: CU-MEC-09 · Transmite su ubicación
        M1->>S: CU-MEC-10 · Cierra el auxilio en sitio
    else La unidad no se puede mover
        C->>S: CU-CHO-15 · Solicita arrastre → entra a P9
        S-->>Mon: Alerta de arrastre
    end

    opt Nadie aceptó en N minutos
        S->>S: CU-AUT-07 · Escala
        S-->>Sup: CU-SUP-07 · Nadie respondió
        Sup->>S: Llama por teléfono y despacha a mano
        Note over S,Sup: RESPUESTA_AUXILIO guarda también las NEGATIVAS con su motivo.<br/>Sin eso, un silencio de 20 minutos no se distingue de<br/>"todos ocupados", "está lejos de todos" o "nadie abrió la app".
    end
```

---

## P9 — Arrastre y traslado a taller

**Disparador:** la unidad varada no puede moverse por su cuenta.
**Dueño:** Chofer de grúa · **Traspasos:** 5 · **Casos de uso:** CU-MON-01 a CU-MON-07

```mermaid
sequenceDiagram
    autonumber
    participant S as Sistema
    actor Mon as Chofer de grúa
    actor C as Chofer poseedor
    actor Pe as Pedro · piso

    S-->>Mon: CU-MON-01 · Alerta con la ubicación reportada
    Mon->>S: CU-MON-02 · Acepta el arrastre

    par Ubicación compartida en los dos sentidos
        Mon->>S: CU-MON-03 · Transmite su ubicación
    and
        S-->>C: Le muestra la grúa en el mapa
    end

    Mon->>S: CU-MON-04 · Registra llegada al sitio
    Note over Mon,S: «include» CU-MON-06: protege contra reclamos de daño
    Mon->>S: Adjunta evidencia fotográfica
    Mon->>Pe: Entrega física de la unidad en el taller destino
    Mon->>S: CU-MON-05 · Cierra el arrastre

    rect rgb(253, 235, 235)
        Note over Mon,Pe: DONDE SE ROMPE — y es la regla que sostiene todo el sistema.<br/>Al cerrar, el "chofer responsable" que se registra es el POSEEDOR<br/>de la unidad, NUNCA el chofer de grúa que la movió.<br/>Si esto se modela mal, la responsabilidad se transfiere sin que nadie<br/>lo decidiera y se rompe RN-01.
    end

    S->>S: Abre la orden de servicio → se encadena con P4/P5
```

---

## P10 — Atención de incumplimiento de mantenimiento

**Disparador:** el chofer no se presentó a una cita **confirmada**.
**Dueño:** Gerente · **Traspasos:** 3 · **Casos de uso:** CU-AUT-01, CU-GER-10, CU-ADM-24

> **v2.0 — no es un proceso de castigo.** El sistema **avisa**; el trato con el chofer ocurre en
> persona y fuera de la aplicación. **No debe llamarse «penalización» en la interfaz.**

```mermaid
sequenceDiagram
    autonumber
    participant P as Programador de tareas
    participant S as Sistema
    actor G as Gerente
    actor E as Erick
    actor C as Chofer poseedor
    actor Sup as Supervisor

    P->>S: CU-AUT-01 · Detecta la falta a una cita confirmada
    S->>S: Resuelve QUIÉN era el poseedor a la fecha de la cita
    Note over S: Guarda el fundamento: jornada / préstamo / titularidad.<br/>Si la unidad estaba prestada, el que faltó fue el receptor.

    par Aviso a los dos que pueden actuar
        S-->>G: Aviso de incumplimiento (unidad, chofer, servicio, días)
    and
        S-->>E: Aviso de incumplimiento
    end

    G->>C: Habla con él EN PERSONA (fuera del sistema)
    E->>C: Llamada de atención (fuera del sistema)

    alt Gerente o Erick cierran el caso
        G->>S: CU-GER-10 · Marca como atendido, con nota de lo acordado
        S-->>Sup: Queda informado de que el caso se cerró
    else Nadie lo cierra
        rect rgb(253, 235, 235)
            S-->>G: Recordatorio a los 3 días
            S-->>G: Escalamiento a los 7 días
            Note over G,Sup: DONDE SE ROMPE. Si nadie marca el caso como cerrado, en tres meses<br/>hay cuarenta avisos abiertos y el tablero deja de significar algo.<br/>Por eso el recordatorio recurrente, igual que la alerta de 3 meses.
        end
    end
```

---

## P11 — Control gerencial e indicadores

**Disparador:** continuo, más alertas automáticas.
**Dueño:** Gerente · **Traspasos:** 2 · **Casos de uso:** CU-GER-01 a CU-GER-09, CU-AUT-02

```mermaid
sequenceDiagram
    autonumber
    participant P as Programador de tareas
    participant S as Sistema
    actor G as Gerente
    actor A as Administrador

    loop Consulta continua
        G->>S: CU-GER-01 · Tablero: incumplimiento, ocupación, tiempos, piezas
        S-->>G: Indicadores de las 6 plantas (CU-GER-11 los compara)
    end

    P->>S: CU-AUT-02 · ¿Alguna unidad lleva más de 3 meses parada?
    loop Recurrente hasta ser atendida (RN-08)
        S-->>G: Alerta de unidad parada
    end

    G->>A: Exige explicación (fuera del sistema)
    A-->>G: Explica

    rect rgb(253, 235, 235)
        G->>S: CU-GER-07 · Marca la alerta como atendida
        Note over G,S: DONDE SE ROMPE. La alerta se apaga cuando el GERENTE la marca,<br/>no cuando la unidad realmente sale del taller. Eso permite silenciarla<br/>sin resolver nada. Por eso el modelo exige declarar explícitamente<br/>si la condición SEGUÍA al cerrar (condicion_persistia_al_cerrar).
    end
```

---

## P12 — Administración de datos maestros

**Disparador:** alta o cambio en la organización.
**Dueño:** *sin dueño único — ese es el problema* · **Traspasos:** 0 · **Casos de uso:** CU-GEN-03, CU-ADM-03

```mermaid
sequenceDiagram
    autonumber
    actor E as Erick
    actor Pe as Pedro
    actor G as Gerente
    participant S as Sistema

    alt Cualquiera de los tres
        E->>S: Alta de usuarios, unidades, piezas, tipos de servicio
    else
        Pe->>S: CU-ADM-03 · Alta y baja de espacios del taller
    else
        G->>S: CU-GEN-03 · Alta de plantas, roles y planes
    end
    S-->>S: Los catálogos reflejan la realidad

    rect rgb(253, 235, 235)
        Note over E,S: DONDE SE ROMPE. Es el único proceso SIN traspasos, y por eso mismo<br/>el que nadie se apropia. Hoy lo comparten administrador y gerente, que en<br/>la práctica suele significar que NINGUNO lo mantiene.<br/>Hay que asignarle un dueño único.
    end
```

---

## Cómo se encadenan

```mermaid
flowchart LR
    P2["P2 Operación<br/>diaria"] -->|falla en ruta| P8["P8 Avería<br/>en ruta"]
    P8 -->|requiere grúa| P9["P9 Arrastre"]
    P8 -->|se resuelve en sitio| P2
    P9 -->|entrega la unidad| P4["P4 Ingreso<br/>a taller"]
    P3["P3 Mantenimiento<br/>preventivo"] -->|cita confirmada| P4
    P3 -->|faltó a la cita| P10["P10 Aviso de<br/>incumplimiento"]
    P3 -->|sin cupo| P11["P11 Control<br/>gerencial"]
    P4 -->|unidad en espacio| P5["P5 Reparación<br/>en taller"]
    P5 -->|faltan piezas| P6["P6 Presupuesto<br/>y autorización"]
    P6 -->|aprobado| P7["P7 Compra<br/>y abasto"]
    P7 -->|piezas recibidas| P5
    P5 -->|formato de salida| P2
    P1["P1 Préstamo"] --> P2
    P10 --> P11
    P5 --> P11
    P6 --> P11

    classDef sano fill:#e7f5ec,stroke:#0B7C3E,stroke-width:2px
    classDef caro fill:#fdebeb,stroke:#C33131,stroke-width:2px
    class P2,P3,P4 sano
    class P5,P6,P7 caro
```

**Hay dos ciclos y los dos importan.**

El **ciclo sano** (verde) `P2 → P3 → P4 → P5 → P2`: la unidad opera, se mantiene, vuelve a operar.

El **ciclo caro** (rojo) `P5 → P6 → P7 → P5`: cada vuelta suma días de unidad parada. Cuando gira
más de dos o tres veces, la unidad termina disparando la alerta de los 3 meses. Y los datos reales
lo confirman: de las 869 reparaciones medidas en el Excel del taller, **el 7% pasó de 90 días**, y
hoy hay **18 unidades** en ese rango.

---

## 13. Dónde estos diagramas se apartan de `procesos.md`

`procesos.md` está en v1.1 y `casos-de-uso.md` en v2.0. Estas son las tres diferencias, y en las
tres seguí a la v2.0 porque es lo que el código implementa:

| # | `procesos.md` v1.1 dice | Estos diagramas muestran | Por qué |
|---|---|---|---|
| 1 | «Los mecánicos no usan la aplicación» | **P5 y P7** tienen rama para el **mecánico autónomo** | La v2.0 devolvió el módulo Mecánico para los 6 de las satélites. Están solos en su planta y nadie captura por ellos |
| 2 | **P10 «Penalización»** en el inventario §2 y en el mapa §5 | **P10 «Aviso de incumplimiento»** | El §4 del propio documento ya lo reescribió; lo que quedó viejo es el título y el diagrama. No hay penalización |
| 3 | **P8** despacha el auxilio por el supervisor | **P8** lo **difunde** a todos los autónomos, y el primero que acepta lo gana | Mecanismo nuevo de la v2.0, con `DIFUSION_AUXILIO` y `RESPUESTA_AUXILIO` |

Además, `procesos.md` §4 numera los casos de uso con la numeración vieja: P5 cita `CU-ADM-14/15` y
P6 cita `CU-ADM-12/13`, que en la v2.0 significan otra cosa. Aquí van con la numeración de
`casos-de-uso.md` v2.0.

**Sugerencia:** subir `procesos.md` a v2.0 con estos tres cambios. Es media hora y evita que
alguien defienda el proyecto con el mapa equivocado.
