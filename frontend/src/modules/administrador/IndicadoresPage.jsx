/** CU-ADM-15c — los indicadores del taller.
 *
 * Sustituye la hoja «Graficos» del Excel del área, que hoy tiene dos problemas:
 * sus cuatro números se copian a mano desde la hoja RESUMEN —y por eso no
 * cuadran con ella en cuatro de los siete meses— y su gráfica de servicios está
 * armada con doce series de un punto cada una, así que la leyenda sale con doce
 * entradas.
 *
 * Aquí todo sale de la misma función que arma el Excel: si los dos números
 * discrepan alguna vez, es un error de programación, no de captura.
 */
import { api } from '../../core/api.js'
import { Aviso, Card, Kpi, Regla, Spinner, useApi } from '../../ui/index.js'
import { SelectorTaller } from './PlanoTaller.jsx'
import { useState } from 'react'

/** Barras horizontales. Se usan cuando la etiqueta es una palabra larga
 *  —«Pendientes por Compras»— porque en vertical no cabe sin girarla, y el
 *  texto girado no se lee. */
function Barras({ datos, total }) {
  const tope = Math.max(...datos.map((d) => d.cuantas), 1)
  return (
    <div className="grafica">
      {datos.map((d) => {
        const parte = total ? Math.round((d.cuantas / total) * 100) : 0
        return (
          <div key={d.etiqueta} className={`gbarra${d.alerta && d.cuantas ? ' alerta' : ''}`}
               title={`${d.etiqueta}: ${d.cuantas}${total ? ` · ${parte}% del patio` : ''}`}>
            <span className="get">{d.etiqueta}</span>
            <div className="gpista">
              <div className="gval" style={{ width: `${(d.cuantas / tope) * 100}%` }} />
            </div>
            {/* El número va SIEMPRE al lado de su barra: sirve de etiqueta
                directa y de tabla al mismo tiempo, así que la identidad nunca
                depende solo del color. */}
            <span className="gnum">{d.cuantas}</span>
          </div>
        )
      })}
    </div>
  )
}

/** Columnas para la serie mensual: el tiempo se lee de izquierda a derecha. */
function Columnas({ datos }) {
  const tope = Math.max(...datos.map((d) => d.cuantas), 1)
  return (
    <div className="gcolumnas">
      {datos.map((d) => {
        const [anio, mes] = d.etiqueta.split('-')
        return (
          <div className="gcol" key={d.etiqueta} title={`${d.etiqueta}: ${d.cuantas} entradas`}>
            <span className="gcifra">{d.cuantas}</span>
            <div className="gtorre" style={{ height: `${(d.cuantas / tope) * 100}%` }} />
            <span className="gpie">{mes}/{anio.slice(2)}</span>
          </div>
        )
      })}
    </div>
  )
}

/** RN-12 — la meta de 5 a 7 preventivos por día.
 *
 *  Es techo Y PISO, y el piso es lo que la hace distinta de una restricción de
 *  capacidad: un día con 3 no está «dentro de capacidad», está por debajo de la
 *  meta y el que incumplió es el taller. De eso depende si un chofer que faltó
 *  es responsable o no.
 *
 *  Cuando no hay programas de mantenimiento cargados NO se pinta «0 de 5»: eso
 *  culparía al taller de un hueco de datos. Se dice lo que falta.
 */
function MetaPreventivo() {
  const hoy = useApi(() => api.get('/admin/meta-preventivo'))
  const serie = useApi(() => api.get('/admin/meta-preventivo/serie', { dias: 30 }))

  if (hoy.cargando) return <Spinner />
  if (hoy.error) return <Aviso tipo="err">{hoy.error}</Aviso>
  const d = hoy.data || {}
  const s = serie.data || {}
  const dem = d.demanda || {}
  const cob = d.cobertura || {}

  if (d.estado === 'sin_datos') {
    return (
      <Card title="Meta de mantenimiento preventivo"
            sub={`El objetivo acordado es de ${d.meta_min} a ${d.meta_max} unidades por día`}>
        <Aviso tipo="warn">
          Todavía no se puede medir: solo <strong>{cob.programas}</strong> de
          las <strong>{cob.unidades_con_plan}</strong> unidades con plan tienen programa de
          mantenimiento cargado ({cob.porcentaje}%).
        </Aviso>
        <Regla>
          La flota pide <strong>{dem.al_dia} preventivos al día</strong> según los planes
          activos, pero no hay programas contra los cuales contarlos. Con esta cobertura el
          tablero diría <em>0 de {d.meta_min}</em> todos los días, y eso no mediría al taller:
          mediría un hueco de captura y lo pintaría de rojo como si fuera culpa suya. El número
          empieza a querer decir algo a partir del 10% de la flota cargada.
        </Regla>
      </Card>
    )
  }

  const tono = d.estado === 'bajo' ? 'alert' : (d.estado === 'sobre' ? 'warn' : '')
  const tope = Math.max(...(s.puntos || [{ cumplidos: 0 }]).map((p) => p.cumplidos),
                        d.meta_max || 7, 1)

  return (
    <Card title="Meta de mantenimiento preventivo"
          sub={`Objetivo de ${d.meta_min} a ${d.meta_max} unidades por día · RN-12`}>
      <div className="grid g4">
        <Kpi valor={d.cumplidos} etiqueta="Preventivos de hoy" tono={tono}
             hint={d.estado === 'bajo'
               ? `Faltan ${d.faltan_para_el_piso} para el piso`
               : (d.estado === 'sobre' ? 'Por encima del techo' : 'Dentro de la meta')} />
        <Kpi valor={d.agendados_pendientes} etiqueta="Citas de hoy sin cerrar" />
        <Kpi valor={s.promedio ?? '—'} etiqueta="Promedio de 30 días"
             tono={s.promedio != null && s.promedio < d.meta_min ? 'alert' : ''} />
        <Kpi valor={s.dias_bajo_piso ?? '—'} etiqueta="Días bajo el piso"
             tono={s.dias_bajo_piso ? 'alert' : ''}
             hint={s.dias_evaluados ? `de ${s.dias_evaluados} días evaluados` : ''} />
      </div>

      {(s.puntos || []).length > 0 && (
        <div className="gcolumnas meta" style={{ marginTop: 14 }}>
          {s.puntos.map((p) => (
            <div className={`gcol${p.bajo_piso ? ' bajo' : ''}${p.es_hoy ? ' hoy' : ''}`}
                 key={p.fecha}
                 title={`${p.fecha}: ${p.cumplidos} preventivos`
                        + (p.bajo_piso ? ` · por debajo del piso de ${s.meta_min}` : '')
                        + (p.es_hoy ? ' · hoy, el día no ha terminado' : '')}>
              <span className="gcifra">{p.cumplidos}</span>
              <div className="gtorre" style={{ height: `${(p.cumplidos / tope) * 100}%` }} />
              <span className="gpie">{p.fecha.slice(8)}</span>
            </div>
          ))}
        </div>
      )}

      <Regla>
        La flota pide <strong>{dem.al_dia} preventivos al día</strong> según los planes activos
        ({(dem.detalle || []).map((x) => `${x.unidades} ${x.plan.toLowerCase().replace('servicio preventivo ', '')} cada ${x.cada_dias} d`).join(' · ')}).
        Con la meta en {d.meta_min}–{d.meta_max}, el margen es el que es: si el taller se queda
        en el piso, la demanda se acumula. El día de hoy no cuenta como incumplido —todavía no
        termina—, por eso va marcado aparte.
      </Regla>
    </Card>
  )
}

export function Indicadores() {
  const [tallerId, setTallerId] = useState(null)
  const { data, cargando, error } = useApi(
    () => api.get('/admin/indicadores', tallerId ? { taller_id: tallerId } : undefined),
    [tallerId])

  if (cargando) return <Spinner />
  if (error) return <Aviso tipo="err">{error}</Aviso>
  const d = data || {}
  const patio = d.en_patio || 0

  return (
    <>
      <div className="card-head">
        <h1>Indicadores del taller</h1>
        <div className="spacer" />
        <SelectorTaller valor={tallerId} onCambio={setTallerId} />
      </div>

      <MetaPreventivo />

      <div className="grid g4">
        <Kpi valor={patio} etiqueta="Unidades en el patio" />
        <Kpi valor={d.dias_promedio ?? '—'} etiqueta="Días promedio adentro"
             tono={d.dias_promedio > 90 ? 'warn' : ''} />
        <Kpi valor={d.mas_vieja ? `${d.mas_vieja.dias} d` : '—'}
             etiqueta="La que lleva más tiempo"
             tono={d.mas_vieja && d.mas_vieja.dias > 366 ? 'alert' : ''}
             hint={d.mas_vieja ? `Unidad ${d.mas_vieja.unidad}, desde ${d.mas_vieja.desde}` : ''} />
        <Kpi valor={d.movimientos_totales ?? '—'} etiqueta="Entradas registradas"
             hint="Historial completo desde diciembre de 2021" />
      </div>

      <Card title="Por estado" sub={`Las ${patio} unidades que están adentro hoy`}>
        <Barras datos={d.por_estado || []} total={patio} />
        <Regla>
          Es el mismo corte que el área teclea a diario en la hoja RESUMEN. Aquí se cuenta
          solo, así que no puede descuadrar contra el patio.
        </Regla>
      </Card>

      <Card title="Por antigüedad en el patio"
            sub="Cuánto llevan esperando las unidades que están adentro">
        <Barras datos={d.por_antiguedad || []} total={patio} />
        <Regla>
          La cubeta de <strong>más de 366 días</strong> no existe en el archivo del área: ellos
          cortan ahí y lo más viejo se pierde entre las de un año. Separarla es lo que deja ver
          las unidades olvidadas.
        </Regla>
      </Card>

      <Card title="Entradas por mes" sub="Últimos 12 meses con movimiento">
        <Columnas datos={d.entradas_por_mes || []} />
        <Regla>
          Son entradas, no inventario. La serie diaria del patio no se puede reconstruir hacia
          atrás porque el 98% del historial no trae fecha de salida; para tenerla hay que
          empezar a guardar una foto diaria de hoy en adelante.
        </Regla>
      </Card>

      <div className="grid g2">
        <Card title="Por área" sub="A qué operación sirve cada unidad detenida">
          <Barras datos={d.por_area || []} total={patio} />
        </Card>
        <Card title="Las que más vuelven" sub="Entradas acumuladas desde 2021">
          <Barras datos={d.reincidentes || []} />
          <Regla>
            Esta pregunta el Excel no la puede contestar: exige contar a mano sobre 1,869
            renglones. Una unidad que vuelve quince veces cuesta más de lo que parece cada vez.
          </Regla>
        </Card>
      </div>
    </>
  )
}
