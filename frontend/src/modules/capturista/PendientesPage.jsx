/** CU-CAP-05: los códigos tecleados que el catálogo no reconoce.
 *
 * No es una lista de errores: es la lista de altas que faltan. Un código que
 * aparece en ocho requisiciones y no existe en MATERIALES es una refacción que
 * el taller usa y el catálogo no tiene, no un error de dedo. Ordenados por
 * cuántas veces se pidió, que es el orden en que conviene arreglarlos.
 */
import { api } from '../../core/api.js'
import { Card, Regla, Spinner, Tabla, useApi } from '../../ui/index.js'

export function Pendientes() {
  const { data, cargando } = useApi(() => api.get('/capturista/pendientes-de-catalogo'))
  const total = (data || []).reduce((s, x) => s + x.veces, 0)

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Pendientes de catálogo</h1>
      <Card title="Códigos que el catálogo no reconoce"
            sub={cargando ? null
                 : `${(data || []).length} código(s) distintos en ${total} renglón(es)`}>
        {cargando ? <Spinner /> : (
          <Tabla
            vacio="Todos los códigos capturados existen en el catálogo"
            columnas={[
              { k: 'codigo', t: 'Código' },
              { k: 'descripcion', t: 'Como se tecleó' },
              { k: 'veces', t: 'Veces pedido', num: true },
            ]}
            filas={data || []} />
        )}
      </Card>
      <Regla>
        El renglón se guardó igual, con su código y su texto. Esta lista es para dar de alta
        esas refacciones en MATERIALES: mientras no existan, el almacén contesta «no hay»
        aunque sí haya, registradas con otro nombre.
      </Regla>
    </>
  )
}
