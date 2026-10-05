/* Service worker de Baja Gas: lo que hace que la app se instale y reciba avisos.
 *
 * Vive en public/ (y no en src/) porque tiene que servirse en /sw.js con ese
 * nombre fijo: si cambiara de nombre en cada version, el navegador lo tomaria
 * por OTRO service worker y las suscripciones a los avisos se perderian.
 *
 * Tres trabajos:
 *  1. Avisos: pintar en el telefono lo que manda el servidor
 *     (backend/app/modules/sistema/push_service.py), aunque la app este cerrada.
 *  2. Abrir rapido y sin senal: guarda la ultima pantalla y sus archivos.
 *  3. NO quedarse con versiones viejas: la pagina se pide primero a la red.
 *     Los archivos de /assets/ traen hash en el nombre, asi que una version
 *     nueva son archivos nuevos y nunca se confunden con los guardados.
 *
 * La API (/api/) no pasa por aqui: un dato viejo de la API es peor que ninguno.
 */
const PAGINA = 'bg-pagina-v1'
const ARCHIVOS = 'bg-archivos-v1'
const TOPE_ARCHIVOS = 60
const ESPERA_RED_MS = 4000

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) {
      if (k !== PAGINA && k !== ARCHIVOS) await caches.delete(k)
    }
    await self.clients.claim()
  })())
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return
  // Solo la pagina de la app. Abrir a mano /version.json o un icono tambien es
  // una navegacion, y guardarla como '/' haria abrir la app con ese archivo.
  if (req.mode === 'navigate' && (url.pathname === '/' || url.pathname === '/index.html')) {
    e.respondWith(paginaPrimeroRed(req))
  } else if (url.pathname.startsWith('/assets/')) {
    e.respondWith(archivoGuardado(e, req))
  }
})

const esHtml = (res) => res.ok && res.type === 'basic'
  && (res.headers.get('content-type') || '').includes('text/html')

/** La pagina: de la red; la guardada solo si no hay red o tarda demasiado.
 *
 *  La copia guardada se cambia UNICAMENTE cuando la de la red fue la que se
 *  uso: entonces sus /assets/ los pide la propia pantalla y quedan guardados
 *  junto con ella. Si ganaba la guardada y aun asi se guardaba la nueva, la
 *  proxima vez sin senal abriria una pagina cuyos archivos nunca se bajaron. */
async function paginaPrimeroRed(req) {
  let cache = null
  try { cache = await caches.open(PAGINA) } catch { /* sin almacenamiento: solo red */ }
  const guardar = (res) => {
    if (cache && esHtml(res)) cache.put('/', res.clone()).catch(() => {})
    return res
  }
  const guardada = cache ? await cache.match('/').catch(() => null) : null
  const red = fetch(req)
  if (!guardada) return guardar(await red)
  red.catch(() => { /* sin red: se contesta con la guardada */ })
  const tarde = new Promise((r) => setTimeout(() => r(null), ESPERA_RED_MS))
  try {
    const res = await Promise.race([red, tarde])
    return res && res.ok ? guardar(res) : guardada
  } catch {
    return guardada
  }
}

/** /assets/<nombre-con-hash>: si ya esta guardado no cambia nunca.
 *  Guardar es un extra: si falla (celular sin espacio), el archivo igual se
 *  entrega. Si no, la app quedaria en blanco teniendo red. */
async function archivoGuardado(e, req) {
  let cache = null
  try {
    cache = await caches.open(ARCHIVOS)
    const hay = await cache.match(req)
    if (hay) return hay
  } catch { /* se pide a la red */ }
  const res = await fetch(req)
  if (cache && res.ok && res.type === 'basic') {
    e.waitUntil((async () => {
      await cache.put(req, res.clone())
      const llaves = await cache.keys()
      // Las de versiones viejas se van solas: se borran las mas antiguas.
      for (const k of llaves.slice(0, Math.max(0, llaves.length - TOPE_ARCHIVOS))) await cache.delete(k)
    })().catch(() => {}))
  }
  return res
}

// --------------------------------------------------------------------------
// Avisos
// --------------------------------------------------------------------------
self.addEventListener('push', (e) => {
  let d = {}
  try {
    d = e.data ? e.data.json() : {}
  } catch {
    d = { mensaje: e.data ? e.data.text() : '' }
  }
  e.waitUntil((async () => {
    await self.registration.showNotification(d.titulo || 'Baja Gas · Taller', {
      body: d.mensaje || '',
      icon: '/icono-192.png',
      badge: '/badge-96.png',
      lang: 'es-MX',
      tag: d.tag,
      renotify: Boolean(d.tag),
      data: { url: d.url || '/#/notificaciones' },
    })
    // Si la app esta abierta, que la campana se ponga al dia sola.
    const abiertas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    for (const c of abiertas) c.postMessage({ tipo: 'aviso', datos: d })
  })())
})

self.addEventListener('notificationclick', (e) => {
  e.notification.close()
  const destino = new URL(e.notification.data?.url || '/#/notificaciones', self.location.origin).href
  e.waitUntil((async () => {
    const abiertas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const app = abiertas.find((c) => new URL(c.url).origin === self.location.origin)
    if (app) {
      await app.focus()
      app.postMessage({ tipo: 'abrir', url: destino })
      return
    }
    await self.clients.openWindow(destino)
  })())
})
