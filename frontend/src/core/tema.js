/* Tema claro / oscuro.
 *
 * Arranca SIEMPRE en claro. A proposito NO consulta `prefers-color-scheme`:
 * el fondo blanco es el predeterminado del sistema y el oscuro es una opcion
 * que el usuario enciende. Su eleccion se recuerda en el mismo navegador.
 */
const CLAVE = 'bajagas-tema'

function leer() {
  try {
    return localStorage.getItem(CLAVE)
  } catch {
    return null // modo privado o almacenamiento bloqueado
  }
}

export function temaActual() {
  return leer() === 'dark' ? 'dark' : 'light'
}

export function aplicarTema(tema) {
  document.documentElement.setAttribute('data-theme', tema)
  try {
    localStorage.setItem(CLAVE, tema)
  } catch {
    /* sin persistencia: el tema vale para esta sesion */
  }
  return tema
}

/** Se llama una vez al arrancar, antes de pintar. */
export function iniciarTema() {
  return aplicarTema(temaActual())
}

export function alternarTema() {
  const actual = document.documentElement.getAttribute('data-theme')
  return aplicarTema(actual === 'dark' ? 'light' : 'dark')
}
