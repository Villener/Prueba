/** Sesion del usuario en este navegador.
 *
 * Solo lectura y escritura de credenciales. NO habla con la API: si lo hiciera
 * habria una dependencia circular con api.js, que necesita el token para cada
 * peticion.
 */
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

/** El rol define que modulo ve el usuario. El servidor lo revalida (RNF-04). */
export const rolPrincipal = (usuario) => {
  const orden = ['gerente', 'administrador', 'capturista', 'supervisor',
                 'montacarguista', 'chofer']
  return orden.find((r) => usuario?.roles?.includes(r)) || null
}
