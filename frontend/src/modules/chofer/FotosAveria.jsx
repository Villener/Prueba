/** CU-CHO-14 — las fotos de una avería.
 *
 * La foto va DESPUÉS de mandar la alerta, nunca antes. Pedirla antes cuesta
 * medio minuto en lo que menos corre prisa: primero sale el aviso, que es lo
 * urgente, y la foto se sube con calma. Para entonces el administrador de
 * taller ya está viendo el reporte y la foto le aparece encima.
 *
 * `capture="environment"` abre la cámara trasera directo en el teléfono, sin
 * pasar por el explorador de archivos. En computadora el atributo se ignora y
 * se comporta como un selector normal.
 */
import { useState } from 'react'
import { api } from '../../core/api.js'
import { Aviso, IcoNota, Regla, TiraFotos, useToast } from '../../ui/index.js'

const MAX_MB = 8

export function FotosAveria({ averia, onCambio }) {
  const toast = useToast()
  const [subiendo, setSubiendo] = useState(false)
  const fotos = averia.fotos || []

  const elegir = async (e) => {
    const archivo = e.target.files?.[0]
    // El input se limpia SIEMPRE: si no, elegir la misma foto dos veces
    // seguidas no dispara el evento y parece que el botón se trabó.
    e.target.value = ''
    if (!archivo) return

    if (archivo.size > MAX_MB * 1024 * 1024) {
      toast(`La foto pesa ${(archivo.size / 1048576).toFixed(1)} MB y el tope son ${MAX_MB}.`,
            'err')
      return
    }
    setSubiendo(true)
    try {
      const actualizada = await api.subir(`/chofer/averias/${averia.id}/foto`, archivo)
      toast('Foto subida')
      onCambio(actualizada)
    } catch (err) {
      toast(err.message, 'err')
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <div className="fotos-averia">
      <TiraFotos fotos={fotos} />

      {fotos.length === 0 && (
        <Aviso tipo="info">
          <strong>Sube una foto de cómo quedó.</strong> Es lo que le ahorra la llamada al
          administrador de taller para saber qué mandar.
        </Aviso>
      )}

      <label className={`btn${subiendo ? ' disabled' : ''}`} style={{ cursor: 'pointer' }}>
        <IcoNota size={13} className="ico-inline" aria-hidden="true" />
        {subiendo ? 'Subiendo…' : fotos.length ? 'Agregar otra foto' : 'Tomar foto'}
        <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment"
               onChange={elegir} disabled={subiendo || fotos.length >= 6}
               style={{ display: 'none' }} />
      </label>

      {fotos.length >= 6 && <Regla>Ya son seis fotos; es el tope por reporte.</Regla>}
    </div>
  )
}
