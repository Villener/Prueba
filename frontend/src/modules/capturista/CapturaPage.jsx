/** CU-CAP-03: teclear un papel.
 *
 * El formulario sigue el orden del papel para que se pueda capturar sin
 * levantar la vista: folio, fecha, unidad, quien lo pidio, y luego los
 * renglones. Es el mismo recorrido que hoy se hace sobre la hoja de Excel.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, hoyTijuana } from '../../core/api.js'
import {
  Aviso, Badge, BuscadorPieza, Card, Regla, Tabla, useApi, useToast,
} from '../../ui/index.js'
import { BuscadorUnidad } from '../../ui/BuscadorUnidad.jsx'

const VACIO = { pieza_id: null, codigo: '', descripcion: '', cantidad: 1 }

export function Captura() {
  const toast = useToast()
  const navigate = useNavigate()
  const mecanicos = useApi(() => api.get('/capturista/mecanicos'))

  const [folio, setFolio] = useState('')
  const [fecha, setFecha] = useState(hoyTijuana())
  const [unidad, setUnidad] = useState(null)          // {id, num_economico, ...}
  const [tecnicoId, setTecnicoId] = useState('')
  const [observaciones, setObservaciones] = useState('')
  const [renglones, setRenglones] = useState([])
  const [nuevo, setNuevo] = useState({ ...VACIO })
  const [choque, setChoque] = useState(null)          // el 409 del servidor
  const [guardando, setGuardando] = useState(false)

  const agregar = () => {
    const desc = nuevo.descripcion.trim()
    if (desc.length < 2) return toast('Escribe qué material es', 'err')
    setRenglones((rs) => [...rs, { ...nuevo, descripcion: desc }])
    setNuevo({ ...VACIO })
  }

  const quitar = (i) => setRenglones((rs) => rs.filter((_, k) => k !== i))

  const guardar = async (forzar = false) => {
    if (folio.trim().length < 2) return toast('Falta el folio del papel', 'err')
    if (!renglones.length) return toast('Agrega al menos un material', 'err')
    setGuardando(true)
    try {
      const r = await api.post('/capturista/requisiciones', {
        folio: folio.trim(),
        fecha,
        unidad_id: unidad?.id ?? null,
        unidad_texto: unidad?.num_economico ?? null,
        tecnico_id: tecnicoId ? Number(tecnicoId) : null,
        observaciones: observaciones.trim() || null,
        renglones: renglones.map((x) => ({
          pieza_id: x.pieza_id, codigo: x.codigo || null,
          descripcion: x.descripcion, cantidad: Number(x.cantidad) || 1,
        })),
        forzar,
      })
      toast(`Requisición ${r.folio} capturada`)
      navigate('/')
    } catch (e) {
      // 409 con detalle estructurado: el servidor no solo dice que no, dice
      // cual es la anterior y como seguir.
      if (e.status === 409 && e.datos) setChoque(e.datos)
      else toast(e.message, 'err')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Capturar requisición</h1>

      <Card title="El encabezado del papel">
        <div className="grid g2">
          <div className="field">
            <label htmlFor="folio">Folio</label>
            <input id="folio" value={folio} placeholder="J373"
                   onChange={(e) => { setFolio(e.target.value); setChoque(null) }} />
          </div>
          <div className="field">
            <label htmlFor="fecha">Fecha del papel</label>
            <input id="fecha" type="date" value={fecha}
                   onChange={(e) => { setFecha(e.target.value); setChoque(null) }} />
          </div>
        </div>

        <div className="field">
          <label>Unidad</label>
          <BuscadorUnidad elegida={unidad}
                          onElegir={(u) => { setUnidad(u); setChoque(null) }} />
        </div>

        <div className="field">
          <label htmlFor="mec">Quién pidió el material</label>
          <select id="mec" value={tecnicoId} onChange={(e) => setTecnicoId(e.target.value)}>
            <option value="">— sin especificar —</option>
            {(mecanicos.data || []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.nombre}{t.num_empleado ? ` · ${t.num_empleado}` : ''}
                {t.puesto ? ` · ${t.puesto}` : ''}
              </option>
            ))}
          </select>
        </div>
        {/* Los mecanicos no tienen cuenta (v1.1). Por eso alguien teclea por
            ellos, y por eso el papel guarda dos nombres. */}
        <Regla>
          El mecánico no usa la aplicación: se elige del catálogo. La requisición queda con
          los dos responsables, quien la pidió y quien la tecleó.
        </Regla>
      </Card>

      <Card title="Materiales" sub={`${renglones.length} renglón(es)`}>
        <div className="field">
          <label>Buscar en el catálogo</label>
          <BuscadorPieza
            valor={nuevo.pieza_id} nombre={nuevo.pieza_id ? nuevo.descripcion : null}
            onElegir={(id, nombre) => setNuevo((n) => ({
              ...n, pieza_id: id, descripcion: nombre || '', codigo: n.codigo,
            }))} />
        </div>
        <div className="grid g3">
          <div className="field">
            <label htmlFor="cod">Código del papel</label>
            <input id="cod" value={nuevo.codigo} placeholder="228806"
                   onChange={(e) => setNuevo((n) => ({ ...n, codigo: e.target.value }))} />
          </div>
          <div className="field">
            <label htmlFor="desc">Material</label>
            <input id="desc" value={nuevo.descripcion} placeholder="FILTRO DIESEL CNJ 4T"
                   onChange={(e) => setNuevo((n) => ({ ...n, descripcion: e.target.value }))} />
          </div>
          <div className="field">
            <label htmlFor="cant">Cantidad</label>
            <input id="cant" type="number" min="1" value={nuevo.cantidad}
                   onChange={(e) => setNuevo((n) => ({ ...n, cantidad: e.target.value }))} />
          </div>
        </div>
        <button type="button" className="btn" onClick={agregar}>Agregar renglón</button>

        {/* El renglon se guarda aunque el codigo no exista en el catalogo:
            perderlo seria peor que guardarlo sin casar. */}
        <div style={{ marginTop: 12 }}>
          <Tabla
            vacio="Todavía no agregas materiales"
            columnas={[
              { k: 'codigo', t: 'Código', r: (f) => f.codigo || '—' },
              { k: 'descripcion', t: 'Material' },
              { k: 'cantidad', t: 'Cant.', num: true },
              { k: 'pieza_id', t: 'Catálogo',
                r: (f) => f.pieza_id
                  ? <Badge tono="ok">sí</Badge>
                  : <Badge tono="warn">se casa al guardar</Badge> },
              { k: 'x', t: '',
                r: (f) => <button type="button" className="btn sm"
                                  onClick={() => quitar(renglones.indexOf(f))}>Quitar</button> },
            ]}
            filas={renglones} />
        </div>
      </Card>

      {choque && (
        <Aviso tipo="warn">
          <strong>{choque.mensaje}</strong>
          <br />{choque.sugerencia}
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={() => navigate('/')}>Ver las capturadas</button>
            <button className="btn danger" disabled={guardando}
                    onClick={() => guardar(true)}>
              Sí es otro papel, guardar de todos modos
            </button>
          </div>
        </Aviso>
      )}

      <div className="btn-row" style={{ marginTop: 12 }}>
        <button className="btn primary" disabled={guardando} onClick={() => guardar(false)}>
          {guardando ? 'Guardando…' : 'Guardar requisición'}
        </button>
        <button className="btn" onClick={() => navigate('/')}>Cancelar</button>
      </div>

      <div className="field" style={{ marginTop: 14 }}>
        <label htmlFor="obs">Observaciones</label>
        <textarea id="obs" value={observaciones}
                  onChange={(e) => setObservaciones(e.target.value)}
                  placeholder="Lo que traiga escrito a mano el papel" />
      </div>
    </>
  )
}
