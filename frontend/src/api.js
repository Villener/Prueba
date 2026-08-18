const TOKEN_KEY = 'bg_token'
const USER_KEY = 'bg_user'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const getUser = () => {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') } catch { return null }
}
export const setSession = (token, usuario) => {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(usuario))
}
export const clearSession = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

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
    try {
      const j = await res.json()
      if (typeof j.detail === 'string') detail = j.detail
      else if (Array.isArray(j.detail)) detail = j.detail.map((d) => d.msg).join('; ')
    } catch { /* respuesta sin cuerpo JSON */ }
    throw new ApiError(detail, res.status)
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

/** El rol define que modulo ve el usuario. */
export const rolPrincipal = (usuario) => {
  const orden = ['gerente', 'administrador', 'supervisor', 'montacarguista', 'chofer']
  return orden.find((r) => usuario?.roles?.includes(r)) || null
}

export const fmtFecha = (v) => {
  if (!v) return '—'
  const d = new Date(v)
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: '2-digit' })
}
export const fmtFechaHora = (v) => {
  if (!v) return '—'
  const d = new Date(v)
  return d.toLocaleString('es-MX', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}
export const fmtMoneda = (v) =>
  new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v || 0)
