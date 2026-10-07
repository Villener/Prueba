/** La firma dibujada: el recuadro para firmar con el dedo y su dibujo ya puesto.
 *
 * El trazo viaja como un camino SVG («M x y L x y …») en un lienzo de 600×200,
 * igual que lo valida el servidor (bitacora/asientos_reporte.validar_trazo). Se
 * guarda el trazo y no una foto: pesa poco, se imprime nítido y no hay imagen
 * que alguien pueda cambiar por otra sin que la huella deje de cuadrar.
 */
import { useEffect, useRef, useState } from 'react'

const ANCHO = 600
const ALTO = 200
// Lo mismo que exige el servidor (FIRMA_MIN_PUNTOS / FIRMA_MIN_TINTA): el botón
// se apaga antes, para que nadie se entere del mínimo por un error.
const MIN_PUNTOS = 8
const MIN_TINTA = 150

const r1 = (v) => Math.round(v * 10) / 10

export function trazoDe(lineas) {
  return lineas.filter((l) => l.length)
    // Un toque sin arrastre (el punto de una i) se guarda como una rayita de
    // 0.1: en SVG un «M» solo no se pinta, y la firma impresa saldria sin el.
    .map((l) => (l.length === 1 ? [...l, [l[0][0] + 0.1, l[0][1]]] : l))
    .map((l) => l.map(([x, y], i) => `${i ? 'L' : 'M'} ${r1(x)} ${r1(y)}`).join(' '))
    .join(' ')
}

function medir(lineas) {
  let puntos = 0
  let tinta = 0
  for (const l of lineas) {
    puntos += l.length
    for (let i = 1; i < l.length; i++) tinta += Math.hypot(l[i][0] - l[i - 1][0], l[i][1] - l[i - 1][1])
  }
  return { puntos, tinta }
}

/** El recuadro. Llama `onCambio(trazo)` con el camino, o con null mientras la
 *  firma no alcance el mínimo. */
export function LienzoFirma({ onCambio }) {
  const lienzo = useRef(null)
  const lineas = useRef([])
  const dibujando = useRef(false)
  // El dedo que esta firmando. La palma o un segundo dedo en la tableta llegan
  // como OTRO puntero y se ignoran: si no, su trazo se mezclaba con la firma.
  const dedo = useRef(null)
  const [hayAlgo, setHayAlgo] = useState(false)

  const pintar = () => {
    const c = lienzo.current
    if (!c) return
    const ctx = c.getContext('2d')
    ctx.clearRect(0, 0, ANCHO, ALTO)
    ctx.lineWidth = 2.6
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeStyle = '#13233D'
    for (const l of lineas.current) {
      ctx.beginPath()
      l.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)))
      if (l.length === 1) ctx.lineTo(l[0][0] + 0.1, l[0][1])
      ctx.stroke()
    }
  }

  const avisar = () => {
    const { puntos, tinta } = medir(lineas.current)
    setHayAlgo(puntos > 0)
    onCambio(puntos >= MIN_PUNTOS && tinta >= MIN_TINTA ? trazoDe(lineas.current) : null)
  }

  // Del punto en la pantalla al punto en el lienzo de 600×200, sea cual sea el
  // tamaño con el que se ve (el teléfono lo encoge, la computadora no).
  const punto = (e) => {
    const r = lienzo.current.getBoundingClientRect()
    const x = Math.min(ANCHO, Math.max(0, ((e.clientX - r.left) / r.width) * ANCHO))
    const y = Math.min(ALTO, Math.max(0, ((e.clientY - r.top) / r.height) * ALTO))
    return [x, y]
  }

  const empezar = (e) => {
    e.preventDefault()
    if (dibujando.current) return
    dedo.current = e.pointerId
    lienzo.current.setPointerCapture?.(e.pointerId)
    dibujando.current = true
    lineas.current.push([punto(e)])
    pintar()
  }
  const seguir = (e) => {
    if (!dibujando.current || e.pointerId !== dedo.current) return
    e.preventDefault()
    const l = lineas.current[lineas.current.length - 1]
    const p = punto(e)
    const u = l[l.length - 1]
    // Los puntos casi encimados no aportan forma y solo engordan el trazo.
    if (Math.hypot(p[0] - u[0], p[1] - u[1]) < 1.5) return
    l.push(p)
    pintar()
  }
  const terminar = (e) => {
    if (!dibujando.current || (e && e.pointerId !== dedo.current)) return
    dibujando.current = false
    dedo.current = null
    avisar()
  }
  const borrar = () => {
    lineas.current = []
    pintar()
    avisar()
  }

  useEffect(pintar, [])

  return (
    <div className="lienzo-firma">
      <canvas ref={lienzo} width={ANCHO} height={ALTO} aria-label="Recuadro para firmar"
              onPointerDown={empezar} onPointerMove={seguir} onPointerUp={terminar}
              onPointerCancel={terminar} onPointerLeave={terminar} />
      {!hayAlgo && <span className="lienzo-guia" aria-hidden="true">Firma aquí con el dedo</span>}
      <div className="lienzo-linea" aria-hidden="true" />
      <button type="button" className="btn sm lienzo-borrar" onClick={borrar} disabled={!hayAlgo}>
        Borrar
      </button>
    </div>
  )
}

/** Una firma ya puesta. El camino lo revisó el servidor (solo M y L con
 *  números), y React lo pone como atributo, nunca como HTML. */
export function FirmaTrazo({ trazo, titulo }) {
  if (!trazo) return null
  return (
    <svg className="firma-trazo" viewBox={`0 0 ${ANCHO} ${ALTO}`} role="img"
         aria-label={titulo || 'Firma'} preserveAspectRatio="xMidYMid meet">
      <path d={trazo} fill="none" stroke="currentColor" strokeWidth="3"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
