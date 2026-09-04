/** CU-CAP-01 y CU-CAP-02: lo que el capturista ya tecleo.
 *
 * Abre con las 99 requisiciones reales de julio y agosto que trae el libro
 * `REQUIS 2026 2.xlsx`, no con una tabla vacia. Asi el puesto ve su propio
 * trabajo el primer dia y puede comprobar contra el Excel que nada se perdio.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHora } from '../../core/api.js'
import {
  Badge, Card, Empty, Kpi, Modal, Regla, Spinner, Tabla, useApi,
} from '../../ui/index.js'

export function Requisiciones() {
  const [q, setQ] = useState('')
  const [termino, setTermino] = useState('')
  const [abierta, setAbierta] = useState(null)

  const resumen = useApi(() => api.get('/capturista/resumen'))
  const lista = useApi(() => api.get('/capturista/requisiciones', { q: termino, limite: 100 }),
                       [termino])

  const buscar = (e) => {
    e.preventDefault()
    setTermino(q.trim())
  }

  const r = resumen.data
  return (
    <>
      <div className="card-head" style={{ marginBottom: 14 }}>
        <h1>Requisiciones</h1>
        <Link className="btn primary" to="/capturar">Capturar papel</Link>
      </div>

      {r && (
        <div className="grid g4" style={{ marginBottom: 14 }}>
          <Kpi valor={r.requisiciones} etiqueta="Capturadas"
               hint={r.ultimo_folio ? `última ${r.ultimo_folio}` : null} />
          <Kpi valor={r.del_mes} etiqueta="Este mes" />
          <Kpi valor={r.renglones} etiqueta="Renglones" />
          {/* El unico indicador que hay que vigilar: cada renglon sin casar es
              un codigo que el catalogo no reconoce, y despues aparece como
              "no hay" cuando en realidad si hay, con otro nombre. */}
          <Kpi valor={`${r.pct_casado}%`} etiqueta="Casado con catálogo"
               tono={r.pct_casado >= 90 ? 'ok' : 'warn'}
               hint={r.sin_casar ? `${r.sin_casar} sin casar` : 'todos casados'} />
        </div>
      )}

      <Card>
        <form onSubmit={buscar} className="btn-row" style={{ marginBottom: 12 }}>
          <input value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="folio, unidad o quien pidió: J332, 2154, Ponce…" />
          <button className="btn primary">Buscar</button>
          {termino && (
            <button type="button" className="btn"
                    onClick={() => { setQ(''); setTermino('') }}>Limpiar</button>
          )}
        </form>

        {lista.cargando ? <Spinner /> : (
          <Tabla
            vacio={termino ? `Ninguna requisición coincide con "${termino}"`
                           : 'Todavía no hay requisiciones capturadas'}
            onFila={(f) => setAbierta(f.id)}
            columnas={[
              { k: 'folio', t: 'Folio' },
              { k: 'fecha', t: 'Fecha', r: (f) => fmtFecha(f.fecha) },
              { k: 'unidad', t: 'Unidad', r: (f) => f.unidad || '—' },
              { k: 'solicitante', t: 'Lo pidió', r: (f) => f.solicitante || '—' },
              { k: 'total_renglones', t: 'Renglones', num: true },
              { k: 'total_piezas', t: 'Piezas', num: true },
              { k: 'origen', t: 'Origen',
                r: (f) => <Badge tono={f.origen === 'app' ? 'ok' : ''}>
                            {f.origen === 'app' ? 'capturada aquí' : 'libro REQUIS'}
                          </Badge> },
            ]}
            filas={lista.data || []} />
        )}
      </Card>

      <Regla>
        El folio lo trae el papel y puede venir repetido: en el libro real hay diez folios
        reutilizados para requisiciones distintas. Por eso el sistema avisa, pero no lo prohíbe.
      </Regla>

      {abierta && <Detalle id={abierta} onClose={() => setAbierta(null)} />}
    </>
  )
}

/** El documento completo, renglon por renglon. */
function Detalle({ id, onClose }) {
  const { data, cargando } = useApi(() => api.get(`/capturista/requisiciones/${id}`), [id])
  return (
    <Modal titulo={data ? `Requisición ${data.folio}` : 'Requisición'} onClose={onClose}>
      {cargando || !data ? <Spinner /> : (
        <>
          <p className="sub">
            {fmtFecha(data.fecha)} · Unidad {data.unidad || '—'}
            {data.equipo_sap ? ` · SAP ${data.equipo_sap}` : ''}
            {data.centro_gestion ? ` · ${data.centro_gestion}` : ''}
          </p>
          <p className="sub">
            Lo pidió: {data.solicitante || '—'}
            {data.solicitante_num_empleado ? ` (${data.solicitante_num_empleado})` : ''}
            {data.taller ? ` · ${data.taller}` : ''}
          </p>
          {/* RN-11: los dos responsables del dato, quien lo pidio y quien lo
              tecleo. Es lo que el Excel no guarda. */}
          <p className="sub">
            Tecleada por: {data.capturada_por || 'sin registro'}
            {data.fecha_captura ? ` · ${fmtFechaHora(data.fecha_captura)}` : ''}
          </p>

          <Tabla
            vacio="Sin renglones"
            columnas={[
              { k: 'linea', t: '#', num: true },
              { k: 'codigo', t: 'Código' },
              { k: 'descripcion', t: 'Material' },
              { k: 'cantidad', t: 'Cant.', num: true },
              { k: 'en_catalogo', t: 'Catálogo',
                r: (f) => f.en_catalogo
                  ? <Badge tono="ok">sí</Badge>
                  : <Badge tono="warn">sin casar</Badge> },
            ]}
            filas={data.renglones || []} />

          {data.observaciones && <p className="sub">{data.observaciones}</p>}
          {(data.renglones || []).some((x) => !x.en_catalogo) && (
            <Regla>
              Los renglones «sin casar» se guardaron con su código y su texto tal como venían.
              Aparecen juntos en <strong>Pendientes</strong> para darlos de alta en el catálogo.
            </Regla>
          )}
        </>
      )}
    </Modal>
  )
}
