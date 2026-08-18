import { api, fmtFechaHora } from '../api.js'
import { Card, Empty, Spinner, useApi, useToast } from '../components/ui.jsx'

export default function Notificaciones() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/auth/notificaciones'))

  const leer = async (n) => {
    if (n.leida) return
    try { await api.post(`/auth/notificaciones/${n.id}/leer`); recargar() }
    catch (e) { toast(e.message, 'err') }
  }

  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Notificaciones</h1>
      <Card>
        {(data || []).length === 0 ? <Empty icono="🔔">Sin notificaciones</Empty> : (
          (data || []).map((n) => (
            <div className="list-item" key={n.id} onClick={() => leer(n)}
                 style={{ cursor: n.leida ? 'default' : 'pointer' }}>
              <span className={`dot ${n.leida ? 'off' : 'alert'}`} />
              <div className="grow">
                <div className="t">{n.titulo}</div>
                <div className="s">{n.mensaje}</div>
                <div className="s" style={{ color: 'var(--muted)' }}>
                  {fmtFechaHora(n.fecha_envio)}
                </div>
              </div>
            </div>
          ))
        )}
      </Card>
    </>
  )
}
