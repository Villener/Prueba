import { Empty } from './Feedback.jsx'

/** Tabla que en el telefono se vuelve una tarjeta por fila, con la etiqueta
 *  al frente de cada dato. El chofer y el chofer de grua trabajan asi. */
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
