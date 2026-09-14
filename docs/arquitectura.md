# Arquitectura del código — dónde vive cada cosa

**Versión:** 1.0 · **Fecha:** 2026-08-20
**Deriva de:** [modelo-clases.md](modelo-clases.md) — las carpetas son los paquetes del diagrama.

---

## La regla, en una línea

> **`_model` no sabe de nada · `_service` no sabe de HTTP · `_controller` no toca la base.**

Y `core/` es lo transversal: no contiene reglas de negocio, solo la maquinaria.

Si necesitas cambiar algo, el nombre del archivo te dice si es el lugar correcto:

| Vas a cambiar… | Toca |
|---|---|
| Una tabla, una columna, una relación | `<algo>_model.py` |
| Una regla de negocio o cómo se serializa | `<dominio>_service.py` |
| Una ruta, un permiso, un código de error HTTP | `<dominio>_controller.py` |
| Zona horaria, hash de contraseñas, conexión | `core/` |

---

## Carpeta ↔ paquete del diagrama

| Paquete UML | Carpeta | Clases |
|---|---|---|
| **A** · Organización | `modules/organizacion/` | Planta, Taller, Usuario, Rol, UsuarioRol, Chofer, Supervisor, Chofer de grúa, LimiteAutorizacion, Cuadrilla, Tecnico |
| **B** · Flota | `modules/flota/` | TipoUnidad, Unidad, AsignacionUnidad, PrestamoUnidad, Jornada, UbicacionUnidad |
| **C** · Taller | `modules/taller/` | ZonaTaller, Espacio, OcupacionEspacio |
| **D** · Mantenimiento | `modules/mantenimiento/` | PlanMantenimiento, ProgramaMantenimiento, TipoServicio, CitaTaller, Reprogramacion, AvisoIncumplimiento |
| **E** · Órdenes | `modules/ordenes/` | SolicitudIngreso, OrdenServicio, AsignacionTecnico, FormatoSalida, TrasladoUnidad |
| **F** · Piezas | `modules/piezas/` | Pieza, Existencia, SolicitudPieza, Presupuesto, DetallePresupuesto, Autorizacion, Proveedor, OrdenCompra |
| **G** · Emergencias | `modules/emergencias/` | ReporteAveria, ReportePeritaje, OrdenAuxilio, DifusionAuxilio, RespuestaAuxilio, Arrastre, UbicacionArrastre, Evidencia |
| **H** · Sistema | `modules/sistema/` | Notificacion, AlertaGerencia, BitacoraAuditoria, Configuracion |

---

## El árbol

```
backend/app/
├── main.py                    arranque, CORS, monta los 6 controllers
├── models.py                  FACHADA: reexporta todas las clases
├── services.py                FACHADA: reexporta todos los servicios
├── schemas.py                 contratos de entrada/salida de la API (Pydantic)
├── seed.py                    datos base y catálogo de las 6 plantas
├── importador.py              carga los archivos reales de Baja Gas
├── jobs.py                    los 3 procesos automáticos (CU-AUT-*)
│
├── core/                      ── infraestructura, sin reglas de negocio
│   ├── database.py            conexión y sesión
│   ├── base_model.py          Base declarativa + sellos de tiempo
│   ├── tiempo.py              UTC ↔ America/Tijuana — el único reloj
│   ├── security.py            hash, JWT, dependencias de rol
│   └── migraciones.py         columnas e índices que create_all no aplica
│
└── modules/                   ── un paquete por paquete del UML
    ├── organizacion/          planta · usuario · cuadrilla · tecnico + auth_controller
    ├── flota/                 unidad · prestamo · jornada · ubicacion
    │                          + flota_service + chofer_controller + supervisor_controller
    ├── taller/                espacio + taller_service + administrador_controller
    ├── mantenimiento/         plan · servicio · cita · aviso + mantenimiento_service
    ├── ordenes/               solicitud · orden · traslado
    ├── piezas/                pieza · solicitud_pieza · presupuesto · compra + piezas_service
    ├── emergencias/           averia · auxilio · arrastre · evidencia
    │                          + emergencias_service + chofer de grúa_controller
    └── sistema/               notificacion · bitacora · configuracion
                               + comun_service + gerente_controller
```

**56 archivos Python · 8 paquetes · 52 tablas · 84 rutas.**

---

## Por qué `models.py` y `services.py` siguen existiendo

Son **fachadas**, no archivos de contenido. Reexportan lo que vive en los módulos, y cumplen dos funciones concretas:

1. **SQLAlchemy necesita que TODAS las clases estén registradas** antes de `create_all()`. Importar la fachada garantiza que ninguna tabla falte por no haberse importado su módulo.
2. Los controllers siguen usando `from ... import models as m`. Sin la fachada, la reestructuración habría obligado a reescribir cada consulta del proyecto de un jalón, con todo lo que eso rompe.

Cuando escribas código nuevo, importa **del módulo**, no de la fachada:

```python
from ..flota.unidad_model import Unidad        # preferible
from ... import models as m                    # sigue funcionando
```

---

## Dónde están las reglas que más se consultan

| Regla | Archivo |
|---|---|
| **RN-01** — quién responde por la unidad (jornada > préstamo > titular) | `modules/flota/flota_service.py` → `poseedor_actual()` |
| **RN-06** — no se acepta ingreso sin espacio compatible | `modules/taller/taller_service.py` → `espacios_libres_compatibles()` |
| **RN-04** — peritos antes que grúa | `modules/emergencias/emergencias_service.py` → `puede_solicitar_arrastre()` |
| **RN-05** — aviso de incumplimiento (ya no penalización) | `jobs.py` → `generar_avisos_incumplimiento()` |
| Vehículo duplicado en taller | `modules/taller/administrador_controller.py` + índices en `models.py` |
| Zona horaria | `core/tiempo.py` — **el único lugar** |

---

## El frontend

Se organiza por **rol**, no por dominio, y es a propósito: el backend modela el
negocio (paquetes del diagrama de clases), la interfaz modela a las **personas**
(módulos del diagrama de casos de uso). Cada carpeta es un actor.

```
frontend/src/
├── App.jsx                    ruteo por rol y barra de navegación
├── core/
│   ├── api.js                 cliente HTTP + formato de fechas en Tijuana
│   ├── sesion.js              token, usuario y rol — no habla con la API
│   └── tema.js                claro por defecto, oscuro opcional
├── ui/                        componentes compartidos, uno por archivo
│   ├── Card · Kpi · Badge · Modal · Tabla · Feedback · Toast · useApi
│   └── index.js               barril: `import { Card } from '../../ui/index.js'`
└── modules/
    ├── acceso/          LoginPage             CU-GEN-01
    ├── chofer/          ChoferPage            CU-CHO-*
    ├── supervisor/      SupervisorPage        CU-SUP-*
    ├── administrador/   9 archivos, ver abajo CU-ADM-*
    ├── chofer de grúa/  Chofer de grúaPage    CU-MON-*
    ├── gerente/         GerentePage           CU-GER-*
    └── sistema/         NotificacionesPage    CU-GEN-02
```

**Por qué `sesion.js` está separado de `api.js`.** Si la sesión viviera dentro
del cliente HTTP habría una dependencia circular: `api.js` necesita el token en
cada petición, y el login necesita a `api.js` para pedirlo. `sesion.js` solo
lee y escribe credenciales; no conoce la API.

### El módulo Administrador, partido por caso de uso

Era un archivo de 883 líneas con 14 componentes. Ahora:

| Archivo | Caso de uso |
|---|---|
| `AdministradorPage.jsx` | solo enruta — 26 líneas |
| `SolicitudesPage.jsx` | CU-ADM-01 «include» CU-ADM-02 |
| `PlanoPage.jsx` | CU-ADM-03/04 |
| `ModalEspacio.jsx` | CU-ADM-04 — el menú de la casilla |
| `PlanoTaller.jsx` | pieza compartida: el plano y el selector de taller |
| `AlmacenPage.jsx` | CU-ADM-11 — buscador |
| `OrdenesPage.jsx` | CU-ADM-05/06/08/09/10 |
| `PresupuestosPage.jsx` | CU-ADM-17 a 19 |
| `HojaTrabajoPage.jsx` | CU-ADM-07 |

`PlanoTaller` es compartido porque se usa en dos lugares: la pantalla del plano
y el modal de la solicitud, donde el administrador elige la casilla antes de
aceptar el ingreso.

---

## Lo que la reestructuración NO cambió

Ninguna clase se reescribió: se movieron tal cual. Comprobado después de mover:

- **52 tablas** y **84 rutas**, idénticas a antes.
- **13 de 13 endpoints** en 200, cubriendo los cinco roles.
- Los tres jobs automáticos corren.

El frontend no se tocó: la API no cambió de forma.
