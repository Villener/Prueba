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
import { Fragment, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  api, diaTijuana, fmtFecha, fmtFechaHora, fmtFechaHoraAnio, hoyTijuana,
} from '../../core/api.js'
import { comprimir, kb } from '../../core/imagen.js'
import {
  Aviso, Badge, BuscadorUnidad, Card, Empty, IcoBitacora, IcoImprimir, IcoReportes,
  IcoTecnico, IcoUbicacion, IcoVolver, Modal, Regla, Spinner, TiraFotos, useApi, useToast,
} from '../../ui/index.js'
import { Logo } from '../../ui/Logo.jsx'
import { FirmaTrazo, LienzoFirma } from '../../ui/Firma.jsx'
import { getUser } from '../../core/sesion.js'
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

/* NOM-030 7.1.10: el resultado de cada actividad contra su criterio de
   aceptación o rechazo. Dos valores y no tres: «a medias» es una actividad que
   todavía no se da por realizada. */
const RESULTADO = { conforme: 'Conforme', no_conforme: 'No conforme' }
// Valor del <select> de responsable cuando el trabajo lo hizo alguien fuera del
// catálogo (una llantera, la agencia). No choca con ningún id: los ids son números.
const EXTERNO = 'externo'

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
            onVolver={() => navegar('/reportes')}
            onLibro={(unidadId) => navegar(`/bitacora/${unidadId}`)} />
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
        <Empty icono={IcoReportes}>
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
            <><IcoUbicacion size={13} className="ico-inline" aria-hidden="true" />{r.espacio || 'sin espacio asignado'}</>
            {r.colocado_por ? ` · la colocó ${r.colocado_por}` : ''}
          </div>
          {r.atendido_por.length > 0 && (
            <div className="btn-row" style={{ marginTop: 6 }}>
              {r.atendido_por.map((t) => (
                <Badge key={t.tecnico_id} tono={t.pendientes ? 'info' : 'ok'}>
                  <IcoTecnico size={13} className="ico-inline" aria-hidden="true" /> {t.tecnico}{t.pendientes ? ` · ${t.pendientes} pend.` : ''}
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

/* ------------------------------------------- que el formato quepa en UNA hoja */
/* El cliente entrega UNA hoja por servicio. Vacio el formato cabe de sobra,
   pero los diez renglones de actividades se llenan con lo que el mecanico
   escribio a mano, y con las dos columnas de texto puestas se pasa de los
   996 px de alto util que tiene una carta con margen de 8 mm. Ahi se partia en
   dos, y con fotos de evidencia no habia ni que llenarlas.

   No hay manera de pedirle a CSS «que quepa»: hay que medirlo. Y medirlo en
   pantalla no sirve, porque en pantalla el formato usa otros tamanos de letra y
   el ancho del monitor. Por eso se mide justo antes de imprimir, con las reglas
   de impresion ya aplicadas. */

/* px por milimetro: el navegador arma la hoja a 96 dpi, pase lo que pase la
   impresora despues. */
const MM = 96 / 25.4
/* El alto de una carta (279.4 mm) menos los 8 mm de margen de @page arriba y
   abajo. El ancho lo pone el CSS, que es donde se arma la hoja. */
const ALTO_UTIL_MM = 279.4 - 16
/* Un pelo de holgura. Si la hoja queda a ras, un redondeo del navegador la
   empuja entera a la segunda pagina y la primera sale en blanco -- que es peor
   que partirla. */
const HOLGURA = 0.97
/* Mas apretado que esto, el 8 pt de la tabla ya no se lee en papel. Un formato
   con tanto texto que ni asi cabe se parte, y esta bien: ilegible no sirve. */
const ESCALA_MINIMA = 0.65

/** Corre `hacer()` con las reglas de `@media print` aplicadas de verdad.
 *
 * Les cambia el `print` por `all` un instante y se los devuelve. No se alcanza
 * a ver: nada cede el hilo en medio, asi que el navegador no repinta, y de
 * todas formas iba a cambiar a la vista de impresion enseguida.
 */
function conReglasDeImpresion(hacer) {
  const tocadas = []
  for (const hoja of document.styleSheets) {
    let reglas
    // Una hoja de otro origen no deja leer sus reglas. Hoy no hay ninguna, pero
    // una tipografia de Google metida por cualquier motivo tumbaria esto entero.
    try { reglas = hoja.cssRules } catch { continue }
    for (const r of reglas) {
      if (r.media && r.media.mediaText.includes('print')) {
        tocadas.push([r, r.media.mediaText])
        r.media.mediaText = 'all'
      }
    }
  }
  try {
    return hacer()
  } finally {
    for (const [r, antes] of tocadas) r.media.mediaText = antes
  }
}

/** Mide el formato como va a salir en papel y lo aprieta lo justo para que
 *  quepa. El factor viaja en `--ajuste-hoja`, que solo se usa al imprimir. */
function ajustarAUnaHoja() {
  const formato = document.querySelector('.formato')
  if (!formato) return
  const disponible = ALTO_UTIL_MM * MM * HOLGURA
  const aprieta = (x) => Math.max(ESCALA_MINIMA, Math.min(1, x))
  // Pone un apreton y devuelve lo que mide la hoja con el puesto.
  const probar = (escala) => {
    formato.style.setProperty('--ajuste-hoja', escala)
    return conReglasDeImpresion(() => formato.getBoundingClientRect().height)
  }

  const alto = probar(1)
  if (!alto || alto <= disponible) return

  // Apretar la hoja no la encoge en proporcion: el CSS le divide el ancho entre
  // el mismo factor para que siga llenando el papel a lo ancho, asi que al
  // apretarla tambien se ENSANCHA y el mismo texto cabe en menos renglones. Por
  // eso el factor no sale de una division -- se tantea, partiendo el rango entre
  // el apreton que ya se sabe que cabe y el que no, para dejar la letra lo mas
  // grande que quepa. En papel esa es la diferencia entre leerla y adivinarla.
  let cabe = ESCALA_MINIMA
  let noCabe = 1
  // El primer tanteo por regla de tres siempre se queda corto, pero acota el
  // rango de golpe y ahorra pasadas.
  const aproximado = aprieta(disponible / alto)
  if (probar(aproximado) <= disponible) cabe = aproximado
  else noCabe = aproximado
  for (let i = 0; i < 4; i++) {
    const medio = (cabe + noCabe) / 2
    if (probar(medio) <= disponible) cabe = medio
    else noCabe = medio
  }
  probar(cabe)
}

/* --------------------------------------------------- la hoja, tal cual sale */
function Hoja({ id, catalogo, tecnicos, onVolver, onLibro }) {
  const toast = useToast()
  const { data, cargando, error, recargar } = useApi(() => api.get(`/admin/reportes/${id}`), [id])
  const [firmando, setFirmando] = useState(null)
  const [cerrando, setCerrando] = useState(false)
  const [corrigiendo, setCorrigiendo] = useState(false)

  // `beforeprint` lo dispara igual el boton Imprimir que el Ctrl+P del usuario.
  useEffect(() => {
    window.addEventListener('beforeprint', ajustarAUnaHoja)
    return () => window.removeEventListener('beforeprint', ajustarAUnaHoja)
  }, [])

  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="danger">{error}</Aviso>
  const r = data
  const abierto = r.estado === 'abierto'

  return (
    <>
      <div className="card-head no-print">
        <button className="btn sm" onClick={onVolver}><IcoVolver size={13} className="ico-inline" aria-hidden="true" /> Reportes</button>
        <div className="spacer" />
        <Badge tono={abierto ? 'warn' : 'ok'}>{r.estado}</Badge>
        <button className="btn" onClick={() => onLibro(r.unidad_id)}>
          <IcoBitacora size={13} className="ico-inline" aria-hidden="true" /> Libro de la unidad
        </button>
        <button className="btn" onClick={() => window.print()}><IcoImprimir size={13} className="ico-inline" aria-hidden="true" /> Imprimir</button>
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
        <EvidenciaPreventivo reporteId={r.id} editable={abierto} />
        <Firmas r={r} catalogo={catalogo} editable={abierto}
                onFirmar={(rol) => setFirmando(rol)} />
        <Correcciones r={r} />
      </div>

      {!abierto && (
        <div className="no-print">
          <div className="btn-row" style={{ marginBottom: 8 }}>
            <button className="btn" onClick={() => setCorrigiendo(true)}>Registrar corrección</button>
          </div>
          <Regla>
            El formato está cerrado y ya no cambia. NOM-030 7.1.10 a): si algo quedó mal,
            la corrección es un registro NUEVO en la bitácora que dice qué asiento corrige,
            qué debe decir y por qué. Sale impresa con la hoja.
          </Regla>
        </div>
      )}

      <RegistroEnBitacora r={r} />

      {firmando && (
        <ModalFirma reporte={r} firma={firmando} onCerrar={() => setFirmando(null)}
                    onListo={() => { setFirmando(null); recargar(); toast('Firma registrada') }} />
      )}
      {cerrando && (
        <ModalCierre reporte={r} onCerrar={() => setCerrando(false)}
                     onListo={() => { setCerrando(false); recargar(); toast('Salida sellada') }} />
      )}
      {corrigiendo && (
        <ModalCorreccion reporte={r} onCerrar={() => setCorrigiendo(false)}
                         onListo={() => {
                           setCorrigiendo(false); recargar(); toast('Corrección registrada')
                         }} />
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
      {/* La razón social y el permiso ya no van escritos aquí: los pide la
          NOM-030 (7.1.10 c) y vienen de la configuración o de la unidad, así que
          el día que cambien no hay que tocar la pantalla. */}
      <div className="fmt-marca">
        <Logo alto={34} />
        <div className="fmt-razon">{r.razon_social}</div>
        <div className="fmt-razon">
          Permiso: {r.permiso || <strong className="falta">SIN CAPTURAR</strong>}
        </div>
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

  const [problema, setProblema] = useState(null)

  const empezar = () => {
    setProblema(null)
    setEdicion(Object.fromEntries(r.actividades.map((a) => [
      a.sistema,
      {
        a_realizar: a.a_realizar || '', realizada: a.realizada || '',
        tecnico_id: a.tecnico_id ? String(a.tecnico_id) : (a.responsable_externo ? EXTERNO : ''),
        responsable_externo: a.responsable_externo || '',
        resultado: a.resultado || '', acciones_requeridas: a.acciones_requeridas || '',
        fecha_inicio: a.fecha_inicio || '', fecha_termino: a.fecha_termino || '',
      },
    ])))
  }

  const cambiar = (sistema, campo, valor) => {
    const actual = { ...edicion[sistema], [campo]: valor }
    // «Ninguna» se PROPONE al elegir conforme, a la vista y editable: el campo
    // es obligatorio y en un trabajo conforme casi siempre es la respuesta.
    if (campo === 'resultado' && valor === 'conforme' && !actual.acciones_requeridas.trim()) {
      actual.acciones_requeridas = 'Ninguna'
    }
    // Y se RETIRA al pasar a no conforme: si no cumple, algo hay que hacerle, y
    // un «Ninguna» que se quedó de la opción anterior diría lo contrario.
    if (campo === 'resultado' && valor === 'no_conforme'
        && actual.acciones_requeridas.trim().toLowerCase() === 'ninguna') {
      actual.acciones_requeridas = ''
    }
    // Al dar el sistema por realizado se proponen las fechas de hoy. Se ven y se
    // cambian: el trabajo pudo hacerse ayer y capturarse hoy.
    if (campo === 'realizada' && valor.trim()) {
      actual.fecha_inicio = actual.fecha_inicio || hoyTijuana()
      actual.fecha_termino = actual.fecha_termino || hoyTijuana()
    }
    // Si se borra lo realizado, se va con él todo lo que era de lo realizado:
    // si no, se mandaría un «conforme» con fechas de un trabajo que no existe.
    if (campo === 'realizada' && !valor.trim()) {
      Object.assign(actual, { resultado: '', acciones_requeridas: '',
                              fecha_inicio: '', fecha_termino: '' })
    }
    setEdicion({ ...edicion, [sistema]: actual })
  }

  const guardar = async () => {
    setGuardando(true)
    setProblema(null)
    try {
      await api.post(`/admin/reportes/${r.id}/actividades`, {
        actividades: Object.entries(edicion).map(([sistema, v]) => ({
          sistema,
          a_realizar: v.a_realizar || null,
          realizada: v.realizada || null,
          tecnico_id: v.tecnico_id === '' || v.tecnico_id === EXTERNO ? null : Number(v.tecnico_id),
          responsable_externo: v.tecnico_id === EXTERNO ? (v.responsable_externo || null) : null,
          resultado: v.resultado || null,
          acciones_requeridas: v.acciones_requeridas || null,
          fecha_inicio: v.fecha_inicio || null,
          fecha_termino: v.fecha_termino || null,
        })),
      })
      setEdicion(null)
      onGuardado()
      toast('Actividades capturadas')
    } catch (e) {
      // El 422 de la NOM trae qué le falta a cada sistema: se deja a la vista,
      // junto a la tabla, y no en un aviso que se borra en cuatro segundos.
      if (e.datos?.sistemas_incompletos) setProblema(e.message)
      else toast(e.message, 'err')
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
            <button className="btn sm"
                    onClick={() => { setEdicion(null); setProblema(null) }}>Cancelar</button>
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
              const realizando = e && e.realizada.trim()
              return (
                <Fragment key={a.sistema}>
                <tr>
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
                    ) : a.realizada ? (
                      <>
                        <div>{a.realizada}</div>
                        {a.acciones_requeridas && (
                          <div className="s">Acciones requeridas: {a.acciones_requeridas}</div>
                        )}
                      </>
                    ) : <span className="renglon" />}
                  </td>
                  <td>
                    {e ? (
                      <>
                        <select value={e.tecnico_id}
                                onChange={(ev) => cambiar(a.sistema, 'tecnico_id', ev.target.value)}>
                          <option value="">—</option>
                          {tecnicos.map((t) => (
                            <option key={t.id} value={t.id}>{t.nombre}</option>
                          ))}
                          <option value={EXTERNO}>Otro (externo)…</option>
                        </select>
                        {e.tecnico_id === EXTERNO && (
                          <input className="nom-input" value={e.responsable_externo}
                                 placeholder="Quién lo hizo"
                                 onChange={(ev) => cambiar(a.sistema, 'responsable_externo', ev.target.value)} />
                        )}
                      </>
                    ) : a.responsable ? (
                      <>
                        <div>{a.responsable}</div>
                        {(a.fecha_inicio || a.fecha_termino) ? (
                          <div className="s">{fmtFecha(a.fecha_inicio)} → {fmtFecha(a.fecha_termino)}</div>
                        ) : a.fecha_realizada && (
                          // Renglón de antes de la NOM: solo tiene el sello de terminado.
                          <div className="s">{fmtFecha(a.fecha_realizada)}</div>
                        )}
                        {a.resultado && (
                          <div className={`s resultado ${a.resultado}`}>
                            {a.resultado === 'conforme' ? '✓' : '✗'} {RESULTADO[a.resultado]}
                          </div>
                        )}
                        {a.faltantes_nom030.length > 0 && (
                          <div className="s falta no-print">Falta: {a.faltantes_nom030.join(', ')}</div>
                        )}
                        {editable && a.tecnico_id && (
                          <button className="btn sm no-print" style={{ marginTop: 4 }}
                                  onClick={() => setReasignando(a)}>
                            Reasignar
                          </button>
                        )}
                      </>
                    ) : a.faltantes_nom030.length > 0 ? (
                      <div className="s falta no-print">Falta: {a.faltantes_nom030.join(', ')}</div>
                    ) : <span className="renglon" />}
                  </td>
                </tr>
                {/* Los datos que la NOM pide de lo realizado, en un renglón de
                    ancho completo y solo mientras se captura. Apilados dentro
                    de la columna del responsable quedaban en 42 px a 375 px de
                    ancho: no se leía ni la fecha elegida. */}
                {realizando && (
                  <tr className="nom-fila">
                    <td colSpan={4}>
                      <div className="nom-rejilla">
                        <label className="nom-campo">
                          <span>Inicio</span>
                          <input type="date" max={hoyTijuana()} min={diaTijuana(r.fecha_entrada)}
                                 value={e.fecha_inicio}
                                 onChange={(ev) => cambiar(a.sistema, 'fecha_inicio', ev.target.value)} />
                        </label>
                        <label className="nom-campo">
                          <span>Término</span>
                          <input type="date" max={hoyTijuana()}
                                 min={e.fecha_inicio || diaTijuana(r.fecha_entrada)}
                                 value={e.fecha_termino}
                                 onChange={(ev) => cambiar(a.sistema, 'fecha_termino', ev.target.value)} />
                        </label>
                        <label className="nom-campo">
                          <span>Resultado</span>
                          <select value={e.resultado}
                                  onChange={(ev) => cambiar(a.sistema, 'resultado', ev.target.value)}>
                            <option value="">—</option>
                            <option value="conforme">Conforme</option>
                            <option value="no_conforme">No conforme</option>
                          </select>
                        </label>
                        <label className="nom-campo ancho">
                          <span>Acciones requeridas</span>
                          <textarea rows={1} value={e.acciones_requeridas}
                                    placeholder={e.resultado === 'no_conforme'
                                      ? 'Qué falta para que cumpla' : 'Ninguna'}
                                    onChange={(ev) => cambiar(a.sistema, 'acciones_requeridas', ev.target.value)} />
                        </label>
                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      {problema && (
        <div className="no-print"><Aviso tipo="err">{problema}</Aviso></div>
      )}

      {editable && (
        <div className="no-print">
          <Regla>
            CU-ADM-27 · RN-11: el mecánico no teclea. Tú capturas lo que entregó en papel y
            el sistema guarda los dos responsables: quién lo hizo y quién lo capturó.
            NOM-030 7.1.9 y 7.1.10: un sistema realizado lleva su inicio, su término, su
            resultado, sus acciones requeridas y su responsable. Cada cambio queda en el
            libro de bitácora con lo que decía antes.
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

/* ------------------------------------------------------------- NOM-030 ---- */
/** Correcciones asentadas DESPUÉS del cierre (7.1.10 a).
 *
 *  Van dentro de la hoja y se imprimen: son parte del documento aunque el
 *  formato ya no cambie. Sin ellas, el papel impreso contradiría al libro. */
function Correcciones({ r }) {
  if (!r.correcciones.length) return null
  return (
    <section className="fmt-bloque fmt-correcciones">
      <h2>Correcciones posteriores al cierre</h2>
      {r.correcciones.map((c) => (
        <p key={c.id} className="fmt-parrafo">
          <strong>Asiento {c.numero}</strong>
          {c.corrige_a_numero ? ` (corrige el ${c.corrige_a_numero})` : ''}: {c.descripcion}
          <span className="s"> — {c.registrado_por_nombre}, {fmtFechaHoraAnio(c.registrado_en)}</span>
        </p>
      ))}
    </section>
  )
}

/** Lo que este formato ha dejado en el libro de la unidad, con quién y cuándo.
 *
 *  Fuera de la hoja y sin imprimirse: la hoja tiene que caber en una carta, y
 *  el libro completo se imprime desde su propia página. Aquí sirve para que
 *  quien captura vea, al momento, que lo que guardó quedó asentado. */
function RegistroEnBitacora({ r }) {
  const { data, cargando } = useApi(
    () => api.get(`/bitacora/unidad/${r.unidad_id}`), [r.unidad_id, r.asientos])
  const [abierto, setAbierto] = useState(false)
  if (cargando || !data) return null
  const propios = data.asientos.filter((a) => a.reporte_id === r.id)
  return (
    <section className="card no-print registro-bitacora">
      <div className="card-head">
        <h2>Registro en bitácora · {propios.length} asiento(s)</h2>
        <button className="btn sm" style={{ marginLeft: 'auto' }}
                onClick={() => setAbierto(!abierto)}>
          {abierto ? 'Ocultar' : 'Ver'}
        </button>
      </div>
      {!data.integridad.integra && (
        <Aviso tipo="err">El libro de esta unidad no cuadra: {data.integridad.motivo}</Aviso>
      )}
      {abierto && propios.map((a) => (
        <div key={a.id} className="list-item">
          <div className="grow">
            <div className="t">
              {a.numero}. {a.descripcion}
            </div>
            <div className="s">
              {fmtFechaHoraAnio(a.registrado_en)} · {a.registrado_por_nombre}
              {a.corrige_a_numero ? ` · corrige el ${a.corrige_a_numero}` : ''}
            </div>
          </div>
        </div>
      ))}
    </section>
  )
}

function ModalCorreccion({ reporte, onCerrar, onListo }) {
  const toast = useToast()
  const libro = useApi(() => api.get(`/bitacora/unidad/${reporte.unidad_id}`), [reporte.unidad_id])
  const [form, setForm] = useState({ asiento_id: '', texto: '', motivo: '' })
  const [enviando, setEnviando] = useState(false)
  const asientos = (libro.data?.asientos || []).filter((a) => a.reporte_id === reporte.id)

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try {
      await api.post(`/admin/reportes/${reporte.id}/correcciones`, {
        asiento_id: form.asiento_id === '' ? null : Number(form.asiento_id),
        texto: form.texto.trim(),
        motivo: form.motivo.trim(),
      })
      onListo()
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo={`Registrar corrección · ${reporte.folio}`} onClose={onCerrar}>
      <form onSubmit={enviar}>
        <div className="field">
          <label>¿Qué asiento corrige?</label>
          <select value={form.asiento_id}
                  onChange={(e) => setForm({ ...form, asiento_id: e.target.value })}>
            <option value="">Aclaración al formato completo</option>
            {asientos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.numero}. {a.descripcion.slice(0, 90)}{a.descripcion.length > 90 ? '…' : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>¿Qué debe decir?</label>
          <textarea required minLength={4} rows={3} value={form.texto}
                    onChange={(e) => setForm({ ...form, texto: e.target.value })}
                    placeholder="Ej. Las balatas cambiadas fueron las traseras, no las delanteras" />
        </div>
        <div className="field">
          <label>¿Por qué se corrige?</label>
          <input required minLength={4} value={form.motivo}
                 onChange={(e) => setForm({ ...form, motivo: e.target.value })}
                 placeholder="Error al capturar del papel, dato que llegó después…" />
        </div>
        <button className="btn primary block"
                disabled={enviando || form.texto.trim().length < 4 || form.motivo.trim().length < 4}>
          {enviando ? 'Registrando…' : 'Registrar corrección'}
        </button>
        <Regla>
          El asiento original no se toca: queda como estaba y la corrección se agrega
          después, con tu nombre y la hora que pone el sistema. Así lo pide la NOM-030
          (7.1.10 a) y así se puede explicar frente a un inspector.
        </Regla>
      </form>
    </Modal>
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
              {/* La firma dibujada va ENCIMA de la raya, como en el papel. Las
                  que se registraron antes de la firma en pantalla no traen
                  dibujo: son constancia de una firma de tinta. */}
              {f?.trazo && <FirmaTrazo trazo={f.trazo} titulo={`Firma de ${f.nombre}`} />}
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
                  Firmar{obligatoria ? ' *' : ''}
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

/** Quien firma normalmente cada recuadro, para no teclearlo: el chofer del
 *  formato, su supervisor, o quien esta en sesion para el Vo. Bo. Se puede
 *  cambiar si firmo otra persona. */
function nombreSugerido(reporte, firma) {
  const quien = (firma.quien || '').toLowerCase()
  if (quien.includes('chofer')) return reporte.chofer_nombre || ''
  if (quien.includes('supervisor')) return reporte.supervisor_nombre || ''
  if (quien.includes('jefe')) {
    const yo = getUser()
    return yo ? `${yo.nombre} ${yo.apellidos || ''}`.trim() : ''
  }
  return ''
}

function ModalFirma({ reporte, firma, onCerrar, onListo }) {
  const toast = useToast()
  const [nombre, setNombre] = useState(() => nombreSugerido(reporte, firma))
  const [trazo, setTrazo] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const enviar = async (e) => {
    e.preventDefault()
    if (!trazo) return
    setEnviando(true)
    try {
      await api.post(`/admin/reportes/${reporte.id}/firmar`,
                     { rol_firma: firma.clave, nombre: nombre.trim(), trazo })
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
          <label>Quién firma ({firma.quien.toLowerCase()})</label>
          <input required minLength={2} value={nombre}
                 onChange={(e) => setNombre(e.target.value)} />
        </div>
        <div className="field">
          <label>Firma</label>
          <LienzoFirma onCambio={setTrazo} />
          {!trazo && (
            <p className="hint" style={{ marginTop: 4 }}>
              Pásale el teléfono o la tableta a quien firma: que firme completo, como en el papel.
            </p>
          )}
        </div>
        <button className="btn primary block"
                disabled={enviando || !trazo || nombre.trim().length < 2}>
          {enviando ? 'Guardando…' : 'Guardar firma'}
        </button>
        <Regla>
          Queda guardado el dibujo de la firma, el nombre, la hora y quién estaba en sesión.
          La firma entra al libro de bitácora de la unidad con su huella: si alguien la
          cambiara después, el libro dejaría de salir íntegro.
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
  const [problema, setProblema] = useState(null)
  const faltan = reporte.firmas_faltantes.length > 0
  const incompletas = reporte.actividades.filter((a) => a.faltantes_nom030.length > 0)

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setProblema(null)
    try {
      await api.post(`/admin/reportes/${reporte.id}/cerrar`, {
        comentarios_adicionales: form.comentarios || null,
        operacion_a_realizar: form.operacion || null,
        unidad_operativa: form.operativa,
      })
      onListo()
    } catch (err) {
      // El rechazo del servidor dice QUÉ falta (firmas, foto, datos de la
      // NOM): se queda dentro de la ventana, a la vista, hasta que se resuelva.
      if (err.status === 409 && err.datos) setProblema(err.message)
      else toast(err.message, 'err')
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
        {incompletas.length > 0 && (
          <Aviso tipo="warn">
            A {incompletas.map((a) => a.etiqueta).join(', ')} le faltan datos que pide la
            NOM-030 (inicio, término, resultado, acciones requeridas o responsable).
            Captúralos en la tabla de actividades antes de cerrar.
          </Aviso>
        )}
        {problema && <Aviso tipo="err">{problema}</Aviso>}

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


/* --------------------------------------------------------------- CU-ADM-31 -- */
/** RN-15 — la evidencia fotográfica del preventivo.
 *
 *  La firma prueba que alguien cerró el formato; la foto prueba que el trabajo
 *  se hizo. Hasta hoy solo se exigía la primera, así que un preventivo se podía
 *  dar por hecho sin que nadie hubiera tocado la unidad.
 *
 *  Solo se exige en el PREVENTIVO. Un correctivo entra porque algo se rompió y
 *  su prueba es que la unidad volvió a andar.
 *
 *  Y se comprime en el dispositivo antes de subir (RF-GEN-15): el original de
 *  cámara nunca sale del teléfono.
 */
function EvidenciaPreventivo({ reporteId, editable }) {
  const { data, cargando, recargar } = useApi(
    () => api.get(`/admin/reportes/${reporteId}/evidencia`), [reporteId])
  const [subiendo, setSubiendo] = useState(false)
  const toast = useToast()

  if (cargando) return null
  const d = data || {}
  if (!d.exige_evidencia && !(d.fotos || []).length) return null

  async function elegir(e) {
    const archivo = e.target.files && e.target.files[0]
    e.target.value = ''
    if (!archivo) return
    setSubiendo(true)
    try {
      const original = archivo.size
      const listo = await comprimir(archivo)
      await api.subir(`/admin/reportes/${reporteId}/evidencia`, listo)
      toast(listo.size < original
        ? `Evidencia subida · ${kb(original)} → ${kb(listo.size)}`
        : 'Evidencia subida')
      recargar()
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <section className="fmt-bloque fmt-evidencia">
      <h2>Evidencia del servicio</h2>
      {/* El recordatorio es para quien captura, no para el papel: en un formato
          impreso «todavía no tiene foto» no significa nada. */}
      {!d.cumple && (
        <div className="no-print">
          <Aviso tipo="warn">
            Es un servicio <strong>preventivo</strong> y todavía no tiene foto.
            El formato no se puede cerrar sin ella.
          </Aviso>
        </div>
      )}
      <TiraFotos fotos={d.fotos || []} />
      {editable && (
        <div className="no-print" style={{ marginTop: 8 }}>
          <label className="btn">
            {subiendo ? 'Subiendo…' : 'Agregar foto'}
            <input type="file" accept="image/*" capture="environment" hidden
                   onChange={elegir} disabled={subiendo} />
          </label>
          <Regla>
            La foto se reduce en este dispositivo antes de subirse: se guarda una
            imagen de unos 200 KB, no el original de cámara de 4 MB. Con 5 a 7
            preventivos al día, la diferencia es medio giga al mes contra veinte megas.
          </Regla>
        </div>
      )}
    </section>
  )
}
