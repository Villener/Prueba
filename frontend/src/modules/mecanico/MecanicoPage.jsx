/** Módulo Mecánico autónomo — CU-MEC-01 a 12.
 *
 * ESTA PANTALLA ES EL ARREGLO DE LAS CUENTAS SIN ROL. Las seis cuentas de los
 * mecánicos de Tecate, Rosarito, Guaycura, Carranza y Valle Redondo existían en
 * producción con su contraseña buena y sin un solo rol: autenticaban y no les
 * tocaba ningún módulo, así que entraban, veían la aplicación vacía y concluían
 * que estaba descompuesta. Una cuenta que deja pasar y no lleva a ninguna parte
 * es peor que una que no existe.
 *
 * QUIÉN LA USA. Los de Álamos NO: tienen a Erick al lado y entregan en papel
 * (por eso son ASISTIDO y no tienen cuenta). El de la planta satélite está solo
 * —no hay quien capture por él— y es el único que puede.
 *
 * SE USA CON GUANTES Y A MEDIO PATIO. Por eso todo son tarjetas y botones
 * grandes en vez de tablas: el teléfono se sostiene con una mano.
 */
import { useEffect, useState } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import { Plano } from '../administrador/PlanoPage.jsx'
import { Solicitudes } from '../administrador/SolicitudesPage.jsx'
import { api, diaTijuana, fmtFecha, fmtFechaHora, hoyTijuana } from '../../core/api.js'
import {
  Aviso, Badge, BuscadorPieza, BuscadorUnidad, Card, Empty, EstadoBadge, IcoAlmacen,
  IcoBitacora, IcoListo, IcoUbicacion, Kpi, Modal, Regla, Spinner, Tabla, useApi, useToast,
} from '../../ui/index.js'

export default function Mecanico() {
  return (
    <Routes>
      <Route path="/" element={<MiTrabajo />} />
      {/* SU planta: el plano y las solicitudes de ingreso de ahi. El servidor
          no le da ninguna otra (Martin, 2026-10-07). */}
      <Route path="/planta" element={<Plano esMecanico />} />
      <Route path="/solicitudes" element={<Solicitudes esMecanico />} />
      <Route path="/auxilios" element={<Auxilios />} />
      <Route path="/piezas" element={<Piezas />} />
      <Route path="/traslados" element={<Traslados />} />
    </Routes>
  )
}

/* ========================================================== CU-MEC-01/02/06 */
function MiTrabajo() {
  const { data, cargando, error, recargar } = useApi(() => api.get('/mecanico/cola'))
  const [editando, setEditando] = useState(null)
  const [salida, setSalida] = useState(null)

  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="err">{error}</Aviso>
  const cola = data || []
  const pendientes = cola.filter((c) => !c.terminada)
  const listas = cola.filter((c) => c.terminada)

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Mi trabajo</h1>

      <div className="grid g3">
        <Kpi valor={pendientes.length} etiqueta="Sistemas pendientes"
             tono={pendientes.length ? 'warn' : 'ok'} />
        <Kpi valor={listas.length} etiqueta="Terminados" />
        <Kpi valor={new Set(cola.map((c) => c.folio)).size} etiqueta="Unidades" />
      </div>

      {!cola.length ? (
        <Card><Empty icono={IcoListo}>
          No tienes sistemas asignados en formatos abiertos.
        </Empty></Card>
      ) : cola.map((a) => (
        <Card key={a.actividad_id}
              title={`Unidad ${a.unidad} · ${a.sistema}`}
              sub={`${a.folio} · ${a.tipo_servicio} · entró ${fmtFecha(a.fecha_entrada)}`}
              actions={a.terminada
                ? <Badge tono="ok">Terminado</Badge>
                : <Badge tono="warn">Pendiente</Badge>}>

          {/* Las dos columnas del papel, una frente a otra. Se leen juntas
              porque esa comparación es lo que el supervisor firma. */}
          <div className="grid g2">
            <div>
              <div className="s"><strong>Lo que hay que hacerle</strong></div>
              <p className="sub">{a.a_realizar || '— sin diagnóstico todavía —'}</p>
            </div>
            <div>
              <div className="s"><strong>Lo que se le hizo</strong></div>
              <p className="sub">{a.realizada || '— nada capturado —'}</p>
            </div>
          </div>
          {a.fecha_realizada && (
            <p className="sub">Terminado el {fmtFechaHora(a.fecha_realizada)}</p>
          )}

          {!a.terminada && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn" onClick={() => setEditando({ a, modo: 'diagnostico' })}>
                {a.a_realizar ? 'Corregir diagnóstico' : 'Escribir diagnóstico'}
              </button>
              <button className="btn primary" onClick={() => setEditando({ a, modo: 'avance' })}>
                Capturar avance
              </button>
            </div>
          )}
          <div className="btn-row">
            <button className="btn sm" onClick={() => setSalida(a.reporte_id)}>
              Ver formato de salida
            </button>
            <Link className="btn sm" to={`/bitacora/${a.unidad_id}`}>
              <IcoBitacora size={13} className="ico-inline" aria-hidden="true" /> Bitácora
            </Link>
          </div>
        </Card>
      ))}

      <Regla>
        El diagnóstico y el avance son dos campos distintos a propósito: en el papel
        son dos columnas y compararlas es lo que se firma. Escribir el avance encima del
        diagnóstico dejaría sin con qué comparar.
      </Regla>

      {editando && (
        <ModalTexto datos={editando} onCerrar={() => setEditando(null)}
                    onListo={() => { setEditando(null); recargar() }} />
      )}
      {salida && <ModalSalida reporteId={salida} onCerrar={() => setSalida(null)} />}
    </>
  )
}

function ModalTexto({ datos, onCerrar, onListo }) {
  const { a, modo } = datos
  const diag = modo === 'diagnostico'
  const [texto, setTexto] = useState(diag ? (a.a_realizar || '') : (a.realizada || ''))
  const [terminada, setTerminada] = useState(false)
  // NOM-030 7.1.9 y 7.1.10: al terminar se registran inicio, término, resultado
  // y acciones requeridas. Las fechas se proponen (hoy) pero se DECLARAN: el
  // trabajo pudo empezar antier.
  const hoy = hoyTijuana()
  const [nom, setNom] = useState({
    fecha_inicio: a.fecha_inicio || hoy,
    fecha_termino: a.fecha_termino || hoy,
    resultado: a.resultado || '',
    acciones_requeridas: a.acciones_requeridas || '',
  })
  const [enviando, setEnviando] = useState(false)
  const toast = useToast()
  const setN = (k) => (e) => setNom({ ...nom, [k]: e.target.value })
  const elegirResultado = (valor) => {
    // «Ninguna» se PROPONE al elegir conforme, a la vista y editable: el campo
    // es obligatorio y casi siempre esa es la respuesta. Y se retira al pasar a
    // no conforme: si no cumple, algo hay que hacerle.
    let acciones = nom.acciones_requeridas
    if (valor === 'conforme' && !acciones.trim()) acciones = 'Ninguna'
    if (valor === 'no_conforme' && acciones.trim().toLowerCase() === 'ninguna') acciones = ''
    setNom({ ...nom, resultado: valor, acciones_requeridas: acciones })
  }
  const nomCompleto = nom.fecha_inicio && nom.fecha_termino && nom.resultado
    && nom.acciones_requeridas.trim() && nom.fecha_inicio <= nom.fecha_termino

  const enviar = async () => {
    setEnviando(true)
    try {
      if (diag) {
        await api.post(`/mecanico/actividades/${a.actividad_id}/diagnostico`,
                       undefined, { texto })
        toast('Diagnóstico guardado')
      } else {
        // Las acciones van en el cuerpo y no en la URL: son texto libre y la
        // URL se queda escrita en el log del servidor.
        await api.post(`/mecanico/actividades/${a.actividad_id}/avance`,
                       // Un avance no declara fechas: el campo no está a la vista, y
                       // una fecha que nadie vio no es una fecha declarada.
                       terminada ? { ...nom, resultado: nom.resultado || null } : undefined,
                       { texto, terminada })
        toast(terminada ? 'Sistema marcado como terminado' : 'Avance guardado')
      }
      onListo()
    } catch (e) { toast(e.message, 'err') } finally { setEnviando(false) }
  }

  return (
    <Modal titulo={`${diag ? 'Diagnóstico' : 'Avance'} · ${a.sistema}`} onClose={onCerrar}>
      <p className="sub">Unidad {a.unidad} · {a.folio}</p>
      {!diag && a.a_realizar && (
        <Aviso tipo="info"><strong>Se pidió:</strong> {a.a_realizar}</Aviso>
      )}
      <div className="field">
        <label>{diag ? '¿Qué hay que hacerle?' : '¿Qué le hiciste?'}</label>
        <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={4}
                  placeholder={diag
                    ? 'Ej. cambiar balatas delanteras y rectificar discos'
                    : 'Ej. balatas puestas, discos rectificados'} />
      </div>
      {!diag && (
        <>
          <label className="radio-fila">
            <input type="checkbox" checked={terminada}
                   onChange={(e) => setTerminada(e.target.checked)} />
            <span>Ya quedó: dar por terminado este sistema</span>
          </label>
          {terminada && (
            <div className="nom-captura">
              <div className="grid g2">
                <div className="field">
                  <label>Empezó el</label>
                  <input type="date" max={hoy} min={diaTijuana(a.fecha_entrada)}
                         value={nom.fecha_inicio} onChange={setN('fecha_inicio')} />
                </div>
                <div className="field">
                  <label>Terminó el</label>
                  <input type="date" max={hoy} min={nom.fecha_inicio} value={nom.fecha_termino}
                         onChange={setN('fecha_termino')} />
                </div>
              </div>
              <label className="radio-fila">
                <input type="radio" name="resultado" checked={nom.resultado === 'conforme'}
                       onChange={() => elegirResultado('conforme')} />
                <span>Conforme: quedó dentro de lo que se pide</span>
              </label>
              <label className="radio-fila">
                <input type="radio" name="resultado" checked={nom.resultado === 'no_conforme'}
                       onChange={() => elegirResultado('no_conforme')} />
                <span>No conforme: todavía no cumple</span>
              </label>
              <div className="field" style={{ marginTop: 10 }}>
                <label>Acciones requeridas</label>
                <textarea rows={2} value={nom.acciones_requeridas}
                          onChange={setN('acciones_requeridas')}
                          placeholder={nom.resultado === 'no_conforme'
                            ? 'Qué falta para que cumpla' : 'Ninguna'} />
              </div>
            </div>
          )}
          <Regla>
            Mientras no lo marques, se guarda como avance y puedes seguir escribiendo.
            Al terminar, la NOM-030 pide que el libro de bitácora diga cuándo empezó y
            terminó, si quedó conforme y qué acciones requiere.
          </Regla>
        </>
      )}
      <button className="btn primary block"
              disabled={!texto.trim() || enviando || (terminada && !nomCompleto)}
              onClick={enviar}>
        {enviando ? 'Guardando…' : 'Guardar'}
      </button>
    </Modal>
  )
}

/* ============================================================== CU-MEC-12 */
function ModalSalida({ reporteId, onCerrar }) {
  const { data, cargando, error } = useApi(
    () => api.get(`/mecanico/reportes/${reporteId}/salida`), [reporteId])
  return (
    <Modal titulo="Formato de salida" onClose={onCerrar}>
      {cargando ? <Spinner /> : error ? <Aviso tipo="err">{error}</Aviso> : (
        <>
          <p className="sub">
            {data.folio} · unidad {data.unidad} · {data.taller || 'sin taller'}
          </p>
          <div className="grid g2">
            <div className="s"><strong>Servicio:</strong> {data.tipo_servicio}</div>
            <div className="s"><strong>Kilometraje:</strong> {data.kilometraje ?? '—'}</div>
            <div className="s"><strong>Entró:</strong> {fmtFechaHora(data.fecha_entrada)}</div>
            <div className="s"><strong>Chofer:</strong> {data.chofer_nombre || '—'}</div>
          </div>
          <Tabla
            vacio="Sin sistemas"
            columnas={[
              { k: 'sistema', t: 'Sistema' },
              { k: 'a_realizar', t: 'A realizar' },
              { k: 'realizada', t: 'Realizada' },
              { k: 'terminada', t: 'Listo',
                r: (f) => (f.terminada
                  ? <Badge tono="ok">Sí</Badge> : <Badge tono="warn">No</Badge>) },
            ]}
            filas={data.mis_actividades || []} />
          {!data.todas_mis_actividades_terminadas && (
            <Aviso tipo="warn">
              Todavía tienes sistemas sin terminar en esta unidad.
            </Aviso>
          )}
          <Aviso tipo="info">{data.lo_cierra}</Aviso>
          <button className="btn block no-print" onClick={() => window.print()}>
            Imprimir
          </button>
        </>
      )}
    </Modal>
  )
}

/* ========================================================= CU-MEC-07 a 10 */
function Auxilios() {
  const { data, cargando, error, recargar } = useApi(() => api.get('/mecanico/auxilios'))
  const [rechazando, setRechazando] = useState(null)
  const [cerrando, setCerrando] = useState(null)
  const toast = useToast()

  // Se recarga TAMBIEN al fallar, y esa es la parte que importa: si otro se
  // adelantó y tomó el auxilio, el 409 llega con su explicación pero la tarjeta
  // seguiría mostrando «Voy yo». Al recargar, el botón desaparece y en su lugar
  // aparece «Lo tomó otro», que es la verdad.
  const correr = async (fn, exito) => {
    try { await fn(); toast(exito) } catch (e) { toast(e.message, 'err') } finally { recargar() }
  }

  const aceptar = (o) => correr(
    () => api.post(`/mecanico/auxilios/${o.orden_id}/responder`, undefined, { acepto: true }),
    'Auxilio aceptado. Ya se le avisó al chofer.')

  // Mismo patrón que la grúa: si el navegador no da permiso, se manda la
  // coordenada del taller central en vez de no mandar nada. Una posición
  // aproximada le sirve más al chofer que un mapa vacío.
  const mandarUbicacion = (o) => {
    const enviar = (lat, lng) => correr(
      () => api.post(`/mecanico/auxilios/${o.orden_id}/ubicacion`, undefined,
                     { latitud: lat, longitud: lng }),
      'Ubicación enviada al chofer')
    if (!navigator.geolocation) return enviar(32.5149, -117.0382)
    navigator.geolocation.getCurrentPosition(
      (p) => enviar(p.coords.latitude, p.coords.longitude),
      () => enviar(32.5149, -117.0382), { timeout: 8000 })
  }

  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="err">{error}</Aviso>
  const lista = data || []
  const mios = lista.filter((x) => x.mio)
  const libres = lista.filter((x) => !x.mio && !x.tomado_por_otro && !x.ya_respondi)

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Auxilios en carretera</h1>

      <div className="grid g3">
        <Kpi valor={libres.length} etiqueta="Por tomar" tono={libres.length ? 'alert' : ''} />
        <Kpi valor={mios.length} etiqueta="Míos" tono={mios.length ? 'warn' : ''} />
        <Kpi valor={lista.length} etiqueta="Difundidos a mí" />
      </div>

      {!lista.length ? (
        <Card><Empty icono={IcoListo}>Ninguna unidad varada esperando.</Empty></Card>
      ) : lista.map((o) => (
        <Card key={o.orden_id}
              title={`${o.folio} · unidad ${o.unidad}`}
              sub={o.tipo === 'choque' ? 'Choque' : 'Avería'}
              actions={o.mio
                ? <EstadoBadge estado={o.estado} />
                : o.tomado_por_otro
                  ? <Badge>Lo tomó otro</Badge>
                  : <Badge tono="danger">Por tomar</Badge>}>

          <p className="sub">{o.descripcion || 'Sin descripción'}</p>
          <div className="grid g2">
            <div className="s"><strong>Chofer:</strong> {o.chofer || '—'}</div>
            <div className="s"><strong>Avisado:</strong> {fmtFechaHora(o.notificado_en)}</div>
            {o.distancia_km_estimada != null && (
              <div className="s"><strong>Distancia:</strong> ~{o.distancia_km_estimada} km</div>
            )}
            {o.direccion_referencia && (
              <div className="s"><strong>Referencia:</strong> {o.direccion_referencia}</div>
            )}
          </div>

          {o.latitud != null && (
            <a className="btn sm" target="_blank" rel="noreferrer"
               href={`https://www.google.com/maps?q=${o.latitud},${o.longitud}`}>
              <IcoUbicacion size={15} strokeWidth={1.75} aria-hidden="true" /> Ver en el mapa
            </a>
          )}

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            {!o.mio && !o.tomado_por_otro && !o.ya_respondi && (
              <>
                <button className="btn primary" onClick={() => aceptar(o)}>Voy yo</button>
                <button className="btn" onClick={() => setRechazando(o)}>No puedo</button>
              </>
            )}
            {o.mio && (
              <>
                <button className="btn" onClick={() => mandarUbicacion(o)}>
                  Mandar mi ubicación
                </button>
                <button className="btn primary" onClick={() => setCerrando(o)}>
                  Cerrar auxilio
                </button>
              </>
            )}
            {o.ya_respondi && !o.mio && !o.tomado_por_otro && (
              <span className="sub">Dijiste que no podías. Sigue esperando a otro.</span>
            )}
          </div>
        </Card>
      ))}

      <Regla>
        El auxilio se manda a todos los mecánicos autónomos y lo gana el primero que
        acepta: si aprietas «Voy yo» y otro se te adelantó, el sistema te lo dice en vez
        de mandar a dos. Decir «No puedo» con motivo tampoco se pierde — es lo que deja
        al supervisor escalar a grúa cuando nadie puede ir.
      </Regla>

      {rechazando && (
        <ModalRechazo orden={rechazando} onCerrar={() => setRechazando(null)}
                      onListo={() => { setRechazando(null); recargar() }} />
      )}
      {cerrando && (
        <ModalCierre orden={cerrando} onCerrar={() => setCerrando(null)}
                     onListo={() => { setCerrando(null); recargar() }} />
      )}
    </>
  )
}

function ModalRechazo({ orden, onCerrar, onListo }) {
  const [motivo, setMotivo] = useState('')
  const toast = useToast()
  const enviar = async () => {
    try {
      await api.post(`/mecanico/auxilios/${orden.orden_id}/responder`, undefined,
                     { acepto: false, motivo })
      toast('Se registró que no puedes ir')
      onListo()
    } catch (e) { toast(e.message, 'err') }
  }
  return (
    <Modal titulo="No puedo ir" onClose={onCerrar}>
      <p className="sub">{orden.folio} · unidad {orden.unidad}</p>
      <div className="field">
        <label>¿Por qué? (lo lee el supervisor)</label>
        <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={3}
                  placeholder="Ej. estoy en otra unidad hasta la tarde" />
      </div>
      <Regla>
        El motivo importa: sin él, «nadie contestó» y «todos dijeron que no» se ven
        igual, y son problemas distintos.
      </Regla>
      <button className="btn primary block" disabled={!motivo.trim()} onClick={enviar}>
        Enviar
      </button>
    </Modal>
  )
}

function ModalCierre({ orden, onCerrar, onListo }) {
  const [resuelto, setResuelto] = useState(null)
  const [nota, setNota] = useState('')
  const toast = useToast()
  const enviar = async () => {
    try {
      await api.post(`/mecanico/auxilios/${orden.orden_id}/cerrar`, undefined,
                     { resuelto_en_sitio: resuelto, nota })
      toast(resuelto ? 'Auxilio cerrado. La unidad sigue su ruta.'
                     : 'Se avisó que hace falta grúa.')
      onListo()
    } catch (e) { toast(e.message, 'err') }
  }
  return (
    <Modal titulo="Cerrar auxilio" onClose={onCerrar}>
      <p className="sub">{orden.folio} · unidad {orden.unidad}</p>
      <label className="radio-fila">
        <input type="radio" name="res" checked={resuelto === true}
               onChange={() => setResuelto(true)} />
        <span>Quedó: la unidad ya puede seguir</span>
      </label>
      <label className="radio-fila">
        <input type="radio" name="res" checked={resuelto === false}
               onChange={() => setResuelto(false)} />
        <span>No quedó: hace falta grúa</span>
      </label>
      <div className="field">
        <label>Nota (opcional)</label>
        <textarea value={nota} onChange={(e) => setNota(e.target.value)} rows={2}
                  placeholder="Ej. era el fusible de la bomba" />
      </div>
      <Regla>
        Hay que decir cuál de las dos fue. Si quedó, el reporte se cierra aquí mismo;
        si no, se queda abierto para que alguien mande grúa. Cerrar sin decirlo dejaría
        a la unidad en el limbo.
      </Regla>
      <button className="btn primary block" disabled={resuelto === null} onClick={enviar}>
        Cerrar
      </button>
    </Modal>
  )
}

/* ========================================================== CU-MEC-03/04/05 */
function Piezas() {
  const solicitudes = useApi(() => api.get('/mecanico/piezas/solicitudes'))
  const [pidiendo, setPidiendo] = useState(false)
  const [q, setQ] = useState('')
  const [res, setRes] = useState(null)
  const [buscando, setBuscando] = useState(false)

  // Se llama a `/admin/piezas` a propósito, aunque el rol sea mecánico: es el
  // buscador que calcula el disponible REAL leyendo `Existencia` del almacén
  // central. Un buscador propio que leyera `Pieza.stock_actual` diría «no hay»
  // de las 18,233 piezas, porque ese campo no lo llena nadie.
  //
  // CON FRENO Y CON GUARDIA, igual que <BuscadorPieza>. Son 18,233 refacciones y
  // se busca mientras el mecánico escribe: sin los 300 ms se dispara una consulta
  // por letra, y sin la bandera `vivo` la respuesta de «bala» puede llegar
  // después de la de «balata» y dejar en pantalla el resultado de lo que ya no
  // está escrito. Los `*` no cuentan como letras: son comodines, igual que en el
  // servidor.
  useEffect(() => {
    if (q.trim().replace(/\*/g, '').length < 2) { setRes(null); return }
    let vivo = true
    setBuscando(true)
    const id = setTimeout(() => {
      api.get('/admin/piezas', { q, limite: 15 })
        .then((d) => vivo && setRes(d))
        .catch(() => vivo && setRes({ total: 0, resultados: [], aviso: 'No se pudo consultar el almacén.' }))
        .finally(() => vivo && setBuscando(false))
    }, 300)
    return () => { vivo = false; clearTimeout(id) }
  }, [q])

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Piezas</h1>

      <Card title="¿Hay en el almacén de Álamos?"
            sub="Búscala antes de pedirla: puede que ya esté y solo haya que traerla">
        <div className="field">
          <input value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="Nombre, SKU o el número de la caja" />
        </div>
        {buscando && <Spinner />}
        {res && !res.total && (
          <Empty icono={IcoAlmacen}>
            {res.aviso || 'No aparece en el catálogo. Pídela describiéndola con tus palabras.'}
          </Empty>
        )}
        {res && res.total > 0 && (
          <>
            <Tabla
              vacio=""
              columnas={[
                { k: 'nombre', t: 'Pieza' },
                { k: 'codigo', t: 'Código', r: (f) => f.codigo || '—' },
                { k: 'ubicacion', t: 'Dónde', r: (f) => f.ubicacion || '—' },
                { k: 'disponible', t: 'Hay', num: true,
                  r: (f) => (f.hay
                    ? <Badge tono="ok">{f.disponible}</Badge>
                    : <Badge tono="danger">No hay</Badge>) },
              ]}
              filas={res.resultados || []} />
            {res.total > res.mostrando && (
              <p className="sub">{res.total} coinciden · afina la búsqueda</p>
            )}
          </>
        )}
        <Regla>
          «Hay» es el disponible del almacén central, ya descontado lo reservado. Si dice
          que no hay, pídela abajo — y si dice que sí, avísale al administrador antes de
          pedir una compra.
        </Regla>
      </Card>

      <Card title="Mis solicitudes"
            actions={<button className="btn primary sm" onClick={() => setPidiendo(true)}>
              Pedir pieza
            </button>}>
        {solicitudes.error ? <Aviso tipo="err">{solicitudes.error}</Aviso>
          : solicitudes.cargando ? <Spinner /> : (
          <Tabla
            vacio="No has pedido ninguna pieza"
            columnas={[
              { k: 'pieza', t: 'Pieza' },
              { k: 'cantidad', t: 'Cant.', num: true },
              { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
              { k: 'fecha_solicitud', t: 'Pedida', r: (f) => fmtFecha(f.fecha_solicitud) },
              { k: 'fecha_estimada_llegada', t: 'Llega',
                r: (f) => (f.fecha_estimada_llegada
                  ? fmtFecha(f.fecha_estimada_llegada)
                  : <span className="sub">sin fecha</span>) },
              { k: 'motivo_rechazo', t: 'Nota',
                r: (f) => f.motivo_rechazo || '—' },
            ]}
            filas={solicitudes.data || []} />
        )}
      </Card>

      {pidiendo && (
        <ModalPedirPieza onCerrar={() => setPidiendo(false)}
                         onListo={() => { setPidiendo(false); solicitudes.recargar() }} />
      )}
    </>
  )
}

function ModalPedirPieza({ onCerrar, onListo }) {
  // BuscadorPieza avisa con (id, nombre, precio) sueltos, no con un objeto, y
  // manda (null, null, null) cuando el usuario aprieta «Cambiar».
  const [pieza, setPieza] = useState(null)
  const [libre, setLibre] = useState('')
  const [cantidad, setCantidad] = useState(1)
  const [justificacion, setJustificacion] = useState('')
  const toast = useToast()

  const enviar = async () => {
    try {
      await api.post('/mecanico/piezas/solicitar', undefined, {
        cantidad,
        pieza_id: pieza?.id,
        descripcion_libre: pieza ? undefined : libre,
        justificacion,
      })
      toast('Solicitud enviada al administrador')
      onListo()
    } catch (e) { toast(e.message, 'err') }
  }

  return (
    <Modal titulo="Pedir una pieza" onClose={onCerrar}>
      <div className="field">
        <label>Del catálogo</label>
        <BuscadorPieza valor={pieza?.id} nombre={pieza?.nombre}
                       onElegir={(id, nombre) => {
                         setPieza(id ? { id, nombre } : null)
                         if (id) setLibre('')
                       }} />
      </div>
      {!pieza && (
        <div className="field">
          <label>…o descríbela si no aparece</label>
          <input value={libre} onChange={(e) => setLibre(e.target.value)}
                 placeholder="Ej. manguera de radiador del Kenworth blanco" />
        </div>
      )}
      <div className="field">
        <label>Cantidad</label>
        <input type="number" min={1} value={cantidad}
               onChange={(e) => setCantidad(Math.max(1, Number(e.target.value) || 1))} />
      </div>
      <div className="field">
        <label>¿Para qué? (lo lee quien autoriza)</label>
        <textarea value={justificacion} rows={2}
                  onChange={(e) => setJustificacion(e.target.value)}
                  placeholder="Ej. la unidad BG-142 está parada por esto" />
      </div>
      <Regla>
        Se puede pedir algo que no está en el catálogo: en una planta satélite muchas
        piezas no tienen SKU, y obligarte a escoger de la lista acabaría en una llamada
        por teléfono que no deja rastro.
      </Regla>
      <button className="btn primary block" disabled={!pieza && !libre.trim()}
              onClick={enviar}>
        Enviar solicitud
      </button>
    </Modal>
  )
}

/* ============================================================== CU-MEC-11 */
function Traslados() {
  // `error` se destructura a propósito: sin él, una petición que falla se veía
  // igual que una lista vacía — «No has pedido ningún traslado» cuando en
  // realidad el servidor no contestó. Decirle a alguien que no pidió nada
  // cuando sí pidió es peor que no decirle nada.
  const { data, cargando, error, recargar } = useApi(() => api.get('/mecanico/traslados'))
  const [pidiendo, setPidiendo] = useState(false)

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Traslados a Álamos</h1>
      <Aviso tipo="info">
        Tú <strong>pides</strong> el traslado; lo autoriza el administrador. Mover una
        unidad entre plantas ocupa una grúa y un cajón en Álamos, y esa capacidad no se
        decide desde aquí.
      </Aviso>

      <Card title="Mis solicitudes"
            actions={<button className="btn primary sm" onClick={() => setPidiendo(true)}>
              Pedir traslado
            </button>}>
        {error ? <Aviso tipo="err">{error}</Aviso> : cargando ? <Spinner /> : (
          <Tabla
            vacio="No has pedido ningún traslado"
            columnas={[
              { k: 'unidad', t: 'Unidad' },
              { k: 'motivo', t: 'Motivo' },
              { k: 'requiere_grua', t: 'Grúa',
                r: (f) => (f.requiere_grua ? <Badge tono="warn">Sí</Badge> : <Badge>No</Badge>) },
              { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
              { k: 'fecha_solicitud', t: 'Pedido', r: (f) => fmtFecha(f.fecha_solicitud) },
              { k: 'autorizado_por', t: 'Autorizó', r: (f) => f.autorizado_por || '—' },
            ]}
            filas={data || []} />
        )}
      </Card>

      {pidiendo && (
        <ModalTraslado onCerrar={() => setPidiendo(false)}
                       onListo={() => { setPidiendo(false); recargar() }} />
      )}
    </>
  )
}

function ModalTraslado({ onCerrar, onListo }) {
  const [unidad, setUnidad] = useState(null)
  const [motivo, setMotivo] = useState('')
  const [grua, setGrua] = useState(true)
  const toast = useToast()

  const enviar = async () => {
    try {
      await api.post('/mecanico/traslados', undefined, {
        unidad_id: unidad.id, motivo, requiere_grua: grua,
      })
      toast('Traslado solicitado. Lo tiene que autorizar el administrador.')
      onListo()
    } catch (e) { toast(e.message, 'err') }
  }

  return (
    <Modal titulo="Pedir traslado a Álamos" onClose={onCerrar}>
      <div className="field">
        <label>Unidad</label>
        <BuscadorUnidad elegida={unidad} endpoint="/mecanico/unidades"
                        onElegir={setUnidad} />
      </div>
      <div className="field">
        <label>¿Por qué no se puede reparar aquí?</label>
        <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} rows={3}
                  placeholder="Ej. necesita prensa hidráulica y aquí no hay" />
      </div>
      <label className="radio-fila">
        <input type="checkbox" checked={grua} onChange={(e) => setGrua(e.target.checked)} />
        <span>Necesita grúa (no se puede mover sola)</span>
      </label>
      <button className="btn primary block" disabled={!unidad || !motivo.trim()}
              onClick={enviar}>
        Enviar solicitud
      </button>
    </Modal>
  )
}
