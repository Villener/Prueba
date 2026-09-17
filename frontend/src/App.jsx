import { useState } from 'react'
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { clearSession, getUser, rolPrincipal } from './core/sesion.js'
import { alternarTema, temaActual } from './core/tema.js'
import Login from './modules/acceso/LoginPage.jsx'
import Chofer from './modules/chofer/ChoferPage.jsx'
import Supervisor from './modules/supervisor/SupervisorPage.jsx'
import Administrador from './modules/administrador/AdministradorPage.jsx'
import Capturista from './modules/capturista/CapturistaPage.jsx'
import ChoferGrua from './modules/chofer-grua/ChoferGruaPage.jsx'
import Gerente from './modules/gerente/GerentePage.jsx'
import Perito from './modules/perito/PeritoPage.jsx'
import Notificaciones from './modules/sistema/NotificacionesPage.jsx'
import { Logo } from './ui/Logo.jsx'
import {
  IcoAgenda, IcoAlertas, IcoAlmacen, IcoArrastres, IcoAverias, IcoCampana, IcoCapturar,
  IcoPlantilla, IcoCumplimiento, IcoHistorial, IcoHoja, IcoIncumplimiento, IcoIndicadores,
  IcoOrdenes,
  IcoPendientes, IcoPlano, IcoPrestamos, IcoPresupuestos, IcoReportes, IcoSolicitudes,
  IcoTablero, IcoTaller, IcoTemaClaro, IcoTemaOscuro, IcoUnidad,
} from './ui/iconos.jsx'

/** Cada rol ve solo su modulo. El servidor lo vuelve a validar (RNF-04). */
const MODULOS = {
  chofer: { titulo: 'Chofer', Componente: Chofer, tabs: [
    { to: '/', Ico: IcoUnidad, txt: 'Mi unidad' },
    { to: '/prestamos', Ico: IcoPrestamos, txt: 'Préstamos' },
    { to: '/taller', Ico: IcoTaller, txt: 'Taller' },
    { to: '/averias', Ico: IcoAverias, txt: 'Averías' },
  ] },
  supervisor: { titulo: 'Supervisor', Componente: Supervisor, tabs: [
    { to: '/', Ico: IcoPlantilla, txt: 'Plantilla' },
    { to: '/prestamos', Ico: IcoPrestamos, txt: 'Préstamos' },
    { to: '/averias', Ico: IcoAverias, txt: 'Averías' },
    { to: '/cumplimiento', Ico: IcoCumplimiento, txt: 'Cumplimiento' },
  ] },
  administrador: { titulo: 'Administrador', Componente: Administrador, tabs: [
    { to: '/', Ico: IcoSolicitudes, txt: 'Solicitudes' },
    { to: '/arrastres', Ico: IcoArrastres, txt: 'Carretera' },
    { to: '/agenda', Ico: IcoAgenda, txt: 'Agenda' },
    { to: '/plano', Ico: IcoPlano, txt: 'Plano' },
    { to: '/almacen', Ico: IcoAlmacen, txt: 'Almacén' },
    { to: '/ordenes', Ico: IcoOrdenes, txt: 'Órdenes' },
    { to: '/presupuestos', Ico: IcoPresupuestos, txt: 'Presupuestos' },
    { to: '/reportes', Ico: IcoReportes, txt: 'Reportes' },
    { to: '/hoja', Ico: IcoHoja, txt: 'Hoja' },
    { to: '/indicadores', Ico: IcoIndicadores, txt: 'Indicadores' },
  ] },
  capturista: { titulo: 'Capturista', Componente: Capturista, tabs: [
    { to: '/', Ico: IcoOrdenes, txt: 'Requisiciones' },
    { to: '/capturar', Ico: IcoCapturar, txt: 'Capturar' },
    { to: '/pendientes', Ico: IcoPendientes, txt: 'Pendientes' },
  ] },
  // Nota 9: Edgar es del sindicato pero trabaja para Baja Gas. Actor interno,
  // con su propio modulo -- por eso el peritaje se levanta dentro del sistema.
  perito: { titulo: 'Perito', Componente: Perito, tabs: [
    { to: '/', Ico: IcoAverias, txt: 'Pendientes' },
    { to: '/historial', Ico: IcoHistorial, txt: 'Mis peritajes' },
  ] },
  chofer_grua: { titulo: 'Chofer de grúa', Componente: ChoferGrua, tabs: [
    { to: '/', Ico: IcoAlertas, txt: 'Alertas' },
    { to: '/arrastres', Ico: IcoArrastres, txt: 'Arrastres' },
    { to: '/historial', Ico: IcoHistorial, txt: 'Historial' },
  ] },
  gerente: { titulo: 'Gerente', Componente: Gerente, tabs: [
    { to: '/', Ico: IcoTablero, txt: 'Tablero' },
    { to: '/incumplimiento', Ico: IcoIncumplimiento, txt: 'Incumplimiento' },
    { to: '/taller', Ico: IcoPlano, txt: 'Taller' },
    { to: '/presupuestos', Ico: IcoPresupuestos, txt: 'Presupuestos' },
    { to: '/alertas', Ico: IcoCampana, txt: 'Alertas' },
    { to: '/estadisticas', Ico: IcoIndicadores, txt: 'Estadísticas' },
  ] },
}

/** Interruptor de tema. Claro por defecto; el oscuro se enciende a mano. */
function BotonTema() {
  const [tema, setTema] = useState(temaActual)
  const oscuro = tema === 'dark'
  return (
    <button className="btn sm theme-btn" onClick={() => setTema(alternarTema())}
            aria-pressed={oscuro} title={oscuro ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}>
      {oscuro
        ? <IcoTemaClaro size={15} strokeWidth={2} aria-hidden="true" />
        : <IcoTemaOscuro size={15} strokeWidth={2} aria-hidden="true" />}
      <span className="solo-ancho">{oscuro ? 'Claro' : 'Oscuro'}</span>
    </button>
  )
}

export default function App() {
  const [usuario, setUsuario] = useState(getUser())
  const navigate = useNavigate()
  const rol = rolPrincipal(usuario)

  if (!usuario || !rol) {
    return (
      <Routes>
        <Route path="/login" element={<Login onEntrar={setUsuario} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  const modulo = MODULOS[rol]
  const salir = () => {
    clearSession()
    setUsuario(null)
    navigate('/login')
  }

  return (
    <div className="app">
      <nav className="nav">
        <span className="nav-brand"><Logo alto={30} /></span>
        {modulo.tabs.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.to === '/'}
                   className={({ isActive }) => (isActive ? 'active' : '')}>
            <span className="ico"><t.Ico size={20} strokeWidth={1.75} aria-hidden="true" /></span>
            <span>{t.txt}</span>
          </NavLink>
        ))}
      </nav>

      <div className="main-col">
        <header className="topbar">
          <span className="brand"><Logo alto={24} /></span>
          <span className="rolechip">{modulo.titulo}</span>
          <span className="spacer" />
          <BotonTema />
          <NavLink to="/notificaciones" className="btn sm" title="Notificaciones"
                 aria-label="Notificaciones">
          <IcoCampana size={15} strokeWidth={2} aria-hidden="true" />
        </NavLink>
          <button className="btn sm" onClick={salir} title="Cerrar sesión">Salir</button>
        </header>

        <main className="content">
          <Routes>
            <Route path="/notificaciones" element={<Notificaciones />} />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/*" element={<modulo.Componente usuario={usuario} />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
