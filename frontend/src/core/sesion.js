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

/** Llama a `fn` cuando OTRA ventana de este navegador cambia de cuenta o sale.
 *
 * La sesion vive en localStorage, que es UNO para todas las ventanas del mismo
 * navegador. Si en otra se entraba con otra cuenta, esta seguia pintando la
 * pantalla de la anterior pero sus peticiones ya salian con el token nuevo: lo
 * que se capturara aqui quedaba a nombre de quien no fue, y en la bitacora de
 * la NOM-030 eso es una firma ajena. El evento `storage` solo llega a las OTRAS
 * ventanas. Se escucha bg_user y no el token porque setSession lo escribe al
 * final, cuando los dos ya estan puestos. Devuelve la funcion para dejar de
 * escuchar. */
export const alCambiarSesionEnOtraVentana = (fn) => {
  const oir = (e) => {
    // key null = alguien hizo localStorage.clear()
    if (e.key === USER_KEY || e.key === null) fn(getUser())
  }
  window.addEventListener('storage', oir)
  return () => window.removeEventListener('storage', oir)
}

/** La misma persona, aunque traiga otro token (volvio a entrar en otra ventana). */
export const mismaPersona = (a, b) => (a?.id ?? a?.email ?? null) === (b?.id ?? b?.email ?? null)

/** Mensaje que sobrevive a una recarga de ESTA ventana (sessionStorage es por ventana). */
const AVISO_KEY = 'bg_aviso_sesion'
export const dejarAvisoSesion = (texto) => {
  try { sessionStorage.setItem(AVISO_KEY, texto) } catch { /* sin almacenamiento: se recarga sin aviso */ }
}
export const leerAvisoSesion = () => {
  try { return sessionStorage.getItem(AVISO_KEY) } catch { return null }
}
export const borrarAvisoSesion = () => {
  try { sessionStorage.removeItem(AVISO_KEY) } catch { /* nada que borrar */ }
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
                 'chofer_grua', 'perito', 'mecanico',
                 'datos_logistica', 'datos_almacen', 'datos_compras', 'datos_taller',
                 'chofer']
  return orden.find((r) => usuario?.roles?.includes(r)) || null
}
