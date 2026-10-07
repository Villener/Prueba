import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import {
  alCambiarSesionEnOtraVentana, borrarAvisoSesion, clearSession, dejarAvisoSesion, getToken, getUser,
  leerAvisoSesion, mismaPersona, rolPrincipal, setSession, telefonoValido,
} from './core/sesion.js'
import { api } from './core/api.js'
import {
  activarAvisos, avisosApagadosAqui, escucharServiceWorker, estadoAvisos, sincronizarAvisos,
  soltarAvisosDeEstaCuenta, vigilarVersion,
} from './core/pwa.js'
import { Aviso } from './ui/Feedback.jsx'
import { useToast } from './ui/Toast.jsx'
import { alternarTema, temaActual } from './core/tema.js'
import Login from './modules/acceso/LoginPage.jsx'
import Chofer from './modules/chofer/ChoferPage.jsx'
import Supervisor from './modules/supervisor/SupervisorPage.jsx'
import Administrador from './modules/administrador/AdministradorPage.jsx'
import Capturista from './modules/capturista/CapturistaPage.jsx'
import ChoferGrua from './modules/chofer-grua/ChoferGruaPage.jsx'
import Gerente from './modules/gerente/GerentePage.jsx'
import Perito from './modules/perito/PeritoPage.jsx'
import Mecanico from './modules/mecanico/MecanicoPage.jsx'
import Notificaciones from './modules/sistema/NotificacionesPage.jsx'
import BitacoraUnidad from './modules/sistema/BitacoraUnidadPage.jsx'
import MisDatos from './modules/sistema/MisDatosPage.jsx'
import Datos from './modules/cargas/CargarDatosPage.jsx'
import { Logo } from './ui/Logo.jsx'
import {
  IcoAgenda, IcoAlertas, IcoAlmacen, IcoArrastres, IcoAverias, IcoCampana, IcoCapturar, IcoDatos,
  IcoMisDatos,
  IcoPlantilla, IcoCumplimiento, IcoHistorial, IcoHoja, IcoIncumplimiento, IcoIndicadores,
  IcoOrdenes,
  IcoPendientes, IcoPlano, IcoPrestamos, IcoPresupuestos, IcoReportes, IcoSolicitudes,
  IcoTablero, IcoTaller, IcoTecnico, IcoTemaClaro, IcoTemaOscuro, IcoUnidad,
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
  administrador: { titulo: 'Administrador', corto: 'Admin', Componente: Administrador, tabs: [
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
    { to: '/datos', Ico: IcoDatos, txt: 'Datos' },
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
  // Los seis de las plantas satélite. Sus cuentas ya existían en producción —con
  // contraseña buena y sin un solo rol— así que autenticaban y no les tocaba
  // ningún módulo: entraban a una aplicación vacía. Este es el módulo que les
  // faltaba. Los 34 de Álamos son ASISTIDO, no tienen cuenta y no la necesitan.
  mecanico: { titulo: 'Mecánico', Componente: Mecanico, tabs: [
    { to: '/', Ico: IcoTecnico, txt: 'Mi trabajo' },
    { to: '/planta', Ico: IcoPlano, txt: 'Mi planta' },
    { to: '/solicitudes', Ico: IcoSolicitudes, txt: 'Solicitudes' },
    { to: '/auxilios', Ico: IcoAverias, txt: 'Carretera' },
    { to: '/piezas', Ico: IcoAlmacen, txt: 'Piezas' },
    { to: '/traslados', Ico: IcoArrastres, txt: 'Traslados' },
  ] },
  chofer_grua: { titulo: 'Chofer de grúa', corto: 'Grúa', Componente: ChoferGrua, tabs: [
    { to: '/', Ico: IcoAlertas, txt: 'Alertas' },
    { to: '/arrastres', Ico: IcoArrastres, txt: 'Arrastres' },
    { to: '/historial', Ico: IcoHistorial, txt: 'Historial' },
  ] },
  // «Estadísticas» salió del menú y «Indicadores» entró en su lugar, y las dos
  // cosas son el mismo pedido del gerente en la junta: lo de Estadísticas ya no
  // es una pantalla —vive dentro del Tablero, junto a las cuatro gráficas del
  // rango, porque preguntar «cómo vamos» y «cómo estamos» en dos pestañas
  // distintas era lo que lo obligaba a ir y venir—, e Indicadores es la pantalla
  // del taller que hasta hoy solo se podía abrir entrando al módulo del
  // administrador con otro correo y otra contraseña. Eran seis pestañas y el menú
  // no creció: cambió de contenido.
  //
  // «Historiales» es la séptima y sí lo hace crecer, con motivo: es lo que el
  // gerente pidió después —todos los mecánicos con su historial de preventivos y
  // a qué unidades fueron, más el historial de cada unidad, cada chofer y cada
  // taller— y no cabía dentro de ninguna de las seis. Va AL FINAL a propósito,
  // aunque por contenido se parezca a Indicadores: meterla en medio correría de
  // lugar las otras seis, y el gerente lleva meses apretando la cuarta posición
  // sin mirar. Las cuatro vistas se eligen DENTRO de la pantalla con el control
  // segmentado, que es lo que evita que fueran cuatro pestañas más: en 375 px la
  // barra ya rueda de lado con siete.
  gerente: { titulo: 'Gerente', Componente: Gerente, tabs: [
    { to: '/', Ico: IcoTablero, txt: 'Tablero' },
    { to: '/incumplimiento', Ico: IcoIncumplimiento, txt: 'Incumplimiento' },
    { to: '/taller', Ico: IcoPlano, txt: 'Taller' },
    { to: '/presupuestos', Ico: IcoPresupuestos, txt: 'Presupuestos' },
    { to: '/alertas', Ico: IcoCampana, txt: 'Alertas' },
    // El mismo icono que lleva esta pantalla en el menú del administrador: es la
    // MISMA pantalla, y darle otro dibujo aquí la haría parecer otra cosa.
    { to: '/indicadores', Ico: IcoIndicadores, txt: 'Indicadores' },
    // IcoHistorial (el reloj con la flecha) y no un dibujo nuevo: es el mismo
    // que ya marca «Mis peritajes» y el «Historial» del chofer de grúa. Dos
    // dibujos distintos para el mismo concepto es exactamente lo que el catálogo
    // de ui/iconos.jsx existe para evitar.
    { to: '/historiales', Ico: IcoHistorial, txt: 'Historiales' },
  ] },
}

// Una cuenta por area (Logistica, Almacen, Compras, Taller) que solo sube sus
// Excel. Las cuatro ven la misma pantalla; que archivos le tocan a cada una lo
// decide el servidor.
for (const area of ['logistica', 'almacen', 'compras', 'taller']) {
  MODULOS[`datos_${area}`] = { titulo: 'Carga de datos', corto: 'Datos', Componente: Datos, tabs: [
    { to: '/', Ico: IcoDatos, txt: 'Cargar datos' },
  ] }
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

/** Por que esta ventana cambio sola de cuenta. Sin esto el usuario vuelve a
 *  ella, ve otro modulo y cree que el sistema se descompuso. */
function AvisoSesion({ texto, onCerrar }) {
  if (!texto) return null
  return (
    <Aviso tipo="warn">
      {texto}{' '}
      <button className="btn sm" onClick={onCerrar}>Entendido</button>
    </Aviso>
  )
}

/** Recordatorio para quien no tiene celular: sin el, el taller no puede
 *  avisarle de sus citas por WhatsApp. Se puede posponer en esta ventana. Las
 *  cuentas de carga de datos son de un area, no de una persona: a esas no. */
const LUEGO_KEY = 'bg_tel_luego'
const pideTelefono = (usuario) => !telefonoValido(usuario.telefono)
  && !(usuario.roles || []).every((r) => r.startsWith('datos_'))
function PideTelefono({ usuario, onLuego }) {
  if (!pideTelefono(usuario)) return null
  return (
    <Aviso tipo="info">
      Agrega tu celular para que el taller te pueda avisar de tus citas.{' '}
      <NavLink to="/mis-datos" className="btn sm primary">Agregar celular</NavLink>{' '}
      <button className="btn sm" onClick={onLuego}>Ahora no</button>
    </Aviso>
  )
}

/** Invitacion a recibir los avisos en este celular. Solo sale cuando se pueden
 *  activar con un toque (navegador compatible y permiso sin pedir todavia); el
 *  caso del iPhone, que primero hay que instalar, se explica en Mis datos.
 *  "Ahora no" la guarda una semana: el permiso del navegador se pide UNA vez y
 *  conviene pedirlo cuando la persona dijo que si, no a la fuerza. */
const AVISOS_LUEGO_KEY = 'bg_avisos_luego'
const SEMANA_MS = 7 * 24 * 3600 * 1000
function avisosPospuestos() {
  try { return Date.now() - Number(localStorage.getItem(AVISOS_LUEGO_KEY) || 0) < SEMANA_MS } catch { return false }
}
function PideAvisos({ usuario }) {
  const [mostrar, setMostrar] = useState(false)
  const [activando, setActivando] = useState(false)
  const toast = useToast()
  const deArea = (usuario.roles || []).every((r) => r.startsWith('datos_'))

  useEffect(() => {
    if (deArea || avisosPospuestos() || avisosApagadosAqui()) return
    let vivo = true
    estadoAvisos().then((e) => { if (vivo) setMostrar(e === 'inactivo') })
    return () => { vivo = false }
  }, [deArea])

  if (!mostrar) return null
  const luego = () => {
    try { localStorage.setItem(AVISOS_LUEGO_KEY, String(Date.now())) } catch { /* solo esta vez */ }
    setMostrar(false)
  }
  const activar = async () => {
    setActivando(true)
    try {
      await activarAvisos()
      toast('Listo: los avisos del taller te llegarán a este celular')
      setMostrar(false)
    } catch (e) {
      toast(e.message, 'err')
      if (typeof Notification !== 'undefined' && Notification.permission === 'denied') setMostrar(false)
    } finally {
      setActivando(false)
    }
  }
  return (
    <Aviso tipo="info">
      Activa los avisos para enterarte al momento de tus citas y cambios, aunque la app esté cerrada.{' '}
      <button className="btn sm primary" onClick={activar} disabled={activando}>
        {activando ? 'Activando…' : 'Activar avisos'}
      </button>{' '}
      <button className="btn sm" onClick={luego}>Ahora no</button>
    </Aviso>
  )
}

/** Ya hay otra version en el servidor y esta ventana sigue con la anterior. */
function NuevaVersion() {
  const [hay, setHay] = useState(false)
  useEffect(() => vigilarVersion(() => setHay(true)), [])
  if (!hay) return null
  return (
    <Aviso tipo="info">
      Hay una versión nueva de la app.{' '}
      <button className="btn sm primary" onClick={() => window.location.reload()}>Actualizar</button>
    </Aviso>
  )
}

export default function App() {
  const [usuario, setUsuario] = useState(getUser())
  const [avisoSesion, setAvisoSesion] = useState(leerAvisoSesion)
  const navigate = useNavigate()
  const rol = rolPrincipal(usuario)

  // Se lee una vez y se borra: si la persona vuelve a recargar, ya no sale.
  useEffect(() => { borrarAvisoSesion() }, [])

  // El service worker avisa dos cosas: que tocaron un aviso (se abre donde
  // diga) y que llego uno con la app abierta (las pantallas que lo muestran
  // se recargan solas escuchando 'bg:aviso').
  useEffect(() => escucharServiceWorker((m) => {
    if (m.tipo === 'abrir' && m.url) {
      const h = new URL(m.url).hash
      if (h) window.location.hash = h
    } else if (m.tipo === 'aviso') {
      window.dispatchEvent(new CustomEvent('bg:aviso', { detail: m.datos }))
    }
  }), [])

  // Con sesion: si este celular ya tenia los avisos, quedan a nombre de quien
  // esta adentro ahora.
  useEffect(() => {
    if (usuario?.id) sincronizarAvisos()
  }, [usuario?.id])

  // Otra ventana entro con otra cuenta o salio: esta se recarga entera con la
  // sesion que quedo, para que ningun componente se quede con datos de la
  // anterior. Si es la misma persona que volvio a entrar, no pasa nada.
  useEffect(() => alCambiarSesionEnOtraVentana((nuevo) => {
    if (mismaPersona(nuevo, usuario)) return
    dejarAvisoSesion(nuevo
      ? `En otra ventana de este navegador se entró con la cuenta de ${nuevo.nombre}. `
        + 'Esta ventana se cambió a esa cuenta para que nada quede a nombre de otra persona. '
        + 'Para usar dos cuentas a la vez, abre la otra en una ventana de incógnito.'
      : 'Se cerró la sesión en otra ventana de este navegador.')
    window.location.hash = '#/'
    window.location.reload()
  }), [usuario])

  const cerrarAviso = () => setAvisoSesion(null)

  const ubicacion = useLocation()
  const [telLuego, setTelLuego] = useState(() => {
    try { return sessionStorage.getItem(LUEGO_KEY) === '1' } catch { return false }
  })
  const posponerTelefono = () => {
    try { sessionStorage.setItem(LUEGO_KEY, '1') } catch { /* solo dura esta vista */ }
    setTelLuego(true)
  }

  // Los datos guardados al entrar pueden haber envejecido (la carga nocturna pone
  // telefonos, el administrador corrige un nombre): se piden una vez al abrir.
  useEffect(() => {
    if (!usuario) return
    api.get('/auth/me').then((yo) => {
      if (mismaPersona(yo, usuario) && JSON.stringify(yo) !== JSON.stringify(usuario)) {
        setSession(getToken(), yo)
        setUsuario(yo)
      }
    }).catch(() => { /* sin red: se queda con lo guardado */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usuario?.id])

  if (!usuario || !rol) {
    return (
      <>
        <AvisoSesion texto={avisoSesion} onCerrar={cerrarAviso} />
        <Routes>
          <Route path="/login" element={<Login onEntrar={setUsuario} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </>
    )
  }

  const modulo = MODULOS[rol]
  const salir = async () => {
    // ANTES de borrar la sesion: sin token el servidor no deja quitarla, y los
    // avisos de esta cuenta le seguirian llegando a quien use el celular despues.
    await soltarAvisosDeEstaCuenta()
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
          {/* En el telefono, los puestos largos van en corto: «ADMINISTRADOR»
              no cabe junto a los cuatro botones. */}
          <span className="rolechip" title={modulo.titulo}>
            {modulo.corto
              ? <><span className="solo-ancho">{modulo.titulo}</span><span className="solo-angosto">{modulo.corto}</span></>
              : modulo.titulo}
          </span>
          <span className="spacer" />
          <BotonTema />
          <NavLink to="/mis-datos" className="btn sm" title="Mis datos" aria-label="Mis datos">
            <IcoMisDatos size={15} strokeWidth={2} aria-hidden="true" />
          </NavLink>
          <NavLink to="/notificaciones" className="btn sm" title="Notificaciones"
                 aria-label="Notificaciones">
          <IcoCampana size={15} strokeWidth={2} aria-hidden="true" />
        </NavLink>
          <button className="btn sm" onClick={salir} title="Cerrar sesión">Salir</button>
        </header>

        <main className="content">
          <AvisoSesion texto={avisoSesion} onCerrar={cerrarAviso} />
          <NuevaVersion />
          {/* Una invitacion a la vez: primero el celular, que sirve aunque la
              persona nunca abra la app; luego los avisos en este telefono. */}
          {ubicacion.pathname !== '/mis-datos' && (
            !telLuego && pideTelefono(usuario)
              ? <PideTelefono usuario={usuario} onLuego={posponerTelefono} />
              : <PideAvisos usuario={usuario} />
          )}
          <Routes>
            <Route path="/notificaciones" element={<Notificaciones />} />
            <Route path="/mis-datos" element={<MisDatos usuario={usuario} onCambio={setUsuario} />} />
            {/* El libro de bitácora (NOM-030 7.1.10) es UNO para cinco roles:
                vive aquí, como Notificaciones, y no copiado en cada módulo.
                Quién puede ver qué unidad lo decide el servidor. */}
            <Route path="/bitacora" element={<BitacoraUnidad usuario={usuario} />} />
            <Route path="/bitacora/:unidadId" element={<BitacoraUnidad usuario={usuario} />} />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/*" element={<modulo.Componente usuario={usuario} />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
