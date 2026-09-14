/** CU-ADM-07 — la hoja de trabajo que se imprime y se entrega en papel.
 *
 * Existe SOLO por los mecánicos de Álamos: son 31 y no usan la aplicación, así
 * que su cola del día tiene que salir en físico. Los autónomos de las satélites
 * la ven en pantalla y no necesitan esto.
 */
import { useState } from 'react'
import { api, fmtFecha, hoyTijuana } from '../../core/api.js'
import {
  Aviso, Badge, Card, Empty, EstadoBadge, IcoDescargar, IcoImprimir, Spinner, Tabla,
  useApi, useToast,
} from '../../ui/index.js'
import { SelectorTaller } from './PlanoTaller.jsx'

export function HojaTrabajo() {
  // Antes estaba fijo en el taller 1: los otros cinco no podían imprimir nada.
  const [tallerId, setTallerId] = useState(null)
  const [bajando, setBajando] = useState(false)
  const toast = useToast()
  const { data, cargando } = useApi(
    () => (tallerId ? api.get(`/admin/hoja-de-trabajo/${tallerId}`) : Promise.resolve(null)),
    [tallerId])

  const bajarResumen = async () => {
    setBajando(true)
    try {
      const nombre = await api.descargar('/admin/exportar/resumen',
                                         { params: { taller_id: tallerId } })
      toast(`Se descargó ${nombre}`)
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setBajando(false)
    }
  }

  if (cargando) return <Spinner />
  const tecnicos = data?.tecnicos || []
  const total = tecnicos.reduce((s, t) => s + t.trabajos.length, 0)

  return (
    <>
      {/* La cabecera no se imprime: en el papel estorba. */}
      <div className="card-head no-print">
        <h1>Hoja de trabajo del día</h1>
        <div className="spacer" />
        <SelectorTaller valor={tallerId} onCambio={setTallerId} />
        <button className="btn" onClick={bajarResumen} disabled={bajando}>
          <IcoDescargar size={13} className="ico-inline" aria-hidden="true" />
          {bajando ? 'Generando…' : 'Resumen en Excel'}
        </button>
        <button className="btn primary" disabled={!total} onClick={() => window.print()}>
          <IcoImprimir size={13} className="ico-inline" aria-hidden="true" /> Imprimir
        </button>
      </div>

      <div className="no-print">
        <Aviso tipo="info">
          Los mecánicos de Álamos no usan la aplicación: esta hoja se imprime y se les entrega en
          papel. Al imprimir sale <strong>solo la cola</strong> —sin menú ni botones— y cada
          técnico empieza en página nueva.
        </Aviso>
        <Aviso tipo="info">
          <strong>Resumen en Excel</strong> baja el archivo con las secciones de siempre —RESUMEN,
          PATIO y REPARADO— pero calculado de los movimientos, no tecleado. Los totales van como
          fórmula.
        </Aviso>
      </div>

      {/* Encabezado que SOLO sale en el papel: sin él la hoja llega al taller
          sin decir de qué día ni de qué taller es. */}
      <div className="solo-impresion hoja-cabecera">
        <strong>Baja Gas · Hoja de trabajo</strong>
        <span>{data?.taller || ''} · {fmtFecha(hoyTijuana())}</span>
      </div>

      {total === 0 ? (
        <Empty icono={IcoImprimir}>
          Nada pendiente en este taller. La hoja se llena cuando se asigna la cola de
          especialistas a una orden abierta.
        </Empty>
      ) : tecnicos.map((t) => (
        <Card key={t.tecnico} className="hoja-tecnico"
              title={t.tecnico} actions={<Badge>{t.especialidad}</Badge>}>
          <Tabla
            columnas={[
              { k: 'posicion', t: '#', num: true },
              { k: 'orden', t: 'Orden' },
              { k: 'unidad', t: 'Unidad' },
              { k: 'espacio', t: 'Espacio' },
              { k: 'estado', t: 'Estado', r: (f) => <EstadoBadge estado={f.estado} /> },
              // Columna vacía a propósito: el mecánico escribe aquí a mano lo
              // que hizo y Erick lo captura después. Es el puente de papel que
              // describe P5, y sin renglón la hoja no sirve para eso.
              { k: 'anota', t: 'Trabajo realizado / notas', r: () => <span className="renglon" /> },
            ]}
            filas={t.trabajos} />
        </Card>
      ))}
    </>
  )
}
