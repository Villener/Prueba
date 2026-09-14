/** CU-ADM-05 — órdenes de servicio, SOLO CONSULTA.
 *
 * v1.3: esta pantalla ya no captura nada. Capturar diagnóstico, gestionar la
 * cola de especialistas, registrar avance y emitir la salida se pedían aquí Y
 * en el reporte de mantenimiento — las mismas cuatro cosas, dos veces, con dos
 * resultados que podían no coincidir. Ahora el trabajo del piso se captura en
 * un solo lugar: el formato.
 *
 * Lo que queda aquí es lo que el formato NO cubre y sigue haciendo falta: el
 * expediente administrativo de la estancia —folio, estado, días en taller— y su
 * enlace con presupuestos y órdenes de compra, de los que dependen Erick y el
 * gerente.
 *
 * `AsignacionTecnico` y `FormatoSalida` siguen en el modelo: hay órdenes viejas
 * capturadas así y el historial del gerente las lee. Se muestran, no se editan.
 */
import { api, fmtFecha, fmtFechaHora } from '../../core/api.js'
import { useNavigate } from 'react-router-dom'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoNota, IcoOrdenes, Regla, Spinner, useApi,
} from '../../ui/index.js'

export function Ordenes() {
  const navegar = useNavigate()
  const { data, cargando } = useApi(() => api.get('/admin/ordenes'))
  const reportes = useApi(() => api.get('/admin/reportes', { estado: 'abierto', limite: 200 }))

  if (cargando) return <Spinner />
  const ordenes = data || []
  // El formato es lo que se abre; la orden es el expediente. Se cruzan por
  // orden_servicio_id para poder saltar de uno al otro sin buscar a mano.
  const porOrden = Object.fromEntries(
    (reportes.data || []).filter((r) => r.orden_servicio_id).map((r) => [r.orden_servicio_id, r]))

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Órdenes de servicio</h1>

      <Aviso tipo="info">
        Esta pantalla es de <strong>consulta</strong>. El trabajo del piso —qué se le hace a la
        unidad, quién lo hace y cuándo sale— se captura en el <strong>reporte de
        mantenimiento</strong>, que se abre solo cuando la unidad entra.
      </Aviso>

      {ordenes.length === 0 ? <Empty icono={IcoOrdenes}>Sin órdenes abiertas</Empty> : (
        ordenes.map((o) => {
          const rep = porOrden[o.id]
          return (
            <Card key={o.id} title={`${o.folio} · ${o.unidad}`}
                  actions={<EstadoBadge estado={o.estado} />}>
              <p className="sub">
                {o.espacio || 'sin espacio'} · {o.dias_en_taller} días en taller · entró{' '}
                {fmtFecha(o.fecha_entrada)}
              </p>

              {rep ? (
                <>
                  <div className="list-item">
                    <div className="grow">
                      <div className="t">{rep.folio}</div>
                      <div className="s">
                        {rep.atendido_por.length
                          ? rep.atendido_por.map((t) => t.tecnico).join(', ')
                          : 'sin responsable asignado'}
                      </div>
                    </div>
                    <Badge tono="warn">{rep.estado}</Badge>
                  </div>
                  <button className="btn primary block" style={{ marginTop: 10 }}
                          onClick={() => navegar(`/reportes/${rep.id}`)}>
                    Abrir el formato de mantenimiento
                  </button>
                </>
              ) : (
                <p className="sub">
                  Sin formato abierto. Esta orden es anterior a v1.3 o la unidad entró por
                  otro camino; levántalo desde <em>Reportes</em>.
                </p>
              )}

              {/* Cola vieja: se conserva para no perder lo ya capturado, pero
                  ya no se edita desde aquí. */}
              {o.asignaciones.length > 0 && (
                <details style={{ marginTop: 12 }}>
                  <summary className="sub">
                    Cola de especialistas capturada antes de v1.3 ({o.asignaciones.length})
                  </summary>
                  {o.asignaciones.map((a) => (
                    <div className="list-item" key={a.id}>
                      <Badge>{a.orden_en_cola}</Badge>
                      <div className="grow">
                        <div className="t">{a.tecnico}</div>
                        <div className="s">{a.especialidad}</div>
                        {a.diagnostico && <div className="s"><IcoNota size={13} className="ico-inline" aria-hidden="true" /> {a.diagnostico}</div>}
                        {a.capturado_por && (
                          <div className="s" style={{ color: 'var(--muted)' }}>
                            Capturado por {a.capturado_por} · {fmtFechaHora(a.fecha_captura)}
                          </div>
                        )}
                      </div>
                      <EstadoBadge estado={a.estado} />
                    </div>
                  ))}
                </details>
              )}
            </Card>
          )
        })
      )}

      <Regla>
        CU-ADM-05: la orden es el expediente de la estancia y sostiene los presupuestos y las
        órdenes de compra. El formato es el papel del piso. Se cruzan, no se duplican.
      </Regla>
    </>
  )
}

/* ------------------------------------- CU-ADM-12/13/07/16/08 (v1.1) -------- */
