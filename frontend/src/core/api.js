/** Cliente HTTP de la API.
 *
 * Un solo lugar sabe armar la peticion, poner el token y traducir los errores
 * del servidor a un mensaje que la pantalla pueda mostrar.
 */
import { clearSession, getToken, setSession } from './sesion.js'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

/** La ruta de entrar, que es la unica que puede dar 401 SIN haber tenido
 *  sesion. Va como constante y no escrita a mano en los dos sitios donde se
 *  compara: si alguien renombra el endpoint y solo cambia una, el login vuelve
 *  a decir que la sesion expiro y el defecto tarda otra tarde en encontrarse. */
const RUTA_LOGIN = '/auth/login'

async function request(path, { method = 'GET', body, params } = {}) {
  let url = `/api${path}`
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    ).toString()
    if (qs) url += `?${qs}`
  }
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  // El 401 de ENTRAR no es el 401 de una sesion caida, y tratarlos igual
  // confunde justo a quien menos puede permitirselo.
  //
  // Un 401 normal significa "tenias sesion y ya no vale": se limpia y se manda
  // al login. Pero /auth/login contesta 401 cuando la contrasena esta mal, y
  // ahi este camino hacia tres cosas absurdas: borraba una sesion que no
  // existia, redirigia al login a quien YA estaba en el login, y sobre todo
  // tiraba el mensaje del servidor --"Correo o contrasena incorrectos"-- para
  // poner "Tu sesion expiro. Vuelve a entrar."
  //
  // Eso mando a alguien a revisar un despliegue recien hecho buscando por que
  // se le caia la sesion, cuando lo unico que pasaba era que la contrasena
  // habia cambiado. El mensaje describia un sintoma que no estaba ocurriendo.
  if (res.status === 401 && path !== RUTA_LOGIN) {
    clearSession()
    window.location.hash = '#/login'
    throw new ApiError('Tu sesion expiro. Vuelve a entrar.', 401)
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`
    let datos = null
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') detail = j.detail
      else if (Array.isArray(j.detail)) detail = j.detail.map((d) => d.msg).join('; ')
      else if (j.detail && typeof j.detail === 'object') {
        // Detalle estructurado: el servidor no solo dice que no, dice por que y
        // que se puede hacer. Sin esto la pantalla mostraba "Error 409" y el
        // usuario se quedaba sin saber que hacer.
        datos = j.detail
        detail = j.detail.mensaje || detail
      }
    } catch { /* respuesta sin cuerpo JSON */ }
    const err = new ApiError(detail, res.status)
    err.datos = datos
    throw err
  }
  if (res.status === 204) return null
  return res.json()
}

/** Baja un archivo que la API devuelve como binario.
 *
 *  No se puede usar `request()`: esa da por hecho que la respuesta es JSON.
 *  Y tampoco sirve un enlace normal, que seria lo simple: el token vive en
 *  localStorage y no en una cookie, asi que el navegador no lo manda solo. Hay
 *  que pedirlo con fetch, ponerle el encabezado a mano y armar la descarga.
 */
async function descargar(ruta, { params } = {}) {
  let url = `/api${ruta}`
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    ).toString()
    if (qs) url += `?${qs}`
  }
  const token = getToken()
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    throw new ApiError(
      res.status === 401 ? 'Tu sesion expiro. Vuelve a entrar.'
                         : `No se pudo generar el archivo (error ${res.status})`,
      res.status)
  }

  // El nombre lo manda el servidor en Content-Disposition; si no llega, se usa
  // uno con la fecha para que dos descargas no se pisen en la carpeta.
  const disp = res.headers.get('Content-Disposition') || ''
  const encontrado = /filename="?([^"]+)"?/.exec(disp)
  const nombre = encontrado ? encontrado[1]
                            : `descarga-${new Date().toISOString().slice(0, 10)}.xlsx`

  const blob = await res.blob()
  const enlace = document.createElement('a')
  enlace.href = URL.createObjectURL(blob)
  enlace.download = nombre
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  // Sin esto el blob se queda en memoria hasta que se recargue la pagina.
  setTimeout(() => URL.revokeObjectURL(enlace.href), 1000)
  return nombre
}

/** Sube un archivo por multipart.
 *
 *  No se puede usar `request()`: esa pone Content-Type: application/json, y en
 *  multipart el navegador tiene que poner el suyo CON el boundary que el mismo
 *  genera. Si se lo fijamos a mano, el servidor no puede separar las partes y
 *  responde 422 sin decir por que.
 */
async function subir(ruta, archivo, campo = 'archivo') {
  const fd = new FormData()
  fd.append(campo, archivo)
  const token = getToken()
  const res = await fetch(`/api${ruta}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  })
  if (res.status === 401) {
    clearSession()
    window.location.hash = '#/login'
    throw new ApiError('Tu sesion expiro. Vuelve a entrar.', 401)
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') detail = j.detail
      else if (Array.isArray(j.detail)) detail = j.detail.map((d) => d.msg).join('; ')
    } catch { /* sin cuerpo JSON */ }
    throw new ApiError(detail, res.status)
  }
  return res.json()
}

/** Trae una foto y devuelve una URL de blob para ponerla en un <img>.
 *
 *  Un <img src="/api/evidencias/7"> no funciona: la etiqueta no manda
 *  encabezados y el token vive en localStorage, asi que la peticion llegaria
 *  sin sesion. Y meter el token en la consulta (?token=...) tampoco: los JWT
 *  acaban escritos en el log de accesos del servidor y en el Referer de
 *  cualquier enlace de la pagina. Se baja con fetch, que si puede poner el
 *  encabezado, y se pinta desde memoria.
 *
 *  Quien la llame es responsable de soltar la URL con URL.revokeObjectURL()
 *  cuando desmonte: si no, el blob se queda en memoria hasta recargar.
 */
export async function bajarEvidencia(id) {
  const token = getToken()
  const res = await fetch(`/api/evidencias/${id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new ApiError(`No se pudo cargar la foto (${res.status})`, res.status)
  return URL.createObjectURL(await res.blob())
}

export const api = {
  get: (p, params) => request(p, { params }),
  post: (p, body, params) => request(p, { method: 'POST', body, params }),
  put: (p, body, params) => request(p, { method: 'PUT', body, params }),
  del: (p, body) => request(p, { method: 'DELETE', body }),
  descargar,
  subir,
}

/** Los dos desenlaces que el servidor distingue y la pantalla tiene que saber
 *  decir. El texto lo pone AQUI y no el backend a proposito: los 212 mensajes
 *  de HTTPException del servidor van sin acentos --es la convencion de ese
 *  lado-- y "contrasena" en la pantalla de entrada de una empresa se lee como
 *  descuido. Del servidor se respeta el codigo, que es el dato; la redaccion es
 *  de quien la muestra.
 *
 *  401 y 403 dicen cosas distintas y no se pueden juntar: con el 401 uno vuelve
 *  a teclear y entra; con el 403 puede teclear bien toda la tarde y no va a
 *  entrar nunca, porque su cuenta esta desactivada. Decirle "revisa tu
 *  contrasena" a quien tiene la cuenta apagada es mandarlo a perder el tiempo. */
const MENSAJE_ENTRADA = {
  401: 'Correo o contraseña incorrectos.',
  403: 'Tu cuenta está desactivada. Pide al administrador que la reactive.',
}

export const login = async (email, password) => {
  let data
  try {
    data = await request(RUTA_LOGIN, { method: 'POST', body: { email, password } })
  } catch (e) {
    // El 429 NO se reescribe: el servidor manda cuantos minutos hay que
    // esperar, y ese dato vale mas que cualquier redaccion que pongamos aqui.
    const propio = MENSAJE_ENTRADA[e.status]
    if (propio) throw new ApiError(propio, e.status)
    throw e
  }
  setSession(data.access_token, data.usuario)
  return data.usuario
}


// La API responde SIEMPRE en UTC con offset ("...Z" o "+00:00"). Aqui es el
// unico lugar donde se convierte a la hora de operacion. No usar offsets fijos:
// Baja California cambia de UTC-7 a UTC-8 y `timeZone` lo resuelve solo.
export const TZ = 'America/Tijuana'

/** Una fecha de CALENDARIO no tiene zona horaria, y tratarla como si la
 *  tuviera corre el dia.
 *
 *  `new Date('2026-08-24')` se interpreta como medianoche UTC; al pintarla en
 *  Tijuana (UTC-7) retrocede al 23. La cita del 24 se mostraba como 23, y lo
 *  mismo le pasaba a fecha_limite, a fecha_fin_prevista del prestamo y a la
 *  ETA de las piezas. Mostrarle al chofer un dia antes de su cita es de los
 *  errores que mas rapido acaban con la confianza en el sistema.
 *
 *  Por eso las fechas puras (YYYY-MM-DD) se formatean SIN convertir: el 24 de
 *  agosto es el 24 de agosto en cualquier zona. La conversion se queda para los
 *  instantes, que si ocurren en un momento concreto del tiempo.
 */
const SOLO_FECHA = /^\d{4}-\d{2}-\d{2}$/

export const fmtFecha = (v) => {
  if (!v) return '—'
  if (typeof v === 'string' && SOLO_FECHA.test(v)) {
    const [a, mes, dia] = v.split('-').map(Number)
    return new Date(a, mes - 1, dia).toLocaleDateString('es-MX', {
      day: '2-digit', month: 'short', year: '2-digit',
    })
  }
  const d = new Date(v)
  if (isNaN(d)) return '—'
  return d.toLocaleDateString('es-MX', {
    timeZone: TZ, day: '2-digit', month: 'short', year: '2-digit',
  })
}
export const fmtFechaHora = (v) => {
  if (!v) return '—'
  const d = new Date(v)
  if (isNaN(d)) return '—'
  return d.toLocaleString('es-MX', {
    timeZone: TZ, day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit',
  })
}
/** Fecha y hora CON AÑO, para el libro de bitácora (NOM-030 7.1.10 d) 3).
 *
 *  fmtFechaHora omite el año a propósito —en una agenda «03 feb 14:10» basta—,
 *  pero un libro que se conserva por años y que revisa un inspector no puede
 *  dejar a la imaginación de qué año es un registro. */
export const fmtFechaHoraAnio = (v) => {
  if (!v) return '—'
  const d = new Date(v)
  if (isNaN(d)) return '—'
  return d.toLocaleString('es-MX', {
    timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}
/** 6641234567 -> 664 123 4567, como la gente dicta un celular. */
export const fmtCelular = (t) => {
  const d = (t || '').replace(/\D/g, '').slice(-10)
  return d.length === 10 ? d.replace(/(\d{3})(\d{3})(\d{4})/, '$1 $2 $3') : ''
}

export const fmtMoneda = (v) =>
  new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v || 0)

/** El día (en Tijuana) de un instante, como YYYY-MM-DD. Sirve de `min` en un
 *  <input type="date">: «no antes del día en que la unidad entró al taller».
 *  Mismo cuidado que hoyTijuana: toISOString daría el día de UTC. */
export const diaTijuana = (v) => {
  if (!v) return undefined
  const d = new Date(v)
  if (isNaN(d)) return undefined
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(d)
}

/** Fecha de hoy en la zona de operacion, como YYYY-MM-DD para <input type="date">.
 *  No usar toISOString(): eso da la fecha en UTC y despues de las 17:00 de
 *  Tijuana ya adelanto un dia, lo que dejaria elegir "ayer" como valido. */
export const hoyTijuana = () => {
  const p = new Intl.DateTimeFormat('en-CA', {
    timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date())
  return p // en-CA ya entrega YYYY-MM-DD
}
