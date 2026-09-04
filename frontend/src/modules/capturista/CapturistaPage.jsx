/** Modulo Capturista de datos - CU-CAP-* de docs/casos-de-uso.md
 *
 * Este archivo solo ENRUTA. Cada pantalla vive en su propio archivo, nombrada
 * por el caso de uso que realiza.
 */
import { Route, Routes } from 'react-router-dom'

import { Requisiciones } from './RequisicionesPage.jsx'
import { Captura } from './CapturaPage.jsx'
import { Pendientes } from './PendientesPage.jsx'

export default function Capturista() {
  return (
    <Routes>
      <Route path="/" element={<Requisiciones />} />
      <Route path="/capturar" element={<Captura />} />
      <Route path="/pendientes" element={<Pendientes />} />
    </Routes>
  )
}
