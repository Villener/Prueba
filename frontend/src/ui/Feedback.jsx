import { IcoVacio } from './iconos.jsx'

/** El estado "aqui no hay nada".
 *
 * `icono` es un COMPONENTE, no una cadena: se pasa `<Empty icono={IcoTaller}>`.
 * Asi el que escribe la pantalla elige del catalogo de ui/iconos.jsx en vez de
 * pegar un emoji, que era como acababan dos dibujos distintos para lo mismo.
 */
export function Empty({ icono: Icono = IcoVacio, children }) {
  return (
    <div className="empty">
      <span className="ico"><Icono size={30} strokeWidth={1.5} aria-hidden="true" /></span>
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

/** Nota al pie que cita la regla de negocio que la pantalla hace cumplir.
 *  Sirve para rastrear la pantalla hasta el documento de requerimientos. */
export function Regla({ children }) {
  return <p className="rule">{children}</p>
}
