/** Módulo Perito — nota 9 de la junta del 2026-09-14.
 *
 * Edgar es del sindicato pero trabaja para Baja Gas. Siendo de la casa, el
 * orden se invierte: se le avisa desde el sistema y él levanta el peritaje
 * dentro, en vez de que el chofer teclee después el folio que le dio un tercero.
 *
 * SU PANTALLA TIENE UNA SOLA COSA QUE DECIR: cuál unidad está detenida por su
 * firma. Todo lo demás es contexto para ir a verla. Por eso la bandeja ordena
 * por lo que lleva más tiempo esperando y no por folio.
 */
import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { api, fmtFechaHora } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, IcoListo, IcoUbicacion, Kpi, Modal, Regla, Spinner,
  Tabla, TiraFotos, useApi, useToast,
} from '../../ui/index.js'

export default function Perito() {
  return (
    <Routes>
      <Route path="/" element={<Pendientes />} />
      <Route path="/historial" element={<Historial />} />
    </Routes>
  )
}

function Pendientes() {
  const { data, cargando, error, recargar } = useApi(() => api.get('/perito/pendientes'))
  const [peritando, setPeritando] = useState(null)
  const toast = useToast()

  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="err">{error}</Aviso>
  const lista = data || []
  const urgentes = lista.filter((x) => x.urgente).length
  const choques = lista.filter((x) => x.tipo === 'choque').length

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Esperando peritaje</h1>

      <div className="grid g3">
        <Kpi valor={lista.length} etiqueta="Unidades detenidas"
             tono={lista.length ? 'warn' : ''} />
        <Kpi valor={urgentes} etiqueta="Más de 2 horas"
             tono={urgentes ? 'alert' : ''} />
        <Kpi valor={choques} etiqueta="Son choques" />
      </div>

      {!lista.length ? (
        <Card><Empty icono={IcoListo}>Ninguna unidad esperando tu peritaje</Empty></Card>
      ) : lista.map((r) => (
        <Card key={r.id} title={`${r.folio} · unidad ${r.unidad}`}
              sub={r.tipo === 'choque' ? 'Choque' : 'Avería en vialidad pública'}>
          <div className="grid g3">
            <div>
              <div className="s"><strong>Chofer:</strong> {r.chofer}</div>
              <div className="s"><strong>Reportado:</strong> {fmtFechaHora(r.fecha_hora)}</div>
              {r.horas_esperando != null && (
                <div className="s">
                  <strong>Esperando:</strong>{' '}
                  {r.urgente
                    ? <Badge tono="danger">{r.horas_esperando} h</Badge>
                    : <Badge>{r.horas_esperando} h</Badge>}
                </div>
              )}
            </div>
            <div>
              {r.hay_lesionados && <Aviso tipo="err"><strong>Hay lesionados</strong></Aviso>}
              {r.cuantos_terceros > 0 && (
                <div className="s"><strong>Terceros:</strong> {r.cuantos_terceros}</div>
              )}
              {r.direccion_referencia && (
                <div className="s">{r.direccion_referencia}</div>
              )}
              {r.latitud != null && (
                <a className="btn sm" target="_blank" rel="noreferrer"
                   href={`https://www.google.com/maps?q=${r.latitud},${r.longitud}`}>
                  <IcoUbicacion size={13} className="ico-inline" aria-hidden="true" /> Ver en el mapa
                </a>
              )}
            </div>
            <div>
              <div className="s">{r.descripcion}</div>
              {r.bloquea_movimiento && (
                <Aviso tipo="warn">
                  La unidad <strong>no se puede mover</strong> hasta que registres el peritaje.
                </Aviso>
              )}
            </div>
          </div>

          <TiraFotos fotos={r.fotos || []} />

          <div className="acciones">
            <button className="btn primario" onClick={() => setPeritando(r)}>
              Levantar peritaje
            </button>
          </div>
        </Card>
      ))}

      <Regla>
        Aquí solo aparece lo que de verdad necesita peritaje: <strong>todo choque</strong>, haya
        sido donde haya sido, y las <strong>averías en vialidad pública</strong>. Una avería en el
        patio de un cliente no entra — no hay nada que peritar, y llenar la bandeja de casos que
        no te tocan es como se deja de mirar la bandeja.
      </Regla>

      {peritando && (
        <ModalPeritaje r={peritando} onCerrar={() => setPeritando(null)}
                       onListo={() => {
                         setPeritando(null); recargar(); toast('Peritaje registrado')
                       }} />
      )}
    </>
  )
}

function ModalPeritaje({ r, onCerrar, onListo }) {
  const [folio, setFolio] = useState('')
  const [aseguradora, setAseguradora] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  async function enviar() {
    if (!folio.trim()) { setError('El folio es lo que desbloquea la unidad.'); return }
    setEnviando(true); setError(null)
    try {
      await api.post(`/perito/${r.id}/peritaje`, {
        folio_peritos: folio,
        aseguradora: aseguradora || null,
        nombre_perito: null,
        observaciones: observaciones || null,
      })
      onListo()
    } catch (e) { setError(String(e.message || e)); setEnviando(false) }
  }

  return (
    <Modal titulo={`Peritaje · ${r.folio}`} onClose={onCerrar}>
      {error && <Aviso tipo="err">{error}</Aviso>}
      <p>
        Unidad <strong>{r.unidad}</strong>, {r.tipo === 'choque' ? 'choque' : 'avería'} reportado
        por {r.chofer}.
      </p>
      <label className="campo">
        <span>Folio del peritaje</span>
        <input value={folio} onChange={(e) => setFolio(e.target.value)}
               placeholder="El que quede en el acta" />
      </label>
      <label className="campo">
        <span>Aseguradora (si aplica)</span>
        <input value={aseguradora} onChange={(e) => setAseguradora(e.target.value)} />
      </label>
      <label className="campo">
        <span>Observaciones</span>
        <textarea rows={3} value={observaciones}
                  onChange={(e) => setObservaciones(e.target.value)} />
      </label>
      <Regla>
        Queda a <strong>tu nombre</strong> y con la hora en que lo levantaste. Al guardarlo, la
        unidad se puede mover y se le avisa al chofer, a su supervisor y al taller.
      </Regla>
      <div className="acciones">
        <button className="btn" onClick={onCerrar} disabled={enviando}>Cancelar</button>
        <button className="btn primario" onClick={enviar} disabled={enviando}>
          {enviando ? 'Guardando…' : 'Registrar y liberar la unidad'}
        </button>
      </div>
    </Modal>
  )
}

function Historial() {
  const { data, cargando } = useApi(() => api.get('/perito/historial', { dias: 180 }))
  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Mis peritajes</h1>
      <Card sub="Últimos 180 días">
        <Tabla
          vacio="Todavía no has levantado ningún peritaje"
          columnas={[
            { k: 'cuando', t: 'Cuándo', r: (f) => fmtFechaHora(f.cuando) },
            { k: 'reporte_folio', t: 'Reporte' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'tipo', t: 'Tipo',
              r: (f) => <Badge tono={f.tipo === 'choque' ? 'danger' : ''}>{f.tipo}</Badge> },
            { k: 'folio_peritos', t: 'Folio' },
            { k: 'aseguradora', t: 'Aseguradora' },
          ]}
          filas={data || []} />
      </Card>
    </>
  )
}
