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
  // ESTA LISTA ES LA QUE DECIDE SI ALGUIEN PUEDE ENTRAR. Un rol que no esté
  // aquí devuelve null y App manda al login otra vez — aunque el rol exista en
  // el servidor y tenga su módulo escrito. Le pasó a `perito`: Edgar se
  // autenticaba bien y rebotaba al login sin un solo mensaje de error.
  // Al agregar un módulo hay que tocar TRES lugares: ROLES_DEL_SISTEMA en el
  // backend, MODULOS en App.jsx y esta línea.
  const orden = ['gerente', 'administrador', 'capturista', 'supervisor',
                 'chofer_grua', 'perito', 'mecanico', 'chofer']
  return orden.find((r) => usuario?.roles?.includes(r)) || null
}
