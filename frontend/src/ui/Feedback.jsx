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

/** Nota al pie que cita la regla de negocio que la pantalla hace cumplir.
 *  Sirve para rastrear la pantalla hasta el documento de requerimientos. */
export function Regla({ children }) {
  return <p className="rule">{children}</p>
}
