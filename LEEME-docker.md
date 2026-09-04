# Levantar Baja Gas en Docker

Dos contenedores: la API (FastAPI) y la pantalla (React ya compilada, servida por
nginx). Se arrancan juntos con un comando y quedan accesibles desde cualquier
dispositivo de la misma red — otra computadora, un teléfono.

```bash
docker compose up -d --build
```

| Qué | Dónde |
|---|---|
| La aplicación | `http://localhost:8081` |
| Desde otro dispositivo | `http://<IP-de-tu-PC>:8081` |
| API y Swagger | `http://localhost:8000/docs` |

Para saber tu IP: `ipconfig` y toma la **Dirección IPv4** del adaptador Wi-Fi.

Comandos del día a día:

```bash
docker compose ps            # estado
docker compose logs -f api   # ver el log de la API en vivo
docker compose restart api   # reiniciar solo la API
docker compose down          # apagar (la base se conserva)
```

---

# Abrirla a internet (gente en otras redes, durante semanas)

La IP local solo sirve dentro de la misma red. Para que alguien la use desde su
casa o desde datos móviles hace falta un **túnel de Cloudflare**: la conexión
sale de tu PC hacia Cloudflare, así que **no hay que abrir el firewall ni tocar
el router**, y la URL viene con HTTPS.

## Antes de abrir nada: rota las contraseñas

Las 325 cuentas activas comparten `bajagas2026`, que está escrita en `seed.py`,
en `importador.py` y en el README. Con una URL pública, esa contraseña es la
puerta abierta a los datos de 335 empleados reales.

```bash
docker compose exec api python -m app.rotar_passwords --si
docker compose cp api:/datos/credenciales.csv ./credenciales.csv
```

Le pone una contraseña distinta y aleatoria a cada cuenta, y deja el CSV con las
claves en claro para que repartas las que necesites. **Ese CSV es la única
copia**: si lo pierdes hay que volver a rotar. Está en `.gitignore`.

Sin `--si` solo simula y te dice a cuántas cuentas les tocaría.

## Levantar el túnel

**Prueba rápida, sin cuenta.** URL `*.trycloudflare.com` que cambia en cada
arranque. Para enseñarle algo a alguien hoy:

```bash
docker compose --profile tunel-rapido up -d
docker compose logs tunel-rapido | grep trycloudflare
```

**URL fija.** Necesita cuenta de Cloudflare y un túnel creado en el panel
(*Zero Trust → Networks → Tunnels*), apuntado a `http://web:80`. Copia el token
que te da, ponlo en `.env` como `TUNNEL_TOKEN=...` y:

```bash
docker compose --profile tunel up -d
```

Para cerrar el túnel en cualquier momento, sin tocar la aplicación:

```bash
docker compose stop tunel tunel-rapido
```

## Vale la pena: pon Cloudflare Access delante

En el mismo panel de Zero Trust puedes exigir que quien entre verifique su
correo antes de siquiera ver la pantalla de login. Es gratis hasta 50 usuarios y
convierte la URL pública en una URL para invitados. Con datos de empleados
reales detrás, es la diferencia entre "cualquiera que dé con el link" y "las
ocho personas que invité".

---

## Lo que ya está endurecido

| Qué | Dónde |
|---|---|
| La pantalla ya no publica la contraseña ni la lista del personal | `LoginPage.jsx`, tras `import.meta.env.DEV` |
| Límite de intentos: 8 por cuenta, 25 por IP, ventana de 15 min | `core/intentos.py` |
| `/login` y `/token` validan igual (antes `/token` no miraba `activo`) | `auth_controller.py` |
| `SECRET_KEY` propia, generada con `secrets.token_hex(32)` | `.env` |
| Aviso ruidoso al arranque si sigue la clave por defecto | `main.py` |

El panel de cuentas del login sigue apareciendo con `npm run dev` — es
`import.meta.env.DEV`, que es `false` en el build que sirve Docker. La comodidad
local se queda; lo que sale al mundo va limpio.

---

## Solo red local (sin túnel)

Si en algún momento quieres el acceso por IP dentro de la misma red:

### El puerto es 8081, no 8080

El 8080 ya lo ocupa tu contenedor de **ThingsBoard** (`8080->9090`). Los dos
proyectos conviven sin tocarse.

### El firewall de Windows bloquea el 8081

Es el motivo número uno de que "en mi compu sí abre y en el teléfono no". La red
de casa está clasificada como **Pública** y no hay regla que permita ese puerto.

Abre PowerShell **como administrador** y córrelo una vez:

```powershell
New-NetFirewallRule -DisplayName "Baja Gas demo (8081)" -Direction Inbound -Protocol TCP -LocalPort 8081 -Action Allow -Profile Any
```

Para quitarla cuando acabe el demo:

```powershell
Remove-NetFirewallRule -DisplayName "Baja Gas demo (8081)"
```

### El extensor de casa aísla clientes

Aunque el firewall esté abierto, el teléfono no alcanza la PC porque el router
no deja que se vean. Es el mismo problema que ya te pasó con el ESP32. Con el
túnel esto deja de importar: ya no dependes de la red.

---

## Cómo está armado

```
docker-compose.yml        las dos piezas y sus puertos
backend/
  Dockerfile              python:3.12-slim + uvicorn
  entrypoint.sh           copia la base al volumen en el primer arranque
  .dockerignore           las .db NO entran a la imagen
frontend/
  Dockerfile              node compila con Vite -> nginx sirve el resultado
  nginx.conf              sirve la pantalla y hace de proxy a /api
  .dockerignore
```

### Por qué la API va detrás de nginx y no expuesta aparte

`frontend/src/core/api.js` pide `/api/...` en **relativo**, y `main.py` solo
permite CORS desde `localhost:5173`. Si el teléfono llamara directo a
`http://<ip>:8000`, el navegador bloquearía cada petición por CORS.

Pasando todo por el mismo origen (`:8081`), para el navegador no hay petición
cruzada: la pantalla y la API son el mismo servidor. **No hubo que tocar el
código de la aplicación.** El `:8000` queda publicado aparte solo por comodidad,
para abrir `/docs` y probar endpoints a mano.

### La zona horaria del contenedor no es un detalle

El `Dockerfile` instala `tzdata` y fija `TZ=America/Tijuana`. Importa por dos
razones:

- `core/tiempo.py` hace `ZoneInfo("America/Tijuana")` dentro de un `try/except`
  que, si falla, **se cae en silencio a UTC**. La imagen `slim` no trae la base
  de zonas horarias, así que sin `tzdata` el día operativo saldría corrido siete
  u ocho horas y nadie se enteraría.
- Hay siete archivos que usan `date.today()`, que devuelve la fecha **local del
  proceso**. En UTC, después de las 16:00 de Tijuana ya sería "mañana".

### La base de datos

Vive en el volumen `bajagas_db`, no dentro de la imagen: reconstruir no borra lo
que capturaste en el demo.

En el primer arranque `entrypoint.sh` copia `backend/bajagas.db` (montada de solo
lectura en `/semilla`). Sin eso, el contenedor arrancaría con una base nueva: el
seed siembra roles, usuarios y el plano, pero **no las 383 unidades reales** —
esas las trajo `importador.py` desde los Excel y el arranque no lo ejecuta.

Para empezar de cero:

```bash
docker compose down -v      # el -v borra el volumen
docker compose up -d
```

### Antes de sacar esto de la red local

`SECRET_KEY` tiene un valor por omisión público en el código: cualquiera que lea
el repositorio puede firmarse un token válido. Pásale uno propio:

```bash
SECRET_KEY="algo-largo-y-aleatorio" docker compose up -d
```

---

## Si algo falla

**Docker Desktop no arranca** y dice `remove ...\dockerInference: The file cannot
be accessed by the system`. Son sockets Unix rancios que Windows no deja borrar.
Cierra Docker Desktop y renombra las carpetas — se recrean solas:

```powershell
Move-Item "$env:LOCALAPPDATA\Docker\run" "$env:LOCALAPPDATA\Docker\run.viejo"
Move-Item "$env:LOCALAPPDATA\docker-secrets-engine" "$env:LOCALAPPDATA\docker-secrets-engine.viejo"
```

Las carpetas `.viejo` / `.atascado.*` no se pueden borrar hasta reiniciar
Windows. Después del reinicio se van con un `Remove-Item` normal.

**El teléfono no abre la página.** En orden: ¿firewall abierto (paso 2)?, ¿los
dos en la misma red?, ¿es el extensor que aísla clientes (paso 3)?, ¿`docker
compose ps` muestra los dos contenedores `Up`?
