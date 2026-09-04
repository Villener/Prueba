/** CU-ADM-26/27/28/29 — REPORTE DE MANTENIMIENTO.
 *
 * Es el formato de papel de Álamos, tecleado. La pantalla sigue el papel de
 * arriba abajo y en el mismo orden: tipo de servicio, datos de la unidad,
 * revisión rápida, notas al ingresar, los diez sistemas, comentarios y las
 * cinco firmas. Quien captura tiene la hoja al lado y va copiando; reordenar
 * los campos «porque en pantalla se ve mejor» convierte una captura de dos
 * minutos en una búsqueda.
 *
 * Los catálogos NO están escritos aquí: los sirve el backend
 * (`/admin/reportes/catalogo`) desde modules/ordenes/reporte_model.py. Si el
 * cliente cambia el formato, cambia en un solo lugar.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHora, hoyTijuana } from '../../core/api.js'
import {
  Aviso, Badge, BuscadorUnidad, Card, Empty, Modal, Regla, Spinner, useApi, useToast,
} from '../../ui/index.js'
import { Logo } from '../../ui/Logo.jsx'
import { SelectorTaller } from './PlanoTaller.jsx'

/* La casilla del papel. Tres estados y no un ✔/✗ porque la casilla en blanco
   del formato no distingue «lo revisé y está bien» de «no lo revisé», y esa es
   justo la diferencia que importa cuando falta un extintor. */
const CICLO_ESTADO = { sin_revisar: 'bien', bien: 'mal', mal: 'no_aplica', no_aplica: 'sin_revisar' }
const MARCA_ESTADO = { bien: '✓', mal: '✗', no_aplica: 'N/A', sin_revisar: '' }
const AYUDA_ESTADO = {
  sin_revisar: 'sin revisar', bien: 'bien', mal: 'con falla', no_aplica: 'no aplica',
}

const ETIQUETA_AREA = {
  reparto: 'Reparto', pipas: 'Pipas', utilitarias: 'Utilitarias',
  operaciones: 'Operaciones', ventas: 'Ventas', otros: 'Otros',
}
const ETIQUETA_NIVEL = {
  vacio: 'E (vacío)', '1/4': '¼', '1/2': '½', '3/4': '¾', lleno: 'F (lleno)',
}

/* ------------------------------------------------------- CU-ADM-26/27/28/29 */
export function ReportesMantenimiento() {
  // El id viaja en la URL y no en el estado: el plano abre el formato de una
  // unidad con un enlace («#/reportes/12»), y sin ruta no habria a donde apuntar.
  const { id } = useParams()
  const navegar = useNavigate()
  const [nuevo, setNuevo] = useState(false)
  const [filtro, setFiltro] = useState('abierto')
  // `criterios` es lo que se teclea; `busqueda` es lo que ya se mando. Tenerlos
  // aparte evita una peticion por cada letra sin meter un temporizador.
  const [criterios, setCriterios] = useState({ q: '', desde: '', hasta: '', tecnico_id: '' })
  const [busqueda, setBusqueda] = useState({ q: '', desde: '', hasta: '', tecnico_id: '' })
  const catalogo = useApi(() => api.get('/admin/reportes/catalogo'))
  const tecnicos = useApi(() => api.get('/admin/tecnicos'))
  // `id` va en las dependencias porque el mismo componente pinta la lista y la
  // hoja: al volver del formato la ruta cambia pero React NO desmonta nada, asi
  // que sin esto la lista seguia mostrando el estado de antes de capturar --
  // firmas que ya se recabaron, tecnicos que ya se asignaron. Y mientras se ve
  // la hoja no se pide la lista: seria una peticion que nadie mira.
  const lista = useApi(
    () => (id ? Promise.resolve(null) : api.get('/admin/reportes', {
      estado: filtro || undefined,
      q: busqueda.q || undefined,
      desde: busqueda.desde || undefined,
      hasta: busqueda.hasta || undefined,
      tecnico_id: busqueda.tecnico_id || undefined,
    })), [filtro, busqueda, id])

  if (catalogo.cargando) return <Spinner />
  if (catalogo.error) return <Aviso tipo="danger">{catalogo.error}</Aviso>

  if (id) {
    return (
      <Hoja id={Number(id)} catalogo={catalogo.data} tecnicos={tecnicos.data || []}
            onVolver={() => navegar('/reportes')} />
    )
  }

  const reportes = lista.data || []
  const set = (k) => (e) => setCriterios({ ...criterios, [k]: e.target.value })
  const buscar = (e) => { e.preventDefault(); setBusqueda(criterios) }
  const limpiar = () => {
    const vacio = { q: '', desde: '', hasta: '', tecnico_id: '' }
    setCriterios(vacio); setBusqueda(vacio)
  }
  const filtrando = Object.values(busqueda).some(Boolean)

  return (
    <>
      <div className="card-head">
        <h1>Reportes de mantenimiento</h1>
        <div className="spacer" />
        <div className="field" style={{ maxWidth: 180, marginBottom: 0 }}>
          <label>Mostrar</label>
          <select value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="abierto">Abiertos</option>
            <option value="cerrado">Cerrados</option>
            <option value="">Todos</option>
          </select>
        </div>
        <button className="btn" onClick={() => setNuevo(true)}>
          + Levantar a mano
        </button>
      </div>

      <Aviso tipo="info">
        El formato se levanta <strong>solo</strong>, al aceptar el ingreso de la unidad, y se
        queda abierto hasta que se recaban las firmas de salida. «Levantar a mano» es para lo
        que entra por la pluma sin haber pedido cita.
      </Aviso>

      {/* Buscar por unidad, por fecha y por trabajador. Los tres se combinan:
          «los formatos de Ramón en agosto» es UNA pregunta, no tres búsquedas
          que el administrador tenga que cruzar de memoria. */}
      <Card title="Buscar">
        <form onSubmit={buscar}>
          <div className="grid g2">
            <div className="field">
              <label>Unidad o folio</label>
              <input value={criterios.q} onChange={set('q')}
                     placeholder="1009, BG-354P, RM-2026-00001…" />
            </div>
            <div className="field">
              <label>Trabajador que aparece en el formato</label>
              <select value={criterios.tecnico_id} onChange={set('tecnico_id')}>
                <option value="">Cualquiera</option>
                {(tecnicos.data || []).map((t) => (
                  <option key={t.id} value={t.id}>{t.nombre} · {t.especialidad}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid g2">
            <div className="field">
              <label>Entró desde</label>
              <input type="date" max={hoyTijuana()} value={criterios.desde}
                     onChange={set('desde')} />
            </div>
            <div className="field">
              <label>Hasta</label>
              <input type="date" max={hoyTijuana()} value={criterios.hasta}
                     onChange={set('hasta')} />
            </div>
          </div>
          <div className="btn-row">
            <button className="btn primary">Buscar</button>
            {filtrando && (
              <button type="button" className="btn" onClick={limpiar}>Limpiar</button>
            )}
          </div>
        </form>
      </Card>

      {lista.cargando ? <Spinner /> : reportes.length === 0 ? (
        <Empty icono="📋">
          {filtrando
            ? 'Ningún formato coincide con esa búsqueda.'
            : 'Sin reportes. Se levantan solos al aceptar un ingreso.'}
        </Empty>
      ) : reportes.map((r) => (
        <Card key={r.id} title={`${r.folio} · ${r.unidad}`}
              actions={<Badge tono={r.estado === 'abierto' ? 'warn' : 'ok'}>{r.estado}</Badge>}>
          <p className="sub">
            {r.taller} · {r.tipo_servicio} · entró {fmtFechaHora(r.fecha_entrada)}
            {r.fecha_salida ? ` · salió ${fmtFechaHora(r.fecha_salida)}`
                            : ` · ${r.horas_en_taller} h en taller`}
          </p>
          <div className="list-item">
            <div className="grow">
              <div className="t">{r.chofer_nombre || 'Chofer sin nombre en el papel'}</div>
              <div className="s">
                {r.kilometraje ? `${r.kilometraje.toLocaleString('es-MX')} km` : 'sin kilometraje'}
                {r.area ? ` · ${ETIQUETA_AREA[r.area] || r.area}` : ''}
                {r.orden_folio ? ` · orden ${r.orden_folio}` : ''}
              </div>
            </div>
            {r.estado === 'abierto' && r.firmas_faltantes.length > 0 && (
              <Badge tono="warn">faltan {r.firmas_faltantes.length} firmas</Badge>
            )}
          </div>
          {/* Dónde está y quién responde por ella: las dos preguntas que el
              administrador hace antes de abrir el formato. */}
          <div className="s" style={{ marginTop: 6 }}>
            {r.espacio ? `📍 ${r.espacio}` : '📍 sin espacio asignado'}
            {r.colocado_por ? ` · la colocó ${r.colocado_por}` : ''}
          </div>
          {r.atendido_por.length > 0 && (
            <div className="btn-row" style={{ marginTop: 6 }}>
              {r.atendido_por.map((t) => (
                <Badge key={t.tecnico_id} tono={t.pendientes ? 'info' : 'ok'}>
                  🔧 {t.tecnico}{t.pendientes ? ` · ${t.pendientes} pend.` : ''}
                </Badge>
              ))}
            </div>
          )}
          <button className="btn block" style={{ marginTop: 10 }}
                  onClick={() => navegar(`/reportes/${r.id}`)}>
            Abrir formato
          </button>
        </Card>
      ))}

      {nuevo && (
        <ModalNuevo catalogo={catalogo.data} onCerrar={() => setNuevo(false)}
                    onListo={(r) => { setNuevo(false); navegar(`/reportes/${r.id}`) }} />
      )}
    </>
  )
}

/* ---------------------------------------------------------------- CU-ADM-26 */
function ModalNuevo({ catalogo, onCerrar, onListo }) {
  const toast = useToast()
  const [unidad, setUnidad] = useState(null)
  const [tallerId, setTallerId] = useState(null)
  const [enviando, setEnviando] = useState(false)
  // La revisión rápida se captura AQUÍ y solo aquí: es el estado en que se
  // recibió la unidad. Dejarla editable después la convertiría en opinión.
  const [puntos, setPuntos] = useState(
    () => Object.fromEntries(catalogo.puntos.map((p) => [p.clave, 'sin_revisar'])))
  const [form, setForm] = useState({
    tipo_servicio: 'correctivo', origen: '', kilometraje: '', area: '', area_otro: '',
    chofer_nombre: '', supervisor_nombre: '', nivel_combustible: '', notas_ingreso: '',
  })
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  // El chofer sale de la unidad: es el POSEEDOR, no el titular (RN-01). Se
  // deja editable porque el papel a veces trae otro nombre a mano.
  useEffect(() => {
    if (unidad) {
      setForm((f) => ({
        ...f,
        chofer_nombre: f.chofer_nombre || unidad.chofer || '',
        kilometraje: f.kilometraje || (unidad.km_actual ? String(unidad.km_actual) : ''),
      }))
      if (unidad.taller_id) setTallerId((t) => t || unidad.taller_id)
    }
  }, [unidad])

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try {
      const r = await api.post('/admin/reportes', {
        unidad_id: unidad.id,
        taller_id: tallerId,
        tipo_servicio: form.tipo_servicio,
        origen: form.origen || null,
        kilometraje: form.kilometraje === '' ? null : Number(form.kilometraje),
        area: form.area || null,
        area_otro: form.area === 'otros' ? (form.area_otro || null) : null,
        chofer_id: unidad.chofer_id || null,
        chofer_nombre: form.chofer_nombre || null,
        supervisor_nombre: form.supervisor_nombre || null,
        nivel_combustible: form.nivel_combustible || null,
        notas_ingreso: form.notas_ingreso || null,
        puntos: Object.entries(puntos).map(([punto, estado]) => ({ punto, estado })),
      })
      onListo(r)
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo="Levantar reporte de mantenimiento" onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="field">
          <label>Unidad</label>
          <BuscadorUnidad elegida={unidad} onElegir={setUnidad}
                          endpoint="/admin/unidades" />
        </div>
        <SelectorTaller valor={tallerId} onCambio={setTallerId} />

        <div className="field">
          <label>Tipo de servicio</label>
          <select value={form.tipo_servicio} onChange={set('tipo_servicio')}>
            {catalogo.tipos_servicio.map((t) => (
              <option key={t} value={t}>{t === 'correctivo' ? 'Correctivo' : 'Preventivo'}</option>
            ))}
          </select>
        </div>

        <div className="grid g2">
          <div className="field">
            <label>Origen</label>
            <input value={form.origen} onChange={set('origen')} placeholder="Planta, ruta…" />
          </div>
          <div className="field">
            <label>Kilometraje</label>
            <input type="number" min="0" inputMode="numeric"
                   value={form.kilometraje} onChange={set('kilometraje')} />
          </div>
        </div>

        <div className="field">
          <label>Nombre del chofer</label>
          <input value={form.chofer_nombre} onChange={set('chofer_nombre')} />
        </div>
        <div className="field">
          <label>Supervisor de unidad</label>
          <input value={form.supervisor_nombre} onChange={set('supervisor_nombre')} />
        </div>

        <div className="field">
          <label>Área</label>
          <select value={form.area} onChange={set('area')}>
            <option value="">Sin marcar</option>
            {catalogo.areas.map((a) => (
              <option key={a} value={a}>{ETIQUETA_AREA[a] || a}</option>
            ))}
          </select>
        </div>
        {form.area === 'otros' && (
          <div className="field">
            <label>¿Cuál?</label>
            <input value={form.area_otro} onChange={set('area_otro')} />
          </div>
        )}

        <div className="field">
          <label>Combustible al ingresar</label>
          <select value={form.nivel_combustible} onChange={set('nivel_combustible')}>
            <option value="">Sin marcar</option>
            {catalogo.niveles_combustible.map((n) => (
              <option key={n} value={n}>{ETIQUETA_NIVEL[n] || n}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Revisión rápida</label>
          <p className="hint" style={{ marginBottom: 8 }}>
            Toca cada punto para ciclar: sin revisar → ✓ bien → ✗ con falla → N/A.
          </p>
          <div className="fmt-revision editable">
            {catalogo.puntos.map((p) => {
              const estado = puntos[p.clave]
              return (
                <button type="button" key={p.clave} className={`fmt-punto ${estado}`}
                        title={`${p.etiqueta}: ${AYUDA_ESTADO[estado]}`}
                        onClick={() => setPuntos({ ...puntos, [p.clave]: CICLO_ESTADO[estado] })}>
                  <span className="marca">{MARCA_ESTADO[estado]}</span>
                  <span className="txt">{p.etiqueta}</span>
                </button>
              )
            })}
          </div>
        </div>

        <div className="field">
          <label>Notas al ingresar</label>
          <textarea value={form.notas_ingreso} onChange={set('notas_ingreso')} />
        </div>

        <button className="btn primary block" disabled={!unidad || !tallerId || enviando}>
          {enviando ? 'Levantando…' : 'Levantar formato'}
        </button>
        <Regla>
          Los diez sistemas se llenan en el formato ya abierto, conforme los mecánicos
          entregan el papel. Una unidad no puede tener dos formatos abiertos a la vez.
        </Regla>
      </form>
    </Modal>
  )
}

/* --------------------------------------------------- la hoja, tal cual sale */
function Hoja({ id, catalogo, tecnicos, onVolver }) {
  const toast = useToast()
  const { data, cargando, error, recargar } = useApi(() => api.get(`/admin/reportes/${id}`), [id])
  const [firmando, setFirmando] = useState(null)
  const [cerrando, setCerrando] = useState(false)

  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="danger">{error}</Aviso>
  const r = data
  const abierto = r.estado === 'abierto'

  return (
    <>
      <div className="card-head no-print">
        <button className="btn sm" onClick={onVolver}>← Reportes</button>
        <div className="spacer" />
        <Badge tono={abierto ? 'warn' : 'ok'}>{r.estado}</Badge>
        <button className="btn" onClick={() => window.print()}>🖨️ Imprimir</button>
        {abierto && (
          <button className="btn primary" onClick={() => setCerrando(true)}>
            Cerrar y sellar salida
          </button>
        )}
      </div>

      <div className="formato">
        <CabeceraFormato r={r} />
        <DatosFormato r={r} />
        <QuienAtiende r={r} />
        <RevisionRapida r={r} />
        <TablaActividades r={r} tecnicos={tecnicos} editable={abierto}
                          onGuardado={recargar} />
        <Comentarios r={r} />
        <Firmas r={r} catalogo={catalogo} editable={abierto}
                onFirmar={(rol) => setFirmando(rol)} />
      </div>

      {!abierto && (
        <div className="no-print">
          <Regla>
            El formato está cerrado. Un papel firmado no se reescribe: si hay que
            corregirlo, se levanta uno nuevo.
          </Regla>
        </div>
      )}

      {firmando && (
        <ModalFirma reporte={r} firma={firmando} onCerrar={() => setFirmando(null)}
                    onListo={() => { setFirmando(null); recargar(); toast('Firma registrada') }} />
      )}
      {cerrando && (
        <ModalCierre reporte={r} onCerrar={() => setCerrando(false)}
                     onListo={() => { setCerrando(false); recargar(); toast('Salida sellada') }} />
      )}
    </>
  )
}

function CabeceraFormato({ r }) {
  return (
    <div className="fmt-cabecera">
      {/* El logo real, no el nombre escrito. `Logo` lee src/assets/logo.svg y lo
          inyecta en línea, así que el CSS lo recolorea en tema oscuro y en la
          impresión — un <img> no se puede recolorear. */}
      <div className="fmt-marca">
        <Logo alto={34} />
        <div className="fmt-razon">Compañía de Gas de Tijuana, S.A. de C.V.</div>
      </div>
      <h1 className="fmt-titulo">Reporte de mantenimiento</h1>
      <div className="fmt-folio">
        <span className="lbl">Folio</span>
        <strong>{r.folio}</strong>
        <span className="s">{r.tipo_servicio === 'preventivo' ? 'Preventivo' : 'Correctivo'}</span>
      </div>
    </div>
  )
}

function Dato({ etiqueta, valor }) {
  return (
    <div className="fmt-dato">
      <span className="lbl">{etiqueta}</span>
      <span className="val">{valor || '—'}</span>
    </div>
  )
}

function DatosFormato({ r }) {
  return (
    <section className="fmt-bloque">
      <h2>Datos</h2>
      <div className="fmt-datos">
        <Dato etiqueta="Unidad" valor={r.unidad} />
        <Dato etiqueta="Placas" valor={r.unidad_placas} />
        <Dato etiqueta="Origen" valor={r.origen} />
        <Dato etiqueta="Nombre del chofer" valor={r.chofer_nombre} />
        <Dato etiqueta="Supervisor de unidad" valor={r.supervisor_nombre} />
        <Dato etiqueta="Kilometraje"
              valor={r.kilometraje ? r.kilometraje.toLocaleString('es-MX') : null} />
        <Dato etiqueta="Área"
              valor={r.area === 'otros' ? (r.area_otro || 'Otros')
                                        : (ETIQUETA_AREA[r.area] || null)} />
        <Dato etiqueta="Combustible" valor={ETIQUETA_NIVEL[r.nivel_combustible]} />
        <Dato etiqueta="Entrada" valor={fmtFechaHora(r.fecha_entrada)} />
        <Dato etiqueta="Salida" valor={r.fecha_salida ? fmtFechaHora(r.fecha_salida) : null} />
        <Dato etiqueta="Taller" valor={r.taller} />
        <Dato etiqueta="Espacio" valor={r.espacio} />
        <Dato etiqueta="Orden de servicio" valor={r.orden_folio} />
        {/* Qué administrador metió esta unidad a esa casilla. Cada uno atiende
            sus vehículos, y sin el dato nadie sabe a quién preguntarle. */}
        <Dato etiqueta="La colocó" valor={r.colocado_por} />
        <Dato etiqueta="Capturó el formato" valor={r.capturado_por} />
      </div>
    </section>
  )
}

/** Quién está atendiendo AHORA este vehículo.
 *
 * No sale de una columna: sale de que alguien tiene un sistema a su nombre. Se
 * distingue al que todavía debe trabajo del que ya entregó el suyo, porque son
 * preguntas distintas — «¿a quién le pregunto?» y «¿quién respondió por esto?».
 */
function QuienAtiende({ r }) {
  if (!r.atendido_por.length) {
    return (
      <section className="fmt-bloque no-print">
        <h2>Quién atiende</h2>
        <p className="sub">
          Nadie asignado todavía. Se asigna al capturar las actividades: cada sistema
          del vehículo tiene su responsable.
        </p>
      </section>
    )
  }
  // `no-print`: en el papel estos mismos nombres ya están en la columna
  // RESPONSABLE de la tabla de actividades. Imprimirlos aparte gastaba un
  // tercio de la hoja en repetirse, y el formato tiene que caber en una.
  return (
    <section className="fmt-bloque no-print">
      <h2>Quién atiende</h2>
      <div className="fmt-atiende">
        {r.atendido_por.map((t) => (
          <div key={t.tecnico_id} className={`fmt-quien ${t.pendientes ? 'activo' : ''}`}>
            <div className="t">{t.tecnico}</div>
            <div className="s">{t.especialidad}</div>
            <div className="s">
              {t.sistemas.length} sistema{t.sistemas.length === 1 ? '' : 's'}
              {t.pendientes ? ` · ${t.pendientes} sin entregar` : ' · todo entregado'}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function RevisionRapida({ r }) {
  return (
    <section className="fmt-bloque">
      <h2>Revisión rápida</h2>
      <div className="fmt-revision">
        {r.puntos.map((p) => (
          <div key={p.punto} className={`fmt-punto ${p.estado}`}>
            <span className="marca">{MARCA_ESTADO[p.estado]}</span>
            <span className="txt">{p.etiqueta}</span>
          </div>
        ))}
      </div>
      {r.notas_ingreso && (
        <div className="fmt-notas">
          <span className="lbl">Notas al ingresar</span>
          <p>{r.notas_ingreso}</p>
        </div>
      )}
    </section>
  )
}

/* ---------------------------------------------------------------- CU-ADM-27 */
function TablaActividades({ r, tecnicos, editable, onGuardado }) {
  const toast = useToast()
  const [edicion, setEdicion] = useState(null)   // null = no se está editando
  const [guardando, setGuardando] = useState(false)
  const [reasignando, setReasignando] = useState(null)

  const empezar = () => setEdicion(Object.fromEntries(r.actividades.map((a) => [
    a.sistema,
    { a_realizar: a.a_realizar || '', realizada: a.realizada || '', tecnico_id: a.tecnico_id || '' },
  ])))

  const cambiar = (sistema, campo, valor) =>
    setEdicion({ ...edicion, [sistema]: { ...edicion[sistema], [campo]: valor } })

  const guardar = async () => {
    setGuardando(true)
    try {
      await api.post(`/admin/reportes/${r.id}/actividades`, {
        actividades: Object.entries(edicion).map(([sistema, v]) => ({
          sistema,
          a_realizar: v.a_realizar || null,
          realizada: v.realizada || null,
          tecnico_id: v.tecnico_id === '' ? null : Number(v.tecnico_id),
        })),
      })
      setEdicion(null)
      onGuardado()
      toast('Actividades capturadas')
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="fmt-bloque">
      <div className="card-head">
        <h2>Actividades</h2>
        <div className="spacer" />
        {editable && !edicion && (
          <button className="btn sm no-print" onClick={empezar}>Capturar</button>
        )}
        {edicion && (
          <div className="btn-row no-print">
            <button className="btn sm" onClick={() => setEdicion(null)}>Cancelar</button>
            <button className="btn sm primary" disabled={guardando} onClick={guardar}>
              {guardando ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        )}
      </div>

      <div className="table-wrap">
        <table className="fmt-actividades">
          <thead>
            <tr>
              <th>Sistema</th>
              <th>Actividades a realizar</th>
              <th>Actividades realizadas</th>
              <th>Responsable</th>
            </tr>
          </thead>
          <tbody>
            {r.actividades.map((a) => {
              const e = edicion?.[a.sistema]
              return (
                <tr key={a.sistema}>
                  <th scope="row">{a.etiqueta}</th>
                  <td>
                    {e ? (
                      <textarea rows={2} value={e.a_realizar}
                                onChange={(ev) => cambiar(a.sistema, 'a_realizar', ev.target.value)} />
                    ) : (a.a_realizar || <span className="renglon" />)}
                  </td>
                  <td>
                    {e ? (
                      <textarea rows={2} value={e.realizada}
                                onChange={(ev) => cambiar(a.sistema, 'realizada', ev.target.value)} />
                    ) : (a.realizada || <span className="renglon" />)}
                  </td>
                  <td>
                    {e ? (
                      <select value={e.tecnico_id}
                              onChange={(ev) => cambiar(a.sistema, 'tecnico_id', ev.target.value)}>
                        <option value="">—</option>
                        {tecnicos.map((t) => (
                          <option key={t.id} value={t.id}>{t.nombre}</option>
                        ))}
                      </select>
                    ) : a.tecnico ? (
                      <>
                        <div>{a.tecnico}</div>
                        {a.fecha_realizada && (
                          <div className="s">{fmtFecha(a.fecha_realizada)}</div>
                        )}
                        {editable && (
                          <button className="btn sm no-print" style={{ marginTop: 4 }}
                                  onClick={() => setReasignando(a)}>
                            Reasignar
                          </button>
                        )}
                      </>
                    ) : <span className="renglon" />}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {editable && (
        <div className="no-print">
          <Regla>
            CU-ADM-27 · RN-11: el mecánico no teclea. Tú capturas lo que entregó en papel y
            el sistema guarda los dos responsables: quién lo hizo y quién lo capturó.
          </Regla>
        </div>
      )}

      {reasignando && (
        <ModalReasignar reporte={r} actividad={reasignando} tecnicos={tecnicos}
                        onCerrar={() => setReasignando(null)}
                        onListo={() => {
                          setReasignando(null); onGuardado(); toast('Responsable reasignado')
                        }} />
      )}
    </section>
  )
}

/* ---------------------------------------------------------------- CU-ADM-30 */
function ModalReasignar({ reporte, actividad, tecnicos, onCerrar, onListo }) {
  const toast = useToast()
  const [tecnicoId, setTecnicoId] = useState('')
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try {
      await api.post(`/admin/reportes/${reporte.id}/reasignar`, {
        sistema: actividad.sistema,
        tecnico_id: tecnicoId === '' ? null : Number(tecnicoId),
        motivo: motivo.trim(),
      })
      onListo()
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo={`Reasignar · ${actividad.etiqueta}`} onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="unidad-trabajo">
          <span className="lbl">Responsable actual</span>
          <strong>{actividad.tecnico || 'sin asignar'}</strong>
          <span className="s">{reporte.unidad} · {reporte.folio}</span>
        </div>
        <div className="field">
          <label>Nuevo responsable</label>
          <select value={tecnicoId} onChange={(e) => setTecnicoId(e.target.value)}>
            <option value="">Dejarlo sin asignar</option>
            {tecnicos.filter((t) => t.id !== actividad.tecnico_id).map((t) => (
              <option key={t.id} value={t.id}>{t.nombre} · {t.especialidad}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>¿Por qué se reasigna?</label>
          <input required minLength={4} value={motivo} autoFocus
                 placeholder="Lo mandaron a la ruta de Tecate, se fue de incapacidad…"
                 onChange={(e) => setMotivo(e.target.value)} />
        </div>
        <button className="btn primary block" disabled={enviando || motivo.trim().length < 4}>
          {enviando ? 'Reasignando…' : 'Reasignar responsable'}
        </button>
        <Regla>
          El motivo es obligatorio. Reasignar no es corregir un dato mal tecleado: es que a
          alguien se le atravesó otro trabajo, y eso hay que poder explicarlo después. Queda
          en bitácora con el nombre anterior.
        </Regla>
      </form>
    </Modal>
  )
}

function Comentarios({ r }) {
  return (
    <section className="fmt-bloque">
      <h2>Comentarios adicionales</h2>
      {r.comentarios_adicionales
        ? <p className="fmt-parrafo">{r.comentarios_adicionales}</p>
        : <span className="renglon ancho" />}
    </section>
  )
}

/* ---------------------------------------------------------------- CU-ADM-28 */
function Firmas({ r, catalogo, editable, onFirmar }) {
  const puestas = Object.fromEntries(r.firmas.map((f) => [f.rol_firma, f]))
  return (
    <section className="fmt-bloque">
      <h2>Firmas</h2>
      <div className="fmt-firmas">
        {catalogo.firmas.map((c) => {
          const f = puestas[c.clave]
          const obligatoria = r.firmas_faltantes.includes(c.clave)
          return (
            <div key={c.clave} className={`fmt-firma ${f?.nombre ? 'puesta' : ''}`}>
              <div className="raya">{f?.nombre || ''}</div>
              <div className="pie">{c.etiqueta}</div>
              <div className="quien">{c.quien}</div>
              {f?.nombre ? (
                <div className="s">
                  {fmtFechaHora(f.fecha)}
                  {f.registrada_por ? ` · registró ${f.registrada_por}` : ''}
                </div>
              ) : editable ? (
                <button className="btn sm no-print" onClick={() => onFirmar(c)}>
                  Registrar firma{obligatoria ? ' *' : ''}
                </button>
              ) : <div className="s">Sin firma</div>}
            </div>
          )
        })}
      </div>
      {editable && r.firmas_faltantes.length > 0 && (
        <div className="no-print">
          <Aviso tipo="warn">
            * Sin el <strong>Vo. Bo.</strong> del jefe de mantenimiento y la firma de{' '}
            <strong>quien recibe la unidad</strong>, el formato no se puede cerrar.
          </Aviso>
        </div>
      )}
    </section>
  )
}

function ModalFirma({ reporte, firma, onCerrar, onListo }) {
  const toast = useToast()
  const [nombre, setNombre] = useState('')
  const [enviando, setEnviando] = useState(false)
  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try {
      await api.post(`/admin/reportes/${reporte.id}/firmar`,
                     { rol_firma: firma.clave, nombre: nombre.trim() })
      onListo()
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setEnviando(false)
    }
  }
  return (
    <Modal titulo={firma.etiqueta} onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="unidad-trabajo">
          <span className="lbl">Unidad</span>
          <strong>{reporte.unidad}</strong>
          <span className="s">{reporte.folio}</span>
        </div>
        <div className="field">
          <label>Nombre de quien firmó ({firma.quien.toLowerCase()})</label>
          <input required minLength={2} value={nombre}
                 onChange={(e) => setNombre(e.target.value)} autoFocus />
        </div>
        <button className="btn primary block" disabled={enviando || nombre.trim().length < 2}>
          {enviando ? 'Registrando…' : 'Registrar firma'}
        </button>
        <Regla>
          El sistema no firma nada: la firma es de tinta y está en el papel. Esto deja
          constancia de que alguien la vio, de quién la dio y de cuándo.
        </Regla>
      </form>
    </Modal>
  )
}

/* ---------------------------------------------------------------- CU-ADM-29 */
function ModalCierre({ reporte, onCerrar, onListo }) {
  const toast = useToast()
  const [form, setForm] = useState({
    comentarios: reporte.comentarios_adicionales || '',
    operacion: '',
    operativa: true,
  })
  const [enviando, setEnviando] = useState(false)
  const faltan = reporte.firmas_faltantes.length > 0

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try {
      await api.post(`/admin/reportes/${reporte.id}/cerrar`, {
        comentarios_adicionales: form.comentarios || null,
        operacion_a_realizar: form.operacion || null,
        unidad_operativa: form.operativa,
      })
      onListo()
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo={`Sellar salida · ${reporte.folio}`} onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="unidad-trabajo">
          <span className="lbl">Unidad</span>
          <strong>{reporte.unidad}</strong>
          <span className="s">{reporte.taller}{reporte.espacio ? ` · ${reporte.espacio}` : ''}</span>
        </div>
        {faltan && (
          <Aviso tipo="warn">
            Faltan firmas obligatorias. Regístralas antes de cerrar: el servidor lo va a
            rechazar de todos modos.
          </Aviso>
        )}

        {/* Cerrar el formato ES la salida: se libera el cajón, se cierra la
            orden y la unidad deja de estar en el taller. Por eso aquí se
            pregunta lo que antes pedía el formato de salida por separado. */}
        <Aviso tipo="info">
          Al cerrar, la unidad <strong>sale del taller</strong>: se libera{' '}
          {reporte.espacio ? <strong>{reporte.espacio}</strong> : 'su espacio'} y se cierra
          la orden {reporte.orden_folio || ''}.
        </Aviso>

        <div className="field">
          <label>Operación a realizar al salir</label>
          <textarea value={form.operacion} placeholder="Reparto zona centro, regresa a ruta…"
                    onChange={(e) => setForm({ ...form, operacion: e.target.value })} />
        </div>
        <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}>
          <input type="checkbox" style={{ width: 20, height: 20 }} checked={form.operativa}
                 onChange={(e) => setForm({ ...form, operativa: e.target.checked })} />
          <span>La unidad sale operativa</span>
        </label>

        <div className="field">
          <label>Comentarios adicionales</label>
          <textarea value={form.comentarios}
                    onChange={(e) => setForm({ ...form, comentarios: e.target.value })} />
        </div>
        <button className="btn primary block" disabled={enviando || faltan}>
          {enviando ? 'Cerrando…' : 'Cerrar formato y sacar la unidad'}
        </button>
        <Regla>
          La hora de salida la pone el sistema, no se teclea: es la constancia de cuándo
          la unidad cruzó la pluma de regreso. Si no sale operativa, sale igual del taller
          —queda como <em>varada</em>—: seguir marcándola «en taller» sin cajón hacía que
          el plano y el tablero del gerente dijeran cosas distintas.
        </Regla>
      </form>
    </Modal>
  )
}
