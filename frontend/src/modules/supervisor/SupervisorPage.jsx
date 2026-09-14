/** Modulo Supervisor - CU-SUP-* de docs/casos-de-uso.md */
import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHora } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoCuadrilla, IcoListo, IcoPrestamos,
  IcoUbicacion, Modal, Regla, Spinner, Tabla, useApi, useToast,
} from '../../ui/index.js'

export default function Supervisor() {
  return (
    <Routes>
      <Route path="/" element={<Cuadrilla />} />
      <Route path="/prestamos" element={<Prestamos />} />
      <Route path="/averias" element={<Averias />} />
      <Route path="/cumplimiento" element={<Cumplimiento />} />
    </Routes>
  )
}

/* -------------------------------------------------- CU-SUP-01/02/05 -------- */
function Cuadrilla() {
  const { data, cargando, error } = useApi(() => api.get('/supervisor/cuadrilla'))
  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="err">{error}</Aviso>

  const conduciendo = (data || []).filter((x) => x.conduciendo).length

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Mi cuadrilla</h1>
      <div className="grid g3" style={{ marginBottom: 4 }}>
        <div className="card kpi"><div className="val">{data?.length || 0}</div>
          <div className="lbl">Choferes</div></div>
        <div className="card kpi ok"><div className="val">{conduciendo}</div>
          <div className="lbl">Conduciendo</div></div>
        <div className="card kpi warn">
          <div className="val">{(data || []).filter((x) => x.es_prestada).length}</div>
          <div className="lbl">Con unidad prestada</div></div>
      </div>

      <Card title="Estado en tiempo real">
        {(data || []).map((c) => (
          <div className="list-item" key={c.chofer_id}>
            <span className={`dot ${c.conduciendo ? 'on' : 'off'}`} />
            <div className="grow">
              <div className="t">{c.chofer}</div>
              <div className="s">
                {c.conduciendo
                  ? `Conduciendo desde ${fmtFechaHora(c.desde)}`
                  : 'Sin jornada abierta'}
              </div>
              {c.unidades?.length > 0 && (
                <div className="s">
                  Responde por: {c.unidades.map((u) => `${u.num_economico} (${u.estado})`).join(', ')}
                </div>
              )}
              {c.es_prestada && (
                <div className="s" style={{ color: 'var(--warn)' }}>
                  Trae unidad prestada de {c.prestada_por}
                </div>
              )}
              {c.ubicacion && (
                <div className="s">
                  <IcoUbicacion size={13} className="ico-inline" aria-hidden="true" /> {c.ubicacion.lat.toFixed(4)}, {c.ubicacion.lng.toFixed(4)} ·{' '}
                  {fmtFechaHora(c.ubicacion.fecha)}
                </div>
              )}
            </div>
            {c.estado_unidad && <EstadoBadge estado={c.estado_unidad} />}
          </div>
        ))}
        {(data || []).length === 0 && <Empty icono={IcoCuadrilla}>Sin choferes asignados</Empty>}
      </Card>
    </>
  )
}

/* ------------------------------------------------------ CU-SUP-03/04 ------- */
function Prestamos() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/supervisor/prestamos'))
  const [vetar, setVetar] = useState(null)

  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Préstamos de la cuadrilla</h1>
      <Aviso tipo="info">
        Durante un préstamo activo, quien responde por la unidad es quien la recibió (RN-01).
        Si vetas un préstamo activo, la responsabilidad regresa al titular.
      </Aviso>
      <Card>
        {(data || []).length === 0 ? <Empty icono={IcoPrestamos}>Sin préstamos</Empty> : (
          (data || []).map((p) => (
            <div className="list-item" key={p.id}>
              <div className="grow">
                <div className="t">{p.unidad} · {p.motivo}</div>
                <div className="s">{p.chofer_presta} → {p.chofer_recibe}</div>
                <div className="s">
                  Hasta {fmtFecha(p.fecha_fin_prevista)}
                  {p.vencido && <span style={{ color: 'var(--danger)' }}> · vencido</span>}
                </div>
              </div>
              <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
                <EstadoBadge estado={p.estado} />
                {['solicitado', 'activo'].includes(p.estado) && (
                  <button className="btn sm danger" onClick={() => setVetar(p)}>Vetar</button>
                )}
              </div>
            </div>
          ))
        )}
      </Card>
      {vetar && (
        <ModalVetar prestamo={vetar} onCerrar={() => setVetar(null)}
                    onListo={() => { setVetar(null); recargar(); toast('Préstamo vetado') }} />
      )}
    </>
  )
}

function ModalVetar({ prestamo, onCerrar, onListo }) {
  const toast = useToast()
  const [motivo, setMotivo] = useState('')
  const enviar = async () => {
    try {
      await api.post(`/supervisor/prestamos/${prestamo.id}/vetar`, undefined, { motivo })
      onListo()
    } catch (e) { toast(e.message, 'err') }
  }
  return (
    <Modal titulo="Vetar préstamo" onClose={onCerrar}>
      <p className="sub">{prestamo.unidad}: {prestamo.chofer_presta} → {prestamo.chofer_recibe}</p>
      <div className="field">
        <label>Motivo</label>
        <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </div>
      <button className="btn danger block" disabled={!motivo.trim()} onClick={enviar}>
        Vetar préstamo
      </button>
    </Modal>
  )
}

/* ------------------------------------------------------ CU-SUP-06/07/09 ---- */
function Averias() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/supervisor/averias'))
  const tecnicos = useApi(() => api.get('/supervisor/tecnicos'))
  const [enviar, setEnviar] = useState(null)

  const escalar = async (a) => {
    try {
      const r = await api.post(`/supervisor/averias/${a.id}/despachar`, undefined,
                               { tipo: 'chofer_grua' })
      toast(r.mensaje); recargar()
    } catch (e) { toast(e.message, 'err') }
  }

  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Unidades varadas</h1>
      {(data || []).length === 0 ? <Empty icono={IcoListo}>Ninguna unidad varada</Empty> : (
        (data || []).map((a) => (
          <Card key={a.id} title={`${a.folio} · ${a.unidad}`}
                actions={<EstadoBadge estado={a.estado} />}>
            <p className="sub">{a.chofer} · {fmtFechaHora(a.fecha_hora)}</p>
            <p>{a.descripcion_falla}</p>
            {a.latitud && (
              <p className="sub"><IcoUbicacion size={13} className="ico-inline" aria-hidden="true" /> {a.latitud.toFixed(5)}, {a.longitud.toFixed(5)}</p>
            )}
            {a.en_vialidad_publica && !a.tiene_peritaje && (
              <Aviso tipo="warn">
                En vialidad pública sin folio de peritos. El arrastre está bloqueado hasta que el
                chofer lo registre (RN-04).
              </Aviso>
            )}
            <div className="btn-row">
              <button className="btn" disabled={!a.puede_solicitar_arrastre}
                      onClick={() => escalar(a)}>Escalar a chofer de grúa</button>
              <button className="btn" onClick={() => setEnviar(a)}>Registrar envío de mecánico</button>
            </div>
            <Regla>
              CU-SUP-09: el mecánico no usa la app, así que el envío a sitio lo registras tú.
            </Regla>
          </Card>
        ))
      )}
      {enviar && (
        <ModalMecanico averia={enviar} tecnicos={tecnicos.data || []}
                       onCerrar={() => setEnviar(null)}
                       onListo={() => { setEnviar(null); recargar() }} />
      )}
    </>
  )
}

function ModalMecanico({ averia, tecnicos, onCerrar, onListo }) {
  const toast = useToast()
  const [tid, setTid] = useState('')
  const enviar = async () => {
    try {
      const r = await api.post(`/supervisor/averias/${averia.id}/despachar`, undefined,
                               { tipo: 'mecanico', tecnico_id: Number(tid) })
      toast(r.mensaje); onListo()
    } catch (e) { toast(e.message, 'err') }
  }
  return (
    <Modal titulo="Registrar envío de mecánico" onClose={onCerrar}>
      <p className="sub">Unidad {averia.unidad}</p>
      <div className="field">
        <label>¿Qué mecánico fue?</label>
        <select value={tid} onChange={(e) => setTid(e.target.value)}>
          <option value="">Selecciona…</option>
          {tecnicos.filter((t) => t.especialidad === 'mecanico').map((t) => (
            <option key={t.id} value={t.id}>{t.nombre} · {t.telefono}</option>
          ))}
        </select>
      </div>
      <button className="btn primary block" disabled={!tid} onClick={enviar}>
        Registrar constancia
      </button>
      <Regla>
        El sistema no le avisa al mecánico (no tiene cuenta). Solo deja constancia de que lo
        enviaste, con fecha y hora.
      </Regla>
    </Modal>
  )
}

/* ---------------------------------------------------------- CU-SUP-08 ------ */
function Cumplimiento() {
  const { data, cargando } = useApi(() => api.get('/supervisor/cumplimiento'))
  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Cumplimiento de mantenimiento</h1>
      <Aviso tipo="info">
        Se reporta contra el <strong>poseedor actual</strong> de cada unidad, no contra el titular.
      </Aviso>
      <Card>
        <Tabla
          vacio="Toda la cuadrilla al corriente"
          columnas={[
            { k: 'chofer', t: 'Chofer' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'mantenimientos_vencidos', t: 'Vencidos', num: true },
            { k: 'dias_atraso_max', t: 'Atraso', num: true,
              r: (f) => f.dias_atraso_max > 0
                ? <Badge tono="danger">{f.dias_atraso_max} d</Badge>
                : <Badge tono="ok">Al día</Badge> },
            { k: 'penalizaciones', t: 'Penaliz.', num: true },
          ]}
          filas={data || []} />
      </Card>
    </>
  )
}
