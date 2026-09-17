/** Modulo Gerente - CU-GER-* de docs/casos-de-uso.md */
import { useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { api, fmtFecha, fmtFechaHora, fmtMoneda } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoCampana, IcoListo, Kpi, Modal, Regla, Spinner,
  Tabla, useApi, useToast,
} from '../../ui/index.js'

export default function Gerente() {
  return (
    <Routes>
      <Route path="/" element={<Tablero />} />
      <Route path="/incumplimiento" element={<Incumplimiento />} />
      <Route path="/taller" element={<TallerVista />} />
      <Route path="/presupuestos" element={<Presupuestos />} />
      <Route path="/alertas" element={<Alertas />} />
      <Route path="/estadisticas" element={<Estadisticas />} />
    </Routes>
  )
}

/* ---------------------------------------------------------- CU-GER-01 ------ */
function Tablero() {
  const toast = useToast()
  const kpis = useApi(() => api.get('/gerente/kpis'))
  const atendidas = useApi(() => api.get('/gerente/atendidas', { dias: 30 }))
  const piezas = useApi(() => api.get('/gerente/piezas-en-camino'))

  const correrJobs = async () => {
    try {
      const r = await api.post('/jobs/correr')
      toast(`Avisos: ${r.penalizaciones_generadas} · Alertas: ${r.alertas_nuevas} · ` +
            `Préstamos cerrados: ${r.prestamos_cerrados}`)
      kpis.recargar()
    } catch (e) { toast(e.message, 'err') }
  }

  if (kpis.cargando) return <Spinner />
  const k = kpis.data

  return (
    <>
      <div className="card-head">
        <h1>Tablero</h1>
        <button className="btn sm" onClick={correrJobs} title="Dispara CU-AUT-01..03">
          ▶ Correr procesos del día
        </button>
      </div>

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
  )
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
  if (ocupacion.cargando) return <Spinner />
  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Taller</h1>

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

/** Columnas sobre el tiempo. Los periodos vacíos SÍ se dibujan: un mes sin un
 *  solo preventivo es información, y omitirlo lo escondería juntando los que sí
 *  tuvieron. */
function ColumnasTiempo({ etiquetas, datos, color, gran }) {
  const tope = Math.max(...datos, 1)
  const corto = (e) => gran === 'dia' ? e.slice(8) : (gran === 'mes' ? e.slice(5) : e)
  return (
    <div className="gcolumnas" style={{ height: 150 }}>
      {etiquetas.map((e, i) => (
        <div className="gcol" key={e} title={e + ': ' + datos[i]}>
          <span className="gcifra">{datos[i]}</span>
          <div className="gtorre"
               style={{ height: (datos[i] / tope) * 100 + '%', background: color }} />
          <span className="gpie">{corto(e)}</span>
        </div>
      ))}
    </div>
  )
}

function Estadisticas() {
  const [gran, setGran] = useState('mes')
  const cuantos = gran === 'dia' ? 30 : (gran === 'mes' ? 12 : 5)
  const serie = useApi(() => api.get('/gerente/estadisticas',
                                     { granularidad: gran, cuantos }), [gran])
  const cump = useApi(() => api.get('/gerente/cumplimiento-choferes',
                                    { granularidad: gran, cuantos: gran === 'dia' ? 30 : 6 }),
                      [gran])
  const [verChofer, setVerChofer] = useState(null)

  const d = serie.data || {}
  const etiquetas = d.etiquetas || []
  const nombrePeriodo = gran === 'dia' ? 'días' : gran === 'mes' ? 'meses' : 'años'

  return (
    <>
      <div className="card-head">
        <h1>Estadísticas</h1>
        <div className="spacer" />
        <div className="segmentado">
          {[['dia', 'Día'], ['mes', 'Mes'], ['anio', 'Año']].map(([v, t]) => (
            <button key={v} className={'btn sm' + (gran === v ? ' primario' : '')}
                    onClick={() => setGran(v)}>{t}</button>
          ))}
        </div>
      </div>

      {serie.cargando ? <Spinner /> : serie.error ? (
        <Aviso tipo="err">{serie.error}</Aviso>
      ) : (
        <div className="grid g2">
          {(d.series || []).map((sr) => (
            <Card key={sr.clave} title={sr.nombre}
                  sub={'Últimos ' + etiquetas.length + ' ' + nombrePeriodo}>
              <ColumnasTiempo etiquetas={etiquetas} datos={sr.datos}
                              color={SERIES_COLOR[sr.clave]} gran={gran} />
            </Card>
          ))}
        </div>
      )}

      <Card title="Cumplimiento por chofer"
            sub={cump.data ? 'Del ' + cump.data.desde + ' al ' + cump.data.hasta : '…'}>
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
