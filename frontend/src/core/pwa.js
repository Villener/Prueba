/** La app instalada en el celular: service worker, avisos y versiones.
 *
 * Es la misma aplicacion web; no hay tienda de por medio. Se instala desde el
 * navegador ("Instalar app" en Android, "Agregar a inicio" en iPhone) y se
 * actualiza sola: cada vez que se sube una version con subir_version.ps1, el
 * telefono la toma al abrir la app o al volver a ella.
 */
import { api } from './api.js'

// La fija vite.config.js en cada compilacion; /version.json trae la del servidor.
const VERSION = typeof __VERSION_APP__ === 'string' ? __VERSION_APP__ : 'dev'

export const swSoportado = () => typeof navigator !== 'undefined' && 'serviceWorker' in navigator

export function registrarServiceWorker() {
  if (!swSoportado()) return
  // updateViaCache 'none': el navegador pregunta por sw.js nuevo sin mirar su cache.
  navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })
    .catch((e) => console.warn('service worker:', e))
}

/** Lo que manda el service worker a la pagina abierta. */
export function escucharServiceWorker(fn) {
  if (!swSoportado()) return () => {}
  const oir = (e) => fn(e.data || {})
  navigator.serviceWorker.addEventListener('message', oir)
  return () => navigator.serviceWorker.removeEventListener('message', oir)
}

// --------------------------------------------------------------------------
// Instalacion
// --------------------------------------------------------------------------
export const esIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent)
  // iPadOS se presenta como Mac; se le reconoce por la pantalla tactil.
  || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

export const instalada = () => window.matchMedia?.('(display-mode: standalone)').matches
  || window.navigator.standalone === true

// Chrome y Edge avisan UNA vez que la app se puede instalar; se guarda ese
// aviso para ofrecer el boton cuando la persona quiera, no cuando el navegador.
let avisoInstalar = null
const interesados = new Set()
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    avisoInstalar = e
    interesados.forEach((fn) => fn(true))
  })
  window.addEventListener('appinstalled', () => {
    avisoInstalar = null
    interesados.forEach((fn) => fn(false))
  })
}
export const sePuedeInstalar = () => Boolean(avisoInstalar)
export function alCambiarInstalable(fn) {
  interesados.add(fn)
  return () => interesados.delete(fn)
}
export async function instalar() {
  if (!avisoInstalar) return false
  avisoInstalar.prompt()
  const { outcome } = await avisoInstalar.userChoice
  avisoInstalar = null
  interesados.forEach((f) => f(false))
  return outcome === 'accepted'
}

// --------------------------------------------------------------------------
// Avisos al celular
// --------------------------------------------------------------------------
const pushSoportado = () => swSoportado() && 'PushManager' in window && 'Notification' in window

const b64aBytes = (b64) => {
  const s = atob((b64 + '='.repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(s, (c) => c.charCodeAt(0))
}
const mismosBytes = (a, b) => a && b && a.byteLength === b.byteLength
  && new Uint8Array(a).every((x, i) => x === b[i])

/** El service worker listo. Con limite: si no se pudo registrar, `ready` no
 *  contesta nunca y el boton se quedaria pensando para siempre. */
async function listo() {
  const reg = await Promise.race([
    navigator.serviceWorker.ready,
    new Promise((r) => setTimeout(() => r(null), 10000)),
  ])
  if (!reg) throw new Error('La app no terminó de prepararse para avisos. Recarga la página e intenta otra vez.')
  return reg
}

async function suscripcionActual() {
  const reg = await listo()
  return reg.pushManager.getSubscription()
}

/** "Dejar de recibir aqui" se recuerda en ESTE navegador. Quitar la suscripcion
 *  no quita el permiso, y sin esta marca la app la volvia a crear sola la
 *  siguiente vez que se abria. */
const APAGADOS_KEY = 'bg_avisos_off'
export const avisosApagadosAqui = () => {
  try { return localStorage.getItem(APAGADOS_KEY) === '1' } catch { return false }
}
const marcarApagados = (si) => {
  try {
    if (si) localStorage.setItem(APAGADOS_KEY, '1')
    else localStorage.removeItem(APAGADOS_KEY)
  } catch { /* sin almacenamiento */ }
}

/** En que punto esta ESTE navegador:
 *  'no-soportado' | 'ios-instalar' | 'bloqueado' | 'activo' | 'inactivo'.
 *  Con `confirmar`, 'activo' ademas exige que el servidor tenga este celular a
 *  nombre de quien esta adentro: si el registro fallo, no recibe nada. */
export async function estadoAvisos({ confirmar = false } = {}) {
  // En iPhone solo hay avisos con la app agregada a la pantalla de inicio.
  if (esIOS() && !instalada()) return 'ios-instalar'
  if (!pushSoportado()) return 'no-soportado'
  if (Notification.permission === 'denied') return 'bloqueado'
  if (Notification.permission !== 'granted') return 'inactivo'
  let sub
  try {
    sub = await suscripcionActual()
  } catch {
    return 'inactivo'
  }
  if (!sub) return 'inactivo'
  if (!confirmar) return 'activo'
  try {
    const { registrada } = await api.post('/push/revisar', { endpoint: sub.endpoint })
    return registrada ? 'activo' : 'inactivo'
  } catch {
    return 'activo'  // sin red no se puede confirmar; el navegador si esta suscrito
  }
}

/** Una operacion de avisos a la vez. La sincronizacion al abrir y el boton
 *  "Activar" corrian juntas: las dos suscribian el mismo celular y, si una
 *  fallaba, deshacia la suscripcion que la otra acababa de registrar. */
let cola = Promise.resolve()
const enOrden = (fn) => {
  const turno = cola.then(fn, fn)
  cola = turno.catch(() => {})
  return turno
}

async function registrarEnServidor(sub) {
  const j = sub.toJSON()
  await api.post('/push/suscripcion', { endpoint: j.endpoint, keys: j.keys })
}

/** Suscribe y registra. Si el servidor no la recibe, se deshace: un celular
 *  suscrito que el servidor no conoce diria "activo" sin recibir nada. */
async function suscribir(reg, clave) {
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: clave })
  try {
    await registrarEnServidor(sub)
  } catch (e) {
    await sub.unsubscribe().catch(() => {})
    throw e
  }
  return sub
}

/** Pide el permiso y suscribe este celular. El permiso se pide AL MOMENTO del
 *  toque, fuera de la fila: el iPhone ignora la peticion si no sale directo
 *  de un toque, y en la fila podria esperar segundos a otra operacion. */
export async function activarAvisos() {
  if (!pushSoportado()) throw new Error('Este navegador no puede recibir avisos.')
  const permiso = await Notification.requestPermission()
  if (permiso !== 'granted') {
    throw new Error(permiso === 'denied'
      ? 'Los avisos quedaron bloqueados. Actívalos en los permisos del navegador para este sitio.'
      : 'No se activaron los avisos.')
  }
  return enOrden(suscribirEste)
}
async function suscribirEste() {
  const reg = await listo()
  const { clave } = await api.get('/push/clave')
  const llave = b64aBytes(clave)
  const vieja = await reg.pushManager.getSubscription()
  if (vieja && !mismosBytes(vieja.options?.applicationServerKey, llave)) await vieja.unsubscribe()
  else if (vieja) {
    await registrarEnServidor(vieja)
    marcarApagados(false)
    return
  }
  await suscribir(reg, llave)
  marcarApagados(false)
}

/** Este celular deja de recibir avisos (de cualquier cuenta). */
export const desactivarAvisos = () => enOrden(desactivarAvisosYa)
async function desactivarAvisosYa() {
  marcarApagados(true)
  const sub = await suscripcionActual()
  if (!sub) return
  try { await api.del('/push/suscripcion', { endpoint: sub.endpoint }) } finally { await sub.unsubscribe() }
}

/** Al abrir la app con sesion: si este celular ya dio permiso, se asegura de
 *  que el servidor lo tenga a nombre de QUIEN esta adentro (pudo entrar otra
 *  persona en el mismo telefono, o el servidor cambiar de claves). Sin
 *  preguntar nada: el permiso ya estaba dado. */
export const sincronizarAvisos = () => enOrden(sincronizarAvisosYa)
async function sincronizarAvisosYa() {
  try {
    if (!pushSoportado() || Notification.permission !== 'granted') return
    const reg = await listo()
    const { clave } = await api.get('/push/clave')
    const llave = b64aBytes(clave)
    let sub = await reg.pushManager.getSubscription()
    if (sub && !mismosBytes(sub.options?.applicationServerKey, llave)) {
      await sub.unsubscribe()
      sub = null
    }
    if (!sub) {
      // Quien dijo "Dejar de recibir aqui" no se vuelve a suscribir solo.
      if (!avisosApagadosAqui()) await suscribir(reg, llave)
      return
    }
    await registrarEnServidor(sub)
  } catch (e) {
    console.warn('avisos:', e)
  }
}

/** Al salir: los avisos de esta cuenta dejan de llegar a este celular. La
 *  suscripcion del navegador se queda, para que quien entre despues la use. */
export async function soltarAvisosDeEstaCuenta() {
  try {
    if (!pushSoportado()) return
    const reg = await navigator.serviceWorker.getRegistration()
    const sub = reg && await reg.pushManager.getSubscription()
    if (!sub) return
    // Sin red no se espera: salir no puede quedarse colgado.
    await Promise.race([
      api.del('/push/suscripcion', { endpoint: sub.endpoint }),
      new Promise((r) => setTimeout(r, 2000)),
    ])
  } catch { /* se intento; al entrar otra persona la suscripcion cambia de dueno */ }
}

export const probarAvisos = () => api.post('/push/prueba')

// --------------------------------------------------------------------------
// Version nueva
// --------------------------------------------------------------------------
/** Llama a `fn` cuando en el servidor ya hay otra version. Revisa al volver a
 *  la app (en el celular casi nunca se recarga: se sale y se entra) y cada
 *  30 minutos si se queda abierta, como la pantalla del taller. */
export function vigilarVersion(fn) {
  if (VERSION === 'dev') return () => {}
  let avisado = false
  const revisar = async () => {
    if (avisado || document.visibilityState !== 'visible') return
    try {
      const r = await fetch('/version.json', { cache: 'no-store' })
      if (!r.ok) return
      const { version } = await r.json()
      if (version && version !== VERSION) {
        avisado = true
        fn(version)
      }
    } catch { /* sin red: se revisa la proxima vez */ }
  }
  document.addEventListener('visibilitychange', revisar)
  const t = setInterval(revisar, 30 * 60 * 1000)
  revisar()
  return () => {
    document.removeEventListener('visibilitychange', revisar)
    clearInterval(t)
  }
}
