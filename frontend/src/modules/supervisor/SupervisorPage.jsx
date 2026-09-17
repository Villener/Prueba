/** Modulo Supervisor - CU-SUP-* de docs/casos-de-uso.md */
import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHora } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoPlantilla, IcoListo, IcoPrestamos,
  IcoUbicacion, Modal, Regla, Spinner, Tabla, useApi, useToast,
} from '../../ui/index.js'

export default function Supervisor() {
  return (
    <Routes>
      <Route path="/" element={<Plantilla />} />
      <Route path="/prestamos" element={<Prestamos />} />
      <Route path="/averias" element={<Averias />} />
      <Route path="/cumplimiento" element={<Cumplimiento />} />
    </Routes>
  )
}

/* -------------------------------------------------- CU-SUP-01/02/05 -------- */
function Plantilla() {
  const { data, cargando, error } = useApi(() => api.get('/supervisor/plantilla'))
  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="err">{error}</Aviso>

  const conduciendo = (data || []).filter((x) => x.conduciendo).length

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Mi plantilla</h1>
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
        {(data || []).length === 0 && <Empty icono={IcoPlantilla}>Sin choferes asignados</Empty>}
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
      <h1 style={{ marginBottom: 14 }}>Préstamos de la plantilla</h1>
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
          vacio="Toda la plantilla al corriente"
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

      <Amonestaciones />
    </>
  )
}

/* ------------------------------------------------------------ CU-SUP-10 ---- */
/** RN-14. El sistema PROPONE, aqui una persona FIRMA.
 *
 *  A esta lista solo llega lo que ya paso el filtro del aviso: hubo cita
 *  CONFIRMADA y la unidad no se presento. Una unidad a la que el taller nunca
 *  le dio cita no aparece, y por eso no se puede amonestar a ese chofer.
 */
function Amonestaciones() {
  const cand = useApi(() => api.get('/supervisor/amonestaciones/candidatas'))
  const emitidas = useApi(() => api.get('/supervisor/amonestaciones'))
  const [firmar, setFirmar] = useState(null)
  const toast = useToast()

  const recargar = () => { cand.recargar(); emitidas.recargar() }

  return (
    <>
      <Card title="Faltas por amonestar"
            sub="Citas confirmadas a las que el chofer no se presentó">
        <Tabla
          vacio="Ninguna falta pendiente de resolver"
          columnas={[
            { k: 'chofer', t: 'Chofer' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'fecha_falta', t: 'Faltó el', r: (f) => fmtFecha(f.fecha_falta) },
            { k: 'dias_atraso', t: 'Atraso', num: true,
              r: (f) => <Badge tono="danger">{f.dias_atraso} d</Badge> },
            { k: 'seria_la', t: 'Sería la', num: true,
              r: (f) => f.amonestaciones_previas > 0
                ? <Badge tono="danger">{f.seria_la}ª</Badge>
                : <Badge>1ª</Badge> },
            { k: 'acciones', t: '',
              r: (f) => <button className="btn sm" onClick={() => setFirmar(f)}>Amonestar</button> },
          ]}
          filas={cand.data || []} />
        <Regla>
          El sistema arma el expediente, pero <strong>no firma</strong>. Una sanción que sale
          sola de un proceso automático es la que nadie puede explicar cuando el chofer
          reclama. Y antes de firmar se ve si es la primera o la cuarta.
        </Regla>
      </Card>

      <Card title="Amonestaciones emitidas" sub="De mi plantilla, con su estado">
        <Tabla
          vacio="Sin amonestaciones emitidas"
          columnas={[
            { k: 'chofer', t: 'Chofer' },
            { k: 'consecutivo', t: '#', num: true, r: (f) => f.consecutivo + 'ª' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'fecha_emision', t: 'Emitida', r: (f) => fmtFecha(f.fecha_emision) },
            { k: 'emitida_por', t: 'Firmó' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            { k: 'acciones', t: '',
              r: (f) => f.estado === 'inconforme'
                ? <ResolverInconformidad a={f} onListo={recargar} />
                : null },
          ]}
          filas={emitidas.data || []} />
      </Card>

      {firmar && (
        <ModalFirmar falta={firmar} onCerrar={() => setFirmar(null)}
                     onListo={() => { setFirmar(null); recargar(); toast('Amonestación emitida') }} />
      )}
    </>
  )
}

function ModalFirmar({ falta, onCerrar, onListo }) {
  const [nota, setNota] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  async function enviar() {
    setEnviando(true); setError(null)
    try {
      const q = '/supervisor/amonestaciones?aviso_id=' + falta.aviso_id
        + (nota ? '&nota=' + encodeURIComponent(nota) : '')
      await api.post(q)
      onListo()
    } catch (e) { setError(String(e.message || e)); setEnviando(false) }
  }

  return (
    <Modal titulo={'Amonestar a ' + falta.chofer} onClose={onCerrar}>
      {error && <Aviso tipo="err">{error}</Aviso>}
      <p>
        Faltó a su cita del <strong>{fmtFecha(falta.fecha_falta)}</strong> con la unidad{' '}
        <strong>{falta.unidad}</strong>. Sería su <strong>{falta.seria_la}ª</strong> amonestación.
      </p>
      <Aviso tipo="info">
        Es un acto <strong>administrativo</strong>, no económico: va al expediente del chofer y
        no descuenta nada. Él la va a ver y se puede inconformar.
      </Aviso>
      <label className="campo">
        <span>Nota (opcional)</span>
        <textarea rows={3} value={nota} onChange={(e) => setNota(e.target.value)}
                  placeholder="Lo que se habló con el chofer" />
      </label>
      <div className="acciones">
        <button className="btn" onClick={onCerrar}>Cancelar</button>
        <button className="btn primario" onClick={enviar} disabled={enviando}>
          {enviando ? 'Emitiendo...' : 'Emitir amonestación'}
        </button>
      </div>
    </Modal>
  )
}

function ResolverInconformidad({ a, onListo }) {
  const [abierto, setAbierto] = useState(false)
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function resolver(ratifica) {
    setEnviando(true)
    try {
      const q = '/supervisor/amonestaciones/' + a.id + '/resolver?ratifica=' + ratifica
        + (texto ? '&texto=' + encodeURIComponent(texto) : '')
      await api.post(q)
      setAbierto(false); onListo()
    } finally { setEnviando(false) }
  }

  return (
    <>
      <button className="btn sm" onClick={() => setAbierto(true)}>Resolver</button>
      {abierto && (
        <Modal titulo={'Inconformidad de ' + a.chofer} onClose={() => setAbierto(false)}>
          <p><strong>Su amonestación {a.consecutivo}ª:</strong> {a.motivo}</p>
          <Aviso tipo="warn"><strong>Dice:</strong> {a.inconformidad}</Aviso>
          <label className="campo">
            <span>Tu resolución</span>
            <textarea rows={3} value={texto} onChange={(e) => setTexto(e.target.value)} />
          </label>
          <Regla>
            Anular no borra el renglón: el expediente tiene que poder contar que hubo una
            amonestación y que se echó para atrás. Si desapareciera, el chofer perdería la
            prueba de que reclamó y le dieron la razón.
          </Regla>
          <div className="acciones">
            <button className="btn" onClick={() => resolver(false)} disabled={enviando}>
              Dejar sin efecto
            </button>
            <button className="btn primario" onClick={() => resolver(true)} disabled={enviando}>
              Sostener
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
