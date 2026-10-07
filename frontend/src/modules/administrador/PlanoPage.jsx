/** CU-ADM-03/04 - el plano del taller y la gestion de sus espacios. */
import { useState } from 'react'
import { api } from '../../core/api.js'
import { Card, Regla, Spinner, Tabla, useApi, useToast } from '../../ui/index.js'
import { ModalEspacio } from './ModalEspacio.jsx'
import { PlanoTaller } from './PlanoTaller.jsx'
import { SelectorTaller } from './PlanoTaller.jsx'

/** `esMecanico`: el plano de SU planta, para el mecanico de una satelite. El
 *  selector no aparece porque el servidor solo le da su taller. */
export function Plano({ esMecanico = false }) {
  const [tallerId, setTallerId] = useState(null)
  const { data, cargando, recargar } = useApi(
    () => (tallerId ? api.get(`/admin/taller/${tallerId}`) : Promise.resolve(null)), [tallerId])
  const [espacioId, setEspacioId] = useState(null)

  const t = data
  return (
    <>
      <div className="card-head">
        <h1>{t ? t.nombre : 'Plano del taller'}</h1>
        <div className="spacer" />
        <SelectorTaller valor={tallerId} onCambio={setTallerId} />
      </div>

      {cargando || !t ? <Spinner /> : (
        <>
          <div className="grid g3">
            <div className="card kpi"><div className="lbl">Espacios operativos</div>
              <div className="val">{t.total_operativos}</div></div>
            <div className="card kpi alert"><div className="lbl">Ocupados</div>
              <div className="val">{t.ocupados}</div></div>
            <div className="card kpi ok"><div className="lbl">Libres</div>
              <div className="val">{t.libres}</div></div>
          </div>

          <Card title="Plano"
                sub="Toca cualquier casilla para sacar, mover o meter un vehículo.">
            <PlanoTaller taller={t} onEspacio={(e) => setEspacioId(e.id)} />
            <Regla>
              La numeración se repite entre zonas (hay un “1” en REPARTO, otro en ELECTRICOS y
              otro en PATIO): la unicidad es por zona, no global.
            </Regla>
          </Card>
        </>
      )}

      {!esMecanico && <MecanicosDePlanta />}

      {espacioId && (
        <ModalEspacio espacioId={espacioId} esMecanico={esMecanico}
                      onCerrar={() => setEspacioId(null)} onCambio={recargar} />
      )}
    </>
  )
}

/** Los mecanicos con cuenta y su planta. Cada uno ve y trabaja SOLO la suya en
 *  la aplicacion; si se le manda a otra, se cambia aqui. */
function MecanicosDePlanta() {
  const toast = useToast()
  const lista = useApi(() => api.get('/admin/tecnicos/de-planta'))
  const talleres = useApi(() => api.get('/admin/talleres'))
  const cambiar = async (t, tallerId) => {
    try {
      const r = await api.put(`/admin/tecnicos/${t.id}/taller`, undefined, { taller_id: tallerId })
      toast(`${t.nombre} ahora trabaja en ${r.taller}`)
      lista.recargar()
    } catch (e) { toast(e.message, 'err') }
  }
  if (lista.cargando || talleres.cargando) return null
  return (
    <Card title="Mecánicos de planta"
          sub="Cada mecánico ve y trabaja solo la planta que tiene aquí. Si lo mandas a otra, cámbiala.">
      <Tabla vacio="No hay mecánicos con cuenta"
             columnas={[
               { k: 'nombre', t: 'Mecánico' },
               { k: 'especialidad', t: 'Oficio' },
               { k: 'taller', t: 'Planta', r: (t) => (
                 <select value={t.taller_id || ''} aria-label={`Planta de ${t.nombre}`}
                         onChange={(e) => cambiar(t, Number(e.target.value))}>
                   {!t.taller_id && <option value="">Sin planta</option>}
                   {(talleres.data || []).map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
                 </select>
               ) },
             ]}
             filas={lista.data || []} />
    </Card>
  )
}

/* ============================================ CU-ADM-11: buscador de almacén == */
