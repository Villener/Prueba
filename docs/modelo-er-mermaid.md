# Modelo ER en Mermaid — derivado del código real

**Fecha:** 2026-08-27
**Fuente de verdad:** las clases SQLAlchemy en `backend/app/modules/*/*_model.py`
(NO `docs/modelo-er.md`, que es el diseño aspiracional de 82 tablas).
**Verificado contra:** `backend/bajagas.db` — 54 tablas, coinciden una a una.

Se divide en 8 diagramas porque 54 tablas en uno solo no se leen. Los paquetes
son los mismos que declara `backend/app/models.py`.

---

## 0. Vista general (sin atributos)

```mermaid
erDiagram
    PLANTA   ||--o| TALLER : "tiene 1:1"
    TALLER   ||--o{ ZONA_TALLER : "se divide en"
    ZONA_TALLER ||--o{ ESPACIO : "contiene"
    ESPACIO  ||--o{ OCUPACION_ESPACIO : "se ocupa en"

    USUARIO  ||--o{ USUARIO_ROL : "tiene"
    ROL      ||--o{ USUARIO_ROL : "se asigna en"
    USUARIO  ||--o| CHOFER : "es"
    USUARIO  ||--o| SUPERVISOR : "es"
    USUARIO  ||--o| CHOFER_GRUA : "es"
    TALLER   ||--o{ TECNICO : "adscribe"

    TIPO_UNIDAD ||--o{ UNIDAD : "clasifica"
    CHOFER   ||--o{ UNIDAD : "posee"
    UNIDAD   ||--o{ JORNADA : "se opera en"
    UNIDAD   ||--o{ ASIGNACION_UNIDAD : "se asigna en"
    UNIDAD   ||--o{ PRESTAMO_UNIDAD : "se presta en"

    UNIDAD   ||--o{ PROGRAMA_MANTENIMIENTO : "programa"
    PLAN_MANTENIMIENTO ||--o{ PROGRAMA_MANTENIMIENTO : "genera"
    TIPO_SERVICIO ||--o{ PLAN_MANTENIMIENTO : "define"
    PROGRAMA_MANTENIMIENTO ||--o| CITA_TALLER : "se agenda como"
    CITA_TALLER ||--o{ REPROGRAMACION : "se mueve en"
    CITA_TALLER ||--o| AVISO_INCUMPLIMIENTO : "incumple"

    SOLICITUD_INGRESO ||--o| ORDEN_SERVICIO : "abre"
    UNIDAD   ||--o{ ORDEN_SERVICIO : "recibe"
    ORDEN_SERVICIO ||--o{ ASIGNACION_TECNICO : "reparte a"
    ORDEN_SERVICIO ||--o| FORMATO_SALIDA : "cierra con"
    ORDEN_SERVICIO ||--o{ PRESUPUESTO : "cotiza en"
    ORDEN_SERVICIO ||--o{ TRASLADO_UNIDAD : "deriva en"

    PRESUPUESTO ||--o{ DETALLE_PRESUPUESTO : "detalla"
    PRESUPUESTO ||--o{ AUTORIZACION : "pasa por"
    PRESUPUESTO ||--o{ ORDEN_COMPRA : "ejecuta"
    PIEZA    ||--o{ DETALLE_PRESUPUESTO : "se cotiza en"
    PIEZA    ||--o{ EXISTENCIA : "se almacena como"
    REQUISICION ||--o{ RENGLON_REQUISICION : "lista"

    UNIDAD   ||--o{ REPORTE_AVERIA : "se avería en"
    REPORTE_AVERIA ||--o| REPORTE_PERITAJE : "requiere"
    REPORTE_AVERIA ||--o| ORDEN_AUXILIO : "escala a"
    REPORTE_AVERIA ||--o| ARRASTRE : "escala a"
    ORDEN_AUXILIO ||--o{ DIFUSION_AUXILIO : "se difunde en"
    ORDEN_AUXILIO ||--o{ RESPUESTA_AUXILIO : "recibe"
    ARRASTRE ||--o{ UBICACION_ARRASTRE : "rastrea con"
    ARRASTRE ||--o| ORDEN_SERVICIO : "entrega en"

    USUARIO  ||--o{ NOTIFICACION : "recibe"
    USUARIO  ||--o{ BITACORA_AUDITORIA : "genera"
```

---

## 1. Paquete A — Organización, plantas y personas (11 tablas)

`CHOFER`, `SUPERVISOR` y `CHOFER_GRUA` no tienen `id` propio: su PK **es** la FK
a `USUARIO` (herencia tabla-por-subclase). `TECNICO` sí tiene `id` propio y su
`usuario_id` es opcional a propósito: solo el técnico AUTONOMO tiene cuenta.

```mermaid
erDiagram
    PLANTA {
        int id PK
        string clave UK "NN"
        string nombre "NN"
        string direccion
        float latitud
        float longitud
        bool es_central "NN, solo ALAMOS"
        bool tiene_taller "NN, LIBERTAD no"
        bool activo "NN"
        datetime creado_en
        datetime actualizado_en
    }
    TALLER {
        int id PK
        int planta_id FK "UK, 1:1 con planta"
        string nombre UK "NN"
        string tipo "NN, CENTRAL o SATELITE"
        string direccion
        float latitud
        float longitud
        bool opera_sabado "NN"
        bool activo
        datetime creado_en
        datetime actualizado_en
    }
    USUARIO {
        int id PK
        string nombre "NN"
        string apellidos "NN"
        string email UK "NN, indexado"
        string telefono
        string password_hash "NN"
        bool activo "NN"
        datetime fecha_alta
        datetime creado_en
        datetime actualizado_en
    }
    ROL {
        int id PK
        string nombre UK "NN"
        string descripcion
    }
    USUARIO_ROL {
        int usuario_id PK "FK"
        int rol_id PK "FK"
        datetime vigente_desde
        datetime vigente_hasta "NULL = vigente"
    }
    CHOFER {
        int usuario_id PK "FK a usuario.id"
        string num_licencia UK
        string tipo_licencia
        date vencimiento_licencia
        int cuadrilla_id FK
        bool disponible
    }
    SUPERVISOR {
        int usuario_id PK "FK a usuario.id"
        string zona
    }
    CHOFER_GRUA {
        int usuario_id PK "FK a usuario.id"
        int unidad_grua_id FK
        string licencia_especial
        bool en_servicio
    }
    CUADRILLA {
        int id PK
        string nombre "NN"
        int supervisor_id FK
        bool activa
        datetime creado_en
        datetime actualizado_en
    }
    TECNICO {
        int id PK
        string nombre "NN"
        string apellidos "NN"
        string num_empleado UK
        string especialidad "NN"
        int taller_id FK
        string modalidad "NN, AUTONOMO o ASISTIDO"
        int unidad_servicio_id FK "solo AUTONOMO"
        string puesto
        string telefono
        bool disponible
        bool activo
        int usuario_id FK "UK, NULL en ASISTIDO"
        datetime creado_en
        datetime actualizado_en
    }
    LIMITE_AUTORIZACION {
        int id PK
        int rol_id FK "NN"
        decimal monto_maximo "NULL = sin límite"
        string moneda "MXN"
        datetime vigente_desde "NN"
        datetime vigente_hasta
    }

    PLANTA ||--o| TALLER : "1:1"
    USUARIO ||--o{ USUARIO_ROL : "tiene"
    ROL ||--o{ USUARIO_ROL : "se otorga en"
    ROL ||--o{ LIMITE_AUTORIZACION : "topa con"
    USUARIO ||--o| CHOFER : "especializa"
    USUARIO ||--o| SUPERVISOR : "especializa"
    USUARIO ||--o| CHOFER_GRUA : "especializa"
    USUARIO |o--o| TECNICO : "opcional, solo AUTONOMO"
    SUPERVISOR ||--o{ CUADRILLA : "dirige"
    CUADRILLA ||--o{ CHOFER : "agrupa"
    TALLER ||--o{ TECNICO : "adscribe"
```

---

## 2. Paquete B — Flota y responsabilidad (6 tablas)

La regla que sostiene el módulo: **titular ≠ poseedor**. `titular_chofer_id` es a
quién se le asignó la unidad; `poseedor_chofer_id` es quién la trae hoy (RN-01). Un
préstamo mueve el poseedor, no el titular, y de ahí sale a quién se le reclama un
mantenimiento vencido.

```mermaid
erDiagram
    TIPO_UNIDAD {
        int id PK
        string nombre UK "NN"
        string descripcion
        int prioridad_operativa "NN, menor entra antes"
    }
    UNIDAD {
        int id PK
        string num_economico UK "NN"
        string placas UK
        string vin UK
        string marca
        string modelo
        int anio
        int tipo_unidad_id FK "NN"
        int titular_chofer_id FK "a quién se asignó"
        int poseedor_chofer_id FK "quién la trae hoy, RN-01"
        string estado "NN, ver ESTADOS_UNIDAD"
        int km_actual
        int taller_actual_id FK "dónde está AHORA"
        int taller_asignado_id FK "a dónde va si se vara"
        bool activo "NN"
        date fecha_alta
        date fecha_baja
        datetime creado_en
        datetime actualizado_en
    }
    ASIGNACION_UNIDAD {
        int id PK
        int unidad_id FK "NN"
        int chofer_id FK "NN"
        datetime fecha_inicio
        datetime fecha_fin "NULL = vigente"
        int asignado_por_usuario_id FK
        string motivo
    }
    PRESTAMO_UNIDAD {
        int id PK
        int unidad_id FK "NN"
        int chofer_presta_id FK "NN"
        int chofer_recibe_id FK "NN"
        string motivo "NN, vacaciones incapacidad apoyo otro"
        datetime fecha_solicitud
        datetime fecha_aceptacion
        datetime fecha_inicio
        date fecha_fin_prevista "NN"
        datetime fecha_fin_real
        string estado "NN"
        int autorizado_por_supervisor_id FK
        string motivo_rechazo
        datetime creado_en
        datetime actualizado_en
    }
    JORNADA {
        int id PK
        int chofer_id FK "NN"
        int unidad_id FK "NN"
        datetime hora_inicio
        datetime hora_fin
        int km_inicio
        int km_fin
        bool checklist_ok
        text checklist_notas
    }
    UBICACION_UNIDAD {
        int id PK
        int unidad_id FK "NN"
        float latitud "NN"
        float longitud "NN"
        datetime capturado_en
        string fuente "app_chofer"
    }

    TIPO_UNIDAD ||--o{ UNIDAD : "clasifica"
    CHOFER |o--o{ UNIDAD : "es titular de"
    CHOFER |o--o{ UNIDAD : "es poseedor de"
    TALLER |o--o{ UNIDAD : "aloja actualmente"
    TALLER |o--o{ UNIDAD : "tiene asignada"
    UNIDAD ||--o{ ASIGNACION_UNIDAD : "historial de"
    CHOFER ||--o{ ASIGNACION_UNIDAD : "recibe"
    UNIDAD ||--o{ PRESTAMO_UNIDAD : "se presta"
    CHOFER ||--o{ PRESTAMO_UNIDAD : "presta"
    CHOFER ||--o{ PRESTAMO_UNIDAD : "recibe"
    SUPERVISOR |o--o{ PRESTAMO_UNIDAD : "autoriza"
    UNIDAD ||--o{ JORNADA : "se opera en"
    CHOFER ||--o{ JORNADA : "abre"
    UNIDAD ||--o{ UBICACION_UNIDAD : "reporta"
    UNIDAD |o--o| CHOFER_GRUA : "es su grúa"
    UNIDAD |o--o{ TECNICO : "es su vehículo de servicio"
```

`ESTADOS_UNIDAD` = `disponible · en_ruta · varada · en_arrastre · en_taller ·
en_reparacion · lista · baja`

---

## 3. Paquete C — Taller: zonas, espacios y ocupación (3 tablas)

Las dos banderas de `ZONA_TALLER` no son redundantes y confundirlas rompe la agenda:
`admite_unidades` = ¿cabe físicamente una unidad? · `cuenta_para_ocupacion` = ¿cuenta
como capacidad de reparación? El patio admite unidades pero no es capacidad.

```mermaid
erDiagram
    ZONA_TALLER {
        int id PK
        int taller_id FK "NN"
        string nombre "NN"
        string proposito "operativa"
        int capacidad
        bool admite_unidades "NN, ¿cabe aquí?"
        bool cuenta_para_ocupacion "NN, ¿es capacidad?"
        int orden
    }
    ESPACIO {
        int id PK
        int zona_id FK "NN"
        string numero "NN, UK con zona_id"
        int tipo_unidad_permitido_id FK
        string estado "NN, libre u ocupado"
        int pos_x "plano"
        int pos_y "plano"
        bool activo
    }
    OCUPACION_ESPACIO {
        int id PK
        int espacio_id FK "NN"
        int unidad_id FK "NN"
        int orden_servicio_id FK
        datetime fecha_entrada
        datetime fecha_salida "NULL = abierta"
        int colocado_por_admin_id FK
        int retirado_por_admin_id FK
    }

    TALLER ||--o{ ZONA_TALLER : "se divide en"
    ZONA_TALLER ||--o{ ESPACIO : "contiene"
    TIPO_UNIDAD |o--o{ ESPACIO : "restringe"
    ESPACIO ||--o{ OCUPACION_ESPACIO : "historial de"
    UNIDAD ||--o{ OCUPACION_ESPACIO : "ocupa"
    ORDEN_SERVICIO |o--o{ OCUPACION_ESPACIO : "motiva"
```

**Índices únicos parciales** (viven en `models.py`, no en la clase, y Mermaid no los
sabe dibujar):

| Índice | Regla que impone |
|---|---|
| `uq_ocupacion_abierta_por_unidad` | una unidad no puede estar en dos espacios a la vez |
| `uq_ocupacion_abierta_por_espacio` | un espacio no puede tener dos unidades a la vez |
| `uq_orden_abierta_por_unidad` | una unidad no puede tener dos órdenes abiertas |

Los tres son `UNIQUE ... WHERE fecha_salida IS NULL`.

---

## 4. Paquete D — Mantenimiento preventivo y agenda (7 tablas)

La separación clave: `PROGRAMA_MANTENIMIENTO.fecha_limite` viene del plan y **nunca**
se mueve (compromiso técnico); `CITA_TALLER.fecha_cita` la asigna la agenda según
capacidad y **sí** se mueve. Por eso el chofer solo incumple si faltó a una cita
confirmada: si el taller nunca pudo dársela, el problema es de capacidad.

```mermaid
erDiagram
    TIPO_SERVICIO {
        int id PK
        string nombre UK "NN"
        int criticidad "NN, 1 seguridad 2 preventivo 3 estético"
        int duracion_estimada_dias "NN"
        float duracion_mediana_dias "la que manda"
        int duracion_p90_dias
        float duracion_real_promedio "solo para costo"
        int muestras_medidas "NN"
        bool ocupa_espacio "NN, false = servicio de paso"
        string origen_duracion "NN, estimado o medido"
        bool requiere_fosa
        bool activo "NN"
    }
    PLAN_MANTENIMIENTO {
        int id PK
        int tipo_unidad_id FK
        string nombre "NN"
        int tipo_servicio_id FK
        int periodicidad_dias
        int periodicidad_km
        text descripcion
        bool activo
    }
    PROGRAMA_MANTENIMIENTO {
        int id PK
        int unidad_id FK "NN"
        int plan_id FK "NN"
        date fecha_programada
        int km_programado
        date fecha_limite "NN, INMUTABLE"
        string estado "NN"
        int orden_servicio_id FK
        datetime fecha_cumplimiento
        datetime creado_en
        datetime actualizado_en
    }
    CITA_TALLER {
        int id PK
        int taller_id FK "NN"
        int unidad_id FK "NN"
        int programa_mantenimiento_id FK
        int solicitud_id FK
        int tipo_servicio_id FK
        date fecha_cita "NN, SÍ se mueve"
        date fecha_limite_origen "copiada del programa"
        int duracion_estimada_dias
        string estado "NN, ver ESTADOS_CITA"
        int veces_reprogramada "NN"
        int score_prioridad
        string origen_agenda "automatica o manual"
        datetime fecha_confirmacion_taller
        datetime fecha_confirmacion_chofer
        int agendada_por_usuario_id FK
        datetime creado_en
        datetime actualizado_en
    }
    REPROGRAMACION {
        int id PK
        int cita_id FK "NN"
        date fecha_anterior "NN"
        date fecha_nueva "NN"
        string motivo "NN, sin_espacio unidad_atorada urgencia_desplaza"
        bool automatica "NN"
        bool requirio_autorizacion
        bool aviso_enviado
        int usuario_id FK
        datetime fecha "NN"
    }
    AVISO_INCUMPLIMIENTO {
        int id PK
        int cita_id FK "UK"
        int unidad_id FK "NN"
        int chofer_id FK "NN"
        string fundamento_poseedor "jornada prestamo titularidad"
        int jornada_id FK
        int prestamo_id FK
        int asignacion_id FK
        date fecha_generacion "NN"
        int dias_atraso
        string estado "NN, abierto atendido anulado"
        datetime fecha_atencion
        int atendido_por_usuario_id FK
        text nota_atencion
        int veces_recordado "NN"
        datetime creado_en
        datetime actualizado_en
    }
    PENALIZACION {
        int id PK "LEGADO v1.1, ya nadie escribe"
        int chofer_id FK "NN"
        int unidad_id FK "NN"
        int programa_mantenimiento_id FK "UK"
        string motivo "NN"
        date fecha_generacion
        int dias_atraso
        string estado "NN"
        int aplicada_por_usuario_id FK
        text resolucion_disputa
    }

    TIPO_UNIDAD |o--o{ PLAN_MANTENIMIENTO : "aplica a"
    TIPO_SERVICIO |o--o{ PLAN_MANTENIMIENTO : "define trabajo de"
    PLAN_MANTENIMIENTO ||--o{ PROGRAMA_MANTENIMIENTO : "instancia"
    UNIDAD ||--o{ PROGRAMA_MANTENIMIENTO : "tiene programado"
    ORDEN_SERVICIO |o--o{ PROGRAMA_MANTENIMIENTO : "cumple"
    PROGRAMA_MANTENIMIENTO |o--o{ CITA_TALLER : "se agenda como"
    TALLER ||--o{ CITA_TALLER : "recibe"
    UNIDAD ||--o{ CITA_TALLER : "asiste a"
    TIPO_SERVICIO |o--o{ CITA_TALLER : "tipifica"
    SOLICITUD_INGRESO |o--o{ CITA_TALLER : "origina"
    CITA_TALLER ||--o{ REPROGRAMACION : "append-only"
    CITA_TALLER |o--o| AVISO_INCUMPLIMIENTO : "genera al faltar"
    CHOFER ||--o{ AVISO_INCUMPLIMIENTO : "responsable de"
    JORNADA |o--o{ AVISO_INCUMPLIMIENTO : "funda"
    PRESTAMO_UNIDAD |o--o{ AVISO_INCUMPLIMIENTO : "funda"
    ASIGNACION_UNIDAD |o--o{ AVISO_INCUMPLIMIENTO : "funda"
    PROGRAMA_MANTENIMIENTO |o--o| PENALIZACION : "legado"
```

`ESTADOS_CITA` = `propuesta · confirmada · reprogramada · cumplida · no_asistio ·
cancelada`

---

## 5. Paquete E — Orden de servicio y traslados (5 tablas)

`ASIGNACION_TECNICO` guarda **dos** responsables por diseño (RN-11): `tecnico_id` es
quien hizo el trabajo, `capturado_por_admin_id` es quien lo tecleó. Los técnicos
ASISTIDO no usan la app.

```mermaid
erDiagram
    SOLICITUD_INGRESO {
        int id PK
        int unidad_id FK "NN"
        int chofer_id FK "NN"
        int taller_id FK "NN"
        string tipo "correctivo"
        text descripcion_falla
        string urgencia "media"
        datetime fecha_solicitud
        string estado "NN"
        int atendida_por_admin_id FK
        datetime fecha_respuesta
        string motivo_rechazo
        date fecha_ingreso_programada
        datetime creado_en
        datetime actualizado_en
    }
    ORDEN_SERVICIO {
        int id PK
        string folio UK "NN"
        int unidad_id FK "NN"
        int taller_id FK "NN"
        int solicitud_id FK
        int arrastre_id FK
        int tipo_servicio_id FK "para medir duración real"
        int chofer_responsable_id FK
        datetime fecha_entrada
        date fecha_salida_estimada "disparador D3 de la agenda"
        datetime fecha_salida "NULL = abierta"
        string estado "NN"
        int km_entrada
        int km_salida
        string tipo "correctivo o preventivo"
        int abierta_por_admin_id FK
        datetime creado_en
        datetime actualizado_en
    }
    ASIGNACION_TECNICO {
        int id PK
        int orden_servicio_id FK "NN"
        int tecnico_id FK "NN, quién lo hizo"
        string especialidad
        int orden_en_cola "NN"
        string estado "NN, en_espera etc"
        datetime fecha_asignacion
        datetime fecha_inicio
        datetime fecha_fin
        text diagnostico
        text trabajo_realizado
        int asignado_por_admin_id FK
        int capturado_por_admin_id FK "RN-11, quién lo tecleó"
        datetime fecha_captura
    }
    FORMATO_SALIDA {
        int id PK
        int orden_servicio_id FK "UK, NN"
        datetime fecha
        int entregado_a_chofer_id FK
        int elaborado_por_admin_id FK
        text operacion_a_realizar
        bool unidad_operativa
        int km_salida "RETIRADO, se conserva histórico"
        text observaciones "RETIRADO"
        text trabajos_realizados "RETIRADO"
    }
    TRASLADO_UNIDAD {
        int id PK
        int unidad_id FK "NN"
        int taller_origen_id FK "NN"
        int taller_destino_id FK "NN"
        int orden_servicio_origen_id FK
        int orden_servicio_destino_id FK
        int solicitado_por_tecnico_id FK
        text motivo "NN"
        bool requiere_grua "NN"
        int arrastre_id FK
        string estado "NN"
        datetime fecha_solicitud "NN"
        int autorizado_por_usuario_id FK
        datetime fecha_autorizacion
        text motivo_rechazo
        datetime fecha_salida
        datetime fecha_llegada
        datetime creado_en
        datetime actualizado_en
    }

    UNIDAD ||--o{ SOLICITUD_INGRESO : "se solicita para"
    CHOFER ||--o{ SOLICITUD_INGRESO : "levanta"
    TALLER ||--o{ SOLICITUD_INGRESO : "recibe"
    SOLICITUD_INGRESO |o--o{ ORDEN_SERVICIO : "deriva en"
    UNIDAD ||--o{ ORDEN_SERVICIO : "entra con"
    TALLER ||--o{ ORDEN_SERVICIO : "ejecuta"
    TIPO_SERVICIO |o--o{ ORDEN_SERVICIO : "tipifica"
    ARRASTRE |o--o{ ORDEN_SERVICIO : "entrega para"
    ORDEN_SERVICIO ||--o{ ASIGNACION_TECNICO : "reparte en"
    TECNICO ||--o{ ASIGNACION_TECNICO : "ejecuta"
    ORDEN_SERVICIO ||--o| FORMATO_SALIDA : "cierra con"
    CHOFER |o--o{ FORMATO_SALIDA : "recibe unidad"
    UNIDAD ||--o{ TRASLADO_UNIDAD : "se traslada"
    TALLER ||--o{ TRASLADO_UNIDAD : "origen"
    TALLER ||--o{ TRASLADO_UNIDAD : "destino"
    TECNICO |o--o{ TRASLADO_UNIDAD : "solicita"
    ARRASTRE |o--o{ TRASLADO_UNIDAD : "mueve"
```

---

## 6. Paquete F — Piezas, almacén y compras (10 tablas)

Dos caminos distintos que **no** hay que fusionar:

| | `SOLICITUD_PIEZA` | `REQUISICION` |
|---|---|---|
| Qué es | **una** pieza | un **documento** con folio y N renglones |
| Quién la levanta | el mecánico autónomo, desde su teléfono | el capturista, tecleando el papel |
| Quién la pide | el mismo que la levanta | otro; el papel lo firman 3 personas |
| Origen | app | `REQUIS 2026 2.xlsx` |

```mermaid
erDiagram
    PIEZA {
        int id PK
        string sku UK "NN"
        string codigo_externo "indexado, SAP"
        string origen_codigo
        string nombre "NN"
        text descripcion
        string unidad_medida "pieza"
        decimal precio_referencia
        int stock_actual "global, legado"
        int stock_minimo
        bool activa
    }
    EXISTENCIA {
        int id PK
        int taller_id FK "NN, UK con pieza_id"
        int pieza_id FK "NN"
        int stock_actual "NN"
        int stock_reservado "NN"
        int stock_minimo
        string ubicacion_fisica
        datetime creado_en
        datetime actualizado_en
    }
    PROVEEDOR {
        int id PK
        string nombre "NN"
        string rfc
        string contacto
        string telefono
        string email
        bool activo
    }
    PRESUPUESTO {
        int id PK
        string folio UK "NN"
        int orden_servicio_id FK "NN"
        int tecnico_elaboro_id FK "NN, lo hizo en papel"
        int capturado_por_admin_id FK "NN, RN-11"
        date fecha_elaboracion "la del papel"
        datetime fecha_captura
        string folio_papel
        decimal costo_mano_obra
        decimal subtotal_piezas
        decimal total
        string estado "NN"
        text diagnostico
        int dias_estimados_reparacion
        datetime fecha_aviso_al_tecnico
        datetime creado_en
        datetime actualizado_en
    }
    DETALLE_PRESUPUESTO {
        int id PK
        int presupuesto_id FK "NN"
        int pieza_id FK "opcional"
        string descripcion_libre "si no está en catálogo"
        decimal cantidad
        decimal precio_unitario
        decimal importe
        bool disponible_en_almacen
    }
    AUTORIZACION {
        int id PK
        int presupuesto_id FK "NN"
        int usuario_id FK "NN"
        string nivel "NN, administrador o gerente"
        string resultado "NN, aprobado rechazado devuelto remitido"
        datetime fecha
        text comentario
    }
    ORDEN_COMPRA {
        int id PK
        string folio UK "NN"
        int presupuesto_id FK "NN"
        int proveedor_id FK
        int autorizada_por_admin_id FK
        datetime fecha_emision
        string estado "NN"
        date fecha_estimada_llegada
        datetime fecha_recepcion
        decimal total
        string numero_rastreo
        datetime creado_en
        datetime actualizado_en
    }
    SOLICITUD_PIEZA {
        int id PK
        string folio UK
        int tecnico_id FK "NN"
        int taller_id FK "NN"
        int orden_servicio_id FK
        int pieza_id FK
        string descripcion_libre
        int cantidad "NN"
        text justificacion
        string estado "NN, ver ESTADOS_SOLICITUD_PIEZA"
        datetime fecha_solicitud "NN"
        int evaluada_por_usuario_id FK
        datetime fecha_evaluacion
        text motivo_rechazo
        date fecha_estimada_llegada
        datetime fecha_surtido
        datetime creado_en
        datetime actualizado_en
    }
    REQUISICION {
        int id PK
        string folio "NN, indexado, NO único"
        date fecha "NN, la del papel"
        int taller_id FK
        int unidad_id FK
        string unidad_texto "si no casó con el catálogo"
        string equipo_sap
        string centro_gestion "CEGE, AL01 AL07"
        int tecnico_id FK
        string solicitante_num_empleado
        string solicitante_nombre
        int capturada_por_usuario_id FK
        datetime fecha_captura
        string estado "NN"
        string origen "NN, app o excel"
        text observaciones
        datetime creado_en
        datetime actualizado_en
    }
    RENGLON_REQUISICION {
        int id PK
        int requisicion_id FK "NN"
        int linea "NN, UK con requisicion_id"
        int pieza_id FK "opcional a propósito"
        string codigo "indexado, tecleado del papel"
        string descripcion "NN"
        int cantidad "NN"
        decimal costo_unitario
        bool surtido
    }

    PIEZA ||--o{ EXISTENCIA : "se almacena en"
    TALLER ||--o{ EXISTENCIA : "guarda"
    ORDEN_SERVICIO ||--o{ PRESUPUESTO : "se cotiza en"
    TECNICO ||--o{ PRESUPUESTO : "elabora"
    USUARIO ||--o{ PRESUPUESTO : "captura"
    PRESUPUESTO ||--o{ DETALLE_PRESUPUESTO : "detalla"
    PIEZA |o--o{ DETALLE_PRESUPUESTO : "se cotiza como"
    PRESUPUESTO ||--o{ AUTORIZACION : "historial de"
    USUARIO ||--o{ AUTORIZACION : "resuelve"
    PRESUPUESTO ||--o{ ORDEN_COMPRA : "ejecuta"
    PROVEEDOR |o--o{ ORDEN_COMPRA : "surte"
    TECNICO ||--o{ SOLICITUD_PIEZA : "levanta"
    TALLER ||--o{ SOLICITUD_PIEZA : "atiende"
    ORDEN_SERVICIO |o--o{ SOLICITUD_PIEZA : "motiva"
    PIEZA |o--o{ SOLICITUD_PIEZA : "se pide"
    REQUISICION ||--o{ RENGLON_REQUISICION : "lista"
    PIEZA |o--o{ RENGLON_REQUISICION : "reconcilia con"
    UNIDAD |o--o{ REQUISICION : "es para"
    TECNICO |o--o{ REQUISICION : "solicita"
    TALLER |o--o{ REQUISICION : "surte"
```

`ESTADOS_SOLICITUD_PIEZA` = `enviada · en_evaluacion · surtida_de_almacen ·
aprobada_para_compra · en_compra · en_transito · recibida · rechazada`

`ESTADOS_REQUISICION` = `capturada · autorizada · surtida · cancelada`

---

## 7. Paquete G — Averías, auxilio en carretera y arrastre (8 tablas)

`ORDEN_AUXILIO` usa **difusión y toma**: se manda a todos los autónomos disponibles y
el primero que acepta la gana. Por eso hacen falta las dos tablas hijas —
`DIFUSION_AUXILIO` prueba a quién se le avisó, `RESPUESTA_AUXILIO` guarda también las
negativas con su motivo.

```mermaid
erDiagram
    REPORTE_AVERIA {
        int id PK
        string folio UK "NN"
        int unidad_id FK "NN"
        int chofer_id FK "NN"
        datetime fecha_hora
        float latitud
        float longitud
        string direccion_referencia
        text descripcion_falla
        bool en_vialidad_publica "NN, RN-04"
        bool hay_terceros_involucrados
        bool requiere_arrastre
        string estado "NN"
        int supervisor_notificado_id FK
        datetime creado_en
        datetime actualizado_en
    }
    REPORTE_PERITAJE {
        int id PK
        int reporte_averia_id FK "UK, NN"
        string folio_peritos "NN"
        string aseguradora
        datetime hora_aviso
        datetime hora_llegada_perito
        string nombre_perito
        string resultado
        text observaciones
        bool liberada_la_unidad
    }
    ORDEN_AUXILIO {
        int id PK
        string folio UK
        int reporte_averia_id FK "UK"
        datetime fecha_emision "NN"
        string estado "NN, ver ESTADOS_AUXILIO"
        int tecnico_acepta_id FK "el primero que aceptó"
        datetime fecha_aceptacion
        datetime fecha_llegada
        datetime fecha_cierre
        bool resuelto_en_sitio
        int arrastre_id FK
        datetime creado_en
        datetime actualizado_en
    }
    DIFUSION_AUXILIO {
        int id PK
        int orden_auxilio_id FK "NN, UK con tecnico_id"
        int tecnico_id FK "NN"
        datetime notificado_en "NN"
        float distancia_km_estimada
    }
    RESPUESTA_AUXILIO {
        int id PK
        int orden_auxilio_id FK "NN, UK con tecnico_id"
        int tecnico_id FK "NN"
        bool puede_atender "NN, guarda también las negativas"
        string motivo_negativa
        datetime fecha "NN"
    }
    ARRASTRE {
        int id PK
        string folio UK "NN"
        int reporte_averia_id FK "NN"
        int chofer_grua_id FK
        int unidad_arrastrada_id FK "NN"
        int unidad_grua_id FK
        int chofer_responsable_id FK
        int taller_destino_id FK
        string estado "NN"
        datetime fecha_solicitud
        datetime fecha_aceptacion
        datetime fecha_llegada_sitio
        datetime fecha_finalizacion
        string motivo_rechazo
        float km_recorridos
        datetime creado_en
        datetime actualizado_en
    }
    UBICACION_ARRASTRE {
        int id PK
        int arrastre_id FK "NN"
        float latitud "NN"
        float longitud "NN"
        datetime capturado_en
        string emisor "chofer_grua"
    }
    EVIDENCIA {
        int id PK
        string entidad_tipo "NN, POLIMÓRFICA"
        int entidad_id "NN, sin FK real"
        string url_archivo "NN"
        string descripcion
        string momento
        int subida_por_usuario_id FK
        datetime fecha
    }

    UNIDAD ||--o{ REPORTE_AVERIA : "se avería"
    CHOFER ||--o{ REPORTE_AVERIA : "reporta"
    SUPERVISOR |o--o{ REPORTE_AVERIA : "se notifica a"
    REPORTE_AVERIA ||--o| REPORTE_PERITAJE : "RN-04, exige"
    REPORTE_AVERIA ||--o| ORDEN_AUXILIO : "escala a"
    ORDEN_AUXILIO ||--o{ DIFUSION_AUXILIO : "se difunde a"
    TECNICO ||--o{ DIFUSION_AUXILIO : "recibe aviso"
    ORDEN_AUXILIO ||--o{ RESPUESTA_AUXILIO : "recibe"
    TECNICO ||--o{ RESPUESTA_AUXILIO : "contesta"
    TECNICO |o--o{ ORDEN_AUXILIO : "gana la toma"
    REPORTE_AVERIA ||--o| ARRASTRE : "escala a"
    ORDEN_AUXILIO |o--o| ARRASTRE : "escala a"
    CHOFER_GRUA |o--o{ ARRASTRE : "ejecuta"
    UNIDAD ||--o{ ARRASTRE : "es arrastrada"
    UNIDAD |o--o{ ARRASTRE : "es la grúa"
    TALLER |o--o{ ARRASTRE : "recibe"
    ARRASTRE ||--o{ UBICACION_ARRASTRE : "rastrea con"
    USUARIO |o--o{ EVIDENCIA : "sube"
```

`ESTADOS_AUXILIO` = `difundida · aceptada · en_ruta · en_sitio · resuelta ·
escalada_a_arrastre · cancelada`

---

## 8. Paquete H — Transversales (4 tablas)

```mermaid
erDiagram
    NOTIFICACION {
        int id PK
        int usuario_id FK "NN"
        string tipo
        string titulo "NN"
        text mensaje
        string entidad_tipo "polimórfica"
        int entidad_id "sin FK real"
        bool leida "NN"
        datetime fecha_envio
        datetime fecha_lectura
    }
    ALERTA_GERENCIA {
        int id PK
        string tipo "NN"
        int unidad_id FK
        int chofer_id FK
        datetime fecha_generacion
        int veces_notificada "RN-08, reincide"
        datetime ultima_notificacion
        bool atendida "NN"
        datetime fecha_atencion
        int atendida_por_usuario_id FK
        text detalle
    }
    BITACORA_AUDITORIA {
        int id PK
        int usuario_id FK
        string accion "NN"
        string entidad_tipo "polimórfica"
        int entidad_id "sin FK real"
        text datos_antes "JSON"
        text datos_despues "JSON"
        datetime fecha
        string ip_origen
    }
    CONFIGURACION {
        int id PK
        string clave UK "NN"
        string valor "NN"
        string descripcion
        string tipo_dato "int str bool"
    }

    USUARIO ||--o{ NOTIFICACION : "recibe"
    UNIDAD |o--o{ ALERTA_GERENCIA : "dispara"
    CHOFER |o--o{ ALERTA_GERENCIA : "involucra"
    USUARIO |o--o{ ALERTA_GERENCIA : "atiende"
    USUARIO |o--o{ BITACORA_AUDITORIA : "genera"
```

---

## 9. Paquete I — Auditorías de campo a reparto (6 tablas) · **PROPUESTO**

> **Este paquete no existe todavía en `bajagas.db`.** Es el diseño derivado de los dos documentos
> que entregó el cliente; el análisis y lo que falta decidir están en
> [`auditorias-de-campo.md`](auditorias-de-campo.md). No lo cuentes en el inventario verificado de
> §10 hasta que esté migrado.

Tres decisiones sostienen el diseño:

**El cuestionario es catálogo, no columnas.** Los 18 puntos SÍ/NO de las secciones 1 y 3 del
formato viven en `PUNTO_AUDITORIA` y las respuestas en renglones. Con 18 columnas booleanas, cada
vez que el cliente agregue o quite una pregunta habría que migrar la base — y ese formato dice
«FORMATO 2026» en el encabezado, o sea que ya va por versiones.

**El GPS va en la foto, no en la auditoría.** El documento pide latitud, longitud y precisión
«al momento de la foto», y un supervisor se mueve entre una toma y otra. Ponerlo en la cabecera
mediría dónde empezó la auditoría, no dónde se tomó cada evidencia — que es justo lo que hay que
poder defender. Por eso `EVIDENCIA`, que ya es polimórfica, gana columnas en vez de nacer una
tabla de fotos nueva.

**La productividad va aparte.** La sección 4 del formato está declarada fuera de alcance en
`requerimientos.md` §1 y como Won't en RF-SUP-11. Si el cliente confirma que no entra, se borra
una tabla; si estuviera mezclada en la cabecera, habría que desenredar ocho columnas.

```mermaid
erDiagram
    ZONA_REPARTO {
        int id PK
        string nombre UK "NN"
        string ciudad
        string estado_geo "B.C."
        bool activa "NN"
    }
    AUDITORIA_CAMPO {
        int id PK
        string folio UK "NN, AUD-2026-001245"
        int supervisor_id FK "NN, quien la levanta"
        int chofer_id FK "NN, el POSEEDOR del dia, RN-01"
        int unidad_id FK "NN"
        string ruta "copiada de chofer.ruta al levantarla"
        int zona_id FK
        string colonia_calle
        int odometro "copiado de unidad.km_actual"
        datetime fecha_hora_dispositivo "NN"
        datetime fecha_hora_servidor "la que vale si hay señal"
        bool sin_conexion "NN, se levantó offline"
        datetime sincronizada_en
        bool licencia_vigente "auto: chofer.vencimiento_licencia"
        text hallazgo_principal
        text accion_compromiso
        string resultado "NN, CUMPLE|OBSERVACION|CRITICO"
        date seguimiento_fecha
        int seguimiento_responsable_id FK
        string firma_chofer "trazo o registro"
        string firma_supervisor
        datetime cerrada_en "NN una vez firmada: ya no se edita"
        datetime creado_en
        datetime actualizado_en
    }
    PUNTO_AUDITORIA {
        int id PK
        string version_formato "NN, 2026"
        int seccion "NN, 1=control 3=comercial"
        int orden "NN"
        string texto "NN"
        bool activo "NN"
    }
    RESPUESTA_AUDITORIA {
        int id PK
        int auditoria_id FK "NN, UK con punto_id"
        int punto_id FK "NN"
        bool cumple "NN"
        string observacion
    }
    INVENTARIO_ENVASES {
        int id PK
        int auditoria_id FK "NN, UK con presentacion"
        string presentacion "NN, 10|20|45 kg"
        int llenos "NN"
        int vacios "NN"
        string observacion
    }
    OBSERVACION_PRODUCTIVIDAD {
        int id PK
        int auditoria_id FK "UK, NN"
        float venta_acumulada_kg
        time hora_corte
        int piezas_10kg
        int piezas_45kg
        int clientes_atendidos
        int paradas_observadas
        int ventas_observadas
        int prospectos_detectados
        int minutos_observados
        int minutos_improductivos
    }
    EVIDENCIA {
        int id PK
        string entidad_tipo "NN, 'auditoria' reusa lo que ya existe"
        int entidad_id "NN, sin FK real"
        string url_archivo "NN, la ORIGINAL, se conserva"
        string url_sellada "la que lleva el sello visible"
        string hash_imagen "detecta duplicados"
        float latitud
        float longitud
        float precision_gps "umbral 30-50 m, RN-18"
        string direccion_aproximada
        datetime hora_dispositivo
        datetime hora_servidor
        bool sin_conexion
        string descripcion
        int subida_por_usuario_id FK
        datetime fecha
    }

    ZONA_REPARTO       ||--o{ AUDITORIA_CAMPO : "ubica"
    AUDITORIA_CAMPO    ||--o{ RESPUESTA_AUDITORIA : "contesta"
    PUNTO_AUDITORIA    ||--o{ RESPUESTA_AUDITORIA : "se pregunta en"
    AUDITORIA_CAMPO    ||--o{ INVENTARIO_ENVASES : "cuenta"
    AUDITORIA_CAMPO    ||--o| OBSERVACION_PRODUCTIVIDAD : "observa"
    AUDITORIA_CAMPO    ||--o{ EVIDENCIA : "prueba con"
```

**Restricciones que sostienen el paquete:**

- `UNIQUE(auditoria_id, punto_id)` — una respuesta por pregunta. Sin esto, sincronizar dos veces
  la misma auditoría offline la duplicaría renglón por renglón.
- `UNIQUE(auditoria_id, presentacion)` — un conteo por presentación de envase.
- `UNIQUE(hash_imagen)` **no** va: la misma foto puede aparecer legítimamente en dos auditorías
  distintas. El hash sirve para *detectar* el caso y revisarlo, no para impedirlo.
- **Una auditoría con `cerrada_en` no se reescribe.** Misma regla que el formato de mantenimiento
  (CU-ADM-29): un papel firmado editado sin rastro deja de servir como prueba. Para corregir, se
  levanta otra.
- `resultado` y `precision_gps` son obligatorios antes de cerrar. Una auditoría sin precisión GPS
  registrada no prueba dónde se levantó.

---

## 10. Inventario verificado

| Paquete | Tablas | Módulo |
|---|---|---|
| A · Organización, plantas y personas | 11 | `modules/organizacion/` |
| B · Flota y responsabilidad | 6 | `modules/flota/` |
| C · Taller, zonas y espacios | 3 | `modules/taller/` |
| D · Mantenimiento y agenda | 7 | `modules/mantenimiento/` |
| E · Órdenes de servicio y traslados | 5 | `modules/ordenes/` |
| F · Piezas, almacén y compras | 10 | `modules/piezas/` |
| G · Emergencias, auxilio y arrastre | 8 | `modules/emergencias/` |
| H · Transversales | 4 | `modules/sistema/` |
| **Total** | **54** | coincide con `bajagas.db` |

| Paquete | Tablas | Estado |
|---|---|---|
| I · Auditorías de campo a reparto | 6 | **Propuesto**, §9. No está en la base ni cuenta en el total |
