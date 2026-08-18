import { useState } from 'react'
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { clearSession, getUser, rolPrincipal } from './api.js'
import Login from './pages/Login.jsx'
import Chofer from './pages/Chofer.jsx'
import Supervisor from './pages/Supervisor.jsx'
import Administrador from './pages/Administrador.jsx'
import Montacarguista from './pages/Montacarguista.jsx'
import Gerente from './pages/Gerente.jsx'
import Notificaciones from './pages/Notificaciones.jsx'

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
    { to: '/plano', ico: '🅿️', txt: 'Plano' },
    { to: '/ordenes', ico: '🔧', txt: 'Órdenes' },
    { to: '/presupuestos', ico: '💰', txt: 'Presupuestos' },
    { to: '/hoja', ico: '🖨️', txt: 'Hoja' },
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
        <span className="nav-brand">Baja<span>Gas</span></span>
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
          <span className="brand">Baja<span>Gas</span></span>
          <span className="rolechip">{modulo.titulo}</span>
          <span className="spacer" />
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
