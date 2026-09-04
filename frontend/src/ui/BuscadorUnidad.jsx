/** Selector de unidad por número económico.
 *
 * NO es un <select>: son ~700 unidades. Y busca sin guiones ni espacios porque
 * el papel escribe «BG-354P» y el catálogo «BG354P» — el servidor compara las
 * dos formas. Sin eso, la mitad de las unidades del libro no casan y el
 * capturista acaba dejando la unidad en blanco.
 *
 * Vive en ui/ porque lo usan dos módulos con endpoints distintos: el capturista
 * (requisiciones) y el administrador (reporte de mantenimiento). Cada rol solo
 * puede llamar al suyo, así que el endpoint es un parámetro y no una constante.
 */
import { useEffect, useRef, useState } from 'react'
import { api } from '../core/api.js'
import { Badge } from './Badge.jsx'

export function BuscadorUnidad({ elegida, onElegir, endpoint = '/capturista/unidades' }) {
  const [q, setQ] = useState('')
  const [res, setRes] = useState([])
  const [buscando, setBuscando] = useState(false)
  const [abierto, setAbierto] = useState(false)
  const caja = useRef(null)

  useEffect(() => {
    if (q.trim().length < 1) { setRes([]); return }
    let vivo = true
    setBuscando(true)
    const id = setTimeout(() => {
      api.get(endpoint, { q, limite: 8 })
        .then((d) => vivo && setRes(d || []))
        .catch(() => vivo && setRes([]))
        .finally(() => vivo && setBuscando(false))
    }, 250)
    return () => { vivo = false; clearTimeout(id) }
  }, [q, endpoint])

  useEffect(() => {
    const fuera = (e) => { if (caja.current && !caja.current.contains(e.target)) setAbierto(false) }
    document.addEventListener('mousedown', fuera)
    return () => document.removeEventListener('mousedown', fuera)
  }, [])

  if (elegida) {
    return (
      <div className="pieza-elegida">
        <span className="grow">
          {elegida.num_economico}
          {elegida.modelo ? ` · ${elegida.modelo}` : ''}
        </span>
        <button type="button" className="btn sm" onClick={() => onElegir(null)}>Cambiar</button>
      </div>
    )
  }

  return (
    <div className="buscador-pieza" ref={caja}>
      <input value={q} placeholder="2154, BG-354P, 1784…"
             onChange={(e) => { setQ(e.target.value); setAbierto(true) }}
             onFocus={() => setAbierto(true)} />
      {abierto && q.trim().length >= 1 && (
        <div className="bp-lista">
          {buscando ? <div className="bp-vacio">Buscando…</div>
            : res.length === 0 ? <div className="bp-vacio">Ninguna unidad coincide</div>
            : res.map((u) => (
              <button type="button" key={u.id} className="bp-op"
                      onClick={() => { onElegir(u); setAbierto(false); setQ('') }}>
                <span className="grow">
                  <span className="t">{u.num_economico}</span>
                  <span className="s">
                    {u.modelo || u.marca || 'sin descripción'}
                    {u.anio ? ` · ${u.anio}` : ''}
                  </span>
                </span>
                {!u.activo && <Badge tono="danger">baja</Badge>}
              </button>
            ))}
        </div>
      )}
    </div>
  )
}
