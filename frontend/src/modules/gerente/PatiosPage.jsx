/** Los patios de cada planta, para el gerente: que unidades estan adentro, el
 *  croquis y la flota de la planta. Todo de solo lectura.
 *
 *  Lo pidio el Lic. Tiscareno. El croquis es el MISMO componente que usa Victor
 *  en su Plano (administrador/PlanoTaller.jsx), sin la funcion de tocar
 *  casillas: si se copiara, el dia que alguien cambie uno los dos verian plantas
 *  distintas. Quien puede mover unidades lo sigue decidiendo el servidor. */
import { useState } from 'react'
import { api, fmtFecha } from '../../core/api.js'
import { Badge, Card, Kpi, Regla, Spinner, Tabla, useApi } from '../../ui/index.js'
import { PlanoTaller } from '../administrador/PlanoTaller.jsx'

const FUENTE = { croquis: 'Croquis', orden: 'Orden', excel: 'Excel del taller' }
const TONO_SITUACION = {
  'Por ingresar': 'info', 'En reparación': 'ok', 'Pendiente por compras': 'warn',
  'Refacciones chinas': 'warn', 'Taller externo': '',
}
const tonoDias = (d) => (d > 90 ? 'danger' : d > 30 ? 'warn' : 'ok')

function Adentro({ p }) {
  return (
    <Card title={`Adentro ahora (${p.adentro.length})`}
          sub="Unidades en el taller o el patio de esta planta, las que más días llevan primero.">
      {Object.keys(p.situaciones).length > 0 && (
        <p style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '0 0 10px' }}>
          {Object.entries(p.situaciones).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
            <Badge key={s} tono={TONO_SITUACION[s] ?? ''}>{s}: {n}</Badge>
          ))}
        </p>
      )}
      <Tabla
        vacio="No hay unidades registradas adentro de esta planta."
        columnas={[
          { k: 'unidad', t: 'Unidad' },
          { k: 'tipo', t: 'Tipo' },
          { k: 'situacion', t: 'Situación',
            r: (f) => (f.situacion ? <Badge tono={TONO_SITUACION[f.situacion] ?? ''}>
              {f.situacion}</Badge> : '—') },
          { k: 'falla', t: 'Falla' },
          { k: 'desde', t: 'Desde', r: (f) => fmtFecha(f.desde) },
          { k: 'dias', t: 'Días', num: true,
            r: (f) => (f.dias == null ? '—' : <Badge tono={tonoDias(f.dias)}>{f.dias}</Badge>) },
          { k: 'donde', t: 'Dónde', r: (f) => [f.espacio, f.orden].filter(Boolean).join(' · ') || '—' },
          { k: 'fuentes', t: 'Según', r: (f) => f.fuentes.map((x) => FUENTE[x] || x).join(', ') },
        ]}
        filas={p.adentro.map((f) => ({ ...f, id: f.unidad_id }))} />
      <Regla>
        Se junta de tres lados: las casillas del croquis que acomoda el administrador, las
        órdenes de servicio abiertas y la hoja PATIO del Excel del taller (hoy solo la manda
        Álamos). La situación sale de ese Excel.
      </Regla>
    </Card>
  )
}

function Flota({ p }) {
  const [buscar, setBuscar] = useState('')
  const q = buscar.trim().toUpperCase().replace(/[-\s]/g, '')
  const filas = p.flota.filter((u) => !q || u.unidad.toUpperCase().replace(/[-\s]/g, '').includes(q)
    || (u.chofer || '').toUpperCase().includes(buscar.trim().toUpperCase()))
  return (
    <Card title={`Flota de la planta (${p.flota.length})`}
          sub="Todas las unidades activas que tienen a esta planta como su taller.">
      <input type="search" placeholder="Buscar unidad o chofer" value={buscar}
             onChange={(e) => setBuscar(e.target.value)}
             style={{ width: '100%', maxWidth: 320, marginBottom: 10 }} />
      <Tabla
        vacio={buscar ? 'Ninguna unidad coincide.' : 'Esta planta no tiene unidades asignadas.'}
        columnas={[
          { k: 'unidad', t: 'Unidad' },
          { k: 'tipo', t: 'Tipo' },
          { k: 'estado', t: 'Estado',
            r: (u) => (u.adentro ? <Badge tono="warn">en patio</Badge> : u.estado) },
          { k: 'chofer', t: 'Chofer titular' },
        ]}
        filas={filas.map((u) => ({ ...u, id: u.unidad_id }))} />
      {p.sin_planta > 0 && (
        <Regla>Hay {p.sin_planta} unidades activas sin planta asignada en el catálogo: no
          aparecen en ninguna planta hasta que Logística les ponga sucursal.</Regla>
      )}
    </Card>
  )
}

export function Patios() {
  const lista = useApi(() => api.get('/gerente/patios'))
  const [tallerId, setTallerId] = useState(null)
  const id = tallerId ?? lista.data?.[0]?.taller_id
  const patio = useApi(() => (id ? api.get(`/gerente/patios/${id}`) : Promise.resolve(null)), [id])
  const plano = useApi(() => (id ? api.get(`/admin/taller/${id}`) : Promise.resolve(null)), [id])

  if (lista.cargando) return <Spinner />
  const p = patio.data
  // Alamos repara unidades de todas las plantas: de las que estan adentro, no
  // todas son de su flota. Contarlo aparte evita que "adentro 52" y "flota 347"
  // parezcan decir que 52 de esas 347 estan paradas.
  const propias = p ? p.flota.filter((u) => u.adentro).length : 0
  const ajenas = p ? p.adentro.length - propias : 0
  return (
    <>
      <div className="card-head" style={{ marginBottom: 10 }}>
        <h1>Patios</h1>
        <div className="spacer" />
        <select value={id ?? ''} onChange={(e) => setTallerId(Number(e.target.value))}
                aria-label="Planta">
          {(lista.data || []).map((t) => (
            <option key={t.taller_id} value={t.taller_id}>
              {t.nombre} · {t.adentro} adentro
            </option>
          ))}
        </select>
      </div>

      {patio.cargando || !p ? <Spinner /> : (
        <>
          <div className="grid g3" style={{ marginBottom: 14 }}>
            <Kpi valor={p.adentro.length} etiqueta="Adentro ahora" tono={p.adentro.length ? 'alert' : ''}
                 hint={ajenas > 0 ? `${ajenas} son de otras plantas` : undefined} />
            <Kpi valor={p.flota.length} etiqueta="Unidades de la planta" />
            <Kpi valor={propias} etiqueta="De su flota, en el taller"
                 tono={propias ? 'warn' : 'ok'} />
          </div>
          <Adentro p={p} />
          <Card title="Croquis"
                sub="Las casillas como las acomoda el administrador. Aquí solo se ven; no se pueden mover.">
            {plano.cargando || !plano.data ? <Spinner /> : <PlanoTaller taller={plano.data} />}
            {plano.data && p.adentro.length > 0
              && plano.data.zonas.every((z) => z.espacios.every((e) => !e.unidad)) && (
              <Regla>El croquis está vacío porque nadie ha acomodado esas unidades en sus casillas
                desde la app; por eso “Adentro ahora” sale del Excel del taller.</Regla>
            )}
          </Card>
          <Flota p={p} />
        </>
      )}
    </>
  )
}
