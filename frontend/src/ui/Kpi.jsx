/** Cifra grande con su etiqueta. El tono pinta la franja superior. */
export function Kpi({ valor, etiqueta, hint, tono = '' }) {
  return (
    <div className={`card kpi ${tono}`}>
      <div className="lbl">{etiqueta}</div>
      <div className="val">{valor}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}
