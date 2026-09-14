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

  if (res.status === 401) {
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
  descargar,
  subir,
}

export const login = async (email, password) => {
  const data = await request('/auth/login', { method: 'POST', body: { email, password } })
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
export const fmtMoneda = (v) =>
  new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v || 0)

/** Fecha de hoy en la zona de operacion, como YYYY-MM-DD para <input type="date">.
 *  No usar toISOString(): eso da la fecha en UTC y despues de las 17:00 de
 *  Tijuana ya adelanto un dia, lo que dejaria elegir "ayer" como valido. */
export const hoyTijuana = () => {
  const p = new Intl.DateTimeFormat('en-CA', {
    timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date())
  return p // en-CA ya entrega YYYY-MM-DD
}
