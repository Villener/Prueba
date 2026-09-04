/** Marca Baja Gas & Oil.
 *
 * LEE EL ARCHIVO, no lleva el dibujo copiado. La primera versión tenía los
 * trazos escritos aquí a mano, y cuando el cliente reemplazó `logo.svg` la app
 * siguió mostrando el logo viejo — no había forma de notarlo salvo mirándolos
 * lado a lado. El archivo es la única fuente: para cambiar la marca se
 * reemplaza `src/assets/logo.svg` y ya.
 *
 * Va en línea y no como <img> porque el CSS no puede entrar a recolorear un SVG
 * cargado como imagen, y el azul de la marca sobre el fondo del tema oscuro
 * queda ilegible. Inyectado, `styles.css` sí lo alcanza.
 */
import { useMemo } from 'react'
import bruto from '../assets/logo.svg?raw'

// Proporción real del archivo, para no deformarlo si mañana cambia.
const [ANCHO, ALTO] = (() => {
  const vb = /viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(bruto)
  return vb ? [Number(vb[1]), Number(vb[2])] : [931, 378]
})()

let contador = 0

export function Logo({ alto = 40, titulo = 'Baja Gas & Oil' }) {
  // Los ids internos del SVG (clipPath) se repetirían al pintar el logo dos
  // veces en la misma página —el menú y la barra superior— y el segundo
  // apuntaría al recorte del primero. Se les pone sufijo por instancia.
  const svg = useMemo(() => {
    const n = ++contador
    return bruto
      // El alto lo manda quien lo usa, no el archivo. OJO: solo en la etiqueta
      // <svg> de apertura. Quitarlos en todo el documento le arranca las
      // medidas al <rect> del clipPath, el recorte queda en cero y el logo
      // desaparece entero aunque los trazos sigan ahi.
      .replace(/<svg[^>]*>/, (t) => t.replace(/\s(width|height)="[^"]*"/g, ''))
      // Sufijo a los ids internos y a quien los referencia. Se hacen los dos
      // reemplazos con el mismo `n` para que sigan apuntandose entre si.
      .replace(/id="([^"]+)"/g, (t, id) => `id="${id}__${n}"`)
      .replace(/url\(#([^)]+)\)/g, (t, id) => `url(#${id}__${n})`)
      .replace('<svg', `<svg role="img" aria-label="${titulo}"`)
  }, [titulo])

  return (
    <span className="logo" style={{ height: alto, width: alto * (ANCHO / ALTO) }}
          dangerouslySetInnerHTML={{ __html: svg }} />
  )
}
