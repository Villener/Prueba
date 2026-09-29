/** Los cuatro historiales del gerente: por mecánico, por unidad, por chofer y
 *  por taller.
 *
 *  DE DÓNDE SALIÓ ESTA PANTALLA. El administrador de taller ya asigna unidades a
 *  mecánicos dentro del Reporte de Mantenimiento, pero ese dato se quedaba
 *  adentro del formato: para saber qué le tocó a cada mecánico había que abrir
 *  reporte por reporte. La pregunta concreta del gerente fue «a qué mecánico le
 *  asignaron qué preventivos y sobre qué unidades», y de paso pidió lo mismo por
 *  unidad, por chofer y por taller, con su Excel.
 *
 *  UNA PANTALLA CON CUATRO VISTAS Y NO CUATRO PESTAÑAS. El menú del gerente ya
 *  tiene seis entradas y en 375 px la barra rueda de lado; meterle cuatro más lo
 *  volvería impracticable con guantes, que es como se usa en el piso. Además las
 *  cuatro comparten filtro —el mismo rango, el mismo buscador, el mismo botón de
 *  Excel—, y repartirlas en cuatro pestañas obligaría a volver a marcar las
 *  fechas cada vez que se cambia de pregunta. El control segmentado es el mismo
 *  que el Tablero usa para día/mes/año, así que no es un patrón nuevo.
 *
 *  EL BUSCADOR NO ES UN ADORNO. Son 42 técnicos, 442 choferes y 1,367 unidades.
 *  Una tabla de cuatrocientos renglones sin forma de buscar no se lee: se rueda
 *  hasta que uno se rinde. Filtra EN EL CLIENTE, sobre lo que ya se descargó,
 *  porque el servidor ya mandó la lista completa del rango y un viaje más por
 *  cada letra tecleada solo agregaría parpadeo.
 *
 *  LOS FILTROS QUE VE EL SERVIDOR Y LOS QUE NO. El rango, el tipo y el taller
 *  viajan a la API porque cambian LO QUE SE CALCULA. El texto del buscador no
 *  viaja: solo esconde renglones de lo ya calculado. Por eso el botón de Excel
 *  manda los tres primeros y no el cuarto — el archivo trae la tabla completa
 *  del rango, que es lo que el gerente sube a dirección, y no el recorte que
 *  tenía en pantalla mientras buscaba un apellido.
 *
 *  DONDE NO HAY BASE PARA UN PROMEDIO O UN PORCENTAJE SE ESCRIBE «—», NUNCA 0.
 *  Es la regla del repositorio y aquí aparece en cinco columnas distintas: días
 *  promedio del mecánico, días en taller de la unidad, cumplimiento del chofer,
 *  ocupación y días de reparación del taller. Un 0.0 de días afirma que se
 *  reparó en el acto y un 0% de cumplimiento pinta de incumplido a quien no
 *  falló a nada. En los CONTEOS el 0 sí es legítimo: hubo periodo y no hubo
 *  nada, que es un dato y no un hueco.
 */
import { useMemo, useState } from 'react'
import { api, fmtFecha, hoyTijuana } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoDescargar, IcoTecnico, Kpi, Modal,
  Regla, Spinner, Tabla, useApi, useToast,
} from '../../ui/index.js'

/* ------------------------------------------------------------- el filtro --- */
/** El rango que se propone al abrir: los últimos doce meses.
 *
 *  Es el espejo de `_rango_historial()` del servidor (gerente_controller.py), que
 *  pide `_rango_por_defecto("mes")`, y los dos valores tienen que ser el mismo: si
 *  dejaran de coincidir, esta pantalla y un enlace que alguien pegue a mano sin
 *  fechas mostrarían periodos distintos y nadie sabría cuál de los dos citar.
 *
 *  Doce meses y no treinta días porque un historial no es un tablero. Medido
 *  contra la base real: en treinta días hay 4 mecánicos con trabajo de 42, y la
 *  pantalla abriría casi vacía — que no se lee como «este mes hubo poco», se lee
 *  como «el sistema no tiene datos». En doce meses son 17 de 42, y los 25 en cero
 *  son justamente la información que el gerente vino a buscar.
 *
 *  Se arma con el constructor local `new Date(a, m, d)` y se vuelve a escribir a
 *  mano con padStart. NO con toISOString(): eso entrega la fecha en UTC, y desde
 *  las 17:00 de Tijuana en adelante UTC ya va en el día siguiente, así que el
 *  rango propuesto arrancaría un día corrido cada tarde. Es el mismo error que
 *  core/api.js documenta en hoyTijuana() y que reaparecería por la puerta de
 *  atrás. El constructor local además resuelve solo el desborde de mes, que es lo
 *  que se necesita para «once meses hacia atrás».
 *
 *  No se importa el `fechaYMD` de GerentePage.jsx, que hace exactamente esto,
 *  porque GerentePage importa esta pantalla: el import sería un ciclo. Es la
 *  misma razón por la que `letras()` vive en core/busqueda.js y no colgando de
 *  una de las dos pantallas que lo usan.
 */
function rangoInicial() {
  const hasta = hoyTijuana()
  const [a, m] = hasta.split('-').map(Number)
  // Once meses hacia atrás y no doce: el mes que contiene a `hasta` ya cuenta
  // como uno, y restar doce devolvería trece.
  const d = new Date(a, m - 12, 1)
  const desde = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-01'
  return { desde, hasta }
}

/** Lo que cambia entre las cuatro vistas, en un solo lugar.
 *
 *  `clave` es la llave del arreglo dentro de la respuesta y coincide con el
 *  nombre de la vista en las cuatro (`mecanicos`, `unidades`, …) porque así lo
 *  fija el contrato del servidor. Se escribe igual aquí de todos modos, en vez
 *  de reusar la variable de la vista, para que el día que un endpoint devuelva
 *  otra llave se cambie en este renglón y no haya que buscar por qué la tabla
 *  salió vacía.
 *
 *  `texto` es lo que mira el buscador. Se eligió campo por campo y no «todo lo
 *  que tenga la fila»: meter los conteos haría que teclear «3» encendiera media
 *  tabla, y el buscador dejaría de servir justo cuando la lista es larga.
 */
const VISTAS = {
  mecanicos: {
    titulo: 'Mecánicos', clave: 'mecanicos', ruta: '/gerente/historiales/mecanicos',
    singular: 'mecánico', plural: 'mecánicos',
    // Las unidades entran en la búsqueda a propósito: «a qué mecánico le tocó la
    // 1017» es la pregunta de atrás, y sin esto habría que abrir los 42 detalles
    // uno por uno para contestarla.
    texto: (f) => [f.nombre, f.especialidad, f.modalidad, f.taller, ...(f.unidades || [])],
  },
  unidades: {
    titulo: 'Unidades', clave: 'unidades', ruta: '/gerente/historiales/unidades',
    singular: 'unidad', plural: 'unidades',
    texto: (f) => [f.num_economico, f.marca, f.modelo, f.anio, f.estado, f.area, f.chofer],
  },
  choferes: {
    titulo: 'Choferes', clave: 'choferes', ruta: '/gerente/historiales/choferes',
    singular: 'chofer', plural: 'choferes',
    texto: (f) => [f.nombre, f.num_licencia, f.turno, f.ruta, ...(f.unidades || [])],
  },
  talleres: {
    titulo: 'Talleres', clave: 'talleres', ruta: '/gerente/historiales/talleres',
    singular: 'taller', plural: 'talleres',
    texto: (f) => [f.nombre, f.tipo],
  },
}

const ORDEN_VISTAS = ['mecanicos', 'unidades', 'choferes', 'talleres']

/** El taller solo acota dos de las cuatro vistas, y hay que decir cuáles.
 *
 *  En mecánicos y en unidades el servidor recibe `taller_id` y recalcula. En
 *  choferes no: un chofer no pertenece a un taller, pertenece a una ruta. Y en
 *  talleres menos, porque la lista ES de talleres — filtrarla por taller sería
 *  dejar un renglón. Mostrar el selector apagado en esas dos invitaría a moverlo
 *  y a concluir que está roto cuando no pasara nada.
 */
const CON_TALLER = { mecanicos: true, unidades: true, choferes: false, talleres: false }

/* ------------------------------------------------------------- utilidades -- */
/** Texto comparable: sin mayúsculas y sin acentos.
 *
 *  Sin quitar los acentos, buscar «Ramon» no encuentra a «Ramón» y buscar
 *  «Alamos» no encuentra «Álamos». En una base donde los nombres vienen de tres
 *  importaciones distintas —unos con acento y otros sin él— eso hace que el
 *  buscador falle de forma intermitente, que es peor que no tenerlo: el gerente
 *  concluye que el mecánico no existe.
 */
const normaliza = (v) =>
  String(v ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Un número que puede no existir. `—` y nunca 0. Ver la nota de arriba. */
const num = (v) => (v == null ? '—' : v)
const pct = (v) => (v == null ? '—' : v + '%')
const dias = (v) => (v == null ? '—' : v + ' d')

/** El tono del porcentaje de cumplimiento, o ninguno si no hay porcentaje.
 *  Un chofer sin citas no se pinta de rojo: no falló, no le tocaba nada. */
const tonoCumplimiento = (v) =>
  v == null ? '' : v >= 90 ? 'ok' : v >= 70 ? 'warn' : 'danger'

/* ============================================================ la pantalla == */
export default function Historiales() {
  const toast = useToast()
  const [vista, setVista] = useState('mecanicos')
  const [rango, setRango] = useState(rangoInicial)
  const [q, setQ] = useState('')
  const [tipo, setTipo] = useState('todos')
  const [tallerId, setTallerId] = useState('')
  const [todasLasUnidades, setTodasLasUnidades] = useState(false)
  const [detalle, setDetalle] = useState(null)
  const [bajando, setBajando] = useState(false)

  const { desde, hasta } = rango
  const cfg = VISTAS[vista]

  // El catálogo de talleres sale de /admin/talleres, que ya acepta el rol
  // gerente (`admin_o_gerente` en administrador_controller.py) y es el mismo que
  // alimenta el selector de la pestaña de Indicadores. Tener dos catálogos de
  // talleres vivos es como se llega a que un taller nuevo aparezca en una
  // pantalla y en la otra no.
  const talleres = useApi(() => api.get('/admin/talleres'))

  // `|| undefined` y no el valor pelado: si el gerente vacía un calendario el
  // input entrega cadena vacía, y una cadena vacía SÍ viaja en la URL (`?desde=`)
  // porque api.js solo descarta null y undefined. El servidor anota el parámetro
  // como `date | None` y responde 422 ante una cadena vacía, así que la pantalla
  // se llenaría de rojo mientras alguien está a media edición.
  const params = {
    desde: desde || undefined,
    hasta: hasta || undefined,
    tipo: vista === 'mecanicos' ? tipo : undefined,
    taller_id: CON_TALLER[vista] && tallerId ? Number(tallerId) : undefined,
    solo_con_actividad: vista === 'unidades' && todasLasUnidades ? false : undefined,
  }

  // UNA sola consulta, la de la vista que se está mirando. Pedir las cuatro al
  // abrir serían cuatro recorridos completos de la base —la de unidades cruza
  // cinco tablas de toda la flota— para enseñar una.
  const datos = useApi(() => api.get(cfg.ruta, params),
                       [vista, desde, hasta, tipo, tallerId, todasLasUnidades])

  const filas = (datos.data && datos.data[cfg.clave]) || []
  const visibles = useMemo(() => {
    const t = normaliza(q).trim()
    if (!t) return filas
    // Se parte en palabras para que «ramon alamos» encuentre al de Álamos sin
    // exigir que las dos palabras salgan pegadas y en ese orden.
    const partes = t.split(/\s+/)
    return filas.filter((f) => {
      const heno = cfg.texto(f).map(normaliza).join(' ')
      return partes.every((p) => heno.includes(p))
    })
  }, [filas, q, cfg])

  const exportar = async () => {
    setBajando(true)
    try {
      // Los MISMOS filtros que tiene puesta la pantalla, menos el texto del
      // buscador (ver la nota de arriba del archivo). El nombre del archivo lo
      // decide el servidor y trae dentro el rango y el filtro realmente
      // exportados, así que se muestra tal cual: si el rango venía al revés y se
      // corrigió, el gerente lo ve en el aviso.
      const nombre = await api.descargar('/gerente/exportar/historial/' + vista,
                                         { params })
      toast(`Se descargó ${nombre}`)
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setBajando(false)
    }
  }

  return (
    <>
      <div className="card-head">
        <h1>Historiales</h1>
        <div className="btn-row" style={{ marginLeft: 'auto' }}>
          <button className="btn sm primary" onClick={exportar} disabled={bajando}>
            <IcoDescargar size={13} className="ico-inline" aria-hidden="true" />
            {bajando ? 'Generando…' : 'Exportar a Excel'}
          </button>
        </div>
      </div>

      {/* El selector de vista. Es el mismo control segmentado del Tablero: son
          cuatro caras de una decisión (por quién quiero ver la historia), no
          cuatro botones sueltos. */}
      <div className="segmentado bloque" role="group" aria-label="Ver el historial por">
        {ORDEN_VISTAS.map((v) => (
          <button key={v} className={'btn sm' + (vista === v ? ' primario' : '')}
                  aria-pressed={vista === v}
                  onClick={() => { setVista(v); setQ('') }}>
            {VISTAS[v].titulo}
          </button>
        ))}
      </div>

      {/* La barra de filtro. Se dibuja SIEMPRE, también mientras la tabla carga:
          si se ocultara detrás del spinner, cada cambio de fecha desmontaría el
          <input> que el gerente acaba de tocar y el calendario se cerraría solo
          a media elección. Es la misma razón que ya está escrita en el Tablero. */}
      <div className="card filtro-rango">
        <div className="field">
          <label htmlFor="hist-desde">Desde</label>
          <input id="hist-desde" type="date" value={desde}
                 onChange={(e) => setRango((r) => ({ ...r, desde: e.target.value }))} />
        </div>
        <div className="field">
          <label htmlFor="hist-hasta">Hasta</label>
          <input id="hist-hasta" type="date" value={hasta}
                 onChange={(e) => setRango((r) => ({ ...r, hasta: e.target.value }))} />
        </div>
        <div className="field busca">
          <label htmlFor="hist-q">Buscar</label>
          <input id="hist-q" type="search" value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder={vista === 'mecanicos' ? 'Nombre, taller, unidad…'
                   : vista === 'unidades' ? 'Económico, modelo, chofer…'
                   : vista === 'choferes' ? 'Nombre, ruta, licencia…' : 'Nombre del taller…'} />
        </div>

        {CON_TALLER[vista] && (
          <div className="field">
            <label htmlFor="hist-taller">Taller</label>
            <select id="hist-taller" value={tallerId}
                    onChange={(e) => setTallerId(e.target.value)}>
              <option value="">Todos</option>
              {(talleres.data || []).map((t) => (
                <option key={t.id} value={t.id}>{t.nombre}</option>
              ))}
            </select>
          </div>
        )}

        {vista === 'mecanicos' && (
          <div className="field tipo">
            {/* <span> y no <label>: lo que se nombra es el GRUPO de tres botones,
                y un <label> sin control asociado el lector de pantalla lo anuncia
                suelto. Es el mismo patrón que «Agrupar por» en el Tablero. */}
            <span className="lbl-campo">Tipo</span>
            <div className="segmentado" role="group" aria-label="Tipo de servicio">
              {[['preventivo', 'Preventivos'], ['correctivo', 'Correctivos'],
                ['todos', 'Todos']].map(([v, t]) => (
                <button key={v} className={'btn sm' + (tipo === v ? ' primario' : '')}
                        aria-pressed={tipo === v} onClick={() => setTipo(v)}>{t}</button>
              ))}
            </div>
          </div>
        )}

        {vista === 'unidades' && (
          /* Por omisión la lista trae solo las unidades que pisaron el taller en
             el rango, que de 1,367 son unas 460. Sin esta casilla, buscar una
             unidad que no tuvo movimiento devuelve cero renglones y eso se lee
             como «esa unidad no existe», que es la conclusión contraria a la
             correcta: existe y no entró, que es justo lo que se quería saber. */
          <label className="casilla">
            <input type="checkbox" checked={todasLasUnidades}
                   onChange={(e) => setTodasLasUnidades(e.target.checked)} />
            Incluir unidades sin movimiento
          </label>
        )}
      </div>

      {datos.cargando ? <Spinner /> : datos.error ? (
        <Aviso tipo="err">{datos.error}</Aviso>
      ) : (
        <>
          {/* El recorte del servidor se dice con todas sus letras. Una lista
              cortada en silencio se lee como «esto es todo lo que hay», que es
              peor que no darla: el gerente concluye que la flota es más chica. */}
          {datos.data?.aviso && <Aviso tipo="warn">{datos.data.aviso}</Aviso>}
          <RangoReal pedido={rango} devuelto={datos.data} />

          <Resumen vista={vista} filas={filas} />

          <Card title={cfg.titulo}
                sub={leyendaCuenta(visibles.length, filas.length, q, cfg)}>
            <TablaVista vista={vista} filas={visibles}
                        onAbrir={(f) => setDetalle(f)} />
            <NotaDeLaVista vista={vista} />
          </Card>
        </>
      )}

      {detalle && (
        <Detalle vista={vista} fila={detalle} rango={rango} tipo={tipo}
                 onCerrar={() => setDetalle(null)} />
      )}
    </>
  )
}

/** «12 de 42 mecánicos» mientras se busca, «42 mecánicos» cuando no.
 *
 *  Los dos números van juntos a propósito: enseñar solo el de arriba haría que
 *  una búsqueda con una errata («Ramom») se viera igual que una lista corta de
 *  verdad, y el gerente se llevaría la conclusión de que hay doce mecánicos.
 */
function leyendaCuenta(mostrados, total, q, cfg) {
  const nombre = total === 1 ? cfg.singular : cfg.plural
  if (!q.trim()) return `${total} ${nombre}`
  return `${mostrados} de ${total} ${nombre} · filtrando por «${q.trim()}»`
}

/** Avisa cuando el servidor usó un rango distinto del que se pidió.
 *
 *  Si los dos calendarios vienen al revés, el servidor los intercambia en vez de
 *  devolver una pantalla en blanco —una pantalla en blanco no dice «te
 *  equivocaste de calendario», deja pensando que no hubo movimiento, que es la
 *  conclusión contraria—. Cuando eso pasa hay que DECIRLO, o el gerente está
 *  leyendo un periodo distinto del que marcó.
 */
function RangoReal({ pedido, devuelto }) {
  if (!devuelto || !pedido.desde || !pedido.hasta) return null
  if (devuelto.desde === pedido.desde && devuelto.hasta === pedido.hasta) return null
  return (
    <Aviso tipo="info">
      Los calendarios venían al revés. Se está mostrando del{' '}
      <strong>{fmtFecha(devuelto.desde)}</strong> al <strong>{fmtFecha(devuelto.hasta)}</strong>.
    </Aviso>
  )
}

/* ------------------------------------------------------------- el resumen -- */
/** Los cuatro números de arriba, calculados sobre la lista COMPLETA del rango.
 *
 *  Sobre la completa y no sobre la filtrada por el buscador: son el retrato del
 *  periodo, y si se movieran al teclear se leerían como si el taller cambiara
 *  mientras uno busca un apellido.
 *
 *  En mecánicos el número que importa no es el promedio sino CUÁNTOS ESTÁN EN
 *  CERO. Con los datos de hoy son 25 de 42 en doce meses, y esa es la lectura
 *  útil: si son quince, el problema no es de los mecánicos, es de cómo se
 *  reparte el trabajo — o de que nadie lo está capturando, que se atiende
 *  distinto y también hay que poder verlo.
 */
function Resumen({ vista, filas }) {
  const suma = (k) => filas.reduce((a, f) => a + (f[k] || 0), 0)
  if (!filas.length) return null

  if (vista === 'mecanicos') {
    const enCero = filas.filter((f) => !f.trabajos).length
    return (
      <div className="grid g4">
        <Kpi valor={filas.length} etiqueta="Técnicos activos" />
        <Kpi valor={filas.length - enCero} etiqueta="Con trabajo en el rango" />
        <Kpi valor={enCero} etiqueta="Sin un solo trabajo" tono={enCero ? 'warn' : 'ok'}
             hint="Puede ser que nadie les asigna nada o que nadie lo captura" />
        <Kpi valor={suma('preventivos')} etiqueta="Preventivos atendidos" />
      </div>
    )
  }
  if (vista === 'unidades') {
    return (
      <div className="grid g4">
        <Kpi valor={filas.length} etiqueta="Unidades en la lista" />
        <Kpi valor={suma('entradas_taller')} etiqueta="Entradas a taller" />
        <Kpi valor={suma('ordenes')} etiqueta="Órdenes" />
        <Kpi valor={suma('faltas')} etiqueta="Faltas a cita"
             tono={suma('faltas') ? 'warn' : 'ok'} />
      </div>
    )
  }
  if (vista === 'choferes') {
    const conFalta = filas.filter((f) => f.faltas).length
    return (
      <div className="grid g4">
        <Kpi valor={filas.length} etiqueta="Choferes" />
        <Kpi valor={suma('citas')} etiqueta="Citas del rango" />
        <Kpi valor={suma('faltas')} etiqueta="Faltas" tono={suma('faltas') ? 'alert' : 'ok'}
             hint={`${conFalta} chofer(es) con al menos una`} />
        <Kpi valor={suma('amonestaciones')} etiqueta="Amonestaciones" />
      </div>
    )
  }
  return (
    <div className="grid g4">
      <Kpi valor={filas.length} etiqueta="Talleres" />
      <Kpi valor={suma('ordenes')} etiqueta="Órdenes recibidas" />
      <Kpi valor={suma('preventivos')} etiqueta="Preventivos" />
      <Kpi valor={suma('tecnicos')} etiqueta="Técnicos adscritos" />
    </div>
  )
}

/* -------------------------------------------------------------- la tabla --- */
function TablaVista({ vista, filas, onAbrir }) {
  if (vista === 'mecanicos') {
    return (
      <Tabla
        vacio="Ningún técnico coincide con la búsqueda"
        onFila={onAbrir}
        filas={filas}
        columnas={[
          { k: 'nombre', t: 'Mecánico',
            r: (f) => (
              <>
                {f.nombre}
                {/* El que no tiene un solo trabajo se MARCA y se queda en la
                    lista. Esconderlo sería esconder la pregunta. */}
                {!f.trabajos && <> <Badge tono="warn">sin trabajos</Badge></>}
              </>
            ) },
          { k: 'especialidad', t: 'Especialidad' },
          { k: 'modalidad', t: 'Modalidad',
            r: (f) => <Badge tono={f.modalidad === 'AUTONOMO' ? 'ok' : ''}>{f.modalidad}</Badge> },
          { k: 'taller', t: 'Taller' },
          { k: 'trabajos', t: 'Trabajos', num: true },
          { k: 'preventivos', t: 'Prev.', num: true },
          { k: 'correctivos', t: 'Corr.', num: true },
          { k: 'unidades_distintas', t: 'Unidades', num: true },
          { k: 'unidades', t: 'Cuáles',
            r: (f) => (f.unidades || []).join(', ') || '—' },
          { k: 'ultimo_trabajo', t: 'Último',
            r: (f) => (f.ultimo_trabajo ? fmtFecha(f.ultimo_trabajo) : '—') },
        ]} />
    )
  }

  if (vista === 'unidades') {
    return (
      <Tabla
        vacio="Ninguna unidad coincide con la búsqueda"
        onFila={onAbrir}
        filas={filas}
        columnas={[
          { k: 'num_economico', t: 'Unidad' },
          { k: 'modelo', t: 'Modelo',
            r: (f) => [f.marca, f.modelo].filter(Boolean).join(' ') || '—' },
          { k: 'anio', t: 'Año', num: true },
          { k: 'area', t: 'Área' },
          { k: 'chofer', t: 'Chofer' },
          { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
          { k: 'entradas_taller', t: 'Entradas', num: true },
          { k: 'ordenes', t: 'Órdenes', num: true },
          { k: 'preventivos', t: 'Prev.', num: true },
          { k: 'citas', t: 'Citas', num: true },
          { k: 'faltas', t: 'Faltas', num: true,
            r: (f) => (f.faltas ? <Badge tono="danger">{f.faltas}</Badge> : '0') },
          { k: 'dias_en_taller_total', t: 'Días en taller', num: true,
            r: (f) => dias(f.dias_en_taller_total) },
          { k: 'ultima_entrada', t: 'Última entrada',
            r: (f) => (f.ultima_entrada ? fmtFecha(f.ultima_entrada) : '—') },
        ]} />
    )
  }

  if (vista === 'choferes') {
    return (
      <Tabla
        vacio="Ningún chofer coincide con la búsqueda"
        onFila={onAbrir}
        filas={filas}
        columnas={[
          { k: 'nombre', t: 'Chofer' },
          // «Licencia» y no «N.º de empleado»: la tabla de choferes no guarda el
          // número de empleado —esa columna es de `tecnico`— y poner la licencia
          // debajo de un encabezado que dice otra cosa sería etiquetar mal un
          // dato real, que es la forma más difícil de detectar de mentir.
          { k: 'num_licencia', t: 'Licencia' },
          { k: 'turno', t: 'Turno' },
          { k: 'ruta', t: 'Ruta' },
          { k: 'unidades', t: 'Unidades', r: (f) => (f.unidades || []).join(', ') || '—' },
          { k: 'citas', t: 'Citas', num: true },
          { k: 'cumplidas', t: 'Cumplidas', num: true },
          { k: 'faltas', t: 'Faltas', num: true,
            r: (f) => (f.faltas ? <Badge tono="danger">{f.faltas}</Badge> : '0') },
          { k: 'cumplimiento', t: '%', num: true,
            r: (f) => (f.cumplimiento == null ? '—'
              : <Badge tono={tonoCumplimiento(f.cumplimiento)}>{f.cumplimiento}%</Badge>) },
          { k: 'averias', t: 'Averías', num: true },
          { k: 'amonestaciones', t: 'Amonest.', num: true },
        ]} />
    )
  }

  return (
    <Tabla
      vacio="Ningún taller coincide con la búsqueda"
      onFila={onAbrir}
      filas={filas}
      columnas={[
        { k: 'nombre', t: 'Taller' },
        { k: 'tipo', t: 'Tipo' },
        { k: 'ocupacion_pct', t: 'Ocupación', num: true,
          r: (f) => (f.ocupacion_pct == null ? '—'
            : <Badge tono={f.ocupacion_pct > 80 ? 'danger' : f.ocupacion_pct > 50 ? 'warn' : 'ok'}>
                {f.ocupacion_pct}%
              </Badge>) },
        { k: 'espacios', t: 'Espacios',
          r: (f) => `${f.espacios_ocupados} de ${f.espacios_totales}` },
        { k: 'tecnicos', t: 'Técnicos', num: true },
        { k: 'ordenes', t: 'Órdenes', num: true },
        { k: 'preventivos', t: 'Prev.', num: true },
        { k: 'correctivos', t: 'Corr.', num: true },
        { k: 'citas', t: 'Citas', num: true },
        { k: 'ordenes_cerradas', t: 'Cerradas', num: true },
        { k: 'dias_promedio_reparacion', t: 'Días prom.', num: true,
          r: (f) => dias(f.dias_promedio_reparacion) },
        { k: 'unidades_distintas', t: 'Unidades', num: true },
      ]} />
  )
}

/** La nota al pie de cada vista: lo que el número NO dice.
 *
 *  Cada una cita la limitación real del modelo que hay detrás. Callarlas produce
 *  un número que parece bueno y que alguien va a citar en una junta.
 */
function NotaDeLaVista({ vista }) {
  if (vista === 'mecanicos') {
    return (
      <Regla>
        Un <strong>trabajo</strong> es un técnico en una estancia de la unidad, ya
        deduplicado entre el reporte de mantenimiento y la orden de servicio: el mismo paso
        por el taller llega por las dos vías y sumarlas le duplicaría los trabajos.
        <strong> Trabajos</strong> no siempre es preventivos + correctivos — las órdenes de
        tipo «siniestro» cuentan como trabajo y no caen en ninguna de las dos columnas.
        La columna <strong>Cuáles</strong> trae como mucho 12 económicos: es una muestra, el
        total va al lado en <strong>Unidades</strong>, y el buscador solo puede encontrar los
        que están escritos ahí. Los técnicos en cero <strong>se listan</strong>: son 36 de 42
        en modalidad ASISTIDO, que no usan la aplicación, así que su trabajo siempre depende
        de que alguien más lo capture.
      </Regla>
    )
  }
  if (vista === 'unidades') {
    return (
      <Regla>
        <strong>Días en taller</strong> suma únicamente las órdenes que ya cerraron: va en
        «—» cuando ninguna cerró, porque un 0 diría que la unidad no pasó ni un día adentro
        y con órdenes abiertas pasa lo contrario. El <strong>área</strong> no es una columna
        de la unidad: es la que anotó el taller en su último movimiento del rango. Y el
        <strong> chofer</strong> es el poseedor de hoy, no el que la traía en cada entrada.
      </Regla>
    )
  }
  if (vista === 'choferes') {
    return (
      <Regla>
        El <strong>%</strong> solo cuenta citas con desenlace —cumplidas contra faltas—: una
        cita confirmada que todavía no llega no es un incumplimiento, y meterla en el
        denominador pintaba de 0% a quien no había fallado a nada. Por eso va en «—» y no en
        0% en el chofer al que el taller nunca le dio cita. No hay columna de número de
        empleado porque la tabla de choferes no guarda ese dato; lo que existe es la
        licencia.
      </Regla>
    )
  }
  return (
    <Regla>
      <strong>Espacios</strong> y <strong>ocupación</strong> son la foto de este momento, no
      del rango: no se guarda una foto diaria del patio, así que no se puede saber qué había
      adentro un martes de marzo. <strong>Órdenes</strong> cuenta las que ENTRARON en el
      rango; <strong>días prom.</strong> se calcula sobre las que CERRARON, que es el mismo
      criterio de la pestaña Indicadores — tiene que serlo, o el mismo gerente vería dos
      números distintos de lo mismo en dos pantallas.
    </Regla>
  )
}

/* ------------------------------------------------------------- el detalle -- */
/** Abre el expediente de la fila en la que se hizo clic.
 *
 *  Va en Modal y no en una ruta aparte porque el gerente está recorriendo una
 *  lista: cerrar el detalle tiene que devolverlo al renglón donde estaba, con el
 *  buscador y el rango intactos. Una vista de detalle con su propia URL
 *  obligaría a volver a teclear la búsqueda en cada vuelta, y son 442 choferes.
 */
function Detalle({ vista, fila, rango, tipo, onCerrar }) {
  if (vista === 'mecanicos') {
    return <DetalleMecanico id={fila.tecnico_id} rango={rango} tipo={tipo} onCerrar={onCerrar} />
  }
  if (vista === 'unidades') {
    return <DetalleUnidad id={fila.unidad_id} rango={rango} onCerrar={onCerrar} />
  }
  if (vista === 'choferes') {
    return <DetalleChofer id={fila.chofer_id} rango={rango} onCerrar={onCerrar} />
  }
  return <DetalleTaller id={fila.taller_id} rango={rango} onCerrar={onCerrar} />
}

/** Marco común de los cuatro detalles: el título, el spinner y el botón de
 *  cerrar. Sin esto los cuatro repetirían el mismo armazón y acabarían
 *  divergiendo en detalles tontos —uno con el botón y otro sin él—. */
function MarcoDetalle({ titulo, cargando, error, onCerrar, children }) {
  return (
    <Modal titulo={titulo} onClose={onCerrar}>
      {cargando ? <Spinner /> : error ? <Aviso tipo="err">{error}</Aviso> : children}
      <div className="acciones">
        <button className="btn" onClick={onCerrar}>Cerrar</button>
      </div>
    </Modal>
  )
}

function DetalleMecanico({ id, rango, tipo, onCerrar }) {
  const { data, cargando, error } = useApi(
    () => api.get('/gerente/historiales/mecanicos/' + id,
                  { desde: rango.desde || undefined, hasta: rango.hasta || undefined, tipo }),
    [id, rango.desde, rango.hasta, tipo])
  const t = data?.tecnico || {}
  const r = data?.resumen || {}
  const trabajos = data?.trabajos || []

  return (
    <MarcoDetalle titulo={t.nombre || 'Mecánico'} cargando={cargando} error={error}
                  onCerrar={onCerrar}>
      <p className="sub">
        {[t.especialidad, t.modalidad, t.taller].filter(Boolean).join(' · ')}
        {data && <> · del {fmtFecha(data.desde)} al {fmtFecha(data.hasta)}</>}
        {tipo !== 'todos' && <> · solo {tipo}s</>}
      </p>

      <div className="grid g4">
        <Kpi valor={num(r.trabajos)} etiqueta="Trabajos" />
        <Kpi valor={num(r.preventivos)} etiqueta="Preventivos" />
        <Kpi valor={num(r.correctivos)} etiqueta="Correctivos" />
        <Kpi valor={num(r.unidades_distintas)} etiqueta="Unidades distintas" />
      </div>
      <div className="grid g2">
        <Kpi valor={dias(r.dias_promedio)} etiqueta="Días promedio de la estancia"
             hint="Solo las estancias que ya cerraron" />
        <Kpi valor={trabajos.length ? fmtFecha(trabajos[0].fecha) : '—'}
             etiqueta="Último trabajo" />
      </div>

      {!cargando && !trabajos.length ? (
        <>
          <Empty icono={IcoTecnico}>Sin trabajos en el rango</Empty>
          <Regla>
            Un mecánico en cero <strong>es información</strong>, no un faltante: puede ser que
            nadie le asignó nada o que nadie lo capturó, y las dos cosas se atienden. Prueba a
            ampliar el rango o a quitar el filtro de tipo antes de concluir.
          </Regla>
        </>
      ) : (
        <Tabla
          vacio="Sin trabajos en el rango"
          filas={trabajos}
          columnas={[
            { k: 'fecha', t: 'Fecha', r: (f) => fmtFecha(f.fecha) },
            { k: 'unidad', t: 'Unidad' },
            { k: 'tipo_servicio', t: 'Tipo',
              r: (f) => <Badge tono={f.tipo_servicio === 'preventivo' ? 'ok' : 'warn'}>
                {f.tipo_servicio}</Badge> },
            { k: 'sistema', t: 'Sistema' },
            { k: 'actividad', t: 'Actividad' },
            { k: 'folio', t: 'Folio',
              r: (f) => (f.folio_orden && f.folio_orden !== f.folio
                ? `${f.folio} · ${f.folio_orden}` : f.folio || '—') },
            { k: 'taller', t: 'Taller' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
          ]} />
      )}

      <Regla>
        El <strong>estado</strong> se deja en el vocabulario de donde salió el renglón: del
        lado del reporte una actividad queda «realizada» o «pendiente», y del lado de la orden
        existen «en espera», «en proceso» y «terminada». Forzar los dos a una sola escala
        inventaría un estado que nadie escribió. Cuando el renglón trae dos folios, es el
        mismo paso por el taller visto desde el reporte y desde la orden.
      </Regla>
    </MarcoDetalle>
  )
}

const TONO_EVENTO = {
  entrada: '', orden: 'info', reporte: 'info', cita: 'warn', averia: 'danger',
}

function DetalleUnidad({ id, rango, onCerrar }) {
  const { data, cargando, error } = useApi(
    () => api.get('/gerente/historiales/unidades/' + id,
                  { desde: rango.desde || undefined, hasta: rango.hasta || undefined }),
    [id, rango.desde, rango.hasta])
  const u = data?.unidad || {}
  const r = data?.resumen || {}

  return (
    <MarcoDetalle titulo={'Unidad ' + (u.num_economico || '')} cargando={cargando} error={error}
                  onCerrar={onCerrar}>
      <p className="sub">
        {[u.marca, u.modelo, u.anio, u.placas].filter(Boolean).join(' · ')}
        {u.chofer && <> · poseedor actual: <strong>{u.chofer}</strong></>}
        {data && <> · del {fmtFecha(data.desde)} al {fmtFecha(data.hasta)}</>}
      </p>
      {/* En pestaña nueva y no navegando: este detalle es un modal A PROPÓSITO
          para no perder el buscador ni el rango, y navegar desmontaría toda la
          pantalla de Historiales. La sesión vive en localStorage, así que la
          pestaña nueva ya entra con ella. */}
      <div className="btn-row" style={{ marginBottom: 10 }}>
        <a className="btn sm" href={`#/bitacora/${id}`} target="_blank" rel="noreferrer">
          Libro de bitácora (NOM-030)
        </a>
      </div>

      <div className="grid g4">
        <Kpi valor={num(r.entradas_taller)} etiqueta="Entradas a taller" />
        <Kpi valor={num(r.ordenes)} etiqueta="Órdenes" />
        <Kpi valor={num(r.preventivos)} etiqueta="Preventivos" />
        <Kpi valor={num(r.correctivos)} etiqueta="Correctivos" />
      </div>
      <div className="grid g4">
        <Kpi valor={num(r.citas)} etiqueta="Citas" />
        <Kpi valor={num(r.faltas)} etiqueta="Faltas" tono={r.faltas ? 'warn' : ''} />
        <Kpi valor={num(r.averias)} etiqueta="Averías" tono={r.averias ? 'alert' : ''} />
        <Kpi valor={dias(r.dias_en_taller_total)} etiqueta="Días en taller"
             hint="Solo las órdenes que ya cerraron" />
      </div>

      {data?.aviso && <Aviso tipo="warn">{data.aviso}</Aviso>}

      <Card title="Línea de tiempo" sub="Lo más reciente primero">
        <Tabla
          vacio="Sin movimientos en el rango"
          filas={data?.eventos || []}
          columnas={[
            { k: 'fecha', t: 'Fecha', r: (f) => fmtFecha(f.fecha) },
            { k: 'tipo', t: 'Qué pasó',
              r: (f) => <Badge tono={TONO_EVENTO[f.tipo] ?? ''}>{f.tipo}</Badge> },
            { k: 'folio', t: 'Folio' },
            { k: 'taller', t: 'Taller' },
            { k: 'detalle', t: 'Detalle' },
            { k: 'tecnico', t: 'Atendió' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
          ]} />
      </Card>

      <Regla>
        La <strong>entrada</strong> viene del histórico del área y ahí «atendió» es el apodo
        que escribió el taller («RIVAS», «RESENDIZ»), no una cuenta del sistema: sirve para
        rastrear, no para medir a nadie. Las <strong>averías</strong> ocurren en carretera y
        no tienen taller. Una <strong>orden</strong> cuenta en el día que la unidad ENTRÓ —una
        que entró en enero y sigue abierta no puede faltar del historial de enero esperando a
        que cierre.
      </Regla>
    </MarcoDetalle>
  )
}

/** El expediente del chofer.
 *
 *  LO DELICADO AQUÍ SON LOS DOS HORIZONTES, y por eso van en dos bloques con
 *  título y no en una sola fila de cifras: el ACUMULADO es toda la vida del
 *  chofer —expediente() no admite fechas— y el RANGO es lo que el gerente marcó
 *  en los calendarios. Mezclados, el gerente resta el detalle del total y no
 *  entiende por qué no cuadra; y si alguien cita el acumulado creyendo que es
 *  del mes, está sosteniendo una amonestación con un número que no es.
 */
function DetalleChofer({ id, rango, onCerrar }) {
  const { data, cargando, error } = useApi(
    () => api.get('/gerente/historiales/choferes/' + id,
                  { desde: rango.desde || undefined, hasta: rango.hasta || undefined }),
    [id, rango.desde, rango.hasta])
  const a = data?.acumulado || {}
  const r = data?.rango || {}
  const am = a.amonestaciones || {}

  return (
    <MarcoDetalle titulo={data?.nombre || 'Chofer'} cargando={cargando} error={error}
                  onCerrar={onCerrar}>
      <p className="sub">
        {[data?.num_licencia && 'licencia ' + data.num_licencia, data?.turno,
          data?.ruta && 'ruta ' + data.ruta, data?.perfil].filter(Boolean).join(' · ')}
      </p>

      <h3 style={{ margin: '12px 0 6px' }}>
        En el rango {data && <span className="sub">· del {fmtFecha(r.desde)} al {fmtFecha(r.hasta)}</span>}
      </h3>
      <div className="grid g4">
        <Kpi valor={num(r.citas)} etiqueta="Citas" />
        <Kpi valor={num(r.cumplidas)} etiqueta="Cumplidas" />
        <Kpi valor={num(r.faltas)} etiqueta="Faltas" tono={r.faltas ? 'alert' : ''} />
        <Kpi valor={pct(r.cumplimiento)} etiqueta="Cumplimiento"
             tono={tonoCumplimiento(r.cumplimiento) === 'danger' ? 'alert' : ''} />
      </div>

      <h3 style={{ margin: '16px 0 6px' }}>Acumulado · toda su historia</h3>
      <div className="grid g4">
        <Kpi valor={num(a.citas_confirmadas)} etiqueta="Citas confirmadas" />
        <Kpi valor={num(a.citas_cumplidas)} etiqueta="Cumplidas" />
        <Kpi valor={num(a.faltas)} etiqueta="Faltas" tono={a.faltas ? 'alert' : ''} />
        <Kpi valor={pct(a.cumplimiento)} etiqueta="Cumplimiento" />
      </div>
      <p>
        Unidades: <strong>{(a.unidades || []).join(', ') || 'ninguna'}</strong>{' · '}
        préstamos recibidos: <strong>{num(a.prestamos_recibidos)}</strong>{' · '}
        averías reportadas: <strong>{num(a.averias_reportadas)}</strong>
      </p>

      {data?.aviso && <Aviso tipo="info">{data.aviso}</Aviso>}

      <Card title="Amonestaciones"
            sub={(am.vigentes || 0) + ' vigente(s)'
                 + (am.anuladas ? ', ' + am.anuladas + ' sin efecto' : '')}>
        {!(am.amonestaciones || []).length ? (
          <Empty>Ninguna amonestación</Empty>
        ) : (am.amonestaciones || []).map((x) => (
          <div className="list-item" key={x.id}>
            <div className="grow">
              <div className="t">{x.consecutivo}ª · unidad {x.unidad}</div>
              <div className="s">{x.motivo}</div>
              <div className="s">Firmó {x.emitida_por} · {fmtFecha(x.fecha_emision)}</div>
            </div>
            <EstadoBadge estado={x.estado} />
          </div>
        ))}
      </Card>

      <Card title="Sus citas en el rango">
        <Tabla
          vacio="Ninguna cita en el rango"
          filas={data?.citas || []}
          columnas={[
            { k: 'fecha', t: 'Fecha', r: (f) => fmtFecha(f.fecha) },
            { k: 'unidad', t: 'Unidad' },
            { k: 'taller', t: 'Taller' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            { k: 'veces_reprogramada', t: 'Reprogr.', num: true },
          ]} />
      </Card>

      <Card title="Entradas a taller de sus unidades"
            sub="Contesta «y mientras tanto, dónde estuvo el vehículo»">
        <Tabla
          vacio="Ninguna entrada en el rango"
          filas={data?.entradas_taller || []}
          columnas={[
            { k: 'fecha', t: 'Fecha', r: (f) => fmtFecha(f.fecha) },
            { k: 'unidad', t: 'Unidad' },
            { k: 'taller', t: 'Taller' },
            { k: 'detalle', t: 'Detalle' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
          ]} />
      </Card>

      <Regla>
        Una falta se le carga al chofer que dice el <strong>aviso</strong> —porque el aviso ya
        resolvió quién era el poseedor ESE día, y una unidad cambia de manos— y una cita sin
        aviso al poseedor actual. Es el mismo criterio de la pestaña de Indicadores: tener dos
        formas de atribuir en la misma aplicación es como se llega a que dos pantallas den
        números distintos del mismo chofer.
      </Regla>
    </MarcoDetalle>
  )
}

function DetalleTaller({ id, rango, onCerrar }) {
  const { data, cargando, error } = useApi(
    () => api.get('/gerente/historiales/talleres/' + id,
                  { desde: rango.desde || undefined, hasta: rango.hasta || undefined }),
    [id, rango.desde, rango.hasta])
  const t = data?.taller || {}
  const r = data?.resumen || {}

  return (
    <MarcoDetalle titulo={t.nombre || 'Taller'} cargando={cargando} error={error}
                  onCerrar={onCerrar}>
      <p className="sub">
        {[t.tipo, t.direccion, t.opera_sabado ? 'opera sábado' : null,
          t.activo === false ? 'dado de baja' : null].filter(Boolean).join(' · ')}
        {data && <> · del {fmtFecha(data.desde)} al {fmtFecha(data.hasta)}</>}
      </p>

      <div className="grid g4">
        <Kpi valor={pct(r.ocupacion_pct)} etiqueta="Ocupación (hoy)"
             hint={`${num(r.espacios_ocupados)} de ${num(r.espacios_totales)} espacios`} />
        <Kpi valor={num(r.ordenes)} etiqueta="Órdenes recibidas" />
        <Kpi valor={num(r.preventivos)} etiqueta="Preventivos" />
        <Kpi valor={dias(r.dias_promedio_reparacion)} etiqueta="Días prom. de reparación"
             hint={`Sobre ${num(r.ordenes_cerradas)} orden(es) cerrada(s)`} />
      </div>

      {data?.aviso && <Aviso tipo="warn">{data.aviso}</Aviso>}

      <Card title="Técnicos"
            sub={`${r.tecnicos_listados ?? 0} en la lista · ${num(r.tecnicos)} adscritos al taller`}>
        <Tabla
          vacio="Sin técnicos"
          filas={data?.tecnicos || []}
          columnas={[
            { k: 'nombre', t: 'Mecánico',
              r: (f) => (
                <>
                  {f.nombre}
                  {!f.trabajos && <> <Badge tono="warn">sin trabajos</Badge></>}
                </>
              ) },
            { k: 'especialidad', t: 'Especialidad' },
            { k: 'taller', t: 'Adscrito a' },
            { k: 'trabajos', t: 'Trabajos', num: true },
            { k: 'preventivos', t: 'Prev.', num: true },
            { k: 'correctivos', t: 'Corr.', num: true },
            { k: 'unidades_distintas', t: 'Unidades', num: true },
          ]} />
        <Regla>
          Los dos conteos miden cosas distintas y por eso no coinciden:{' '}
          <strong>adscritos</strong> es cuánta gente tiene el taller, y{' '}
          <strong>en la lista</strong> es cuánta pasó por él — incluye al técnico de otra
          planta que vino a ayudar, que es un viaje que hoy no queda registrado en ningún
          otro lado.
        </Regla>
      </Card>

      <Card title="Órdenes del rango"
            sub={data ? `${(data.ordenes || []).length} de ${data.total_ordenes}` : '…'}>
        <Tabla
          vacio="Sin órdenes en el rango"
          filas={data?.ordenes || []}
          columnas={[
            { k: 'folio', t: 'Folio' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'tipo', t: 'Tipo' },
            { k: 'fecha_entrada', t: 'Entrada', r: (f) => fmtFecha(f.fecha_entrada) },
            { k: 'fecha_salida', t: 'Salida', r: (f) => fmtFecha(f.fecha_salida) },
            { k: 'dias_en_taller', t: 'Días', num: true },
            { k: 'espacio', t: 'Espacio' },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
          ]} />
      </Card>
    </MarcoDetalle>
  )
}
