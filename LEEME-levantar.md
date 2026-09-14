# Cómo levantar Baja Gas — nativo y Docker

## Lo primero: dónde vive el código

Esta es la causa de casi todos los errores raros. Hay **dos carpetas** y no son
la misma:

| Carpeta | Qué hay | Se usa para |
|---|---|---|
| `C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js` | solo `bajagas.cmd`, `dev.cmd` | los atajos |
| `...\PrototipoNode.js\.claude\worktrees\silly-neumann-fc6fb1` | **todo el código**, `docker-compose.yml` | los comandos de verdad |

El código está en la segunda porque es un *worktree* de git: la rama de trabajo
vive en su propia carpeta. Si corres `docker compose up` en la primera obtienes
`no configuration file provided: not found`, y si corres `npm run dev` obtienes
`ENOENT: no such file or directory, package.json`.

De aquí en adelante, **RAÍZ** significa:

```
C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js\.claude\worktrees\silly-neumann-fc6fb1
```

---

## Modo NATIVO (desarrollo)

Es el que usas para programar: guardas un archivo y la pantalla se recarga sola.
Necesita **dos ventanas abiertas al mismo tiempo**, una para cada mitad.

### Paso 0 — apagar Docker

Docker también publica el 8000. Con los dos escuchando no hay forma de saber
cuál te contesta: parece que tus cambios no se aplican cuando en realidad te
está respondiendo el contenedor.

```
cd C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js
```
```
.\bajagas.cmd abajo
```

### Paso 1 — ventana 1: la API

Abre una ventana de PowerShell:

```
cd C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js\.claude\worktrees\silly-neumann-fc6fb1\backend
```
```
python -m uvicorn app.main:app --reload --port 8000
```

Se queda ocupada imprimiendo el log. **No la cierres.** Cuando guardes un `.py`
se reinicia sola.

Comprobación: `http://localhost:8000/docs` debe abrir Swagger.

### Paso 2 — ventana 2: la pantalla

Abre **otra** ventana:

```
cd C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js\.claude\worktrees\silly-neumann-fc6fb1\frontend
```
```
npm.cmd run dev
```

`npm.cmd`, no `npm`. En este equipo la política de ejecución de PowerShell 5.1
está en `Restricted` y `npm` es un `.ps1`, así que muere antes de empezar con
*"no se puede cargar el archivo npm.ps1"*. El `.cmd` no es un script y no le
aplica la política — y no cambias ningún ajuste del sistema.

### Paso 3 — abrir

```
http://localhost:5173
```

La pantalla habla con la API sola: `vite.config.js` reenvía todo lo que empiece
con `/api` a `http://127.0.0.1:8000`. Por eso las **dos** ventanas tienen que
estar vivas; con la API caída la pantalla carga pero no muestra datos.

### Cerrar

`Ctrl+C` en cada ventana, o desde cualquier carpeta:

```
C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js\dev.cmd abajo
```

### El atajo

`dev.cmd` hace los pasos 1 y 2 de un tirón, abre las dos ventanas y comprueba
antes que el 8000 esté libre:

```
C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js\dev.cmd
```

---

## Modo DOCKER

Es el que usas para enseñárselo a alguien: la pantalla va compilada, escucha en
la IP de la red y aguanta reinicios.

### Paso 1 — pararte donde está el compose

`docker compose` **solo** funciona parado en la carpeta del `docker-compose.yml`.

```
cd C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js\.claude\worktrees\silly-neumann-fc6fb1
```

### Paso 2 — levantar

```
docker compose up -d
```

`-d` = en segundo plano, te devuelve la terminal. La primera vez tarda varios
minutos porque construye las dos imágenes; después son segundos.

### Paso 3 — comprobar y abrir

```
docker compose ps
```

Los tres deben decir `Up`, y `api` además `(healthy)`.

| Qué | Dónde |
|---|---|
| La aplicación | `http://localhost:8081` |
| La API y Swagger | `http://localhost:8000/docs` |
| Desde el teléfono, misma red | `http://<IP-de-tu-PC>:8081` |

Es el **8081** y no el 8080 porque el 8080 ya lo tiene ThingsBoard.

### Comandos del día a día

```
docker compose logs -f api
```
```
docker compose restart api
```
```
docker compose down
```

`down` apaga sin borrar: la base vive en un volumen y sobrevive.

---

## Copiar del nativo al Docker

Aquí hay **dos cosas distintas** que se copian por caminos distintos. Confundirlas
es lo que hace que "ya lo cambié y no se ve".

### A) El CÓDIGO — reconstruir la imagen

Docker **no** monta tu carpeta: el `Dockerfile` copia el código *dentro* de la
imagen (`COPY app ./app`, y el frontend además lo compila con `npm run build`).
O sea que el contenedor trae una **foto** del código de cuando se construyó. Si
editas un archivo y solo haces `restart`, el contenedor sigue con la foto vieja.

Para meter tus cambios:

```
docker compose up -d --build
```

`--build` es la palabra que importa. Sin ella, `up -d` ve los contenedores
`Running` y no hace nada.

Atajo equivalente, desde cualquier carpeta:

```
C:\Users\marti\Prueba\TallerBajaGas\PrototipoNode.js\bajagas.cmd publicar
```

Si solo tocaste Python puedes reconstruir nada más esa mitad, que es mucho más
rápido que recompilar el frontend:

```
docker compose up -d --build api
```

### B) La BASE DE DATOS — copiar el archivo

Son dos bases diferentes y no se enteran una de la otra:

| | Archivo real |
|---|---|
| Nativo | `backend\bajagas.db` (lo ves en el explorador) |
| Docker | volumen `bajagas_db`, montado como `/datos/bajagas.db` |

El `entrypoint.sh` copia la del repo al volumen **solo si el volumen está
vacío**, o sea únicamente el primer arranque. Tu volumen ya tiene datos, así que
esa copia automática ya no va a ocurrir nunca más.

**Nativo → Docker** (empujar tu base al contenedor). Se para la API primero para
no copiar un SQLite a media escritura:

```
docker compose stop api
```
```
docker compose cp ./backend/bajagas.db api:/datos/bajagas.db
```
```
docker compose start api
```

**Docker → nativo** (traerte lo que se capturó en el demo). Haz respaldo antes,
porque sobrescribe:

```
copy backend\bajagas.db backend\bajagas.db.respaldo
```
```
docker compose cp api:/datos/bajagas.db ./backend/bajagas.db
```

**Empezar el Docker de cero** desde la base del repo. `-v` **borra el volumen**:
todo lo que se haya capturado en Docker y no esté en `backend\bajagas.db` se
pierde. Al volver a subir, el entrypoint ve el volumen vacío y copia de nuevo
desde `/semilla`:

```
docker compose down -v
```
```
docker compose up -d
```

---

## Cuál usar

| Quieres | Usa |
|---|---|
| Programar, ver el cambio al guardar | nativo (`dev.cmd`) |
| Enseñárselo a alguien, teléfono, túnel | Docker (`bajagas.cmd arriba`) |

**Nunca los dos a la vez**: se pelean por el 8000. Al cambiar de modo, apaga el
otro primero.

## Flujo completo típico

1. `bajagas.cmd abajo` — libera los puertos
2. `dev.cmd` — a programar
3. Guardas archivos, pruebas en `http://localhost:5173`
4. `dev.cmd abajo` — cierras el modo desarrollo
5. `bajagas.cmd publicar` — construye y levanta Docker con tus cambios
6. `bajagas.cmd enlace` — saca la URL pública (rota contraseñas antes)

La base **no** viaja sola en el paso 5. Si lo que cambiaste fueron *datos* y no
código, hazlo a mano con el `docker compose cp` de arriba.
