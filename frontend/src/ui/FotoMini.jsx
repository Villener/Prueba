/** Miniatura de una evidencia.
 *
 * Vive en ui/ y no junto a la pantalla del chofer porque la misma foto la
 * miran tres personas: quien la subió, el administrador de taller que decide
 * qué apoyo mandar y el supervisor.
 *
 * La imagen se baja con fetch y se pinta desde memoria. Un <img src="/api/...">
 * no serviría: la etiqueta no manda encabezados y el token vive en
 * localStorage, así que la petición llegaría sin sesión. Meter el token en la
 * consulta tampoco, porque los JWT acaban escritos en el log de accesos.
 */
import { useEffect, useState } from 'react'
import { bajarEvidencia, fmtFechaHora } from '../core/api.js'

export function FotoMini({ foto }) {
  const [url, setUrl] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let vivo = true
    let creada = null
    bajarEvidencia(foto.id)
      .then((u) => { if (vivo) { creada = u; setUrl(u) } else URL.revokeObjectURL(u) })
      .catch(() => { if (vivo) setError(true) })
    return () => {
      vivo = false
      // Sin esto, cada visita a la pantalla deja el blob en memoria hasta que
      // se recargue la página.
      if (creada) URL.revokeObjectURL(creada)
    }
  }, [foto.id])

  if (error) return <div className="foto-mini foto-rota">No se pudo cargar</div>
  if (!url) return <div className="foto-mini foto-cargando" />
  return (
    <a href={url} target="_blank" rel="noreferrer" className="foto-mini"
       title={`${foto.subida_por || 'Subida'} · ${fmtFechaHora(foto.fecha)}`}>
      <img src={url} alt={foto.descripcion || 'Foto de la avería'} />
    </a>
  )
}

/** La tira de fotos de una entidad. Sin fotos no pinta nada. */
export function TiraFotos({ fotos }) {
  if (!fotos || fotos.length === 0) return null
  return (
    <div className="fotos-fila">
      {fotos.map((f) => <FotoMini key={f.id} foto={f} />)}
    </div>
  )
}
