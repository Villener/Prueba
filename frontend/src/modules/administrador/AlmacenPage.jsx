/** CU-ADM-11 - buscador del almacen con respuesta inmediata. */
import { useEffect, useState } from 'react'
import { api } from '../../core/api.js'
import { letras } from '../../core/busqueda.js'
import { Aviso, Badge, Card, Empty, Spinner } from '../../ui/index.js'
import { SelectorTaller } from './PlanoTaller.jsx'

/* ============================================ CU-ADM-11: buscador de almacén == */
export function Almacen() {
  const [q, setQ] = useState('')
  const [tallerId, setTallerId] = useState(null)
  const [datos, setDatos] = useState(null)
  const [buscando, setBuscando] = useState(false)

  // Se busca mientras escribe, pero con freno: son más de 18 mil refacciones.
  //
  // Los asteriscos NO cuentan como letras, igual que en el servidor: si
  // contaran, teclear «J*» dispararía una petición que sólo puede volver
  // con el aviso de que faltan letras.
  useEffect(() => {
    if (letras(q) < 2) { setDatos(null); return }
    let vivo = true
    setBuscando(true)
    const id = setTimeout(() => {
      api.get('/admin/piezas', { q, taller_id: tallerId })
        .then((d) => vivo && setDatos(d))
        .catch(() => vivo && setDatos(null))
        .finally(() => vivo && setBuscando(false))
    }, 300)
    return () => { vivo = false; clearTimeout(id) }
  }, [q, tallerId])

  return (
    <>
      <div className="card-head">
        <h1>Almacén</h1>
        <div className="spacer" />
        <SelectorTaller valor={tallerId} onCambio={setTallerId} />
      </div>

      <Card>
        <div className="field">
          <label>Buscar refacción</label>
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="balatas, filtro de aceite, 231208, JUE*EM*G*7000…" />
        </div>
        <p className="sub">
          Busca por nombre o por número de parte. Poco más de la mitad del catálogo
          trae código de SAP; el resto solo se encuentra por nombre.
        </p>
        <p className="sub">
          {/* El mismo truco del Excel de MATERIALES, que es como busca almacén. */}
          Con <code>*</code> se rellena lo que va en medio, como en el Excel:{' '}
          <code>JUE*EM*G*7000</code> encuentra <em>JUEGO EMPAQUE GMC 7000</em>.
        </p>

        {letras(q) >= 2 && (
          buscando ? <Spinner /> : !datos ? null : datos.total === 0 ? (
            <Empty icono="🔍">{datos.aviso}</Empty>
          ) : (
            <>
              <Aviso tipo={datos.con_existencia ? 'ok' : 'warn'}>
                {datos.total} resultado(s) · <strong>{datos.con_existencia}</strong> con existencia
                {datos.total > datos.mostrando && ` · mostrando los ${datos.mostrando} más parecidos`}
              </Aviso>
              {datos.resultados.map((p) => (
                <div className="list-item" key={p.id}>
                  <div className="grow">
                    <div className="t">{p.nombre}</div>
                    <div className="s">
                      {/* El código de SAP sirve para PEDIR la pieza; el que se
                          rescató del nombre solo para encontrarla. No valen lo
                          mismo, así que se distinguen. */}
                      {p.codigo
                        ? <strong>{p.codigo}{p.codigo_es_sap ? '' : ' (del nombre)'}</strong>
                        : <span style={{ color: 'var(--muted)' }}>sin código</span>}
                      {p.ubicacion ? ` · ${p.ubicacion}` : ''}
                    </div>
                  </div>
                  {p.hay ? (
                    <Badge tono="ok">Hay {p.disponible}</Badge>
                  ) : (
                    <Badge tono="danger">No hay</Badge>
                  )}
                </div>
              ))}
            </>
          )
        )}
      </Card>
    </>
  )
}

/* ------------------------------- CU-ADM-05/06/11/14/10 (captura v1.1) ------ */
