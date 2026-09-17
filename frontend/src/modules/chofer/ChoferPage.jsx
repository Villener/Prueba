/** Modulo Chofer - CU-CHO-* de docs/casos-de-uso.md */
import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { BotonEmergencia } from './BotonEmergencia.jsx'
import { FotosAveria } from './FotosAveria.jsx'
import { api, fmtFecha, fmtFechaHora, hoyTijuana } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoListo, IcoPrestamos, IcoTaller, IcoUbicacion,
  IcoUnidad, Modal, Regla, Spinner, Tabla, useApi, useToast,
} from '../../ui/index.js'

export default function Chofer({ usuario }) {
  return (
    <Routes>
      <Route path="/" element={<MiUnidad usuario={usuario} />} />
      <Route path="/prestamos" element={<Prestamos />} />
      <Route path="/taller" element={<Taller />} />
      <Route path="/averias" element={<Averias />} />
    </Routes>
  )
}

/* ------------------------------------------------ CU-CHO-01/02/03/14/15 ---- */
function MiUnidad({ usuario }) {
  const toast = useToast()
  const unidad = useApi(() => api.get('/chofer/mi-unidad'))
  const mtto = useApi(() => api.get('/chofer/mantenimientos'))
  const jornada = useApi(() => api.get('/chofer/jornada/actual'))
  const [checklist, setChecklist] = useState(false)

  const accion = async (fn, ok) => {
    try { await fn(); toast(ok); jornada.recargar(); unidad.recargar() }
    catch (e) { toast(e.message, 'err') }
  }

  if (unidad.cargando) return <Spinner />
  if (!unidad.data) {
    return <Empty icono={IcoUnidad}>No tienes una unidad asignada. Habla con tu supervisor.</Empty>
  }

  const u = unidad.data
  const vencidos = (mtto.data || []).filter((x) => x.vencido)
  const j = jornada.data

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Hola, {usuario.nombre}</h1>

      {u.es_prestada && (
        <Aviso tipo="warn">
          Traes una unidad <strong>prestada</strong>. Mientras la tengas, tú respondes por su
          estado técnico y por su mantenimiento (RN-01).
        </Aviso>
      )}
      {vencidos.length > 0 && (
        <Aviso tipo="err">
          Tienes {vencidos.length} mantenimiento(s) vencido(s). Si no ingresas la unidad al
          taller, el sistema genera un aviso de incumplimiento a tu nombre (RN-05), y tu
          supervisor puede convertirlo en una amonestación.
        </Aviso>
      )}

      <Card title={`Unidad ${u.num_economico}`}
            actions={<EstadoBadge estado={u.estado} />}>
        <div className="list-item">
          <div className="grow">
            <div className="t">{u.marca} {u.modelo} {u.anio}</div>
            <div className="s">Placas {u.placas} · {u.tipo} · {u.km_actual?.toLocaleString('es-MX')} km</div>
          </div>
        </div>
        <div className="list-item">
          <div className="grow">
            <div className="s">Titular</div>
            <div className="t">{u.titular || '—'}</div>
          </div>
          <div className="grow">
            <div className="s">Responsable hoy</div>
            <div className="t">{u.poseedor || '—'}</div>
          </div>
        </div>
        {u.taller_actual && <p className="sub">En taller: {u.taller_actual}</p>}
      </Card>

      <Card title="Jornada">
        {j?.abierta ? (
          <>
            <p className="sub">Abierta desde {fmtFechaHora(j.hora_inicio)}</p>
            <button className="btn block"
                    onClick={() => accion(() => api.post('/chofer/jornada/cerrar'), 'Jornada cerrada')}>
              Cerrar jornada
            </button>
          </>
        ) : (
          <>
            <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}>
              <input type="checkbox" style={{ width: 20, height: 20 }} checked={checklist}
                     onChange={(e) => setChecklist(e.target.checked)} />
              <span>Realicé el checklist pre-operacional</span>
            </label>
            <button className="btn primary block" disabled={!checklist}
                    onClick={() => accion(
                      () => api.post('/chofer/jornada/iniciar', undefined,
                                     { checklist_ok: true }), 'Jornada iniciada')}>
              Iniciar jornada
            </button>
            <Regla>CU-CHO-03 «include» CU-CHO-04: no se abre jornada sin checklist.</Regla>
          </>
        )}
      </Card>

      <Card title="Mantenimiento preventivo">
        {mtto.cargando ? <Spinner /> : (
          <Tabla
            vacio="Sin mantenimientos programados"
            columnas={[
              { k: 'plan', t: 'Plan' },
              { k: 'fecha_limite', t: 'Límite', r: (f) => fmtFecha(f.fecha_limite) },
              { k: 'dias_restantes', t: 'Días', num: true,
                r: (f) => (
                  <Badge tono={f.dias_restantes < 0 ? 'danger' : f.dias_restantes < 15 ? 'warn' : 'ok'}>
                    {f.dias_restantes < 0 ? `${-f.dias_restantes} vencido` : f.dias_restantes}
                  </Badge>
                ) },
              { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            ]}
            filas={mtto.data || []} />
        )}
      </Card>

    </>
  )
}

/* La tarjeta «Mis penalizaciones» y su modal vivían aquí. Se quitaron el
 * 2026-09-17: leían de `Penalizacion`, la tabla de la v1.1 que la v2.0
 * reemplazó y que hoy tiene CERO filas en producción — así que la tarjeta
 * siempre decía «sin penalizaciones» y no probaba nada.
 *
 * Lo que sí existe está en la pestaña Taller: «Mis amonestaciones», que sale de
 * RN-14 y sí tiene su propio camino de inconformidad. Dejar las dos era tener
 * dos palabras y dos pantallas para lo mismo, con una de ellas siempre vacía.
 */

/* -------------------------------------------------- CU-CHO-07/08/09 -------- */
function Prestamos() {
  const toast = useToast()
  const prestamos = useApi(() => api.get('/chofer/prestamos'))
  const unidad = useApi(() => api.get('/chofer/mi-unidad'))
  const [abrir, setAbrir] = useState(false)

  const accion = async (fn, ok) => {
    try { await fn(); toast(ok); prestamos.recargar(); unidad.recargar() }
    catch (e) { toast(e.message, 'err') }
  }

  return (
    <>
      <div className="card-head">
        <h1>Préstamos</h1>
        <button className="btn primary" disabled={!unidad.data} onClick={() => setAbrir(true)}>
          Prestar unidad
        </button>
      </div>

      <Aviso tipo="info">
        La responsabilidad de la unidad cambia de manos <strong>cuando el otro chofer
        acepta</strong>, no cuando tú la ofreces (RN-01).
      </Aviso>

      {prestamos.cargando ? <Spinner /> : (
        <Card>
          {(prestamos.data || []).length === 0 ? <Empty icono={IcoPrestamos}>Sin préstamos</Empty> : (
            (prestamos.data || []).map((p) => (
              <div className="list-item" key={p.id}>
                <div className="grow">
                  <div className="t">{p.unidad} · {p.motivo}</div>
                  <div className="s">{p.chofer_presta} → {p.chofer_recibe}</div>
                  <div className="s">Hasta {fmtFecha(p.fecha_fin_prevista)}</div>
                </div>
                <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
                  <EstadoBadge estado={p.estado} />
                  {p.estado === 'solicitado' && (
                    <div className="btn-row">
                      <button className="btn sm ok" onClick={() => accion(
                        () => api.post(`/chofer/prestamos/${p.id}/aceptar`),
                        'Aceptaste la unidad: ahora tú respondes por ella')}>Aceptar</button>
                      <button className="btn sm danger" onClick={() => accion(
                        () => api.post(`/chofer/prestamos/${p.id}/rechazar`, undefined,
                                       { motivo: 'No puedo recibirla' }), 'Préstamo rechazado')}>
                        Rechazar
                      </button>
                    </div>
                  )}
                  {p.estado === 'activo' && (
                    <button className="btn sm" onClick={() => accion(
                      () => api.post(`/chofer/prestamos/${p.id}/devolver`),
                      'Unidad devuelta')}>Devolver</button>
                  )}
                </div>
              </div>
            ))
          )}
        </Card>
      )}

      {abrir && (
        <ModalPrestar unidad={unidad.data} onCerrar={() => setAbrir(false)}
                      onListo={() => { setAbrir(false); prestamos.recargar() }} />
      )}
    </>
  )
}

function ModalPrestar({ unidad, onCerrar, onListo }) {
  const toast = useToast()
  const companeros = useApi(() => api.get('/chofer/companeros'))
  const [form, setForm] = useState({
    chofer_recibe_id: '', motivo: 'vacaciones', fecha_fin_prevista: '',
  })

  const enviar = async (e) => {
    e.preventDefault()
    try {
      await api.post('/chofer/prestamos', {
        unidad_id: unidad.id,
        chofer_recibe_id: Number(form.chofer_recibe_id),
        motivo: form.motivo,
        fecha_fin_prevista: form.fecha_fin_prevista,
      })
      toast('Préstamo enviado. Falta que lo acepten.')
      onListo()
    } catch (err) { toast(err.message, 'err') }
  }

  return (
    <Modal titulo={`Prestar ${unidad.num_economico}`} onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="field">
          <label>¿A quién?</label>
          <select required value={form.chofer_recibe_id}
                  onChange={(e) => setForm({ ...form, chofer_recibe_id: e.target.value })}>
            <option value="">Selecciona un chofer…</option>
            {(companeros.data || []).map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Motivo</label>
          <select value={form.motivo} onChange={(e) => setForm({ ...form, motivo: e.target.value })}>
            <option value="vacaciones">Vacaciones</option>
            <option value="incapacidad">Incapacidad</option>
            <option value="apoyo">Apoyo</option>
            <option value="otro">Otro</option>
          </select>
        </div>
        <div className="field">
          <label>Regresa el</label>
          {/* No se puede devolver una unidad en el pasado: el minimo es hoy. */}
          <input type="date" required min={hoyTijuana()} value={form.fecha_fin_prevista}
                 onChange={(e) => setForm({ ...form, fecha_fin_prevista: e.target.value })} />
        </div>
        <button className="btn primary block">Enviar préstamo</button>
        <Regla>
          Solo aparecen choferes con licencia vigente. Al vencer la fecha, la responsabilidad
          regresa sola al titular (RN-03).
        </Regla>
      </form>
    </Modal>
  )
}

/* ---------------------------------------------------- CU-CHO-05/06 -------- */
/* ----------------------------------------------------------- CU-CHO-07 ----- */
/** Las citas que el taller le agendó, y el botón de confirmar.
 *
 * Es la mitad del mecanismo nuevo que le toca al chofer. Antes él tenía que
 * SOLICITAR el ingreso preventivo, y como el taller le cuesta comisiones podía
 * "olvidarlo". Ahora Víctor agenda y él solo confirma.
 */
function MisCitas() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/chofer/citas'))
  const [ocupado, setOcupado] = useState(false)

  if (cargando) return null
  const citas = data || []
  if (!citas.length) return null

  const confirmar = async (c) => {
    setOcupado(true)
    try {
      await api.post(`/chofer/citas/${c.id}/confirmar`)
      toast('Confirmaste tu cita. Te esperan ese día.')
      recargar()
    } catch (e) { toast(e.message, 'err') } finally { setOcupado(false) }
  }

  return (
    <Card title={`Tus citas de taller (${citas.length})`}>
      <Aviso tipo="info">
        Confirma que te vas a presentar. <strong>Solo se cuenta como incumplimiento si faltas a
        una cita que confirmaste</strong>, así que confirmar te protege a ti también.
      </Aviso>
      {citas.map((c) => (
        <div className="list-item" key={c.id}>
          <div className="grow">
            <div className="t">{fmtFecha(c.fecha_cita)} · {c.servicio}</div>
            <div className="s">{c.unidad} en {c.taller}</div>
            <div className="s">
              La unidad se queda entre {c.duracion_rango.tipico} y {c.duracion_rango.pesimista} día(s)
            </div>
            {c.veces_reprogramada > 0 && (
              <div className="s">El taller la movió {c.veces_reprogramada} vez/veces</div>
            )}
          </div>
          <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
            {/* NO se enseña `estado` aquí. Para el sistema "confirmada" quiere
                decir que el TALLER confirmó, pero al chofer le leía como "ya
                quedó" al lado de un botón que le pedía confirmar. El estado
                interno no es asunto suyo: lo que necesita saber es si le toca
                hacer algo. */}
            {c.confirmada_por_chofer
              ? <Badge tono="ok"><IcoListo size={13} className="ico-inline" aria-hidden="true" /> Ya confirmaste</Badge>
              : (
                <>
                  <Badge tono="warn">Pendiente</Badge>
                  <button className="btn sm primary" disabled={ocupado}
                          onClick={() => confirmar(c)}>Confirmar</button>
                </>
              )}
          </div>
        </div>
      ))}
    </Card>
  )
}

function Taller() {
  const toast = useToast()
  const solicitudes = useApi(() => api.get('/chofer/solicitudes'))
  const unidad = useApi(() => api.get('/chofer/mi-unidad'))
  const talleres = useApi(() => api.get('/chofer/talleres'))
  const [form, setForm] = useState({ taller_id: '', tipo: 'preventivo', urgencia: 'media', descripcion_falla: '' })

  const enviar = async (e) => {
    e.preventDefault()
    try {
      await api.post('/chofer/solicitudes', {
        unidad_id: unidad.data.id, taller_id: Number(form.taller_id),
        tipo: form.tipo, urgencia: form.urgencia, descripcion_falla: form.descripcion_falla,
      })
      toast('Solicitud enviada al administrador')
      setForm({ ...form, descripcion_falla: '' })
      solicitudes.recargar()
    } catch (err) { toast(err.message, 'err') }
  }

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Ingreso a taller</h1>

      <MisCitas />

      <Card title="Nueva solicitud"
            sub="Para una falla. El mantenimiento preventivo ya no se solicita: te lo agenda el taller.">
        <form onSubmit={enviar}>
          <div className="field">
            <label>Taller</label>
            <select required value={form.taller_id}
                    onChange={(e) => setForm({ ...form, taller_id: e.target.value })}>
              <option value="">Selecciona…</option>
              {(talleres.data || []).map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Tipo</label>
            <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
              <option value="preventivo">Preventivo (mantenimiento)</option>
              <option value="correctivo">Correctivo (falla)</option>
              <option value="verificacion">Verificación</option>
            </select>
          </div>
          <div className="field">
            <label>Urgencia</label>
            <select value={form.urgencia}
                    onChange={(e) => setForm({ ...form, urgencia: e.target.value })}>
              <option value="baja">Baja</option><option value="media">Media</option>
              <option value="alta">Alta</option><option value="critica">Crítica</option>
            </select>
          </div>
          <div className="field">
            <label>¿Qué tiene la unidad?</label>
            <textarea required value={form.descripcion_falla}
                      onChange={(e) => setForm({ ...form, descripcion_falla: e.target.value })} />
          </div>
          <button className="btn primary block" disabled={!unidad.data}>Enviar solicitud</button>
        </form>
      </Card>

      <Card title="Mis solicitudes">
        {solicitudes.cargando ? <Spinner /> : (
          (solicitudes.data || []).length === 0 ? <Empty icono={IcoTaller}>Sin solicitudes</Empty> : (
            (solicitudes.data || []).map((s) => (
              <div className="list-item" key={s.id}>
                <div className="grow">
                  <div className="t">{s.unidad} · {s.taller}</div>
                  <div className="s">{s.descripcion_falla}</div>
                  <div className="s">{fmtFechaHora(s.fecha_solicitud)}</div>
                  {s.motivo_rechazo && (
                    <div className="s" style={{ color: 'var(--danger)' }}>
                      Motivo: {s.motivo_rechazo}
                    </div>
                  )}
                </div>
                <EstadoBadge estado={s.estado} />
              </div>
            ))
          )
        )}
      </Card>

      <MisAmonestaciones />
    </>
  )
}

/* --------------------------------------------------------------- CU-CHO-17 -- */
/** RF-CHO-15 y 16: el chofer ve sus amonestaciones y puede inconformarse.
 *
 *  Se entera por el sistema, no por el pasillo. Y si va a su expediente, tiene
 *  que haber a donde reclamar.
 */
function MisAmonestaciones() {
  const { data, cargando, recargar } = useApi(() => api.get('/chofer/amonestaciones'))
  const [reclamar, setReclamar] = useState(null)
  if (cargando) return null
  const d = data || {}
  const lista = d.amonestaciones || []
  if (!lista.length) return null

  return (
    <>
      <Card title="Mis amonestaciones"
            sub={d.vigentes + ' vigente(s)' + (d.anuladas ? ', ' + d.anuladas + ' sin efecto' : '')}>
        {lista.map((a) => (
          <div className="list-item" key={a.id}>
            <div className="grow">
              <div className="t">{a.consecutivo}ª amonestación · unidad {a.unidad}</div>
              <div className="s">{a.motivo}</div>
              <div className="s">Firmó {a.emitida_por} · {fmtFecha(a.fecha_emision)}</div>
              {a.inconformidad && (
                <div className="s"><strong>Te inconformaste:</strong> {a.inconformidad}</div>
              )}
              {a.resolucion && (
                <div className="s"><strong>Resolución:</strong> {a.resolucion}</div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <EstadoBadge estado={a.estado} />
              {a.estado === 'emitida' && (
                <button className="btn sm" onClick={() => setReclamar(a)}>No estoy de acuerdo</button>
              )}
            </div>
          </div>
        ))}
        <Regla>
          Una amonestación es <strong>administrativa</strong>: va a tu expediente y no descuenta
          nada de tu pago. Solo se emite si faltaste a una cita <strong>confirmada</strong>; si el
          taller nunca te dio cita, no procede.
        </Regla>
      </Card>

      {reclamar && (
        <ModalInconformidadAmonestacion a={reclamar} onCerrar={() => setReclamar(null)}
                                        onListo={() => { setReclamar(null); recargar() }} />
      )}
    </>
  )
}

function ModalInconformidadAmonestacion({ a, onCerrar, onListo }) {
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  async function enviar() {
    if (!texto.trim()) { setError('Escribe por qué no estás de acuerdo.'); return }
    setEnviando(true); setError(null)
    try {
      await api.post('/chofer/amonestaciones/' + a.id + '/inconformidad?texto='
                     + encodeURIComponent(texto))
      onListo()
    } catch (e) { setError(String(e.message || e)); setEnviando(false) }
  }

  return (
    <Modal titulo={'Inconformidad · ' + a.consecutivo + 'ª amonestación'} onClose={onCerrar}>
      {error && <Aviso tipo="err">{error}</Aviso>}
      <p>{a.motivo}</p>
      <label className="campo">
        <span>¿Por qué no estás de acuerdo?</span>
        <textarea rows={4} value={texto} onChange={(e) => setTexto(e.target.value)}
                  placeholder="Lo que pasó ese día" />
      </label>
      <Regla>
        Lo va a leer quien la firmó. Puede sostenerla o dejarla sin efecto, y en los dos casos
        queda por escrito en tu expediente.
      </Regla>
      <div className="acciones">
        <button className="btn" onClick={onCerrar}>Cancelar</button>
        <button className="btn primario" onClick={enviar} disabled={enviando}>
          {enviando ? 'Enviando...' : 'Enviar inconformidad'}
        </button>
      </div>
    </Modal>
  )
}

/* ------------------------------------------- CU-CHO-10/11/12/13 ------------ */
function Averias() {
  const toast = useToast()
  const averias = useApi(() => api.get('/chofer/averias'))
  const unidad = useApi(() => api.get('/chofer/mi-unidad'))
  const [abrir, setAbrir] = useState(false)
  const [peritaje, setPeritaje] = useState(null)

  const arrastre = async (a) => {
    try {
      const r = await api.post(`/chofer/averias/${a.id}/arrastre`)
      toast(r.mensaje)
      averias.recargar()
    } catch (e) { toast(e.message, 'err') }
  }

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Averías</h1>

      {/* El botón de pánico manda la alerta con dos toques. El formulario largo
          sigue existiendo debajo para cuando NO hay prisa --una falla que se
          detecta en el patio-- y ahí sí conviene llenarlo completo. */}
      <BotonEmergencia unidad={unidad.data}
                       onListo={() => averias.recargar()} />

      {averias.cargando ? <Spinner /> : (
        (averias.data || []).length === 0 ? <Empty icono={IcoListo}>Sin averías reportadas</Empty> : (
          (averias.data || []).map((a) => (
            <Card key={a.id} title={`${a.folio} · ${a.unidad}`}
                  actions={<EstadoBadge estado={a.estado} />}>
              <p className="sub">{a.descripcion_falla}</p>
              <p className="sub">{fmtFechaHora(a.fecha_hora)}</p>

              {a.en_vialidad_publica && !a.tiene_peritaje && (
                <Aviso tipo="err">
                  Estás en vialidad pública. <strong>Primero llama a los peritos</strong> y
                  registra el folio. Hasta entonces no se habilita el arrastre (RN-04).
                </Aviso>
              )}
              {a.tiene_peritaje && (
                <Aviso tipo="ok">Peritos avisados · folio {a.folio_peritos}</Aviso>
              )}
              {!a.latitud && (
                <Aviso tipo="warn">
                  Esta alerta salió <strong>sin ubicación</strong>. Tu supervisor ya lo sabe,
                  pero si tienes señal ahora, vuelve a entrar para que se complete sola.
                </Aviso>
              )}

              <FotosAveria averia={a} onCambio={() => averias.recargar()} />

              <div className="btn-row">
                {a.en_vialidad_publica && !a.tiene_peritaje && (
                  <button className="btn primary" onClick={() => setPeritaje(a)}>
                    Registrar aviso a peritos
                  </button>
                )}
                {!a.arrastre_id && (
                  <button className="btn" disabled={!a.puede_solicitar_arrastre}
                          onClick={() => arrastre(a)}>
                    Solicitar arrastre
                  </button>
                )}
                {a.arrastre_id && <Badge tono="info">Arrastre {a.arrastre_estado}</Badge>}
              </div>
            </Card>
          ))
        )
      )}

      <div className="btn-row" style={{ marginTop: 10 }}>
        <button className="btn" disabled={!unidad.data} onClick={() => setAbrir(true)}>
          Reportar con formulario completo
        </button>
      </div>
      <Regla>
        El botón rojo es para cuando estás varado. El formulario completo sirve cuando hay
        tiempo: pide referencia del lugar y si hay terceros involucrados.
      </Regla>

      {abrir && (
        <ModalAveria unidad={unidad.data} onCerrar={() => setAbrir(false)}
                     onListo={() => { setAbrir(false); averias.recargar() }} />
      )}
      {peritaje && (
        <ModalPeritaje averia={peritaje} onCerrar={() => setPeritaje(null)}
                       onListo={() => { setPeritaje(null); averias.recargar() }} />
      )}
    </>
  )
}

function ModalAveria({ unidad, onCerrar, onListo }) {
  const toast = useToast()
  const [form, setForm] = useState({
    descripcion_falla: '', en_vialidad_publica: false, hay_terceros_involucrados: false,
    direccion_referencia: '',
  })
  const [gps, setGps] = useState(null)
  const [buscando, setBuscando] = useState(false)
  const [falloGps, setFalloGps] = useState(false)

  const ubicar = () => {
    setBuscando(true)
    if (!navigator.geolocation) {
      // Antes aquí se ponían las coordenadas de Álamos. Eso no es un valor por
      // omisión: es una mentira que nadie puede detectar después.
      setGps(null); setFalloGps(true); setBuscando(false)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (p) => { setGps({ lat: p.coords.latitude, lng: p.coords.longitude }); setBuscando(false) },
      () => { setGps(null); setFalloGps(true); setBuscando(false) },
      { timeout: 8000 }
    )
  }

  const enviar = async (e) => {
    e.preventDefault()
    try {
      await api.post('/chofer/averias', {
        unidad_id: unidad.id,
        latitud: gps ? gps.lat : null, longitud: gps ? gps.lng : null,
        descripcion_falla: form.descripcion_falla,
        direccion_referencia: form.direccion_referencia,
        en_vialidad_publica: form.en_vialidad_publica,
        hay_terceros_involucrados: form.hay_terceros_involucrados,
        requiere_arrastre: true,
      })
      toast('Avería reportada. Tu supervisor ya la ve.')
      onListo()
    } catch (err) { toast(err.message, 'err') }
  }

  return (
    <Modal titulo={`Reportar avería · ${unidad.num_economico}`} onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="field">
          <label>¿Qué pasó?</label>
          <textarea required value={form.descripcion_falla}
                    onChange={(e) => setForm({ ...form, descripcion_falla: e.target.value })} />
        </div>
        <div className="field">
          <label>Referencia del lugar</label>
          <input value={form.direccion_referencia} placeholder="Ej. Blvd. Díaz Ordaz y Ferrocarril"
                 onChange={(e) => setForm({ ...form, direccion_referencia: e.target.value })} />
        </div>
        <div className="field">
          <button type="button" className="btn block" onClick={ubicar} disabled={buscando}>
            {buscando ? 'Ubicando…' : gps ? 'Ubicación lista' : 'Compartir mi ubicación'}
          </button>
          {gps && (
            <p className="sub" style={{ marginTop: 6 }}>
              {gps.lat.toFixed(5)}, {gps.lng.toFixed(5)}
            </p>
          )}
          {falloGps && (
            <Aviso tipo="warn">
              El navegador no dio la ubicación. Se manda sin punto y tu supervisor recibe el
              aviso de que llegó así. Si entraste por una dirección sin candado
              (<code>http://</code>), el GPS está bloqueado por el navegador, no por la app.
            </Aviso>
          )}
        </div>
        <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 }}>
          <input type="checkbox" style={{ width: 20, height: 20 }}
                 checked={form.en_vialidad_publica}
                 onChange={(e) => setForm({ ...form, en_vialidad_publica: e.target.checked })} />
          <span>Estoy en vialidad pública</span>
        </label>
        <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}>
          <input type="checkbox" style={{ width: 20, height: 20 }}
                 checked={form.hay_terceros_involucrados}
                 onChange={(e) => setForm({ ...form, hay_terceros_involucrados: e.target.checked })} />
          <span>Hay terceros involucrados</span>
        </label>
        {form.en_vialidad_publica && (
          <Aviso tipo="warn">
            Al reportar en vialidad pública tendrás que registrar el folio de peritos antes de
            pedir el arrastre.
          </Aviso>
        )}
        <button className="btn danger block">Reportar avería</button>
      </form>
    </Modal>
  )
}

function ModalPeritaje({ averia, onCerrar, onListo }) {
  const toast = useToast()
  const [form, setForm] = useState({ folio_peritos: '', aseguradora: '', nombre_perito: '' })
  const enviar = async (e) => {
    e.preventDefault()
    try {
      await api.post(`/chofer/averias/${averia.id}/peritaje`, form)
      toast('Peritaje registrado. Ya puedes pedir el arrastre.')
      onListo()
    } catch (err) { toast(err.message, 'err') }
  }
  return (
    <Modal titulo="Aviso a peritos" onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="field">
          <label>Folio que dieron los peritos *</label>
          <input required value={form.folio_peritos}
                 onChange={(e) => setForm({ ...form, folio_peritos: e.target.value })} />
        </div>
        <div className="field">
          <label>Aseguradora</label>
          <input value={form.aseguradora}
                 onChange={(e) => setForm({ ...form, aseguradora: e.target.value })} />
        </div>
        <div className="field">
          <label>Nombre del perito</label>
          <input value={form.nombre_perito}
                 onChange={(e) => setForm({ ...form, nombre_perito: e.target.value })} />
        </div>
        <button className="btn primary block">Registrar</button>
        <Regla>RN-04: sin este folio el sistema no habilita el arrastre.</Regla>
      </form>
    </Modal>
  )
}
