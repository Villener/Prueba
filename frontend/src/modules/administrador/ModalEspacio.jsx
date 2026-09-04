/** CU-ADM-04 - menu que se despliega al tocar una casilla del plano:
sacar el vehiculo, moverlo, o meter uno que espera lugar.

v1.3: al tocar una casilla OCUPADA lo primero que sale es el formato de
mantenimiento de esa unidad y quien la esta atendiendo. Es la puerta natural:
el administrador esta parado frente al vehiculo, no buscando un folio. */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, fmtFechaHora } from '../../core/api.js'
import { Aviso, Badge, Empty, Modal, Regla, Spinner, useApi, useToast } from '../../ui/index.js'

export function ModalEspacio({ espacioId, onCerrar, onCambio }) {
  const toast = useToast()
  const navegar = useNavigate()
  const { data, cargando, recargar } = useApi(
    () => api.get(`/admin/espacios/${espacioId}`), [espacioId])
  const [moviendo, setMoviendo] = useState(false)

  const accion = async (fn, ok) => {
    try { await fn(); toast(ok); onCambio(); onCerrar() }
    catch (e) { toast(e.message, 'err') }
  }

  if (cargando) return <Modal titulo="Espacio" onClose={onCerrar}><Spinner /></Modal>
  const d = data || {}
  const ocupado = !!d.ocupado_por
  const rep = d.reporte

  return (
    <Modal titulo={`${d.zona || 'Espacio'} · ${d.numero}`} onClose={onCerrar}>
      {d.es_sala_espera && (
        <Aviso tipo="info">
          <strong>Sala de espera.</strong> Aquí la unidad aguarda turno: no cuenta como
          capacidad de atención del taller, así que estacionarla no infla el indicador de
          ocupación. Cuando se libere una bahía, muévela con «Mover a otro espacio».
        </Aviso>
      )}

      {ocupado ? (
        <>
          <div className="list-item">
            <div className="grow">
              <div className="t">{d.ocupado_por.num_economico}</div>
              <div className="s">
                {[d.ocupado_por.marca, d.ocupado_por.modelo].filter(Boolean).join(' ') || '—'}
              </div>
              <div className="s">Desde {fmtFechaHora(d.ocupado_por.desde)}</div>
              {/* Quién la metió aquí: cada administrador atiende sus vehículos
                  y esto dice a quién preguntarle por este. */}
              {d.ocupado_por.colocado_por && (
                <div className="s">La colocó {d.ocupado_por.colocado_por}</div>
              )}
            </div>
            <Badge tono="info">ocupado</Badge>
          </div>

          {/* El formato, al frente. Es lo que Pedro viene a verificar. */}
          {rep ? (
            <div className="card" style={{ background: 'var(--surface-2)', marginBottom: 12 }}>
              <div className="card-head">
                <h3>{rep.folio}</h3>
                <Badge tono={rep.estado === 'abierto' ? 'warn' : 'ok'}>{rep.estado}</Badge>
              </div>
              <p className="sub">
                {rep.tipo_servicio}
                {rep.chofer_nombre ? ` · ${rep.chofer_nombre}` : ''}
              </p>

              <div className="field" style={{ marginBottom: 8 }}>
                <label>Quién la está atendiendo</label>
                {rep.atendido_por.length === 0 ? (
                  <p className="sub" style={{ margin: 0 }}>
                    Nadie asignado todavía. Se asigna al capturar las actividades del formato.
                  </p>
                ) : (
                  <div className="btn-row">
                    {rep.atendido_por.map((t) => (
                      <Badge key={t.tecnico_id} tono={t.pendientes ? 'info' : 'ok'}>
                        🔧 {t.tecnico} · {t.especialidad}
                        {t.pendientes ? ` · ${t.pendientes} pend.` : ' · entregado'}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {rep.estado === 'abierto' && rep.firmas_faltantes.length > 0 && (
                <p className="hint">
                  Faltan {rep.firmas_faltantes.length} firma(s) para poder cerrarlo.
                </p>
              )}

              <button className="btn primary block" style={{ marginTop: 8 }}
                      onClick={() => { onCerrar(); navegar(`/reportes/${rep.id}`) }}>
                Abrir el formato de mantenimiento
              </button>
            </div>
          ) : (
            <Aviso tipo="warn">
              Esta unidad está adentro pero <strong>no tiene formato abierto</strong>. Desde
              v1.3 el formato se levanta solo al aceptar el ingreso; si falta, es una unidad
              que entró por otro camino. Levántalo desde <em>Reportes → Levantar a mano</em>.
            </Aviso>
          )}

          <button className="btn danger block"
                  onClick={() => accion(
                    () => api.post(`/admin/espacios/${espacioId}/retirar`),
                    `Unidad ${d.ocupado_por.num_economico} retirada`)}>
            Sacar el vehículo de este espacio
          </button>

          <div style={{ height: 8 }} />
          <button className="btn block" onClick={() => setMoviendo((v) => !v)}>
            {moviendo ? 'Cancelar' : 'Mover a otro espacio'}
          </button>
          {moviendo && (
            <Destinos taller_id={d.taller_id} espacioActual={espacioId}
                      ordenId={d.ocupado_por.orden_id}
                      unidad={d.ocupado_por.num_economico}
                      onMover={(destino) => accion(
                        () => api.post(
                          `/admin/espacios/${destino.id}/mover/${d.ocupado_por.orden_id}`),
                        `${d.ocupado_por.num_economico} movida a ${destino.etiqueta}`)} />
          )}
        </>
      ) : (
        <>
          <p className="sub">Espacio libre. Elige qué vehículo entra aquí.</p>
          {d.candidatas?.length ? (
            d.candidatas.map((c) => (
              <div className="list-item" key={c.orden_id}>
                <div className="grow">
                  <div className="t">{c.num_economico}</div>
                  <div className="s">
                    Orden {c.folio}
                    {[c.marca, c.modelo].filter(Boolean).length
                      ? ` · ${[c.marca, c.modelo].filter(Boolean).join(' ')}` : ''}
                  </div>
                </div>
                <button className="btn primary sm"
                        onClick={() => accion(
                          () => api.post(`/admin/espacios/${espacioId}/colocar/${c.orden_id}`),
                          `Unidad ${c.num_economico} colocada`)}>
                  Meter aquí
                </button>
              </div>
            ))
          ) : (
            <Empty icono="🅿️">
              No hay unidades esperando lugar en este taller. Solo aparecen las que ya tienen
              una orden abierta y no están en otro cajón.
            </Empty>
          )}
        </>
      )}

      <Regla>
        Una unidad no puede estar en dos espacios a la vez, ni un espacio tener dos unidades:
        lo impide un índice único en la base, no solo esta pantalla. Y el sistema guarda qué
        administrador colocó cada vehículo en cada casilla.
      </Regla>
      <button className="btn sm" onClick={recargar} style={{ marginTop: 8 }}>Actualizar</button>
    </Modal>
  )
}

/**
 * A dónde se puede mover la unidad, sin salir del menú.
 *
 * Antes «Mover a otro espacio» solo mostraba un aviso que decía «cierra esto y
 * toca el cajón destino»: había que acordarse de cuál estaba libre, cerrar,
 * buscarlo en el plano y volver a abrir otro menú. Aquí salen los libres que
 * ADEMÁS admiten el tipo de unidad, agrupados por zona, y la sala de espera
 * marcada como tal — que es a donde va la unidad cuando no hay bahía.
 */
function Destinos({ taller_id, espacioActual, ordenId, unidad, onMover }) {
  const { data, cargando } = useApi(
    () => (taller_id ? api.get(`/admin/taller/${taller_id}`) : Promise.resolve(null)),
    [taller_id])

  if (!ordenId) {
    return (
      <Aviso tipo="warn">
        Esta unidad no tiene orden de servicio abierta, así que no se puede mover entre
        cajones: sácala del espacio y vuelve a darle ingreso.
      </Aviso>
    )
  }
  if (cargando) return <Spinner />

  const zonas = (data?.zonas || [])
    .map((z) => ({
      ...z,
      libres: z.espacios.filter((e) => e.estado === 'libre' && e.id !== espacioActual),
    }))
    .filter((z) => z.libres.length > 0)

  if (!zonas.length) {
    return <Aviso tipo="warn">No hay ningún cajón libre en este taller.</Aviso>
  }

  return (
    <div className="destinos">
      <p className="hint">
        Mover <strong>{unidad}</strong> a:
      </p>
      {zonas.map((z) => (
        <div className="destino-zona" key={z.id}>
          <div className="destino-head">
            <span>{z.nombre}</span>
            {!z.cuenta_para_ocupacion && <Badge>sala de espera</Badge>}
          </div>
          <div className="destino-casillas">
            {z.libres.map((e) => (
              <button key={e.id} type="button" className="btn sm"
                      title={`Admite ${e.tipo_permitido || 'cualquier tipo'}`}
                      onClick={() => onMover({ id: e.id, etiqueta: `${z.nombre} ${e.numero}` })}>
                {e.numero}
              </button>
            ))}
          </div>
        </div>
      ))}
      <p className="hint">
        Si el cajón no admite el tipo de unidad, el servidor lo rechaza (RI-04): la lista no
        adivina, el candado está en el servidor.
      </p>
    </div>
  )
}
