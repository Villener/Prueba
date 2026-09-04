/** CU-ADM-13 a CU-ADM-16 — la agenda de Víctor.
 *
 * La pantalla enseña las citas en el MISMO orden en que la cola las decidió,
 * no por fecha. Es a propósito: así Víctor puede ver por qué una unidad quedó
 * antes que otra, en vez de tener que confiar en el algoritmo a ciegas.
 */
import { useState } from 'react'
import { api, fmtFecha } from '../../core/api.js'
import { Aviso, Badge, Card, Empty, Modal, Spinner, Tabla, useApi, useToast } from '../../ui/index.js'
import { SelectorTaller } from './PlanoTaller.jsx'

/* Días entre la cita y el límite técnico. Es el dato que decide si la agenda
   está cumpliendo o el taller ya no da abasto, así que va a la vista siempre. */
function Holgura({ dias }) {
  if (dias === null || dias === undefined) return <span className="s">—</span>
  if (dias < 0) return <Badge tono="danger">{Math.abs(dias)} d tarde</Badge>
  if (dias <= 3) return <Badge tono="warn">{dias} d de margen</Badge>
  return <Badge tono="ok">{dias} d de margen</Badge>
}

function Confirmaciones({ cita }) {
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <Badge tono={cita.confirmada_por_taller ? 'ok' : ''}>
        {cita.confirmada_por_taller ? '✓' : '·'} Taller
      </Badge>
      <Badge tono={cita.confirmada_por_chofer ? 'ok' : ''}>
        {cita.confirmada_por_chofer ? '✓' : '·'} Chofer
      </Badge>
    </div>
  )
}

export function Agenda() {
  const toast = useToast()
  const [tallerId, setTallerId] = useState(null)
  const [mover, setMover] = useState(null)
  const [ocupado, setOcupado] = useState(false)

  const citas = useApi(() => api.get('/agenda/citas', { taller_id: tallerId }), [tallerId])
  const sinCupo = useApi(() => api.get('/agenda/sin-cupo', { taller_id: tallerId }), [tallerId])

  const recargarTodo = () => { citas.recargar(); sinCupo.recargar() }

  /** Ejecuta, avisa y recarga. Devuelve si salió bien, para que quien llame
   *  decida si cierra el modal: cerrarlo tras un error escondería el error.
   *  `alFallar` deja que quien llama trate un rechazo esperado —el sobrecupo—
   *  en vez de que solo salga un toast rojo. */
  const accion = async (fn, mensaje, alFallar) => {
    setOcupado(true)
    try {
      const r = await fn()
      toast(typeof mensaje === 'function' ? mensaje(r) : mensaje)
      recargarTodo()
      return true
    } catch (e) {
      toast(e.message, 'err')
      alFallar?.(e)
      return false
    } finally {
      setOcupado(false)
    }
  }

  const recalcular = () => accion(
    () => api.post('/agenda/recalcular', {}, { taller_id: tallerId }),
    (r) => `${r.propuestas} propuesta(s), ${r.movidas} movida(s), ${r.sin_cupo} sin cupo`)

  if (citas.cargando) return <Spinner />

  const lista = citas.data || []
  const faltan = sinCupo.data || []
  const propuestas = lista.filter((c) => c.estado === 'propuesta')
  const porConfirmar = lista.filter((c) => c.confirmada_por_taller && !c.confirmada_por_chofer)

  return (
    <>
      <div className="card-head">
        <h1>Agenda de mantenimiento</h1>
        <div className="spacer" />
        <SelectorTaller valor={tallerId} onCambio={setTallerId} />
        <button className="btn sm primary" disabled={ocupado} onClick={recalcular}>
          Recalcular
        </button>
      </div>

      <Aviso tipo="info">
        La <strong>fecha límite</strong> viene del plan y nunca se mueve; la <strong>cita</strong> la
        asigna la agenda según la capacidad real y sí se mueve. Por eso el chofer solo incumple si
        faltó a una cita confirmada: si el taller nunca pudo dársela, el problema es del taller.
      </Aviso>

      {faltan.length > 0 && (
        <Card title={`Sin cupo antes del límite (${faltan.length})`}>
          <Aviso tipo="warn">
            Esto <strong>no es incumplimiento del chofer</strong>: es capacidad del taller. Va a
            este tablero y no al de incumplimientos.
          </Aviso>
          <Tabla
            vacio="Ninguna"
            columnas={[
              { k: 'unidad', t: 'Unidad' },
              { k: 'servicio', t: 'Servicio' },
              { k: 'taller', t: 'Taller' },
              { k: 'fecha_limite', t: 'Límite', r: (x) => fmtFecha(x.fecha_limite) },
              { k: 'dias_vencido', t: 'Retraso', r: (x) => <Badge tono="danger">{x.dias_vencido} d</Badge> },
            ]}
            filas={faltan}
          />
        </Card>
      )}

      <Card title={`Propuestas por confirmar (${propuestas.length})`}>
        {propuestas.length === 0 ? (
          <Empty icono="📅">
            No hay propuestas. Usa «Recalcular» si liberaste espacios o registraste la llegada de
            unas piezas.
          </Empty>
        ) : propuestas.map((c) => (
          <div className="list-item" key={c.id}>
            <div className="grow">
              <div className="t">{c.unidad} · {c.servicio}</div>
              <div className="s">
                Cita <strong>{fmtFecha(c.fecha_cita)}</strong> · límite {fmtFecha(c.fecha_limite_origen)}
              </div>
              <div className="s">
                Ocupa entre {c.duracion_rango.tipico} y {c.duracion_rango.pesimista} día(s)
                {c.chofer ? ` · ${c.chofer}` : ''}
              </div>
              {c.veces_reprogramada > 0 && (
                <div className="s">Reprogramada {c.veces_reprogramada} vez/veces</div>
              )}
            </div>
            <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
              <Holgura dias={c.dias_de_holgura} />
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn sm" disabled={ocupado} onClick={() => setMover(c)}>Mover</button>
                <button className="btn sm primary" disabled={ocupado}
                        onClick={() => accion(() => api.post(`/agenda/citas/${c.id}/confirmar`),
                                              `Cita de ${c.unidad} confirmada`)}>
                  Confirmar
                </button>
              </div>
            </div>
          </div>
        ))}
      </Card>

      {porConfirmar.length > 0 && (
        <Card title={`Esperando confirmación del chofer (${porConfirmar.length})`}>
          <p className="sub">
            Ya las confirmaste tú. Mientras el chofer no confirme, no hay compromiso de su lado.
          </p>
          {porConfirmar.map((c) => (
            <div className="list-item" key={c.id}>
              <div className="grow">
                <div className="t">{c.unidad} · {c.servicio}</div>
                <div className="s">{fmtFecha(c.fecha_cita)} · {c.chofer || 'sin poseedor'}</div>
              </div>
              <Confirmaciones cita={c} />
            </div>
          ))}
        </Card>
      )}

      <Card title={`Toda la agenda (${lista.length})`}>
        <p className="sub">
          En el orden que decidió la cola: criticidad, luego días al límite, luego veces
          reprogramada, luego prioridad de la unidad.
        </p>
        <Tabla
          vacio="Sin citas"
          columnas={[
            { k: 'unidad', t: 'Unidad' },
            { k: 'servicio', t: 'Servicio' },
            { k: 'fecha_cita', t: 'Cita', r: (c) => fmtFecha(c.fecha_cita) },
            { k: 'fecha_limite_origen', t: 'Límite', r: (c) => fmtFecha(c.fecha_limite_origen) },
            { k: 'dias_de_holgura', t: 'Margen', r: (c) => <Holgura dias={c.dias_de_holgura} /> },
            { k: 'estado', t: 'Estado', r: (c) => <Badge>{c.estado}</Badge> },
            { k: 'conf', t: 'Confirmada', r: (c) => <Confirmaciones cita={c} /> },
            {
              k: 'movible', t: 'Se mueve sola',
              r: (c) => (c.movible
                ? <span className="s">sí</span>
                : <Badge tono="warn">no · faltan menos de 48 h</Badge>),
            },
          ]}
          filas={lista}
        />
      </Card>

      {mover && (
        <ModalMover
          cita={mover}
          ocupado={ocupado}
          onClose={() => setMover(null)}
          onGuardar={async (fecha, motivo, forzar, alFallar) => {
            const ok = await accion(
              () => api.post(`/agenda/citas/${mover.id}/reprogramar`,
                             { fecha_nueva: fecha, motivo, forzar }),
              `Cita de ${mover.unidad} movida al ${fmtFecha(fecha)}` +
                (forzar ? ' (con sobrecupo)' : ''),
              alFallar)
            if (ok) setMover(null)
          }}
          onCancelar={async () => {
            const ok = await accion(
              () => api.post(`/agenda/citas/${mover.id}/cancelar`),
              'Cita cancelada. El programa vuelve a la cola.')
            if (ok) setMover(null)
          }}
        />
      )}
    </>
  )
}

/* Calendario de cupo. Cada casilla es un día y dice cuántos espacios quedan
   para ESE tipo de unidad — la capacidad nunca es global: el taller puede
   estar lleno de pipas y tener libres los de reparto. */
function Calendario({ tallerId, tipoUnidadId, seleccion, onElegir }) {
  // Sin taller o sin tipo no hay capacidad que consultar: la del taller es
  // siempre POR TIPO. Se corta antes de pedir para no mandar un 422 al
  // servidor y dejar la caja vacía sin explicación.
  const falta = !tallerId || !tipoUnidadId
  const { data, cargando } = useApi(
    () => (falta ? Promise.resolve(null)
                 : api.get('/agenda/capacidad', {
                     taller_id: tallerId, tipo_unidad_id: tipoUnidadId, dias: 30,
                   })),
    [tallerId, tipoUnidadId])

  if (falta) {
    return (
      <Aviso tipo="warn">
        Esta cita no tiene taller o tipo de unidad, así que no se puede calcular el cupo.
        Escribe la fecha a mano.
      </Aviso>
    )
  }
  if (cargando) return <Spinner />
  if (!data) return null

  return (
    <>
      <div className="cal">
        {data.dias.map((d) => {
          const cerrado = !d.opera
          const lleno = d.opera && d.libres === 0
          const clases = ['cal-dia', cerrado ? 'cerrado' : lleno ? 'lleno' : 'hay',
                          d.fecha === seleccion ? 'elegido' : ''].join(' ')
          return (
            <button type="button" key={d.fecha} className={clases} disabled={cerrado}
                    onClick={() => onElegir(d.fecha)}
                    title={cerrado ? 'El taller no opera'
                                   : `${d.libres} espacio(s) de ${data.tipo_unidad}`}>
              <span className="cal-n">{Number(d.fecha.slice(8, 10))}</span>
              <small>{cerrado ? '—' : d.libres}</small>
            </button>
          )
        })}
      </div>
      <p className="hint" style={{ marginTop: 8 }}>
        El número es cuántos espacios de <strong>{data.tipo_unidad}</strong> quedan ese día en
        {' '}{data.taller}. Rayado = el taller no opera.
      </p>
    </>
  )
}

/* --------------------------------------------------------------- CU-ADM-15 -- */
function ModalMover({ cita, ocupado, onClose, onGuardar, onCancelar }) {
  const [fecha, setFecha] = useState(cita.fecha_cita)
  const [motivo, setMotivo] = useState('solicitud_chofer')
  // Días que el servidor rechazó por falta de espacio. Se guardan para que el
  // sobrecupo sea una segunda decisión consciente y no un botón que ya estaba
  // ahí: primero se entera de que no cabe, luego decide si lo mete igual.
  const [sinCupo, setSinCupo] = useState(null)

  const guardar = (forzar) => {
    setSinCupo(null)
    onGuardar(fecha, motivo, forzar, (err) => {
      // El servidor rechazó por falta de espacio pero dijo que se puede
      // forzar. No se fuerza solo: se le enseña y él decide.
      if (err.datos?.puede_forzar) setSinCupo(err.datos)
    })
  }

  return (
    <Modal titulo={`Mover la cita de ${cita.unidad}`} onClose={onClose}>
      <p className="sub">
        Límite técnico: <strong>{fmtFecha(cita.fecha_limite_origen)}</strong>. Ese no se mueve —
        solo la cita. Ocupa {cita.duracion_estimada_dias || 1} día(s).
      </p>

      {!cita.movible && (
        <Aviso tipo="warn">
          Faltan menos de 48 h. El recálculo automático ya no la toca, pero tú sí puedes moverla:
          queda registrado que requirió tu autorización.
        </Aviso>
      )}

      <div className="field">
        <label>Elige el día</label>
        <Calendario tallerId={cita.taller_id} tipoUnidadId={cita.tipo_unidad_id}
                    seleccion={fecha} onElegir={setFecha} />
      </div>

      <div className="field">
        <label htmlFor="f">Fecha nueva</label>
        <input id="f" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
      </div>

      <div className="field">
        <label htmlFor="mot">Motivo</label>
        <select id="mot" value={motivo} onChange={(e) => setMotivo(e.target.value)}>
          <option value="sin_espacio">No hay espacio</option>
          <option value="unidad_atorada">La unidad anterior sigue adentro</option>
          <option value="urgencia_desplaza">Una urgencia la desplazó</option>
          <option value="solicitud_chofer">Lo pidió el chofer</option>
        </select>
      </div>

      {sinCupo ? (
        <Aviso tipo="err">
          <strong>No hay espacio</strong> el {sinCupo.dias_sin_cupo.map(fmtFecha).join(', ')}.
          Puedes meterla de todas formas, pero el taller queda sobrecupo ese día y quedará
          registrado que lo autorizaste.
        </Aviso>
      ) : (
        <Aviso tipo="info">
          Al moverla, el chofer tiene que <strong>volver a confirmar</strong>: no se le da por
          aceptada una fecha que no aceptó.
        </Aviso>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
        {sinCupo ? (
          <button className="btn danger" disabled={ocupado} onClick={() => guardar(true)}>
            Meterla de todas formas
          </button>
        ) : (
          <button className="btn primary" disabled={ocupado} onClick={() => guardar(false)}>
            Mover la cita
          </button>
        )}
        <button className="btn" disabled={ocupado} onClick={onClose}>Cerrar</button>
        <span style={{ flex: 1 }} />
        <button className="btn danger" disabled={ocupado} onClick={onCancelar}>Cancelar cita</button>
      </div>
    </Modal>
  )
}
