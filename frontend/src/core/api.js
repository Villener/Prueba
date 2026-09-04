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

export const api = {
  get: (p, params) => request(p, { params }),
  post: (p, body, params) => request(p, { method: 'POST', body, params }),
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
