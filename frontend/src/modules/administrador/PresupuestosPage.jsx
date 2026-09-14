/** CU-ADM-17 a 19 - captura del presupuesto y envio al gerente (RN-07). */
import { useState } from 'react'
import { api, fmtFecha, fmtFechaHora, fmtMoneda } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoCerrar, IcoListo, IcoPresupuestos, Modal,
  Regla, Spinner, Tabla, useApi, useToast,
} from '../../ui/index.js'
import { BuscadorPieza } from '../../ui/BuscadorPieza.jsx'

/* ------------------------------------- CU-ADM-12/13/07/16/08 (v1.1) -------- */
export function Presupuestos() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/admin/presupuestos'))
  const ordenes = useApi(() => api.get('/admin/ordenes'))
  const tecnicos = useApi(() => api.get('/admin/tecnicos'))
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
              <IcoListo size={13} className="ico-inline" aria-hidden="true" /> Se avisó al mecánico el {fmtFechaHora(p.fecha_aviso_al_tecnico)}
            </p>
          )}
        </Card>
      ))}
      {(data || []).length === 0 && <Empty icono={IcoPresupuestos}>Sin presupuestos capturados</Empty>}

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
                          onCerrar={() => setCapturar(false)}
                          onListo={() => { setCapturar(false); recargar() }} />
      )}
    </>
  )
}

function ModalPresupuesto({ ordenes, tecnicos, onCerrar, onListo }) {
  const toast = useToast()
  const hoy = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({
    orden_servicio_id: '', tecnico_elaboro_id: '', fecha_elaboracion: hoy,
    folio_papel: '', costo_mano_obra: '', diagnostico: '',
  })
  const [lineas, setLineas] = useState([{ pieza_id: '', nombre: '', cantidad: 1, precio_unitario: '' }])

  const setLinea = (i, campo, valor) => {
    const cp = [...lineas]
    if (campo === 'pieza') {
      // El buscador ya trae el precio de referencia: se propone y se puede
      // corregir, porque el papel del mecanico manda sobre el catalogo.
      cp[i] = { ...cp[i], pieza_id: valor.id || '', nombre: valor.nombre || '',
                precio_unitario: valor.precio ?? cp[i].precio_unitario }
    } else {
      cp[i] = { ...cp[i], [campo]: valor }
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
          <div key={i} className="linea-pieza">
            <BuscadorPieza
              valor={l.pieza_id} nombre={l.nombre}
              onElegir={(id, nombre, precio) => setLinea(i, 'pieza', { id, nombre, precio })} />
            <input type="number" min="1" value={l.cantidad} title="Cantidad"
                   onChange={(e) => setLinea(i, 'cantidad', e.target.value)} />
            <input type="number" placeholder="$" value={l.precio_unitario} title="Precio unitario"
                   onChange={(e) => setLinea(i, 'precio_unitario', e.target.value)} />
            <button type="button" className="btn sm" title="Quitar esta pieza"
                    disabled={lineas.length === 1}
                    onClick={() => setLineas(lineas.filter((_, j) => j !== i))}><IcoCerrar size={13} aria-hidden="true" /></button>
          </div>
        ))}
        <button type="button" className="btn sm"
                onClick={() => setLineas([...lineas, { pieza_id: '', nombre: '', cantidad: 1, precio_unitario: '' }])}>
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
