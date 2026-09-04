import { useState } from 'react'
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { clearSession, getUser, rolPrincipal } from './core/sesion.js'
import { alternarTema, temaActual } from './core/tema.js'
import Login from './modules/acceso/LoginPage.jsx'
import Chofer from './modules/chofer/ChoferPage.jsx'
import Supervisor from './modules/supervisor/SupervisorPage.jsx'
import Administrador from './modules/administrador/AdministradorPage.jsx'
import Capturista from './modules/capturista/CapturistaPage.jsx'
import Montacarguista from './modules/montacarguista/MontacarguistaPage.jsx'
import Gerente from './modules/gerente/GerentePage.jsx'
import Notificaciones from './modules/sistema/NotificacionesPage.jsx'
import { Logo } from './ui/Logo.jsx'

/** Cada rol ve solo su modulo. El servidor lo vuelve a validar (RNF-04). */
const MODULOS = {
  chofer: { titulo: 'Chofer', Componente: Chofer, tabs: [
    { to: '/', ico: '🚚', txt: 'Mi unidad' },
    { to: '/prestamos', ico: '🔁', txt: 'Préstamos' },
    { to: '/taller', ico: '🔧', txt: 'Taller' },
    { to: '/averias', ico: '⚠️', txt: 'Averías' },
  ] },
  supervisor: { titulo: 'Supervisor', Componente: Supervisor, tabs: [
    { to: '/', ico: '👥', txt: 'Cuadrilla' },
    { to: '/prestamos', ico: '🔁', txt: 'Préstamos' },
    { to: '/averias', ico: '⚠️', txt: 'Averías' },
    { to: '/cumplimiento', ico: '📋', txt: 'Cumplimiento' },
  ] },
  administrador: { titulo: 'Administrador', Componente: Administrador, tabs: [
    { to: '/', ico: '📥', txt: 'Solicitudes' },
    { to: '/agenda', ico: '📅', txt: 'Agenda' },
    { to: '/plano', ico: '🅿️', txt: 'Plano' },
    { to: '/almacen', ico: '📦', txt: 'Almacén' },
    { to: '/ordenes', ico: '🔧', txt: 'Órdenes' },
    { to: '/presupuestos', ico: '💰', txt: 'Presupuestos' },
    { to: '/reportes', ico: '📋', txt: 'Reportes' },
    { to: '/hoja', ico: '🖨️', txt: 'Hoja' },
  ] },
  capturista: { titulo: 'Capturista', Componente: Capturista, tabs: [
    { to: '/', ico: '📋', txt: 'Requisiciones' },
    { to: '/capturar', ico: '✏️', txt: 'Capturar' },
    { to: '/pendientes', ico: '🔎', txt: 'Pendientes' },
  ] },
  montacarguista: { titulo: 'Montacarguista', Componente: Montacarguista, tabs: [
    { to: '/', ico: '🚨', txt: 'Alertas' },
    { to: '/arrastres', ico: '🛻', txt: 'Arrastres' },
    { to: '/historial', ico: '🗂️', txt: 'Historial' },
  ] },
  gerente: { titulo: 'Gerente', Componente: Gerente, tabs: [
    { to: '/', ico: '📊', txt: 'Tablero' },
    { to: '/incumplimiento', ico: '🚦', txt: 'Incumplimiento' },
    { to: '/taller', ico: '🅿️', txt: 'Taller' },
    { to: '/presupuestos', ico: '💰', txt: 'Presupuestos' },
    { to: '/alertas', ico: '🔔', txt: 'Alertas' },
  ] },
}

/** Interruptor de tema. Claro por defecto; el oscuro se enciende a mano. */
function BotonTema() {
  const [tema, setTema] = useState(temaActual)
  const oscuro = tema === 'dark'
  return (
    <button className="btn sm theme-btn" onClick={() => setTema(alternarTema())}
            aria-pressed={oscuro} title={oscuro ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}>
      {oscuro ? '☀' : '☾'}<span className="solo-ancho">{oscuro ? 'Claro' : 'Oscuro'}</span>
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
            <span className="ico">{t.ico}</span>
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
          <NavLink to="/notificaciones" className="btn sm" title="Notificaciones">🔔</NavLink>
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
