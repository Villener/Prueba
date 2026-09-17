/** RF-GEN-15 — comprimir la evidencia EN EL TELÉFONO, antes de subirla.
 *
 * No es una optimización: es el requisito. El cliente lo pidió con estas
 * palabras — «en un formato que sea ligero de almacenar».
 *
 * LA CUENTA QUE LO JUSTIFICA. Un celular moderno saca fotos de 3 a 5 MB. Con
 * 5 a 7 preventivos al día (RN-12) y varias fotos cada uno, son del orden de
 * medio giga al mes solo en evidencia — sobre un servidor de 25 GB que ya está
 * pagado y que también guarda la base. A 200 KB por foto, lo mismo cabe en
 * veinte megas.
 *
 * Y para lo que la foto tiene que probar —que el filtro se cambió, que la
 * salpicadera quedó así— 1600 px de lado largo alcanzan de sobra. Guardar 4000
 * px no prueba nada más; solo llena el disco.
 *
 * SE CONSERVA EL ORIGINAL SI SALE PEOR. Una foto ya pequeña recomprimida puede
 * crecer, y en ese caso se sube tal cual: el objetivo es que ocupe menos, no
 * pasarla por el molino a como dé lugar.
 */

const LADO_MAX = 1600
const OBJETIVO_BYTES = 220 * 1024
const CALIDADES = [0.82, 0.7, 0.58, 0.45]

/** ¿El navegador sabe escribir WebP? Safari viejo no. */
function soportaWebp() {
  try {
    const c = document.createElement('canvas')
    c.width = c.height = 1
    return c.toDataURL('image/webp').startsWith('data:image/webp')
  } catch {
    return false
  }
}

function cargar(archivo) {
  return new Promise((res, rej) => {
    const url = URL.createObjectURL(archivo)
    const img = new Image()
    img.onload = () => { URL.revokeObjectURL(url); res(img) }
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('No se pudo leer la imagen')) }
    img.src = url
  })
}

function aBlob(canvas, tipo, calidad) {
  return new Promise((res) => canvas.toBlob(res, tipo, calidad))
}

/**
 * Devuelve un File listo para subir, o el original si comprimirlo no ayuda.
 * Nunca lanza por culpa de la compresión: si algo falla, sube el original —
 * perder la evidencia por un error de canvas sería mucho peor que subirla pesada.
 */
export async function comprimir(archivo, { ladoMax = LADO_MAX, objetivo = OBJETIVO_BYTES } = {}) {
  if (!archivo || !archivo.type || !archivo.type.startsWith('image/')) return archivo

  try {
    const img = await cargar(archivo)
    // Nunca se agranda: una foto de 800 px se queda en 800.
    const escala = Math.min(1, ladoMax / Math.max(img.width, img.height))
    const w = Math.round(img.width * escala)
    const h = Math.round(img.height * escala)

    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    ctx.imageSmoothingQuality = 'high'
    ctx.drawImage(img, 0, 0, w, h)

    const tipo = soportaWebp() ? 'image/webp' : 'image/jpeg'
    const ext = tipo === 'image/webp' ? 'webp' : 'jpg'

    // Se baja la calidad por pasos hasta alcanzar el objetivo. Se para en el
    // primero que cabe: seguir bajando solo empeora la foto sin ganar nada.
    let mejor = null
    for (const q of CALIDADES) {
      const blob = await aBlob(canvas, tipo, q)
      if (!blob) continue
      mejor = blob
      if (blob.size <= objetivo) break
    }
    if (!mejor || mejor.size >= archivo.size) return archivo

    const base = (archivo.name || 'evidencia').replace(/\.[^.]+$/, '')
    return new File([mejor], `${base}.${ext}`, { type: tipo, lastModified: Date.now() })
  } catch {
    return archivo
  }
}

/** Para poder decirle al usuario cuánto se ahorró. */
export function kb(bytes) {
  if (bytes == null) return '—'
  return bytes >= 1024 * 1024
    ? (bytes / (1024 * 1024)).toFixed(1) + ' MB'
    : Math.round(bytes / 1024) + ' KB'
}
