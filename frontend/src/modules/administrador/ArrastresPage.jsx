/** CU-ADM-31 — el despacho de auxilio en carretera.
 *
 * Esta pantalla no existía. Antes, quien decidía qué apoyo salía era el
 * supervisor, y solo tenía dos opciones: mandar mecánico o escalar a grúa. En
 * la operación real son cuatro, y la que faltaba es la más frecuente: la
 * llamada en la que el chofer mueve algo él mismo y sigue su ruta.
 *
 * Dos decisiones de diseño que vale la pena dejar escritas:
 *
 * 1. LA LISTA DE APOYO NO ESCONDE A LOS OCUPADOS. Enseñar solo a los libres
 *    obliga a preguntar por radio quién falta. Salen todos, con el motivo por
 *    el que no pueden, y el botón deshabilitado.
 *
 * 2. LA DISPONIBILIDAD NO SE TECLEA. Sale de hechos ya registrados: un arrastre
 *    abierto ocupa a su chofer, y una grúa dentro del patio no puede salir. Una
 *    casilla de «estoy disponible» siempre acaba mintiendo — la columna
 *    Tecnico.disponible está en true para los 42 técnicos porque nadie la ha
 *    tocado nunca.
 */
import { useState } from 'react'
import { api, fmtFecha, fmtFechaHora } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoArrastres, IcoListo, IcoTecnico,
  IcoUbicacion, Modal, Regla, Spinner, Tabla, TiraFotos, useApi, useToast,
} from '../../ui/index.js'

/* Las cuatro salidas, en el orden en que conviene pensarlas: de la más barata
   a la más cara. Ponerlas al revés empuja a mandar grúa por costumbre. */
const SALIDAS = [
  { tipo: 'telefono', txt: 'Se resolvió por teléfono',
    ayuda: 'No sale nadie. El chofer lo movió él mismo y la unidad sigue su ruta.' },
  { tipo: 'llantero', txt: 'Mandar llantero',
    ayuda: 'Problema de llanta. Requiere elegir a quién va.' },
  { tipo: 'mecanico', txt: 'Mandar mecánico',
    ayuda: 'Falla mecánica que se puede atender en sitio.' },
  { tipo: 'grua', txt: 'Mandar grúa',
    ayuda: 'La unidad no camina. Genera el arrastre y su folio.' },
]

/* ------------------------------------------------------------------------- */

export function Arrastres() {
  const [ver, setVer] = useState('abiertas')
  return (
    <>
      <div className="card-head">
        <h1>Auxilio en carretera</h1>
        <div className="spacer" />
        <button className={`btn${ver === 'abiertas' ? ' primary' : ''}`}
                onClick={() => setVer('abiertas')}>Por atender</button>
        <button className={`btn${ver === 'registro' ? ' primary' : ''}`}
                onClick={() => setVer('registro')}>Registro de arrastres</button>
      </div>
      {ver === 'abiertas' ? <PorAtender /> : <RegistroArrastres />}
    </>
  )
}

/* ------------------------------------------------------- unidades varadas -- */

function PorAtender() {
  const { data, cargando, recargar } = useApi(() => api.get('/admin/averias'))
  const [despachar, setDespachar] = useState(null)

  if (cargando) return <Spinner />
  const averias = data || []
  const sinDespachar = averias.filter((a) => !a.desenlace)

  return (
    <>
      <Aviso tipo="info">
        Aquí decides tú qué apoyo sale, sin esperar la validación del supervisor. Él recibe el
        aviso al mismo tiempo para enterarse de que su chofer está parado, pero no bloquea.
      </Aviso>

      {averias.length === 0 ? (
        <Empty icono={IcoListo}>
          Ninguna unidad varada. Cuando un chofer reporte una avería aparece aquí.
        </Empty>
      ) : (
        averias.map((a) => (
          <Card key={a.id} title={`${a.folio} · Unidad ${a.unidad}`}
                actions={a.desenlace
                  ? <Badge>{a.desenlace_texto}</Badge>
                  : <EstadoBadge estado={a.estado} />}>
            <p className="sub">{a.chofer} · {fmtFechaHora(a.fecha_hora)}</p>
            <p>{a.descripcion_falla || 'Sin descripción'}</p>

            {a.latitud ? (
              <p className="sub">
                <IcoUbicacion size={13} className="ico-inline" aria-hidden="true" />{' '}
                {a.latitud.toFixed(5)}, {a.longitud.toFixed(5)}{' '}
                <a href={`https://www.google.com/maps?q=${a.latitud},${a.longitud}`}
                   target="_blank" rel="noreferrer">ver en el mapa</a>
              </p>
            ) : (
              /* Sin coordenadas no se puede ordenar el apoyo por cercanía, y hay
                 que decirlo: si no, la lista sale en un orden que parece
                 arbitrario y nadie entiende por qué. */
              <Aviso tipo="warn">
                Llegó sin ubicación. El apoyo no se puede ordenar por cercanía: háblale al
                chofer para saber dónde quedó.
              </Aviso>
            )}

            {/* Las fotos van ARRIBA de los avisos y del botón: son lo que
                decide qué apoyo mandar, y bajarlas a un pie de tarjeta haría
                que se despachara sin verlas. */}
            <TiraFotos fotos={a.fotos} />

            {a.en_vialidad_publica && !a.tiene_peritaje && (
              <Aviso tipo="warn">
                <strong>Vialidad pública sin folio de peritos.</strong> La grúa está bloqueada
                hasta que se registre (RN-04). No es trámite interno: sin peritaje la
                aseguradora puede no cubrir el siniestro. Las otras tres salidas sí están
                disponibles.
              </Aviso>
            )}

            {a.desenlace ? (
              <Regla>
                {a.desenlace_texto} · lo decidió {a.despachado_por || '—'}
                {a.fecha_despacho ? ` el ${fmtFechaHora(a.fecha_despacho)}` : ''}
                {a.nota_despacho ? ` · «${a.nota_despacho}»` : ''}
              </Regla>
            ) : (
              <div className="btn-row">
                <button className="btn primary" onClick={() => setDespachar(a)}>
                  Asignar apoyo
                </button>
              </div>
            )}
          </Card>
        ))
      )}

      {averias.length > 0 && sinDespachar.length === 0 && (
        <Regla>Todas las averías abiertas ya tienen apoyo asignado.</Regla>
      )}

      {despachar && (
        <ModalDespacho averia={despachar} onCerrar={() => setDespachar(null)}
                       onListo={() => { setDespachar(null); recargar() }} />
      )}
    </>
  )
}

/* ------------------------------------------------------------- el despacho -- */

function ModalDespacho({ averia, onCerrar, onListo }) {
  const toast = useToast()
  const [tipo, setTipo] = useState('')
  const [tecnicoId, setTecnicoId] = useState('')
  const [gruaId, setGruaId] = useState('')
  const [tallerId, setTallerId] = useState('')
  const [nota, setNota] = useState('')
  const [enviando, setEnviando] = useState(false)
  const apoyo = useApi(() => api.get(`/admin/averias/${averia.id}/apoyo`), [averia.id])

  const d = apoyo.data || {}
  const salida = SALIDAS.find((s) => s.tipo === tipo)
  // Solo los AUTONOMO salen a carretera: los 34 de Álamos son ASISTIDO, no usan
  // la app y no se mueven del taller. Ofrecerlos sería despachar a alguien que
  // no va a ir.
  const candidatos = (d.tecnicos || []).filter(
    (t) => t.sale_a_carretera && (tipo === 'llantero'
      ? t.especialidad === 'llantero'
      : t.especialidad !== 'llantero'))
  const gruas = d.gruas || []

  const necesitaTecnico = tipo === 'mecanico' || tipo === 'llantero'
  const listo = tipo && (!necesitaTecnico || tecnicoId)

  const enviar = async () => {
    setEnviando(true)
    try {
      const cuerpo = { tipo, nota: nota || null }
      if (necesitaTecnico) cuerpo.tecnico_id = Number(tecnicoId)
      if (tipo === 'grua') {
        if (gruaId) cuerpo.chofer_grua_id = Number(gruaId)
        if (tallerId) cuerpo.taller_destino_id = Number(tallerId)
      }
      const r = await api.post(`/admin/averias/${averia.id}/despachar`, cuerpo)
      toast(r.desenlace_texto || 'Apoyo asignado')
      onListo()
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal titulo={`Asignar apoyo · unidad ${averia.unidad}`} onClose={onCerrar}>
      <p className="sub">{averia.descripcion_falla || 'Sin descripción'}</p>

      <div className="field">
        <label>¿Qué se hace?</label>
        {SALIDAS.map((s) => {
          const bloqueada = s.tipo === 'grua' && !averia.puede_solicitar_arrastre
          return (
            <label key={s.tipo} className="radio-fila">
              <input type="radio" name="salida" value={s.tipo} checked={tipo === s.tipo}
                     disabled={bloqueada}
                     onChange={() => { setTipo(s.tipo); setTecnicoId(''); setGruaId('') }} />
              <span>
                <strong>{s.txt}</strong>
                <small className="sub">
                  {bloqueada ? 'Bloqueada por RN-04: falta el folio de peritos.' : s.ayuda}
                </small>
              </span>
            </label>
          )
        })}
      </div>

      {apoyo.cargando && <Spinner />}

      {necesitaTecnico && !apoyo.cargando && (
        <div className="field">
          <label>¿Quién va? · del más cerca al más lejos</label>
          {candidatos.length === 0 ? (
            <Aviso tipo="warn">
              No hay ningún {tipo} autónomo disponible. En la plantilla actual solo los técnicos
              autónomos de las satélites salen a carretera, y de llantero hay uno solo y es
              asistido de Álamos. Para este caso hace falta un proveedor externo.
            </Aviso>
          ) : (
            <select value={tecnicoId} onChange={(e) => setTecnicoId(e.target.value)}>
              <option value="">Selecciona…</option>
              {candidatos.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nombre} · {t.taller || 'sin taller'}
                  {t.km != null ? ` · ${t.km} km` : ''}
                  {t.telefono ? ` · ${t.telefono}` : ' · sin teléfono'}
                </option>
              ))}
            </select>
          )}
          <Regla>
            La distancia es en línea recta de su taller al punto de la avería. Sirve para
            saber a quién le queda más cerca, no para prometer una hora de llegada.
          </Regla>
        </div>
      )}

      {tipo === 'grua' && !apoyo.cargando && (
        <>
          <div className="field">
            <label>¿Qué chofer de grúa?</label>
            <Tabla
              columnas={[
                { k: 'sel', t: '', r: (f) => (
                  <input type="radio" name="grua" disabled={!f.libre}
                         checked={String(f.usuario_id) === gruaId}
                         onChange={() => setGruaId(String(f.usuario_id))} />
                ) },
                { k: 'nombre', t: 'Chofer' },
                { k: 'grua', t: 'Grúa', r: (f) => f.grua
                  || (f.grua_desconocida ? <span className="sub">sin registrar</span> : '—') },
                { k: 'estado', t: 'Estado', r: (f) => (
                  f.libre ? <Badge>Libre</Badge> : <span className="sub">{f.motivo}</span>
                ) },
              ]}
              filas={gruas} />
            {gruas.some((g) => g.grua_desconocida) && (
              <Aviso tipo="warn">
                Hay choferes sin grúa registrada. Mientras falte ese dato el sistema no puede
                saber si su unidad está en el taller, así que aparecen como libres aunque quizá
                no lo estén.
              </Aviso>
            )}
            <Regla>
              Si no seleccionas a nadie, el arrastre se difunde a los tres y lo toma el primero
              que pueda. Sirve cuando ninguno aparece libre o cuando corre mucha prisa.
            </Regla>
          </div>

          <div className="field">
            <label>Taller destino · opcional</label>
            <select value={tallerId} onChange={(e) => setTallerId(e.target.value)}>
              <option value="">Que lo decida el chofer de grúa</option>
              {(d.talleres || []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nombre}{t.km != null ? ` · ${t.km} km` : ''}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      {tipo && (
        <div className="field">
          <label>Nota · opcional</label>
          <textarea rows={2} value={nota} onChange={(e) => setNota(e.target.value)}
                    placeholder="Qué le dijiste al chofer, qué quedó pendiente…" />
        </div>
      )}

      <button className="btn primary block" disabled={!listo || enviando} onClick={enviar}>
        {enviando ? 'Enviando…' : salida ? salida.txt : 'Elige una salida'}
      </button>

      <Regla>
        El supervisor del chofer recibe el aviso de lo que decidiste, no una solicitud de
        permiso. Y el desenlace queda guardado: es lo que permite saber a fin de mes cuántas
        averías se resolvieron sin que saliera nadie.
      </Regla>
    </Modal>
  )
}

/* --------------------------------------------------- registro de arrastres -- */

function RegistroArrastres() {
  const { data, cargando } = useApi(() => api.get('/admin/arrastres'))
  if (cargando) return <Spinner />
  const filas = data || []

  return (
    <Card title="Arrastres realizados"
          sub={`${filas.length} registrados · del más reciente al más viejo`}>
      {filas.length === 0 ? (
        <Empty icono={IcoArrastres}>
          Todavía no hay arrastres. Aparecen aquí en cuanto se despacha el primero.
        </Empty>
      ) : (
        <Tabla
          columnas={[
            { k: 'folio', t: 'Folio' },
            { k: 'unidad', t: 'Unidad' },
            { k: 'descripcion_falla', t: 'Falla',
              r: (f) => f.descripcion_falla || <span className="sub">—</span> },
            { k: 'chofer_grua', t: 'Chofer de grúa',
              r: (f) => f.chofer_grua || <span className="sub">sin asignar</span> },
            { k: 'taller_destino', t: 'Destino',
              r: (f) => f.taller_destino || <span className="sub">—</span> },
            { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
            { k: 'fecha_solicitud', t: 'Solicitado',
              r: (f) => fmtFecha(f.fecha_solicitud) },
            { k: 'dias_abierto', t: 'Días', num: true },
          ]}
          filas={filas} />
      )}
      <Regla>
        Estos datos siempre estuvieron en la base; lo que no había era por dónde verlos.
        <IcoTecnico size={12} className="ico-inline" aria-hidden="true" /> La columna de días
        cuenta hasta el cierre, o hasta hoy si sigue abierto.
      </Regla>
    </Card>
  )
}
