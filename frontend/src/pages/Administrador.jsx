import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHora, fmtMoneda } from '../api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, Modal, Regla, Spinner, Tabla, useApi, useToast,
} from '../components/ui.jsx'

export default function Administrador() {
  return (
    <Routes>
      <Route path="/" element={<Solicitudes />} />
      <Route path="/plano" element={<Plano />} />
      <Route path="/ordenes" element={<Ordenes />} />
      <Route path="/presupuestos" element={<Presupuestos />} />
      <Route path="/hoja" element={<HojaTrabajo />} />
    </Routes>
  )
}

/* -------------------------------------------------- CU-ADM-01/02 ----------- */
function Solicitudes() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/admin/solicitudes'))
  const [resolver, setResolver] = useState(null)

  if (cargando) return <Spinner />
  const pendientes = (data || []).filter((s) => ['pendiente', 'en_cola'].includes(s.estado))

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Solicitudes de ingreso</h1>
      <Aviso tipo="info">
        No se acepta un ingreso sin espacio libre <strong>compatible con el tipo de unidad</strong>:
        una pipa no cabe en un espacio de reparto (RN-06).
      </Aviso>

      <Card title={`Pendientes (${pendientes.length})`}>
        {pendientes.length === 0 ? <Empty icono="📥">Bandeja vacía</Empty> : (
          pendientes.map((s) => (
            <div className="list-item" key={s.id}>
              <div className="grow">
                <div className="t">
                  {s.unidad} <Badge tono={s.urgencia === 'critica' || s.urgencia === 'alta'
                    ? 'danger' : ''}>{s.urgencia}</Badge>
                </div>
                <div className="s">{s.chofer} · {s.tipo}</div>
                <div className="s">{s.descripcion_falla}</div>
                <div className="s">{fmtFechaHora(s.fecha_solicitud)}</div>
                <div className="s">
                  {s.espacios_libres_compatibles > 0
                    ? <span style={{ color: 'var(--ok)' }}>
                        {s.espacios_libres_compatibles} espacio(s) compatible(s) libre(s)</span>
                    : <span style={{ color: 'var(--danger)' }}>Sin espacio compatible</span>}
                </div>
              </div>
              <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
                <EstadoBadge estado={s.estado} />
                <button className="btn sm primary" onClick={() => setResolver(s)}>Atender</button>
              </div>
            </div>
          ))
        )}
      </Card>

      <Card title="Historial">
        <Tabla
          vacio="Sin historial"
          columnas={[
            { k: 'unidad', t: 'Unidad' },
            { k: 'chofer', t: 'Chofer' },
            { k: 'tipo', t: 'Tipo' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            { k: 'fecha_solicitud', t: 'Fecha', r: (f) => fmtFecha(f.fecha_solicitud) },
          ]}
          filas={(data || []).filter((s) => !['pendiente', 'en_cola'].includes(s.estado))} />
      </Card>

      {resolver && (
        <ModalResolver solicitud={resolver} onCerrar={() => setResolver(null)}
                       onListo={() => { setResolver(null); recargar() }} />
      )}
    </>
  )
}

function ModalResolver({ solicitud, onCerrar, onListo }) {
  const toast = useToast()
  const [motivo, setMotivo] = useState('')
  const hayEspacio = solicitud.espacios_libres_compatibles > 0

  const enviar = async (payload, ok) => {
    try {
      await api.post(`/admin/solicitudes/${solicitud.id}/resolver`, payload)
      toast(ok); onListo()
    } catch (e) { toast(e.message, 'err') }
  }

  return (
    <Modal titulo={`Solicitud · ${solicitud.unidad}`} onClose={onCerrar}>
      <p className="sub">{solicitud.chofer} · {solicitud.tipo} · urgencia {solicitud.urgencia}</p>
      <p>{solicitud.descripcion_falla}</p>

      {hayEspacio ? (
        <Aviso tipo="ok">
          {solicitud.espacios_libres_compatibles} espacio(s) compatible(s) disponible(s).
        </Aviso>
      ) : (
        <Aviso tipo="err">
          No hay espacio compatible libre. Solo puedes dejarla en cola o rechazarla con motivo
          (RN-06).
        </Aviso>
      )}

      <button className="btn primary block" disabled={!hayEspacio}
              onClick={() => enviar({ aceptar: true }, 'Ingreso aceptado y espacio asignado')}>
        Aceptar y asignar espacio
      </button>

      <div style={{ height: 10 }} />
      <button className="btn block"
              onClick={() => enviar({ aceptar: false, dejar_en_cola: true }, 'Solicitud en cola')}>
        Dejar en cola
      </button>

      <div className="field" style={{ marginTop: 14 }}>
        <label>Motivo de rechazo</label>
        <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </div>
      <button className="btn danger block" disabled={!motivo.trim()}
              onClick={() => enviar({ aceptar: false, motivo_rechazo: motivo },
                                    'Solicitud rechazada')}>
        Rechazar
      </button>
    </Modal>
  )
}

/* ------------------------------------------------- CU-ADM-03/04 ------------ */
function Plano() {
  const { data, cargando, recargar } = useApi(() => api.get('/admin/taller/1'))
  const toast = useToast()

  const retirar = async (e) => {
    if (!e.unidad) return
    try {
      await api.post(`/admin/espacios/${e.id}/retirar`)
      toast(`Unidad ${e.unidad} retirada`); recargar()
    } catch (err) { toast(err.message, 'err') }
  }

  if (cargando) return <Spinner />
  const t = data
  return (
    <>
      <h1 style={{ marginBottom: 4 }}>{t.nombre}</h1>
      <p className="sub">{t.direccion}</p>

      <div className="grid g3">
        <div className="card kpi"><div className="val">{t.total_operativos}</div>
          <div className="lbl">Espacios operativos</div></div>
        <div className="card kpi alert"><div className="val">{t.ocupados}</div>
          <div className="lbl">Ocupados</div></div>
        <div className="card kpi ok"><div className="val">{t.libres}</div>
          <div className="lbl">Libres</div></div>
      </div>

      <Card title="Plano del taller"
            sub="Toca un espacio ocupado para retirar la unidad. Las zonas atenuadas no cuentan para la ocupación.">
        {t.zonas.map((z) => (
          <div className="zona" key={z.id}>
            <div className="zona-head">
              <span>{z.nombre}</span>
              {!z.cuenta_para_ocupacion && <Badge>no cuenta</Badge>}
              <span style={{ color: 'var(--muted)', fontWeight: 500 }}>
                {z.espacios.filter((e) => e.estado === 'ocupado').length}/{z.espacios.length}
              </span>
            </div>
            <div className="espacios">
              {z.espacios.map((e) => (
                <button key={e.id} type="button"
                        className={`espacio ${e.estado} ${z.cuenta_para_ocupacion ? '' : 'no-cuenta'}`}
                        title={e.unidad
                          ? `${e.unidad} · ${e.dias_ocupado} días`
                          : `Libre · admite ${e.tipo_permitido || 'cualquier tipo'}`}
                        onClick={() => retirar(e)}>
                  <span>{e.numero}</span>
                  {e.unidad && <small>{e.unidad}</small>}
                </button>
              ))}
              {z.espacios.length === 0 && <span className="sub">Zona sin espacios</span>}
            </div>
          </div>
        ))}
        <Regla>
          La numeración se repite entre zonas (hay un “1” en REPARTO, otro en ELECTRICOS y otro en
          PATIO): la unicidad es por zona, no global.
        </Regla>
      </Card>
    </>
  )
}

/* ------------------------------- CU-ADM-05/06/11/14/10 (captura v1.1) ------ */
function Ordenes() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/admin/ordenes'))
  const tecnicos = useApi(() => api.get('/admin/tecnicos'))
  const [detalle, setDetalle] = useState(null)
  const [salida, setSalida] = useState(null)

  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Órdenes de servicio</h1>
      {(data || []).length === 0 ? <Empty icono="🔧">Sin órdenes abiertas</Empty> : (
        (data || []).map((o) => (
          <Card key={o.id} title={`${o.folio} · ${o.unidad}`}
                actions={<EstadoBadge estado={o.estado} />}>
            <p className="sub">
              {o.espacio || 'sin espacio'} · {o.dias_en_taller} días en taller · entró{' '}
              {fmtFecha(o.fecha_entrada)}
            </p>

            <h3 style={{ marginBottom: 8 }}>Cola de especialistas</h3>
            {o.asignaciones.length === 0 ? (
              <p className="sub">Nadie asignado todavía.</p>
            ) : o.asignaciones.map((a) => (
              <div className="list-item" key={a.id}>
                <Badge>{a.orden_en_cola}</Badge>
                <div className="grow">
                  <div className="t">{a.tecnico}</div>
                  <div className="s">{a.especialidad}</div>
                  {a.diagnostico && <div className="s">📝 {a.diagnostico}</div>}
                  {a.capturado_por && (
                    <div className="s" style={{ color: 'var(--muted)' }}>
                      Capturado por {a.capturado_por} · {fmtFechaHora(a.fecha_captura)}
                    </div>
                  )}
                </div>
                <EstadoBadge estado={a.estado} />
              </div>
            ))}

            <div className="btn-row" style={{ marginTop: 12 }}>
              <button className="btn sm" onClick={() => setDetalle(o)}>Gestionar cola</button>
              <button className="btn sm ok" onClick={() => setSalida(o)}>Emitir salida</button>
            </div>
          </Card>
        ))
      )}

      {detalle && (
        <ModalCola orden={detalle} tecnicos={tecnicos.data || []}
                   onCerrar={() => setDetalle(null)}
                   onCambio={() => { recargar() }} />
      )}
      {salida && (
        <ModalSalida orden={salida} onCerrar={() => setSalida(null)}
                     onListo={() => { setSalida(null); recargar(); toast('Salida emitida') }} />
      )}
    </>
  )
}

function ModalCola({ orden, tecnicos, onCerrar, onCambio }) {
  const toast = useToast()
  const { data, recargar } = useApi(() => api.get(`/admin/ordenes/${orden.id}`))
  const [tid, setTid] = useState('')
  const [diag, setDiag] = useState({})

  const refrescar = () => { recargar(); onCambio() }
  const correr = async (fn, ok) => {
    try { await fn(); toast(ok); refrescar() } catch (e) { toast(e.message, 'err') }
  }

  const o = data || orden
  return (
    <Modal titulo={`Cola · ${o.folio}`} onClose={onCerrar}>
      <div className="field">
        <label>Agregar especialista a la fila</label>
        <select value={tid} onChange={(e) => setTid(e.target.value)}>
          <option value="">Selecciona…</option>
          {tecnicos.map((t) => (
            <option key={t.id} value={t.id}>{t.nombre} · {t.especialidad}</option>
          ))}
        </select>
      </div>
      <button className="btn primary block" disabled={!tid}
              onClick={() => correr(
                () => api.post(`/admin/ordenes/${o.id}/asignar`, { tecnico_id: Number(tid) }),
                'Especialista agregado a la cola')}>
        Agregar a la cola
      </button>

      <div style={{ height: 16 }} />
      {o.asignaciones.map((a) => (
        <div className="card" key={a.id} style={{ background: 'var(--surface-2)' }}>
          <div className="card-head">
            <h3>{a.orden_en_cola}. {a.tecnico}</h3>
            <EstadoBadge estado={a.estado} />
          </div>
          <div className="btn-row" style={{ marginBottom: 10 }}>
            <button className="btn sm" onClick={() => correr(
              () => api.post(`/admin/asignaciones/${a.id}/mover`, undefined, { direccion: 'arriba' }),
              'Cola reordenada')}>↑</button>
            <button className="btn sm" onClick={() => correr(
              () => api.post(`/admin/asignaciones/${a.id}/mover`, undefined, { direccion: 'abajo' }),
              'Cola reordenada')}>↓</button>
            <button className="btn sm" onClick={() => correr(
              () => api.post(`/admin/asignaciones/${a.id}/avance`, { estado: 'en_proceso' }),
              'Trabajo iniciado')}>Iniciar</button>
            <button className="btn sm ok" onClick={() => correr(
              () => api.post(`/admin/asignaciones/${a.id}/avance`,
                             { estado: 'terminada', trabajo_realizado: a.diagnostico || 'Terminado' }),
              'Trabajo terminado')}>Terminar</button>
          </div>
          <div className="field" style={{ marginBottom: 6 }}>
            <label>Diagnóstico que entregó el mecánico</label>
            <textarea value={diag[a.id] ?? a.diagnostico ?? ''}
                      onChange={(e) => setDiag({ ...diag, [a.id]: e.target.value })} />
          </div>
          <button className="btn sm block" onClick={() => correr(
            () => api.post(`/admin/asignaciones/${a.id}/diagnostico`,
                           { diagnostico: diag[a.id] ?? a.diagnostico ?? '' }),
            'Diagnóstico capturado')}>
            Capturar diagnóstico
          </button>
        </div>
      ))}
      <Regla>
        CU-ADM-11: el mecánico no teclea nada. Tú capturas y el sistema guarda los dos
        responsables: quién lo hizo y quién lo capturó (RN-11).
      </Regla>
    </Modal>
  )
}

function ModalSalida({ orden, onCerrar, onListo }) {
  const toast = useToast()
  const [form, setForm] = useState({
    km_salida: '', trabajos_realizados: '', observaciones: '', unidad_operativa: true,
  })
  const enviar = async (e) => {
    e.preventDefault()
    try {
      await api.post(`/admin/ordenes/${orden.id}/salida`, {
        ...form, km_salida: Number(form.km_salida),
      })
      onListo()
    } catch (err) { toast(err.message, 'err') }
  }
  return (
    <Modal titulo={`Formato de salida · ${orden.folio}`} onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="field">
          <label>Kilometraje de salida</label>
          <input type="number" required value={form.km_salida}
                 onChange={(e) => setForm({ ...form, km_salida: e.target.value })} />
        </div>
        <div className="field">
          <label>Trabajos realizados</label>
          <textarea required value={form.trabajos_realizados}
                    onChange={(e) => setForm({ ...form, trabajos_realizados: e.target.value })} />
        </div>
        <div className="field">
          <label>Observaciones</label>
          <textarea value={form.observaciones}
                    onChange={(e) => setForm({ ...form, observaciones: e.target.value })} />
        </div>
        <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}>
          <input type="checkbox" style={{ width: 20, height: 20 }} checked={form.unidad_operativa}
                 onChange={(e) => setForm({ ...form, unidad_operativa: e.target.checked })} />
          <span>La unidad sale operativa</span>
        </label>
        <button className="btn primary block">Emitir salida y liberar espacio</button>
      </form>
    </Modal>
  )
}

/* ------------------------------------- CU-ADM-12/13/07/16/08 (v1.1) -------- */
function Presupuestos() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/admin/presupuestos'))
  const ordenes = useApi(() => api.get('/admin/ordenes'))
  const tecnicos = useApi(() => api.get('/admin/tecnicos'))
  const piezas = useApi(() => api.get('/admin/piezas'))
  const compras = useApi(() => api.get('/admin/ordenes-compra'))
  const [capturar, setCapturar] = useState(false)

  const correr = async (fn, ok) => {
    try { const r = await fn(); toast(r?.mensaje || ok); recargar(); compras.recargar() }
    catch (e) { toast(e.message, 'err') }
  }

  if (cargando) return <Spinner />
  return (
    <>
      <div className="card-head">
        <h1>Presupuestos</h1>
        <button className="btn primary" onClick={() => setCapturar(true)}>Capturar presupuesto</button>
      </div>

      <Aviso tipo="info">
        El mecánico lo elabora en papel y tú lo capturas. Queda registrado quién lo hizo y quién
        lo tecleó (RN-11). El gerente es el único que aprueba (RN-07).
      </Aviso>

      {(data || []).map((p) => (
        <Card key={p.id} title={`${p.folio} · ${p.unidad}`}
              actions={<EstadoBadge estado={p.estado} />}>
          <p className="sub">
            Elaboró <strong>{p.tecnico_elaboro}</strong> el {fmtFecha(p.fecha_elaboracion)} ·
            capturó <strong>{p.capturado_por}</strong>
            {p.dias_retraso_captura != null && (
              <> · <Badge tono={p.dias_retraso_captura > 1 ? 'warn' : 'ok'}>
                {p.dias_retraso_captura} d de retraso
              </Badge></>
            )}
          </p>
          <Tabla
            columnas={[
              { k: 'pieza', t: 'Concepto', r: (f) => f.pieza || f.descripcion_libre },
              { k: 'cantidad', t: 'Cant.', num: true },
              { k: 'importe', t: 'Importe', num: true, r: (f) => fmtMoneda(f.importe) },
            ]}
            filas={p.detalles} vacio="Sin piezas" />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 }}>
            <span className="sub">Mano de obra {fmtMoneda(p.costo_mano_obra)}</span>
            <strong>Total {fmtMoneda(p.total)}</strong>
          </div>

          {p.autorizaciones.length > 0 && (
            <div style={{ marginTop: 10 }}>
              {p.autorizaciones.map((a) => (
                <div className="s" key={a.id}>
                  {fmtFechaHora(a.fecha)} · <strong>{a.nivel}</strong> {a.usuario}:{' '}
                  {a.resultado} {a.comentario && `— ${a.comentario}`}
                </div>
              ))}
            </div>
          )}

          <div className="btn-row" style={{ marginTop: 12 }}>
            {['capturado', 'devuelto'].includes(p.estado) && (
              <button className="btn primary sm" onClick={() => correr(
                () => api.post(`/admin/presupuestos/${p.id}/remitir`), 'Remitido al gerente')}>
                Remitir al gerente
              </button>
            )}
            {['aprobado', 'rechazado', 'devuelto'].includes(p.estado) && !p.fecha_aviso_al_tecnico && (
              <button className="btn sm" onClick={() => correr(
                () => api.post(`/admin/presupuestos/${p.id}/avisar-tecnico`), 'Constancia registrada')}>
                Registrar aviso al mecánico
              </button>
            )}
            {p.estado === 'aprobado' && (
              <button className="btn ok sm" onClick={() => correr(
                () => api.post(`/admin/presupuestos/${p.id}/orden-compra`), 'Orden de compra creada')}>
                Autorizar orden de compra
              </button>
            )}
          </div>
          {p.fecha_aviso_al_tecnico && (
            <p className="sub" style={{ marginTop: 8 }}>
              ✅ Se avisó al mecánico el {fmtFechaHora(p.fecha_aviso_al_tecnico)}
            </p>
          )}
        </Card>
      ))}
      {(data || []).length === 0 && <Empty icono="💰">Sin presupuestos capturados</Empty>}

      <Card title="Órdenes de compra">
        <Tabla
          vacio="Sin órdenes de compra"
          columnas={[
            { k: 'folio', t: 'Folio' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            { k: 'fecha_estimada_llegada', t: 'Llega', r: (f) => fmtFecha(f.fecha_estimada_llegada) },
            { k: 'total', t: 'Total', num: true, r: (f) => fmtMoneda(f.total) },
            { k: 'acc', t: '', r: (f) => f.estado !== 'recibida' && (
              <button className="btn sm" onClick={() => correr(
                () => api.post(`/admin/ordenes-compra/${f.id}/recibir`), 'Piezas recibidas')}>
                Recibir
              </button>
            ) },
          ]}
          filas={compras.data || []} />
      </Card>

      {capturar && (
        <ModalPresupuesto ordenes={ordenes.data || []} tecnicos={tecnicos.data || []}
                          piezas={piezas.data || []} onCerrar={() => setCapturar(false)}
                          onListo={() => { setCapturar(false); recargar() }} />
      )}
    </>
  )
}

function ModalPresupuesto({ ordenes, tecnicos, piezas, onCerrar, onListo }) {
  const toast = useToast()
  const hoy = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({
    orden_servicio_id: '', tecnico_elaboro_id: '', fecha_elaboracion: hoy,
    folio_papel: '', costo_mano_obra: '', diagnostico: '',
  })
  const [lineas, setLineas] = useState([{ pieza_id: '', cantidad: 1, precio_unitario: '' }])

  const setLinea = (i, campo, valor) => {
    const cp = [...lineas]
    cp[i] = { ...cp[i], [campo]: valor }
    if (campo === 'pieza_id') {
      const p = piezas.find((x) => String(x.id) === String(valor))
      if (p) cp[i].precio_unitario = p.precio_referencia
    }
    setLineas(cp)
  }

  const total = lineas.reduce((s, l) => s + Number(l.cantidad || 0) * Number(l.precio_unitario || 0), 0)
                + Number(form.costo_mano_obra || 0)

  const enviar = async (e) => {
    e.preventDefault()
    try {
      await api.post('/admin/presupuestos', {
        orden_servicio_id: Number(form.orden_servicio_id),
        tecnico_elaboro_id: Number(form.tecnico_elaboro_id),
        fecha_elaboracion: form.fecha_elaboracion,
        folio_papel: form.folio_papel,
        costo_mano_obra: Number(form.costo_mano_obra || 0),
        diagnostico: form.diagnostico,
        detalles: lineas.filter((l) => l.pieza_id).map((l) => ({
          pieza_id: Number(l.pieza_id), cantidad: Number(l.cantidad),
          precio_unitario: Number(l.precio_unitario),
        })),
      })
      toast('Presupuesto capturado')
      onListo()
    } catch (err) { toast(err.message, 'err') }
  }

  return (
    <Modal titulo="Capturar presupuesto del mecánico" onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="field">
          <label>Orden de servicio</label>
          <select required value={form.orden_servicio_id}
                  onChange={(e) => setForm({ ...form, orden_servicio_id: e.target.value })}>
            <option value="">Selecciona…</option>
            {ordenes.map((o) => <option key={o.id} value={o.id}>{o.folio} · {o.unidad}</option>)}
          </select>
        </div>
        <div className="field">
          <label>¿Qué mecánico lo elaboró?</label>
          <select required value={form.tecnico_elaboro_id}
                  onChange={(e) => setForm({ ...form, tecnico_elaboro_id: e.target.value })}>
            <option value="">Selecciona…</option>
            {tecnicos.map((t) => <option key={t.id} value={t.id}>{t.nombre} · {t.especialidad}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Fecha que trae el papel</label>
          <input type="date" required max={hoy} value={form.fecha_elaboracion}
                 onChange={(e) => setForm({ ...form, fecha_elaboracion: e.target.value })} />
        </div>
        <div className="field">
          <label>Folio del formato físico</label>
          <input value={form.folio_papel}
                 onChange={(e) => setForm({ ...form, folio_papel: e.target.value })} />
        </div>
        <div className="field">
          <label>Diagnóstico</label>
          <textarea value={form.diagnostico}
                    onChange={(e) => setForm({ ...form, diagnostico: e.target.value })} />
        </div>

        <label>Piezas</label>
        {lineas.map((l, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 60px 90px', gap: 6, marginBottom: 6 }}>
            <select value={l.pieza_id} onChange={(e) => setLinea(i, 'pieza_id', e.target.value)}>
              <option value="">Pieza…</option>
              {piezas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
            <input type="number" min="1" value={l.cantidad}
                   onChange={(e) => setLinea(i, 'cantidad', e.target.value)} />
            <input type="number" placeholder="$" value={l.precio_unitario}
                   onChange={(e) => setLinea(i, 'precio_unitario', e.target.value)} />
          </div>
        ))}
        <button type="button" className="btn sm"
                onClick={() => setLineas([...lineas, { pieza_id: '', cantidad: 1, precio_unitario: '' }])}>
          + Otra pieza
        </button>

        <div className="field" style={{ marginTop: 12 }}>
          <label>Mano de obra</label>
          <input type="number" value={form.costo_mano_obra}
                 onChange={(e) => setForm({ ...form, costo_mano_obra: e.target.value })} />
        </div>

        <p style={{ textAlign: 'right', fontWeight: 700, marginBottom: 12 }}>
          Total {fmtMoneda(total)}
        </p>
        <button className="btn primary block">Capturar</button>
        <Regla>
          La fecha del papel no puede ser futura (RI-11). La diferencia con la fecha de captura es
          el indicador de retraso que ve el gerente.
        </Regla>
      </form>
    </Modal>
  )
}

/* ---------------------------------------------------------- CU-ADM-15 ------ */
function HojaTrabajo() {
  const { data, cargando } = useApi(() => api.get('/admin/hoja-de-trabajo/1'))
  if (cargando) return <Spinner />
  return (
    <>
      <div className="card-head">
        <h1>Hoja de trabajo del día</h1>
        <button className="btn" onClick={() => window.print()}>🖨️ Imprimir</button>
      </div>
      <Aviso tipo="info">
        Los mecánicos no usan la aplicación: esta hoja se imprime y se les entrega en papel
        (CU-ADM-15).
      </Aviso>
      {(data?.tecnicos || []).length === 0 ? (
        <Empty icono="🖨️">Nada pendiente por asignar</Empty>
      ) : (data.tecnicos.map((t) => (
        <Card key={t.tecnico} title={t.tecnico} actions={<Badge>{t.especialidad}</Badge>}>
          <Tabla
            columnas={[
              { k: 'posicion', t: '#', num: true },
              { k: 'orden', t: 'Orden' },
              { k: 'unidad', t: 'Unidad' },
              { k: 'espacio', t: 'Espacio' },
              { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            ]}
            filas={t.trabajos} />
        </Card>
      )))}
    </>
  )
}
