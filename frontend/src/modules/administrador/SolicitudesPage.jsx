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
/** Motivos de rechazo de un toque. Le llegan al chofer tal cual, asi que van en
 *  su idioma; si ninguno queda, se escribe el propio. */
const MOTIVOS_RECHAZO = [
  'No es falla para taller',
  'Solicitud repetida',
  'Falta describir la falla',
  'Se atiende en otra planta',
  'La unidad está dada de baja',
]

/** `esMecanico`: la misma bandeja, para el mecanico de una planta satelite. El
 *  servidor ya le manda solo las de su planta; aqui solo cambia a donde lleva
 *  aceptar (el formato lo llena el administrador, no el). */
export function Solicitudes({ esMecanico = false }) {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/admin/solicitudes'))
  const [resolver, setResolver] = useState(null)
  const [rechazar, setRechazar] = useState(null)

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
                <div className="s">
                  Pide {s.taller}
                  {s.planta_madre && s.planta_madre !== s.taller && ` · la unidad es de ${s.planta_madre}`}
                </div>
                <div className="s">{s.descripcion_falla}</div>
                <div className="s">{fmtFechaHora(s.fecha_solicitud)}</div>
                <div className="s">
                  {s.espacios_libres_compatibles > 0
                    ? <span style={{ color: 'var(--ok)' }}>
                        {s.espacios_libres_compatibles} espacio(s) compatible(s) libre(s)</span>
                    : <span style={{ color: 'var(--danger)' }}>Sin espacio compatible</span>}
                  {s.espacios_libres_compatibles === 0 && !esMecanico && s.otras_plantas?.length > 0 && (
                    <span> · hay lugar en {s.otras_plantas.map((o) => o.nombre).join(', ')}</span>
                  )}
                </div>
              </div>
              {/* Rechazar a la vista, junto a Atender. Antes vivia al final de la
                  ventana de Atender, debajo del plano, y no lo encontraba nadie. */}
              <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
                <EstadoBadge estado={s.estado} />
                <button className="btn sm primary" onClick={() => setResolver(s)}>Atender</button>
                <button className="btn sm danger" onClick={() => setRechazar(s)}>Rechazar</button>
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
            { k: 'atendida_por', t: 'Atendió', r: (f) => f.atendida_por || '—' },
            { k: 'motivo_rechazo', t: 'Motivo', r: (f) => f.motivo_rechazo || '—' },
          ]}
          filas={(data || []).filter((s) => !['pendiente', 'en_cola'].includes(s.estado))} />
      </Card>

      {resolver && (
        <ModalResolver solicitud={resolver} esMecanico={esMecanico}
                       onCerrar={() => setResolver(null)}
                       onListo={() => { setResolver(null); recargar() }} />
      )}
      {rechazar && (
        <ModalRechazo solicitud={rechazar} onCerrar={() => setRechazar(null)}
                      onListo={() => { setRechazar(null); recargar(); toast('Solicitud rechazada') }} />
      )}
    </>
  )
}

/** Rechazar con motivo. El motivo le llega al chofer por aviso (y al celular si
 *  los activo), y queda en el historial y en la bitacora. */
function ModalRechazo({ solicitud, onCerrar, onListo }) {
  const toast = useToast()
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)
  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try {
      await api.post(`/admin/solicitudes/${solicitud.id}/resolver`,
                     { aceptar: false, motivo_rechazo: motivo.trim() })
      onListo()
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setEnviando(false)
    }
  }
  return (
    <Modal titulo={`Rechazar · ${solicitud.unidad}`} onClose={onCerrar}>
      <p className="sub">{solicitud.chofer} · {solicitud.tipo} · urgencia {solicitud.urgencia}</p>
      <p>{solicitud.descripcion_falla}</p>
      <form onSubmit={enviar}>
        <div className="field">
          <label>Motivo (se le avisa al chofer)</label>
          <div className="btn-row" style={{ marginBottom: 8 }}>
            {MOTIVOS_RECHAZO.map((m) => (
              <button type="button" key={m} className={`btn sm${motivo === m ? ' primary' : ''}`}
                      onClick={() => setMotivo(m)}>{m}</button>
            ))}
          </div>
          <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)}
                    placeholder="O escribe el motivo" maxLength={240} />
        </div>
        <button className="btn danger block" disabled={enviando || !motivo.trim()}>
          {enviando ? 'Rechazando…' : 'Rechazar solicitud'}
        </button>
      </form>
    </Modal>
  )
}

function ModalResolver({ solicitud, esMecanico, onCerrar, onListo }) {
  const toast = useToast()
  const navegar = useNavigate()
  const [motivo, setMotivo] = useState('')
  const [espacioId, setEspacioId] = useState(null)
  // Donde se atiende. Arranca en la planta que pidio el chofer; el
  // administrador la puede mandar a otra con lugar y la unidad sigue siendo de
  // su planta madre (regla de Baja Gas, 2026-10-08).
  const opciones = [
    { taller_id: solicitud.taller_id, nombre: solicitud.taller,
      libres: solicitud.espacios_libres_compatibles },
    ...(esMecanico ? [] : solicitud.otras_plantas || []),
  ]
  const [tallerId, setTallerId] = useState(solicitud.taller_id)
  const actual = opciones.find((o) => o.taller_id === tallerId) || opciones[0]
  const otraPlanta = actual.taller_id !== solicitud.taller_id
  // CU-ADM-01 «include» CU-ADM-02: el plano se ve AQUI, al momento de decidir,
  // para elegir la casilla en vez de aceptar a ciegas.
  const { data: cargado, cargando, error, recargar } = useApi(
    () => api.get(`/admin/taller/${actual.taller_id}`), [actual.taller_id])
  // Solo el plano de la planta ELEGIDA: useApi conserva el anterior mientras
  // carga (o si falla), y elegir una casilla de otra planta acabaria en un 409.
  const taller = cargado?.id === actual.taller_id ? cargado : null
  const hayEspacio = actual.libres > 0

  const enviar = async (payload, ok) => {
    try {
      const res = await api.post(`/admin/solicitudes/${solicitud.id}/resolver`, payload)
      toast(ok)
      onListo()
      // Aceptar el ingreso ABRE el formato de esa unidad (CU-ADM-26). Llevar
      // ahi al administrador en el mismo movimiento es lo que hace que el
      // formato se empiece: dejarlo en la bandeja significaba que alguien
      // tenia que acordarse de ir a Reportes a buscarlo.
      if (payload.aceptar && res?.reporte_id && !esMecanico) navegar(`/reportes/${res.reporte_id}`)
    } catch (e) { toast(e.message, 'err') }
  }

  const elegido = espacioId
    ? taller?.zonas.flatMap((z) => z.espacios).find((e) => e.id === espacioId)
    : null

  return (
    <Modal titulo={`Solicitud · ${solicitud.unidad}`} onClose={onCerrar}>
      <p className="sub">{solicitud.chofer} · {solicitud.tipo} · urgencia {solicitud.urgencia}</p>
      <p>{solicitud.descripcion_falla}</p>

      {opciones.length > 1 && (
        <div className="field">
          <label>Dónde se atiende</label>
          <select value={actual.taller_id}
                  onChange={(e) => { setTallerId(Number(e.target.value)); setEspacioId(null) }}>
            {opciones.map((o) => (
              <option key={o.taller_id} value={o.taller_id}>
                {o.nombre} · {o.libres ? `${o.libres} libre(s)` : 'sin lugar'}
                {o.taller_id === solicitud.taller_id ? ' (la que pidió)' : ''}
              </option>
            ))}
          </select>
          <p className="hint">
            {otraPlanta
              ? `Se atiende en ${actual.nombre}; la unidad sigue siendo de `
                + `${solicitud.planta_madre || solicitud.taller}. Al chofer le llega el aviso.`
              : 'Si en esta planta no hay lugar, puedes mandarla a otra que sí tenga.'}
          </p>
        </div>
      )}

      {hayEspacio ? (
        <Aviso tipo="ok">
          {actual.libres} espacio(s) compatible(s) disponible(s) en {actual.nombre}.
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
          {taller && !cargando ? (
            <div style={{ maxHeight: 260, overflowY: 'auto' }}>
              <PlanoTaller taller={taller} soloLibres seleccionado={espacioId}
                           onEspacio={(e) => setEspacioId(e.id)} />
            </div>
          ) : error && !cargando ? (
            <Aviso tipo="err">
              No cargó el plano de {actual.nombre}: {error}{' '}
              <button type="button" className="btn sm" onClick={recargar}>Reintentar</button>
            </Aviso>
          ) : <Spinner />}
          <p className="sub">
            Si no eliges ninguno, el sistema toma el primer espacio compatible libre.
          </p>
        </>
      )}

      <button className="btn primary block" disabled={!hayEspacio}
              onClick={() => enviar({ aceptar: true, espacio_id: espacioId || undefined,
                                      taller_id: otraPlanta ? actual.taller_id : undefined },
                                    otraPlanta ? `Ingreso aceptado en ${actual.nombre} · se abrió el formato`
                                               : 'Ingreso aceptado · se abrió el formato')}>
        {elegido
          ? `Colocar en ${elegido.numero} y abrir el formato`
          : 'Asignar espacio y abrir el formato'}
      </button>
      <p className="hint" style={{ marginTop: 6 }}>
        {esMecanico
          ? 'Al aceptar se abre el reporte de mantenimiento de esta unidad; el administrador del taller te asigna el trabajo.'
          : 'Al aceptar se abre solo el reporte de mantenimiento de esta unidad y te lleva a él.'}
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

/** Selector de taller. Ya son 7 plantas, no una sola. */
