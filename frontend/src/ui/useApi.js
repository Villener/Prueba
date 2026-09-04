import { useEffect, useState } from 'react'

/** Carga datos de la API con los estados de carga y error ya resueltos.
 *  Devuelve `recargar()` para volver a pedir despues de una accion. */
export function useApi(fn, deps = []) {
  const [data, setData] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [n, setN] = useState(0)

  useEffect(() => {
    let vivo = true
    setCargando(true)
    fn()
      .then((d) => vivo && (setData(d), setError(null)))
      .catch((e) => vivo && setError(e.message))
      .finally(() => vivo && setCargando(false))
    return () => { vivo = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n])

  return { data, cargando, error, recargar: () => setN((x) => x + 1) }
}
