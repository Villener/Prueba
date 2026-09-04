/** Selector de refacción por búsqueda.
 *
 * NO es un <select>. El catálogo real trae 18,233 refacciones: una lista
 * desplegable con todas es imposible de usar y además fue la causa de que la
 * pantalla de presupuestos se cayera entera —`/admin/piezas` devuelve el objeto
 * del buscador, no un arreglo, y el `.map` reventaba el árbol de React.
 *
 * Se busca por TEXTO y por CÓDIGO: desde que entró `CODIGOS TALLER.xlsx` buena
 * parte del catálogo trae número de material de SAP, así que se puede teclear el
 * código que viene en el papel del mecánico.
 *
 * Vive en ui/ y no en un módulo porque lo usan dos: el administrador al armar
 * un presupuesto y el capturista al teclear una requisición.
 */
import { useEffect, useRef, useState } from 'react'
import { api } from '../core/api.js'
import { Badge } from './Badge.jsx'
import { letras } from '../core/busqueda.js'

export function BuscadorPieza({ valor, nombre, onElegir }) {
  const [q, setQ] = useState('')
  const [res, setRes] = useState(null)
  const [buscando, setBuscando] = useState(false)
  const [abierto, setAbierto] = useState(false)
  const caja = useRef(null)

  // Con freno: son más de 18 mil piezas y se busca mientras escribe.
  // Los * no cuentan como letras: son comodines, igual que en el servidor.
  useEffect(() => {
    if (letras(q) < 2) { setRes(null); return }
    let vivo = true
    setBuscando(true)
    const id = setTimeout(() => {
      api.get('/admin/piezas', { q, limite: 8 })
        .then((d) => vivo && setRes(d))
        .catch(() => vivo && setRes(null))
        .finally(() => vivo && setBuscando(false))
    }, 300)
    return () => { vivo = false; clearTimeout(id) }
  }, [q])

  // Cerrar al hacer clic fuera: si no, la lista tapa el resto del formulario.
  useEffect(() => {
    const fuera = (e) => { if (caja.current && !caja.current.contains(e.target)) setAbierto(false) }
    document.addEventListener('mousedown', fuera)
    return () => document.removeEventListener('mousedown', fuera)
  }, [])

  if (valor && nombre) {
    return (
      <div className="pieza-elegida">
        <span className="grow">{nombre}</span>
        <button type="button" className="btn sm" onClick={() => onElegir(null, null, null)}>
          Cambiar
        </button>
      </div>
    )
  }

  return (
    <div className="buscador-pieza" ref={caja}>
      <input value={q} placeholder="balatas, filtro, 211790, JUE*EMP…"
             onChange={(e) => { setQ(e.target.value); setAbierto(true) }}
             onFocus={() => setAbierto(true)} />
      {abierto && letras(q) >= 2 && (
        <div className="bp-lista">
          {buscando ? <div className="bp-vacio">Buscando…</div>
            : !res || res.total === 0
              ? <div className="bp-vacio">{res?.aviso || 'Ninguna refacción coincide'}</div>
            : res.resultados.map((p) => (
              <button type="button" key={p.id} className="bp-op"
                      onClick={() => { onElegir(p.id, p.nombre, p.precio_referencia); setAbierto(false); setQ('') }}>
                <span className="grow">
                  <span className="t">{p.nombre}</span>
                  <span className="s">{p.sku || 'sin código'}{p.ubicacion ? ` · ${p.ubicacion}` : ''}</span>
                </span>
                <Badge tono={p.hay ? 'ok' : 'danger'}>{p.hay ? `Hay ${p.disponible}` : 'No hay'}</Badge>
              </button>
            ))}
          {res && res.total > res.mostrando && (
            <div className="bp-vacio">
              {res.total} coinciden · afina la búsqueda
            </div>
          )}
        </div>
      )}
    </div>
  )
}
