import { useState } from 'react'
import { login } from '../api.js'
import { Aviso, Card } from '../components/ui.jsx'

const DEMO = [
  ['gerente@bajagas.mx', 'Gerente', 'Tablero, aprobación de presupuestos'],
  ['admin@bajagas.mx', 'Administrador de taller', 'Espacios, colas, captura del mecánico'],
  ['supervisor@bajagas.mx', 'Supervisor', 'Cuadrilla y préstamos'],
  ['chofer1@bajagas.mx', 'Chofer — Luis', 'Titular de la U-101'],
  ['chofer2@bajagas.mx', 'Chofer — Ana', 'Recibe unidades prestadas'],
  ['montacargas@bajagas.mx', 'Montacarguista', 'Arrastres'],
]

export default function Login({ onEntrar }) {
  const [email, setEmail] = useState('gerente@bajagas.mx')
  const [password, setPassword] = useState('demo1234')
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(false)

  const enviar = async (e) => {
    e.preventDefault()
    setCargando(true)
    setError(null)
    try {
      onEntrar(await login(email, password))
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div style={{ textAlign: 'center', marginBottom: 18 }}>
          <h1>Baja Gas</h1>
          <p style={{ color: 'var(--ink-2)', fontSize: '.88rem' }}>
            Gestión de Flota y Taller
          </p>
        </div>

        <Card>
          <form onSubmit={enviar}>
            <Aviso tipo="err">{error}</Aviso>
            <div className="field">
              <label htmlFor="email">Correo</label>
              <input id="email" type="email" value={email} autoComplete="username"
                     onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="pwd">Contraseña</label>
              <input id="pwd" type="password" value={password} autoComplete="current-password"
                     onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button className="btn primary block" disabled={cargando}>
              {cargando ? 'Entrando…' : 'Entrar'}
            </button>
          </form>
        </Card>

        <Card title="Usuarios de prueba" sub="Todos usan la contraseña demo1234">
          <div className="demo-users">
            {DEMO.map(([correo, rol, desc]) => (
              <button key={correo} type="button"
                      onClick={() => { setEmail(correo); setPassword('demo1234') }}>
                <strong>{rol}</strong><br />
                <span style={{ color: 'var(--muted)' }}>{desc}</span>
              </button>
            ))}
          </div>
          <p className="rule">
            Los mecánicos no aparecen: no usan la aplicación (v1.1). Existen como catálogo
            asignable y el administrador captura su trabajo.
          </p>
        </Card>
      </div>
    </div>
  )
}
