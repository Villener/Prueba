/** CU-ADM-03/04 - el plano del taller y la gestion de sus espacios. */
import { useState } from 'react'
import { api } from '../../core/api.js'
import { Card, Regla, Spinner, useApi } from '../../ui/index.js'
import { ModalEspacio } from './ModalEspacio.jsx'
import { PlanoTaller } from './PlanoTaller.jsx'
import { SelectorTaller } from './PlanoTaller.jsx'

export function Plano() {
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

      {espacioId && (
        <ModalEspacio espacioId={espacioId} onCerrar={() => setEspacioId(null)}
                      onCambio={recargar} />
      )}
    </>
  )
}

/* ============================================ CU-ADM-11: buscador de almacén == */
