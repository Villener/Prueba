/** Modulo Gerente - CU-GER-* de docs/casos-de-uso.md */
import { useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHora, fmtMoneda, hoyTijuana } from '../../core/api.js'
/* La pantalla de Indicadores del taller se IMPORTA del modulo del administrador
   en vez de copiarse aquí. La queja del gerente era literalmente esa: para ver
   estas gráficas tenía que salirse de su módulo y entrar con el correo y la
   contraseña del administrador. Copiar el componente habría quitado la segunda
   contraseña dejando dos pantallas iguales que se separan el día que alguien
   toca una sola — y entonces los dos verían números distintos y cada uno creería
   el suyo. Las cuatro rutas /admin/… que usa (indicadores, meta-preventivo,
   meta-preventivo/serie y talleres) ya aceptan el rol gerente en el servidor
   (`admin_o_gerente` en administrador_controller.py) y las cuatro son de solo
   lectura, así que montarla aquí era lo único que faltaba. */
import { Indicadores } from '../administrador/IndicadoresPage.jsx'
/* Los cuatro historiales —por mecánico, por unidad, por chofer y por taller—
   viven en su propio archivo y no aquí: este ya pasaba de las novecientas líneas
   con cinco pantallas adentro, y la de historiales trae cuatro vistas, cuatro
   detalles y su propio Excel. La pantalla nació de una pregunta concreta del
   gerente: el administrador de taller ya asigna unidades a mecánicos dentro del
   Reporte de Mantenimiento, pero ese dato se quedaba adentro del formato y para
   saber qué le tocó a cada quien había que abrir reporte por reporte. */
import Historiales from './HistorialesPage.jsx'
// Los patios de cada planta (pedido de Tiscareno): van arriba de la pestana Taller.
import { Patios } from './PatiosPage.jsx'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoCampana, IcoDescargar, IcoListo, Kpi, Modal,
  Regla, Spinner, Tabla, useApi, useToast,
} from '../../ui/index.js'

export default function Gerente() {
  return (
    <Routes>
      <Route path="/" element={<Tablero />} />
      <Route path="/incumplimiento" element={<Incumplimiento />} />
      <Route path="/taller" element={<TallerVista />} />
      <Route path="/presupuestos" element={<Presupuestos />} />
      <Route path="/alertas" element={<Alertas />} />
      <Route path="/historiales" element={<Historiales />} />
      <Route path="/indicadores" element={<Indicadores />} />
      {/* «Estadísticas» dejó de ser una pantalla: su contenido vive ahora dentro
          del Tablero, que es lo que el gerente pidió en la junta — todo en una.
          La ruta se queda viva como redirección en vez de borrarse porque este
          enlace está guardado en los favoritos de quien la abría a diario, y un
          enlace guardado que de pronto no lleva a ningún lado no se reporta como
          «cambió la pantalla», se reporta como «se cayó el sistema». */}
      <Route path="/estadisticas" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

/* -------------------------------------------- CU-GER-01/12 · RF-GER-14..18 - */
/** La fecha de calendario que resulta de moverse por días o meses desde otra.
 *
 *  Se arma con el constructor local `new Date(a, m - 1, d)` y se vuelve a
 *  escribir a mano con padStart. NO con toISOString(): eso entrega la fecha en
 *  UTC, y desde las 17:00 de Tijuana en adelante UTC ya va en el día siguiente,
 *  así que el rango que se propone al abrir la pantalla arrancaría un día
 *  corrido cada tarde. Es el mismo error que core/api.js ya documenta en
 *  hoyTijuana(), y aquí reaparecería por la puerta de atrás.
 *
 *  El constructor local además resuelve solo los desbordes, que es justo lo que
 *  se necesita para «once meses hacia atrás»: mes 0 es diciembre del año
 *  anterior y día −8 es el 23 del mes pasado, sin una sola resta a mano.
 */
function fechaYMD(anio, mes, dia) {
  const f = new Date(anio, mes - 1, dia)
  return f.getFullYear() + '-' + String(f.getMonth() + 1).padStart(2, '0')
         + '-' + String(f.getDate()).padStart(2, '0')
}

/** El rango que se propone para cada corte. Es el espejo de `_rango_por_defecto()`
 *  del servidor (gerente_controller.py) y los tres valores son los mismos a
 *  propósito: si dejaran de coincidir, esta pantalla y un enlace que alguien
 *  pegue a mano sin fechas mostrarían periodos distintos y nadie sabría cuál de
 *  los dos números citar.
 *
 *  La ventana depende de la granularidad en vez de ser «doce meses» siempre,
 *  porque doce meses significan cosas distintas en cada corte: por mes son doce
 *  barras que caben en la pantalla, por día son 365 y el tablero se abriría en
 *  un amasijo de rayas verticales del que no se saca ninguna conclusión.
 */
function rangoPorDefecto(gran) {
  const hasta = hoyTijuana()
  const [a, m, d] = hasta.split('-').map(Number)
  if (gran === 'dia') return [fechaYMD(a, m, d - 29), hasta]     // el mes corrido
  if (gran === 'anio') return [fechaYMD(a - 4, 1, 1), hasta]     // el histórico útil
  // Once meses hacia atrás y no doce: el mes que contiene a `hasta` ya cuenta
  // como uno, y restar doce devolvería trece barras.
  return [fechaYMD(a, m - 11, 1), hasta]
}

/** Todo lo que cambia entre las cuatro gráficas del rango, en un solo lugar.
 *
 *  `resumen` es la llave del número grande dentro de `resumen` que devuelve
 *  /gerente/tablero-rango — y no se deduce del `clave` de la serie porque no
 *  coinciden: la serie se llama `dias_reparacion` y el total del rango
 *  `dias_reparacion_prom`. Deducirlo con una concatenación funcionaría hoy y
 *  pintaría «—» para siempre el día que el servidor renombre uno.
 *
 *  `hueco` es lo que el tooltip dice cuando un periodo no tiene dato. No es
 *  adorno: es la diferencia entre «aquí no hubo nada que medir» y «aquí midió
 *  cero», que en una gráfica de barras se ven casi igual y significan lo
 *  contrario.
 */
const SERIES_RANGO = {
  dias_reparacion: {
    color: 'var(--brand)', resumen: 'dias_reparacion_prom', kpi: 'Promedio del rango',
    hueco: 'el taller no cerró ninguna orden en ese periodo, así que no hay reparación '
           + 'que promediar',
  },
  tasa_concretadas: {
    color: 'var(--ok)', resumen: 'tasa_concretadas', kpi: 'Promedio del rango',
    hueco: 'ninguna cita de ese periodo llegó a tener desenlace: ni se cumplió ni se '
           + 'faltó a ella todavía',
  },
  citas_totales: {
    color: 'var(--grafica)', resumen: 'citas_totales', kpi: 'Total del rango',
    hueco: 'no hay citas registradas en ese periodo',
  },
  // Verde y no el rojo de --grafica-alerta, aunque fuera el cuarto color libre:
  // con los datos de hoy esta serie son nueve ceros, y nueve barras rojas a ras
  // de suelo se leen como una alarma cuando lo que dicen es «todavía no hay
  // citas cumplidas». El rojo de gráfica está reservado para lo que de verdad va
  // mal. Comparte el verde con «citas concretadas» a propósito: las dos miden lo
  // mismo desde dos ángulos --las citas que sí se atendieron-- y cada tarjeta
  // lleva su título y su cifra encima de cada barra, así que la identidad de la
  // serie nunca depende solo del color.
  atenciones: {
    color: 'var(--ok)', resumen: 'atenciones', kpi: 'Total del rango',
    hueco: 'no hay citas registradas en ese periodo',
  },
}

/** El valor de una barra, escrito según lo que mide su serie.
 *
 *  Las cuatro series del rango no son cuatro conteos: una trae días con decimal
 *  y otra es un porcentaje. Pintar «87.5» a secas debajo de una barra deja al
 *  gerente adivinando si son citas o por ciento, y el día que lo lea como 87
 *  citas en una junta el número va a estar mal sin que nadie tocara el código.
 *
 *  El `null` se escribe «—» y no «0». Es la regla del repositorio y aquí es
 *  donde más importa: cero días de reparación promedio es una afirmación —se
 *  reparó en el acto—, no un hueco.
 */
function fmtValor(v, unidad) {
  if (v == null) return '—'
  const n = Math.round(v * 10) / 10
  if (unidad === 'pct') return n + '%'
  if (unidad === 'dias') return n + ' d'
  return String(n)
}

/* --------------------------------------------------- preventivo vs correctivo */

const COLOR_MEZCLA = {
  preventivo: 'var(--ok)',
  correctivo: 'var(--grafica)',
  siniestro: 'var(--danger)',
  otros: 'var(--muted)',
}

/** La dona de preventivo contra correctivo.
 *
 *  ES UNA DONA Y NO UN PASTEL, y no es capricho: el agujero de en medio es
 *  donde vive el número que el gerente vino a buscar —el porcentaje de
 *  preventivo—, y leerlo de una cifra es exacto, mientras que leerlo del
 *  ángulo de una rebanada es adivinar. La rebanada da la proporción de un
 *  vistazo; la cifra da el dato.
 *
 *  SE DIBUJA CON UN SOLO CÍRCULO Y `stroke-dasharray`, sin arcos ni
 *  trigonometría. Cada rebanada es el mismo círculo pintado con un guion tan
 *  largo como su porcentaje y desplazado por lo que suman las anteriores. Sale
 *  en una docena de líneas, sin una librería de gráficas de 40 kB, y el
 *  navegador la escala sola.
 *
 *  CADA REBANADA LLEVA SU NÚMERO AL LADO en la leyenda. El color no es nunca el
 *  único portador del dato: quien no distingue el verde del azul lee la tabla y
 *  se entera igual, y quien la imprime en blanco y negro también.
 */
function Dona({ partes, total, meta }) {
  if (!total || !(partes || []).length) {
    return <Empty>Ninguna orden entró al taller en este periodo</Empty>
  }
  // El radio sale de la circunferencia y no al revés: con 100 de perímetro,
  // el porcentaje de cada rebanada ES su largo de guion, sin conversión.
  const r = 100 / (2 * Math.PI)
  let acumulado = 0
  const prev = partes.find((p) => p.clave === 'preventivo')
  const pctPrev = prev ? prev.pct : 0
  // La meta del gerente (80%) es una rayita sobre el anillo: si la rebanada
  // verde no la alcanza, se ve sin leer nada.
  const a = ((meta || 0) / 100) * 2 * Math.PI - Math.PI / 2
  const marca = meta ? {
    x1: 21 + (r - 3.6) * Math.cos(a), y1: 21 + (r - 3.6) * Math.sin(a),
    x2: 21 + (r + 3.6) * Math.cos(a), y2: 21 + (r + 3.6) * Math.sin(a),
  } : null

  return (
    <div className="dona-wrap">
      <svg viewBox="0 0 42 42" className="dona" role="img"
           aria-label={'Reparto del trabajo del taller: '
                       + partes.map((p) => `${p.nombre} ${p.pct}%`).join(', ')}>
        <circle cx="21" cy="21" r={r} fill="none"
                stroke="var(--grafica-pista)" strokeWidth="5" />
        {partes.map((p) => {
          const trazo = (
            <circle key={p.clave} cx="21" cy="21" r={r} fill="none"
                    stroke={COLOR_MEZCLA[p.clave] || 'var(--muted)'} strokeWidth="5"
                    strokeDasharray={`${p.pct} ${100 - p.pct}`}
                    // El -25 arranca el reparto en las doce y no en las tres,
                    // que es donde el ojo espera que empiece.
                    strokeDashoffset={25 - acumulado}>
              <title>{`${p.nombre}: ${p.cuantas} (${p.pct}%)`}</title>
            </circle>
          )
          acumulado += p.pct
          return trazo
        })}
        {marca && (
          <line {...marca} stroke="var(--ink)" strokeWidth="0.8">
            <title>{`Meta: ${meta}% preventivo`}</title>
          </line>
        )}
        {prev && (
          <>
            <text x="21" y="20.2" className="dona-cifra">{prev.pct}%</text>
            <text x="21" y="24.6" className="dona-pie">preventivo</text>
          </>
        )}
      </svg>

      <ul className="dona-leyenda">
        {partes.map((p) => (
          <li key={p.clave}>
            <span className="dona-punto"
                  style={{ background: COLOR_MEZCLA[p.clave] || 'var(--muted)' }} />
            <span className="grow">{p.nombre}</span>
            <strong>{p.cuantas}</strong>
            <span className="dona-pct">{p.pct}%</span>
          </li>
        ))}
        <li className="dona-total">
          <span className="grow">Total de órdenes</span>
          <strong>{total}</strong>
        </li>
        {meta ? (
          <li className="dona-total">
            <span className="grow">Meta de preventivo (la rayita)</span>
            <strong>{meta}%</strong>
            <span className="dona-pct">
              {pctPrev >= meta ? 'cumplida' : `faltan ${Math.round((meta - pctPrev) * 10) / 10} pts`}
            </span>
          </li>
        ) : null}
      </ul>
    </div>
  )
}

/* ------------------------------------------------ mecánicos en preventivo */

const COLOR_MECANICO = ['var(--grafica)', 'var(--ok)', 'var(--warn-mark)',
                        'var(--logo-azul)', 'var(--danger)']

/** Pastel de quién hizo los preventivos del periodo, con su ranking abajo.
 *
 *  Mismo trazo que la dona (un círculo y stroke-dasharray), pero lleno: aquí
 *  no hay un número único que poner en medio. Los cinco que más hicieron van
 *  con color; el resto se junta en «Otros». La tabla de abajo trae a TODOS,
 *  porque es la que sirve para decidir un premio.
 */
function MecanicosPreventivo({ datos }) {
  if (!datos || !datos.total) {
    return <Empty>Ningún preventivo tiene mecánico capturado en este periodo</Empty>
  }
  const r = 100 / (2 * Math.PI)
  let acumulado = 0
  const color = (p, i) => (p.clave === 'otros' ? 'var(--muted)'
    : COLOR_MECANICO[i % COLOR_MECANICO.length])
  return (
    <>
      <div className="dona-wrap">
        <svg viewBox="0 0 42 42" className="dona" role="img"
             aria-label={'Preventivos por mecánico: '
                         + datos.partes.map((p) => `${p.nombre} ${p.cuantas}`).join(', ')}>
          {datos.partes.map((p, i) => {
            const trazo = (
              <circle key={p.clave} cx="21" cy="21" r={r / 2} fill="none"
                      stroke={color(p, i)} strokeWidth={r}
                      pathLength="100"
                      strokeDasharray={`${p.pct} ${100 - p.pct}`}
                      strokeDashoffset={25 - acumulado}>
                <title>{`${p.nombre}: ${p.cuantas} (${p.pct}%)`}</title>
              </circle>
            )
            acumulado += p.pct
            return trazo
          })}
        </svg>
        <ul className="dona-leyenda">
          {datos.partes.map((p, i) => (
            <li key={p.clave}>
              <span className="dona-punto" style={{ background: color(p, i) }} />
              <span className="grow">{p.nombre}</span>
              <strong>{p.cuantas}</strong>
              <span className="dona-pct">{p.pct}%</span>
            </li>
          ))}
          <li className="dona-total">
            <span className="grow">Preventivos con mecánico</span>
            <strong>{datos.total}</strong>
          </li>
        </ul>
      </div>
      <Tabla
        columnas={[
          { k: 'lugar', t: '#', num: true },
          { k: 'nombre', t: 'Mecánico' },
          { k: 'taller', t: 'Taller' },
          { k: 'preventivos', t: 'Preventivos', num: true },
          { k: 'correctivos', t: 'Correctivos', num: true },
          { k: 'pct', t: '% preventivo', num: true },
        ]}
        filas={datos.ranking.map((f) => ({
          ...f, id: f.lugar, taller: f.taller || '—',
          pct: f.pct_preventivo === null ? '—' : `${f.pct_preventivo}%`,
        }))}
      />
    </>
  )
}

/** El tablero unificado: el AHORA y el CÓMO VAMOS en una sola pantalla.
 *
 *  Hasta la junta eran tres lugares para una misma pregunta: «Tablero» traía los
 *  números de hoy, «Estadísticas» las series en el tiempo, y la mitad de los
 *  indicadores de las unidades solo se veían entrando al módulo del
 *  administrador con otro correo y otra contraseña. El gerente lo dijo con todas
 *  sus letras y tiene razón — una segunda cuenta para mirar tus propios números
 *  es una cuenta que se acaba prestando.
 *
 *  El filtro de arriba (los dos calendarios y el corte por día, mes o año) manda
 *  sobre TODO lo que se calcula por periodo: las cuatro gráficas nuevas, las
 *  series de operación, el cumplimiento por chofer y el Excel. Que el Excel
 *  salga del mismo filtro no es un detalle de comodidad: si el botón exportara
 *  un rango fijo, el archivo que el gerente lleva a dirección diría otra cosa
 *  que la pantalla desde la que lo bajó, y esa discrepancia solo se descubre
 *  enfrente de dirección.
 *
 *  Lo que el filtro NO toca son los KPIs de estado —ocupación, varadas,
 *  presupuestos por autorizar, piezas en camino—: son una foto de este momento y
 *  no tienen periodo que recortar. Van juntos y bajo su propio título justo por
 *  eso; intercalados entre las gráficas se leerían como si también respondieran
 *  a las fechas de arriba, que es el malentendido más fácil de provocar en una
 *  pantalla que tiene un calendario hasta arriba.
 */
function Tablero() {
  const toast = useToast()
  // El filtro va en UN solo estado y no en tres. `tocado` recuerda si el gerente
  // ya movió un calendario, y de eso depende qué hace el selector de día/mes/año:
  //
  //   sin tocar  -> cambiar el corte también propone la ventana de ese corte.
  //                 Es lo que evita que un clic en «Día» sobre el rango anual de
  //                 arranque pinte 365 barras de un pixel.
  //   ya tocado  -> las fechas del gerente se respetan y el corte solo cambia el
  //                 agrupamiento. Tirar un rango que alguien acaba de teclear
  //                 para «ayudarlo» es peor que cualquier gráfica apretada, y
  //                 esa la resuelve el scroll horizontal de la propia gráfica.
  const [filtro, setFiltro] = useState(() => {
    const [d, h] = rangoPorDefecto('mes')
    return { gran: 'mes', desde: d, hasta: h, tocado: false }
  })
  const { gran, desde, hasta } = filtro
  const [bajando, setBajando] = useState(false)

  const cambiarGran = (g) => setFiltro((f) => {
    if (f.tocado) return { ...f, gran: g }
    const [d, h] = rangoPorDefecto(g)
    return { gran: g, desde: d, hasta: h, tocado: false }
  })
  const cambiarFecha = (cual, valor) =>
    setFiltro((f) => ({ ...f, [cual]: valor, tocado: true }))

  // `|| undefined` y no el valor pelado: si el gerente vacía un calendario, el
  // input entrega cadena vacía, y una cadena vacía SÍ viaja en la URL
  // (`?desde=`) porque api.js solo descarta null y undefined. El servidor anota
  // el parámetro como `date | None` y responde 422 ante una cadena vacía, así
  // que la pantalla se llenaría de un error rojo mientras alguien está a media
  // edición. Mandándolo como undefined el servidor completa su rango por
  // omisión y se sigue viendo algo.
  const paramsRango = {
    desde: desde || undefined, hasta: hasta || undefined, granularidad: gran,
  }
  const rango = useApi(() => api.get('/gerente/tablero-rango', paramsRango),
                       [desde, hasta, gran])

  const kpis = useApi(() => api.get('/gerente/kpis'))
  const atendidas = useApi(() => api.get('/gerente/atendidas', { dias: 30 }))
  const piezas = useApi(() => api.get('/gerente/piezas-en-camino'))

  const exportar = async () => {
    setBajando(true)
    try {
      // Los MISMOS parámetros que tiene puestos la pantalla. El nombre del
      // archivo lo decide el servidor y trae dentro el rango realmente
      // exportado, así que se muestra tal cual en el aviso: si el rango se
      // recortó o venía al revés, el gerente ve en el toast el periodo que de
      // verdad se llevó.
      const nombre = await api.descargar('/gerente/exportar/tablero',
                                         { params: paramsRango })
      toast(`Se descargó ${nombre}`)
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setBajando(false)
    }
  }

  const correrJobs = async () => {
    try {
      const r = await api.post('/jobs/correr')
      // Los nombres tienen que ser los que DEVUELVE el servidor (jobs.py,
      // correr_todos). Aquí decía `penalizaciones_generadas`, que no existe:
      // la clave es `avisos_incumplimiento` desde que la v2.0 quitó la palabra
      // «penalización», así que el mensaje salía «Avisos: undefined» cada vez
      // que alguien apretaba el botón.
      const ag = r.agenda || {}
      toast(`Avisos de incumplimiento: ${r.avisos_incumplimiento ?? 0} · ` +
            `Alertas: ${r.alertas_nuevas ?? 0} · ` +
            `Citas avisadas: ${r.avisos_cita ?? 0} · ` +
            `Agenda: ${ag.propuestas ?? 0} propuestas, ${ag.sin_cupo ?? 0} sin cupo`)
      kpis.recargar()
    } catch (e) { toast(e.message, 'err') }
  }

  const k = kpis.data
  const r = rango.data
  // El servidor devuelve el rango que REALMENTE usó, que no siempre es el que se
  // pidió: si los dos calendarios vienen al revés los intercambia en vez de
  // devolver una pantalla en blanco (una pantalla en blanco no dice «te
  // equivocaste de calendario», deja pensando que no hubo movimiento, que es la
  // conclusión contraria). Cuando eso pasa hay que DECIRLO, porque si no el
  // gerente está leyendo un periodo distinto del que marcó.
  const invertido = r && desde && hasta && !r.aviso
                      && (r.desde !== desde || r.hasta !== hasta)

  return (
    <>
      {/* a) Encabezado ------------------------------------------------------ */}
      <div className="card-head">
        <h1>Tablero</h1>
        <div className="btn-row" style={{ marginLeft: 'auto' }}>
          <button className="btn sm" onClick={correrJobs} title="Dispara CU-AUT-01..03">
            ▶ Correr procesos del día
          </button>
          <button className="btn sm primary" onClick={exportar} disabled={bajando}>
            <IcoDescargar size={13} className="ico-inline" aria-hidden="true" />
            {bajando ? 'Generando…' : 'Exportar a Excel'}
          </button>
        </div>
      </div>

      {/* b) Barra de filtro -------------------------------------------------
          Se dibuja SIEMPRE, también mientras las gráficas cargan. Si se ocultara
          detrás del spinner, cada cambio de fecha desmontaría el <input> que el
          gerente acaba de tocar: se pierde el foco y el calendario se cierra
          solo a media elección. */}
      <div className="card filtro-rango">
        <div className="field">
          <label htmlFor="rango-desde">Desde</label>
          <input id="rango-desde" type="date" value={desde}
                 onChange={(e) => cambiarFecha('desde', e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="rango-hasta">Hasta</label>
          <input id="rango-hasta" type="date" value={hasta}
                 onChange={(e) => cambiarFecha('hasta', e.target.value)} />
        </div>
        <div className="field">
          {/* <span> y no <label>: un <label> sin `for` y sin control adentro no
              es válido y el lector de pantalla lo lee suelto, sin decir a qué
              pertenece. Aquí lo que se nombra es el GRUPO de tres botones, y eso
              se hace con role="group" + aria-label; el texto de arriba queda
              solo como rótulo visible. */}
          <span className="lbl-campo">Agrupar por</span>
          <div className="segmentado" role="group" aria-label="Agrupar por">
            {[['dia', 'Día'], ['mes', 'Mes'], ['anio', 'Año']].map(([v, t]) => (
              <button key={v} className={'btn sm' + (gran === v ? ' primario' : '')}
                      aria-pressed={gran === v} onClick={() => cambiarGran(v)}>{t}</button>
            ))}
          </div>
        </div>
      </div>

      {/* c) Las cuatro gráficas del rango ----------------------------------- */}
      {rango.cargando ? <Spinner /> : rango.error ? (
        <Aviso tipo="err">{rango.error}</Aviso>
      ) : r && (
        <>
          {r.aviso && <Aviso tipo="warn">{r.aviso}</Aviso>}
          {invertido && (
            <Aviso tipo="info">
              Los calendarios venían al revés. Se está mostrando del{' '}
              <strong>{fmtFecha(r.desde)}</strong> al <strong>{fmtFecha(r.hasta)}</strong>.
            </Aviso>
          )}

          <div className="grid g2 graficas">
            {(r.series || []).map((sr) => {
              const cfg = SERIES_RANGO[sr.clave] || {}
              const total = r.resumen ? r.resumen[cfg.resumen] : null
              return (
                <Card key={sr.clave} title={sr.nombre}
                      sub={r.etiquetas.length + ' ' + nombrePeriodos(gran, r.etiquetas.length)
                           + ' · del ' + fmtFecha(r.desde) + ' al ' + fmtFecha(r.hasta)}>
                  <Kpi valor={fmtValor(total, sr.unidad)} etiqueta={cfg.kpi}
                       hint={pistaResumen(sr.clave, total, r.resumen)} />
                  <ColumnasTiempo etiquetas={r.etiquetas} datos={sr.datos}
                                  color={cfg.color} gran={gran} enCurso={r.en_curso}
                                  unidad={sr.unidad} hueco={cfg.hueco} />
                </Card>
              )
            })}
          </div>

          <Card title="Preventivo contra correctivo"
                sub={'Las ' + (r.mezcla ? r.mezcla.total : 0) + ' orden(es) que ENTRARON'
                     + ' al taller · del ' + fmtFecha(r.desde) + ' al ' + fmtFecha(r.hasta)}>
            <Dona partes={(r.mezcla || {}).partes} total={(r.mezcla || {}).total}
                  meta={(r.mezcla || {}).meta_pct} />
            <Regla>
              Es la pregunta de fondo: <strong>¿el taller se adelanta a las fallas o las va
              apagando?</strong> Un preventivo alto quiere decir que el programa de
              mantenimiento sirve. Se cuenta por la <strong>entrada</strong> de la orden y no
              por su salida —a diferencia del tiempo de reparación— porque lo que se mide es
              qué clase de trabajo le <em>llegó</em> al taller en el periodo: una unidad que
              entró por un correctivo y sigue adentro ya gastó esa capacidad, haya salido o
              no. El siniestro va aparte y no con los correctivos: un choque no es una falla
              de mantenimiento, y sumarlo ahí hace ver al taller peor de lo que está.
            </Regla>
          </Card>

          <Card title="Mecánicos en preventivos"
                sub={'Quién hizo los preventivos · del ' + fmtFecha(r.desde)
                     + ' al ' + fmtFecha(r.hasta)}>
            <MecanicosPreventivo datos={r.mecanicos_preventivo} />
            <Regla>
              Cuenta los preventivos donde el mecánico quedó <strong>capturado como
              responsable</strong> en el formato de mantenimiento, en las fechas de los dos
              calendarios. Es la misma cuenta que <em>Historiales → Mecánicos</em>. El que
              trabajó sin quedar capturado no aparece: para que el premio sea justo, Pedro
              tiene que registrar quién hizo cada trabajo.
            </Regla>
          </Card>

          <Regla>
            Un periodo marcado <strong>«sin dato»</strong> no es un cero: es que ahí no había
            nada que medir —ninguna orden cerrada, ninguna cita con desenlace—. Se dibuja con
            el recuadro punteado y su etiqueta en su lugar, nunca como una barra de altura
            cero, porque cero días de reparación promedio es una afirmación (<em>se reparó en
            el acto</em>) y no un hueco. En <strong>citas totales</strong> y{' '}
            <strong>atenciones</strong>, en cambio, el cero sí es un dato legítimo: hubo
            periodo y no hubo citas. Las citas <strong>canceladas</strong> no cuentan en
            ningún lado — nunca llegaron a ser un compromiso vivo.
          </Regla>
        </>
      )}

      {/* d) El estado de hoy ------------------------------------------------ */}
      <h2 style={{ margin: '20px 0 8px' }}>Estado de hoy</h2>
      <Regla>
        Estos números son una foto de <strong>este momento</strong> y no dependen de las fechas
        de arriba: una ocupación o un presupuesto por autorizar no tienen periodo que recortar.
        El filtro manda sobre las gráficas y sobre el Excel.
      </Regla>

      {kpis.cargando ? <Spinner /> : kpis.error ? (
        <Aviso tipo="err">{kpis.error}</Aviso>
      ) : k && (
        <>
        <div className="grid g4">
          <Kpi valor={k.choferes_incumpliendo} etiqueta="Choferes incumpliendo"
               tono={k.choferes_incumpliendo ? 'alert' : 'ok'}
               hint="Mantenimiento preventivo vencido" />
          <Kpi valor={`${k.ocupacion_pct}%`} etiqueta="Ocupación del taller"
               hint={`${k.espacios_ocupados} de ${k.espacios_totales} espacios operativos`} />
          <Kpi valor={k.unidades_varadas} etiqueta="Unidades varadas"
               tono={k.unidades_varadas ? 'warn' : 'ok'} />
          <Kpi valor={k.presupuestos_pendientes} etiqueta="Presupuestos por autorizar"
               tono={k.presupuestos_pendientes ? 'warn' : ''} />
        </div>

        <div className="grid g4">
          <Kpi valor={k.unidades_total} etiqueta="Unidades" />
          <Kpi valor={k.unidades_en_taller} etiqueta="En taller" />
          <Kpi valor={k.unidades_en_ruta} etiqueta="En ruta" />
          <Kpi valor={k.piezas_en_camino} etiqueta="Piezas en camino" />
        </div>

        <div className="grid g2">
          <Kpi valor={k.alertas_abiertas} etiqueta="Alertas sin atender"
               tono={k.alertas_abiertas ? 'alert' : 'ok'} hint="Unidades paradas > 3 meses" />
          <Kpi valor={k.retraso_captura_promedio ?? '—'} etiqueta="Retraso de captura (días)"
               tono={k.retraso_captura_promedio > 1 ? 'warn' : 'ok'}
               hint="Entre que el mecánico entrega el papel y el admin lo teclea" />
        </div>

        {k.retraso_captura_promedio > 1 && (
          <Aviso tipo="warn">
            Los datos del taller llegan con {k.retraso_captura_promedio} días de retraso en promedio.
            Este tablero no es “tiempo real” mientras el administrador capture tarde el trabajo de
            los mecánicos.
          </Aviso>
        )}

        <Card title="Unidades atendidas (últimos 30 días)">
          {atendidas.data && (
            <>
              <div className="grid g3">
                <Kpi valor={atendidas.data.total} etiqueta="Órdenes cerradas" />
                <Kpi valor={atendidas.data.dias_promedio} etiqueta="Días promedio en taller" />
                <Kpi valor={Object.keys(atendidas.data.por_taller).length} etiqueta="Talleres" />
              </div>
              <Tabla
                vacio="Sin órdenes cerradas en el periodo"
                columnas={[{ k: 'tipo', t: 'Tipo' }, { k: 'n', t: 'Cantidad', num: true }]}
                filas={Object.entries(atendidas.data.por_tipo).map(([tipo, n]) => ({ tipo, n }))} />
            </>
          )}
        </Card>

        <Card title="Piezas en camino">
          <Tabla
            vacio="Ninguna pieza en tránsito"
            columnas={[
              { k: 'folio', t: 'Orden compra' },
              { k: 'unidad', t: 'Unidad' },
              { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
              { k: 'fecha_estimada_llegada', t: 'Llega', r: (f) => fmtFecha(f.fecha_estimada_llegada) },
              { k: 'dias_para_llegar', t: 'Días', num: true,
                r: (f) => <Badge tono={f.retrasada ? 'danger' : 'ok'}>
                  {f.retrasada ? `${-f.dias_para_llegar} tarde` : f.dias_para_llegar}
                </Badge> },
              { k: 'total', t: 'Total', num: true, r: (f) => fmtMoneda(f.total) },
            ]}
            filas={piezas.data || []} />
        </Card>
        </>
      )}

      {/* e) La operación en el tiempo --------------------------------------
          Lo que hasta ayer era la pestaña «Estadísticas». Recibe el filtro de
          arriba por props y no trae control propio: dos selectores de
          granularidad en la misma pantalla es la forma más rápida de que lo de
          arriba y lo de abajo hablen de periodos distintos y el gerente los
          compare de todos modos. */}
      <h2 style={{ margin: '20px 0 8px' }}>Operación en el tiempo</h2>
      <Estadisticas desde={desde} hasta={hasta} gran={gran} />
    </>
  )
}

/** «Días», «meses» o «años», en singular cuando toca.
 *
 *  Un rango de un solo periodo no es un caso raro: el gerente marca el mismo día
 *  en los dos calendarios para ver una fecha suelta, y el subtítulo decía «1
 *  días». Es una errata minúscula que hace ver descuidada toda la pantalla justo
 *  cuando se está proyectando en una junta.
 */
function nombrePeriodos(gran, cuantos) {
  if (gran === 'dia') return cuantos === 1 ? 'día' : 'días'
  if (gran === 'mes') return cuantos === 1 ? 'mes' : 'meses'
  return cuantos === 1 ? 'año' : 'años'
}

/** La línea chica debajo del número grande de cada gráfica del rango.
 *
 *  Cuando el indicador no se pudo calcular, esta línea es lo único que explica
 *  por qué se ve un «—». Un guion sin explicación se lee como que la pantalla
 *  está rota, y el siguiente paso de quien lo ve es dejar de creerle al resto de
 *  los números.
 */
function pistaResumen(clave, valor, resumen) {
  const res = resumen || {}
  if (clave === 'dias_reparacion') {
    return valor == null
      ? 'Ninguna orden cerrada en el rango: no hay reparación que promediar'
      : `Sobre ${res.ordenes_cerradas} orden(es) cerrada(s) en el rango`
  }
  if (clave === 'tasa_concretadas') {
    return valor == null
      ? 'Ninguna cita del rango llegó a tener desenlace todavía'
      : 'Solo cuenta las citas con desenlace: cumplidas contra faltas'
  }
  if (clave === 'citas_totales') return 'Todos los estados menos las canceladas'
  return 'Citas que el taller marcó como cumplidas'
}

/* ---------------------------------------------------------- CU-GER-02 ------ */
/** Dos preguntas distintas, separadas a propósito.
 *
 *  Antes iban una encima de otra y se leían como contradicción: arriba decía
 *  «toda la flota al corriente» y justo debajo listaba dos «penalizaciones».
 *  No era un error de datos — son dos cosas:
 *
 *    VENCIDO HOY  → qué está fuera de plazo en este momento. Puede ser cero y
 *                   estar bien: significa que nadie trae un servicio atrasado.
 *    ACUMULADO    → cuántas veces ha faltado cada chofer desde siempre. Es
 *                   historia, y no baja nunca aunque hoy todo esté al día.
 *
 *  Y el vocabulario: «penalización» era la palabra de la v1.1. Su tabla ya no
 *  se escribe —cero filas en producción— pero el nombre seguía en pantalla
 *  conviviendo con «aviso» y «amonestación» como si fueran lo mismo. Aquí se
 *  usan solo los dos que existen de verdad.
 */
function Incumplimiento() {
  const { data, cargando } = useApi(() => api.get('/gerente/incumplimiento'))
  const historico = useApi(() => api.get('/gerente/incumplimientos-acumulados'))
  if (cargando) return <Spinner />
  const vencidos = data || []
  const hist = historico.data || []

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Incumplimiento de mantenimiento</h1>
      <Aviso tipo="info">
        Se reporta contra el <strong>poseedor actual</strong> de la unidad. La columna “Por
        préstamo” indica que quien responde no es el titular: sin ese dato se culparía al chofer
        equivocado (RN-01).
      </Aviso>

      <Card title="Vencido hoy"
            sub={vencidos.length
              ? `${vencidos.length} servicio(s) fuera de plazo en este momento`
              : 'Nada fuera de plazo en este momento'}>
        <Tabla
          vacio="Ninguna unidad con servicio vencido hoy"
          columnas={[
            { k: 'chofer', t: 'Responsable' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'plan', t: 'Plan' },
            { k: 'fecha_limite', t: 'Límite', r: (f) => fmtFecha(f.fecha_limite) },
            { k: 'dias_atraso', t: 'Atraso', num: true,
              r: (f) => <Badge tono="danger">{f.dias_atraso} d</Badge> },
            { k: 'es_poseedor_por_prestamo', t: 'Por préstamo',
              r: (f) => f.es_poseedor_por_prestamo
                ? <Badge tono="warn">Sí</Badge> : <Badge>No</Badge> },
          ]}
          filas={vencidos} />
      </Card>

      <Card title="Historial acumulado por chofer"
            sub="Desde siempre. No baja aunque hoy todo esté al corriente">
        <Tabla
          vacio="Ningún chofer ha faltado a una cita confirmada"
          columnas={[
            { k: 'chofer', t: 'Chofer' },
            { k: 'total', t: 'Faltas acumuladas', num: true },
            { k: 'abiertos', t: 'Sin atender', num: true,
              r: (f) => f.abiertos
                ? <Badge tono="warn">{f.abiertos}</Badge> : <Badge tono="ok">0</Badge> },
            { k: 'amonestadas', t: 'Amonestadas', num: true,
              r: (f) => f.amonestadas
                ? <Badge tono="danger">{f.amonestadas}</Badge> : '0' },
          ]}
          filas={hist} />
        <Regla>
          Tres números distintos. <strong>Faltas acumuladas</strong> es historia y no baja nunca.
          <strong> Sin atender</strong> es lo accionable: avisos que nadie ha cerrado todavía.
          <strong> Amonestadas</strong> son las que una persona convirtió en acto formal — pueden
          ser menos que las faltas, y eso es a propósito: no toda falta se amonesta.
        </Regla>
      </Card>
    </>
  )
}

/* ------------------------------------------------------ CU-GER-03/04/06 ---- */
function TallerVista() {
  const ocupacion = useApi(() => api.get('/gerente/ocupacion'))
  const permanencia = useApi(() => api.get('/gerente/permanencia'))
  const historial = useApi(() => api.get('/gerente/historial', { dias: 90 }))
  return (
    <>
      <Patios />

      <h1 style={{ margin: '24px 0 14px' }}>Ocupación del taller</h1>
      {ocupacion.cargando && <Spinner />}

      {(ocupacion.data || []).map((t) => (
        <Card key={t.taller_id} title={t.taller}
              actions={<Badge tono={t.pct > 80 ? 'danger' : t.pct > 50 ? 'warn' : 'ok'}>
                {t.pct}% ocupado</Badge>}>
          <p className="sub">{t.ocupados} de {t.total} espacios operativos</p>
          <Tabla
            columnas={[
              { k: 'zona', t: 'Zona' },
              { k: 'ocupados', t: 'Ocupados', num: true },
              { k: 'total', t: 'Total', num: true },
            ]}
            filas={t.zonas} />
          <Regla>
            El yonke y el área de lavado no cuentan para la ocupación; si contaran, el indicador
            saldría inflado por 46 espacios que no son capacidad de taller.
          </Regla>
        </Card>
      ))}

      <Card title="Tiempo de permanencia (órdenes abiertas)">
        <Tabla
          vacio="Sin unidades en taller"
          columnas={[
            { k: 'folio', t: 'Orden' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'espacio', t: 'Espacio' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            { k: 'dias_en_taller', t: 'Días', num: true,
              r: (f) => <Badge tono={f.dias_en_taller > 90 ? 'danger'
                : f.dias_en_taller > 30 ? 'warn' : 'ok'}>{f.dias_en_taller}</Badge> },
          ]}
          filas={permanencia.data || []} />
      </Card>

      <Card title="Historial del taller (90 días)">
        <Tabla
          vacio="Sin historial"
          columnas={[
            { k: 'folio', t: 'Orden' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'tipo', t: 'Tipo' },
            { k: 'fecha_entrada', t: 'Entrada', r: (f) => fmtFecha(f.fecha_entrada) },
            { k: 'fecha_salida', t: 'Salida', r: (f) => fmtFecha(f.fecha_salida) },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
          ]}
          filas={historial.data || []} />
      </Card>
    </>
  )
}

/* ---------------------------------------------------------- CU-GER-08 ------ */
function Presupuestos() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/gerente/presupuestos'))
  const todos = useApi(() => api.get('/gerente/presupuestos', { pendientes: false }))
  const [resolver, setResolver] = useState(null)

  if (cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Presupuestos por autorizar</h1>
      <Aviso tipo="info">
        Solo tú apruebas o rechazas. Ninguna pieza se compra sin tu autorización (RN-07).
      </Aviso>

      {(data || []).length === 0 ? <Empty icono={IcoListo}>Nada pendiente</Empty> : (
        (data || []).map((p) => (
          <Card key={p.id} title={`${p.folio} · ${p.unidad}`}
                actions={<strong>{fmtMoneda(p.total)}</strong>}>
            <p className="sub">
              Elaboró {p.tecnico_elaboro} el {fmtFecha(p.fecha_elaboracion)} · capturó{' '}
              {p.capturado_por}
              {p.dias_retraso_captura > 1 && (
                <> · <Badge tono="warn">{p.dias_retraso_captura} d de retraso</Badge></>
              )}
            </p>
            {p.diagnostico && <p>{p.diagnostico}</p>}
            <Tabla
              columnas={[
                { k: 'pieza', t: 'Concepto', r: (f) => f.pieza || f.descripcion_libre },
                { k: 'cantidad', t: 'Cant.', num: true },
                { k: 'importe', t: 'Importe', num: true, r: (f) => fmtMoneda(f.importe) },
              ]}
              filas={p.detalles} vacio="Sin piezas" />
            <p className="sub" style={{ textAlign: 'right', marginTop: 8 }}>
              Mano de obra {fmtMoneda(p.costo_mano_obra)} · piezas {fmtMoneda(p.subtotal_piezas)}
            </p>
            <button className="btn primary block" onClick={() => setResolver(p)}>Resolver</button>
          </Card>
        ))
      )}

      <Card title="Historial de presupuestos">
        <Tabla
          vacio="Sin presupuestos"
          columnas={[
            { k: 'folio', t: 'Folio' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'tecnico_elaboro', t: 'Elaboró' },
            { k: 'total', t: 'Total', num: true, r: (f) => fmtMoneda(f.total) },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
          ]}
          filas={todos.data || []} />
      </Card>

      {resolver && (
        <ModalResolver presupuesto={resolver} onCerrar={() => setResolver(null)}
                       onListo={() => {
                         setResolver(null); recargar(); todos.recargar(); toast('Resuelto')
                       }} />
      )}
    </>
  )
}

function ModalResolver({ presupuesto, onCerrar, onListo }) {
  const toast = useToast()
  const [comentario, setComentario] = useState('')
  const enviar = async (resultado) => {
    try {
      await api.post(`/gerente/presupuestos/${presupuesto.id}/resolver`, { resultado, comentario })
      onListo()
    } catch (e) { toast(e.message, 'err') }
  }
  return (
    <Modal titulo={`${presupuesto.folio} · ${fmtMoneda(presupuesto.total)}`} onClose={onCerrar}>
      <p className="sub">
        Unidad {presupuesto.unidad} · elaboró {presupuesto.tecnico_elaboro}
      </p>
      <div className="field">
        <label>Comentario</label>
        <textarea value={comentario} onChange={(e) => setComentario(e.target.value)} />
      </div>
      <button className="btn ok block" onClick={() => enviar('aprobado')}>Aprobar</button>
      <div style={{ height: 8 }} />
      <button className="btn block" onClick={() => enviar('devuelto')}>
        Devolver para corrección
      </button>
      <div style={{ height: 8 }} />
      <button className="btn danger block" onClick={() => enviar('rechazado')}>Rechazar</button>
      <Regla>
        Si lo devuelves, el administrador tiene que avisarle al mecánico en persona: él no recibe
        notificaciones del sistema. Queda constancia en CU-ADM-16.
      </Regla>
    </Modal>
  )
}

/* ---------------------------------------------------------- CU-GER-07 ------ */
function Alertas() {
  const toast = useToast()
  const { data, cargando, recargar } = useApi(() => api.get('/gerente/alertas'))
  if (cargando) return <Spinner />

  const atender = async (a) => {
    try {
      await api.post(`/gerente/alertas/${a.id}/atender`, undefined, { nota: 'Revisada por gerencia' })
      toast('Alerta atendida'); recargar()
    } catch (e) { toast(e.message, 'err') }
  }

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Alertas</h1>
      <Aviso tipo="info">
        Las unidades con más de 3 meses paradas se vuelven a notificar todos los días hasta que
        alguien las atienda (RN-08). El contador muestra cuántas veces se ha insistido.
      </Aviso>
      {(data || []).length === 0 ? <Empty icono={IcoCampana}>Sin alertas abiertas</Empty> : (
        (data || []).map((a) => (
          <Card key={a.id} title={a.unidad || a.tipo}
                actions={<Badge tono={a.veces_notificada > 5 ? 'danger' : 'warn'}>
                  notificada {a.veces_notificada}×</Badge>}>
            <p>{a.detalle}</p>
            <p className="sub">Desde {fmtFechaHora(a.fecha_generacion)}</p>
            <button className="btn ok block" onClick={() => atender(a)}>Marcar como atendida</button>
          </Card>
        ))
      )}
    </>
  )
}


/* ------------------------------------------- CU-GER-12/13/14 · RF-GER-14..18 */
/** El eje de tiempo del tablero.
 *
 *  El tablero de arriba enseña el AHORA. Esto contesta «cómo vamos», que es otra
 *  pregunta — y es la que el cliente pidió en la junta: los mismos indicadores
 *  por día, por mes y por año, y en gráficos.
 */
const SERIES_COLOR = {
  entradas: 'var(--grafica)',
  preventivos: 'var(--ok)',
  citas: 'var(--grafica)',
  faltas: 'var(--grafica-alerta)',
  amonestaciones: 'var(--danger)',
  averias: 'var(--brand)',
}

/** Columnas sobre el tiempo.
 *
 *  Los periodos vacíos SÍ se dibujan: un mes sin un solo preventivo es
 *  información, y omitirlo lo escondería pegando el mes de antes con el de
 *  después — el bajón desaparece de la vista en vez de saltar a los ojos.
 *
 *  «Vacío» son DOS COSAS DISTINTAS y esta función es donde se separan, porque
 *  en una gráfica de barras se ven casi igual y significan lo contrario:
 *
 *    dato 0     -> se midió y dio cero. Hubo periodo y no hubo citas. Se pinta
 *                  la barra a ras del suelo (los 2px de min-height de .gtorre)
 *                  con su «0» encima: es una medición y se lee como tal.
 *    dato null  -> no había nada que medir. Se pinta el recuadro punteado de
 *                  .ghueco, la cifra va en «—» y el tooltip dice POR QUÉ. Una
 *                  barra de altura cero aquí sería una mentira con forma de
 *                  dato: cero días de reparación promedio afirma que se reparó
 *                  en el acto, que es lo contrario de «no se cerró nada».
 *
 *  La escala también depende de lo que se mide. Los conteos y los días se
 *  escalan al máximo de la serie, que es lo que deja ver la forma. Los
 *  PORCENTAJES no: van fijos a 100, porque autoescalarlos haría que el mejor mes
 *  llenara la tarjeta de arriba abajo aunque fuera un 41% — la gráfica diría
 *  «excelente» y el número diría «reprobado», y la que se recuerda es la
 *  gráfica.
 */
function ColumnasTiempo({ etiquetas, datos, color, gran, enCurso,
                          unidad = 'conteo', hueco }) {
  // Los null se sacan ANTES del máximo. Math.max(null, …) los convierte en 0 en
  // silencio, que aquí daría igual, pero una serie entera de null devolvería
  // -Infinity sin el 1 de piso y todas las alturas saldrían NaN.
  const conDato = datos.filter((v) => v != null)
  const tope = unidad === 'pct' ? 100 : Math.max(...conDato, 1)
  const corto = (e) => gran === 'dia' ? e.slice(8) : (gran === 'mes' ? e.slice(5) : e)
  const nombre = gran === 'dia' ? 'día' : gran === 'mes' ? 'mes' : 'año'
  return (
    <div className="gcolumnas rango">
      {etiquetas.map((e, i) => {
        const v = datos[i]
        const vacio = v == null
        const abierto = e === enCurso
        const titulo = e + ': '
          + (vacio ? 'sin dato' + (hueco ? ' — ' + hueco : '') : fmtValor(v, unidad))
          + (abierto ? ` · ${nombre} en curso, todavía no termina` : '')
        return (
          <div key={e} title={titulo}
               className={'gcol' + (abierto ? ' en-curso' : '') + (vacio ? ' sin-dato' : '')}>
            <span className="gcifra">{fmtValor(v, unidad)}</span>
            {vacio
              ? <div className="ghueco" />
              : <div className="gtorre"
                     style={{ height: (v / tope) * 100 + '%', background: color }} />}
            <span className="gpie">{corto(e)}</span>
          </div>
        )
      })}
    </div>
  )
}

/** Las series de operación y el cumplimiento por chofer.
 *
 *  Era la pantalla «Estadísticas», con su propio título y su propio selector de
 *  día/mes/año. Ahora vive dentro del Tablero y recibe el filtro por props: el
 *  selector propio se quitó a propósito, porque dos controles de granularidad en
 *  la misma pantalla es la forma más rápida de que las gráficas de arriba y las
 *  de abajo queden en periodos distintos — y el gerente las va a comparar igual,
 *  porque están una debajo de la otra.
 *
 *  `desde` y `hasta` se mandan a los dos endpoints. Los dos los aceptan como
 *  opcionales (ver gerente_controller.py) y sin ellos responden lo de siempre —
 *  los últimos N periodos hacia atrás—, que es justo lo que aquí no sirve: si
 *  estas gráficas siguieran su propia ventana mientras las de arriba siguen la
 *  del calendario, la misma pantalla se contradiría sola.
 */
function Estadisticas({ desde, hasta, gran }) {
  // Sin `cuantos`: con desde/hasta puestos el servidor lo ignora, y mandarlo
  // igual sugeriría que todavía manda en algo.
  const params = { granularidad: gran, desde: desde || undefined, hasta: hasta || undefined }
  const serie = useApi(() => api.get('/gerente/estadisticas', params), [gran, desde, hasta])
  const cump = useApi(() => api.get('/gerente/cumplimiento-choferes', params),
                      [gran, desde, hasta])
  const [verChofer, setVerChofer] = useState(null)

  const d = serie.data || {}
  const etiquetas = d.etiquetas || []

  return (
    <>
      {serie.cargando ? <Spinner /> : serie.error ? (
        <Aviso tipo="err">{serie.error}</Aviso>
      ) : (
        <div className="grid g2 graficas">
          {(d.series || []).map((sr) => (
            <Card key={sr.clave} title={sr.nombre}
                  sub={etiquetas.length + ' ' + nombrePeriodos(gran, etiquetas.length)
                       + ' del rango'}>
              <ColumnasTiempo etiquetas={etiquetas} datos={sr.datos}
                              color={SERIES_COLOR[sr.clave]} gran={gran}
                              enCurso={d.en_curso} />
            </Card>
          ))}
        </div>
      )}

      <Card title="Cumplimiento por chofer"
            sub={cump.data ? 'Del ' + cump.data.desde + ' al ' + cump.data.hasta : '…'}>
        {/* El error se muestra en vez de tragárselo. Sin esto, una tabla vacía
            por una consulta que reventó se lee exactamente igual que una tabla
            vacía porque ningún chofer faltó a nada — y son noticias opuestas. */}
        {cump.error && <Aviso tipo="err">{cump.error}</Aviso>}
        <Tabla
          vacio="Sin citas confirmadas en el periodo"
          columnas={[
            { k: 'chofer', t: 'Chofer' },
            { k: 'confirmadas', t: 'Citas', num: true },
            { k: 'cumplidas', t: 'Cumplidas', num: true },
            { k: 'faltas', t: 'Faltas', num: true,
              r: (f) => f.faltas ? <Badge tono="danger">{f.faltas}</Badge> : '0' },
            { k: 'pendientes', t: 'Pend.', num: true,
              r: (f) => f.pendientes ? <Badge>{f.pendientes}</Badge> : '0' },
            { k: 'amonestaciones', t: 'Amonest.', num: true },
            { k: 'cumplimiento', t: '%', num: true,
              r: (f) => f.cumplimiento == null ? '—'
                : <Badge tono={f.cumplimiento >= 90 ? 'ok' : f.cumplimiento >= 70 ? 'warn' : 'danger'}>
                    {f.cumplimiento}%
                  </Badge> },
            { k: 'acciones', t: '',
              r: (f) => <button className="btn sm"
                                onClick={() => setVerChofer(f.chofer_id)}>Expediente</button> },
          ]}
          filas={(cump.data && cump.data.choferes) || []} />
        <Regla>
          Se mide sobre <strong>citas confirmadas</strong>. Una unidad a la que el taller nunca
          le dio cita no entra en este cálculo: eso mediría al taller, no al chofer. Y se mide
          contra el <strong>poseedor</strong> de la unidad ese día, no contra el titular.
          El porcentaje sale solo de las citas <strong>con desenlace</strong>: una cita confirmada
          que todavía no llega no es un incumplimiento, y meterla en la cuenta pintaría de 0% a
          quien no ha fallado a nada.
        </Regla>
      </Card>

      <Regla>
        La última columna de cada gráfica va <strong>apagada</strong>: es el
        {gran === 'dia' ? ' día' : gran === 'mes' ? ' mes' : ' año'} en curso y todavía no
        termina. Comparar un periodo a medias contra periodos completos siempre lo hace ver
        caído — y con granularidad de día es peor: a las nueve de la mañana hoy va a la mitad de
        cualquier otro día.
      </Regla>

      <Regla>
        La ocupación del patio día por día hacia atrás no se puede reconstruir: el 98% del
        historial importado no trae fecha de salida. Se puede desde hoy, guardando una foto
        diaria; hacia atrás no se recupera.
      </Regla>

      {verChofer && (
        <ModalExpediente choferId={verChofer} onCerrar={() => setVerChofer(null)} />
      )}
    </>
  )
}

/** CU-GER-13: sostiene una amonestación con historial Y defiende al chofer al
 *  que el taller nunca le dio cita. Las dos cosas importan. */
function ModalExpediente({ choferId, onCerrar }) {
  const { data, cargando } = useApi(
    () => api.get('/gerente/choferes/' + choferId + '/expediente'), [choferId])
  const e = data || {}
  const am = e.amonestaciones || {}
  return (
    <Modal titulo={'Expediente de ' + (e.chofer || '…')} onClose={onCerrar}>
      {cargando ? <Spinner /> : (
        <>
          <div className="grid g4">
            <Kpi valor={e.citas_confirmadas ?? '—'} etiqueta="Citas confirmadas" />
            <Kpi valor={e.citas_cumplidas ?? '—'} etiqueta="Cumplidas" />
            <Kpi valor={e.faltas ?? '—'} etiqueta="Faltas" tono={e.faltas ? 'alert' : ''} />
            <Kpi valor={e.cumplimiento == null ? '—' : e.cumplimiento + '%'}
                 etiqueta="Cumplimiento"
                 tono={e.cumplimiento != null && e.cumplimiento < 70 ? 'alert' : ''} />
          </div>
          <p>
            Unidades: <strong>{(e.unidades || []).join(', ') || 'ninguna'}</strong>{' · '}
            préstamos recibidos: <strong>{e.prestamos_recibidos}</strong>{' · '}
            averías reportadas: <strong>{e.averias_reportadas}</strong>
          </p>
          <Card title="Amonestaciones"
                sub={(am.vigentes || 0) + ' vigente(s)'
                     + (am.anuladas ? ', ' + am.anuladas + ' sin efecto' : '')}>
            {!(am.amonestaciones || []).length ? (
              <Empty icono={IcoListo}>Ninguna amonestación</Empty>
            ) : (am.amonestaciones || []).map((a) => (
              <div className="list-item" key={a.id}>
                <div className="grow">
                  <div className="t">{a.consecutivo}ª · unidad {a.unidad}</div>
                  <div className="s">{a.motivo}</div>
                  <div className="s">Firmó {a.emitida_por} · {fmtFecha(a.fecha_emision)}</div>
                </div>
                <EstadoBadge estado={a.estado} />
              </div>
            ))}
          </Card>
        </>
      )}
      <div className="acciones">
        <button className="btn" onClick={onCerrar}>Cerrar</button>
      </div>
    </Modal>
  )
}
