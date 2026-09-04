/** Modulo Administrador - CU-ADM-* de docs/casos-de-uso.md
 *
 * Este archivo solo ENRUTA. Cada pantalla vive en su propio archivo, nombrada
 * por el caso de uso que realiza.
 */
import { Route, Routes } from 'react-router-dom'

import { Solicitudes } from './SolicitudesPage.jsx'
import { Agenda } from './AgendaPage.jsx'
import { Plano } from './PlanoPage.jsx'
import { Almacen } from './AlmacenPage.jsx'
import { Ordenes } from './OrdenesPage.jsx'
import { Presupuestos } from './PresupuestosPage.jsx'
import { HojaTrabajo } from './HojaTrabajoPage.jsx'
import { ReportesMantenimiento } from './ReporteMantenimientoPage.jsx'

export default function Administrador() {
  return (
    <Routes>
      <Route path="/" element={<Solicitudes />} />
      <Route path="/agenda" element={<Agenda />} />
      <Route path="/plano" element={<Plano />} />
      <Route path="/almacen" element={<Almacen />} />
      <Route path="/ordenes" element={<Ordenes />} />
      <Route path="/presupuestos" element={<Presupuestos />} />
      <Route path="/reportes" element={<ReportesMantenimiento />} />
      <Route path="/reportes/:id" element={<ReportesMantenimiento />} />
      <Route path="/hoja" element={<HojaTrabajo />} />
    </Routes>
  )
}
