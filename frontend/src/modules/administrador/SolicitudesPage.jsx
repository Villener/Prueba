/** CU-ADM-01 con «include» CU-ADM-02: no se decide sin ver los espacios. */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHora } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoSolicitudes, Modal, Spinner, Tabla, useApi,
  useToast,
} from '../../ui/index.js'
import { PlanoTaller } from './PlanoTaller.jsx'

/* -------------------------------------------------- CU-ADM-01/02 ----------- */
export function Solicitudes() {
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
        {pendientes.length === 0 ? <Empty icono={IcoSolicitudes}>Bandeja vacía</Empty> : (
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
  const navegar = useNavigate()
  const [motivo, setMotivo] = useState('')
  const [espacioId, setEspacioId] = useState(null)
  // CU-ADM-01 «include» CU-ADM-02: el plano se ve AQUI, al momento de decidir,
  // para elegir la casilla en vez de aceptar a ciegas.
  const { data: taller, cargando } = useApi(
    () => api.get(`/admin/taller/${solicitud.taller_id}`), [solicitud.taller_id])
  const hayEspacio = solicitud.espacios_libres_compatibles > 0

  const enviar = async (payload, ok) => {
    try {
      const res = await api.post(`/admin/solicitudes/${solicitud.id}/resolver`, payload)
      toast(ok)
      onListo()
      // Aceptar el ingreso ABRE el formato de esa unidad (CU-ADM-26). Llevar
      // ahi al administrador en el mismo movimiento es lo que hace que el
      // formato se empiece: dejarlo en la bandeja significaba que alguien
      // tenia que acordarse de ir a Reportes a buscarlo.
      if (payload.aceptar && res?.reporte_id) navegar(`/reportes/${res.reporte_id}`)
    } catch (e) { toast(e.message, 'err') }
  }

  const elegido = espacioId
    ? taller?.zonas.flatMap((z) => z.espacios).find((e) => e.id === espacioId)
    : null

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

      {hayEspacio && (
        <>
          <h3 style={{ margin: '14px 0 8px' }}>
            {elegido ? `Espacio elegido: ${elegido.numero}` : 'Elige el espacio'}
          </h3>
          {cargando ? <Spinner /> : (
            <div style={{ maxHeight: 260, overflowY: 'auto' }}>
              <PlanoTaller taller={taller} soloLibres seleccionado={espacioId}
                           onEspacio={(e) => setEspacioId(e.id)} />
            </div>
          )}
          <p className="sub">
            Si no eliges ninguno, el sistema toma el primer espacio compatible libre.
          </p>
        </>
      )}

      <button className="btn primary block" disabled={!hayEspacio}
              onClick={() => enviar({ aceptar: true, espacio_id: espacioId || undefined },
                                    'Ingreso aceptado · se abrió el formato')}>
        {elegido
          ? `Colocar en ${elegido.numero} y abrir el formato`
          : 'Asignar espacio y abrir el formato'}
      </button>
      <p className="hint" style={{ marginTop: 6 }}>
        Al aceptar se abre solo el reporte de mantenimiento de esta unidad y te lleva a él.
      </p>

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

/* ================================================= CU-ADM-03/04: el plano ==== */

/** Selector de taller. Ya son 6 plantas, no una sola. */
