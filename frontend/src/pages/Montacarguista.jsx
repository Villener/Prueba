import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { api, fmtFechaHora } from '../api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, Modal, Regla, Spinner, Tabla, useApi, useToast,
} from '../components/ui.jsx'

export default function Montacarguista() {
  return (
    <Routes>
      <Route path="/" element={<Alertas />} />
      <Route path="/arrastres" element={<Arrastres />} />
      <Route path="/historial" element={<Historial />} />
    </Routes>
  )
}

/* ---------------------------------------------------------- CU-MON-01 ------ */
function Alertas() {
  const { data, cargando } = useApi(() => api.get('/montacarguista/alertas'))
  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Unidades varadas</h1>
      {(data || []).length === 0 ? <Empty icono="✅">Sin alertas activas</Empty> : (
        (data || []).map((a) => (
          <Card key={a.id} title={`${a.folio} · ${a.unidad}`}
                actions={<EstadoBadge estado={a.estado} />}>
            <p className="sub">{a.chofer} · {fmtFechaHora(a.fecha_hora)}</p>
            <p>{a.descripcion_falla}</p>
            {a.latitud && (
              <p className="sub">
                📍 {a.latitud.toFixed(5)}, {a.longitud.toFixed(5)}{' '}
                <a href={`https://www.google.com/maps?q=${a.latitud},${a.longitud}`}
                   target="_blank" rel="noreferrer">abrir en mapa</a>
              </p>
            )}
            {a.en_vialidad_publica && !a.tiene_peritaje && (
              <Aviso tipo="warn">
                Vialidad pública sin folio de peritos. No puedes tomar este arrastre hasta que el
                chofer lo registre (RN-04).
              </Aviso>
            )}
            {a.arrastre_id
              ? <Badge tono="info">Arrastre {a.arrastre_estado}</Badge>
              : <Badge>Sin arrastre solicitado</Badge>}
          </Card>
        ))
      )}
    </>
  )
}

/* ------------------------------------------- CU-MON-02/03/04/05/06 --------- */
function Arrastres() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/montacarguista/arrastres'))
  const [cerrar, setCerrar] = useState(null)

  const correr = async (fn, ok) => {
    try { await fn(); toast(ok); recargar() } catch (e) { toast(e.message, 'err') }
  }

  const mandarUbicacion = (a) => {
    const enviar = (lat, lng) => correr(
      () => api.post(`/montacarguista/arrastres/${a.id}/ubicacion`, { latitud: lat, longitud: lng }),
      'Ubicación enviada al chofer')
    if (!navigator.geolocation) return enviar(32.5149, -117.0382)
    navigator.geolocation.getCurrentPosition(
      (p) => enviar(p.coords.latitude, p.coords.longitude),
      () => enviar(32.5149, -117.0382), { timeout: 8000 })
  }

  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Arrastres</h1>
      {(data || []).length === 0 ? <Empty icono="🛻">Sin arrastres activos</Empty> : (
        (data || []).map((a) => (
          <Card key={a.id} title={`${a.folio} · ${a.unidad}`}
                actions={<EstadoBadge estado={a.estado} />}>
            <p className="sub">Responsable: {a.chofer_responsable || '—'}</p>
            <p className="sub">Solicitado {fmtFechaHora(a.fecha_solicitud)}</p>
            {a.latitud_origen && (
              <p className="sub">
                📍 Destino:{' '}
                <a href={`https://www.google.com/maps?q=${a.latitud_origen},${a.longitud_origen}`}
                   target="_blank" rel="noreferrer">
                  {a.latitud_origen.toFixed(4)}, {a.longitud_origen.toFixed(4)}
                </a>
              </p>
            )}
            {a.ultima_actualizacion && (
              <p className="sub">Última posición enviada {fmtFechaHora(a.ultima_actualizacion)}</p>
            )}

            <div className="btn-row" style={{ marginTop: 10 }}>
              {a.estado === 'solicitado' && (
                <>
                  <button className="btn primary sm" onClick={() => correr(
                    () => api.post(`/montacarguista/arrastres/${a.id}/aceptar`),
                    'Arrastre aceptado')}>Aceptar</button>
                  <button className="btn danger sm" onClick={() => correr(
                    () => api.post(`/montacarguista/arrastres/${a.id}/rechazar`, undefined,
                                   { motivo: 'No disponible' }), 'Arrastre rechazado')}>
                    Rechazar
                  </button>
                </>
              )}
              {['aceptado', 'en_ruta'].includes(a.estado) && (
                <>
                  <button className="btn sm" onClick={() => mandarUbicacion(a)}>
                    📍 Enviar mi ubicación
                  </button>
                  <button className="btn sm" onClick={() => correr(
                    () => api.post(`/montacarguista/arrastres/${a.id}/llegada`),
                    'Llegada registrada')}>Llegué al sitio</button>
                </>
              )}
              {a.estado === 'en_traslado' && (
                <button className="btn ok sm" onClick={() => setCerrar(a)}>Cerrar arrastre</button>
              )}
            </div>
          </Card>
        ))
      )}
      {cerrar && (
        <ModalCierre arrastre={cerrar} onCerrar={() => setCerrar(null)}
                     onListo={() => { setCerrar(null); recargar() }} />
      )}
    </>
  )
}

function ModalCierre({ arrastre, onCerrar, onListo }) {
  const toast = useToast()
  const talleres = useApi(() => api.get('/montacarguista/talleres'))
  const [form, setForm] = useState({ taller_destino_id: '', km_recorridos: '', observaciones: '' })

  const enviar = async (e) => {
    e.preventDefault()
    try {
      await api.post(`/montacarguista/arrastres/${arrastre.id}/cerrar`, {
        taller_destino_id: Number(form.taller_destino_id),
        km_recorridos: Number(form.km_recorridos || 0),
        observaciones: form.observaciones,
      })
      toast('Arrastre cerrado y registrado')
      onListo()
    } catch (err) { toast(err.message, 'err') }
  }

  return (
    <Modal titulo={`Cerrar ${arrastre.folio}`} onClose={onCerrar}>
      <form onSubmit={enviar}>
        <p className="sub">
          Unidad {arrastre.unidad} · responsable {arrastre.chofer_responsable}
        </p>
        <div className="field">
          <label>¿En qué taller quedó?</label>
          <select required value={form.taller_destino_id}
                  onChange={(e) => setForm({ ...form, taller_destino_id: e.target.value })}>
            <option value="">Selecciona…</option>
            {(talleres.data || []).map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Kilómetros recorridos</label>
          <input type="number" step="0.1" value={form.km_recorridos}
                 onChange={(e) => setForm({ ...form, km_recorridos: e.target.value })} />
        </div>
        <div className="field">
          <label>Observaciones / evidencia</label>
          <textarea value={form.observaciones} placeholder="Estado en que se entregó la unidad"
                    onChange={(e) => setForm({ ...form, observaciones: e.target.value })} />
        </div>
        <button className="btn primary block">Cerrar arrastre</button>
        <Regla>
          Queda registrado: taller destino, unidad, chofer responsable y hora de cierre. Además se
          genera la solicitud de ingreso al taller automáticamente.
        </Regla>
      </form>
    </Modal>
  )
}

/* ---------------------------------------------------------- CU-MON-07 ------ */
function Historial() {
  const { data, cargando } = useApi(() => api.get('/montacarguista/arrastres', { historial: true }))
  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Mis arrastres</h1>
      <Card>
        <Tabla
          vacio="Sin arrastres realizados"
          columnas={[
            { k: 'folio', t: 'Folio' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'taller_destino', t: 'Taller destino' },
            { k: 'chofer_responsable', t: 'Responsable' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            { k: 'fecha_finalizacion', t: 'Cierre', r: (f) => fmtFechaHora(f.fecha_finalizacion) },
          ]}
          filas={data || []} />
      </Card>
    </>
  )
}
