import { useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { api, fmtFechaHora } from '../../core/api.js'
import { Badge } from '../../ui/Badge.jsx'
import { Card } from '../../ui/Card.jsx'
import { Aviso, Regla, Spinner } from '../../ui/Feedback.jsx'
import { Tabla } from '../../ui/Tabla.jsx'
import { useToast } from '../../ui/Toast.jsx'

/** Carga de los Excel de las areas: subir, revisar contra una copia, confirmar.
 *
 *  La usan el administrador (todos los archivos) y una cuenta por area (solo
 *  los suyos). Quien puede subir que lo decide el servidor
 *  (backend/app/modules/sistema/cargas_service.py); esta pantalla solo pone los
 *  nombres que la gente reconoce. */

const AREA = { logistica: 'Logística', almacen: 'Almacén', compras: 'Compras', taller: 'Taller' }

const ARCHIVO = {
  unidades: { titulo: 'Catálogo de unidades', nombre: 'UNIDADES BAJA GAS',
              que: 'Placas, VIN, tipo de unidad, si está activa y su sucursal.' },
  choferes: { titulo: 'Información de choferes', nombre: 'INFO CHOFERES 2026 ACTUAL',
              que: 'Plantas, supervisores, choferes y la unidad que trae cada uno.' },
  choferes_lan: { titulo: 'Choferes LAN y estacionario', nombre: 'CHOFERES LAN ESTACIONARIO 1',
                  que: 'Teléfonos, turnos y rutas de los choferes.' },
  requisiciones: { titulo: 'Libro de requisiciones', nombre: 'REQUIS',
                   que: 'Refacciones con su código de SAP y las requisiciones del taller.' },
  codigos: { titulo: 'Códigos del taller', nombre: 'CODIGOS TALLER',
             que: 'Ubicación en el almacén de cada refacción.' },
  resumen: { titulo: 'Resumen del taller', nombre: 'RESUMEN',
             que: 'Historial de entradas al taller y unidades en el patio.' },
}

// Los nombres de tabla que salen en la revision, como los diria el taller.
const TABLA = {
  unidad: 'Unidades', usuario: 'Cuentas de usuario', usuario_rol: 'Permisos de cuentas',
  chofer: 'Choferes', supervisor: 'Supervisores', planta: 'Plantas', plantilla: 'Plantillas',
  tecnico: 'Técnicos', pieza: 'Refacciones', existencia: 'Existencias',
  requisicion: 'Requisiciones', renglon_requisicion: 'Renglones de requisición',
  movimiento_taller: 'Historial del taller', tipo_unidad: 'Tipos de unidad',
  bitacora_auditoria: 'Auditoría', proveedor: 'Proveedores',
}
const PASO = {
  base: 'Catálogo base', limpieza: 'Unidades duplicadas', flota: 'Placas y VIN',
  catalogo: 'Activas y sucursal', personal: 'Teléfonos y turnos', taller: 'Historial del taller',
}
const nombreTabla = (t) => TABLA[t] || t.replaceAll('_', ' ')
const titulo = (tipo) => ARCHIVO[tipo]?.titulo || tipo
const TONO_PASO = { ok: 'ok', error: 'danger', omitido: 'warn' }

function Archivo({ a, ocupado, onElegir }) {
  const d = ARCHIVO[a.tipo] || {}
  const revisando = ocupado === a.tipo
  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="card-head">
        <h2>{d.titulo}</h2>
        <Badge tono="info">{AREA[a.area]}</Badge>
      </div>
      <p className="sub">{d.que}</p>
      <p className="sub">
        {a.actual
          ? <>Ahora: <strong>{a.actual.nombre}</strong> · {fmtFechaHora(a.actual.actualizado)}</>
          : <>Todavía no hay archivo. Se espera uno llamado como <strong>{d.nombre}</strong>.</>}
      </p>
      {revisando ? (
        <Aviso tipo="info">
          <Spinner /> Revisando contra una copia de la base. Tarda hasta un minuto; no cierres la página.
        </Aviso>
      ) : (
        <label className="btn primary" aria-disabled={!!ocupado}
               style={ocupado ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}>
          Subir nuevo
          <input type="file" accept=".xlsx,.xlsm" hidden disabled={!!ocupado}
                 onChange={(e) => {
                   const f = e.target.files?.[0]
                   e.target.value = ''
                   if (f) onElegir(a.tipo, f)
                 }} />
        </label>
      )}
    </div>
  )
}

/** Lo que el importador dice que leyo, en sus palabras ("no vienen en el
 *  catalogo: 90"). Son conteos de lectura, no de cambios: por eso van aparte
 *  y cerrados, y la tabla de "Que cambia" es la que manda. */
function Lectura({ pasos }) {
  const n = pasos.flatMap((p) => Object.entries(p.resultado || {})
    .filter(([, v]) => typeof v === 'number' && v && typeof v !== 'boolean')
    .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v}`))
  if (!n.length) return null
  return (
    <details style={{ margin: '6px 0 10px' }}>
      <summary>Lo que el sistema leyó del archivo</summary>
      <p className="sub" style={{ margin: '6px 0 0' }}>{n.join(' · ')}</p>
    </details>
  )
}

function Revision({ r, aplicando, onAplicar, onDescartar }) {
  const [revise, setRevise] = useState(false)
  const filas = Object.entries(r.cambios || {}).map(([t, x]) => ({ id: t, que: nombreTabla(t), ...x }))
  const ejemplos = Object.entries(r.ejemplos || {}).filter(([, l]) => l.length)
  const alertas = r.alertas || []
  const listo = r.puede_aplicar && (!alertas.length || revise)
  // Solo los pasos que leen ESTE archivo. Los de otras areas corren igual (la
  // revision es completa), pero aqui solo se mencionan si fallaron.
  const propios = r.pasos.filter((p) => r.pasos_propios.includes(p.paso))
  const ajenosRotos = r.pasos.filter((p) => !r.pasos_propios.includes(p.paso) && p.estado !== 'ok')
  return (
    <Card title={`Revisión: ${titulo(r.tipo)}`}
          sub={`Subiste «${r.original}». Esto es lo que cambiaría; todavía no se ha guardado nada.`}>
      {!r.puede_aplicar && (
        <Aviso tipo="err">Este archivo no se puede aplicar: {r.motivo}. Revisa que sea el archivo
          correcto y que tenga las hojas y columnas de siempre.</Aviso>
      )}
      <ul style={{ margin: '0 0 4px', paddingLeft: 18 }}>
        {propios.map((p) => (
          <li key={p.paso}>
            {PASO[p.paso] || p.paso}{' '}
            <Badge tono={TONO_PASO[p.estado] || ''}>{p.estado}</Badge>
            {p.estado !== 'ok' && <span style={{ color: 'var(--muted)' }}> · {p.motivo}</span>}
          </li>
        ))}
      </ul>
      <Lectura pasos={propios.filter((p) => p.estado === 'ok')} />
      {ajenosRotos.length > 0 && (
        <p className="sub">Aparte, el archivo de otra área trae un problema
          ({ajenosRotos.map((p) => PASO[p.paso] || p.paso).join(', ')}). No impide aplicar este.</p>
      )}
      {filas.length ? (
        <Tabla columnas={[
          { k: 'que', t: 'Qué' },
          { k: 'nuevas', t: 'Nuevas', num: true },
          { k: 'borradas', t: 'Borradas', num: true },
          { k: 'cambiadas', t: 'Cambian', num: true },
        ]} filas={filas} />
      ) : (
        <Aviso tipo="ok">No cambia nada: la base ya estaba al día con este archivo.</Aviso>
      )}
      {ejemplos.length > 0 && (
        <details style={{ margin: '10px 0' }}>
          <summary>Ver ejemplos de lo que cambia</summary>
          {ejemplos.map(([t, lineas]) => (
            <div key={t} style={{ marginTop: 8 }}>
              <strong>{nombreTabla(t)}</strong>
              <ul style={{ margin: '4px 0', paddingLeft: 18, fontSize: 13 }}>
                {lineas.map((l, i) => <li key={i} style={{ wordBreak: 'break-word' }}>{l}</li>)}
              </ul>
            </div>
          ))}
        </details>
      )}
      {r.cuentas_nuevas > 0 && (
        <Aviso tipo="info">Se crearían {r.cuentas_nuevas} cuentas nuevas de choferes. Entran con una
          contraseña al azar: hay que darles la suya.</Aviso>
      )}
      {alertas.length > 0 && r.puede_aplicar && (
        <Aviso tipo="warn">
          <strong>Revisa bien antes de aplicar:</strong>
          <ul style={{ margin: '4px 0 8px', paddingLeft: 18 }}>
            {alertas.map((a) => (
              <li key={a.tabla + a.tipo}>
                {a.tipo === 'borradas'
                  ? `Se borrarían ${a.cuantas} filas de ${nombreTabla(a.tabla)}.`
                  : `Cambian ${a.cuantas} filas de ${nombreTabla(a.tabla)}.`}
              </li>
            ))}
          </ul>
          Si no esperabas tantos cambios, puede ser otro archivo o una hoja equivocada.
          <label style={{ display: 'block', marginTop: 6 }}>
            <input type="checkbox" checked={revise} onChange={(e) => setRevise(e.target.checked)} />{' '}
            Ya revisé los cambios y es el archivo correcto
          </label>
        </Aviso>
      )}
      <div className="btn-row" style={{ marginTop: 12 }}>
        <button className="btn primary" disabled={!listo || aplicando} onClick={onAplicar}>
          {aplicando ? 'Aplicando…' : 'Aplicar cambios'}
        </button>
        <button className="btn" disabled={aplicando} onClick={onDescartar}>Descartar</button>
      </div>
      <Regla>Al aplicar, la base se respalda antes y el archivo anterior se guarda en el historial
        del servidor. Queda anotado quién subió qué y cuándo.</Regla>
    </Card>
  )
}

export function CargarDatos() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState(null)
  const [revision, setRevision] = useState(null)
  const [ocupado, setOcupado] = useState(null)
  const [aplicando, setAplicando] = useState(false)
  const toast = useToast()

  const cargar = () => api.get('/cargas').then(setDatos).catch((e) => setError(e.message))
  useEffect(() => { cargar() }, [])

  const revisar = async (tipo, archivo) => {
    setRevision(null)
    setOcupado(tipo)
    try {
      setRevision(await api.subir(`/cargas/${tipo}/simular`, archivo))
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setOcupado(null)
    }
  }

  const aplicar = async () => {
    setAplicando(true)
    try {
      await api.post(`/cargas/${revision.carga_id}/aplicar`)
      toast(`${titulo(revision.tipo)}: cambios aplicados`)
      setRevision(null)
      cargar()
    } catch (e) {
      toast(e.message, 'err')
      if (e.status === 409) setRevision(null)
    } finally {
      setAplicando(false)
    }
  }

  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!datos) return <Spinner />

  const ultima = datos.ultima
  const rotos = (ultima?.pasos || []).filter((p) => p.estado === 'error')
  return (
    <>
      <h1>Cargar datos</h1>
      <Regla>Sube el Excel de tu área con el formato de siempre. Primero se revisa contra una copia
        de la base y te enseña qué cambiaría: nada se guarda hasta que lo confirmes. Cada
        madrugada el sistema vuelve a leer los archivos que estén puestos.</Regla>
      {ultima && (
        <p className="sub">
          Última actualización: {fmtFechaHora(ultima.fin)}
          {rotos.length > 0 && <> · <Badge tono="danger">
            con error en {rotos.map((p) => PASO[p.paso] || p.paso).join(', ')}</Badge></>}
        </p>
      )}

      {revision && (
        <Revision key={revision.carga_id} r={revision} aplicando={aplicando}
                  onAplicar={aplicar} onDescartar={() => setRevision(null)} />
      )}

      {datos.archivos.map((a) => (
        <Archivo key={a.tipo} a={a} ocupado={ocupado || (aplicando ? 'aplicando' : null)}
                 onElegir={revisar} />
      ))}

      <Card title="Últimas cargas">
        <Tabla vacio="Todavía nadie ha subido archivos desde aquí."
               columnas={[
                 { k: 'fecha', t: 'Cuándo', r: (h) => fmtFechaHora(h.fecha) },
                 { k: 'tipo', t: 'Archivo', r: (h) => titulo(h.tipo) },
                 { k: 'original', t: 'Nombre subido' },
                 { k: 'quien', t: 'Quién' },
                 { k: 'cambios', t: 'Filas que cambiaron', num: true },
               ]}
               filas={datos.historial} />
      </Card>
    </>
  )
}

/** El modulo completo de las cuentas por area: no tienen otra pantalla. */
export default function Datos() {
  return (
    <Routes>
      <Route path="/*" element={<CargarDatos />} />
    </Routes>
  )
}
