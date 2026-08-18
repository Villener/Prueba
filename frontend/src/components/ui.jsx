import { useEffect, useState, createContext, useContext, useCallback } from 'react'

export function Card({ title, sub, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {actions}
        </div>
      )}
      {sub && <p className="sub">{sub}</p>}
      {children}
    </section>
  )
}

export function Kpi({ valor, etiqueta, hint, tono = '' }) {
  return (
    <div className={`card kpi ${tono}`}>
      <div className="val">{valor}</div>
      <div className="lbl">{etiqueta}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}

export function Badge({ children, tono = '' }) {
  return <span className={`badge ${tono}`}>{children}</span>
}

/** Colores consistentes para los estados del modelo. */
export function EstadoBadge({ estado }) {
  const tonos = {
    disponible: 'ok', lista: 'ok', aceptada: 'ok', aprobado: 'ok', activo: 'ok',
    finalizado: 'ok', terminada: 'ok', cerrada: '', recibida: 'ok', cumplido: 'ok',
    en_ruta: 'info', en_proceso: 'info', enviado_gerente: 'info', capturado: 'info',
    solicitado: 'info', aceptado: 'info', en_traslado: 'info', pendiente: 'warn',
    en_cola: 'warn', en_espera: 'warn', esperando_peritos: 'warn', espera_presupuesto: 'warn',
    espera_refacciones: 'warn', en_transito: 'warn', devuelto: 'warn', en_disputa: 'warn',
    varada: 'danger', en_arrastre: 'danger', rechazada: 'danger', rechazado: 'danger',
    vencido: 'danger', aplicada: 'danger', baja: 'danger',
  }
  return <Badge tono={tonos[estado] ?? ''}>{String(estado || '—').replace(/_/g, ' ')}</Badge>
}

export function Empty({ icono = '📭', children }) {
  return (
    <div className="empty">
      <span className="ico">{icono}</span>
      {children}
    </div>
  )
}

export function Spinner() {
  return <div className="spinner" aria-label="Cargando" />
}

export function Aviso({ tipo = 'info', children }) {
  if (!children) return null
  return <div className={`alert-box ${tipo}`}>{children}</div>
}

/** Nota que cita la regla de negocio que hace cumplir la pantalla. */
export function Regla({ children }) {
  return <p className="rule">{children}</p>
}

export function Modal({ titulo, onClose, children }) {
  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', esc)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', esc)
      document.body.style.overflow = ''
    }
  }, [onClose])
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true">
        <div className="card-head">
          <h2>{titulo}</h2>
          <button className="btn sm" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ toast -- */
const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }) {
  const [t, setT] = useState(null)
  const show = useCallback((mensaje, tipo = 'ok') => {
    setT({ mensaje, tipo })
    setTimeout(() => setT(null), 3800)
  }, [])
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {t && <div className={`toast ${t.tipo}`} role="status">{t.mensaje}</div>}
    </ToastCtx.Provider>
  )
}

/** Carga datos de la API con estados de carga y error ya resueltos. */
export function useApi(fn, deps = []) {
  const [data, setData] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [n, setN] = useState(0)

  useEffect(() => {
    let vivo = true
    setCargando(true)
    fn()
      .then((d) => vivo && (setData(d), setError(null)))
      .catch((e) => vivo && setError(e.message))
      .finally(() => vivo && setCargando(false))
    return () => { vivo = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n])

  return { data, cargando, error, recargar: () => setN((x) => x + 1) }
}

/** Tabla que se convierte en tarjetas en pantallas chicas. */
export function Tabla({ columnas, filas, vacio = 'Sin registros', onFila }) {
  if (!filas?.length) return <Empty>{vacio}</Empty>
  return (
    <div className="table-wrap stack-mobile">
      <table>
        <thead>
          <tr>{columnas.map((c) => <th key={c.k} className={c.num ? 'num' : ''}>{c.t}</th>)}</tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={f.id ?? i} onClick={onFila ? () => onFila(f) : undefined}
                style={onFila ? { cursor: 'pointer' } : undefined}>
              {columnas.map((c) => (
                <td key={c.k} data-l={c.t} className={c.num ? 'num' : ''}>
                  {c.r ? c.r(f) : (f[c.k] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
