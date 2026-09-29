/** Libro de bitácora de mantenimiento de una unidad — PROY-NOM-030-ASEA-2026, 7.1.10.
 *
 * Es la página que se le enseña al inspector: los registros de mantenimiento de
 * UNA unidad, numerados, con quién y cuándo los registró el sistema, y la
 * prueba de que nadie los tocó después.
 *
 * LA COMPARTEN CINCO ROLES y por eso vive aquí y no en un módulo. El inciso b)
 * pide el libro «en un lugar de fácil acceso tanto para el Operador de la
 * Unidad como para el personal responsable del mantenimiento»: el chofer lo
 * abre desde Mi unidad; el administrador desde la hoja del reporte; el
 * mecánico desde su trabajo; el supervisor desde su plantilla; el gerente desde
 * el historial de la unidad. Quién puede ver qué lo decide el servidor.
 *
 * SOLO LECTURA. Aquí no se registra nada del mantenimiento: los asientos los
 * deja quien llena el formato. Lo único que se captura aquí son los datos de
 * identificación de 7.1.10 c) (permiso, razón social, personal auxiliar).
 */
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHoraAnio } from '../../core/api.js'
import {
  Aviso, Card, Empty, IcoBitacora, IcoImprimir, IcoVolver, Modal, Regla, Spinner,
  useApi, useToast,
} from '../../ui/index.js'

const TIPO = {
  apertura: 'Entrada al taller',
  actividad: 'Actividad',
  reasignacion: 'Reasignación',
  firma: 'Firma',
  evidencia: 'Evidencia',
  comentarios: 'Comentarios',
  vinculo: 'Orden ligada',
  identificacion: 'Datos de identificación',
  cierre: 'Salida del taller',
  correccion: 'Corrección',
  migracion: 'Transcripción',
  hallazgo: 'Hallazgo',
}
const RESULTADO = { conforme: 'Conforme', no_conforme: 'No conforme' }
// Asientos cuyas fechas son las de la estancia, no las de una actividad.
const ESTANCIA = new Set(['apertura', 'cierre', 'migracion'])

export default function BitacoraUnidad({ usuario }) {
  const { unidadId } = useParams()
  if (!unidadId) return <MisUnidades />
  return <Libro unidadId={Number(unidadId)} usuario={usuario} />
}

/** `/bitacora` sin unidad: el chofer llega aquí y se le lleva a la suya.
 *  Si responde por dos (la que trae y la que prestó), elige. */
function MisUnidades() {
  const navegar = useNavigate()
  const { data, cargando, error } = useApi(() => api.get('/bitacora/mis-unidades'))
  const unidades = data || []
  useEffect(() => {
    if (unidades.length === 1) navegar(`/bitacora/${unidades[0].id}`, { replace: true })
  }, [unidades, navegar])

  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="err">{error}</Aviso>
  if (!unidades.length) {
    return <Empty icono={IcoBitacora}>No tienes ninguna unidad a tu nombre.</Empty>
  }
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Libro de bitácora</h1>
      <Card title="¿De cuál unidad?">
        {unidades.map((u) => (
          <button key={u.id} className="btn block" style={{ marginBottom: 8 }}
                  onClick={() => navegar(`/bitacora/${u.id}`)}>
            {u.num_economico}
            {u.la_traigo ? ' · la traigo hoy' : u.soy_titular ? ' · soy titular' : ''}
          </button>
        ))}
      </Card>
    </>
  )
}

function Libro({ unidadId, usuario }) {
  const navegar = useNavigate()
  const { data, cargando, error, recargar } = useApi(
    () => api.get(`/bitacora/unidad/${unidadId}`), [unidadId])
  const [folio, setFolio] = useState('')
  const [editando, setEditando] = useState(false)

  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="err">{error}</Aviso>

  const { cabecera: c, asientos, integridad, ultimo, faltan_datos_nom030: faltan } = data
  const puedeEditar = ['administrador', 'gerente'].some((r) => usuario?.roles?.includes(r))
  // Abierta desde el historial del gerente llega en pestaña nueva: ahí no hay
  // «atrás» al que volver, y el botón lleva al inicio de su módulo.
  const volver = () => (window.history.length > 1 ? navegar(-1) : navegar('/'))

  const folios = [...new Set(asientos.map((a) => a.folio).filter(Boolean))]
  const visibles = folio ? asientos.filter((a) => a.folio === folio) : asientos
  const transcritos = visibles.filter((a) => a.tipo === 'migracion')
  const propios = visibles.filter((a) => a.tipo !== 'migracion')

  return (
    <div className="libro">
      <div className="card-head no-print">
        <button className="btn sm" onClick={volver}>
          <IcoVolver size={13} className="ico-inline" aria-hidden="true" /> Volver
        </button>
        <div className="btn-row" style={{ marginLeft: 'auto' }}>
          {puedeEditar && (
            <button className="btn" onClick={() => setEditando(true)}>Datos de identificación</button>
          )}
          <button className="btn" onClick={() => window.print()}>
            <IcoImprimir size={13} className="ico-inline" aria-hidden="true" /> Imprimir
          </button>
        </div>
      </div>

      {/* ------------------------------------------------ 7.1.10 c) cabecera */}
      <section className="libro-cabecera">
        <div className="libro-titulo">
          <IcoBitacora size={22} aria-hidden="true" className="no-print" />
          <div>
            <h1>Libro de bitácora de mantenimiento</h1>
            <div className="s">PROY-NOM-030-ASEA-2026 · numeral 7.1.10 · bitácora electrónica</div>
          </div>
        </div>
        <div className="libro-datos">
          <Dato etiqueta="Denominación o razón social" valor={c.razon_social} />
          <Dato etiqueta="Número de permiso" valor={c.permiso}
                falta={c.es_unidad_distribucion} />
          <Dato etiqueta="Número económico" valor={c.num_economico} fuerte />
          <Dato etiqueta="Clase (NOM-030)"
                valor={c.clase_nom030 || `${c.tipo_unidad || 'sin tipo'} · no es Unidad de Distribución`} />
          <Dato etiqueta="Marca / modelo / año"
                valor={[c.marca, c.modelo, c.anio].filter(Boolean).join(' ') || null} />
          <Dato etiqueta="Número de serie" valor={c.serie} />
          <Dato etiqueta="Placas" valor={c.placas} />
          <Dato etiqueta="Operador(es)" valor={c.operadores.join(', ') || null}
                falta={c.es_unidad_distribucion} />
          <Dato etiqueta="Personal auxiliar" valor={c.personal_auxiliar}
                falta={c.es_unidad_distribucion} />
        </div>
      </section>

      {faltan.length > 0 && (
        <div className="no-print">
          <Aviso tipo="warn">
            Falta capturar {faltan.join(', ')}. La NOM-030 (7.1.10 c) pide estos datos en el
            libro de cada Auto-tanque y Vehículo de Reparto.
            {puedeEditar ? ' Captúralos con «Datos de identificación».'
                         : ' Pídeselos al administrador del taller o al gerente.'}
          </Aviso>
        </div>
      )}

      {/* --------------------------------------------- integridad del libro */}
      {integridad.integra ? (
        <Aviso tipo="ok">
          <strong>Libro íntegro.</strong> {integridad.asientos} asiento(s), numerados sin
          huecos y encadenados: ninguno cambió desde que se registró.
        </Aviso>
      ) : (
        <Aviso tipo="err">
          <strong>El libro no cuadra.</strong> {integridad.motivo} Esto no lo puede causar
          la aplicación: alguien modificó la base de datos por fuera. Avisa al responsable
          del sistema.
        </Aviso>
      )}

      {folios.length > 1 && (
        <div className="field no-print" style={{ maxWidth: 260 }}>
          <label>Mostrar</label>
          <select value={folio} onChange={(e) => setFolio(e.target.value)}>
            <option value="">Todo el libro</option>
            {folios.map((f) => <option key={f} value={f}>Formato {f}</option>)}
          </select>
        </div>
      )}

      {!asientos.length && (
        <Empty icono={IcoBitacora}>
          Esta unidad todavía no tiene registros. El libro se abre solo la primera vez
          que entra al taller.
        </Empty>
      )}

      {propios.length > 0 && (
        <section className="libro-seccion">
          <h2>Registros</h2>
          {propios.map((a) => <Asiento key={a.id} a={a} />)}
        </section>
      )}

      {/* Separados y rotulados: se capturaron antes de que existiera el libro,
          sin inicio, término ni resultado por actividad. Se conservan como
          historial, pero no se presentan como evidencia de 7.1.9. */}
      {transcritos.length > 0 && (
        <section className="libro-seccion">
          <h2>Registros anteriores a la bitácora electrónica</h2>
          <p className="libro-nota">
            Formatos capturados antes del {data.libro_desde ? fmtFecha(data.libro_desde) : 'inicio del libro'},
            transcritos tal como estaban. No traen las fechas de inicio y término ni el
            resultado por actividad que pide el numeral 7.1.9.
          </p>
          {transcritos.map((a) => <Asiento key={a.id} a={a} />)}
        </section>
      )}

      {/* El ancla del papel: con el número y la huella del último asiento
          impresos, un libro entregado antes demuestra si después se quitó algo. */}
      {ultimo && (
        <footer className="libro-pie">
          <div>
            Último asiento: <strong>{ultimo.numero}</strong> · registrado el{' '}
            {fmtFechaHoraAnio(ultimo.registrado_en)}
          </div>
          <div className="huella">Huella del último asiento: {ultimo.hash}</div>
          <div>
            Consultado el {fmtFechaHoraAnio(new Date())} por {usuario?.nombre}{' '}
            {usuario?.apellidos || ''}
          </div>
        </footer>
      )}

      <div className="no-print">
        <Regla>
          NOM-030 7.1.10: cada asiento lleva la fecha, la hora y el nombre de quien lo
          registró, y los pone el sistema, no quien captura. Ningún asiento se edita ni se
          borra —la base de datos lo impide—: una corrección es un asiento nuevo que dice
          a cuál corrige. Consultan este libro el operador de la unidad, el administrador y
          el jefe de mantenimiento del taller, los mecánicos de planta, el supervisor y el
          gerente.
        </Regla>
      </div>

      {editando && (
        <ModalIdentificacion unidadId={unidadId} cabecera={c}
                             onCerrar={() => setEditando(false)}
                             onListo={() => { setEditando(false); recargar() }} />
      )}
    </div>
  )
}

function Dato({ etiqueta, valor, falta = false, fuerte = false }) {
  return (
    <div className="fmt-dato">
      <span className="lbl">{etiqueta}</span>
      <span className={`val ${fuerte ? 'fuerte' : ''}`}>
        {valor || (falta ? <span className="falta">Sin capturar</span> : '—')}
      </span>
    </div>
  )
}

function Asiento({ a }) {
  const esActividad = a.fecha_inicio || a.fecha_termino || a.resultado || a.responsable_nombre
  return (
    <article className={`asiento ${a.tipo}`}>
      <header>
        <span className="num">{a.numero}</span>
        <span className="tipo">
          {TIPO[a.tipo] || a.tipo}{a.folio ? ` · ${a.folio}` : ''}
        </span>
        {a.corrige_a_numero && (
          <span className="corrige">↳ corrige el asiento {a.corrige_a_numero}</span>
        )}
        <span className="quien">
          {fmtFechaHoraAnio(a.registrado_en)} · {a.registrado_por_nombre}
        </span>
      </header>
      <p className="desc">{a.descripcion}</p>
      {/* 7.1.10 c) como era AL ENTRAR: la cabecera dice los datos de hoy, y
          sin esto el libro atribuiría una visita de hace un año al permiso y
          al personal auxiliar de hoy. */}
      {a.identificacion && (
        <p className="ident">
          Al entrar: permiso {a.identificacion.permiso || 'sin capturar'} ·{' '}
          operador(es) {(a.identificacion.operadores || []).join(', ') || '—'} ·{' '}
          personal auxiliar {a.identificacion.personal_auxiliar || 'sin capturar'}
        </p>
      )}
      {esActividad && (
        <dl className="campos">
          {(a.fecha_inicio || a.fecha_termino) && (
            // En una actividad son las fechas de 7.1.9; en la entrada, la salida
            // o un formato transcrito, son las de la estancia en el taller.
            <div><dt>{ESTANCIA.has(a.tipo) ? 'En el taller' : 'Se llevó a cabo'}</dt>
              <dd>{fmtFecha(a.fecha_inicio)}{a.fecha_termino ? ` al ${fmtFecha(a.fecha_termino)}` : ''}</dd></div>
          )}
          {a.resultado && (
            <div><dt>Resultado</dt>
              <dd className={a.resultado}>{RESULTADO[a.resultado] || a.resultado}</dd></div>
          )}
          {a.responsable_nombre && (
            <div><dt>Responsable</dt><dd>{a.responsable_nombre}</dd></div>
          )}
          {a.acciones_requeridas && (
            <div className="ancho"><dt>Acciones requeridas</dt>
              <dd className="pre">{a.acciones_requeridas}</dd></div>
          )}
        </dl>
      )}
      <div className="huella" title={a.hash}>{a.hash.slice(0, 12)}</div>
    </article>
  )
}

/* ------------------------------------------------------ 7.1.10 c) captura -- */
function ModalIdentificacion({ unidadId, cabecera, onCerrar, onListo }) {
  const toast = useToast()
  const regulado = useApi(() => api.get('/bitacora/regulado'))
  const ayudantes = useApi(() => api.get('/bitacora/ayudantes'))
  const [general, setGeneral] = useState(null)
  const [propio, setPropio] = useState({
    personal_auxiliar: cabecera.personal_auxiliar || '',
    permiso_hidrocarburos: cabecera.permiso_propio ? cabecera.permiso : '',
    razon_social_regulado: cabecera.razon_social_propia ? cabecera.razon_social : '',
  })
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    if (regulado.data && general === null) setGeneral(regulado.data)
  }, [regulado.data, general])

  const guardar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try {
      if (general && (general.razon_social !== regulado.data.razon_social
                      || general.permiso !== regulado.data.permiso)) {
        await api.post('/bitacora/regulado', general)
      }
      await api.post(`/bitacora/unidad/${unidadId}/identificacion`, propio)
      toast('Datos guardados')
      onListo()
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setEnviando(false)
    }
  }

  if (regulado.cargando || !general) return <Modal titulo="Datos de identificación" onClose={onCerrar}><Spinner /></Modal>

  return (
    <Modal titulo={`Datos de identificación · ${cabecera.num_economico}`} onClose={onCerrar}>
      <form onSubmit={guardar}>
        <h3 style={{ marginBottom: 8 }}>De toda la empresa</h3>
        <div className="field">
          <label>Denominación o razón social</label>
          <input required minLength={3} value={general.razon_social}
                 onChange={(e) => setGeneral({ ...general, razon_social: e.target.value })} />
        </div>
        <div className="field">
          <label>Número de permiso (autoridad del Sector Hidrocarburos)</label>
          <input value={general.permiso} placeholder="Tal como viene en el permiso"
                 onChange={(e) => setGeneral({ ...general, permiso: e.target.value })} />
        </div>

        <h3 style={{ margin: '14px 0 8px' }}>De esta unidad</h3>
        <div className="field">
          <label>Personal auxiliar</label>
          <input list="lista-ayudantes" value={propio.personal_auxiliar}
                 placeholder="Nombre del ayudante que va en la unidad"
                 onChange={(e) => setPropio({ ...propio, personal_auxiliar: e.target.value })} />
          <datalist id="lista-ayudantes">
            {(ayudantes.data || []).map((n) => <option key={n} value={n} />)}
          </datalist>
        </div>
        <div className="field">
          <label>Permiso propio (solo si NO es el de la empresa)</label>
          <input value={propio.permiso_hidrocarburos} placeholder="Vacío = el de la empresa"
                 onChange={(e) => setPropio({ ...propio, permiso_hidrocarburos: e.target.value })} />
        </div>
        <div className="field">
          <label>Razón social propia (franquicia)</label>
          <input value={propio.razon_social_regulado} placeholder="Vacío = la de la empresa"
                 onChange={(e) => setPropio({ ...propio, razon_social_regulado: e.target.value })} />
        </div>
        <button className="btn primary block" disabled={enviando}>
          {enviando ? 'Guardando…' : 'Guardar'}
        </button>
        <Regla>
          Cambiar estos datos no reescribe ningún asiento: cada entrada al taller ya guardó
          el permiso y la razón social que tenía ese día. El cambio queda en la bitácora de
          auditoría con el valor anterior.
        </Regla>
      </form>
    </Modal>
  )
}
